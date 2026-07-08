"""RideCoach — automated weekly scheduling, bike-route optimisation and
personalised WhatsApp notifications for a fitness & nutrition trainer.

See ``SPEC.md`` for the full system design; this package is the MVP engine.
"""

from .models import (
    Category,
    FixedSession,
    FlexibleRequest,
    Location,
    ScheduledSession,
    TimeWindow,
    Trainee,
    Trainer,
    WeeklyPlan,
)
from .orchestrator import SendReport, plan_week, send_plan
from .scheduler import build_weekly_plan

__all__ = [
    "Category", "FixedSession", "FlexibleRequest", "Location", "ScheduledSession",
    "TimeWindow", "Trainee", "Trainer", "WeeklyPlan",
    "build_weekly_plan", "plan_week", "send_plan", "SendReport",
]
