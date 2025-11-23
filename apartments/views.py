from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .firestore_service import (
    FirestoreService,
    FirestoreApartment,
    FirestoreUserPreferences,
)
from .forms import ApartmentForm, UserPreferencesForm, CustomUserCreationForm, LoginForm
from .auth_utils import (
    firestore_login,
    firestore_logout,
    firestore_authenticate,
    login_required_firestore,
)
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def calculate_net_effective_price(apt_data, discount_calculation='daily'):
    """Calculate net effective price for session apartments"""
    from decimal import Decimal

    price = Decimal(str(apt_data.get('price', 0)))
    lease_length_months = apt_data.get('lease_length_months', 12)
    months_free = apt_data.get('months_free', 0)
    weeks_free = apt_data.get('weeks_free', 0)
    flat_discount = Decimal(str(apt_data.get('flat_discount', 0)))

    total_discount = Decimal('0')

    if discount_calculation == 'daily':
        # Calculate annual rent divided by 365 days
        daily_rate = price * Decimal('12') / Decimal('365')
        # Convert months_free to days (using 365/12 for precision)
        if months_free > 0:
            days_free_from_months = Decimal(str(months_free)) * Decimal('365') / Decimal('12')
            total_discount += daily_rate * days_free_from_months
        # Convert weeks_free to days
        if weeks_free > 0:
            total_discount += daily_rate * Decimal('7') * Decimal(str(weeks_free))
    elif discount_calculation == 'weekly':
        # Calculate annual rent divided by 52 weeks
        weekly_rate = price * Decimal('12') / Decimal('52')
        # Convert months_free to weeks (using 52/12 for precision)
        if months_free > 0:
            weeks_free_from_months = Decimal(str(months_free)) * Decimal('52') / Decimal('12')
            total_discount += weekly_rate * weeks_free_from_months
        # Add weeks_free directly
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
    # Round to 2 decimal places and return as float
    return float(round(net_price, 2))


def get_session_apartments(request):
    """Get apartments from session for anonymous users"""
    session_apartments = request.session.get("anonymous_apartments", [])
    apartments = []

    for apt_data in session_apartments:
        # Create a simple object with the apartment data
        class SessionApartment:
            def __init__(self, data):
                for key, value in data.items():
                    setattr(self, key, value)
                # Ensure we have a doc_id attribute
                if not hasattr(self, "doc_id"):
                    self.doc_id = data.get("id", f"session_{len(apartments)}")
                # Add price_per_sqft property (rounded to 2 decimals)
                self.price_per_sqft = round(self.price / self.square_footage, 2) if self.square_footage > 0 else 0

        apartment = SessionApartment(apt_data)
        apartments.append(apartment)

    return apartments


def save_session_apartment(request, apartment_data):
    """Save apartment to session for anonymous users"""
    session_apartments = request.session.get("anonymous_apartments", [])

    # Add unique ID for session apartments
    apartment_data["id"] = (
        f"session_{len(session_apartments)}_{apartment_data.get('name', 'apt').replace(' ', '_')}"
    )

    session_apartments.append(apartment_data)
    request.session["anonymous_apartments"] = session_apartments
    request.session.modified = True


def clear_session_apartments(request):
    """Clear session apartments (used when user signs up)"""
    if "anonymous_apartments" in request.session:
        del request.session["anonymous_apartments"]
        request.session.modified = True


def delete_session_apartment_by_id(request, apartment_id):
    """Delete a single session apartment by ID"""
    session_apartments = request.session.get("anonymous_apartments", [])

    # Filter out the apartment with the matching ID
    updated_apartments = [apt for apt in session_apartments if apt.get("id") != apartment_id]

    request.session["anonymous_apartments"] = updated_apartments
    request.session.modified = True

    return len(session_apartments) != len(updated_apartments)  # Return True if apartment was found and deleted


