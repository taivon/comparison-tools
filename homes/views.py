import json
import logging
import random
import string
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apartments.geocoding_service import get_geocoding_service
from apartments.google_maps_service import get_google_maps_service
from apartments.models import (
    FavoritePlace,
    Plan,
    Product,
    UserProfile,
    get_user_item_limit,
    user_has_premium,
)
from apartments.stripe_service import StripeService

from .forms import HomeForm, HomePreferencesForm, HomeSuggestionForm, InviteCodeForm
from .models import (
    AgentClientRelationship,
    AgentInviteCode,
    Home,
    HomeDistance,
    HomePreferences,
    HomeSuggestion,
    RealEstateAgent,
)
from .models import (
    can_add_favorite_place as homes_can_add_favorite_place,
)
from .models import (
    get_favorite_place_limit as homes_get_favorite_place_limit,
)

logger = logging.getLogger(__name__)

# Product slug for this app
PRODUCT_SLUG = "homes"
AGENT_PRODUCT_SLUG = "homes-agent"


def get_or_create_profile(user):
    """Get or create UserProfile for a user"""
    profile, created = UserProfile.objects.get_or_create(user=user)
    return profile


def index(request):
    """Homepage - landing page with form and features"""
    if request.user.is_authenticated:
        homes = Home.objects.filter(user=request.user)
        home_count = homes.count()
        item_limit = get_user_item_limit(request.user, PRODUCT_SLUG)
        can_add_home = home_count < item_limit
    else:
        home_count = 0
        can_add_home = True  # JavaScript will enforce the limit

    from apartments.context_processors import subscription_status

    # Get context from subscription_status processor
    subscription_context = subscription_status(request)
    context = {
        "can_add_home": can_add_home,
        "is_anonymous": not request.user.is_authenticated,
        "home_count": home_count,
        "user_has_premium": subscription_context.get("user_has_premium", False),
        "google_client_id": subscription_context.get("google_client_id", ""),
    }
    return render(request, "homes/index.html", context)


