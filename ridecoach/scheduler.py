"""The scheduling engine.

Primary solver models the whole week as a single Vehicle Routing Problem with
Time Windows, using the "each weekday is a separate vehicle" trick from the spec:

* Node 0 is the depot (the trainer's home); every vehicle starts and ends there.
* Each *fixed* session is one mandatory node pinned to an exact week-minute.
* Each *flexible* request becomes one node **per availability window**; all copies
  sit in a single disjunction so the solver serves exactly one of them.
* *Remote* sessions (e.g. nutrition by video) get zero travel to every node, so
  they consume calendar time without distorting the bike route.
* The objective minimises total riding time; disjunction penalties force every
  session to be served whenever a feasible placement exists.

A dependency-free greedy solver is provided as a fallback so the package still
runs (and is testable) without OR-Tools installed.
"""

from __future__ import annotations

import os

from .models import (
    Category,
    FixedSession,
    FlexibleRequest,
    Location,
    ScheduledSession,
    Trainer,
    WeeklyPlan,
    split_week_minute,
    week_minute,
)
from .routing import MatrixProvider, default_provider

FIXED_PENALTY = 100_000_000   # dropping a fixed anchor is a last resort
FLEX_PENALTY = 1_000_000      # dropping a flexible session is costly but allowed
SOLVER_SECONDS = int(os.environ.get("RIDECOACH_SOLVER_SECONDS", "3"))


# --------------------------------------------------------------------------- #
#  Shared helpers
# --------------------------------------------------------------------------- #

def _collect_locations(
    trainer: Trainer,
    fixed: list[FixedSession],
    flexible: list[FlexibleRequest],
) -> tuple[list[Location], dict[tuple, int]]:
    """Build the ordered location list for the matrix (home first) + an index map."""
    locations = [trainer.home]
    index: dict[tuple, int] = {(trainer.home.lat, trainer.home.lng): 0}
    for item in [*fixed, *flexible]:
        loc = item.location
        if loc is None:
            continue
        key = (loc.lat, loc.lng)
        if key not in index:
            index[key] = len(locations)
            locations.append(loc)
    return locations, index


def _finalise_metrics(
    trainer: Trainer,
    sessions: list[ScheduledSession],
    matrix: list[list[int]],
    loc_index: dict[tuple, int],
) -> int:
    """Set order_in_day / travel_from_prev per day and return total ride minutes."""
    total = 0
    by_day: dict[int, list[ScheduledSession]] = {}
    for s in sessions:
        by_day.setdefault(s.weekday, []).append(s)

    for day_sessions in by_day.values():
        day_sessions.sort(key=lambda x: x.start)
        prev_loc_idx = 0  # start from home
        for order, s in enumerate(day_sessions, start=1):
            s.order_in_day = order
            if s.is_remote or s.location is None:
                s.travel_from_prev_min = 0
                continue
            loc_idx = loc_index[(s.location.lat, s.location.lng)]
            leg = matrix[prev_loc_idx][loc_idx]
            s.travel_from_prev_min = leg
            total += leg
            prev_loc_idx = loc_idx
        if prev_loc_idx != 0:  # ride home at the end of the day
            total += matrix[prev_loc_idx][0]
    return total


# --------------------------------------------------------------------------- #
#  OR-Tools VRPTW solver
# --------------------------------------------------------------------------- #