def index(request):
    """Homepage - landing page with form and features"""
    firestore_service = FirestoreService()

    # Simple apartment count check for form availability
    if request.user.is_authenticated:
        apartments = firestore_service.get_user_apartments(request.user.id)
        apartment_count = len(apartments)
        # Authenticated users: staff = unlimited, others = 2
        can_add_apartment = request.user.is_staff or apartment_count < 2
    else:
        # Anonymous users - will check via JavaScript/sessionStorage
        apartment_count = 0
        can_add_apartment = True  # JavaScript will enforce the 2-apartment limit

    context = {
        "can_add_apartment": can_add_apartment,
        "is_anonymous": not request.user.is_authenticated,
        "apartment_count": apartment_count,
    }
    return render(request, "apartments/index.html", context)


def dashboard(request):
    """Dashboard view showing user's apartments in table/card format"""
    firestore_service = FirestoreService()

    # Handle both authenticated and anonymous users
    if request.user.is_authenticated:
        # Authenticated user - get data from Firestore
        apartments = firestore_service.get_user_apartments(request.user.id)
        preferences = firestore_service.get_user_preferences(request.user.id)
    else:
        # Anonymous user - apartments stored in sessionStorage (client-side)
        # Return empty list; JavaScript will load from sessionStorage
        apartments = []
        # Get anonymous user preferences from session (still server-side)
        session_prefs = request.session.get('anonymous_preferences', {})
        if session_prefs:
            # Create a simple preferences object
            class SessionPreferences:
                def __init__(self, data):
                    self.price_weight = data.get('price_weight', 50)
                    self.sqft_weight = data.get('sqft_weight', 50)
                    self.distance_weight = data.get('distance_weight', 50)
                    self.discount_calculation = data.get('discount_calculation', 'daily')
            preferences = SessionPreferences(session_prefs)
        else:
            preferences = None

    # Handle preferences form submission (for both authenticated and anonymous users)
    if request.method == "POST":
        form = UserPreferencesForm(request.POST)
        if form.is_valid():
            preferences_data = {
                "price_weight": form.cleaned_data["price_weight"],
                "sqft_weight": form.cleaned_data["sqft_weight"],
                "distance_weight": form.cleaned_data["distance_weight"],
                "discount_calculation": form.cleaned_data["discount_calculation"],
            }

            if request.user.is_authenticated:
                # Save to Firestore for authenticated users
                firestore_service.update_user_preferences(request.user.id, preferences_data)
            else:
                # Save to session for anonymous users
                request.session['anonymous_preferences'] = preferences_data
                request.session.modified = True

            messages.success(request, "Preferences updated successfully!")
            return redirect("apartments:dashboard")
    else:
        # Create form with current preferences values
        initial_data = {}
        if preferences:
            initial_data = {
                "price_weight": preferences.price_weight,
                "sqft_weight": preferences.sqft_weight,
                "distance_weight": preferences.distance_weight,
                "discount_calculation": preferences.discount_calculation,
            }
        form = UserPreferencesForm(initial=initial_data)

    # Calculate net effective price for each apartment first
    discount_calc_method = preferences.discount_calculation if preferences else 'daily'
    for apartment in apartments:
        if hasattr(apartment, 'net_effective_price') and callable(apartment.net_effective_price):
            # FirestoreApartment - call method with preferences
            apartment.net_effective_price = apartment.net_effective_price(preferences)
        else:
            # Session apartment - calculate manually
            apt_data = {
                'price': getattr(apartment, 'price', 0),
                'lease_length_months': getattr(apartment, 'lease_length_months', 12),
                'months_free': getattr(apartment, 'months_free', 0),
                'weeks_free': getattr(apartment, 'weeks_free', 0),
                'flat_discount': getattr(apartment, 'flat_discount', 0),
            }
            apartment.net_effective_price = calculate_net_effective_price(apt_data, discount_calc_method)

    # Sort apartments based on user preferences
    if preferences and apartments:
        apartments = sorted(
            apartments,
            key=lambda x: (
                (float(x.net_effective_price) * preferences.price_weight)
                + (x.square_footage * preferences.sqft_weight)
                + (0 * preferences.distance_weight)  # Distance is not implemented yet
            ),
            reverse=True,
        )  # Sort in descending order

    # Check if user can add more apartments
    if request.user.is_authenticated:
        # Authenticated users: staff = unlimited, others = 2
        can_add_apartment = request.user.is_staff or len(apartments) < 2
    else:
        # Anonymous users: max 2 apartments
        can_add_apartment = len(apartments) < 2

    # Check if any apartment has discounts
    has_discounts = any(
        (
            getattr(apt, "months_free", 0) > 0
            or getattr(apt, "weeks_free", 0) > 0
            or getattr(apt, "flat_discount", 0) > 0
        )
        for apt in apartments
    )

    context = {
        "apartments": apartments,
        "preferences": preferences,
        "form": form,  # Add the form to the context
        "is_premium": request.user.is_staff if request.user.is_authenticated else False,
        "can_add_apartment": can_add_apartment,
        "apartment_count": len(apartments),
        "apartment_limit": (
            2 if not (request.user.is_authenticated and request.user.is_staff) else None
        ),
        "is_anonymous": not request.user.is_authenticated,
        "has_discounts": has_discounts,
    }
    return render(request, "apartments/dashboard.html", context)


