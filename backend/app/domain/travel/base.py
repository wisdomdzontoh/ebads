"""Travel-time service interface (docs/01-architecture.md §3.6, docs/09 §7).

The allocation engine asks this abstraction for the road travel time between two points and
is unaware whether the answer came from the Google Distance Matrix API, the Haversine
fallback, or a precomputed simulation matrix (Phase 4). Every result carries
``is_estimated`` so a fallback is always visible to callers and persisted in the audit.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Coordinate:
    """A decimal lat/long point."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class TravelTimeResult:
    """A travel time in minutes and whether it came from the estimated (Haversine) path."""

    minutes: float
    is_estimated: bool


class TravelTimeUnavailableError(Exception):
    """Raised internally when the primary (maps API) source cannot answer; triggers fallback."""


class TravelTimeService(ABC):
    """Abstract source of road travel times (docs/01 §3.6)."""

    @abstractmethod
    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        """Return the travel time from ``origin`` to ``destination``."""
