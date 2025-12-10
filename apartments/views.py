import json
import logging
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .distance_service import (
    calculate_and_cache_distances,
    get_apartments_with_distances,
    recalculate_distances_for_favorite_place,
)
from .forms import ApartmentForm, CustomUserCreationForm, FavoritePlaceForm, LoginForm, UserPreferencesForm
from .geocoding_service import get_geocoding_service
from .google_maps_service import get_google_maps_service
from .models import (
    Apartment,
    FavoritePlace,
    Plan,
    UserPreferences,
    UserProfile,
    can_add_favorite_place,
    get_favorite_place_limit,
    get_user_item_limit,
    user_has_premium,
)
from .scoring_service import ScoringService, recalculate_user_scores

logger = logging.getLogger(__name__)

# Product slug for this app
PRODUCT_SLUG = "apartments"


def get_or_create_profile(user):
    """Get or create UserProfile for a user"""
    profile, created = UserProfile.objects.get_or_create(user=user)
    return profile


def main_homepage(request):
    """Main landing page showcasing all comparison tools"""
    context = {}

    # Check if user has apartments to show appropriate CTA
    if request.user.is_authenticated:
        apartment_count = Apartment.objects.filter(user=request.user).count()
        context["apartment_count"] = apartment_count
        context["has_apartments"] = apartment_count > 0

    return render(request, "home.html", context)


def homes_coming_soon(request):
    """Placeholder for homes comparison tool"""
    return render(
        request,
        "coming_soon.html",
        {
            "tool_name": "Home Comparison",
            "tool_description": "Compare homes for purchase by price, features, location, and more.",
            "icon_path": "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
        },
    )


def hotels_coming_soon(request):
    """Placeholder for hotels comparison tool"""
    return render(
        request,
        "coming_soon.html",
        {
            "tool_name": "Hotel Comparison",
            "tool_description": "Compare hotels by price, amenities, location, and reviews.",
            "icon_path": "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
        },
    )


def calculate_net_effective_price(apt_data, discount_calculation="weekly"):
    """Calculate net effective price for session apartments"""
    price = Decimal(str(apt_data.get("price", 0)))
    lease_length_months = apt_data.get("lease_length_months", 12)
    months_free = apt_data.get("months_free", 0)
    weeks_free = apt_data.get("weeks_free", 0)
    flat_discount = Decimal(str(apt_data.get("flat_discount", 0)))

    total_discount = Decimal("0")

    if discount_calculation == "daily":
        daily_rate = price * Decimal("12") / Decimal("365")
        if months_free > 0:
            days_free_from_months = Decimal(str(months_free)) * Decimal("365") / Decimal("12")
            total_discount += daily_rate * days_free_from_months
        if weeks_free > 0:
            total_discount += daily_rate * Decimal("7") * Decimal(str(weeks_free))
    elif discount_calculation == "weekly":
        weekly_rate = price * Decimal("12") / Decimal("52")
        if months_free > 0:
            weeks_free_from_months = Decimal(str(months_free)) * Decimal("52") / Decimal("12")
            total_discount += weekly_rate * weeks_free_from_months
        if weeks_free > 0:
            total_discount += weekly_rate * Decimal(str(weeks_free))
    else:  # monthly
        if months_free > 0:
            total_discount += price * Decimal(str(months_free))
        if weeks_free > 0:
            total_discount += price * Decimal(str(weeks_free / 4))

    total_discount += flat_discount
    total_lease_value = price * Decimal(str(lease_length_months))
    net_price = (total_lease_value - total_discount) / Decimal(str(lease_length_months))
    return float(round(net_price, 2))


def index(request):
    """Homepage - landing page with form and features"""
    if request.user.is_authenticated:
        apartments = Apartment.objects.filter(user=request.user)
        apartment_count = apartments.count()
        item_limit = get_user_item_limit(request.user, PRODUCT_SLUG)
        can_add_apartment = apartment_count < item_limit
    else:
        apartment_count = 0
        can_add_apartment = True  # JavaScript will enforce the limit

    context = {
        "can_add_apartment": can_add_apartment,
        "is_anonymous": not request.user.is_authenticated,
        "apartment_count": apartment_count,
    }
    return render(request, "apartments/index.html", context)


