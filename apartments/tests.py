"""
Tests for the apartments app.

Run with: uv run python manage.py test apartments
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from .forms import ApartmentForm, CustomUserCreationForm, FavoritePlaceForm, UserPreferencesForm
from .models import (
    Apartment,
    ApartmentDistance,
    ApartmentScore,
    FavoritePlace,
    Plan,
    Product,
    Subscription,
    UserPreferences,
    UserProfile,
    can_add_favorite_place,
    get_favorite_place_count,
    get_favorite_place_limit,
    get_product_free_tier_limit,
    get_product_pro_tier_limit,
    get_user_item_limit,
    get_user_subscription,
    user_has_premium,
)
from .scoring_service import ScoringService, recalculate_user_scores

# =============================================================================
# Model Tests
# =============================================================================


class ProductModelTest(TestCase):
    def test_product_creation(self):
        product = Product.objects.create(
            slug="apartments",
            name="Apartments",
            description="Compare apartments",
            free_tier_limit=2,
            pro_tier_limit=20,
        )
        self.assertEqual(str(product), "Apartments")
        self.assertTrue(product.is_active)
        self.assertEqual(product.free_tier_limit, 2)
        self.assertEqual(product.pro_tier_limit, 20)

    def test_product_slug_unique(self):
        Product.objects.create(slug="apartments", name="Apartments")
        with self.assertRaises(IntegrityError):
            Product.objects.create(slug="apartments", name="Apartments 2")


class PlanModelTest(TestCase):
    def setUp(self):
        self.product = Product.objects.create(slug="apartments", name="Apartments")

    def test_plan_creation(self):
        plan = Plan.objects.create(
            product=self.product,
            name="Pro Monthly",
            tier="pro",
            price_amount=Decimal("9.99"),
            billing_interval="month",
        )
        self.assertEqual(str(plan), "Apartments - Pro Monthly")
        self.assertEqual(plan.tier, "pro")

    def test_plan_tier_choices(self):
        free_plan = Plan.objects.create(product=self.product, name="Free", tier="free")
        pro_plan = Plan.objects.create(product=self.product, name="Pro", tier="pro")
        self.assertEqual(free_plan.tier, "free")
        self.assertEqual(pro_plan.tier, "pro")


class SubscriptionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.product = Product.objects.create(slug="apartments", name="Apartments")
        self.free_plan = Plan.objects.create(product=self.product, name="Free", tier="free")
        self.pro_plan = Plan.objects.create(
            product=self.product,
            name="Pro Monthly",
            tier="pro",
            billing_interval="month",
        )
        self.lifetime_plan = Plan.objects.create(
            product=self.product,
            name="Pro Lifetime",
            tier="pro",
            billing_interval="lifetime",
        )

    def test_subscription_creation(self):
        subscription = Subscription.objects.create(user=self.user, plan=self.pro_plan, status="active")
        self.assertEqual(str(subscription), "testuser - Apartments - Pro Monthly")

    def test_is_premium_active_for_pro(self):
        subscription = Subscription.objects.create(user=self.user, plan=self.pro_plan, status="active")
        self.assertTrue(subscription.is_premium_active)

    def test_is_premium_active_for_free(self):
        subscription = Subscription.objects.create(user=self.user, plan=self.free_plan, status="active")
        self.assertFalse(subscription.is_premium_active)

    def test_is_premium_active_lifetime(self):
        subscription = Subscription.objects.create(user=self.user, plan=self.lifetime_plan, status="active")
        self.assertTrue(subscription.is_premium_active)

    def test_is_premium_active_canceled_with_grace_period(self):
        future_date = timezone.now() + timezone.timedelta(days=7)
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.pro_plan,
            status="canceled",
            current_period_end=future_date,
        )
        self.assertTrue(subscription.is_premium_active)

    def test_is_premium_active_canceled_expired(self):
        past_date = timezone.now() - timezone.timedelta(days=7)
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.pro_plan,
            status="canceled",
            current_period_end=past_date,
        )
        self.assertFalse(subscription.is_premium_active)


class SubscriptionHelperFunctionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.product = Product.objects.create(
            slug="apartments", name="Apartments", free_tier_limit=2, pro_tier_limit=20
        )
        self.pro_plan = Plan.objects.create(
            product=self.product,
            name="Pro Monthly",
            tier="pro",
            billing_interval="month",
        )

    def test_get_user_subscription_none(self):
        result = get_user_subscription(self.user, "apartments")
        self.assertIsNone(result)

    def test_get_user_subscription_with_subscription(self):
        subscription = Subscription.objects.create(user=self.user, plan=self.pro_plan, status="active")
        result = get_user_subscription(self.user, "apartments")
        self.assertEqual(result, subscription)

    def test_user_has_premium_false(self):
        self.assertFalse(user_has_premium(self.user, "apartments"))

    def test_user_has_premium_true(self):
        Subscription.objects.create(user=self.user, plan=self.pro_plan, status="active")
        self.assertTrue(user_has_premium(self.user, "apartments"))

    def test_user_has_premium_staff(self):
        self.user.is_staff = True
        self.user.save()
        self.assertTrue(user_has_premium(self.user, "apartments"))

    def test_get_product_free_tier_limit(self):
        self.assertEqual(get_product_free_tier_limit("apartments"), 2)

    def test_get_product_free_tier_limit_default(self):
        self.assertEqual(get_product_free_tier_limit("nonexistent"), 2)

    def test_get_product_pro_tier_limit(self):
        self.assertEqual(get_product_pro_tier_limit("apartments"), 20)

    def test_get_user_item_limit_free(self):
        self.assertEqual(get_user_item_limit(self.user, "apartments"), 2)

    def test_get_user_item_limit_premium(self):
        Subscription.objects.create(user=self.user, plan=self.pro_plan, status="active")
        self.assertEqual(get_user_item_limit(self.user, "apartments"), 20)


class UserProfileModelTest(TestCase):
    def test_user_profile_creation(self):
        user = User.objects.create_user(username="testuser", password="testpass123")
        profile = UserProfile.objects.create(user=user, stripe_customer_id="cus_test123")
        self.assertEqual(str(profile), "Profile for testuser")
        self.assertEqual(profile.stripe_customer_id, "cus_test123")


class ApartmentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        # Create preferences with default settings
        UserPreferences.objects.create(
            user=self.user,
            price_weight=50,
            sqft_weight=50,
            distance_weight=50,
            discount_calculation="weekly",
        )

    def test_apartment_creation(self):
        apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            bedrooms=Decimal("1"),
            bathrooms=Decimal("1"),
            lease_length_months=12,
            user=self.user,
        )
        self.assertEqual(str(apt), "Test Apartment")
        self.assertEqual(apt.price, Decimal("2000.00"))

    def test_apartment_unique_name_per_user(self):
        Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            user=self.user,
        )
        with self.assertRaises(IntegrityError):
            Apartment.objects.create(
                name="Test Apartment",
                price=Decimal("2500.00"),
                square_footage=900,
                lease_length_months=12,
                user=self.user,
            )

    def test_price_per_sqft(self):
        apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=1000,
            lease_length_months=12,
            user=self.user,
        )
        self.assertEqual(apt.price_per_sqft, Decimal("2.00"))

    def test_price_per_sqft_zero_sqft(self):
        apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=0,
            lease_length_months=12,
            user=self.user,
        )
        self.assertEqual(apt.price_per_sqft, Decimal("0"))

    def test_net_effective_price_no_discount(self):
        apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            user=self.user,
        )
        self.assertEqual(apt.net_effective_price, Decimal("2000.00"))

    def test_net_effective_price_with_months_free(self):
        apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            months_free=1,
            user=self.user,
        )
        # With weekly calculation: 1 month = 52/12 weeks
        # Weekly rate = 2000 * 12 / 52 = ~461.54
        # Discount = 461.54 * (52/12) = ~2000
        # Net = (24000 - 2000) / 12 = ~1833.33
        self.assertLess(apt.net_effective_price, Decimal("2000.00"))

    def test_net_effective_price_with_flat_discount(self):
        apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            flat_discount=Decimal("1200.00"),
            user=self.user,
        )
        # Net = (24000 - 1200) / 12 = 1900
        self.assertEqual(apt.net_effective_price, Decimal("1900.00"))

    def test_total_cost(self):
        apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            parking_cost=Decimal("150.00"),
            utilities=Decimal("100.00"),
            user=self.user,
        )
        # Total = 2000 + 150 + 100 = 2250
        self.assertEqual(apt.total_cost, Decimal("2250.00"))

    def test_view_quality_validators(self):
        apt = Apartment(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            view_quality=6,  # Invalid, max is 5
            user=self.user,
        )
        with self.assertRaises(ValidationError):
            apt.full_clean()


class UserPreferencesModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_preferences_creation(self):
        prefs = UserPreferences.objects.create(
            user=self.user,
            price_weight=75,
            sqft_weight=25,
            distance_weight=50,
        )
        self.assertEqual(str(prefs), "Preferences for testuser")
        self.assertEqual(prefs.price_weight, 75)

    def test_preferences_default_values(self):
        prefs = UserPreferences.objects.create(user=self.user)
        self.assertEqual(prefs.price_weight, 50)
        self.assertEqual(prefs.sqft_weight, 50)
        self.assertEqual(prefs.discount_calculation, "weekly")

    def test_preferences_weight_validators(self):
        prefs = UserPreferences(user=self.user, price_weight=150)  # Invalid, max is 100
        with self.assertRaises(ValidationError):
            prefs.full_clean()


class ApartmentScoreModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            user=self.user,
        )

    def test_score_creation(self):
        score = ApartmentScore.objects.create(apartment=self.apt, user=self.user, score=Decimal("8.5"))
        self.assertEqual(str(score), "Test Apartment - testuser: 8.5/10")

    def test_score_unique_per_user_apartment(self):
        ApartmentScore.objects.create(apartment=self.apt, user=self.user, score=Decimal("8.5"))
        with self.assertRaises(IntegrityError):
            ApartmentScore.objects.create(apartment=self.apt, user=self.user, score=Decimal("9.0"))


class FavoritePlaceModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")

    def test_favorite_place_creation(self):
        place = FavoritePlace.objects.create(
            user=self.user,
            label="Work",
            address="123 Main St, New York, NY",
            latitude=Decimal("40.712776"),
            longitude=Decimal("-74.005974"),
        )
        self.assertEqual(str(place), "Work (testuser)")
        self.assertTrue(place.is_geocoded)

    def test_favorite_place_not_geocoded(self):
        place = FavoritePlace.objects.create(
            user=self.user,
            label="Work",
            address="123 Main St",
        )
        self.assertFalse(place.is_geocoded)

    def test_favorite_place_travel_modes(self):
        driving_place = FavoritePlace.objects.create(
            user=self.user, label="Work", address="123 Main St", travel_mode="driving"
        )
        transit_place = FavoritePlace.objects.create(
            user=self.user, label="Gym", address="456 Oak Ave", travel_mode="transit"
        )
        self.assertEqual(driving_place.travel_mode, "driving")
        self.assertEqual(transit_place.travel_mode, "transit")

    def test_get_next_datetime(self):
        from datetime import time

        place = FavoritePlace.objects.create(
            user=self.user,
            label="Work",
            address="123 Main St",
            day_of_week=0,  # Monday
            time_of_day=time(9, 0),
        )
        next_dt = place.get_next_datetime()
        self.assertEqual(next_dt.weekday(), 0)  # Monday


class FavoritePlaceHelperFunctionsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.product = Product.objects.create(slug="apartments", name="Apartments")
        self.pro_plan = Plan.objects.create(
            product=self.product,
            name="Pro Monthly",
            tier="pro",
            billing_interval="month",
        )

    def test_get_favorite_place_limit_free(self):
        self.assertEqual(get_favorite_place_limit(self.user), 1)

    def test_get_favorite_place_limit_premium(self):
        Subscription.objects.create(user=self.user, plan=self.pro_plan, status="active")
        self.assertEqual(get_favorite_place_limit(self.user), 5)

    def test_can_add_favorite_place_free_user(self):
        self.assertTrue(can_add_favorite_place(self.user))
        FavoritePlace.objects.create(user=self.user, label="Work", address="123 Main St")
        self.assertFalse(can_add_favorite_place(self.user))

    def test_can_add_favorite_place_premium_user(self):
        Subscription.objects.create(user=self.user, plan=self.pro_plan, status="active")
        for i in range(4):
            FavoritePlace.objects.create(user=self.user, label=f"Place {i}", address=f"{i} Main St")
        self.assertTrue(can_add_favorite_place(self.user))
        FavoritePlace.objects.create(user=self.user, label="Place 5", address="5 Main St")
        self.assertFalse(can_add_favorite_place(self.user))

    def test_get_favorite_place_count(self):
        self.assertEqual(get_favorite_place_count(self.user), 0)
        FavoritePlace.objects.create(user=self.user, label="Work", address="123 Main St")
        self.assertEqual(get_favorite_place_count(self.user), 1)


class ApartmentDistanceModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        self.apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            user=self.user,
        )
        self.place = FavoritePlace.objects.create(user=self.user, label="Work", address="123 Main St")

    def test_distance_creation(self):
        distance = ApartmentDistance.objects.create(
            apartment=self.apt,
            favorite_place=self.place,
            distance_miles=Decimal("5.5"),
            travel_time_minutes=15,
        )
        self.assertEqual(str(distance), "Test Apartment -> Work: 5.5 mi")

    def test_distance_unique_per_apartment_place(self):
        ApartmentDistance.objects.create(
            apartment=self.apt,
            favorite_place=self.place,
            distance_miles=Decimal("5.5"),
        )
        with self.assertRaises(IntegrityError):
            ApartmentDistance.objects.create(
                apartment=self.apt,
                favorite_place=self.place,
                distance_miles=Decimal("6.0"),
            )


# =============================================================================
# Scoring Service Tests
# =============================================================================


class ScoringServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPreferences.objects.create(
            user=self.user,
            price_weight=50,
            sqft_weight=50,
            distance_weight=0,
        )
        # Create some test apartments
        self.apt1 = Apartment.objects.create(
            name="Cheap Small",
            price=Decimal("1500.00"),
            square_footage=600,
            lease_length_months=12,
            user=self.user,
        )
        self.apt2 = Apartment.objects.create(
            name="Expensive Large",
            price=Decimal("3000.00"),
            square_footage=1200,
            lease_length_months=12,
            user=self.user,
        )
        self.apt3 = Apartment.objects.create(
            name="Mid Range",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            user=self.user,
        )

    def test_scoring_service_initialization(self):
        apartments = [self.apt1, self.apt2, self.apt3]
        service = ScoringService(self.user, apartments)
        self.assertEqual(len(service.apartments), 3)
        self.assertFalse(service.is_premium)

    def test_get_available_factors_free(self):
        service = ScoringService(self.user, [])
        factors = service.get_available_factors()
        self.assertEqual(factors, ["price", "distance"])

    def test_normalize_value(self):
        service = ScoringService(self.user, [])
        # Normal case
        result = service.normalize_value(Decimal("50"), Decimal("0"), Decimal("100"))
        self.assertEqual(result, 0.5)
        # Inverted (for price)
        result = service.normalize_value(Decimal("50"), Decimal("0"), Decimal("100"), invert=True)
        self.assertEqual(result, 0.5)
        # Min equals max
        result = service.normalize_value(Decimal("50"), Decimal("50"), Decimal("50"))
        self.assertEqual(result, 0.5)

    def test_normalize_weights(self):
        service = ScoringService(self.user, [])
        weights = {"price": 60, "sqft": 40}
        normalized = service.normalize_weights(weights)
        self.assertAlmostEqual(normalized["price"], 0.6)
        self.assertAlmostEqual(normalized["sqft"], 0.4)

    def test_normalize_weights_empty(self):
        service = ScoringService(self.user, [])
        result = service.normalize_weights({})
        self.assertEqual(result, {})

    def test_get_min_max_values(self):
        apartments = [self.apt1, self.apt2, self.apt3]
        service = ScoringService(self.user, apartments)
        min_max = service.get_min_max_values()

        self.assertEqual(min_max["price"], (Decimal("1500.00"), Decimal("3000.00")))
        self.assertEqual(min_max["sqft"], (Decimal("600"), Decimal("1200")))

    def test_calculate_all_scores(self):
        apartments = [self.apt1, self.apt2, self.apt3]
        service = ScoringService(self.user, apartments)
        scores = service.calculate_all_scores()

        self.assertEqual(len(scores), 3)
        # All scores should be between 0 and 10
        for score in scores.values():
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 10)

    def test_calculate_score_breakdown(self):
        apartments = [self.apt1, self.apt2]
        service = ScoringService(self.user, apartments)
        breakdown = service.calculate_score_breakdown(self.apt1)

        self.assertIn("total_score", breakdown)
        self.assertIn("factors", breakdown)
        self.assertGreaterEqual(breakdown["total_score"], 0)
        self.assertLessEqual(breakdown["total_score"], 10)

    def test_calculate_and_cache_scores(self):
        apartments = [self.apt1, self.apt2, self.apt3]
        service = ScoringService(self.user, apartments)
        service.calculate_and_cache_scores()

        # Check scores were cached
        cached_scores = ApartmentScore.objects.filter(user=self.user)
        self.assertEqual(cached_scores.count(), 3)

    def test_get_cached_scores(self):
        apartments = [self.apt1, self.apt2]
        service = ScoringService(self.user, apartments)

        # Create cached scores
        ApartmentScore.objects.create(apartment=self.apt1, user=self.user, score=Decimal("8.0"))
        ApartmentScore.objects.create(apartment=self.apt2, user=self.user, score=Decimal("6.0"))

        cached = service.get_cached_scores()
        self.assertEqual(len(cached), 2)
        self.assertEqual(cached[self.apt1.id], 8.0)

    def test_get_or_calculate_scores_uses_cache(self):
        apartments = [self.apt1, self.apt2]
        service = ScoringService(self.user, apartments)

        # Create cached scores
        ApartmentScore.objects.create(apartment=self.apt1, user=self.user, score=Decimal("8.0"))
        ApartmentScore.objects.create(apartment=self.apt2, user=self.user, score=Decimal("6.0"))

        scores = service.get_or_calculate_scores()
        self.assertEqual(scores[self.apt1.id], 8.0)
        self.assertEqual(scores[self.apt2.id], 6.0)


class RecalculateUserScoresTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass123")
        UserPreferences.objects.create(user=self.user, price_weight=50, sqft_weight=50, distance_weight=0)
        self.apt = Apartment.objects.create(
            name="Test Apartment",
            price=Decimal("2000.00"),
            square_footage=800,
            lease_length_months=12,
            user=self.user,
        )

    def test_recalculate_user_scores(self):
        scores = recalculate_user_scores(self.user)
        self.assertIn(self.apt.id, scores)

    def test_recalculate_user_scores_no_apartments(self):
        other_user = User.objects.create_user(username="other", password="testpass123")
        scores = recalculate_user_scores(other_user)
        self.assertEqual(scores, {})


# =============================================================================
# Form Tests
# =============================================================================


class CustomUserCreationFormTest(TestCase):
    def test_valid_form(self):
        form = CustomUserCreationForm(
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        self.assertTrue(form.is_valid())

    def test_password_mismatch(self):
        form = CustomUserCreationForm(
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "SecurePass123!",
                "password2": "DifferentPass123!",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_duplicate_username(self):
        User.objects.create_user(username="existinguser", password="testpass123")
        form = CustomUserCreationForm(
            data={
                "username": "existinguser",
                "email": "new@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_duplicate_email(self):
        User.objects.create_user(username="user1", email="existing@example.com", password="testpass123")
        form = CustomUserCreationForm(
            data={
                "username": "newuser",
                "email": "existing@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_invalid_username_characters(self):
        form = CustomUserCreationForm(
            data={
                "username": "user name",  # space not allowed
                "email": "new@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_form_save(self):
        form = CustomUserCreationForm(
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "first_name": "Test",
                "last_name": "User",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            }
        )
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.username, "newuser")
        self.assertEqual(user.email, "newuser@example.com")
        self.assertEqual(user.first_name, "Test")


class ApartmentFormTest(TestCase):
    def test_valid_form(self):
        form = ApartmentForm(
            data={
                "name": "Test Apartment",
                "price": "2000.00",
                "square_footage": 800,
                "bedrooms": "1",
                "bathrooms": "1",
                "lease_length_months": 12,
                "months_free": 0,
                "weeks_free": 0,
                "flat_discount": "0.00",
                "parking_cost": "0.00",
                "utilities": "0.00",
                "view_quality": 0,
            }
        )
        self.assertTrue(form.is_valid())

    def test_negative_price(self):
        form = ApartmentForm(
            data={
                "name": "Test",
                "price": "-100",
                "square_footage": 800,
                "lease_length_months": 12,
                "months_free": 0,
                "weeks_free": 0,
                "flat_discount": "0",
                "parking_cost": "0",
                "utilities": "0",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("price", form.errors)

    def test_zero_lease_length(self):
        form = ApartmentForm(
            data={
                "name": "Test",
                "price": "2000",
                "square_footage": 800,
                "lease_length_months": 0,
                "months_free": 0,
                "weeks_free": 0,
                "flat_discount": "0",
                "parking_cost": "0",
                "utilities": "0",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("lease_length_months", form.errors)


class UserPreferencesFormTest(TestCase):
    def test_valid_form(self):
        form = UserPreferencesForm(
            data={
                "price_weight": 75,
                "sqft_weight": 25,
                "distance_weight": 50,
                "discount_calculation": "weekly",
                "price_per_sqft_basis": "net_effective",
                "pricing_sort_basis": "base",
            }
        )
        self.assertTrue(form.is_valid())

    def test_weight_out_of_range(self):
        form = UserPreferencesForm(
            data={
                "price_weight": 150,  # Invalid
                "sqft_weight": 25,
                "distance_weight": 50,
                "discount_calculation": "weekly",
                "price_per_sqft_basis": "net_effective",
                "pricing_sort_basis": "base",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("price_weight", form.errors)


class FavoritePlaceFormTest(TestCase):
    def test_valid_form(self):
        form = FavoritePlaceForm(
            data={
                "label": "Work",
                "address": "123 Main St, New York, NY",
                "travel_mode": "driving",
                "time_type": "departure",
                "day_of_week": 0,
                "time_of_day": "09:00",
            }
        )
        self.assertTrue(form.is_valid())

    def test_missing_label(self):
        form = FavoritePlaceForm(
            data={
                "address": "123 Main St",
                "travel_mode": "driving",
                "time_type": "departure",
                "day_of_week": 0,
                "time_of_day": "09:00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("label", form.errors)

    def test_invalid_travel_mode(self):
        form = FavoritePlaceForm(
            data={
                "label": "Work",
                "address": "123 Main St",
                "travel_mode": "flying",  # Invalid
                "time_type": "departure",
                "day_of_week": 0,
                "time_of_day": "09:00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("travel_mode", form.errors)