def create_apartment(request):
    if request.method == "POST":
        form = ApartmentForm(request.POST)
        logger.debug(f"Form data: {request.POST}")
        if form.is_valid():
            logger.debug("Form is valid")

            apartment_data = {
                "name": form.cleaned_data["name"],
                "price": float(form.cleaned_data["price"]),
                "square_footage": form.cleaned_data["square_footage"],
                "lease_length_months": form.cleaned_data["lease_length_months"],
                "months_free": form.cleaned_data["months_free"],
                "weeks_free": form.cleaned_data["weeks_free"],
                "flat_discount": float(form.cleaned_data["flat_discount"]),
            }

            # Only authenticated users should reach this endpoint
            # Anonymous users store apartments in sessionStorage (client-side)
            if not request.user.is_authenticated:
                return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

            # Authenticated user - save to Firestore
            firestore_service = FirestoreService()

            # Check free tier limit for authenticated users
            if (
                not request.user.is_staff
                and len(firestore_service.get_user_apartments(request.user.id)) >= 2
            ):
                messages.error(
                    request,
                    "Free tier limit reached. Upgrade to premium to add more apartments.",
                )
                return redirect("apartments:index")

            try:
                apartment_data["user_id"] = str(request.user.id)
                firestore_service.create_apartment(apartment_data)
                messages.success(request, "Apartment added successfully!")
                return redirect("apartments:dashboard")
            except Exception as e:
                logger.error(f"Error saving apartment: {str(e)}")
                messages.error(
                    request, "An error occurred while saving the apartment."
                )
        else:
            logger.error(f"Form errors: {form.errors}")
            messages.error(request, "Please correct the errors below.")
    else:
        form = ApartmentForm()

    return render(request, "apartments/apartment_form.html", {"form": form})


