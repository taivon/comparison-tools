from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True, widget=forms.EmailInput(attrs={"placeholder": "Email address"})
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "First name (optional)"}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Last name (optional)"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"placeholder": "Username"})
        self.fields["email"].widget.attrs.update({"placeholder": "Email address"})
        self.fields["first_name"].widget.attrs.update({"placeholder": "First name"})
        self.fields["last_name"].widget.attrs.update({"placeholder": "Last name"})
        self.fields["password1"].widget.attrs.update({"placeholder": "Password"})
        self.fields["password2"].widget.attrs.update(
            {"placeholder": "Confirm password"}
        )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save()
        return user


class ApartmentForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        )
    )
    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        )
    )
    square_footage = forms.IntegerField(
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        )
    )
    lease_length_months = forms.IntegerField(
        validators=[MinValueValidator(1)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        )
    )
    months_free = forms.IntegerField(
        initial=0,
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        )
    )
    weeks_free = forms.IntegerField(
        initial=0,
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        )
    )
    flat_discount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        )
    )


class UserPreferencesForm(forms.Form):
    DISCOUNT_CHOICES = [
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily')
    ]
    
    price_weight = forms.IntegerField(
        initial=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput()
    )
    sqft_weight = forms.IntegerField(
        initial=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput()
    )
    distance_weight = forms.IntegerField(
        initial=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput()
    )
    discount_calculation = forms.ChoiceField(
        choices=DISCOUNT_CHOICES,
        initial='monthly',
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        )
    )
