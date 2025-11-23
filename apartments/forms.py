from django import forms
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from .firestore_service import FirestoreService
import re


class CustomUserCreationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Username",
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm",
            }
        ),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "Email address",
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm",
            }
        ),
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "First name (optional)",
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm",
            }
        ),
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Last name (optional)",
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm",
            }
        ),
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm",
            }
        ),
        min_length=8,
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Confirm password",
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm",
            }
        ),
    )

    def clean_username(self):
        username = self.cleaned_data["username"]
        if not re.match(r"^[\w.@+-]+$", username):
            raise forms.ValidationError(
                "Username can only contain letters, numbers, and @/./+/-/_ characters."
            )

        # Check if username already exists
        firestore_service = FirestoreService()
        if firestore_service.get_user_by_username(username):
            raise forms.ValidationError("A user with this username already exists.")

        return username

    def clean_email(self):
        email = self.cleaned_data["email"]

        # Check if email already exists
        firestore_service = FirestoreService()
        if firestore_service.get_user_by_email(email):
            raise forms.ValidationError("A user with this email already exists.")

        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")

        return password2

    def save(self):
        """Create and return a new Firestore user"""
        firestore_service = FirestoreService()
        user_data = {
            "username": self.cleaned_data["username"],
            "email": self.cleaned_data["email"],
            "first_name": self.cleaned_data.get("first_name", ""),
            "last_name": self.cleaned_data.get("last_name", ""),
            "is_staff": False,  # New users start as free tier
        }
        return firestore_service.create_user(user_data, self.cleaned_data["password1"])


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Username",
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm",
            }
        ),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Password",
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm",
            }
        )
    )


class ApartmentForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        ),
    )
    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    square_footage = forms.IntegerField(
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        ),
    )
    lease_length_months = forms.IntegerField(
        validators=[MinValueValidator(1)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        ),
    )
    months_free = forms.IntegerField(
        initial=0,
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        ),
    )
    weeks_free = forms.IntegerField(
        initial=0,
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        ),
    )
    flat_discount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )


class UserPreferencesForm(forms.Form):
    DISCOUNT_CHOICES = [
        ("monthly", "Monthly"),
        ("weekly", "Weekly"),
        ("daily", "Daily"),
    ]

    price_weight = forms.IntegerField(
        initial=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    sqft_weight = forms.IntegerField(
        initial=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    distance_weight = forms.IntegerField(
        initial=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    discount_calculation = forms.ChoiceField(
        choices=DISCOUNT_CHOICES,
        initial="monthly",
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary"
            }
        ),
    )
