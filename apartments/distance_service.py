"""
Distance calculation service for computing distances between apartments and favorite places.
Uses Google Maps Distance Matrix API for accurate driving distances when available,
falls back to Haversine formula for straight-line distance calculation.
"""

import logging
from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)

# Earth's radius in miles
EARTH_RADIUS_MILES = 3959


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth using the Haversine formula.
    This is a fallback when Google Maps API is not available.

    Args:
        lat1: Latitude of point 1 in degrees
        lon1: Longitude of point 1 in degrees
        lat2: Latitude of point 2 in degrees
        lon2: Longitude of point 2 in degrees

    Returns:
        Distance in miles between the two points
    """
    # Convert to floats if Decimal
    lat1, lon1 = float(lat1), float(lon1)
    lat2, lon2 = float(lat2), float(lon2)

    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return EARTH_RADIUS_MILES * c


def _get_google_maps_distance(
    origin: tuple[float, float], destination: tuple[float, float], mode: str = "driving"
) -> tuple[float, int, float | None] | None:
    """
    Get distance, time, and fare using Google Maps Distance Matrix API.

    Args:
        origin: (latitude, longitude) of origin
        destination: (latitude, longitude) of destination
        mode: Travel mode - 'driving', 'walking', 'bicycling', 'transit'

    Returns:
        Tuple of (distance_miles, travel_time_minutes, fare) or None if failed
        fare is only populated for transit mode
    """
    try:
        from .google_maps_service import get_google_maps_service

        google_maps = get_google_maps_service()
        if not google_maps.is_available:
            return None

        result = google_maps.get_single_distance(origin, destination, mode=mode)
        if result:
            return (result.distance_miles, result.duration_minutes, result.fare)
        return None
    except Exception as e:
        logger.error(f"Google Maps distance calculation failed: {e}")
        return None


def _calculate_distance_with_fallback(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    use_google_maps: bool = True,
    mode: str = "driving",
) -> tuple[float, int | None, float | None, bool]:
    """
    Calculate distance, trying Google Maps first then falling back to Haversine.

    Args:
        origin_lat: Origin latitude
        origin_lng: Origin longitude
        dest_lat: Destination latitude
        dest_lng: Destination longitude
        use_google_maps: Whether to attempt Google Maps API
        mode: Travel mode - 'driving', 'transit', etc.

    Returns:
        Tuple of (distance_miles, travel_time_minutes, fare, is_google_maps)
        is_google_maps is True if from Google Maps, False if Haversine fallback
        fare is only populated for transit mode
    """
    if use_google_maps:
        google_result = _get_google_maps_distance(
            (float(origin_lat), float(origin_lng)), (float(dest_lat), float(dest_lng)), mode=mode
        )
        if google_result:
            distance_miles, travel_time, fare = google_result
            return (distance_miles, travel_time, fare, True)

    # Fallback to Haversine (straight-line distance)
    distance = haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
    return (round(distance, 2), None, None, False)


def calculate_and_cache_distances(apartment, use_google_maps: bool = True) -> None:
    """
    Calculate and cache distances from an apartment to all of the user's favorite places.
    Uses Google Maps Distance Matrix API for accurate driving distances when available.

    Args:
        apartment: The Apartment instance to calculate distances for
        use_google_maps: Whether to use Google Maps API (default True)
    """
    from .models import ApartmentDistance, FavoritePlace

    if not apartment.latitude or not apartment.longitude:
        logger.info(f"Apartment {apartment.id} has no coordinates, skipping distance calculation")
        return

    # Get all favorite places for this user
    favorite_places = FavoritePlace.objects.filter(user=apartment.user)

    # Check if Google Maps is available (do this once, not per place)
    google_maps_available = use_google_maps and bool(settings.GOOGLE_MAPS_API_KEY)

    for place in favorite_places:
        if not place.latitude or not place.longitude:
            logger.info(f"Favorite place {place.id} has no coordinates, skipping")
            continue

        distance_miles, travel_time, fare, is_google = _calculate_distance_with_fallback(
            apartment.latitude,
            apartment.longitude,
            place.latitude,
            place.longitude,
            use_google_maps=google_maps_available,
            mode=place.travel_mode,
        )

        # Prepare defaults with fare if available
        defaults = {
            "distance_miles": Decimal(str(distance_miles)),
            "travel_time_minutes": travel_time,
        }
        if fare is not None:
            defaults["transit_fare"] = Decimal(str(fare))

        ApartmentDistance.objects.update_or_create(
            apartment=apartment,
            favorite_place=place,
            defaults=defaults,
        )

        distance_type = place.get_travel_mode_display() if is_google else "straight-line"
        time_str = f" ({travel_time} min)" if travel_time else ""
        fare_str = f" (${fare} fare)" if fare else ""
        logger.info(
            f"Cached {distance_type} distance: {apartment.name} -> {place.label} = {distance_miles} mi{time_str}{fare_str}"
        )


def recalculate_distances_for_favorite_place(favorite_place, use_google_maps: bool = True) -> None:
    """
    Recalculate distances when a favorite place is added or updated.
    Uses Google Maps Distance Matrix API for accurate driving distances when available.

    Args:
        favorite_place: The FavoritePlace instance that was changed
        use_google_maps: Whether to use Google Maps API (default True)
    """
    from .models import Apartment, ApartmentDistance

    if not favorite_place.latitude or not favorite_place.longitude:
        logger.info(f"Favorite place {favorite_place.id} has no coordinates, skipping distance calculation")
        return

    # Get all apartments for this user
    apartments = Apartment.objects.filter(user=favorite_place.user)

    # Check if Google Maps is available
    google_maps_available = use_google_maps and bool(settings.GOOGLE_MAPS_API_KEY)

    for apartment in apartments:
        if not apartment.latitude or not apartment.longitude:
            logger.info(f"Apartment {apartment.id} has no coordinates, skipping")
            continue

        distance_miles, travel_time, fare, is_google = _calculate_distance_with_fallback(
            apartment.latitude,
            apartment.longitude,
            favorite_place.latitude,
            favorite_place.longitude,
            use_google_maps=google_maps_available,
            mode=favorite_place.travel_mode,
        )

        # Prepare defaults with fare if available
        defaults = {
            "distance_miles": Decimal(str(distance_miles)),
            "travel_time_minutes": travel_time,
        }
        if fare is not None:
            defaults["transit_fare"] = Decimal(str(fare))

        ApartmentDistance.objects.update_or_create(
            apartment=apartment,
            favorite_place=favorite_place,
            defaults=defaults,
        )

        distance_type = favorite_place.get_travel_mode_display() if is_google else "straight-line"
        time_str = f" ({travel_time} min)" if travel_time else ""
        fare_str = f" (${fare} fare)" if fare else ""
        logger.info(
            f"Cached {distance_type} distance: {apartment.name} -> {favorite_place.label} = {distance_miles} mi{time_str}{fare_str}"
        )


def recalculate_all_distances_for_user(user, use_google_maps: bool = True) -> None:
    """
    Recalculate all distances for a user's apartments and favorite places.

    Args:
        user: The User instance to recalculate distances for
        use_google_maps: Whether to use Google Maps API (default True)
    """
    from .models import Apartment

    apartments = Apartment.objects.filter(user=user)
    for apartment in apartments:
        calculate_and_cache_distances(apartment, use_google_maps=use_google_maps)


def get_apartment_distances(apartment) -> dict[str, Any]:
    """
    Get all cached distances for an apartment, including average distance.

    Args:
        apartment: The Apartment instance to get distances for

    Returns:
        Dictionary with:
            - distances: List of {label, distance, travel_time} dicts
            - average_distance: Average distance across all favorite places (or None)
            - average_travel_time: Average travel time across all favorite places (or None)
    """
    from .models import ApartmentDistance

    distances = ApartmentDistance.objects.filter(apartment=apartment).select_related("favorite_place")

    distance_list: list[dict[str, Any]] = []
    total_distance = 0.0
    total_time = 0
    count = 0
    time_count = 0

    for d in distances:
        if d.distance_miles is not None:
            dist_float = float(d.distance_miles)
            distance_list.append(
                {"label": d.favorite_place.label, "distance": dist_float, "travel_time": d.travel_time_minutes}
            )
            total_distance += dist_float
            count += 1

            if d.travel_time_minutes is not None:
                total_time += d.travel_time_minutes
                time_count += 1

    average_distance = round(total_distance / count, 2) if count > 0 else None
    average_travel_time = round(total_time / time_count) if time_count > 0 else None

    return {
        "distances": distance_list,
        "average_distance": average_distance,
        "average_travel_time": average_travel_time,
    }


def get_apartments_with_distances(apartments, favorite_places) -> list[dict[str, Any]]:
    """
    Get distance data for a list of apartments organized for template rendering.

    Args:
        apartments: QuerySet or list of Apartment instances
        favorite_places: QuerySet or list of FavoritePlace instances

    Returns:
        List of dictionaries with apartment and distance info:
            - apartment: The apartment instance
            - distances: Dict mapping place label to {distance, travel_time}
            - average_distance: Average distance (or None)
            - average_travel_time: Average travel time (or None)
    """
    from collections import defaultdict

    from .models import ApartmentDistance

    result = []
    place_labels = [p.label for p in favorite_places]

    # Batch fetch all distances for all apartments in a single query
    apartment_ids = [apt.id for apt in apartments]
    all_distances = ApartmentDistance.objects.filter(apartment_id__in=apartment_ids).select_related("favorite_place")

    # Group distances by apartment_id
    distances_by_apartment = defaultdict(list)
    for d in all_distances:
        distances_by_apartment[d.apartment_id].append(d)

    for apartment in apartments:
        # Initialize distances dict with None for all places
        distances_dict = {
            label: {"distance": None, "travel_time": None, "transit_fare": None} for label in place_labels
        }

        # Get cached distances from pre-fetched data
        cached_distances = distances_by_apartment.get(apartment.id, [])

        total_distance = 0.0
        total_time = 0
        count = 0
        time_count = 0

        for d in cached_distances:
            if d.distance_miles is not None:
                dist_float = float(d.distance_miles)
                distances_dict[d.favorite_place.label] = {
                    "distance": dist_float,
                    "travel_time": d.travel_time_minutes,
                    "transit_fare": float(d.transit_fare) if d.transit_fare else None,
                }
                total_distance += dist_float
                count += 1

                if d.travel_time_minutes is not None:
                    total_time += d.travel_time_minutes
                    time_count += 1

        average_distance = round(total_distance / count, 2) if count > 0 else None
        average_travel_time = round(total_time / time_count) if time_count > 0 else None

        result.append(
            {
                "apartment": apartment,
                "distances": distances_dict,
                "average_distance": average_distance,
                "average_travel_time": average_travel_time,
            }
        )

    return result