def dashboard(request):
    """Dashboard view showing user's homes in table/card format"""
    favorite_places = []

    if request.user.is_authenticated:
        homes = list(Home.objects.filter(user=request.user).select_related("user").order_by("-created_at"))
        favorite_places = list(FavoritePlace.objects.filter(user=request.user))
        preferences, _ = HomePreferences.objects.get_or_create(
            user=request.user,
            defaults={"price_weight": 50, "sqft_weight": 50, "distance_weight": 50},
        )
    else:
        homes = []
        preferences = None

    # Handle preferences form submission
    if request.method == "POST":
        form = HomePreferencesForm(request.POST)
        if form.is_valid():
            preferences_data = {
                "price_weight": form.cleaned_data["price_weight"],
                "sqft_weight": form.cleaned_data["sqft_weight"],
                "distance_weight": form.cleaned_data["distance_weight"],
                "hoa_fees_weight": form.cleaned_data.get("hoa_fees_weight", 0),
                "property_taxes_weight": form.cleaned_data.get("property_taxes_weight", 0),
                "lot_size_weight": form.cleaned_data.get("lot_size_weight", 0),
                "year_built_weight": form.cleaned_data.get("year_built_weight", 0),
                "bedrooms_weight": form.cleaned_data.get("bedrooms_weight", 0),
                "bathrooms_weight": form.cleaned_data.get("bathrooms_weight", 0),
                "factor_order": form.cleaned_data.get(
                    "factor_order",
                    "price,sqft,distance,hoaFees,propertyTaxes,lotSize,yearBuilt,bedrooms,bathrooms",
                ),
            }

            if request.user.is_authenticated:
                HomePreferences.objects.update_or_create(user=request.user, defaults=preferences_data)
                # Recalculate scores when preferences change
                from .scoring_service import recalculate_user_scores

                recalculate_user_scores(request.user, PRODUCT_SLUG)
            else:
                request.session["anonymous_home_preferences"] = preferences_data
                request.session.modified = True

            messages.success(request, "Preferences updated successfully!")
            return redirect("homes:dashboard")
    else:
        initial_data = {}
        if preferences:
            initial_data = {
                "price_weight": preferences.price_weight,
                "sqft_weight": preferences.sqft_weight,
                "distance_weight": preferences.distance_weight,
                "hoa_fees_weight": getattr(preferences, "hoa_fees_weight", 0),
                "property_taxes_weight": getattr(preferences, "property_taxes_weight", 0),
                "lot_size_weight": getattr(preferences, "lot_size_weight", 0),
                "year_built_weight": getattr(preferences, "year_built_weight", 0),
                "bedrooms_weight": getattr(preferences, "bedrooms_weight", 0),
                "bathrooms_weight": getattr(preferences, "bathrooms_weight", 0),
                "factor_order": getattr(
                    preferences,
                    "factor_order",
                    "price,sqft,distance,hoaFees,propertyTaxes,lotSize,yearBuilt,bedrooms,bathrooms",
                ),
            }
        form = HomePreferencesForm(initial=initial_data)

    # Calculate scores
    home_scores = {}
    score_breakdowns = {}
    if homes and request.user.is_authenticated:
        from .scoring_service import HomeScoringService

        scoring_service = HomeScoringService(request.user, homes, PRODUCT_SLUG)
        home_scores = scoring_service.get_or_calculate_scores()
        score_breakdowns = scoring_service.get_all_score_breakdowns()

        # Attach scores and breakdowns to homes for template use
        for home in homes:
            home.score = home_scores.get(home.id)
            home.score_breakdown = score_breakdowns.get(home.id)

    # Sort homes by score (highest first) if scores available
    if home_scores:
        homes = sorted(homes, key=lambda x: home_scores.get(x.id, 0), reverse=True)

    has_premium = user_has_premium(request.user, PRODUCT_SLUG) if request.user.is_authenticated else False
    item_limit = get_user_item_limit(request.user, PRODUCT_SLUG) if request.user.is_authenticated else 2
    can_add_home = len(homes) < item_limit

    # Check which optional fields have data
    has_hoa = any(getattr(home, "hoa_fees", 0) > 0 for home in homes)
    has_taxes = any(getattr(home, "property_taxes", 0) > 0 for home in homes)
    has_year_built = any(getattr(home, "year_built", None) for home in homes)
    has_lot_size = any(getattr(home, "lot_size_sqft", None) for home in homes)

    # Get distance data for homes
    homes_needing_distances = []
    if favorite_places and homes and has_premium:
        geocoded_places = [p for p in favorite_places if p.latitude and p.longitude]
        expected_count = len(geocoded_places)

        if expected_count > 0:
            apt_ids_with_coords = [home.id for home in homes if home.latitude and home.longitude]
            if apt_ids_with_coords:
                from django.db.models import Count

                distance_counts = dict(
                    HomeDistance.objects.filter(home_id__in=apt_ids_with_coords)
                    .values("home_id")
                    .annotate(count=Count("id"))
                    .values_list("home_id", "count")
                )
                for home in homes:
                    if home.id in apt_ids_with_coords:
                        actual_count = distance_counts.get(home.id, 0)
                        if actual_count < expected_count:
                            homes_needing_distances.append(home.id)

        # Use similar logic to apartments for getting distances
        # Batch fetch all distances for efficiency
        home_ids = [home.id for home in homes if home.latitude and home.longitude]
        if home_ids:
            all_distances = HomeDistance.objects.filter(home_id__in=home_ids).select_related("favorite_place")
            distances_by_home = defaultdict(list)
            for d in all_distances:
                distances_by_home[d.home_id].append(d)

        for home in homes:
            if home.latitude and home.longitude:
                # Initialize distances dict with place labels as keys (matching apartments structure)
                distances_dict = {
                    place.label: {"distance": None, "travel_time": None, "transit_fare": None}
                    for place in favorite_places
                }

                # Get cached distances from pre-fetched data
                cached_distances = distances_by_home.get(home.id, [])

                total_distance = 0.0
                total_time = 0
                count = 0
                time_count = 0

                for d in cached_distances:
                    if d.distance_miles is not None:
                        dist_float = float(d.distance_miles)
                        distances_dict[d.favorite_place.label] = {
                            "distance": dist_float,
                            "travel_time": d.travel_time_minutes,
                            "transit_fare": float(d.transit_fare) if d.transit_fare else None,
                        }
                        total_distance += dist_float
                        count += 1

                        if d.travel_time_minutes is not None:
                            total_time += d.travel_time_minutes
                            time_count += 1

                home.distance_data = distances_dict
                home.average_distance = round(total_distance / count, 2) if count > 0 else None
                home.average_travel_time = round(total_time / time_count) if time_count > 0 else None
            else:
                home.distance_data = {}
                home.average_distance = None
                home.average_travel_time = None
    else:
        for home in homes:
            home.distance_data = {}
            home.average_distance = None
            home.average_travel_time = None

    # Get favorite place stats
    favorite_place_count = len(favorite_places)
    favorite_place_limit = (
        homes_get_favorite_place_limit(request.user, PRODUCT_SLUG) if request.user.is_authenticated else 1
    )
    can_add_favorite_place_flag = (
        homes_can_add_favorite_place(request.user, PRODUCT_SLUG) if request.user.is_authenticated else False
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

    # Check if user has linked agent
    linked_agent = None
    if request.user.is_authenticated:
        try:
            relationship = AgentClientRelationship.objects.get(client=request.user, status="active")
            linked_agent = relationship.agent
        except AgentClientRelationship.DoesNotExist:
            pass

    # Check which optional fields have data (for template conditionals)
    # These are needed for the dashboard template to show/hide columns
    has_beds_baths_variation = False
    if homes:
        bedrooms_set = {home.bedrooms for home in homes}
        bathrooms_set = {home.bathrooms for home in homes}
        has_beds_baths_variation = len(bedrooms_set) > 1 or len(bathrooms_set) > 1

    # Homes don't have discounts, parking, utilities, view, or balcony like apartments
    # But we need these variables for template compatibility
    has_discounts = False  # Homes are purchased, not rented with discounts
    has_parking = False  # Not applicable for homes
    has_utilities = False  # Not applicable for homes
    has_view_ratings = False  # Not applicable for homes
    has_balcony = False  # Not applicable for homes
    has_additional_costs = has_hoa or has_taxes  # HOA and taxes are additional costs

    context = {
        "homes": homes,
        "preferences": preferences,
        "form": form,
        "is_premium": has_premium,
        "can_add_home": can_add_home,
        "home_count": len(homes),
        "home_limit": item_limit,
        "is_anonymous": not request.user.is_authenticated,
        "has_hoa": has_hoa,
        "has_taxes": has_taxes,
        "has_year_built": has_year_built,
        "has_lot_size": has_lot_size,
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
        "homes_needing_distances": homes_needing_distances,
        "monthly_price": monthly_price,
        "linked_agent": linked_agent,
    }
    return render(request, "homes/dashboard.html", context)


@login_required
def create_home(request):
    """Create a new home"""
    if request.method == "POST":
        form = HomeForm(request.POST)
        logger.debug(f"Form data: {request.POST}")
        if form.is_valid():
            logger.debug("Form is valid")

            # Check tier limit
            current_count = Home.objects.filter(user=request.user).count()
            item_limit = get_user_item_limit(request.user, PRODUCT_SLUG)
            if current_count >= item_limit:
                has_premium = user_has_premium(request.user, PRODUCT_SLUG)
                if has_premium:
                    messages.error(
                        request,
                        f"You've reached the limit of {item_limit} homes. Please remove one to add another.",
                    )
                else:
                    messages.error(request, "Free tier limit reached. Upgrade to Pro to add more homes.")
                return redirect("homes:index")

            try:
                address = form.cleaned_data.get("address", "")
                latitude, longitude = None, None
                geocode_warning = None

                # Check if we have pre-fetched coordinates from Google Places
                google_lat = request.POST.get("google_latitude", "").strip()
                google_lng = request.POST.get("google_longitude", "").strip()

                if google_lat and google_lng:
                    try:
                        latitude = float(google_lat)
                        longitude = float(google_lng)
                        logger.info("Using Google Places coordinates for home.")
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

                home = Home.objects.create(
                    user=request.user,
                    name=form.cleaned_data["name"],
                    address=address,
                    latitude=latitude,
                    longitude=longitude,
                    price=form.cleaned_data["price"],
                    square_footage=form.cleaned_data["square_footage"],
                    bedrooms=form.cleaned_data.get("bedrooms", 1),
                    bathrooms=form.cleaned_data.get("bathrooms", 1),
                    hoa_fees=form.cleaned_data.get("hoa_fees", Decimal("0")),
                    property_taxes=form.cleaned_data.get("property_taxes", Decimal("0")),
                    year_built=form.cleaned_data.get("year_built"),
                    lot_size_sqft=form.cleaned_data.get("lot_size_sqft"),
                    mls_number=form.cleaned_data.get("mls_number", ""),
                    zillow_id=form.cleaned_data.get("zillow_id", ""),
                    redfin_id=form.cleaned_data.get("redfin_id", ""),
                    source=form.cleaned_data.get("source", "manual"),
                )

                # Calculate distances to favorite places (premium only)
                if home.latitude and home.longitude and user_has_premium(request.user, PRODUCT_SLUG):
                    calculate_home_distances(home)

                # Recalculate scores for all homes
                from .scoring_service import recalculate_user_scores

                recalculate_user_scores(request.user, PRODUCT_SLUG)

                if geocode_warning:
                    has_premium = user_has_premium(request.user, PRODUCT_SLUG)
                    if has_premium:
                        messages.warning(
                            request,
                            f"Home added, but couldn't locate the address. {geocode_warning} "
                            "You can edit the home to update the address.",
                        )
                    else:
                        messages.warning(
                            request,
                            "Home added, but we couldn't locate the address in our free database. "
                            "Distance calculations and location-based scoring won't work for this home. "
                            "You can edit the home to try a different address format, "
                            "or upgrade to Pro for Google Maps address lookup which supports more addresses.",
                        )
                elif not address:
                    messages.success(
                        request,
                        "Home added! Tip: Add an address to enable distance calculations and location-based scoring.",
                    )
                else:
                    messages.success(request, "Home added successfully!")
                return redirect("homes:dashboard")
            except IntegrityError:
                logger.warning(f"Duplicate home name attempted: {form.cleaned_data['name']}")
                form.add_error("name", "You already have a home with this name. Please choose a different name.")
            except Exception as e:
                logger.error(f"Error saving home: {str(e)}")
                messages.error(request, "An error occurred while saving the home.")
        else:
            logger.error(f"Form errors: {form.errors}")
            messages.error(request, "Please correct the errors below.")
    else:
        form = HomeForm()

    return render(request, "homes/home_form.html", {"form": form})


@login_required
def update_home(request, pk):
    """Update an existing home"""
    home = get_object_or_404(Home, pk=pk, user=request.user)

    if request.method == "POST":
        form = HomeForm(request.POST)
        if form.is_valid():
            new_address = form.cleaned_data.get("address", "")
            address_changed = new_address != home.address

            home.name = form.cleaned_data["name"]
            home.address = new_address
            home.price = form.cleaned_data["price"]
            home.square_footage = form.cleaned_data["square_footage"]
            home.bedrooms = form.cleaned_data.get("bedrooms", 1)
            home.bathrooms = form.cleaned_data.get("bathrooms", 1)
            home.hoa_fees = form.cleaned_data.get("hoa_fees", Decimal("0"))
            home.property_taxes = form.cleaned_data.get("property_taxes", Decimal("0"))
            home.year_built = form.cleaned_data.get("year_built")
            home.lot_size_sqft = form.cleaned_data.get("lot_size_sqft")

            # Re-geocode if address changed
            geocode_warning = None
            if address_changed:
                if new_address:
                    google_lat = request.POST.get("google_latitude", "").strip()
                    google_lng = request.POST.get("google_longitude", "").strip()

                    if google_lat and google_lng:
                        try:
                            home.latitude = float(google_lat)
                            home.longitude = float(google_lng)
                            logger.info("Using Google Places coordinates for home update.")
                        except ValueError:
                            logger.warning("Invalid Google coordinates received during home update.")
                            home.latitude = None
                            home.longitude = None
                    else:
                        geocoding_service = get_geocoding_service()
                        result = geocoding_service.geocode_address_detailed(new_address)
                        home.latitude = result.latitude
                        home.longitude = result.longitude
                        if not result.success:
                            logger.warning(f"Could not geocode address: {new_address}")
                            geocode_warning = result.suggestion
                else:
                    home.latitude = None
                    home.longitude = None

            try:
                home.save()

                # Recalculate distances if address changed (premium only)
                if (
                    address_changed
                    and home.latitude
                    and home.longitude
                    and user_has_premium(request.user, PRODUCT_SLUG)
                ):
                    calculate_home_distances(home)

                # Recalculate scores for all homes since data changed
                from .scoring_service import recalculate_user_scores

                recalculate_user_scores(request.user, PRODUCT_SLUG)

                if geocode_warning:
                    has_premium = user_has_premium(request.user, PRODUCT_SLUG)
                    if has_premium:
                        messages.warning(
                            request,
                            f"Home updated, but couldn't locate the new address. {geocode_warning}",
                        )
                    else:
                        messages.warning(
                            request,
                            "Home updated, but we couldn't locate the address in our free database. "
                            "Distance calculations and location-based scoring won't work for this home. "
                            "Try a different address format, "
                            "or upgrade to Pro for Google Maps address lookup which supports more addresses.",
                        )
                elif not new_address and not home.latitude:
                    messages.success(
                        request,
                        "Home updated! Tip: Add an address to enable distance calculations and location-based scoring.",
                    )
                else:
                    messages.success(request, "Home updated successfully!")
                return redirect("homes:dashboard")
            except IntegrityError:
                logger.warning(f"Duplicate home name attempted on update: {form.cleaned_data['name']}")
                form.add_error("name", "You already have a home with this name. Please choose a different name.")
    else:
        initial_data = {
            "name": home.name,
            "address": home.address,
            "price": home.price,
            "square_footage": home.square_footage,
            "bedrooms": home.bedrooms,
            "bathrooms": home.bathrooms,
            "hoa_fees": home.hoa_fees,
            "property_taxes": home.property_taxes,
            "year_built": home.year_built,
            "lot_size_sqft": home.lot_size_sqft,
        }
        form = HomeForm(initial=initial_data)

    return render(request, "homes/home_form.html", {"form": form, "home": home})


@login_required
@require_http_methods(["POST"])
def delete_home(request, pk):
    """Delete a home"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    home = get_object_or_404(Home, pk=pk, user=request.user)
    home.delete()

    # Recalculate scores for remaining homes
    from .scoring_service import recalculate_user_scores

    recalculate_user_scores(request.user, PRODUCT_SLUG)

    messages.success(request, "Home deleted successfully!")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        remaining_count = Home.objects.filter(user=request.user).count()
        return JsonResponse({"success": True, "remaining_count": remaining_count})

    remaining_homes = Home.objects.filter(user=request.user).exists()
    if remaining_homes:
        return redirect("homes:dashboard")
    else:
        return redirect("homes:index")


def calculate_home_distances(home):
    """Calculate distances from a home to all favorite places"""
    if not home.latitude or not home.longitude:
        return

    favorite_places = FavoritePlace.objects.filter(user=home.user)
    google_maps_available = bool(settings.GOOGLE_MAPS_API_KEY)

    for place in favorite_places:
        if not place.latitude or not place.longitude:
            continue

        # Use apartments distance service logic
        from apartments.distance_service import _calculate_distance_with_fallback

        distance_miles, travel_time, fare, is_google = _calculate_distance_with_fallback(
            home.latitude,
            home.longitude,
            place.latitude,
            place.longitude,
            use_google_maps=google_maps_available,
            mode=place.travel_mode,
        )

        defaults = {
            "distance_miles": Decimal(str(distance_miles)),
            "travel_time_minutes": travel_time,
        }
        if fare is not None:
            defaults["transit_fare"] = Decimal(str(fare))

        HomeDistance.objects.update_or_create(home=home, favorite_place=place, defaults=defaults)


# =============================================================================
# Agent Views
# =============================================================================


@login_required
def agent_dashboard(request):
    """Agent dashboard showing all clients and their homes"""
    # Check if user is an agent with active agent subscription
    try:
        agent_profile = RealEstateAgent.objects.get(user=request.user)
    except RealEstateAgent.DoesNotExist:
        messages.error(request, "You must be a registered real estate agent to access this page.")
        return redirect("homes:dashboard")

    if not agent_profile.is_agent_tier_active():
        messages.error(request, "You need an active agent subscription to access the agent dashboard.")
        return redirect("homes:pricing")

    # Get all active client relationships
    relationships = AgentClientRelationship.objects.filter(agent=request.user, status="active").select_related("client")

    # Get all clients' homes
    clients_data = []
    for relationship in relationships:
        client = relationship.client
        homes = Home.objects.filter(user=client).order_by("-created_at")
        pending_suggestions = HomeSuggestion.objects.filter(agent=request.user, client=client, status="pending").count()

        clients_data.append(
            {
                "client": client,
                "relationship": relationship,
                "homes": homes,
                "home_count": homes.count(),
                "pending_suggestions": pending_suggestions,
            }
        )

    # Get all pending suggestions
    all_pending_suggestions = HomeSuggestion.objects.filter(agent=request.user, status="pending").select_related(
        "client", "home"
    )

    context = {
        "agent_profile": agent_profile,
        "clients_data": clients_data,
        "all_pending_suggestions": all_pending_suggestions,
        "client_count": len(clients_data),
    }
    return render(request, "homes/agent_dashboard.html", context)


@login_required
def generate_invite_code(request):
    """Generate a new invite code for an agent"""
    try:
        agent_profile = RealEstateAgent.objects.get(user=request.user)
    except RealEstateAgent.DoesNotExist:
        messages.error(request, "You must be a registered real estate agent.")
        return redirect("homes:dashboard")

    if not agent_profile.is_agent_tier_active():
        messages.error(request, "You need an active agent subscription to generate invite codes.")
        return redirect("homes:pricing")

    if request.method == "POST":
        # Generate a random code (6 characters, alphanumeric)
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # Ensure uniqueness
        while AgentInviteCode.objects.filter(code=code).exists():
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

        max_uses = request.POST.get("max_uses", "").strip()
        expires_days = request.POST.get("expires_days", "").strip()

        AgentInviteCode.objects.create(
            agent=request.user,
            code=code,
            max_uses=int(max_uses) if max_uses else None,
            expires_at=timezone.now() + timezone.timedelta(days=int(expires_days)) if expires_days else None,
        )

        messages.success(request, f"Invite code generated: {code}")
        return redirect("homes:agent_dashboard")

    # Show existing invite codes
    invite_codes = AgentInviteCode.objects.filter(agent=request.user).order_by("-created_at")

    context = {
        "agent_profile": agent_profile,
        "invite_codes": invite_codes,
    }
    return render(request, "homes/generate_invite_code.html", context)


@login_required
def enter_invite_code(request):
    """Client enters an agent's invite code to link"""
    if not user_has_premium(request.user, PRODUCT_SLUG):
        messages.error(request, "Agent linking is a premium feature. Please upgrade to Pro.")
        return redirect("homes:pricing")

    if request.method == "POST":
        form = InviteCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]

            try:
                invite_code = AgentInviteCode.objects.get(code=code, is_active=True)
            except AgentInviteCode.DoesNotExist:
                form.add_error("code", "Invalid or expired invite code.")
                return render(request, "homes/enter_invite_code.html", {"form": form})

            if not invite_code.is_valid():
                form.add_error("code", "This invite code has expired or reached its usage limit.")
                return render(request, "homes/enter_invite_code.html", {"form": form})

            # Check if already linked
            if AgentClientRelationship.objects.filter(agent=invite_code.agent, client=request.user).exists():
                messages.info(request, "You are already linked with this agent.")
                return redirect("homes:dashboard")

            # Create relationship
            AgentClientRelationship.objects.create(
                agent=invite_code.agent,
                client=request.user,
                invite_code=code,
                status="active",
                linked_at=timezone.now(),
            )

            # Increment uses count
            invite_code.uses_count += 1
            invite_code.save()

            messages.success(
                request,
                f"Successfully linked with agent {invite_code.agent.get_full_name() or invite_code.agent.username}!",
            )
            return redirect("homes:dashboard")
    else:
        form = InviteCodeForm()

    return render(request, "homes/enter_invite_code.html", {"form": form})


