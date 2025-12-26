"""
Home Scoring Service

Calculates normalized scores for homes based on user preferences.
Supports multiple metrics with customizable weights.
"""

from decimal import Decimal

from apartments.models import user_has_premium

from .models import Home, HomeDistance, HomePreferences, HomeScore


class HomeScoringService:
    """Service for calculating home scores based on user preferences"""

    # Free tier: only price + sqft (2 factors, no distance without premium)
    # Pro tier: all factors
    FREE_TIER_FACTORS = ["price", "sqft"]
    PRO_TIER_FACTORS = [
        "price",
        "sqft",
        "distance",
        "hoa_fees",
        "property_taxes",
        "lot_size",
        "year_built",
        "bedrooms",
        "bathrooms",
    ]

    def __init__(self, user, homes: list[Home], product_slug: str = "homes"):
        """
        Initialize scoring service

        Args:
            user: Django User instance
            homes: List of Home objects to score
            product_slug: Product identifier for premium checks
        """
        self.user = user
        self.homes = homes
        self.product_slug = product_slug
        self.is_premium = user_has_premium(user, product_slug) if user.is_authenticated else False
        self._distance_cache = None  # Lazy-loaded cache for average distances

        # Get user preferences
        if user.is_authenticated:
            self.preferences, _ = HomePreferences.objects.get_or_create(
                user=user,
                defaults={
                    "price_weight": 50,
                    "sqft_weight": 50,
                    "distance_weight": 50,
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
            invert: If True, invert so lower values score higher (for price, distance, fees, taxes)

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
        Calculate min/max values for each metric across all homes

        Returns:
            Dictionary mapping metric names to (min, max) tuples
        """
        if not self.homes:
            return {}

        metrics = {}

        # Price
        prices = [home.price for home in self.homes]
        metrics["price"] = (min(prices), max(prices))

        # Square footage
        sqfts = [Decimal(home.square_footage) for home in self.homes]
        metrics["sqft"] = (min(sqfts), max(sqfts))

        # Distance - get average distance to all favorite places
        distance_values = []
        for home in self.homes:
            avg_distance = self._get_average_distance(home)
            if avg_distance is not None:
                distance_values.append(avg_distance)

        if distance_values:
            metrics["distance"] = (min(distance_values), max(distance_values))
        else:
            metrics["distance"] = (Decimal("0"), Decimal("0"))

        # HOA fees
        hoa_values = [home.hoa_fees if home.hoa_fees else Decimal("0") for home in self.homes]
        metrics["hoa_fees"] = (min(hoa_values), max(hoa_values))

        # Property taxes
        tax_values = [home.property_taxes if home.property_taxes else Decimal("0") for home in self.homes]
        metrics["property_taxes"] = (min(tax_values), max(tax_values))

        # Lot size
        lot_values = [Decimal(home.lot_size_sqft) for home in self.homes if home.lot_size_sqft]
        if lot_values:
            metrics["lot_size"] = (min(lot_values), max(lot_values))
        else:
            metrics["lot_size"] = (Decimal("0"), Decimal("0"))

        # Year built (newer = better, so we'll invert in scoring)
        year_values = [Decimal(home.year_built) for home in self.homes if home.year_built]
        if year_values:
            metrics["year_built"] = (min(year_values), max(year_values))
        else:
            metrics["year_built"] = (Decimal("0"), Decimal("0"))

        # Bedrooms
        bedrooms = [home.bedrooms for home in self.homes]
        metrics["bedrooms"] = (min(bedrooms), max(bedrooms))

        # Bathrooms
        bathrooms = [home.bathrooms for home in self.homes]
        metrics["bathrooms"] = (min(bathrooms), max(bathrooms))

        return metrics

    def _load_distance_cache(self) -> None:
        """
        Batch load all home distances into cache to avoid N+1 queries.
        """
        from django.db.models import Avg

        home_ids = [home.id for home in self.homes]

        # Single query to get average distances for all homes
        avg_distances = (
            HomeDistance.objects.filter(home_id__in=home_ids, distance_miles__isnull=False)
            .values("home_id")
            .annotate(avg_distance=Avg("distance_miles"))
        )

        self._distance_cache = {row["home_id"]: row["avg_distance"] for row in avg_distances}

    def _get_average_distance(self, home: Home) -> Decimal | None:
        """
        Get average distance from home to all favorite places

        Args:
            home: Home instance

        Returns:
            Average distance in miles, or None if no distances available
        """
        # Lazy load distance cache on first access
        if self._distance_cache is None:
            self._load_distance_cache()

        return self._distance_cache.get(home.id)

    def get_active_weights(self) -> dict[str, int]:
        """
        Get active scoring weights based on user preferences and tier

        Returns:
            Dictionary mapping factor names to their weights (0-100)
        """
        if not self.preferences:
            # Default weights for anonymous users
            return {"price": 50, "sqft": 50}

        available_factors = self.get_available_factors()
        weights = {}

        # Map preference fields to factor names
        weight_mapping = {
            "price": self.preferences.price_weight,
            "sqft": self.preferences.sqft_weight,
            "distance": self.preferences.distance_weight,
            "hoa_fees": getattr(self.preferences, "hoa_fees_weight", 0),
            "property_taxes": getattr(self.preferences, "property_taxes_weight", 0),
            "lot_size": getattr(self.preferences, "lot_size_weight", 0),
            "year_built": getattr(self.preferences, "year_built_weight", 0),
            "bedrooms": getattr(self.preferences, "bedrooms_weight", 0),
            "bathrooms": getattr(self.preferences, "bathrooms_weight", 0),
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

    def calculate_score_for_home(self, home: Home) -> float | None:
        """
        Calculate final score (0-10) for a single home

        Args:
            home: Home instance to score

        Returns:
            Score from 0-10, or None if cannot be calculated
        """
        breakdown = self.calculate_score_breakdown(home)
        if breakdown is None:
            return None
        return breakdown["total_score"]

    def _get_factor_value(self, home: Home, factor: str) -> tuple[Decimal | None, bool]:
        """
        Get the value for a scoring factor from a home.

        Args:
            home: Home instance
            factor: Factor name

        Returns:
            Tuple of (value, invert) where value is None if factor is not applicable
        """
        if factor == "price":
            return (home.price, True)  # Lower price is better
        elif factor == "sqft":
            return (Decimal(home.square_footage), False)  # Larger is better
        elif factor == "bedrooms":
            return (home.bedrooms, False)  # More bedrooms is better
        elif factor == "bathrooms":
            return (home.bathrooms, False)  # More bathrooms is better
        elif factor == "distance":
            value = self._get_average_distance(home)
            if value is None:
                return (None, True)
            return (value, True)  # Shorter distance is better
        elif factor == "hoa_fees":
            return (home.hoa_fees if home.hoa_fees else Decimal("0"), True)  # Lower fees is better
        elif factor == "property_taxes":
            return (home.property_taxes if home.property_taxes else Decimal("0"), True)  # Lower taxes is better
        elif factor == "lot_size":
            if home.lot_size_sqft:
                return (Decimal(home.lot_size_sqft), False)  # Larger lot is better
            return (None, False)
        elif factor == "year_built":
            if home.year_built:
                return (Decimal(home.year_built), False)  # Newer is better (higher year = better)
            return (None, False)
        return (None, False)

    def calculate_score_breakdown(self, home: Home) -> dict | None:
        """
        Calculate score breakdown for a home showing contribution from each factor

        Args:
            home: Home instance to score

        Returns:
            Dictionary with score breakdown, or None if cannot be calculated
        """
        # Get active weights
        raw_weights = self.get_active_weights()
        if not raw_weights:
            return None

        # Get min/max values for normalization
        min_max_values = self.get_min_max_values()

        # Factor labels for display
        factor_labels = {
            "price": "Price",
            "sqft": "Square Footage",
            "bedrooms": "Bedrooms",
            "bathrooms": "Bathrooms",
            "distance": "Location",
            "hoa_fees": "HOA Fees",
            "property_taxes": "Property Taxes",
            "lot_size": "Lot Size",
            "year_built": "Year Built",
        }

        # First pass: determine which factors are applicable for this home
        applicable_weights = {}
        factor_data = {}  # Store (value, invert, min_val, max_val) for applicable factors

        for factor, weight in raw_weights.items():
            if factor not in min_max_values:
                continue

            value, invert = self._get_factor_value(home, factor)
            if value is None:
                continue  # Skip factors with no data for this home

            min_val, max_val = min_max_values[factor]
            applicable_weights[factor] = weight
            factor_data[factor] = (value, invert, min_val, max_val)

        # No applicable factors means no score
        if not applicable_weights:
            return None

        # Renormalize weights based only on applicable factors for THIS home
        normalized_weights = self.normalize_weights(applicable_weights)

        # Second pass: calculate weighted score with renormalized weights
        weighted_score = 0.0
        factors = []

        for factor, weight in normalized_weights.items():
            value, invert, min_val, max_val = factor_data[factor]

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
        Calculate score breakdowns for all homes

        Returns:
            Dictionary mapping home IDs to their score breakdowns
        """
        breakdowns = {}
        for home in self.homes:
            breakdown = self.calculate_score_breakdown(home)
            if breakdown is not None:
                breakdowns[home.id] = breakdown
        return breakdowns

    def calculate_all_scores(self) -> dict[int, float]:
        """
        Calculate scores for all homes

        Returns:
            Dictionary mapping home IDs to their scores
        """
        scores = {}
        for home in self.homes:
            score = self.calculate_score_for_home(home)
            if score is not None:
                scores[home.id] = score
        return scores

    def calculate_and_cache_scores(self) -> dict[int, float]:
        """
        Calculate scores for all homes and save them to the database

        Returns:
            Dictionary mapping home IDs to their scores
        """
        if not self.user.is_authenticated:
            return self.calculate_all_scores()

        scores = self.calculate_all_scores()

        # Bulk update/create scores
        score_objects = []
        for home_id, score_value in scores.items():
            score_objects.append(HomeScore(home_id=home_id, user=self.user, score=Decimal(str(score_value))))

        # Delete old scores and create new ones
        HomeScore.objects.filter(user=self.user, home__in=self.homes).delete()
        HomeScore.objects.bulk_create(score_objects)

        return scores

    def get_cached_scores(self) -> dict[int, float]:
        """
        Retrieve cached scores from database

        Returns:
            Dictionary mapping home IDs to their cached scores
        """
        if not self.user.is_authenticated:
            return {}

        home_ids = [home.id for home in self.homes]
        cached = HomeScore.objects.filter(user=self.user, home_id__in=home_ids)

        return {score.home_id: float(score.score) for score in cached}

    def get_or_calculate_scores(self, force_recalculate: bool = False) -> dict[int, float]:
        """
        Get cached scores or calculate if not available

        Args:
            force_recalculate: If True, always recalculate scores

        Returns:
            Dictionary mapping home IDs to their scores
        """
        if force_recalculate or not self.user.is_authenticated:
            return self.calculate_and_cache_scores()

        cached_scores = self.get_cached_scores()

        # Check if we have scores for all homes
        home_ids = {home.id for home in self.homes}
        cached_ids = set(cached_scores.keys())

        if home_ids == cached_ids:
            return cached_scores

        # Some homes don't have scores, recalculate all
        return self.calculate_and_cache_scores()


def recalculate_user_scores(user, product_slug: str = "homes"):
    """
    Recalculate scores for all user's homes

    Args:
        user: Django User instance
        product_slug: Product identifier

    Returns:
        Dictionary mapping home IDs to their scores
    """
    homes = list(Home.objects.filter(user=user))
    if not homes:
        return {}

    scoring_service = HomeScoringService(user, homes, product_slug)
    return scoring_service.calculate_and_cache_scores()
