from datetime import datetime, timezone

from trading.live.notifications import FakeChannel, Notifier, Severity


def test_min_severity_filters():
    ch = FakeChannel()
    n = Notifier(channels=[ch], min_severity=Severity.WARN)
    assert n.notify(Severity.INFO, "low") is False
    assert n.notify(Severity.WARN, "mid") is True
    assert len(ch.sent) == 1 and ch.sent[0].title == "mid"


def test_quiet_hours_suppress_non_critical():
    ch = FakeChannel()
    n = Notifier(channels=[ch], min_severity=Severity.INFO, quiet_hours=(0, 8))
    at_3am = datetime(2026, 6, 19, 3, tzinfo=timezone.utc)
    assert n.notify(Severity.WARN, "shh", now=at_3am) is False
    assert n.notify(Severity.CRITICAL, "wake up", now=at_3am) is True   # critical ignores quiet
    assert [m.title for m in ch.sent] == ["wake up"]


def test_quiet_hours_wraparound_midnight():
    ch = FakeChannel()
    n = Notifier(channels=[ch], min_severity=Severity.INFO, quiet_hours=(22, 6))
    assert n.notify(Severity.WARN, "x", now=datetime(2026, 6, 19, 23, tzinfo=timezone.utc)) is False
    assert n.notify(Severity.WARN, "y", now=datetime(2026, 6, 19, 12, tzinfo=timezone.utc)) is True


def test_multiple_channels_receive():
    a, b = FakeChannel(), FakeChannel()
    Notifier(channels=[a, b], min_severity=Severity.INFO).notify(Severity.CRITICAL, "boom")
    assert len(a.sent) == 1 and len(b.sent) == 1