@login_required
def suggest_home(request):
    """Agent suggests a home to a client"""
    try:
        agent_profile = RealEstateAgent.objects.get(user=request.user)
    except RealEstateAgent.DoesNotExist:
        messages.error(request, "You must be a registered real estate agent.")
        return redirect("homes:dashboard")

    if not agent_profile.is_agent_tier_active():
        messages.error(request, "You need an active agent subscription to suggest homes.")
        return redirect("homes:pricing")

    # Get agent's active clients
    relationships = AgentClientRelationship.objects.filter(agent=request.user, status="active")
    clients = [rel.client for rel in relationships]

    if request.method == "POST":
        form = HomeSuggestionForm(request.POST)
        form.fields["client"].queryset = User.objects.filter(id__in=[c.id for c in clients])
        form.fields["home"].queryset = Home.objects.filter(user=request.user)  # Agent's own homes

        if form.is_valid():
            client = form.cleaned_data["client"]
            home = form.cleaned_data["home"]
            message = form.cleaned_data.get("message", "")

            # Check if suggestion already exists
            if HomeSuggestion.objects.filter(agent=request.user, client=client, home=home).exists():
                messages.error(request, "You have already suggested this home to this client.")
                return redirect("homes:suggest_home")

            # Create suggestion
            HomeSuggestion.objects.create(
                agent=request.user,
                client=client,
                home=home,
                message=message,
                status="pending",
            )

            messages.success(request, f"Home suggestion sent to {client.get_full_name() or client.username}!")
            return redirect("homes:agent_dashboard")
    else:
        form = HomeSuggestionForm()
        form.fields["client"].queryset = User.objects.filter(id__in=[c.id for c in clients])
        form.fields["home"].queryset = Home.objects.filter(user=request.user)

    context = {
        "agent_profile": agent_profile,
        "form": form,
        "clients": clients,
    }
    return render(request, "homes/suggest_home.html", context)


