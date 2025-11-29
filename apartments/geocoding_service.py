"""
Geocoding service for converting addresses to latitude/longitude coordinates.
Uses Nominatim (OpenStreetMap) for MVP - free and no API key required.
"""

import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)


class GeocodingResult(NamedTuple):
    """Result of a geocoding operation with detailed information"""

    latitude: float | None
    longitude: float | None
    success: bool
    matched_address: str | None = None
    error_type: str | None = None  # 'not_found', 'timeout', 'service_error'
    suggestion: str | None = None


class GeocodingService:
    """Service for geocoding addresses to coordinates"""

    def __init__(self):
        # Lazy import to avoid loading geopy if not needed
        self._geolocator = None

    @property
    def geolocator(self):
        """Lazy load the geolocator"""
        if self._geolocator is None:
            try:
                from geopy.geocoders import Nominatim

                self._geolocator = Nominatim(user_agent="comparison-tools")
            except ImportError:
                logger.error("geopy is not installed. Run: pip install geopy")
                return None
        return self._geolocator

    def geocode_address_detailed(self, address: str) -> GeocodingResult:
        """
        Convert an address string to coordinates with detailed feedback.

        Args:
            address: The full address string to geocode

        Returns:
            GeocodingResult with coordinates and diagnostic information
        """
        if not address or not address.strip():
            return GeocodingResult(
                latitude=None, longitude=None, success=False, error_type="empty", suggestion="Please enter an address."
            )

        if self.geolocator is None:
            return GeocodingResult(
                latitude=None,
                longitude=None,
                success=False,
                error_type="service_error",
                suggestion="Geocoding service is unavailable.",
            )

        try:
            from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable

            location = self.geolocator.geocode(address, timeout=10, addressdetails=True)
            if location:
                logger.info(f"Successfully geocoded: {address} -> ({location.latitude}, {location.longitude})")
                return GeocodingResult(
                    latitude=location.latitude,
                    longitude=location.longitude,
                    success=True,
                    matched_address=location.address,
                )
            else:
                logger.warning(f"No results for address: {address}")
                return GeocodingResult(
                    latitude=None,
                    longitude=None,
                    success=False,
                    error_type="not_found",
                    suggestion="Address not found. Try simplifying (remove unit/building numbers) or use a nearby landmark or intersection.",
                )

        except GeocoderTimedOut:
            logger.warning(f"Geocoding timeout for address: {address}")
            return GeocodingResult(
                latitude=None,
                longitude=None,
                success=False,
                error_type="timeout",
                suggestion="Request timed out. Please try again.",
            )
        except (GeocoderServiceError, GeocoderUnavailable) as e:
            logger.error(f"Geocoding service error for address {address}: {e}")
            return GeocodingResult(
                latitude=None,
                longitude=None,
                success=False,
                error_type="service_error",
                suggestion="Geocoding service is temporarily unavailable. Please try again later.",
            )
        except Exception as e:
            logger.error(f"Unexpected geocoding error for address {address}: {e}")
            return GeocodingResult(
                latitude=None,
                longitude=None,
                success=False,
                error_type="unknown",
                suggestion="An error occurred. Please try again.",
            )

    def geocode_address(self, address: str) -> tuple[float | None, float | None]:
        """
        Convert an address string to latitude/longitude coordinates.
        Simple interface that returns just coordinates.

        Args:
            address: The full address string to geocode

        Returns:
            Tuple of (latitude, longitude) or (None, None) if geocoding failed
        """
        result = self.geocode_address_detailed(address)
        return (result.latitude, result.longitude)


# Singleton instance for easy access
_geocoding_service = None


def get_geocoding_service() -> GeocodingService:
    """Get the singleton geocoding service instance"""
    global _geocoding_service
    if _geocoding_service is None:
        _geocoding_service = GeocodingService()
    return _geocoding_service


def geocode_address(address: str) -> tuple[float | None, float | None]:
    """
    Convenience function to geocode an address.

    Args:
        address: The full address string to geocode

    Returns:
        Tuple of (latitude, longitude) or (None, None) if geocoding failed
    """
    service = get_geocoding_service()
    return service.geocode_address(address)
