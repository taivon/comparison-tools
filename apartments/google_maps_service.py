"""
Google Maps API service for Places Autocomplete and Distance Matrix.
Provides premium geocoding and real driving distance/time calculations.
"""

import logging
from typing import NamedTuple

from django.conf import settings

logger = logging.getLogger(__name__)


class AutocompleteResult(NamedTuple):
    """Result from Places Autocomplete"""

    place_id: str
    description: str  # Full address description
    main_text: str  # Primary text (e.g., street address)
    secondary_text: str  # Secondary text (e.g., city, state)


class PlaceDetails(NamedTuple):
    """Details for a place including coordinates"""

    place_id: str
    formatted_address: str
    latitude: float
    longitude: float


class DistanceResult(NamedTuple):
    """Result from Distance Matrix API"""

    origin_place_id: str
    destination_place_id: str
    distance_meters: int
    distance_miles: float
    duration_seconds: int
    duration_minutes: int
    duration_text: str  # Human readable, e.g., "15 mins"
    distance_text: str  # Human readable, e.g., "3.2 mi"
    fare: float | None = None  # Transit fare in USD (only for transit mode)


class GoogleMapsService:
    """Service for Google Maps API interactions"""

    def __init__(self):
        self._client = None
        self._api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", None)

    @property
    def client(self):
        """Lazy load the Google Maps client"""
        if self._client is None:
            if not self._api_key:
                logger.error("GOOGLE_MAPS_API_KEY not configured")
                return None
            try:
                import googlemaps

                self._client = googlemaps.Client(key=self._api_key)
            except ImportError:
                logger.error("googlemaps package not installed. Run: pip install googlemaps")
                return None
        return self._client

    @property
    def is_available(self) -> bool:
        """Check if the service is properly configured"""
        return self.client is not None

    def autocomplete(
        self, input_text: str, session_token: str | None = None, location_bias: tuple[float, float] | None = None
    ) -> list[AutocompleteResult]:
        """
        Get address autocomplete suggestions.

        Args:
            input_text: The text the user has typed
            session_token: Optional session token to reduce API costs
            location_bias: Optional (lat, lng) to bias results toward

        Returns:
            List of AutocompleteResult with suggestions
        """
        if not self.client or not input_text:
            return []

        try:
            # Build request parameters
            # Use 'geocode' type to get addresses and places (not just 'address')
            # This allows searching for businesses like "Starbucks" or landmarks
            params = {
                "input_text": input_text,
                "types": "geocode|establishment",  # Addresses AND places/businesses
                "components": {"country": "us"},  # Bias to US addresses
            }

            if session_token:
                params["session_token"] = session_token

            if location_bias:
                params["location"] = location_bias
                params["radius"] = 50000  # 50km radius bias

            results = self.client.places_autocomplete(**params)

            suggestions = []
            for result in results[:5]:  # Limit to 5 suggestions
                structured = result.get("structured_formatting", {})
                suggestions.append(
                    AutocompleteResult(
                        place_id=result["place_id"],
                        description=result["description"],
                        main_text=structured.get("main_text", result["description"]),
                        secondary_text=structured.get("secondary_text", ""),
                    )
                )

            logger.info(f"Autocomplete for '{input_text}': {len(suggestions)} results")
            return suggestions

        except Exception as e:
            logger.error(f"Autocomplete error for '{input_text}': {e}")
            return []

    def get_place_details(self, place_id: str, session_token: str | None = None) -> PlaceDetails | None:
        """
        Get details for a place including coordinates.

        Args:
            place_id: The Google place_id from autocomplete
            session_token: Same session token used in autocomplete (for billing)

        Returns:
            PlaceDetails with coordinates, or None if failed
        """
        if not self.client or not place_id:
            return None

        try:
            params = {"place_id": place_id, "fields": ["formatted_address", "geometry"]}

            if session_token:
                params["session_token"] = session_token

            result = self.client.place(place_id=place_id, fields=["formatted_address", "geometry"])

            if result and result.get("result"):
                place = result["result"]
                location = place.get("geometry", {}).get("location", {})

                return PlaceDetails(
                    place_id=place_id,
                    formatted_address=place.get("formatted_address", ""),
                    latitude=location.get("lat"),
                    longitude=location.get("lng"),
                )

            return None

        except Exception as e:
            logger.error(f"Place details error for '{place_id}': {e}")
            return None

    def get_distance_matrix(
        self, origins: list[tuple[float, float]], destinations: list[tuple[float, float]], mode: str = "driving"
    ) -> list[list[DistanceResult | None]]:
        """
        Calculate distances and travel times between origins and destinations.

        Args:
            origins: List of (lat, lng) tuples for origin points
            destinations: List of (lat, lng) tuples for destination points
            mode: Travel mode - 'driving', 'walking', 'bicycling', 'transit'

        Returns:
            2D list of DistanceResult [origin_idx][destination_idx]
        """
        if not self.client or not origins or not destinations:
            return []

        try:
            result = self.client.distance_matrix(
                origins=origins,
                destinations=destinations,
                mode=mode,
                units="imperial",  # Use miles
            )

            distance_results = []

            for i, row in enumerate(result.get("rows", [])):
                row_results = []
                for j, element in enumerate(row.get("elements", [])):
                    if element.get("status") == "OK":
                        distance = element.get("distance", {})
                        duration = element.get("duration", {})
                        fare_data = element.get("fare", {})

                        distance_meters = distance.get("value", 0)
                        duration_seconds = duration.get("value", 0)

                        # Extract fare if available (transit mode only)
                        fare = None
                        if fare_data:
                            # Fare value is already in the actual currency amount (e.g., 6 = $6.00)
                            fare_value = fare_data.get("value")
                            if fare_value is not None:
                                fare = round(fare_value, 2)

                        row_results.append(
                            DistanceResult(
                                origin_place_id=f"origin_{i}",
                                destination_place_id=f"dest_{j}",
                                distance_meters=distance_meters,
                                distance_miles=round(distance_meters / 1609.34, 2),
                                duration_seconds=duration_seconds,
                                duration_minutes=round(duration_seconds / 60),
                                duration_text=duration.get("text", ""),
                                distance_text=distance.get("text", ""),
                                fare=fare,
                            )
                        )
                    else:
                        row_results.append(None)
                distance_results.append(row_results)

            logger.info(f"Distance matrix: {len(origins)} origins x {len(destinations)} destinations")
            return distance_results

        except Exception as e:
            logger.error(f"Distance matrix error: {e}")
            return []

    def get_single_distance(
        self, origin: tuple[float, float], destination: tuple[float, float], mode: str = "driving"
    ) -> DistanceResult | None:
        """
        Calculate distance and travel time between two points.

        Args:
            origin: (lat, lng) tuple for origin
            destination: (lat, lng) tuple for destination
            mode: Travel mode - 'driving', 'walking', 'bicycling', 'transit'

        Returns:
            DistanceResult or None if failed
        """
        results = self.get_distance_matrix([origin], [destination], mode)
        if results and results[0] and results[0][0]:
            return results[0][0]
        return None


# Singleton instance
_google_maps_service = None


def get_google_maps_service() -> GoogleMapsService:
    """Get the singleton Google Maps service instance"""
    global _google_maps_service
    if _google_maps_service is None:
        _google_maps_service = GoogleMapsService()
    return _google_maps_service