@login_required
def view_suggestions(request):
    """Client views pending agent suggestions"""
    suggestions = HomeSuggestion.objects.filter(client=request.user, status="pending").select_related("agent", "home")

    context = {
        "suggestions": suggestions,
    }
    return render(request, "homes/view_suggestions.html", context)


@login_required
@require_http_methods(["POST"])
def approve_suggestion(request, pk):
    """Client approves an agent suggestion"""
    suggestion = get_object_or_404(HomeSuggestion, pk=pk, client=request.user, status="pending")

    # Create a copy of the home for the client
    original_home = suggestion.home
    new_home = Home.objects.create(
        user=request.user,
        name=original_home.name,
        address=original_home.address,
        latitude=original_home.latitude,
        longitude=original_home.longitude,
        price=original_home.price,
        square_footage=original_home.square_footage,
        bedrooms=original_home.bedrooms,
        bathrooms=original_home.bathrooms,
        hoa_fees=original_home.hoa_fees,
        property_taxes=original_home.property_taxes,
        year_built=original_home.year_built,
        lot_size_sqft=original_home.lot_size_sqft,
        mls_number=original_home.mls_number,
        zillow_id=original_home.zillow_id,
        redfin_id=original_home.redfin_id,
        source=original_home.source,
    )

    # Update suggestion status
    suggestion.status = "approved"
    suggestion.responded_at = timezone.now()
    suggestion.save()

    # Recalculate scores
    from .scoring_service import recalculate_user_scores

    recalculate_user_scores(request.user, PRODUCT_SLUG)

    messages.success(request, f"Added {new_home.name} to your comparison list!")
    return redirect("homes:dashboard")


