from django import forms

# Common Tailwind CSS classes matching project patterns
INPUT_CLASS = "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm"
TEXTAREA_CLASS = "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm"
SELECT_CLASS = "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-brand-purple focus:ring-brand-purple sm:text-sm"


class FeedbackForm(forms.Form):
    """Form for submitting general feedback"""

    CATEGORY_CHOICES = [
        ("bug", "Bug Report"),
        ("feature", "Feature Request"),
        ("other", "Other"),
    ]

    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        initial="other",
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": TEXTAREA_CLASS,
                "rows": 5,
                "placeholder": "Tell us what you think...",
            }
        ),
        min_length=10,
        max_length=2000,
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "your@email.com (optional)",
            }
        ),
        help_text="Optional - provide if you'd like us to follow up",
    )
    page_url = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )


class FeatureRequestForm(forms.Form):
    """Form for submitting new feature ideas"""

    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "Brief title for your idea...",
            }
        ),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": TEXTAREA_CLASS,
                "rows": 4,
                "placeholder": "Describe your idea in more detail (optional)...",
            }
        ),
        max_length=2000,
    )