def dashboard(request):
    """Dashboard view showing user's apartments in table/card format"""
    favorite_places = []

    if request.user.is_authenticated:
        # Use select_related to prefetch user and preferences in one query (avoid N+1)
        apartments = list(
            Apartment.objects.filter(user=request.user).select_related("user__preferences").order_by("-created_at")
        )
        favorite_places = list(FavoritePlace.objects.filter(user=request.user))
        preferences, _ = UserPreferences.objects.get_or_create(
            user=request.user,
            defaults={"price_weight": 50, "sqft_weight": 50, "distance_weight": 50, "discount_calculation": "weekly"},
        )
    else:
        apartments = []
        session_prefs = request.session.get("anonymous_preferences", {})
        if session_prefs:

            class SessionPreferences:
                def __init__(self, data):
                    self.price_weight = data.get("price_weight", 50)
                    self.sqft_weight = data.get("sqft_weight", 50)
                    self.distance_weight = data.get("distance_weight", 50)
                    self.discount_calculation = data.get("discount_calculation", "weekly")

            preferences = SessionPreferences(session_prefs)
        else:
            preferences = None

    # Handle preferences form submission
    if request.method == "POST":
        form = UserPreferencesForm(request.POST)
        if form.is_valid():
            preferences_data = {
                "price_weight": form.cleaned_data["price_weight"],
                "sqft_weight": form.cleaned_data["sqft_weight"],
                "distance_weight": form.cleaned_data["distance_weight"],
                "net_rent_weight": form.cleaned_data.get("net_rent_weight", 0),
                "total_cost_weight": form.cleaned_data.get("total_cost_weight", 0),
                "bedrooms_weight": form.cleaned_data.get("bedrooms_weight", 0),
                "bathrooms_weight": form.cleaned_data.get("bathrooms_weight", 0),
                "discount_weight": form.cleaned_data.get("discount_weight", 0),
                "parking_weight": form.cleaned_data.get("parking_weight", 0),
                "utilities_weight": form.cleaned_data.get("utilities_weight", 0),
                "view_weight": form.cleaned_data.get("view_weight", 0),
                "balcony_weight": form.cleaned_data.get("balcony_weight", 0),
                "discount_calculation": form.cleaned_data["discount_calculation"],
                "price_per_sqft_basis": form.cleaned_data.get("price_per_sqft_basis", "net_effective"),
                "pricing_sort_basis": form.cleaned_data.get("pricing_sort_basis", "base"),
                "factor_order": form.cleaned_data.get(
                    "factor_order",
                    "price,sqft,distance,netRent,totalCost,bedrooms,bathrooms,discount,parking,utilities,view,balcony",
                ),
            }

            if request.user.is_authenticated:
                UserPreferences.objects.update_or_create(user=request.user, defaults=preferences_data)
                # Recalculate scores when preferences change
                recalculate_user_scores(request.user, PRODUCT_SLUG)
            else:
                request.session["anonymous_preferences"] = preferences_data
                request.session.modified = True

            messages.success(request, "Preferences updated successfully!")
            return redirect("apartments:dashboard")
    else:
        initial_data = {}
        if preferences:
            initial_data = {
                "price_weight": preferences.price_weight,
                "sqft_weight": preferences.sqft_weight,
                "distance_weight": preferences.distance_weight,
                "net_rent_weight": getattr(preferences, "net_rent_weight", 0),
                "total_cost_weight": getattr(preferences, "total_cost_weight", 0),
                "bedrooms_weight": getattr(preferences, "bedrooms_weight", 0),
                "bathrooms_weight": getattr(preferences, "bathrooms_weight", 0),
                "discount_weight": getattr(preferences, "discount_weight", 0),
                "parking_weight": getattr(preferences, "parking_weight", 0),
                "utilities_weight": getattr(preferences, "utilities_weight", 0),
                "view_weight": getattr(preferences, "view_weight", 0),
                "balcony_weight": getattr(preferences, "balcony_weight", 0),
                "discount_calculation": preferences.discount_calculation,
                "factor_order": getattr(
                    preferences,
                    "factor_order",
                    "price,sqft,distance,netRent,totalCost,bedrooms,bathrooms,discount,parking,utilities,view,balcony",
                ),
            }
        form = UserPreferencesForm(initial=initial_data)

    # Calculate net effective price for each apartment
    discount_calc_method = preferences.discount_calculation if preferences else "weekly"
    for apartment in apartments:
        # For Django model apartments, use the property
        if hasattr(apartment, "net_effective_price"):
            apartment.calculated_net_effective = apartment.net_effective_price
        else:
            apt_data = {
                "price": getattr(apartment, "price", 0),
                "lease_length_months": getattr(apartment, "lease_length_months", 12),
                "months_free": getattr(apartment, "months_free", 0),
                "weeks_free": getattr(apartment, "weeks_free", 0),
                "flat_discount": getattr(apartment, "flat_discount", 0),
            }
            apartment.calculated_net_effective = calculate_net_effective_price(apt_data, discount_calc_method)

    # Calculate apartment scores
    apartment_scores = {}
    score_breakdowns = {}
    if apartments and request.user.is_authenticated:
        scoring_service = ScoringService(request.user, apartments, PRODUCT_SLUG)
        apartment_scores = scoring_service.get_or_calculate_scores()
        score_breakdowns = scoring_service.get_all_score_breakdowns()

        # Attach scores and breakdowns to apartments for template use
        for apartment in apartments:
            apartment.score = apartment_scores.get(apartment.id)
            apartment.score_breakdown = score_breakdowns.get(apartment.id)

    # Sort apartments by score (highest first) if scores available, otherwise use old sorting
    if apartment_scores:
        apartments = sorted(
            apartments,
            key=lambda x: apartment_scores.get(x.id, 0),
            reverse=True,
        )
    elif preferences and apartments:
        # Fallback to old sorting method
        apartments = sorted(
            apartments,
            key=lambda x: (
                (float(x.net_effective_price) * preferences.price_weight)
                + (x.square_footage * preferences.sqft_weight)
                + (0 * preferences.distance_weight)
            ),
            reverse=True,
        )

    has_premium = user_has_premium(request.user, PRODUCT_SLUG) if request.user.is_authenticated else False
    item_limit = get_user_item_limit(request.user, PRODUCT_SLUG) if request.user.is_authenticated else 2
    can_add_apartment = len(apartments) < item_limit

    has_discounts = any(
        (
            getattr(apt, "months_free", 0) > 0
            or getattr(apt, "weeks_free", 0) > 0
            or getattr(apt, "flat_discount", 0) > 0
        )
        for apt in apartments
    )

    # Check which optional fields have data (for conditional column display)
    has_parking = any(getattr(apt, "parking_cost", 0) > 0 for apt in apartments)
    has_utilities = any(getattr(apt, "utilities", 0) > 0 for apt in apartments)
    has_view_ratings = any(getattr(apt, "view_quality", 0) > 0 for apt in apartments)
    has_balcony = any(getattr(apt, "has_balcony", False) for apt in apartments)
    # Show total cost column if any apartment has parking or utilities
    has_additional_costs = has_parking or has_utilities
    # Show beds/baths column only if there's variation among apartments
    if len(apartments) > 1:
        bed_bath_combos = {(apt.bedrooms, apt.bathrooms) for apt in apartments}
        has_beds_baths_variation = len(bed_bath_combos) > 1
    else:
        has_beds_baths_variation = False

    # Get distance data for apartments
    apartments_with_distances = []
    apartments_needing_distances = []
    if favorite_places and apartments:
        # Check for apartments with missing distance calculations (single query)
        from django.db.models import Count

        from .models import ApartmentDistance

        geocoded_places = [p for p in favorite_places if p.latitude and p.longitude]
        expected_count = len(geocoded_places)

        if expected_count > 0:
            # Get distance counts for all apartments in one query
            apt_ids_with_coords = [apt.id for apt in apartments if apt.latitude and apt.longitude]
            if apt_ids_with_coords:
                distance_counts = dict(
                    ApartmentDistance.objects.filter(apartment_id__in=apt_ids_with_coords)
                    .values("apartment_id")
                    .annotate(count=Count("id"))
                    .values_list("apartment_id", "count")
                )
                # Identify apartments that need distance calculation (done async via JS)
                for apt in apartments:
                    if apt.id in apt_ids_with_coords:
                        actual_count = distance_counts.get(apt.id, 0)
                        if actual_count < expected_count:
                            apartments_needing_distances.append(apt.id)

        apartments_with_distances = get_apartments_with_distances(apartments, favorite_places)
        # Add distance data to apartment objects for template access
        for apt_data in apartments_with_distances:
            apt = apt_data["apartment"]
            apt.distance_data = apt_data["distances"]
            apt.average_distance = apt_data["average_distance"]
            apt.average_travel_time = apt_data.get("average_travel_time")
    else:
        # No favorite places, just set empty distance data
        for apt in apartments:
            apt.distance_data = {}
            apt.average_distance = None
            apt.average_travel_time = None

    # Get favorite place stats for the user
    favorite_place_count = len(favorite_places)
    favorite_place_limit = get_favorite_place_limit(request.user, PRODUCT_SLUG) if request.user.is_authenticated else 1
    can_add_favorite_place_flag = (
        can_add_favorite_place(request.user, PRODUCT_SLUG) if request.user.is_authenticated else False
    )

    # Get the lowest monthly price for upgrade banner
    monthly_plan = (
        Plan.objects.filter(
            product__slug=PRODUCT_SLUG,
            tier="pro",
            billing_interval="month",
            is_active=True,
        )
        .order_by("price_amount")
        .first()
    )
    monthly_price = monthly_plan.price_amount if monthly_plan else None

    context = {
        "apartments": apartments,
        "preferences": preferences,
        "form": form,
        "is_premium": has_premium,
        "can_add_apartment": can_add_apartment,
        "apartment_count": len(apartments),
        "apartment_limit": item_limit,
        "is_anonymous": not request.user.is_authenticated,
        "has_discounts": has_discounts,
        "has_parking": has_parking,
        "has_utilities": has_utilities,
        "has_view_ratings": has_view_ratings,
        "has_balcony": has_balcony,
        "has_additional_costs": has_additional_costs,
        "has_beds_baths_variation": has_beds_baths_variation,
        "favorite_places": favorite_places,
        "favorite_place_count": favorite_place_count,
        "favorite_place_limit": favorite_place_limit,
        "can_add_favorite_place": can_add_favorite_place_flag,
        "apartments_needing_distances": apartments_needing_distances,
        "monthly_price": monthly_price,
    }
    return render(request, "apartments/dashboard.html", context)