@login_required
@require_http_methods(["POST"])
def reject_suggestion(request, pk):
    """Client rejects an agent suggestion"""
    suggestion = get_object_or_404(HomeSuggestion, pk=pk, client=request.user, status="pending")

    suggestion.status = "rejected"
    suggestion.responded_at = timezone.now()
    suggestion.save()

    messages.info(request, "Suggestion rejected.")
    return redirect("homes:view_suggestions")


# =============================================================================
# API Import Views
# =============================================================================


@login_required
@require_http_methods(["POST"])
def import_zillow_property(request):
    """Import a property from Zillow API"""
    if not user_has_premium(request.user, PRODUCT_SLUG):
        return JsonResponse({"success": False, "error": "API imports are a premium feature."}, status=403)

    # TODO: Implement Zillow API integration
    return JsonResponse({"success": False, "error": "Zillow API integration not yet implemented."}, status=501)


@login_required
@require_http_methods(["POST"])
def import_mls_listing(request):
    """Import a listing from MLS API"""
    if not user_has_premium(request.user, PRODUCT_SLUG):
        return JsonResponse({"success": False, "error": "API imports are a premium feature."}, status=403)

    # TODO: Implement MLS API integration
    return JsonResponse({"success": False, "error": "MLS API integration not yet implemented."}, status=501)


