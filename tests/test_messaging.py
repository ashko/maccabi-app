"""Tests for the WhatsApp messaging layer."""

from __future__ import annotations

from ridecoach.messaging import DryRunSender, render_message, template_variables
from ridecoach.models import Category, Location, ScheduledSession, Trainee

WEEK = "2026-07-12"


def _session(consent=True, remote=False):
    tr = Trainee("t", "דנה", "+972500000001",
                 Location("צפון ישן", 32.09, 34.78), consent=consent)
    return ScheduledSession(
        trainee=tr, label="HIIT", category=Category.PHYSICAL,
        weekday=0, start=490, end=535, is_remote=remote,
        location=None if remote else tr.location)


def test_message_is_personalised():
    body = render_message(_session())
    assert "דנה" in body and "08:10" in body and "ראשון" in body


def test_template_has_five_variables():
    assert len(template_variables(_session())) == 5


def test_no_consent_is_skipped():
    sender = DryRunSender()
    res = sender.send(_session(consent=False), WEEK)
    assert res.status == "skipped-no-consent"


def test_send_is_idempotent():
    sender = DryRunSender()
    first = sender.send(_session(), WEEK)
    second = sender.send(_session(), WEEK)
    assert first.status == "sent"
    assert second.status == "duplicate"


def test_remote_location_reads_online():
    assert "אונליין" in render_message(_session(remote=True))
