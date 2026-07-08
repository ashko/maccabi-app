"""Zero-cost persistence: a single JSON file on disk.

For a single trainer this is all that is needed — no database server, no monthly
bill. The file lives next to the app (``ridecoach_data.json`` by default, override
with ``RIDECOACH_DATA``). Running locally, the data simply persists on the
trainer's machine. On an ephemeral host (e.g. Streamlit Community Cloud) point
``RIDECOACH_DATA`` at a mounted volume, or set ``DATABASE_URL`` and swap in a
Postgres-backed store later — the app only depends on the ``Store`` interface.

The very first run seeds the sample Tel Aviv roster so the app is never empty.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import (
    Category,
    FixedSession,
    FlexibleRequest,
    Location,
    TimeWindow,
    Trainee,
    Trainer,
)

DEFAULT_PATH = os.environ.get("RIDECOACH_DATA", "ridecoach_data.json")


# ---- (de)serialisation helpers ------------------------------------------- #

def _loc_to_d(l: Location) -> dict:
    return {"name": l.name, "lat": l.lat, "lng": l.lng}


def _loc_from_d(d: dict) -> Location:
    return Location(d["name"], float(d["lat"]), float(d["lng"]))


def _trainee_to_d(t: Trainee) -> dict:
    return {"id": t.id, "name": t.name, "phone": t.phone,
            "location": _loc_to_d(t.location), "consent": t.consent}


def _trainee_from_d(d: dict) -> Trainee:
    return Trainee(d["id"], d["name"], d["phone"],
                   _loc_from_d(d["location"]), bool(d.get("consent", False)))


def _fixed_to_d(f: FixedSession) -> dict:
    return {"trainee_id": f.trainee.id, "label": f.label, "category": f.category.value,
            "duration": f.duration, "weekday": f.weekday, "start": f.start,
            "is_remote": f.is_remote}


def _flex_to_d(r: FlexibleRequest) -> dict:
    return {"trainee_id": r.trainee.id, "label": r.label, "category": r.category.value,
            "duration": r.duration, "is_remote": r.is_remote,
            "availability": [{"weekday": w.weekday, "start": w.start, "end": w.end}
                             for w in r.availability]}


def _trainer_to_d(t: Trainer) -> dict:
    return {"home": _loc_to_d(t.home),
            "work_hours": {str(k): list(v) for k, v in t.work_hours.items()},
            "buffer_min": t.buffer_min, "max_per_day": t.max_per_day,
            "bike_speed_kmh": t.bike_speed_kmh}


def _trainer_from_d(d: dict) -> Trainer:
    return Trainer(home=_loc_from_d(d["home"]),
                   work_hours={int(k): tuple(v) for k, v in d["work_hours"].items()},
                   buffer_min=int(d.get("buffer_min", 10)),
                   max_per_day=int(d.get("max_per_day", 8)),
                   bike_speed_kmh=float(d.get("bike_speed_kmh", 15.0)))


class Store:
    """In-memory domain objects backed by a JSON file."""

    def __init__(self, path: str | os.PathLike = DEFAULT_PATH) -> None:
        self.path = Path(path)
        self.trainer: Trainer
        self.trainees: list[Trainee] = []
        self.fixed: list[FixedSession] = []
        self.flexible: list[FlexibleRequest] = []
        self.load()

    # ---- persistence ---- #
    def load(self) -> None:
        if not self.path.exists():
            self._seed_sample()
            self.save()
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.trainer = _trainer_from_d(data["trainer"])
        self.trainees = [_trainee_from_d(d) for d in data.get("trainees", [])]
        by_id = {t.id: t for t in self.trainees}
        self.fixed = [
            FixedSession(by_id[d["trainee_id"]], d["label"], Category(d["category"]),
                         int(d["duration"]), int(d["weekday"]), int(d["start"]),
                         bool(d.get("is_remote", False)))
            for d in data.get("fixed", []) if d["trainee_id"] in by_id
        ]
        self.flexible = [
            FlexibleRequest(
                by_id[d["trainee_id"]], d["label"], Category(d["category"]),
                int(d["duration"]),
                [TimeWindow(int(w["weekday"]), int(w["start"]), int(w["end"]))
                 for w in d.get("availability", [])],
                bool(d.get("is_remote", False)))
            for d in data.get("flexible", []) if d["trainee_id"] in by_id
        ]

    def save(self) -> None:
        data = {
            "trainer": _trainer_to_d(self.trainer),
            "trainees": [_trainee_to_d(t) for t in self.trainees],
            "fixed": [_fixed_to_d(f) for f in self.fixed],
            "flexible": [_flex_to_d(r) for r in self.flexible],
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    # ---- helpers ---- #
    def trainee_by_id(self, tid: str) -> Trainee | None:
        return next((t for t in self.trainees if t.id == tid), None)

    def next_trainee_id(self) -> str:
        n = 1
        existing = {t.id for t in self.trainees}
        while f"t{n}" in existing:
            n += 1
        return f"t{n}"

    def _seed_sample(self) -> None:
        from .sample_data import build_fixed, build_flexible, build_trainer, TRAINEES
        self.trainer = build_trainer()
        self.trainees = list(TRAINEES)
        self.fixed = build_fixed()
        self.flexible = build_flexible()