@login_required
@require_http_methods(["POST"])
def import_redfin_property(request):
    """Import a property from Redfin API"""
    if not user_has_premium(request.user, PRODUCT_SLUG):
        return JsonResponse({"success": False, "error": "API imports are a premium feature."}, status=403)

    # TODO: Implement Redfin API integration
    return JsonResponse({"success": False, "error": "Redfin API integration not yet implemented."}, status=501)


# =============================================================================
# Favorite Places Views (reuse from apartments)
# =============================================================================


@login_required
def favorite_places_list(request):
    """List user's favorite places with management options"""
    has_premium = user_has_premium(request.user, PRODUCT_SLUG)

    # Require premium for location features
    if not has_premium:
        messages.info(request, "Favorite Places with distance calculations is a Pro feature. Upgrade to unlock!")
        return redirect("homes:pricing")

    places = FavoritePlace.objects.filter(user=request.user)

    place_count = places.count()
    place_limit = homes_get_favorite_place_limit(request.user, PRODUCT_SLUG)
    can_add = place_count < place_limit

    context = {
        "favorite_places": places,
        "place_count": place_count,
        "place_limit": place_limit,
        "can_add_place": can_add,
        "is_premium": has_premium,
    }
    return render(request, "homes/favorite_places.html", context)


@login_required
def create_favorite_place(request):
    """Create a new favorite place with geocoding"""
    has_premium = user_has_premium(request.user, PRODUCT_SLUG)

    # Require premium for location features
    if not has_premium:
        messages.info(request, "Favorite Places is a Pro feature. Upgrade to unlock distance calculations!")
        return redirect("signup")

    # Check limit
    if not homes_can_add_favorite_place(request.user, PRODUCT_SLUG):
        messages.error(request, "You've reached the maximum of 5 favorite places.")
        return redirect("homes:favorite_places")

    from apartments.forms import FavoritePlaceForm

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
                # Calculate distances to all apartments and homes
                from apartments.distance_service import recalculate_distances_for_favorite_place

                recalculate_distances_for_favorite_place(place)

            return redirect("homes:favorite_places")
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

    from apartments.forms import FavoritePlaceForm

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
                from apartments.distance_service import recalculate_distances_for_favorite_place

                recalculate_distances_for_favorite_place(place)

            if geocode_failed:
                messages.warning(request, f"Updated '{place.label}' but couldn't locate the new address.")
            else:
                messages.success(request, f"Updated '{place.label}'!")
            return redirect("homes:favorite_places")
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
        return redirect("homes:favorite_places")

    # GET request - show confirmation (handled by template form)
    return redirect("homes:favorite_places")


