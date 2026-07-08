"""End-to-end demo of the RideCoach MVP.

Runs the full Friday chain on the sample roster and prints:
  1. the optimised weekly schedule, grouped by day, with ride times, and
  2. the personalised WhatsApp messages that would go out.

Runs fully offline (haversine matrix + dry-run sender). To use the real
providers, set ORS_API_KEY and/or WHATSAPP_TOKEN + WHATSAPP_PHONE_ID.

    python demo.py            # OR-Tools if available, else greedy
    python demo.py greedy     # force the dependency-free solver
"""

from __future__ import annotations

import sys

from ridecoach.messaging import DryRunSender
from ridecoach.models import CATEGORY_HE, WEEKDAYS_HE, fmt_hm
from ridecoach.orchestrator import plan_week, send_plan
from ridecoach.sample_data import build_fixed, build_flexible, build_trainer

WEEK_START = "2026-07-12"  # a Sunday


def main() -> None:
    prefer = sys.argv[1] if len(sys.argv) > 1 else "auto"
    trainer = build_trainer()
    fixed = build_fixed()
    flexible = build_flexible()

    plan = plan_week(trainer, fixed, flexible, WEEK_START, prefer=prefer)

    print("=" * 64)
    print(f"  לו״ז אימונים לשבוע שמתחיל {plan.week_start}")
    print(f"  סולבר: {plan.solver}   |   סה״כ רכיבה בשבוע: {plan.total_ride_min} דק׳")
    print("=" * 64)

    for weekday, sessions in plan.by_day().items():
        print(f"\n▸ יום {WEEKDAYS_HE[weekday]}")
        print("  " + "-" * 58)
        for s in sessions:
            ride = f"🚲 {s.travel_from_prev_min:>2} דק׳" if not s.is_remote else "💻 אונליין"
            where = "אונליין" if s.is_remote else (s.location.name if s.location else "-")
            print(f"  {s.start_hm}-{s.end_hm}  {ride}  {s.trainee.name:<5} "
                  f"{CATEGORY_HE[s.category]:<10} [{s.label}]  ·  {where}")

    if plan.unscheduled:
        print("\n⚠️  לא שובצו:")
        for reason in plan.unscheduled:
            print(f"     • {reason}")

    print("\n" + "=" * 64)
    print("  הודעות וואטסאפ (DRY-RUN — לא נשלח בפועל)")
    print("=" * 64)
    sender = DryRunSender()
    report = send_plan(plan, sender=sender)
    for r in report.results:
        icon = {"sent": "✅", "skipped-no-consent": "🚫",
                "duplicate": "♻️", "failed": "❌"}.get(r.status, "•")
        print(f"\n{icon} [{r.status}] → {r.trainee} ({r.phone})")
        print(f'   "{r.body}"')
    print(f"\nסיכום שליחה: נשלחו {report.sent} · דולגו {report.skipped} · "
          f"נכשלו {report.failed}")


if __name__ == "__main__":
    main()
