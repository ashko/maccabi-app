"""Headless weekly run — for a free local cron job.

Generates next week's plan from the saved roster and prints it. With ``--send``
it also dispatches the WhatsApp messages. Intended for a trainer who prefers
automation over opening the app: add a line to their own machine's crontab, e.g.

    # every Friday at 07:00
    0 7 * * 5  cd /path/to/maccabi-app && python weekly_job.py --send >> ridecoach.log 2>&1

Without WHATSAPP_TOKEN/PHONE_ID configured, --send runs in dry-run mode.
Runs entirely on free tiers; no paid services required.
"""

from __future__ import annotations

import argparse
import datetime as dt

from ridecoach.messaging import DryRunSender, default_sender
from ridecoach.models import CATEGORY_HE, WEEKDAYS_HE
from ridecoach.orchestrator import plan_week, send_plan
from ridecoach.storage import Store


def next_sunday(today: dt.date | None = None) -> dt.date:
    today = today or dt.date.today()
    return today + dt.timedelta(days=(6 - today.weekday()) % 7 or 7)


def main() -> None:
    ap = argparse.ArgumentParser(description="RideCoach weekly plan runner")
    ap.add_argument("--send", action="store_true", help="also send WhatsApp messages")
    ap.add_argument("--real", action="store_true",
                    help="send for real (needs WhatsApp config); otherwise dry-run")
    ap.add_argument("--week", help="ISO date of the target Sunday (default: next Sunday)")
    args = ap.parse_args()

    store = Store()
    week = args.week or str(next_sunday())
    plan = plan_week(store.trainer, store.fixed, store.flexible, week)

    print(f"# לו״ז לשבוע {week}  (סולבר: {plan.solver}, רכיבה: {plan.total_ride_min} דק׳)")
    for weekday, sessions in plan.by_day().items():
        print(f"\n▸ {WEEKDAYS_HE[weekday]}")
        for s in sessions:
            where = "אונליין" if s.is_remote else (s.location.name if s.location else "-")
            print(f"  {s.start_hm}-{s.end_hm}  {s.trainee.name}  "
                  f"{CATEGORY_HE[s.category]} [{s.label}]  · {where}")
    for u in plan.unscheduled:
        print(f"  ⚠️ {u}")

    if args.send:
        sender = default_sender() if args.real else DryRunSender()
        report = send_plan(plan, sender=sender)
        mode = "אמיתי" if args.real else "DRY-RUN"
        print(f"\n[{mode}] נשלחו {report.sent} · דולגו {report.skipped} · נכשלו {report.failed}")


if __name__ == "__main__":
    main()