# =============================================================================
# Subscription Views
# =============================================================================


def pricing_redirect(request):
    """Redirect pricing page to signup page"""
    return redirect("signup")


@login_required
def create_checkout_session(request):
    """Create a Stripe checkout session for subscription"""
    import stripe as stripe_lib

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

        success_url = request.build_absolute_uri("/homes/subscription/success/")
        cancel_url = request.build_absolute_uri("/homes/subscription/cancel/")

        stripe_service = StripeService()
        session = stripe_service.create_checkout_session(
            user=request.user, plan_id=plan_id, success_url=success_url, cancel_url=cancel_url
        )

        return JsonResponse({"sessionId": session.id})

    except stripe_lib.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        return JsonResponse({"error": "Payment processing error"}, status=400)
    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@login_required
def checkout_success(request):
    """Handle successful checkout"""
    messages.success(request, "Thank you for subscribing! Your premium access is now active.")
    return redirect("homes:dashboard")


@login_required
def checkout_cancel(request):
    """Handle cancelled checkout"""
    messages.info(request, "Checkout cancelled. You can upgrade to premium anytime.")
    return redirect("homes:pricing")


# =============================================================================
# Google Maps API Endpoints
# =============================================================================


@login_required
@require_http_methods(["GET"])
def address_autocomplete(request):
    """API endpoint for address autocomplete suggestions"""
    if not user_has_premium(request.user, PRODUCT_SLUG):
        return JsonResponse({"suggestions": [], "error": "Address autocomplete is a premium feature"}, status=403)

    query = request.GET.get("q", "").strip()
    session_token = request.GET.get("session_token", "")

    if not query or len(query) < 3:
        return JsonResponse({"suggestions": []})

    google_maps = get_google_maps_service()

    if not google_maps.is_available:
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
        return JsonResponse({"suggestions": [], "error": "An internal error occurred"})


@login_required
@require_http_methods(["GET"])
def place_details(request):
    """API endpoint to get place details including coordinates"""
    if not user_has_premium(request.user, PRODUCT_SLUG):
        return JsonResponse({"error": "Place details is a premium feature"}, status=403)

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
        return JsonResponse({"error": "An internal error occurred."}, status=500)