def create_apartment(request):
    if request.method == "POST":
        form = ApartmentForm(request.POST)
        logger.debug(f"Form data: {request.POST}")
        if form.is_valid():
            logger.debug("Form is valid")

            if not request.user.is_authenticated:
                return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

            # Check tier limit
            current_count = Apartment.objects.filter(user=request.user).count()
            item_limit = get_user_item_limit(request.user, PRODUCT_SLUG)
            if current_count >= item_limit:
                has_premium = user_has_premium(request.user, PRODUCT_SLUG)
                if has_premium:
                    messages.error(
                        request,
                        f"You've reached the limit of {item_limit} apartments. Please remove one to add another.",
                    )
                else:
                    messages.error(
                        request,
                        "Free tier limit reached. Upgrade to Pro to add more apartments.",
                    )
                return redirect("apartments:index")

            try:
                address = form.cleaned_data.get("address", "")
                latitude, longitude = None, None
                geocode_warning = None

                # Check if we have pre-fetched coordinates from Google Places
                google_lat = request.POST.get("google_latitude", "").strip()
                google_lng = request.POST.get("google_longitude", "").strip()

                if google_lat and google_lng:
                    # Use coordinates from Google Places (user selected from dropdown)
                    try:
                        latitude = float(google_lat)
                        longitude = float(google_lng)
                        logger.info(f"Using Google Places coordinates for apartment: ({latitude}, {longitude})")
                    except ValueError:
                        logger.warning("Invalid Google coordinates received from POST data.")
                elif address:
                    # Fall back to geocoding (user typed address manually)
                    geocoding_service = get_geocoding_service()
                    result = geocoding_service.geocode_address_detailed(address)
                    latitude, longitude = result.latitude, result.longitude
                    if not result.success:
                        logger.warning(f"Could not geocode address: {address}")
                        geocode_warning = result.suggestion

                apartment = Apartment.objects.create(
                    user=request.user,
                    name=form.cleaned_data["name"],
                    address=address,
                    latitude=latitude,
                    longitude=longitude,
                    price=form.cleaned_data["price"],
                    square_footage=form.cleaned_data["square_footage"],
                    bedrooms=form.cleaned_data["bedrooms"],
                    bathrooms=form.cleaned_data["bathrooms"],
                    lease_length_months=form.cleaned_data["lease_length_months"],
                    months_free=form.cleaned_data["months_free"],
                    weeks_free=form.cleaned_data["weeks_free"],
                    flat_discount=form.cleaned_data["flat_discount"],
                    parking_cost=form.cleaned_data.get("parking_cost", Decimal("0")),
                    utilities=form.cleaned_data.get("utilities", Decimal("0")),
                    view_quality=int(form.cleaned_data.get("view_quality", 0)),
                    has_balcony=form.cleaned_data.get("has_balcony", False),
                )

                # Calculate distances to favorite places
                if apartment.latitude and apartment.longitude:
                    calculate_and_cache_distances(apartment)

                # Recalculate scores for all apartments
                recalculate_user_scores(request.user, PRODUCT_SLUG)

                if geocode_warning:
                    # Check if user is on free tier to suggest upgrade
                    has_premium = user_has_premium(request.user, PRODUCT_SLUG)
                    if has_premium:
                        messages.warning(
                            request,
                            f"Apartment added, but couldn't locate the address. {geocode_warning} "
                            "You can edit the apartment to update the address.",
                        )
                    else:
                        messages.warning(
                            request,
                            "Apartment added, but we couldn't locate the address in our free database. "
                            "Distance calculations and location-based scoring won't work for this apartment. "
                            "You can edit the apartment to try a different address format, "
                            "or upgrade to Pro for Google Maps address lookup which supports more addresses.",
                        )
                elif not address:
                    # No address was entered at all
                    messages.success(
                        request,
                        "Apartment added! Tip: Add an address to enable distance calculations and location-based scoring.",
                    )
                else:
                    messages.success(request, "Apartment added successfully!")
                return redirect("apartments:dashboard")
            except IntegrityError:
                logger.warning(f"Duplicate apartment name attempted: {form.cleaned_data['name']}")
                form.add_error("name", "You already have an apartment with this name. Please choose a different name.")
            except Exception as e:
                logger.error(f"Error saving apartment: {str(e)}")
                messages.error(request, "An error occurred while saving the apartment.")
        else:
            logger.error(f"Form errors: {form.errors}")
            messages.error(request, "Please correct the errors below.")
    else:
        form = ApartmentForm()

    return render(request, "apartments/apartment_form.html", {"form": form})