@login_required_firestore
def update_apartment(request, pk):
    firestore_service = FirestoreService()
    apartment = firestore_service.get_apartment(pk)

    if not apartment or apartment.user_id != str(request.user.id):
        raise Http404("Apartment not found")

    if request.method == "POST":
        form = ApartmentForm(request.POST)
        if form.is_valid():
            apartment_data = {
                "name": form.cleaned_data["name"],
                "price": float(form.cleaned_data["price"]),
                "square_footage": form.cleaned_data["square_footage"],
                "lease_length_months": form.cleaned_data["lease_length_months"],
                "months_free": form.cleaned_data["months_free"],
                "weeks_free": form.cleaned_data["weeks_free"],
                "flat_discount": float(form.cleaned_data["flat_discount"]),
            }
            firestore_service.update_apartment(pk, apartment_data)
            messages.success(request, "Apartment updated successfully!")
            return redirect("apartments:index")
    else:
        # Initialize form with current apartment data
        initial_data = {
            "name": apartment.name,
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
    if pk.startswith("session_"):
        # Anonymous user deleting session apartment
        deleted = delete_session_apartment_by_id(request, pk)
        if deleted:
            return JsonResponse({"success": True})
        else:
            return JsonResponse({"success": False, "error": "Apartment not found"}, status=404)
    else:
        # Authenticated user deleting Firestore apartment
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

        firestore_service = FirestoreService()
        apartment = firestore_service.get_apartment(pk)

        if not apartment or apartment.user_id != str(request.user.id):
            return JsonResponse({"success": False, "error": "Apartment not found"}, status=404)

        firestore_service.delete_apartment(pk)
        messages.success(request, "Apartment deleted successfully!")

        # Return JSON for AJAX requests, redirect for form submissions
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Check remaining apartments count
            remaining_apartments = firestore_service.get_user_apartments(request.user.id)
            return JsonResponse({
                "success": True,
                "remaining_count": len(remaining_apartments)
            })

        # For non-AJAX: Check if user still has apartments
        remaining_apartments = firestore_service.get_user_apartments(request.user.id)
        if remaining_apartments:
            return redirect("apartments:dashboard")
        else:
            return redirect("apartments:index")


@login_required_firestore
def update_preferences(request):
    firestore_service = FirestoreService()
    preferences = firestore_service.get_user_preferences(request.user.id)

    if request.method == "POST":
        form = UserPreferencesForm(request.POST)
        if form.is_valid():
            preferences_data = {
                "price_weight": form.cleaned_data["price_weight"],
                "sqft_weight": form.cleaned_data["sqft_weight"],
                "distance_weight": form.cleaned_data["distance_weight"],
                "discount_calculation": form.cleaned_data["discount_calculation"],
            }
            firestore_service.update_user_preferences(request.user.id, preferences_data)
            messages.success(request, "Preferences updated successfully!")
            return redirect("apartments:index")
    else:
        # Initialize form with current preferences
        initial_data = {}
        if preferences:
            initial_data = {
                "price_weight": preferences.price_weight,
                "sqft_weight": preferences.sqft_weight,
                "distance_weight": preferences.distance_weight,
                "discount_calculation": preferences.discount_calculation,
            }
        form = UserPreferencesForm(initial=initial_data)

    return render(request, "apartments/preferences_form.html", {"form": form})


@require_http_methods(["POST"])
def transfer_apartments(request):
    """Transfer apartments from sessionStorage to Firestore after user signs up"""
    if not request.user.is_authenticated:
        return JsonResponse({"success": False, "error": "Authentication required"}, status=401)

    try:
        data = json.loads(request.body)
        apartments = data.get("apartments", [])

        firestore_service = FirestoreService()
        transferred_count = 0

        for apartment in apartments:
            try:
                apartment_data = {
                    "name": apartment["name"],
                    "price": float(apartment["price"]),
                    "square_footage": int(apartment["square_footage"]),
                    "lease_length_months": int(apartment.get("lease_length_months", 12)),
                    "months_free": int(apartment.get("months_free", 0)),
                    "weeks_free": int(apartment.get("weeks_free", 0)),
                    "flat_discount": float(apartment.get("flat_discount", 0)),
                    "user_id": str(request.user.id),
                }
                firestore_service.create_apartment(apartment_data)
                transferred_count += 1
            except Exception as e:
                logger.error(f"Error transferring apartment: {e}")

        return JsonResponse({
            "success": True,
            "transferred_count": transferred_count
        })
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
                firestore_login(request, user)

                # Frontend will transfer apartments from sessionStorage via API call
                messages.success(
                    request,
                    f"Welcome {user.first_name or user.username}! Your account has been created successfully.",
                )

                return redirect("apartments:index")
            except Exception as e:
                logger.error(f"Error creating user: {e}")
                messages.error(
                    request,
                    "An error occurred while creating your account. Please try again.",
                )
    else:
        form = CustomUserCreationForm()

    # Check if there are apartments in sessionStorage (client-side check)
    apartment_count = 0  # Will be checked by JavaScript

    context = {
        "form": form,
        "apartment_count": apartment_count,
        "has_apartments_to_save": apartment_count > 0,
    }

    return render(request, "apartments/signup.html", context)


def login_view(request):
    """Handle user login"""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = firestore_authenticate(username, password)
            if user:
                firestore_login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")

                # Check if user has apartments and redirect accordingly
                firestore_service = FirestoreService()
                apartments = firestore_service.get_user_apartments(user.id)
                if apartments:
                    return redirect("apartments:dashboard")
                else:
                    return redirect("apartments:index")
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    return render(request, "apartments/login.html", {"form": form})


def logout_view(request):
    """Handle user logout with GET and POST requests"""
    firestore_logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect("apartments:index")


def google_oauth_callback(request):
    """Handle Google OAuth callback and redirect after social auth"""
    # This view is called after successful social auth
    # The pipeline should have already logged the user in

    # Check if user is in session (Firestore authentication)
    user_id = request.session.get("user_id")
    if user_id and hasattr(request, "user") and request.user.is_authenticated:
        logger.info(f"OAuth callback successful for user: {request.user.username}")
        messages.success(request, f"Welcome back, {request.user.username}!")

        # Check if user has apartments and redirect accordingly
        firestore_service = FirestoreService()
        apartments = firestore_service.get_user_apartments(user_id)
        if apartments:
            return redirect("apartments:dashboard")
        else:
            return redirect("apartments:index")
    else:
        logger.warning(
            f"OAuth callback failed - user_id: {user_id}, user authenticated: {hasattr(request, 'user') and request.user.is_authenticated}"
        )
        messages.error(request, "Authentication failed. Please try again.")
        return redirect("login")


@csrf_exempt
@require_http_methods(["POST"])
def sync_firebase_user(request):
    """Sync Firebase authenticated user with Firestore user collection"""
    try:
        data = json.loads(request.body)
        firebase_uid = data.get("uid")
        email = data.get("email")
        display_name = data.get("displayName", "")
        photo_url = data.get("photoURL", "")

        if not firebase_uid or not email:
            return JsonResponse({"error": "Missing required fields"}, status=400)

        firestore_service = FirestoreService()

        # Check if user already exists by email
        existing_user = firestore_service.get_user_by_email(email)

        if existing_user:
            # Update existing user with Firebase UID
            update_data = {
                "firebase_uid": firebase_uid,
                "photo_url": photo_url,
            }
            firestore_service.update_user(existing_user.doc_id, update_data)
            user = firestore_service.get_user(existing_user.doc_id)
        else:
            # Create new user
            # Generate username from display_name or email
            username = (
                display_name.lower().replace(" ", "")
                if display_name
                else email.split("@")[0]
            )

            # Ensure username is unique
            counter = 1
            base_username = username
            while firestore_service.get_user_by_username(username):
                username = f"{base_username}{counter}"
                counter += 1

            user_data = {
                "username": username,
                "email": email,
                "first_name": display_name.split(" ")[0] if display_name else "",
                "last_name": (
                    " ".join(display_name.split(" ")[1:])
                    if display_name and len(display_name.split(" ")) > 1
                    else ""
                ),
                "firebase_uid": firebase_uid,
                "photo_url": photo_url,
                "is_staff": False,  # New users start as free tier
            }

            # Create user without password (Firebase handles auth)
            user = firestore_service.create_firebase_user(user_data)

        # Log the user into Django session
        firestore_login(request, user)

        return JsonResponse(
            {
                "success": True,
                "user": {
                    "id": user.doc_id,
                    "username": user.username,
                    "email": user.email,
                    "is_staff": user.is_staff,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error syncing Firebase user: {e}")
        return JsonResponse({"error": "Internal server error"}, status=500)


def privacy_policy(request):
    """Display privacy policy page"""
    from datetime import datetime
    return render(request, "apartments/privacy.html", {
        "current_date": datetime.now().strftime("%B %d, %Y")
    })


def terms_of_service(request):
    """Display terms of service page"""
    from datetime import datetime
    return render(request, "apartments/terms.html", {
        "current_date": datetime.now().strftime("%B %d, %Y")
    })
