from decimal import Decimal

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

# =============================================================================
# Product & Subscription Models
# =============================================================================


class Product(models.Model):
    """Represents a comparison tool product (apartments, homes, cars, hotels, bundle)"""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    free_tier_limit = models.IntegerField(default=2)  # Items allowed on free tier
    pro_tier_limit = models.IntegerField(default=20)  # Items allowed on pro tier
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Plan(models.Model):
    """Subscription plan for a product (Free, Pro Monthly, Pro Annual, Pro Lifetime)"""

    TIER_CHOICES = [
        ("free", "Free"),
        ("pro", "Pro"),
    ]
    INTERVAL_CHOICES = [
        ("", "None"),
        ("month", "Monthly"),
        ("year", "Annual"),
        ("lifetime", "Lifetime"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="plans")
    name = models.CharField(max_length=100)  # "Free", "Pro Monthly", "Pro Annual"
    tier = models.CharField(max_length=50, choices=TIER_CHOICES, default="free")
    stripe_price_id = models.CharField(max_length=200, blank=True)
    price_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billing_interval = models.CharField(max_length=20, choices=INTERVAL_CHOICES, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["product", "tier", "billing_interval"]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class Subscription(models.Model):
    """User's subscription to a product plan"""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("canceled", "Canceled"),
        ("past_due", "Past Due"),
        ("trialing", "Trialing"),
        ("incomplete", "Incomplete"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="subscriptions")
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="active")
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.plan}"

    @property
    def is_premium_active(self):
        """Check if this subscription grants premium access"""
        if self.plan.tier != "pro":
            return False

        # Lifetime plans are always active once purchased
        if self.plan.billing_interval == "lifetime":
            return self.status == "active"

        if self.status == "active":
            return True

        # Grace period for canceled/past_due
        if self.status in ["canceled", "past_due"] and self.current_period_end:
            return self.current_period_end > timezone.now()

        return False


# =============================================================================
# Subscription Helper Functions
# =============================================================================


def get_user_subscription(user, product_slug: str):
    """
    Get user's active subscription for a product.
    Also checks for bundle subscription which grants access to all products.
    """
    if not user.is_authenticated:
        return None

    # First check for product-specific subscription
    try:
        return Subscription.objects.select_related("plan", "plan__product").get(
            user=user, plan__product__slug=product_slug, status__in=["active", "trialing", "canceled", "past_due"]
        )
    except Subscription.DoesNotExist:
        pass

    # Check for bundle subscription
    try:
        return Subscription.objects.select_related("plan", "plan__product").get(
            user=user, plan__product__slug="bundle", status__in=["active", "trialing", "canceled", "past_due"]
        )
    except Subscription.DoesNotExist:
        return None


def user_has_premium(user, product_slug: str) -> bool:
    """Check if user has premium access for a specific product."""
    if not user.is_authenticated:
        return False

    # Staff and superusers always have premium access
    if user.is_staff or user.is_superuser:
        return True

    subscription = get_user_subscription(user, product_slug)
    if subscription:
        return subscription.is_premium_active

    return False


def get_product_free_tier_limit(product_slug: str) -> int:
    """Get the free tier limit for a product."""
    try:
        product = Product.objects.get(slug=product_slug)
        return product.free_tier_limit
    except Product.DoesNotExist:
        return 2  # Default


def get_product_pro_tier_limit(product_slug: str) -> int:
    """Get the pro tier limit for a product."""
    try:
        product = Product.objects.get(slug=product_slug)
        return product.pro_tier_limit
    except Product.DoesNotExist:
        return 20  # Default


def get_user_item_limit(user, product_slug: str) -> int:
    """Get the item limit for a user based on their subscription status."""
    if user_has_premium(user, product_slug):
        return get_product_pro_tier_limit(product_slug)
    return get_product_free_tier_limit(product_slug)


# =============================================================================
# User Profile Model
# =============================================================================