@login_required
def update_apartment(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk, user=request.user)

    if request.method == "POST":
        form = ApartmentForm(request.POST)
        if form.is_valid():
            new_address = form.cleaned_data.get("address", "")
            address_changed = new_address != apartment.address

            apartment.name = form.cleaned_data["name"]
            apartment.address = new_address
            apartment.price = form.cleaned_data["price"]
            apartment.square_footage = form.cleaned_data["square_footage"]
            apartment.bedrooms = form.cleaned_data["bedrooms"]
            apartment.bathrooms = form.cleaned_data["bathrooms"]
            apartment.lease_length_months = form.cleaned_data["lease_length_months"]
            apartment.months_free = form.cleaned_data["months_free"]
            apartment.weeks_free = form.cleaned_data["weeks_free"]
            apartment.flat_discount = form.cleaned_data["flat_discount"]
            apartment.parking_cost = form.cleaned_data.get("parking_cost", Decimal("0"))
            apartment.utilities = form.cleaned_data.get("utilities", Decimal("0"))
            apartment.view_quality = int(form.cleaned_data.get("view_quality", 0))
            apartment.has_balcony = form.cleaned_data.get("has_balcony", False)

            # Re-geocode if address changed
            geocode_warning = None
            if address_changed:
                if new_address:
                    # Check if we have pre-fetched coordinates from Google Places
                    google_lat = request.POST.get("google_latitude", "").strip()
                    google_lng = request.POST.get("google_longitude", "").strip()

                    if google_lat and google_lng:
                        # Use coordinates from Google Places
                        try:
                            apartment.latitude = float(google_lat)
                            apartment.longitude = float(google_lng)
                            logger.info("Using Google Places coordinates for apartment update.")
                        except ValueError:
                            logger.warning("Invalid Google coordinates received during apartment update.")
                            apartment.latitude = None
                            apartment.longitude = None
                    else:
                        # Fall back to geocoding
                        geocoding_service = get_geocoding_service()
                        result = geocoding_service.geocode_address_detailed(new_address)
                        apartment.latitude = result.latitude
                        apartment.longitude = result.longitude
                        if not result.success:
                            logger.warning(f"Could not geocode address: {new_address}")
                            geocode_warning = result.suggestion
                else:
                    apartment.latitude = None
                    apartment.longitude = None

            try:
                apartment.save()

                # Recalculate distances if address changed
                if address_changed and apartment.latitude and apartment.longitude:
                    calculate_and_cache_distances(apartment)

                # Recalculate scores for all apartments since data changed
                recalculate_user_scores(request.user, PRODUCT_SLUG)

                if geocode_warning:
                    # Check if user is on free tier to suggest upgrade
                    has_premium = user_has_premium(request.user, PRODUCT_SLUG)
                    if has_premium:
                        messages.warning(
                            request,
                            f"Apartment updated, but couldn't locate the new address. {geocode_warning}",
                        )
                    else:
                        messages.warning(
                            request,
                            "Apartment updated, but we couldn't locate the address in our free database. "
                            "Distance calculations and location-based scoring won't work for this apartment. "
                            "Try a different address format, "
                            "or upgrade to Pro for Google Maps address lookup which supports more addresses.",
                        )
                elif not new_address and not apartment.latitude:
                    # Address was removed or never set
                    messages.success(
                        request,
                        "Apartment updated! Tip: Add an address to enable distance calculations and location-based scoring.",
                    )
                else:
                    messages.success(request, "Apartment updated successfully!")
                return redirect("apartments:dashboard")
            except IntegrityError:
                logger.warning(f"Duplicate apartment name attempted on update: {form.cleaned_data['name']}")
                form.add_error("name", "You already have an apartment with this name. Please choose a different name.")
    else:
        initial_data = {
            "name": apartment.name,
            "address": apartment.address,
            "price": apartment.price,
            "square_footage": apartment.square_footage,
            "lease_length_months": apartment.lease_length_months,
            "months_free": apartment.months_free,
            "weeks_free": apartment.weeks_free,
            "flat_discount": apartment.flat_discount,
        }
        form = ApartmentForm(initial=initial_data)

    return render(request, "apartments/apartment_form.html", {"form": form})


