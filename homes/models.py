from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

# Import shared models from apartments app
from apartments.models import (
    FavoritePlace,
    user_has_premium,
)

# =============================================================================
# Home Comparison Models
# =============================================================================


class Home(models.Model):
    """Home/condo for purchase comparison"""

    SOURCE_CHOICES = [
        ("manual", "Manual Entry"),
        ("mls", "MLS"),
        ("zillow", "Zillow"),
        ("redfin", "Redfin"),
    ]

    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    square_footage = models.IntegerField(validators=[MinValueValidator(0)])
    bedrooms = models.DecimalField(
        max_digits=3, decimal_places=1, default=1, validators=[MinValueValidator(Decimal("0"))]
    )
    bathrooms = models.DecimalField(
        max_digits=3, decimal_places=1, default=1, validators=[MinValueValidator(Decimal("0.5"))]
    )

    # Location fields
    address = models.CharField(max_length=500, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Home-specific fields
    hoa_fees = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )
    property_taxes = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )
    year_built = models.IntegerField(
        null=True, blank=True, validators=[MinValueValidator(1800), MaxValueValidator(2100)]
    )
    lot_size_sqft = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(0)])

    # API source fields
    mls_number = models.CharField(max_length=50, blank=True, default="")
    zillow_id = models.CharField(max_length=100, blank=True, default="")
    redfin_id = models.CharField(max_length=100, blank=True, default="")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="manual")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_home_name_per_user"),
        ]

    def __str__(self):
        return self.name

    @property
    def total_monthly_cost(self):
        """
        Calculate estimated total monthly cost excluding mortgage:
        HOA fees + (property taxes / 12).

        Note: Mortgage payment is intentionally not included here until a proper
        calculation (with interest rate, term, and down payment) is implemented.
        """
        hoa = self.hoa_fees if self.hoa_fees else Decimal("0")
        taxes_monthly = (self.property_taxes / Decimal("12")) if self.property_taxes else Decimal("0")
        return round(hoa + taxes_monthly, 2)

    @property
    def price_per_sqft(self):
        """Price per square foot"""
        if self.square_footage > 0:
            return round(self.price / Decimal(str(self.square_footage)), 2)
        return Decimal("0")


class HomePreferences(models.Model):
    """User preferences for home scoring"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="home_preferences")
    price_weight = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    sqft_weight = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    distance_weight = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Home-specific scoring weights
    hoa_fees_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    property_taxes_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    lot_size_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    year_built_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    bedrooms_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    bathrooms_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Store the explicit order of scoring factors
    factor_order = models.CharField(
        max_length=300,
        default="price,sqft,distance,hoaFees,propertyTaxes,lotSize,yearBuilt,bedrooms,bathrooms",
        blank=True,
    )

    def __str__(self):
        return f"Home Preferences for {self.user.username}"


class HomeScore(models.Model):
    """Cached home scores for each user"""

    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name="scores")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="home_scores")
    score = models.DecimalField(
        max_digits=3, decimal_places=1, validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("10"))]
    )
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["home", "user"]
        ordering = ["-score", "home__name"]

    def __str__(self):
        return f"{self.home.name} - {self.user.username}: {self.score}/10"


class HomeDistance(models.Model):
    """Cached distance between a home and a favorite place"""

    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name="distances")
    favorite_place = models.ForeignKey(FavoritePlace, on_delete=models.CASCADE, related_name="home_distances")
    distance_miles = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    travel_time_minutes = models.IntegerField(null=True, blank=True)
    transit_fare = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, help_text="Transit fare in USD"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["home", "favorite_place"]
        ordering = ["favorite_place__label"]

    def __str__(self):
        return f"{self.home.name} -> {self.favorite_place.label}: {self.distance_miles} mi"


# =============================================================================
# Real Estate Agent Models
# =============================================================================


class RealEstateAgent(models.Model):
    """Real estate agent profile"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="real_estate_agent")
    license_number = models.CharField(max_length=100, blank=True, default="")
    brokerage_name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Agent: {self.user.get_full_name() or self.user.username}"

    def is_agent_tier_active(self) -> bool:
        """Check if agent has active agent-tier subscription"""
        return user_has_premium(self.user, "homes-agent")


class AgentClientRelationship(models.Model):
    """Relationship between an agent and their client"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("declined", "Declined"),
    ]

    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="agent_relationships")
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="client_relationships")
    invite_code = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    linked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("agent", "client")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent.username} -> {self.client.username} ({self.status})"


class AgentInviteCode(models.Model):
    """Invite codes that agents can generate for clients"""

    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="invite_codes")
    code = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    max_uses = models.IntegerField(null=True, blank=True)
    uses_count = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} (Agent: {self.agent.username})"

    def is_valid(self) -> bool:
        """Check if invite code is still valid"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.max_uses and self.uses_count >= self.max_uses:
            return False
        return True


class HomeSuggestion(models.Model):
    """Agent's suggestion of a home to a client"""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="home_suggestions")
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name="suggested_homes")
    home = models.ForeignKey(Home, on_delete=models.CASCADE, related_name="suggestions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    message = models.TextField(blank=True, default="")
    suggested_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("agent", "client", "home")]
        ordering = ["-suggested_at"]

    def __str__(self):
        return f"{self.agent.username} suggested {self.home.name} to {self.client.username} ({self.status})"


# =============================================================================
# Helper Functions
# =============================================================================


def get_favorite_place_limit(user, product_slug: str = "homes") -> int:
    """Returns max favorite places allowed: 1 for free, 5 for pro"""
    if user_has_premium(user, product_slug):
        return 5
    return 1


def can_add_favorite_place(user, product_slug: str = "homes") -> bool:
    """Check if user can add another favorite place"""
    if not user.is_authenticated:
        return False
    current_count = FavoritePlace.objects.filter(user=user).count()
    limit = get_favorite_place_limit(user, product_slug)
    return current_count < limit


def get_favorite_place_count(user) -> int:
    """Get current count of user's favorite places"""
    if not user.is_authenticated:
        return 0
    return FavoritePlace.objects.filter(user=user).count()
