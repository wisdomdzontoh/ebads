"""Haversine fallback + estimated-flag behaviour (docs/09 §7, docs/12 §7)."""

from __future__ import annotations

import math

import pytest

from app.domain.travel.base import Coordinate
from app.domain.travel.haversine import haversine_km, haversine_minutes
from app.domain.travel.live import LiveTravelTimeService
from app.parameters import HAVERSINE_SPEED_KMH

# 37 Military Hospital and Korle Bu Teaching Hospital (approx).
_A = Coordinate(5.5826, -0.1880)
_B = Coordinate(5.5366, -0.2261)


def test_zero_distance_is_zero() -> None:
    assert haversine_km(_A, _A) == 0.0
    assert haversine_minutes(_A, _A) == 0.0


def test_distance_matches_independent_formula() -> None:
    # Independent great-circle computation (not the module under test).
    r = 6371.0088
    lat1, lon1, lat2, lon2 = map(
        math.radians, (_A.latitude, _A.longitude, _B.latitude, _B.longitude)
    )
    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    expected_km = r * 2 * math.asin(math.sqrt(a))
    assert haversine_km(_A, _B) == pytest.approx(expected_km, rel=1e-12)


def test_minutes_use_configured_speed() -> None:
    km = haversine_km(_A, _B)
    assert haversine_minutes(_A, _B) == pytest.approx(km / HAVERSINE_SPEED_KMH * 60.0, rel=1e-12)


async def test_no_api_key_uses_estimated_path() -> None:
    """Without a Google key the service returns the Haversine estimate, flagged estimated."""
    service = LiveTravelTimeService(api_key="")
    result = await service.travel_time(_A, _B)
    assert result.is_estimated is True
    assert result.minutes == pytest.approx(haversine_minutes(_A, _B), rel=1e-12)
