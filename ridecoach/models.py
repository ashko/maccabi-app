"""Domain model for the RideCoach weekly scheduler.

Time is represented in two ways:

* ``minute-of-day`` — integer minutes from midnight (e.g. 8:30 -> 510).
* ``week-minute``    — ``weekday * 1440 + minute_of_day``. A single monotonic
  axis across the whole week, which is what the scheduler optimises on.

The Israeli work-week runs Sunday..Friday, so weekday 0 = Sunday and
weekday 5 = Friday.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

MINUTES_PER_DAY = 1440
WEEKDAYS_HE = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"]


def hm(text: str) -> int:
    """Parse ``"HH:MM"`` into minutes from midnight."""
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def fmt_hm(minute_of_day: int) -> str:
    """Format minutes-from-midnight back into ``"HH:MM"``."""
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"


def week_minute(weekday: int, minute_of_day: int) -> int:
    return weekday * MINUTES_PER_DAY + minute_of_day


def split_week_minute(value: int) -> tuple[int, int]:
    return divmod(value, MINUTES_PER_DAY)


class Category(str, Enum):
    PHYSICAL = "physical"   # אימון גופני
    NUTRITION = "nutrition"  # אימון תזונה


CATEGORY_HE = {Category.PHYSICAL: "אימון גופני", Category.NUTRITION: "אימון תזונה"}


@dataclass(frozen=True)
class Location:
    name: str
    lat: float
    lng: float


@dataclass(frozen=True)
class TimeWindow:
    """A slice of a specific weekday during which a session may be placed."""
    weekday: int
    start: int  # minute-of-day
    end: int    # minute-of-day (the session must *finish* by ``end``)

    def start_week_minute(self) -> int:
        return week_minute(self.weekday, self.start)

    def end_week_minute(self) -> int:
        return week_minute(self.weekday, self.end)


@dataclass
class Trainer:
    home: Location
    # weekday -> (work_start, work_end) in minute-of-day
    work_hours: dict[int, tuple[int, int]]
    buffer_min: int = 10          # rest/margin between consecutive sessions
    max_per_day: int = 8
    bike_speed_kmh: float = 15.0  # used only by the offline fallback matrix


@dataclass
class Trainee:
    id: str
    name: str
    phone: str                    # E.164, e.g. +972501234567
    location: Location
    consent: bool = False         # WhatsApp opt-in — no consent, no message


@dataclass
class FixedSession:
    """A recurring anchor: locked to a specific weekday and start time."""
    trainee: Trainee
    label: str
    category: Category
    duration: int                 # minutes
    weekday: int
    start: int                    # minute-of-day
    is_remote: bool = False

    @property
    def location(self) -> Location | None:
        return None if self.is_remote else self.trainee.location


@dataclass
class FlexibleRequest:
    """A session to be placed this week inside one of its availability windows."""
    trainee: Trainee
    label: str
    category: Category
    duration: int                 # minutes
    availability: list[TimeWindow]
    is_remote: bool = False

    @property
    def location(self) -> Location | None:
        return None if self.is_remote else self.trainee.location


@dataclass
class ScheduledSession:
    """The output unit: a concrete placement in the week."""
    trainee: Trainee
    label: str
    category: Category
    weekday: int
    start: int                    # minute-of-day
    end: int                      # minute-of-day
    is_remote: bool
    location: Location | None
    order_in_day: int = 0         # 1-based position along that day's route
    travel_from_prev_min: int = 0  # bike minutes ridden to reach this stop

    @property
    def start_hm(self) -> str:
        return fmt_hm(self.start)

    @property
    def end_hm(self) -> str:
        return fmt_hm(self.end)

    @property
    def weekday_he(self) -> str:
        return WEEKDAYS_HE[self.weekday]


@dataclass
class WeeklyPlan:
    week_start: str               # ISO date of the Sunday
    sessions: list[ScheduledSession] = field(default_factory=list)
    unscheduled: list[str] = field(default_factory=list)  # human-readable reasons
    total_ride_min: int = 0
    solver: str = ""

    def by_day(self) -> dict[int, list[ScheduledSession]]:
        out: dict[int, list[ScheduledSession]] = {}
        for s in sorted(self.sessions, key=lambda x: (x.weekday, x.start)):
            out.setdefault(s.weekday, []).append(s)
        return out