def delete_apartment(request, pk):
    """Delete an apartment - handles both authenticated users and anonymous session apartments"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    # Check if this is a session apartment (starts with "session_")
    if str(pk).startswith("session_"):
        # Anonymous user deleting session apartment - handled by JavaScript
        return JsonResponse({"success": True})
    else:
        if not request.user.is_authenticated:
            return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

        apartment = get_object_or_404(Apartment, pk=pk, user=request.user)
        apartment.delete()

        # Recalculate scores for remaining apartments
        recalculate_user_scores(request.user, PRODUCT_SLUG)

        messages.success(request, "Apartment deleted successfully!")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            remaining_count = Apartment.objects.filter(user=request.user).count()
            return JsonResponse({"success": True, "remaining_count": remaining_count})

        remaining_apartments = Apartment.objects.filter(user=request.user).exists()
        if remaining_apartments:
            return redirect("apartments:dashboard")
        else:
            return redirect("apartments:index")


@login_required
def update_preferences(request):
    preferences, _ = UserPreferences.objects.get_or_create(
        user=request.user,
        defaults={"price_weight": 50, "sqft_weight": 50, "distance_weight": 50, "discount_calculation": "weekly"},
    )

    if request.method == "POST":
        form = UserPreferencesForm(request.POST)
        if form.is_valid():
            preferences.price_weight = form.cleaned_data["price_weight"]
            preferences.sqft_weight = form.cleaned_data["sqft_weight"]
            preferences.distance_weight = form.cleaned_data["distance_weight"]
            preferences.discount_calculation = form.cleaned_data["discount_calculation"]
            preferences.price_per_sqft_basis = form.cleaned_data.get("price_per_sqft_basis", "net_effective")
            preferences.pricing_sort_basis = form.cleaned_data.get("pricing_sort_basis", "base")
            preferences.save()
            messages.success(request, "Preferences updated successfully!")
            return redirect("apartments:index")
    else:
        initial_data = {
            "price_weight": preferences.price_weight,
            "sqft_weight": preferences.sqft_weight,
            "distance_weight": preferences.distance_weight,
            "discount_calculation": preferences.discount_calculation,
            "price_per_sqft_basis": getattr(preferences, "price_per_sqft_basis", "net_effective"),
            "pricing_sort_basis": getattr(preferences, "pricing_sort_basis", "base"),
        }
        form = UserPreferencesForm(initial=initial_data)

    return render(request, "apartments/preferences_form.html", {"form": form})


@require_http_methods(["POST"])
def transfer_apartments(request):
    """Transfer apartments from sessionStorage to database after user signs up"""
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

    try:
        data = json.loads(request.body)
        apartments = data.get("apartments", [])

        transferred_count = 0

        for apartment in apartments:
            try:
                Apartment.objects.create(
                    user=request.user,
                    name=apartment["name"],
                    price=Decimal(str(apartment["price"])),
                    square_footage=int(apartment["square_footage"]),
                    lease_length_months=int(apartment.get("lease_length_months", 12)),
                    months_free=int(apartment.get("months_free", 0)),
                    weeks_free=int(apartment.get("weeks_free", 0)),
                    flat_discount=Decimal(str(apartment.get("flat_discount", 0))),
                )
                transferred_count += 1
            except Exception as e:
                logger.error(f"Error transferring apartment: {e}")

        return JsonResponse({"success": True, "transferred_count": transferred_count})
    except Exception as e:
        logger.error(f"Error in transfer_apartments: {e}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def signup_view(request):
    """Handle user registration"""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                # Create UserProfile for the new user
                UserProfile.objects.get_or_create(user=user)
                # Specify backend since we have multiple auth backends
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")

                messages.success(
                    request,
                    f"Welcome {user.first_name or user.username}! Your account has been created successfully.",
                )

                from django.utils.http import url_has_allowed_host_and_scheme

                next_url = request.POST.get("next") or request.GET.get("next")

                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                else:
                    return redirect("home")
            except Exception as e:
                logger.error(f"Error creating user: {e}")
                messages.error(
                    request,
                    "An error occurred while creating your account. Please try again.",
                )
    else:
        form = CustomUserCreationForm()

    apartment_count = 0

    # Auto-sync plans from Stripe (creates/updates Product and Plan records)
    from .stripe_service import StripeService

    synced_plans = StripeService.sync_plans_from_stripe(PRODUCT_SLUG)
    monthly_plan = synced_plans.get("monthly")
    annual_plan = synced_plans.get("annual")
    lifetime_plan = synced_plans.get("lifetime")

    # Fetch live prices from Stripe
    if monthly_plan:
        monthly_price_data = StripeService.get_price_from_stripe(
            monthly_plan.stripe_price_id, fallback_amount=float(monthly_plan.price_amount)
        )
        monthly_price = monthly_price_data["amount"]
        monthly_interval = monthly_price_data["interval"] or "month"
    else:
        monthly_price = 5.00
        monthly_interval = "month"

    if annual_plan:
        annual_price_data = StripeService.get_price_from_stripe(
            annual_plan.stripe_price_id, fallback_amount=float(annual_plan.price_amount)
        )
        annual_price = annual_price_data["amount"]
        annual_interval = annual_price_data["interval"] or "year"
    else:
        annual_price = 50.00
        annual_interval = "year"

    if lifetime_plan:
        lifetime_price_data = StripeService.get_price_from_stripe(
            lifetime_plan.stripe_price_id, fallback_amount=float(lifetime_plan.price_amount)
        )
        lifetime_price = lifetime_price_data["amount"]
    else:
        lifetime_price = None

    annual_savings = (monthly_price * 12) - annual_price

    next_url = request.GET.get("next", "")

    context = {
        "form": form,
        "apartment_count": apartment_count,
        "has_apartments_to_save": apartment_count > 0,
        "monthly_price": monthly_price,
        "annual_price": annual_price,
        "lifetime_price": lifetime_price,
        "monthly_interval": monthly_interval,
        "annual_interval": annual_interval,
        "annual_savings": annual_savings,
        "monthly_plan_id": monthly_plan.id if monthly_plan else None,
        "annual_plan_id": annual_plan.id if annual_plan else None,
        "lifetime_plan_id": lifetime_plan.id if lifetime_plan else None,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
        "stripe_enabled": settings.STRIPE_ENABLED,
        "next": next_url,
        "google_client_id": getattr(settings, "SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", ""),
    }

    return render(request, "apartments/signup.html", context)


def login_view(request):
    """Handle user login"""
    from django.conf import settings

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")

                from django.utils.http import url_has_allowed_host_and_scheme

                next_url = request.POST.get("next") or request.GET.get("next")

                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                else:
                    return redirect("home")
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    next_url = request.GET.get("next", "")
    # Store next URL in session for OAuth flow
    if next_url:
        request.session["oauth_next"] = next_url
    return render(
        request,
        "apartments/login.html",
        {
            "form": form,
            "next": next_url,
            "debug": settings.DEBUG,
            "google_client_id": getattr(settings, "SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", ""),
        },
    )


def logout_view(request):
    """Handle user logout with GET and POST requests"""
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect("apartments:index")


def google_oauth_callback(request):
    """Handle Google OAuth callback and redirect after social auth"""
    if request.user.is_authenticated:
        logger.info(f"OAuth callback successful for user: {request.user.username}")
        messages.success(request, f"Welcome back, {request.user.username}!")

        from django.utils.http import url_has_allowed_host_and_scheme

        next_url = request.session.get("oauth_next")

        if "oauth_next" in request.session:
            del request.session["oauth_next"]

        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        else:
            return redirect("home")
    else:
        logger.warning("OAuth callback failed - user not authenticated")
        messages.error(request, "Authentication failed. Please try again.")
        return redirect("login")


def privacy_policy(request):
    """Display privacy policy page"""
    from datetime import datetime

    return render(request, "apartments/privacy.html", {"current_date": datetime.now().strftime("%B %d, %Y")})


def terms_of_service(request):
    """Display terms of service page"""
    from datetime import datetime

    return render(request, "apartments/terms.html", {"current_date": datetime.now().strftime("%B %d, %Y")})


def robots_txt(request):
    """Generate robots.txt file dynamically"""
    from django.http import HttpResponse

    protocol = "https" if request.is_secure() else "http"
    host = request.get_host()
    sitemap_url = f"{protocol}://{host}/sitemap.xml"

    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        f"Sitemap: {sitemap_url}",
    ]

    return HttpResponse("\n".join(lines), content_type="text/plain")


# Subscription Views


def pricing_redirect(request):
    """Redirect pricing page to signup page (all pricing info is on signup page)"""
    return redirect("signup")


@login_required
def create_checkout_session(request):
    """Create a Stripe checkout session for subscription"""
    import stripe as stripe_lib

    from .models import Product
    from .stripe_service import StripeService

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
        plan_id = data.get("plan_id")
        plan_type = data.get("plan_type")  # 'monthly', 'annual', or 'lifetime'

        # If plan_type is provided, look up the plan by type
        if plan_type and not plan_id:
            try:
                product = Product.objects.get(slug=PRODUCT_SLUG)
                # Map plan_type to billing_interval
                interval_map = {"monthly": "month", "annual": "year", "lifetime": "lifetime"}
                billing_interval = interval_map.get(plan_type)
                if not billing_interval:
                    return JsonResponse({"error": f"Invalid plan type: {plan_type}"}, status=400)
                plan = Plan.objects.get(product=product, tier="pro", billing_interval=billing_interval, is_active=True)
                plan_id = plan.id
            except (Product.DoesNotExist, Plan.DoesNotExist):
                return JsonResponse({"error": f"No {plan_type} plan found for this product"}, status=400)

        if not plan_id:
            return JsonResponse({"error": "Plan ID or plan type is required"}, status=400)

        # Verify plan exists and is active
        try:
            plan = Plan.objects.get(id=plan_id, is_active=True, tier="pro")
        except Plan.DoesNotExist:
            return JsonResponse({"error": "Invalid plan"}, status=400)

        success_url = request.build_absolute_uri("/apartments/subscription/success/")
        cancel_url = request.build_absolute_uri("/apartments/subscription/cancel/")

        stripe_service = StripeService()
        session = stripe_service.create_checkout_session(
            user=request.user, plan_id=plan_id, success_url=success_url, cancel_url=cancel_url
        )

        return JsonResponse({"sessionId": session.id})

    except stripe_lib.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@login_required
def checkout_success(request):
    """Handle successful checkout"""
    messages.success(request, "Thank you for subscribing! Your premium access is now active.")
    return redirect("apartments:dashboard")


@login_required
def checkout_cancel(request):
    """Handle cancelled checkout"""
    messages.info(request, "Checkout cancelled. You can upgrade to premium anytime.")
    return redirect("apartments:pricing")


@login_required
def billing_portal(request):
    """Redirect to Stripe billing portal for subscription management"""
    import stripe as stripe_lib

    from .stripe_service import StripeService

    try:
        stripe_service = StripeService()
        return_url = request.build_absolute_uri("/apartments/dashboard/")

        session = stripe_service.create_billing_portal_session(user=request.user, return_url=return_url)

        return redirect(session.url)

    except ValueError:
        messages.error(request, "You don't have an active subscription.")
        return redirect("apartments:pricing")
    except stripe_lib.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        messages.error(request, "Unable to access billing portal. Please try again.")
        return redirect("apartments:dashboard")
    except Exception as e:
        logger.error(f"Error creating billing portal session: {e}")
        messages.error(request, "An error occurred. Please try again.")
        return redirect("apartments:dashboard")


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """Handle Stripe webhook events"""
    import stripe as stripe_lib

    from .stripe_service import StripeService

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe_lib.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except ValueError:
        logger.error("Invalid webhook payload")
        return JsonResponse({"error": "Invalid payload"}, status=400)
    except stripe_lib.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        return JsonResponse({"error": "Invalid signature"}, status=400)

    stripe_service = StripeService()
    event_type = event["type"]

    try:
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]
            subscription_id = session.get("subscription")

            if subscription_id:
                # Recurring subscription
                subscription = stripe_lib.Subscription.retrieve(subscription_id)
                stripe_service.sync_subscription_status(subscription)
                logger.info(f"Checkout completed: {subscription_id}")
            else:
                # One-time payment (lifetime plan)
                metadata = session.get("metadata", {})
                user_id = metadata.get("user_id")
                plan_id = metadata.get("plan_id")

                if user_id and plan_id:
                    from .models import Plan, Subscription

                    try:
                        user = User.objects.get(id=user_id)
                        plan = Plan.objects.get(id=plan_id)

                        # Create subscription record for lifetime plan
                        Subscription.objects.update_or_create(
                            user=user,
                            plan=plan,
                            defaults={
                                "status": "active",
                                "stripe_subscription_id": session.get("payment_intent", ""),
                                "current_period_end": None,  # Lifetime has no end
                                "cancel_at_period_end": False,
                            },
                        )
                        logger.info(f"Lifetime plan activated for user {user_id}, plan {plan_id}")
                    except (User.DoesNotExist, Plan.DoesNotExist) as e:
                        logger.error(f"Error activating lifetime plan: {e}")

        elif event_type == "customer.subscription.updated":
            subscription = event["data"]["object"]
            stripe_service.sync_subscription_status(subscription)
            logger.info(f"Subscription updated: {subscription.id}")

        elif event_type == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            stripe_service.sync_subscription_status(subscription)
            logger.info(f"Subscription deleted: {subscription.id}")

        elif event_type == "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            subscription_id = invoice.get("subscription")

            if subscription_id:
                subscription = stripe_lib.Subscription.retrieve(subscription_id)
                stripe_service.sync_subscription_status(subscription)
                logger.info(f"Payment succeeded for subscription: {subscription_id}")

        elif event_type == "invoice.payment_failed":
            invoice = event["data"]["object"]
            subscription_id = invoice.get("subscription")

            if subscription_id:
                subscription = stripe_lib.Subscription.retrieve(subscription_id)
                stripe_service.sync_subscription_status(subscription)
                logger.warning(f"Payment failed for subscription: {subscription_id}")

        else:
            logger.info(f"Unhandled webhook event type: {event_type}")

    except Exception as e:
        logger.error(f"Error processing webhook event {event_type}: {e}")
        return JsonResponse({"error": "Webhook processing failed"}, status=500)

    return JsonResponse({"status": "success"})


# =============================================================================
# Favorite Places Views
# =============================================================================


@login_required
def favorite_places_list(request):
    """List user's favorite places with management options"""
    has_premium = user_has_premium(request.user, PRODUCT_SLUG)

    # Require premium for location features
    if not has_premium:
        messages.info(request, "Favorite Places with distance calculations is a Pro feature. Upgrade to unlock!")
        return redirect("signup")

    places = FavoritePlace.objects.filter(user=request.user)

    place_count = places.count()
    place_limit = get_favorite_place_limit(request.user, PRODUCT_SLUG)
    can_add = place_count < place_limit

    context = {
        "favorite_places": places,
        "place_count": place_count,
        "place_limit": place_limit,
        "can_add_place": can_add,
        "is_premium": has_premium,
    }
    return render(request, "apartments/favorite_places.html", context)


