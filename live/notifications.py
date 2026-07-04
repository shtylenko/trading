"""Notifications — push the things you can't watch the UI for (DESIGN §15).

Severity model routes events to channels, with quiet hours for the low-severity ones
(CRITICAL always goes through). Channels are pluggable: `ConsoleChannel` (default,
dev), `WebhookChannel` (Telegram/ntfy/Slack — thin), and `FakeChannel` (tests). The
engine raises events; this decides what reaches you.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum


class Severity(IntEnum):
    INFO = 10
    WARN = 20
    ACTION_REQUIRED = 30
    CRITICAL = 40


@dataclass
class Notification:
    severity: Severity
    title: str
    body: str = ""
    portfolio_id: str | None = None
    ts: str = ""


class Channel:
    def send(self, n: Notification) -> None: raise NotImplementedError


class ConsoleChannel(Channel):
    def send(self, n: Notification) -> None:
        print(f"[{n.severity.name}] {n.title}" + (f" — {n.body}" if n.body else ""))


class FakeChannel(Channel):
    """Captures notifications for tests."""
    def __init__(self) -> None:
        self.sent: list[Notification] = []

    def send(self, n: Notification) -> None:
        self.sent.append(n)


class WebhookChannel(Channel):
    """POST to a webhook (Telegram/ntfy/Slack). Best-effort; failures never block trading."""
    def __init__(self, url: str):
        self.url = url

    def send(self, n: Notification) -> None:  # pragma: no cover - network
        try:
            import json
            import urllib.request
            payload = json.dumps({"severity": n.severity.name, "title": n.title,
                                  "body": n.body, "portfolio_id": n.portfolio_id}).encode()
            req = urllib.request.Request(self.url, data=payload,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass


@dataclass
class Notifier:
    """Routes notifications to channels above a min severity, honoring quiet hours."""
    channels: list[Channel] = field(default_factory=list)
    min_severity: Severity = Severity.WARN
    quiet_hours: tuple[int, int] | None = None   # (start_hour_utc, end_hour_utc), CRITICAL ignores

    def _in_quiet_hours(self, now: datetime) -> bool:
        if not self.quiet_hours:
            return False
        s, e = self.quiet_hours
        h = now.hour
        return (s <= h < e) if s <= e else (h >= s or h < e)

    def notify(self, severity: Severity, title: str, body: str = "",
               portfolio_id: str | None = None, now: datetime | None = None) -> bool:
        """Dispatch. Returns True if it was sent (False if suppressed)."""
        now = now or datetime.now(timezone.utc)
        if severity < self.min_severity:
            return False
        if severity < Severity.CRITICAL and self._in_quiet_hours(now):
            return False
        n = Notification(severity, title, body, portfolio_id, ts=now.isoformat())
        for ch in self.channels:
            ch.send(n)
        return True


def default_notifier() -> Notifier:
    """No channels by default — wire ConsoleChannel/WebhookChannel per deployment."""
    return Notifier(channels=[])
