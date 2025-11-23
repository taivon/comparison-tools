from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Apartment, UserPreferences

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm'
    }))
    first_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={
        'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm'
    }))
    last_name = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={
        'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm'
    }))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm',
            'placeholder': 'Username'
        })
        self.fields['email'].widget.attrs.update({
            'placeholder': 'Email address'
        })
        self.fields['first_name'].widget.attrs.update({
            'placeholder': 'First name (optional)'
        })
        self.fields['last_name'].widget.attrs.update({
            'placeholder': 'Last name (optional)'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm',
            'placeholder': 'Password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm',
            'placeholder': 'Confirm password'
        })

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user

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