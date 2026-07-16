"""Haversine great-circle fallback (docs/09 §7, thesis §3.5.7).

When the maps API is unavailable, travel time is estimated from the great-circle distance at
a fixed urban speed (``HAVERSINE_SPEED_KMH`` = 30 km/h). Pure and deterministic, so it is
unit-testable and reproducible.
"""

from __future__ import annotations

import math

from app.domain.travel.base import Coordinate
from app.parameters import HAVERSINE_SPEED_KMH

# Mean Earth radius in kilometres.
_EARTH_RADIUS_KM = 6371.0088


def haversine_km(origin: Coordinate, destination: Coordinate) -> float:
    """Great-circle distance between two points in kilometres."""
    lat1, lon1 = math.radians(origin.latitude), math.radians(origin.longitude)
    lat2, lon2 = math.radians(destination.latitude), math.radians(destination.longitude)
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return _EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def haversine_minutes(
    origin: Coordinate, destination: Coordinate, speed_kmh: float = HAVERSINE_SPEED_KMH
) -> float:
    """Estimated travel time in minutes: great-circle distance / speed, converted to minutes."""
    return haversine_km(origin, destination) / speed_kmh * 60.0