@login_required
def create_favorite_place(request):
    """Create a new favorite place with geocoding"""
    has_premium = user_has_premium(request.user, PRODUCT_SLUG)

    # Require premium for location features
    if not has_premium:
        messages.info(request, "Favorite Places is a Pro feature. Upgrade to unlock distance calculations!")
        return redirect("signup")

    # Check limit
    if not can_add_favorite_place(request.user, PRODUCT_SLUG):
        messages.error(request, "You've reached the maximum of 5 favorite places.")
        return redirect("apartments:favorite_places")

    if request.method == "POST":
        form = FavoritePlaceForm(request.POST)
        if form.is_valid():
            label = form.cleaned_data["label"]
            address = form.cleaned_data["address"]

            # Check if we have pre-fetched coordinates from Google Places
            google_lat = request.POST.get("google_latitude", "").strip()
            google_lng = request.POST.get("google_longitude", "").strip()

            latitude = None
            longitude = None
            geocode_failed = False

            if google_lat and google_lng:
                # Use coordinates from Google Places (user selected from dropdown)
                try:
                    latitude = float(google_lat)
                    longitude = float(google_lng)
                    logger.info(f"Using Google Places coordinates for '{label}'.")
                except ValueError:
                    logger.warning(f"Invalid Google coordinates received for label '{label}'.")
                    geocode_failed = True

            if latitude is None or longitude is None:
                # Fall back to geocoding (user typed address manually)
                geocoding_service = get_geocoding_service()
                result = geocoding_service.geocode_address_detailed(address)
                latitude = result.latitude
                longitude = result.longitude
                if not result.success:
                    geocode_failed = True

            # Get travel preferences
            travel_mode = form.cleaned_data["travel_mode"]
            time_type = form.cleaned_data["time_type"]
            day_of_week = form.cleaned_data["day_of_week"]
            time_of_day = form.cleaned_data["time_of_day"]

            place = FavoritePlace.objects.create(
                user=request.user,
                label=label,
                address=address,
                latitude=latitude,
                longitude=longitude,
                travel_mode=travel_mode,
                time_type=time_type,
                day_of_week=int(day_of_week),
                time_of_day=time_of_day,
            )

            if geocode_failed or (latitude is None and longitude is None):
                messages.warning(
                    request,
                    f"Added '{label}' but couldn't locate the address. Distance calculations won't be available.",
                )
            else:
                messages.success(request, f"Added '{label}' to your favorite places!")
                # Calculate distances to all apartments
                recalculate_distances_for_favorite_place(place)

            return redirect("apartments:favorite_places")
    else:
        form = FavoritePlaceForm()

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "apartments/favorite_place_form.html", context)


