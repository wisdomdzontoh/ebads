"""Live travel-time service: Google Distance Matrix with Haversine fallback (docs/01 §3.6).

Tries the Google Distance Matrix API when an API key is configured; on any failure — no key,
network error, non-OK status, or unparseable response — it falls back to the Haversine
estimate and flags the result with ``is_estimated=True``. The engine therefore never fails
on maps-API unavailability (docs/14 §1.4).
"""

from __future__ import annotations

import httpx

from app.domain.travel.base import (
    Coordinate,
    TravelTimeResult,
    TravelTimeService,
    TravelTimeUnavailableError,
)
from app.domain.travel.haversine import haversine_minutes

_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
_REQUEST_TIMEOUT_SECONDS = 5.0


class LiveTravelTimeService(TravelTimeService):
    """Road travel time from Google, degrading to Haversine on any failure (docs/09 §7)."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key

    async def travel_time(self, origin: Coordinate, destination: Coordinate) -> TravelTimeResult:
        """Return the road travel time, estimated via Haversine if the API cannot answer."""
        if self._api_key:
            try:
                minutes = await self._google_minutes(origin, destination)
                return TravelTimeResult(minutes=minutes, is_estimated=False)
            except TravelTimeUnavailableError:
                pass  # fall through to the estimated path
        return TravelTimeResult(minutes=haversine_minutes(origin, destination), is_estimated=True)

    async def _google_minutes(self, origin: Coordinate, destination: Coordinate) -> float:
        """Query the Distance Matrix API for the driving duration in minutes.

        Raises ``TravelTimeUnavailableError`` on any transport/status/parse failure so the
        caller can fall back cleanly.
        """
        params = {
            "origins": f"{origin.latitude},{origin.longitude}",
            "destinations": f"{destination.latitude},{destination.longitude}",
            "mode": "driving",
            "key": self._api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.get(_DISTANCE_MATRIX_URL, params=params)
                response.raise_for_status()
                payload = response.json()
            element = payload["rows"][0]["elements"][0]
            if element.get("status") != "OK":
                raise TravelTimeUnavailableError(f"element status {element.get('status')!r}")
            return float(element["duration"]["value"]) / 60.0
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise TravelTimeUnavailableError(str(exc)) from exc
