from django import forms
from .models import Apartment, UserPreferences

class ApartmentForm(forms.ModelForm):
    class Meta:
        model = Apartment
        fields = [
            'name', 'price', 'square_footage', 'lease_length_months',
            'months_free', 'weeks_free', 'flat_discount'
        ]
        widgets = {
            'price': forms.NumberInput(attrs={'step': '0.01'}),
            'flat_discount': forms.NumberInput(attrs={'step': '0.01'}),
        }

class UserPreferencesForm(forms.ModelForm):
    class Meta:
        model = UserPreferences
        fields = ['price_weight', 'sqft_weight', 'distance_weight', 'discount_calculation']
        widgets = {
            'price_weight': forms.HiddenInput(),
            'sqft_weight': forms.HiddenInput(),
            'distance_weight': forms.HiddenInput(),
        } 