@login_required
def update_favorite_place(request, pk):
    """Update an existing favorite place"""
    has_premium = user_has_premium(request.user, PRODUCT_SLUG)

    # Require premium for location features
    if not has_premium:
        messages.info(request, "Favorite Places is a Pro feature. Upgrade to unlock!")
        return redirect("signup")

    place = get_object_or_404(FavoritePlace, pk=pk, user=request.user)

    if request.method == "POST":
        form = FavoritePlaceForm(request.POST)
        if form.is_valid():
            new_address = form.cleaned_data["address"]
            address_changed = new_address != place.address

            place.label = form.cleaned_data["label"]
            place.address = new_address

            # Update travel preferences
            travel_mode = form.cleaned_data["travel_mode"]
            time_type = form.cleaned_data["time_type"]
            day_of_week = form.cleaned_data["day_of_week"]
            time_of_day = form.cleaned_data["time_of_day"]

            # Check if travel preferences changed
            travel_prefs_changed = (
                place.travel_mode != travel_mode
                or place.time_type != time_type
                or place.day_of_week != int(day_of_week)
                or place.time_of_day != time_of_day
            )

            place.travel_mode = travel_mode
            place.time_type = time_type
            place.day_of_week = int(day_of_week)
            place.time_of_day = time_of_day

            # Re-geocode if address changed
            geocode_failed = False
            if address_changed:
                # Check if we have pre-fetched coordinates from Google Places
                google_lat = request.POST.get("google_latitude", "").strip()
                google_lng = request.POST.get("google_longitude", "").strip()

                if google_lat and google_lng:
                    # Use coordinates from Google Places
                    try:
                        place.latitude = float(google_lat)
                        place.longitude = float(google_lng)
                        logger.info(f"Using Google Places coordinates for place id {place.id}")
                    except ValueError:
                        logger.warning(f"Invalid Google coordinates received for place '{place.label}'.")
                        geocode_failed = True
                        place.latitude = None
                        place.longitude = None
                else:
                    # Fall back to geocoding
                    geocoding_service = get_geocoding_service()
                    result = geocoding_service.geocode_address_detailed(new_address)
                    place.latitude = result.latitude
                    place.longitude = result.longitude
                    if not result.success:
                        geocode_failed = True

            place.save()

            # Recalculate distances if address or travel preferences changed
            if (address_changed or travel_prefs_changed) and place.latitude and place.longitude:
                recalculate_distances_for_favorite_place(place)

            if geocode_failed:
                messages.warning(request, f"Updated '{place.label}' but couldn't locate the new address.")
            else:
                messages.success(request, f"Updated '{place.label}'!")
            return redirect("apartments:favorite_places")
    else:
        form = FavoritePlaceForm(
            initial={
                "label": place.label,
                "address": place.address,
                "travel_mode": place.travel_mode,
                "time_type": place.time_type,
                "day_of_week": place.day_of_week,
                "time_of_day": place.time_of_day,
            }
        )

    context = {
        "form": form,
        "place": place,
        "is_edit": True,
    }
    return render(request, "apartments/favorite_place_form.html", context)


