"""
Apartment Scoring Service

Calculates normalized scores for apartments based on user preferences.
Supports multiple metrics with customizable weights.
"""

from decimal import Decimal

from .models import Apartment, ApartmentDistance, ApartmentScore, UserPreferences, user_has_premium


class ScoringService:
    """Service for calculating apartment scores based on user preferences"""

    # Free tier: only price + distance (2 factors)
    # Pro tier: all factors
    FREE_TIER_FACTORS = ["price", "distance"]
    PRO_TIER_FACTORS = [
        "price",
        "net_effective_rent",
        "total_cost",
        "sqft",
        "distance",
        "bedrooms",
        "bathrooms",
        "discount",
        "parking",
        "utilities",
        "view",
        "balcony",
    ]

    def __init__(self, user, apartments: list[Apartment], product_slug: str = "apartments"):
        """
        Initialize scoring service

        Args:
            user: Django User instance
            apartments: List of Apartment objects to score
            product_slug: Product identifier for premium checks
        """
        self.user = user
        self.apartments = apartments
        self.product_slug = product_slug
        self.is_premium = user_has_premium(user, product_slug) if user.is_authenticated else False

        # Get user preferences
        if user.is_authenticated:
            self.preferences, _ = UserPreferences.objects.get_or_create(
                user=user,
                defaults={
                    "price_weight": 50,
                    "sqft_weight": 50,
                    "distance_weight": 50,
                    "discount_calculation": "weekly",
                },
            )
        else:
            self.preferences = None

    def get_available_factors(self) -> list[str]:
        """Get list of scoring factors available to user based on tier"""
        if self.is_premium:
            return self.PRO_TIER_FACTORS
        return self.FREE_TIER_FACTORS

    def normalize_value(self, value: Decimal, min_val: Decimal, max_val: Decimal, invert: bool = False) -> float:
        """
        Normalize a value to 0-1 range using min-max normalization

        Args:
            value: The value to normalize
            min_val: Minimum value in the dataset
            max_val: Maximum value in the dataset
            invert: If True, invert so lower values score higher (for price, distance)

        Returns:
            Normalized value between 0 and 1
        """
        if max_val == min_val:
            return 0.5  # All values are the same

        normalized = float((value - min_val) / (max_val - min_val))

        if invert:
            normalized = 1 - normalized

        return max(0.0, min(1.0, normalized))  # Clamp to 0-1

    def get_min_max_values(self) -> dict[str, tuple[Decimal, Decimal]]:
        """
        Calculate min/max values for each metric across all apartments

        Returns:
            Dictionary mapping metric names to (min, max) tuples
        """
        if not self.apartments:
            return {}

        metrics = {}

        # Check if any apartments have discounts (net effective is different from base price)
        has_discounts = any(apt.net_effective_price != apt.price for apt in self.apartments)

        # Price - use net effective rent if any apartments have discounts
        if has_discounts:
            prices = [apt.net_effective_price for apt in self.apartments]
        else:
            prices = [apt.price for apt in self.apartments]
        metrics["price"] = (min(prices), max(prices))

        # Net effective rent (for Pro tier as separate factor)
        net_prices = [apt.net_effective_price for apt in self.apartments]
        metrics["net_effective_rent"] = (min(net_prices), max(net_prices))

        # Total cost (net effective rent + parking + utilities)
        total_costs = [apt.total_cost for apt in self.apartments]
        metrics["total_cost"] = (min(total_costs), max(total_costs))

        # Square footage
        sqfts = [Decimal(apt.square_footage) for apt in self.apartments]
        metrics["sqft"] = (min(sqfts), max(sqfts))

        # Bedrooms
        bedrooms = [apt.bedrooms for apt in self.apartments]
        metrics["bedrooms"] = (min(bedrooms), max(bedrooms))

        # Bathrooms
        bathrooms = [apt.bathrooms for apt in self.apartments]
        metrics["bathrooms"] = (min(bathrooms), max(bathrooms))

        # Distance - get average distance to all favorite places
        distance_values = []
        for apt in self.apartments:
            avg_distance = self._get_average_distance(apt)
            if avg_distance is not None:
                distance_values.append(avg_distance)

        if distance_values:
            metrics["distance"] = (min(distance_values), max(distance_values))
        else:
            metrics["distance"] = (Decimal("0"), Decimal("0"))

        # Discount amount (total savings over lease)
        discount_values = [self._get_discount_amount(apt) for apt in self.apartments]
        metrics["discount"] = (min(discount_values), max(discount_values))

        # Parking cost
        parking_values = [apt.parking_cost if apt.parking_cost else Decimal("0") for apt in self.apartments]
        metrics["parking"] = (min(parking_values), max(parking_values))

        # Utilities
        utilities_values = [apt.utilities if apt.utilities else Decimal("0") for apt in self.apartments]
        metrics["utilities"] = (min(utilities_values), max(utilities_values))

        # View quality (only count rated apartments, 0 = not rated)
        view_values = [Decimal(apt.view_quality) for apt in self.apartments if apt.view_quality > 0]
        if view_values:
            metrics["view"] = (min(view_values), max(view_values))
        else:
            metrics["view"] = (Decimal("0"), Decimal("0"))

        # Has balcony (binary: 0 or 1)
        balcony_values = [Decimal("1") if apt.has_balcony else Decimal("0") for apt in self.apartments]
        metrics["balcony"] = (min(balcony_values), max(balcony_values))

        return metrics

    def _get_average_distance(self, apartment: Apartment) -> Decimal | None:
        """
        Get average distance from apartment to all favorite places

        Args:
            apartment: Apartment instance

        Returns:
            Average distance in miles, or None if no distances available
        """
        distances = ApartmentDistance.objects.filter(apartment=apartment, distance_miles__isnull=False).values_list(
            "distance_miles", flat=True
        )

        if not distances:
            return None

        return sum(distances) / len(distances)

    def _get_discount_amount(self, apartment: Apartment) -> Decimal:
        """
        Calculate total discount amount (savings) for an apartment

        Args:
            apartment: Apartment instance

        Returns:
            Total discount amount in dollars
        """
        total_discount = Decimal("0")
        discount_calc = self.preferences.discount_calculation if self.preferences else "weekly"

        if discount_calc == "daily":
            daily_rate = apartment.price * Decimal("12") / Decimal("365")
            if apartment.months_free > 0:
                days_free = Decimal(str(apartment.months_free)) * Decimal("365") / Decimal("12")
                total_discount += daily_rate * days_free
            if apartment.weeks_free > 0:
                total_discount += daily_rate * Decimal("7") * Decimal(str(apartment.weeks_free))
        elif discount_calc == "weekly":
            weekly_rate = apartment.price * Decimal("12") / Decimal("52")
            if apartment.months_free > 0:
                weeks_free = Decimal(str(apartment.months_free)) * Decimal("52") / Decimal("12")
                total_discount += weekly_rate * weeks_free
            if apartment.weeks_free > 0:
                total_discount += weekly_rate * Decimal(str(apartment.weeks_free))
        else:  # monthly
            if apartment.months_free > 0:
                total_discount += apartment.price * Decimal(str(apartment.months_free))
            if apartment.weeks_free > 0:
                total_discount += apartment.price * Decimal(str(apartment.weeks_free)) / Decimal("4")

        total_discount += apartment.flat_discount
        return total_discount

    def get_active_weights(self) -> dict[str, int]:
        """
        Get active scoring weights based on user preferences and tier

        Returns:
            Dictionary mapping factor names to their weights (0-100)
        """
        if not self.preferences:
            # Default weights for anonymous users
            return {"price": 50, "distance": 50}

        available_factors = self.get_available_factors()
        weights = {}

        # Map preference fields to factor names
        weight_mapping = {
            "price": self.preferences.price_weight,
            "net_effective_rent": getattr(self.preferences, "net_rent_weight", 0),
            "total_cost": getattr(self.preferences, "total_cost_weight", 0),
            "sqft": self.preferences.sqft_weight,
            "distance": self.preferences.distance_weight,
            "bedrooms": getattr(self.preferences, "bedrooms_weight", 0),
            "bathrooms": getattr(self.preferences, "bathrooms_weight", 0),
            "discount": getattr(self.preferences, "discount_weight", 0),
            "parking": getattr(self.preferences, "parking_weight", 0),
            "utilities": getattr(self.preferences, "utilities_weight", 0),
            "view": getattr(self.preferences, "view_weight", 0),
            "balcony": getattr(self.preferences, "balcony_weight", 0),
        }

        for factor in available_factors:
            if factor in weight_mapping:
                weight = weight_mapping[factor]
                if weight > 0:  # Only include non-zero weights
                    weights[factor] = weight

        return weights

    def normalize_weights(self, weights: dict[str, int]) -> dict[str, float]:
        """
        Normalize weights to sum to 1.0

        Args:
            weights: Dictionary of factor names to raw weights

        Returns:
            Dictionary of factor names to normalized weights (0-1)
        """
        total = sum(weights.values())
        if total == 0:
            return {}

        return {factor: weight / total for factor, weight in weights.items()}

    def calculate_score_for_apartment(self, apartment: Apartment) -> float | None:
        """
        Calculate final score (0-10) for a single apartment

        Args:
            apartment: Apartment instance to score

        Returns:
            Score from 0-10, or None if cannot be calculated
        """
        breakdown = self.calculate_score_breakdown(apartment)
        if breakdown is None:
            return None
        return breakdown["total_score"]

    def calculate_score_breakdown(self, apartment: Apartment) -> dict | None:
        """
        Calculate score breakdown for an apartment showing contribution from each factor

        Args:
            apartment: Apartment instance to score

        Returns:
            Dictionary with score breakdown, or None if cannot be calculated
        """
        # Get active weights and normalize
        raw_weights = self.get_active_weights()
        if not raw_weights:
            return None

        normalized_weights = self.normalize_weights(raw_weights)

        # Get min/max values for normalization
        min_max_values = self.get_min_max_values()

        # Check if any apartments have discounts
        has_discounts = any(apt.net_effective_price != apt.price for apt in self.apartments)

        # Factor labels for display
        factor_labels = {
            "price": "Rent",
            "net_effective_rent": "Net Effective Rent",
            "total_cost": "Total Cost",
            "sqft": "Square Footage",
            "bedrooms": "Bedrooms",
            "bathrooms": "Bathrooms",
            "distance": "Location",
            "discount": "Discount",
            "parking": "Parking Cost",
            "utilities": "Utilities",
            "view": "View Quality",
            "balcony": "Balcony",
        }

        # Calculate weighted score with breakdown
        weighted_score = 0.0
        factors = []

        for factor, weight in normalized_weights.items():
            if factor not in min_max_values:
                continue

            min_val, max_val = min_max_values[factor]

            # Get the value for this apartment
            if factor == "price":
                value = apartment.net_effective_price if has_discounts else apartment.price
                invert = True
            elif factor == "net_effective_rent":
                value = apartment.net_effective_price
                invert = True
            elif factor == "total_cost":
                value = apartment.total_cost
                invert = True  # Lower total cost is better
            elif factor == "sqft":
                value = Decimal(apartment.square_footage)
                invert = False
            elif factor == "bedrooms":
                value = apartment.bedrooms
                invert = False
            elif factor == "bathrooms":
                value = apartment.bathrooms
                invert = False
            elif factor == "distance":
                value = self._get_average_distance(apartment)
                if value is None:
                    continue
                invert = True
            elif factor == "discount":
                value = self._get_discount_amount(apartment)
                invert = False  # Higher discount is better
            elif factor == "parking":
                value = apartment.parking_cost if apartment.parking_cost else Decimal("0")
                invert = True  # Lower parking cost is better
            elif factor == "utilities":
                value = apartment.utilities if apartment.utilities else Decimal("0")
                invert = True  # Lower utilities is better
            elif factor == "view":
                value = Decimal(apartment.view_quality)
                if value == 0:
                    continue  # Skip unrated apartments for view scoring
                invert = False  # Higher view quality is better
            elif factor == "balcony":
                value = Decimal("1") if apartment.has_balcony else Decimal("0")
                invert = False  # Having balcony is better
            else:
                continue

            # Normalize value
            normalized = self.normalize_value(value, min_val, max_val, invert=invert)
            contribution = normalized * weight
            weighted_score += contribution

            # Store breakdown info
            factors.append(
                {
                    "name": factor_labels.get(factor, factor),
                    "weight_pct": round(weight * 100),
                    "normalized_score": round(normalized * 10, 1),
                    "contribution": round(contribution * 10, 1),
                }
            )

        # Sort by weight (highest first)
        factors.sort(key=lambda x: x["weight_pct"], reverse=True)

        final_score = round(weighted_score * 10, 1)

        return {
            "total_score": final_score,
            "factors": factors,
        }

    def get_all_score_breakdowns(self) -> dict[int, dict]:
        """
        Calculate score breakdowns for all apartments

        Returns:
            Dictionary mapping apartment IDs to their score breakdowns
        """
        breakdowns = {}
        for apartment in self.apartments:
            breakdown = self.calculate_score_breakdown(apartment)
            if breakdown is not None:
                breakdowns[apartment.id] = breakdown
        return breakdowns

    def calculate_all_scores(self) -> dict[int, float]:
        """
        Calculate scores for all apartments

        Returns:
            Dictionary mapping apartment IDs to their scores
        """
        scores = {}
        for apartment in self.apartments:
            score = self.calculate_score_for_apartment(apartment)
            if score is not None:
                scores[apartment.id] = score
        return scores

    def calculate_and_cache_scores(self) -> dict[int, float]:
        """
        Calculate scores for all apartments and save them to the database

        Returns:
            Dictionary mapping apartment IDs to their scores
        """
        if not self.user.is_authenticated:
            return self.calculate_all_scores()

        scores = self.calculate_all_scores()

        # Bulk update/create scores
        score_objects = []
        for apartment_id, score_value in scores.items():
            score_objects.append(
                ApartmentScore(apartment_id=apartment_id, user=self.user, score=Decimal(str(score_value)))
            )

        # Delete old scores and create new ones
        ApartmentScore.objects.filter(user=self.user, apartment__in=self.apartments).delete()
        ApartmentScore.objects.bulk_create(score_objects)

        return scores

    def get_cached_scores(self) -> dict[int, float]:
        """
        Retrieve cached scores from database

        Returns:
            Dictionary mapping apartment IDs to their cached scores
        """
        if not self.user.is_authenticated:
            return {}

        apartment_ids = [apt.id for apt in self.apartments]
        cached = ApartmentScore.objects.filter(user=self.user, apartment_id__in=apartment_ids)

        return {score.apartment_id: float(score.score) for score in cached}

    def get_or_calculate_scores(self, force_recalculate: bool = False) -> dict[int, float]:
        """
        Get cached scores or calculate if not available

        Args:
            force_recalculate: If True, always recalculate scores

        Returns:
            Dictionary mapping apartment IDs to their scores
        """
        if force_recalculate or not self.user.is_authenticated:
            return self.calculate_and_cache_scores()

        cached_scores = self.get_cached_scores()

        # Check if we have scores for all apartments
        apartment_ids = {apt.id for apt in self.apartments}
        cached_ids = set(cached_scores.keys())

        if apartment_ids == cached_ids:
            return cached_scores

        # Some apartments don't have scores, recalculate all
        return self.calculate_and_cache_scores()


def recalculate_user_scores(user, product_slug: str = "apartments"):
    """
    Recalculate scores for all user's apartments

    Args:
        user: Django User instance
        product_slug: Product identifier

    Returns:
        Dictionary mapping apartment IDs to their scores
    """
    apartments = list(Apartment.objects.filter(user=user))
    if not apartments:
        return {}

    scoring_service = ScoringService(user, apartments, product_slug)
    return scoring_service.calculate_and_cache_scores()
