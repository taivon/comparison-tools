from decimal import Decimal

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from .models import Home


class HomeForm(forms.Form):
    """Form for creating/editing homes"""

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
    # Home-specific fields
    hoa_fees = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=Decimal("0"),
        required=False,
        validators=[MinValueValidator(Decimal("0"))],
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    property_taxes = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=Decimal("0"),
        required=False,
        validators=[MinValueValidator(Decimal("0"))],
        widget=forms.NumberInput(
            attrs={
                "step": "0.01",
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    year_built = forms.IntegerField(
        required=False,
        validators=[MinValueValidator(1800), MaxValueValidator(2100)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
                "placeholder": "e.g., 2020",
            }
        ),
    )
    lot_size_sqft = forms.IntegerField(
        required=False,
        validators=[MinValueValidator(0)],
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
                "placeholder": "e.g., 5000",
            }
        ),
    )
    # API source fields (hidden, set programmatically)
    mls_number = forms.CharField(max_length=50, required=False, widget=forms.HiddenInput())
    zillow_id = forms.CharField(max_length=100, required=False, widget=forms.HiddenInput())
    redfin_id = forms.CharField(max_length=100, required=False, widget=forms.HiddenInput())
    source = forms.ChoiceField(
        choices=Home.SOURCE_CHOICES,
        initial="manual",
        required=False,
        widget=forms.HiddenInput(),
    )


class HomePreferencesForm(forms.Form):
    """Form for home scoring preferences"""

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
    # Home-specific scoring weights
    hoa_fees_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    property_taxes_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    lot_size_weight = forms.IntegerField(
        initial=0,
        required=False,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        widget=forms.HiddenInput(),
    )
    year_built_weight = forms.IntegerField(
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
    factor_order = forms.CharField(
        initial="price,sqft,distance,hoaFees,propertyTaxes,lotSize,yearBuilt,bedrooms,bathrooms",
        required=False,
        widget=forms.HiddenInput(),
    )


class InviteCodeForm(forms.Form):
    """Form for entering an agent invite code"""

    code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
                "placeholder": "Enter invite code",
                "autocomplete": "off",
            }
        ),
    )

    def clean_code(self):
        code = self.cleaned_data.get("code", "").strip().upper()
        if not code:
            raise forms.ValidationError("Invite code is required.")
        return code


class HomeSuggestionForm(forms.Form):
    """Form for agent to suggest a home to a client"""

    home = forms.ModelChoiceField(
        queryset=Home.objects.none(),  # Will be set in view
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    client = forms.ModelChoiceField(
        queryset=None,  # Will be set in view
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
                "rows": 4,
                "placeholder": "Optional message explaining why you're suggesting this home...",
            }
        ),
    )


class AgentProfileForm(forms.Form):
    """Form for agent profile information"""

    license_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    brokerage_name = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-secondary shadow-sm focus:border-primary focus:ring-primary sm:text-sm bg-white text-secondary",
            }
        ),
    )


class RedfinCSVImportForm(forms.Form):
    """Form for uploading Redfin CSV export file"""

    csv_file = forms.FileField(
        widget=forms.FileInput(
            attrs={
                "class": "hidden",
                "accept": ".csv,.xlsx,.xls",
                "id": "csv-file-input",
            }
        ),
        help_text="Upload a CSV file exported from Redfin (max 350 homes)",
    )

    def clean_csv_file(self):
        file = self.cleaned_data.get("csv_file")
        if file:
            # Check file extension
            name = file.name.lower()
            if not name.endswith((".csv", ".xlsx", ".xls")):
                raise forms.ValidationError("Please upload a CSV or Excel file.")

            # Check file size (max 5MB)
            if file.size > 5 * 1024 * 1024:
                raise forms.ValidationError("File size must be less than 5MB.")

        return file