@login_required
def delete_favorite_place(request, pk):
    """Delete a favorite place"""
    has_premium = user_has_premium(request.user, PRODUCT_SLUG)

    # Require premium for location features
    if not has_premium:
        messages.info(request, "Favorite Places is a Pro feature. Upgrade to unlock!")
        return redirect("signup")

    place = get_object_or_404(FavoritePlace, pk=pk, user=request.user)

    if request.method == "POST":
        label = place.label
        place.delete()
        messages.success(request, f"Deleted '{label}' from your favorite places.")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})

        return redirect("apartments:favorite_places")

    return JsonResponse({"error": "Method not allowed"}, status=405)


# =============================================================================
# Google Maps API Endpoints
# =============================================================================


@login_required
@require_http_methods(["GET"])
def address_autocomplete(request):
    """
    API endpoint for address autocomplete suggestions.
    Uses Google Places Autocomplete API.
    """
    query = request.GET.get("q", "").strip()
    session_token = request.GET.get("session_token", "")

    if not query or len(query) < 3:
        return JsonResponse({"suggestions": []})

    google_maps = get_google_maps_service()

    if not google_maps.is_available:
        # Fall back to empty results if Google Maps is not configured
        logger.warning("Google Maps API not available for autocomplete")
        return JsonResponse({"suggestions": [], "error": "Address autocomplete not available"})

    try:
        results = google_maps.autocomplete(query, session_token=session_token or None)
        suggestions = [
            {
                "place_id": r.place_id,
                "description": r.description,
                "main_text": r.main_text,
                "secondary_text": r.secondary_text,
            }
            for r in results
        ]
        return JsonResponse({"suggestions": suggestions})
    except Exception as e:
        logger.error(f"Autocomplete error: {e}")
        return JsonResponse({"suggestions": [], "error": str(e)})


@login_required
@require_http_methods(["GET"])
def place_details(request):
    """
    API endpoint to get place details including coordinates.
    Uses Google Places Details API.
    """
    place_id = request.GET.get("place_id", "").strip()
    session_token = request.GET.get("session_token", "")

    if not place_id:
        return JsonResponse({"error": "place_id is required"}, status=400)

    google_maps = get_google_maps_service()

    if not google_maps.is_available:
        return JsonResponse({"error": "Google Maps API not available"}, status=503)

    try:
        details = google_maps.get_place_details(place_id, session_token=session_token or None)
        if details:
            return JsonResponse(
                {
                    "place_id": details.place_id,
                    "formatted_address": details.formatted_address,
                    "latitude": details.latitude,
                    "longitude": details.longitude,
                }
            )
        else:
            return JsonResponse({"error": "Place not found"}, status=404)
    except Exception as e:
        logger.error(f"Place details error: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@login_required
def google_maps_status(request):
    """Check if Google Maps API is available and configured."""
    google_maps = get_google_maps_service()
    return JsonResponse(
        {
            "available": google_maps.is_available,
            "api_key_configured": bool(settings.GOOGLE_MAPS_API_KEY),
        }
    )


@login_required
@require_http_methods(["POST"])
def calculate_apartment_distances(request, pk):
    """
    Calculate distances for a single apartment asynchronously.
    Returns the distance data as JSON for updating the UI.
    """
    apartment = get_object_or_404(Apartment, pk=pk, user=request.user)

    if not apartment.latitude or not apartment.longitude:
        return JsonResponse({"error": "Apartment has no coordinates"}, status=400)

    # Calculate distances
    calculate_and_cache_distances(apartment)

    # Get the updated distance data
    favorite_places = FavoritePlace.objects.filter(user=request.user)
    apartments_with_distances = get_apartments_with_distances([apartment], favorite_places)

    if apartments_with_distances:
        apt_data = apartments_with_distances[0]
        return JsonResponse(
            {
                "apartment_id": apartment.id,
                "distances": apt_data["distances"],
                "average_distance": apt_data["average_distance"],
                "average_travel_time": apt_data["average_travel_time"],
            }
        )

    return JsonResponse({"error": "Failed to calculate distances"}, status=500)
