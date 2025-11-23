from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.http import JsonResponse
from .models import Apartment, UserPreferences
from .forms import ApartmentForm, UserPreferencesForm, CustomUserCreationForm
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

@login_required
def index(request):
    apartments = Apartment.objects.filter(user=request.user)
    preferences = UserPreferences.objects.filter(user=request.user).first()
    
    # Handle preferences form submission
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=preferences)
        if form.is_valid():
            prefs = form.save(commit=False)
            prefs.user = request.user
            prefs.save()
            messages.success(request, "Preferences updated successfully!")
            return redirect('apartments:index')
    else:
        form = UserPreferencesForm(instance=preferences)
    
    # Sort apartments based on user preferences
    if preferences:
        apartments = sorted(apartments, key=lambda x: (
            (x.net_effective_price * preferences.price_weight) +
            (x.square_footage * preferences.sqft_weight) +
            (0 * preferences.distance_weight)  # Distance is not implemented yet
        ), reverse=True)  # Sort in descending order
    
    context = {
        'apartments': apartments,
        'preferences': preferences,
        'form': form,  # Add the form to the context
        'is_premium': request.user.is_staff,  # Temporary premium check
    }
    return render(request, 'apartments/index.html', context)

@login_required
def create_apartment(request):
    if request.method == 'POST':
        form = ApartmentForm(request.POST)
        logger.debug(f"Form data: {request.POST}")
        if form.is_valid():
            logger.debug("Form is valid")
            apartment = form.save(commit=False)
            apartment.user = request.user
            
            # Check free tier limit
            if not request.user.is_staff and Apartment.objects.filter(user=request.user).count() >= 2:
                messages.error(request, "Free tier limit reached. Upgrade to premium to add more apartments.")
                return redirect('apartments:index')
            
            try:
                apartment.save()
                messages.success(request, "Apartment added successfully!")
                return redirect('apartments:index')
            except Exception as e:
                logger.error(f"Error saving apartment: {str(e)}")
                messages.error(request, "An error occurred while saving the apartment.")
        else:
            logger.error(f"Form errors: {form.errors}")
            messages.error(request, "Please correct the errors below.")
    else:
        form = ApartmentForm()
    
    return render(request, 'apartments/apartment_form.html', {'form': form})

@login_required
def update_apartment(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk, user=request.user)
    if request.method == 'POST':
        form = ApartmentForm(request.POST, instance=apartment)
        if form.is_valid():
            form.save()
            messages.success(request, "Apartment updated successfully!")
            return redirect('apartments:index')
    else:
        form = ApartmentForm(instance=apartment)
    
    return render(request, 'apartments/apartment_form.html', {'form': form})

@login_required
def delete_apartment(request, pk):
    apartment = get_object_or_404(Apartment, pk=pk, user=request.user)
    if request.method == 'POST':
        apartment.delete()
        messages.success(request, "Apartment deleted successfully!")
    return redirect('apartments:index')

@login_required
def update_preferences(request):
    preferences = UserPreferences.objects.filter(user=request.user).first()
    
    if request.method == 'POST':
        form = UserPreferencesForm(request.POST, instance=preferences)
        if form.is_valid():
            prefs = form.save(commit=False)
            prefs.user = request.user
            prefs.save()
            messages.success(request, "Preferences updated successfully!")
            return redirect('apartments:index')
    else:
        form = UserPreferencesForm(instance=preferences)
    
    return render(request, 'apartments/preferences_form.html', {'form': form})

def logout_view(request):
    """Handle user logout with GET and POST requests"""
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')