def _solve_ortools(
    trainer: Trainer,
    fixed: list[FixedSession],
    flexible: list[FlexibleRequest],
    matrix: list[list[int]],
    loc_index: dict[tuple, int],
    week_start: str,
) -> WeeklyPlan:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    days = sorted(trainer.work_hours.keys())
    day_to_vehicle = {d: v for v, d in enumerate(days)}

    # ----- build nodes (node 0 = depot) -----
    node_loc: list[int] = [0]        # matrix index per node (-1 == remote/zero-travel)
    node_service: list[int] = [0]    # duration + buffer per node
    node_window: list[tuple[int, int]] = [(0, 0)]  # (lo, hi) start range in week-minutes
    node_vehicle: list[int] = [-1]   # allowed vehicle, -1 == any

    fixed_nodes: list[int] = []
    # request index -> list of its copy node ids
    flex_nodes: dict[int, list[int]] = {}

    def add_node(loc: Location | None, service: int, lo: int, hi: int, vehicle: int) -> int:
        node_loc.append(loc_index[(loc.lat, loc.lng)] if loc else -1)
        node_service.append(service)
        node_window.append((lo, hi))
        node_vehicle.append(vehicle)
        return len(node_loc) - 1

    for fs in fixed:
        if fs.weekday not in day_to_vehicle:
            continue
        t = week_minute(fs.weekday, fs.start)
        node = add_node(fs.location, fs.duration + trainer.buffer_min, t, t,
                        day_to_vehicle[fs.weekday])
        fixed_nodes.append(node)

    for ri, req in enumerate(flexible):
        copies: list[int] = []
        for tw in req.availability:
            if tw.weekday not in day_to_vehicle:
                continue
            lo = week_minute(tw.weekday, tw.start)
            hi = week_minute(tw.weekday, tw.end) - req.duration
            if hi < lo:
                continue  # window too short for this session
            node = add_node(req.location, req.duration + trainer.buffer_min, lo, hi,
                            day_to_vehicle[tw.weekday])
            copies.append(node)
        if copies:
            flex_nodes[ri] = copies

    num_nodes = len(node_loc)
    num_vehicles = len(days)
    manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def travel(from_node: int, to_node: int) -> int:
        a, b = node_loc[from_node], node_loc[to_node]
        if a < 0 or b < 0:   # a remote endpoint means no ride
            return 0
        return matrix[a][b]

    travel_cb = routing.RegisterTransitCallback(
        lambda fi, ti: travel(manager.IndexToNode(fi), manager.IndexToNode(ti))
    )
    routing.SetArcCostEvaluatorOfAllVehicles(travel_cb)  # objective = ride time only

    def time_transit(fi: int, ti: int) -> int:
        f = manager.IndexToNode(fi)
        return travel(f, manager.IndexToNode(ti)) + node_service[f]

    time_cb = routing.RegisterTransitCallback(time_transit)
    horizon = len(days) * 1440 + 1440
    routing.AddDimension(time_cb, horizon, horizon, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    # vehicle day windows
    for d in days:
        v = day_to_vehicle[d]
        ws, we = trainer.work_hours[d]
        lo, hi = week_minute(d, ws), week_minute(d, we)
        time_dim.CumulVar(routing.Start(v)).SetRange(lo, hi)
        time_dim.CumulVar(routing.End(v)).SetRange(lo, hi)

    # Node start-time windows are expressed in week-minutes, which already pins
    # each node to exactly one day: no other vehicle's [start, end] range can
    # reach those minutes, so an explicit allowed-vehicles constraint is redundant.
    for node in range(1, num_nodes):
        idx = manager.NodeToIndex(node)
        lo, hi = node_window[node]
        time_dim.CumulVar(idx).SetRange(lo, hi)

    # max sessions per day
    demand_cb = routing.RegisterUnaryTransitCallback(
        lambda i: 0 if manager.IndexToNode(i) == 0 else 1
    )
    routing.AddDimensionWithVehicleCapacity(
        demand_cb, 0, [trainer.max_per_day] * num_vehicles, True, "Count"
    )

    # disjunctions: fixed = singleton (mandatory-ish), flexible = pick exactly one copy
    for node in fixed_nodes:
        routing.AddDisjunction([manager.NodeToIndex(node)], FIXED_PENALTY)
    for copies in flex_nodes.values():
        routing.AddDisjunction([manager.NodeToIndex(n) for n in copies], FLEX_PENALTY, 1)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    params.time_limit.FromSeconds(SOLVER_SECONDS)

    solution = routing.SolveWithParameters(params)
    plan = WeeklyPlan(week_start=week_start, solver="ortools-vrptw")
    if solution is None:
        plan.unscheduled.append("הסולבר לא מצא פתרון כלל — בדוק אילוצים גלובליים (שעות עבודה).")
        return plan

    # node id -> (kind, ref)
    node_fixed = {n: fs for n, fs in zip(fixed_nodes, fixed)}
    node_flex = {n: flexible[ri] for ri, copies in flex_nodes.items() for n in copies}
    served: set[int] = set()

    for d in days:
        v = day_to_vehicle[d]
        idx = routing.Start(v)
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node != 0:
                served.add(node)
                start_wm = solution.Min(time_dim.CumulVar(idx))
                weekday, start_min = split_week_minute(start_wm)
                if node in node_fixed:
                    fs = node_fixed[node]
                    plan.sessions.append(ScheduledSession(
                        trainee=fs.trainee, label=fs.label, category=fs.category,
                        weekday=weekday, start=start_min, end=start_min + fs.duration,
                        is_remote=fs.is_remote, location=fs.location))
                else:
                    req = node_flex[node]
                    plan.sessions.append(ScheduledSession(
                        trainee=req.trainee, label=req.label, category=req.category,
                        weekday=weekday, start=start_min, end=start_min + req.duration,
                        is_remote=req.is_remote, location=req.location))
            idx = solution.Value(routing.NextVar(idx))

    for node, fs in node_fixed.items():
        if node not in served:
            plan.unscheduled.append(
                f"אימון קבוע לא שובץ (קונפליקט): {fs.trainee.name} — {fs.label}")
    for ri, copies in flex_nodes.items():
        if not any(n in served for n in copies):
            req = flexible[ri]
            plan.unscheduled.append(
                f"אימון משתנה לא שובץ (אין חלון פנוי): {req.trainee.name} — {req.label}")
    for ri, req in enumerate(flexible):
        if ri not in flex_nodes:
            plan.unscheduled.append(
                f"אימון משתנה ללא חלון זמינות תקין: {req.trainee.name} — {req.label}")

    plan.total_ride_min = _finalise_metrics(trainer, plan.sessions, matrix, loc_index)
    return plan


# --------------------------------------------------------------------------- #
#  Greedy fallback solver (no third-party dependency)
# --------------------------------------------------------------------------- #

def _solve_greedy(
    trainer: Trainer,
    fixed: list[FixedSession],
    flexible: list[FlexibleRequest],
    matrix: list[list[int]],
    loc_index: dict[tuple, int],
    week_start: str,
) -> WeeklyPlan:
    plan = WeeklyPlan(week_start=week_start, solver="greedy-nearest-neighbour")
    # per-day list of (start, end) busy blocks including buffer
    busy: dict[int, list[tuple[int, int]]] = {d: [] for d in trainer.work_hours}
    count: dict[int, int] = {d: 0 for d in trainer.work_hours}

    def reserve(day: int, start: int, dur: int) -> None:
        busy[day].append((start - trainer.buffer_min, start + dur + trainer.buffer_min))
        count[day] += 1

    def fits(day: int, start: int, dur: int) -> bool:
        if day not in trainer.work_hours:
            return False
        ws, we = trainer.work_hours[day]
        if start < ws or start + dur > we or count[day] >= trainer.max_per_day:
            return False
        s0, s1 = start, start + dur
        return all(s1 + trainer.buffer_min <= b0 or s0 - trainer.buffer_min >= b1
                   for b0, b1 in busy[day])

    for fs in fixed:
        if fits(fs.weekday, fs.start, fs.duration):
            reserve(fs.weekday, fs.start, fs.duration)
            plan.sessions.append(ScheduledSession(
                trainee=fs.trainee, label=fs.label, category=fs.category,
                weekday=fs.weekday, start=fs.start, end=fs.start + fs.duration,
                is_remote=fs.is_remote, location=fs.location))
        else:
            plan.unscheduled.append(
                f"אימון קבוע לא שובץ (קונפליקט): {fs.trainee.name} — {fs.label}")

    # tightest requests (fewest windows) first
    order = sorted(range(len(flexible)), key=lambda i: len(flexible[i].availability))
    for i in order:
        req = flexible[i]
        placed = False
        best: tuple[int, int, int] | None = None  # (cost, day, start)
        for tw in req.availability:
            for start in range(tw.start, tw.end - req.duration + 1, 5):
                if not fits(tw.weekday, start, req.duration):
                    continue
                if req.location is None:
                    cost = 0
                else:
                    li = loc_index[(req.location.lat, req.location.lng)]
                    same_day = [s for s in plan.sessions
                                if s.weekday == tw.weekday and s.location]
                    if same_day:
                        cost = min(matrix[loc_index[(s.location.lat, s.location.lng)]][li]
                                   for s in same_day)
                    else:
                        cost = matrix[0][li]
                if best is None or cost < best[0]:
                    best = (cost, tw.weekday, start)
                break  # earliest feasible start in this window is enough
        if best is not None:
            _, day, start = best
            reserve(day, start, req.duration)
            plan.sessions.append(ScheduledSession(
                trainee=req.trainee, label=req.label, category=req.category,
                weekday=day, start=start, end=start + req.duration,
                is_remote=req.is_remote, location=req.location))
            placed = True
        if not placed:
            plan.unscheduled.append(
                f"אימון משתנה לא שובץ (אין חלון פנוי): {req.trainee.name} — {req.label}")

    plan.total_ride_min = _finalise_metrics(trainer, plan.sessions, matrix, loc_index)
    return plan


# --------------------------------------------------------------------------- #
#  Public entry point
# --------------------------------------------------------------------------- #

def build_weekly_plan(
    trainer: Trainer,
    fixed: list[FixedSession],
    flexible: list[FlexibleRequest],
    week_start: str,
    provider: MatrixProvider | None = None,
    prefer: str = "auto",
) -> WeeklyPlan:
    """Produce an optimised weekly plan.

    ``prefer`` is one of ``"auto"`` (OR-Tools when importable, else greedy),
    ``"ortools"`` or ``"greedy"``.
    """
    provider = provider or default_provider(trainer.bike_speed_kmh)
    locations, loc_index = _collect_locations(trainer, fixed, flexible)
    matrix = provider.travel_minutes(locations)

    use_ortools = prefer in ("auto", "ortools")
    if use_ortools:
        try:
            import ortools  # noqa: F401
        except ImportError:
            if prefer == "ortools":
                raise
            use_ortools = False

    if use_ortools:
        return _solve_ortools(trainer, fixed, flexible, matrix, loc_index, week_start)
    return _solve_greedy(trainer, fixed, flexible, matrix, loc_index, week_start)
