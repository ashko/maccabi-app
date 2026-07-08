"""Travel-time matrix providers.

The scheduler only needs one thing from the geo layer: a matrix of bike
travel times (in minutes) between a set of locations. Two providers implement
the same interface:

* ``HaversineMatrixProvider`` — offline, zero-dependency estimate. Straight-line
  distance divided by an average bike speed, with a small detour factor so it is
  not wildly optimistic. Lets the whole system run with no API key.
* ``OpenRouteServiceMatrixProvider`` — real cycling times from the ORS Matrix
  API (``cycling-regular`` profile), which accounts for the actual road/bike-path
  network. Used automatically when ``ORS_API_KEY`` is set.

Both cache results, because the trainee roster (and therefore the matrix) changes
slowly — recomputing every Friday would waste API calls and solver warm-up time.
"""

from __future__ import annotations

import math
import os
from typing import Protocol

from .models import Location


class MatrixProvider(Protocol):
    def travel_minutes(self, locations: list[Location]) -> list[list[int]]:
        """Return an NxN matrix of one-way bike travel times in whole minutes."""
        ...


def _haversine_km(a: Location, b: Location) -> float:
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = math.radians(b.lat - a.lat)
    dl = math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


class HaversineMatrixProvider:
    """Offline fallback: crow-flies distance -> minutes at a fixed bike speed."""

    #: real cycling routes are longer than a straight line — inflate accordingly
    DETOUR_FACTOR = 1.35

    def __init__(self, bike_speed_kmh: float = 15.0) -> None:
        self.bike_speed_kmh = bike_speed_kmh
        self._cache: dict[tuple, list[list[int]]] = {}

    def travel_minutes(self, locations: list[Location]) -> list[list[int]]:
        key = tuple((round(l.lat, 5), round(l.lng, 5)) for l in locations)
        if key in self._cache:
            return self._cache[key]
        n = len(locations)
        matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                km = _haversine_km(locations[i], locations[j]) * self.DETOUR_FACTOR
                minutes = round(km / self.bike_speed_kmh * 60)
                matrix[i][j] = max(1, minutes)
        self._cache[key] = matrix
        return matrix


class OpenRouteServiceMatrixProvider:
    """Real cycling times via the OpenRouteService Matrix API."""

    URL = "https://api.openrouteservice.org/v2/matrix/cycling-regular"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._cache: dict[tuple, list[list[int]]] = {}

    def travel_minutes(self, locations: list[Location]) -> list[list[int]]:
        key = tuple((round(l.lat, 5), round(l.lng, 5)) for l in locations)
        if key in self._cache:
            return self._cache[key]
        import requests  # imported lazily so the offline path needs no network stack

        body = {
            # ORS expects [lng, lat] pairs
            "locations": [[l.lng, l.lat] for l in locations],
            "metrics": ["duration"],
        }
        resp = requests.post(
            self.URL,
            json=body,
            headers={"Authorization": self.api_key, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        durations = resp.json()["durations"]  # seconds
        matrix = [[max(1, round(sec / 60)) if sec else 0 for sec in row] for row in durations]
        self._cache[key] = matrix
        return matrix


def default_provider(bike_speed_kmh: float = 15.0) -> MatrixProvider:
    """Pick the best available provider from the environment."""
    api_key = os.environ.get("ORS_API_KEY")
    if api_key:
        return OpenRouteServiceMatrixProvider(api_key)
    return HaversineMatrixProvider(bike_speed_kmh)