class UserProfile(models.Model):
    """Extended user profile with Stripe customer data"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    photo_url = models.URLField(max_length=500, blank=True, default="")
    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")

    def __str__(self):
        return f"Profile for {self.user.username}"


# =============================================================================
# Apartment Comparison Models
# =============================================================================


class Apartment(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    square_footage = models.IntegerField(validators=[MinValueValidator(0)])
    bedrooms = models.DecimalField(
        max_digits=3, decimal_places=1, default=1, validators=[MinValueValidator(Decimal("0"))]
    )  # Supports 0.5 for studios
    bathrooms = models.DecimalField(
        max_digits=3, decimal_places=1, default=1, validators=[MinValueValidator(Decimal("0.5"))]
    )  # Supports 1.5, 2.5, etc.
    lease_length_months = models.IntegerField(validators=[MinValueValidator(1)])

    # Location fields
    address = models.CharField(max_length=500, blank=True, default="")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Discount fields
    months_free = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    weeks_free = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    flat_discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )

    # Additional cost fields
    parking_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )
    utilities = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"), validators=[MinValueValidator(Decimal("0"))]
    )

    # Quality/amenity fields
    view_quality = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Rating for windows/sunlight/view (0=not rated, 1-5 scale)",
    )
    has_balcony = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "name"], name="unique_apartment_name_per_user"),
        ]

    def __str__(self):
        return self.name

    @property
    def price_per_sqft(self):
        """Price per square foot based on user's preferred price basis."""
        if self.square_footage > 0:
            user_preferences, _ = UserPreferences.objects.get_or_create(
                user=self.user,
                defaults={"price_weight": 50, "sqft_weight": 50, "distance_weight": 50},
            )
            basis = getattr(user_preferences, "price_per_sqft_basis", "net_effective")
            if basis == "base":
                price = self.price
            elif basis == "total_cost":
                price = self.total_cost
            else:  # net_effective (default)
                price = self.net_effective_price
            return round(price / Decimal(str(self.square_footage)), 2)
        else:
            return Decimal("0")

    @property
    def net_effective_price(self):
        total_discount = Decimal("0")
        # Use Django's cached relation first to avoid N+1 queries
        try:
            user_preferences = self.user.preferences
        except UserPreferences.DoesNotExist:
            user_preferences, _ = UserPreferences.objects.get_or_create(
                user=self.user,
                defaults={
                    "price_weight": 50,
                    "sqft_weight": 50,
                    "distance_weight": 50,
                    "discount_calculation": "weekly",
                },
            )

        if user_preferences.discount_calculation == "daily":
            daily_rate = self.price * Decimal("12") / Decimal("365")
            if self.months_free > 0:
                days_free_from_months = Decimal(str(self.months_free)) * Decimal("365") / Decimal("12")
                total_discount += daily_rate * days_free_from_months
            if self.weeks_free > 0:
                total_discount += daily_rate * Decimal("7") * Decimal(str(self.weeks_free))
        elif user_preferences.discount_calculation == "weekly":
            weekly_rate = self.price * Decimal("12") / Decimal("52")
            if self.months_free > 0:
                weeks_free_from_months = Decimal(str(self.months_free)) * Decimal("52") / Decimal("12")
                total_discount += weekly_rate * weeks_free_from_months
            if self.weeks_free > 0:
                total_discount += weekly_rate * Decimal(str(self.weeks_free))
        else:  # monthly
            if self.months_free > 0:
                total_discount += self.price * Decimal(str(self.months_free))
            if self.weeks_free > 0:
                total_discount += self.price * Decimal(str(self.weeks_free / 4))

        total_discount += self.flat_discount
        total_lease_value = self.price * Decimal(str(self.lease_length_months))
        net_price = (total_lease_value - total_discount) / Decimal(str(self.lease_length_months))
        return round(net_price, 2)

    @property
    def total_cost(self):
        """Calculate total monthly cost: net effective rent + parking + utilities"""
        base_cost = self.net_effective_price
        parking = self.parking_cost if self.parking_cost else Decimal("0")
        utils = self.utilities if self.utilities else Decimal("0")
        return round(base_cost + parking + utils, 2)


class UserPreferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="preferences")
    price_weight = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    sqft_weight = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    distance_weight = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Additional scoring weights (Pro features)
    net_rent_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    total_cost_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    bedrooms_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    bathrooms_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    discount_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    parking_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    utilities_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    view_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    balcony_weight = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    discount_calculation = models.CharField(
        max_length=20, choices=[("monthly", "Monthly"), ("weekly", "Weekly"), ("daily", "Daily")], default="weekly"
    )

    # Which price to use for $/sqft calculation
    price_per_sqft_basis = models.CharField(
        max_length=20,
        choices=[("base", "Monthly Rent"), ("net_effective", "Net Effective"), ("total_cost", "Total Cost")],
        default="net_effective",
    )

    # Which price to use for sorting the Pricing column
    pricing_sort_basis = models.CharField(
        max_length=20,
        choices=[("base", "Base Rent"), ("net_effective", "Net Effective"), ("total_cost", "Total Cost")],
        default="base",
    )

    # Store the explicit order of scoring factors (comma-separated factor keys)
    # Default order: price,sqft,distance,netRent,totalCost,bedrooms,bathrooms,discount,parking,utilities,view,balcony
    factor_order = models.CharField(
        max_length=300,
        default="price,sqft,distance,netRent,totalCost,bedrooms,bathrooms,discount,parking,utilities,view,balcony",
        blank=True,
    )

    def __str__(self):
        return f"Preferences for {self.user.username}"


class ApartmentScore(models.Model):
    """
    Cached apartment scores for each user.
    Scores are user-specific since they depend on user preferences.
    """

    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="scores")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="apartment_scores")
    score = models.DecimalField(
        max_digits=3, decimal_places=1, validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("10"))]
    )
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["apartment", "user"]
        ordering = ["-score", "apartment__name"]

    def __str__(self):
        return f"{self.apartment.name} - {self.user.username}: {self.score}/10"


# =============================================================================
# Favorite Places Models
# =============================================================================


class FavoritePlace(models.Model):
    """A user's favorite place (e.g., Work, Gym) for distance calculations"""

    TRAVEL_MODE_CHOICES = [
        ("driving", "Driving"),
        ("transit", "Transit"),
    ]

    TIME_TYPE_CHOICES = [
        ("departure", "Departure Time"),
        ("arrival", "Arrival Time"),
    ]

    DAY_OF_WEEK_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorite_places")
    label = models.CharField(max_length=100)  # e.g., "Work", "Gym"
    address = models.CharField(max_length=500)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Travel preferences
    travel_mode = models.CharField(max_length=20, choices=TRAVEL_MODE_CHOICES, default="driving")
    time_type = models.CharField(max_length=20, choices=TIME_TYPE_CHOICES, default="departure")
    day_of_week = models.IntegerField(
        choices=DAY_OF_WEEK_CHOICES, default=5, help_text="Day of week (0=Monday, 6=Sunday)"
    )
    time_of_day = models.TimeField(default="12:00", help_text="Time of day for arrival/departure")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["label"]

    def __str__(self):
        return f"{self.label} ({self.user.username})"

    @property
    def is_geocoded(self):
        """Check if this place has valid coordinates"""
        return self.latitude is not None and self.longitude is not None

    def get_next_datetime(self):
        """Calculate the next occurrence of the selected day/time"""
        from datetime import datetime, timedelta

        now = timezone.now()
        current_weekday = now.weekday()

        # Calculate days until target weekday
        days_ahead = self.day_of_week - current_weekday
        if days_ahead <= 0:  # Target day already happened this week or is today
            days_ahead += 7

        next_date = now.date() + timedelta(days=days_ahead)
        next_datetime = timezone.make_aware(
            datetime.combine(next_date, self.time_of_day), timezone=timezone.get_current_timezone()
        )

        return next_datetime


class ApartmentDistance(models.Model):
    """Cached distance between an apartment and a favorite place"""

    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="distances")
    favorite_place = models.ForeignKey(FavoritePlace, on_delete=models.CASCADE, related_name="apartment_distances")
    distance_miles = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    travel_time_minutes = models.IntegerField(null=True, blank=True)
    transit_fare = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, help_text="Transit fare in USD"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["apartment", "favorite_place"]
        ordering = ["favorite_place__label"]

    def __str__(self):
        return f"{self.apartment.name} -> {self.favorite_place.label}: {self.distance_miles} mi"


# =============================================================================
# Favorite Places Helper Functions
# =============================================================================


def get_favorite_place_limit(user, product_slug: str = "apartments") -> int:
    """Returns max favorite places allowed: 1 for free, 5 for pro"""
    if user_has_premium(user, product_slug):
        return 5
    return 1


def can_add_favorite_place(user, product_slug: str = "apartments") -> bool:
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
