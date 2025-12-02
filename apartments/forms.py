import re
from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.validators import MaxValueValidator, MinValueValidator


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
            raise forms.ValidationError("Username can only contain letters, numbers, and @/./+/-/_ characters.")

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with this username already exists.")

        return username

    def clean_email(self):
        email = self.cleaned_data["email"]

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")

        return email

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if password1:
            validate_password(password1)
        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")

        return password2

    def save(self):
        """Create and return a new Django user"""
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data.get("first_name", ""),
            last_name=self.cleaned_data.get("last_name", ""),
        )
        return user


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
    address = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
                "placeholder": "Start typing an address...",
                "data-address-autocomplete": "true",
                "autocomplete": "off",
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
    bedrooms = forms.ChoiceField(
        choices=[("0", "Studio")] + [(str(i), str(i)) for i in range(1, 16)],
        initial="1",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    bathrooms = forms.ChoiceField(
        choices=[
            (str(Decimal(str(i)) / 2), str(Decimal(str(i)) / 2) if i % 2 == 0 else f"{i // 2}.5") for i in range(1, 31)
        ],
        initial="1",
        required=False,
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
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
    # Additional cost fields
    parking_cost = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary pl-7",
            }
        ),
    )
    utilities = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary pl-7",
            }
        ),
    )
    # Quality/amenity fields
    view_quality = forms.ChoiceField(
        choices=[
            (0, "Not Rated"),
            (1, "1 - Poor"),
            (2, "2 - Fair"),
            (3, "3 - Average"),
            (4, "4 - Good"),
            (5, "5 - Excellent"),
        ],
        initial=0,
        required=False,
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    has_balcony = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                "class": "h-4 w-4 text-brand-purple focus:ring-brand-purple border-gray-300 rounded",
            }
        ),
    )


class UserPreferencesForm(forms.Form):
    DISCOUNT_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
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
    # Premium scoring factors
    net_rent_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    total_cost_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    bedrooms_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    bathrooms_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    discount_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    parking_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    utilities_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    view_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    balcony_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    discount_calculation = forms.ChoiceField(
        choices=DISCOUNT_CHOICES,
        initial="daily",
        widget=forms.RadioSelect(
            attrs={"class": "mt-0.5 h-4 w-4 text-brand-purple focus:ring-brand-purple border-gray-300"}
        ),
    )
    PRICE_PER_SQFT_CHOICES = [
        ("base", "Monthly Rent"),
        ("net_effective", "Net Effective"),
        ("total_cost", "Total Cost"),
    ]
    price_per_sqft_basis = forms.ChoiceField(
        choices=PRICE_PER_SQFT_CHOICES,
        initial="net_effective",
        widget=forms.RadioSelect(
            attrs={"class": "mt-0.5 h-4 w-4 text-brand-purple focus:ring-brand-purple border-gray-300"}
        ),
    )
    PRICING_SORT_CHOICES = [
        ("base", "Base Rent"),
        ("net_effective", "Net Effective"),
        ("total_cost", "Total Cost"),
    ]
    pricing_sort_basis = forms.ChoiceField(
        choices=PRICING_SORT_CHOICES,
        initial="base",
        widget=forms.RadioSelect(
            attrs={"class": "mt-0.5 h-4 w-4 text-brand-purple focus:ring-brand-purple border-gray-300"}
        ),
    )
    factor_order = forms.CharField(
        initial="price,sqft,distance,netRent,totalCost,bedrooms,bathrooms,discount,parking,utilities,view,balcony",
        required=False,
        widget=forms.HiddenInput(),
    )


class FavoritePlaceForm(forms.Form):
    """Form for creating/editing favorite places"""

    label = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
                "placeholder": "e.g., Work, Gym, Parents House",
            }
        ),
    )
    address = forms.CharField(
        max_length=500,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
                "placeholder": "Start typing an address...",
                "data-address-autocomplete": "true",
                "autocomplete": "off",
            }
        ),
    )
    travel_mode = forms.ChoiceField(
        choices=[("driving", "Driving"), ("transit", "Transit")],
        initial="driving",
        widget=forms.RadioSelect(attrs={"class": "h-4 w-4 text-brand-purple focus:ring-brand-purple border-gray-300"}),
    )
    time_type = forms.ChoiceField(
        choices=[("departure", "Departure Time"), ("arrival", "Arrival Time")],
        initial="departure",
        widget=forms.RadioSelect(attrs={"class": "h-4 w-4 text-brand-purple focus:ring-brand-purple border-gray-300"}),
    )
    day_of_week = forms.ChoiceField(
        choices=[
            (0, "Monday"),
            (1, "Tuesday"),
            (2, "Wednesday"),
            (3, "Thursday"),
            (4, "Friday"),
            (5, "Saturday"),
            (6, "Sunday"),
        ],
        initial=5,
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    time_of_day = forms.TimeField(
        initial="12:00",
        widget=forms.TimeInput(
            attrs={
                "type": "time",
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
