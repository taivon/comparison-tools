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
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary'
            }),
            'price': forms.NumberInput(attrs={
                'step': '0.01',
                'class': 'mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary'
            }),
            'square_footage': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary'
            }),
            'lease_length_months': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary'
            }),
            'months_free': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary'
            }),
            'weeks_free': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary'
            }),
            'flat_discount': forms.NumberInput(attrs={
                'step': '0.01',
                'class': 'mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary'
            }),
        }

class UserPreferencesForm(forms.ModelForm):
    class Meta:
        model = UserPreferences
        fields = ['price_weight', 'sqft_weight', 'distance_weight', 'discount_calculation']
        widgets = {
            'price_weight': forms.HiddenInput(),
            'sqft_weight': forms.HiddenInput(),
            'distance_weight': forms.HiddenInput(),
            'discount_calculation': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary'
            }),
        } 