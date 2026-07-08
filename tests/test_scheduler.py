"""Tests for the scheduling engine — run against both solvers."""

from __future__ import annotations

import pytest

from ridecoach.models import (
    Category,
    FixedSession,
    FlexibleRequest,
    Location,
    TimeWindow,
    Trainee,
    Trainer,
    hm,
)
from ridecoach.routing import HaversineMatrixProvider
from ridecoach.sample_data import build_fixed, build_flexible, build_trainer
from ridecoach.scheduler import build_weekly_plan

SOLVERS = ["greedy", "ortools"]
WEEK = "2026-07-12"


def _plan(prefer, fixed=None, flexible=None, trainer=None):
    trainer = trainer or build_trainer()
    fixed = build_fixed() if fixed is None else fixed
    flexible = build_flexible() if flexible is None else flexible
    return build_weekly_plan(trainer, fixed, flexible, WEEK,
                             provider=HaversineMatrixProvider(trainer.bike_speed_kmh),
                             prefer=prefer)


@pytest.mark.parametrize("solver", SOLVERS)
def test_all_sample_sessions_scheduled(solver):
    plan = _plan(solver)
    assert plan.unscheduled == []
    assert len(plan.sessions) == len(build_fixed()) + len(build_flexible())


@pytest.mark.parametrize("solver", SOLVERS)
def test_fixed_sessions_land_on_exact_slot(solver):
    plan = _plan(solver)
    fixed = {(f.trainee.id, f.label): f for f in build_fixed()}
    matched = 0
    for s in plan.sessions:
        f = fixed.get((s.trainee.id, s.label))
        if f:
            assert s.weekday == f.weekday and s.start == f.start
            matched += 1
    assert matched == len(fixed)


@pytest.mark.parametrize("solver", SOLVERS)
def test_flexible_sessions_respect_availability(solver):
    plan = _plan(solver)
    flex = {(r.trainee.id, r.label): r for r in build_flexible()}
    for s in plan.sessions:
        r = flex.get((s.trainee.id, s.label))
        if not r:
            continue
        ok = any(w.weekday == s.weekday and w.start <= s.start
                 and s.end <= w.end for w in r.availability)
        assert ok, f"{s.label} placed outside availability"


@pytest.mark.parametrize("solver", SOLVERS)
def test_no_overlap_and_buffer_within_day(solver):
    plan = _plan(solver)
    trainer = build_trainer()
    for sessions in plan.by_day().values():
        sessions.sort(key=lambda x: x.start)
        for a, b in zip(sessions, sessions[1:]):
            assert b.start >= a.end + trainer.buffer_min


@pytest.mark.parametrize("solver", SOLVERS)
def test_remote_sessions_have_no_ride(solver):
    plan = _plan(solver)
    for s in plan.sessions:
        if s.is_remote:
            assert s.travel_from_prev_min == 0


@pytest.mark.parametrize("solver", SOLVERS)
def test_conflict_is_surfaced_not_silent(solver):
    """A fixed session before working hours cannot be placed — must be reported."""
    tr = Trainee("x", "בדיקה", "+972500000099", Location("מקום", 32.07, 34.78), consent=True)
    trainer = Trainer(home=Location("בית", 32.08, 34.78),
                      work_hours={0: (hm("09:00"), hm("17:00"))})
    impossible = FixedSession(tr, "מוקדם מדי", Category.PHYSICAL, 60, 0, hm("06:00"))
    plan = _plan(solver, fixed=[impossible], flexible=[], trainer=trainer)
    assert plan.sessions == []
    assert any("בדיקה" in u for u in plan.unscheduled)


def test_ortools_is_at_least_as_good_as_greedy():
    assert _plan("ortools").total_ride_min <= _plan("greedy").total_ride_min
