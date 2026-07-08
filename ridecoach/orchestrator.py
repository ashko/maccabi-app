"""The Friday ritual, wired end to end.

``plan_week`` runs steps 1-3 of the spec (collect -> matrix -> optimise) and
``send_plan`` runs step 6 (personalised WhatsApp). Steps 4-5 (review & approve)
are a human gate that lives in the UI, represented here by simply calling
``send_plan`` only after the trainer approves.
"""

from __future__ import annotations

from dataclasses import dataclass

from .messaging import SendResult, Sender, default_sender
from .models import FixedSession, FlexibleRequest, Trainer, WeeklyPlan
from .routing import MatrixProvider
from .scheduler import build_weekly_plan


def plan_week(
    trainer: Trainer,
    fixed: list[FixedSession],
    flexible: list[FlexibleRequest],
    week_start: str,
    provider: MatrixProvider | None = None,
    prefer: str = "auto",
) -> WeeklyPlan:
    """Steps 1-3: build the optimised weekly plan for review."""
    return build_weekly_plan(trainer, fixed, flexible, week_start,
                             provider=provider, prefer=prefer)


@dataclass
class SendReport:
    results: list[SendResult]

    @property
    def sent(self) -> int:
        return sum(r.status == "sent" for r in self.results)

    @property
    def skipped(self) -> int:
        return sum(r.status.startswith("skipped") for r in self.results)

    @property
    def failed(self) -> int:
        return sum(r.status == "failed" for r in self.results)


def send_plan(plan: WeeklyPlan, sender: Sender | None = None) -> SendReport:
    """Step 6: send one personalised message per scheduled session."""
    sender = sender or default_sender()
    results = [sender.send(s, plan.week_start) for s in
               sorted(plan.sessions, key=lambda x: (x.weekday, x.start))]
    return SendReport(results=results)
