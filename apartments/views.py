from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.http import JsonResponse, Http404
from .firestore_service import FirestoreService, FirestoreApartment, FirestoreUserPreferences
from .forms import ApartmentForm, UserPreferencesForm, CustomUserCreationForm
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


@login_required
def index(request):
    firestore_service = FirestoreService()
    apartments = firestore_service.get_user_apartments(request.user.id)
    preferences = firestore_service.get_user_preferences(request.user.id)

    # Handle preferences form submission
    if request.method == "POST":
        form = UserPreferencesForm(request.POST)
        if form.is_valid():
            preferences_data = {
                'price_weight': form.cleaned_data['price_weight'],
                'sqft_weight': form.cleaned_data['sqft_weight'],
                'distance_weight': form.cleaned_data['distance_weight'],
                'discount_calculation': form.cleaned_data['discount_calculation']
            }
            firestore_service.update_user_preferences(request.user.id, preferences_data)
            messages.success(request, "Preferences updated successfully!")
            return redirect("apartments:index")
    else:
        # Create form with current preferences values
        initial_data = {}
        if preferences:
            initial_data = {
                'price_weight': preferences.price_weight,
                'sqft_weight': preferences.sqft_weight,
                'distance_weight': preferences.distance_weight,
                'discount_calculation': preferences.discount_calculation
            }
        form = UserPreferencesForm(initial=initial_data)

    # Sort apartments based on user preferences
    if preferences and apartments:
        apartments = sorted(
            apartments,
            key=lambda x: (
                (float(x.net_effective_price(preferences)) * preferences.price_weight)
                + (x.square_footage * preferences.sqft_weight)
                + (0 * preferences.distance_weight)  # Distance is not implemented yet
            ),
            reverse=True,
        )  # Sort in descending order

    context = {
        "apartments": apartments,
        "preferences": preferences,
        "form": form,  # Add the form to the context
        "is_premium": request.user.is_staff,  # Temporary premium check
    }
    return render(request, "apartments/index.html", context)


@login_required
def create_apartment(request):
    if request.method == "POST":
        form = ApartmentForm(request.POST)
        logger.debug(f"Form data: {request.POST}")
        if form.is_valid():
            logger.debug("Form is valid")

            # Check free tier limit
            firestore_service = FirestoreService()
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
                apartment_data = {
                    'name': form.cleaned_data['name'],
                    'price': form.cleaned_data['price'],
                    'square_footage': form.cleaned_data['square_footage'],
                    'lease_length_months': form.cleaned_data['lease_length_months'],
                    'months_free': form.cleaned_data['months_free'],
                    'weeks_free': form.cleaned_data['weeks_free'],
                    'flat_discount': form.cleaned_data['flat_discount'],
                    'user_id': str(request.user.id)
                }
                firestore_service.create_apartment(apartment_data)
                messages.success(request, "Apartment added successfully!")
                return redirect("apartments:index")
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
    firestore_service = FirestoreService()
    apartment = firestore_service.get_apartment(pk)
    
    if not apartment or apartment.user_id != str(request.user.id):
        raise Http404("Apartment not found")
    
    if request.method == "POST":
        form = ApartmentForm(request.POST)
        if form.is_valid():
            apartment_data = {
                'name': form.cleaned_data['name'],
                'price': form.cleaned_data['price'],
                'square_footage': form.cleaned_data['square_footage'],
                'lease_length_months': form.cleaned_data['lease_length_months'],
                'months_free': form.cleaned_data['months_free'],
                'weeks_free': form.cleaned_data['weeks_free'],
                'flat_discount': form.cleaned_data['flat_discount']
            }
            firestore_service.update_apartment(pk, apartment_data)
            messages.success(request, "Apartment updated successfully!")
            return redirect("apartments:index")
    else:
        # Initialize form with current apartment data
        initial_data = {
            'name': apartment.name,
            'price': apartment.price,
            'square_footage': apartment.square_footage,
            'lease_length_months': apartment.lease_length_months,
            'months_free': apartment.months_free,
            'weeks_free': apartment.weeks_free,
            'flat_discount': apartment.flat_discount
        }
        form = ApartmentForm(initial=initial_data)

    return render(request, "apartments/apartment_form.html", {"form": form})


@login_required
def delete_apartment(request, pk):
    firestore_service = FirestoreService()
    apartment = firestore_service.get_apartment(pk)
    
    if not apartment or apartment.user_id != str(request.user.id):
        raise Http404("Apartment not found")
    
    if request.method == "POST":
        firestore_service.delete_apartment(pk)
        messages.success(request, "Apartment deleted successfully!")
    return redirect("apartments:index")


@login_required
def update_preferences(request):
    firestore_service = FirestoreService()
    preferences = firestore_service.get_user_preferences(request.user.id)

    if request.method == "POST":
        form = UserPreferencesForm(request.POST)
        if form.is_valid():
            preferences_data = {
                'price_weight': form.cleaned_data['price_weight'],
                'sqft_weight': form.cleaned_data['sqft_weight'],
                'distance_weight': form.cleaned_data['distance_weight'],
                'discount_calculation': form.cleaned_data['discount_calculation']
            }
            firestore_service.update_user_preferences(request.user.id, preferences_data)
            messages.success(request, "Preferences updated successfully!")
            return redirect("apartments:index")
    else:
        # Initialize form with current preferences
        initial_data = {}
        if preferences:
            initial_data = {
                'price_weight': preferences.price_weight,
                'sqft_weight': preferences.sqft_weight,
                'distance_weight': preferences.distance_weight,
                'discount_calculation': preferences.discount_calculation
            }
        form = UserPreferencesForm(initial=initial_data)

    return render(request, "apartments/preferences_form.html", {"form": form})


def signup_view(request):
    """Handle user registration"""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Welcome {user.first_name or user.username}! Your account has been created successfully.",
            )
            login(request, user)
            return redirect("apartments:index")
    else:
        form = CustomUserCreationForm()

    return render(request, "apartments/signup.html", {"form": form})


def logout_view(request):
    """Handle user logout with GET and POST requests"""
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect("login")
