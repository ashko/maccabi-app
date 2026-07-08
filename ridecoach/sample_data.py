"""A realistic Tel Aviv roster used by the demo and the tests.

Home base is in the centre of the city; trainees are scattered across nearby
neighbourhoods so the routing has something real to optimise. The week is a
mix of fixed anchors, in-person flexible sessions, and one remote nutrition call.
"""

from __future__ import annotations

from .models import (
    Category,
    FixedSession,
    FlexibleRequest,
    Location,
    TimeWindow,
    Trainer,
    Trainee,
    hm,
)

# weekday indices: 0=Sunday .. 4=Thursday .. 5=Friday
SUN, MON, TUE, WED, THU = 0, 1, 2, 3, 4

HOME = Location("בית המאמן — לב תל אביב", 32.0705, 34.7805)

TRAINEES = [
    Trainee("t1", "דנה", "+972500000001", Location("צפון ישן", 32.0900, 34.7810), consent=True),
    Trainee("t2", "יוסי", "+972500000002", Location("פלורנטין", 32.0560, 34.7690), consent=True),
    Trainee("t3", "רון", "+972500000003", Location("רמת אביב", 32.1130, 34.7960), consent=True),
    Trainee("t4", "מיה", "+972500000004", Location("נווה צדק", 32.0620, 34.7640), consent=True),
    Trainee("t5", "עדי", "+972500000005", Location("יד אליהו", 32.0530, 34.7960), consent=False),
    Trainee("t6", "טל", "+972500000006", Location("בבלי", 32.0980, 34.7900), consent=True),
]


def build_trainer() -> Trainer:
    work = {d: (hm("08:00"), hm("18:00")) for d in (SUN, MON, TUE, WED, THU)}
    work[WED] = (hm("07:00"), hm("18:00"))  # early start for the Wed morning run
    return Trainer(home=HOME, work_hours=work, buffer_min=15, max_per_day=6,
                   bike_speed_kmh=15.0)


def build_fixed() -> list[FixedSession]:
    t = {tr.id: tr for tr in TRAINEES}
    return [
        FixedSession(t["t3"], "כוח קבוע", Category.PHYSICAL, 60, MON, hm("09:00")),
        FixedSession(t["t1"], "ריצה קבועה", Category.PHYSICAL, 45, WED, hm("07:30")),
        FixedSession(t["t6"], "תזונה קבועה", Category.NUTRITION, 30, TUE, hm("16:00")),
    ]


def build_flexible() -> list[FlexibleRequest]:
    t = {tr.id: tr for tr in TRAINEES}
    any_morning = [TimeWindow(d, hm("08:00"), hm("13:00")) for d in (SUN, MON, TUE, WED, THU)]
    return [
        FlexibleRequest(t["t1"], "HIIT", Category.PHYSICAL, 45,
                        [TimeWindow(SUN, hm("08:00"), hm("12:00")),
                         TimeWindow(TUE, hm("09:00"), hm("13:00"))]),
        FlexibleRequest(t["t2"], "כוח", Category.PHYSICAL, 60,
                        [TimeWindow(SUN, hm("08:00"), hm("11:00")),
                         TimeWindow(THU, hm("14:00"), hm("18:00"))]),
        FlexibleRequest(t["t4"], "פונקציונלי", Category.PHYSICAL, 45, any_morning),
        FlexibleRequest(t["t5"], "ייעוץ תזונה", Category.NUTRITION, 30,
                        [TimeWindow(MON, hm("10:00"), hm("14:00"))], is_remote=True),
        FlexibleRequest(t["t2"], "תזונה", Category.NUTRITION, 30,
                        [TimeWindow(WED, hm("15:00"), hm("18:00"))], is_remote=True),
        FlexibleRequest(t["t6"], "כוח", Category.PHYSICAL, 60,
                        [TimeWindow(SUN, hm("08:00"), hm("13:00")),
                         TimeWindow(THU, hm("08:00"), hm("13:00"))]),
    ]
