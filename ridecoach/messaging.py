"""WhatsApp notification layer.

Business-initiated WhatsApp messages must use a pre-approved template. Here the
template is ``weekly_session`` with five positional variables:

    היי {{1}}, הנה האימון שלך לשבוע הבא: {{2}} ביום {{3}} בשעה {{4}} — {{5}}. נתראה! 🚴
        1=name  2=session type  3=weekday  4=time  5=location

Two senders share one interface:

* ``DryRunSender``  — renders and records messages without any network call. This
  is the default, so the whole pipeline is safe to run and demo offline.
* ``WhatsAppCloudSender`` — posts to the Meta WhatsApp Cloud API. Activated when
  ``WHATSAPP_TOKEN`` and ``WHATSAPP_PHONE_ID`` are present.

Sends are **idempotent**: an ``idempotency_key`` derived from (trainee, session,
week) guarantees a message is never delivered twice, even across retries.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Protocol

from .models import CATEGORY_HE, ScheduledSession

TEMPLATE_NAME = "weekly_session"


def render_message(session: ScheduledSession) -> str:
    """The human-readable body — mirrors the approved template exactly."""
    where = "אונליין 💻" if session.is_remote else (
        session.location.name if session.location else "יסוכם")
    kind = CATEGORY_HE.get(session.category, session.label)
    return (
        f"היי {session.trainee.name}, הנה האימון שלך לשבוע הבא: "
        f"{kind} ({session.label}) ביום {session.weekday_he} "
        f"בשעה {session.start_hm} — {where}. נתראה! 🚴"
    )


def template_variables(session: ScheduledSession) -> list[str]:
    where = "אונליין" if session.is_remote else (
        session.location.name if session.location else "יסוכם")
    return [
        session.trainee.name,
        f"{CATEGORY_HE.get(session.category, '')} ({session.label})".strip(),
        session.weekday_he,
        session.start_hm,
        where,
    ]


def idempotency_key(session: ScheduledSession, week_start: str) -> str:
    raw = f"{week_start}|{session.trainee.id}|{session.label}|{session.weekday}|{session.start}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class SendResult:
    trainee: str
    phone: str
    status: str          # sent | skipped-no-consent | failed | duplicate
    body: str
    key: str
    detail: str = ""


class Sender(Protocol):
    def send(self, session: ScheduledSession, week_start: str) -> SendResult: ...


@dataclass
class DryRunSender:
    """Renders messages and records them; performs no network I/O."""
    sent_keys: set[str] = field(default_factory=set)
    outbox: list[SendResult] = field(default_factory=list)

    def send(self, session: ScheduledSession, week_start: str) -> SendResult:
        key = idempotency_key(session, week_start)
        body = render_message(session)
        if not session.trainee.consent:
            res = SendResult(session.trainee.name, session.trainee.phone,
                             "skipped-no-consent", body, key,
                             "אין הסכמת Opt-in — לא נשלח")
        elif key in self.sent_keys:
            res = SendResult(session.trainee.name, session.trainee.phone,
                             "duplicate", body, key, "כבר נשלח — דילוג אידמפוטנטי")
        else:
            self.sent_keys.add(key)
            res = SendResult(session.trainee.name, session.trainee.phone,
                             "sent", body, key, "DRY-RUN")
        self.outbox.append(res)
        return res


@dataclass
class WhatsAppCloudSender:
    """Posts template messages to the Meta WhatsApp Cloud API."""
    token: str
    phone_id: str
    lang: str = "he"
    sent_keys: set[str] = field(default_factory=set)

    def send(self, session: ScheduledSession, week_start: str) -> SendResult:
        key = idempotency_key(session, week_start)
        body = render_message(session)
        if not session.trainee.consent:
            return SendResult(session.trainee.name, session.trainee.phone,
                              "skipped-no-consent", body, key, "אין הסכמת Opt-in")
        if key in self.sent_keys:
            return SendResult(session.trainee.name, session.trainee.phone,
                              "duplicate", body, key, "כבר נשלח")
        import requests

        payload = {
            "messaging_product": "whatsapp",
            "to": session.trainee.phone,
            "type": "template",
            "template": {
                "name": TEMPLATE_NAME,
                "language": {"code": self.lang},
                "components": [{
                    "type": "body",
                    "parameters": [{"type": "text", "text": v}
                                   for v in template_variables(session)],
                }],
            },
        }
        try:
            resp = requests.post(
                f"https://graph.facebook.com/v20.0/{self.phone_id}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=30,
            )
            resp.raise_for_status()
        except Exception as exc:  # network / API failure -> caller can retry
            return SendResult(session.trainee.name, session.trainee.phone,
                              "failed", body, key, str(exc))
        self.sent_keys.add(key)
        msg_id = resp.json().get("messages", [{}])[0].get("id", "")
        return SendResult(session.trainee.name, session.trainee.phone,
                          "sent", body, key, msg_id)


def default_sender() -> Sender:
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")
    if token and phone_id:
        return WhatsAppCloudSender(token=token, phone_id=phone_id)
    return DryRunSender()
