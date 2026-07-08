"""Free address -> coordinates lookup.

Uses OpenStreetMap's Nominatim, which is free and needs no API key (subject to a
fair-use policy — one request at a time, a real User-Agent). If ``ORS_API_KEY``
is set, the OpenRouteService geocoder is used instead. Results are cached to a
small JSON file so the same address is never looked up twice.

Geocoding is always optional: the UI lets the trainer type coordinates directly,
so the app works even with no network at all.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Location

_CACHE_PATH = Path(os.environ.get("RIDECOACH_GEOCACHE", ".ridecoach_geocache.json"))


def _load_cache() -> dict:
    if _CACHE_PATH.exists():
        try:
            return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def geocode(address: str) -> Location | None:
    """Return a :class:`Location` for ``address`` or ``None`` if it can't be found."""
    address = address.strip()
    if not address:
        return None
    cache = _load_cache()
    if address in cache:
        c = cache[address]
        return Location(address, c["lat"], c["lng"])

    try:
        import requests
    except ImportError:
        return None

    try:
        api_key = os.environ.get("ORS_API_KEY")
        if api_key:
            resp = requests.get(
                "https://api.openrouteservice.org/geocode/search",
                params={"api_key": api_key, "text": address, "size": 1},
                timeout=20,
            )
            resp.raise_for_status()
            feats = resp.json().get("features", [])
            if not feats:
                return None
            lng, lat = feats[0]["geometry"]["coordinates"]
        else:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "limit": 1},
                headers={"User-Agent": "RideCoach/1.0 (single-trainer scheduler)"},
                timeout=20,
            )
            resp.raise_for_status()
            hits = resp.json()
            if not hits:
                return None
            lat, lng = float(hits[0]["lat"]), float(hits[0]["lon"])
    except Exception:
        return None

    cache[address] = {"lat": lat, "lng": lng}
    _save_cache(cache)
    return Location(address, lat, lng)
