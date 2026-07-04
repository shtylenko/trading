"""Unit tests for the ACD/ORB detector and idempotent store (no provider calls)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trading.day_trading_simulator.config import ScanConfig
from trading.day_trading_simulator.patterns import detect_from_frame
from trading.day_trading_simulator.screen import GapCandidate
from trading.day_trading_simulator.store import EntryStore, setup_id


def _cand(day=date(2025, 3, 10)) -> GapCandidate:
    return GapCandidate("TEST", day, open_px=5.0, prior_close=4.0, gap_pct=25.0,
                        rvol=8.0, avg_vol=1_000_000, day_volume=8_000_000)


def _frame(day, rows):
    """rows = list of (HH:MM, o,h,l,c,v) in ET."""
    idx = pd.DatetimeIndex(
        [pd.Timestamp(f"{day} {hm}", tz="America/New_York") for hm, *_ in rows],
        name="timestamp",
    )
    data = {
        "open": [r[1] for r in rows], "high": [r[2] for r in rows],
        "low": [r[3] for r in rows], "close": [r[4] for r in rows],
        "volume": [r[5] for r in rows],
    }
    return pd.DataFrame(data, index=idx)


def test_breakout_fires_on_new_high_after_consolidation():
    day = "2025-03-10"
    rows = [
        ("09:30", 5.00, 5.20, 4.95, 5.10, 200_000),   # opening range, high 5.20
        ("09:35", 5.10, 5.18, 5.05, 5.12, 120_000),   # consolidation (no new high)
        ("09:40", 5.12, 5.19, 5.08, 5.15, 110_000),   # consolidation
        ("09:45", 5.15, 5.45, 5.14, 5.42, 400_000),   # BREAKOUT: new high, green, vol up
    ]
    df = _frame(day, rows)
    e = detect_from_frame(df, _cand(date(2025, 3, 10)), ScanConfig(), 8e6)
    assert e is not None
    assert e.time_et == "09:45"
    assert e.entry_px == pytest.approx(5.20)  # cleared the prior consolidation high
    assert e.bar_vol_mult is not None and e.bar_vol_mult > 1.5
    assert "ACD/ORB breakout" in e.reason


def test_fade_day_yields_no_entry():
    """Opens at the high and fades — no 5-min new high ⇒ no ACD entry."""
    day = "2025-03-10"
    rows = [
        ("09:30", 5.30, 5.40, 5.10, 5.20, 700_000),
        ("09:35", 5.20, 5.22, 5.00, 5.05, 200_000),
        ("09:40", 5.05, 5.08, 4.90, 4.95, 150_000),
        ("09:45", 4.95, 4.98, 4.80, 4.85, 130_000),
    ]
    df = _frame(day, rows)
    assert detect_from_frame(df, _cand(date(2025, 3, 10)), ScanConfig(), None) is None


def test_breakout_below_vwap_rejected_when_required():
    day = "2025-03-10"
    # Huge early bar pins VWAP high; later "new high" bar still sits below VWAP.
    rows = [
        ("09:30", 9.00, 9.00, 6.00, 6.10, 5_000_000),  # VWAP pinned ~ high
        ("09:35", 6.10, 6.20, 6.00, 6.15, 100_000),
        ("09:40", 6.15, 6.25, 6.05, 6.20, 100_000),
        ("09:45", 6.20, 6.40, 6.18, 6.38, 300_000),    # new high but < VWAP
    ]
    df = _frame(day, rows)
    cfg = ScanConfig()
    assert cfg.require_above_vwap is True
    assert detect_from_frame(df, _cand(date(2025, 3, 10)), cfg, None) is None


def test_volume_gate_blocks_low_volume_breakout():
    day = "2025-03-10"
    rows = [
        ("09:30", 5.00, 5.20, 4.95, 5.10, 500_000),
        ("09:35", 5.10, 5.18, 5.05, 5.12, 500_000),
        ("09:40", 5.12, 5.19, 5.08, 5.15, 500_000),
        ("09:45", 5.15, 5.45, 5.14, 5.42, 50_000),     # new high but volume contracts
    ]
    df = _frame(day, rows)
    assert detect_from_frame(df, _cand(date(2025, 3, 10)), ScanConfig(), None) is None


def test_store_is_idempotent(tmp_path):
    day = "2025-03-10"
    rows = [
        ("09:30", 5.00, 5.20, 4.95, 5.10, 200_000),
        ("09:35", 5.10, 5.18, 5.05, 5.12, 120_000),
        ("09:40", 5.12, 5.19, 5.08, 5.15, 110_000),
        ("09:45", 5.15, 5.45, 5.14, 5.42, 400_000),
    ]
    e = detect_from_frame(_frame(day, rows), _cand(date(2025, 3, 10)), ScanConfig(), 8e6)
    assert e is not None

    store = EntryStore(tmp_path / "e.db")
    store.upsert(e)
    store.upsert(e)   # second write of the same setup must not duplicate
    store.upsert(e)
    assert store.count() == 1

    rows_out = store.all_rows()
    assert rows_out[0]["setup_id"] == setup_id("TEST", date(2025, 3, 10), "acd_orb")
    store.close()


# ───────────────────── Additional pattern edge cases ─────────────────────

def test_premarket_breakout_is_detected_when_in_window():
    day = "2025-03-10"
    rows = [
        ("07:05", 4.80, 5.05, 4.75, 5.00, 300_000),  # consolidation / first bar in win
        ("07:10", 5.00, 5.25, 4.95, 5.20, 600_000),  # breakout new high, green, vol expansion
    ]
    df = _frame(day, rows)
    cfg = ScanConfig(entry_window_et=("07:00", "12:00"), vol_expansion_mult=1.5)
    e = detect_from_frame(df, _cand(date(2025, 3, 10)), cfg, 5e6)
    assert e is not None
    assert e.time_et == "07:10"


def test_red_breakout_bar_rejected():
    day = "2025-03-10"
    rows = [
        ("09:30", 5.0, 5.3, 5.0, 5.2, 200_000),
        ("09:35", 5.2, 5.25, 5.1, 5.15, 100_000),
        ("09:40", 5.15, 5.4, 5.1, 5.25, 80_000),
        ("09:45", 5.25, 5.5, 5.0, 5.1, 400_000),  # new high but red close
    ]
    df = _frame(day, rows)
    assert detect_from_frame(df, _cand(), ScanConfig(), None) is None


def test_thin_premarket_no_baseline_is_allowed():
    """When no usable vol_avg (all prior zero/NaN), we allow and note it."""
    day = "2025-03-10"
    rows = [
        ("07:00", 4.0, 4.1, 3.9, 4.05, 0),
        ("07:05", 4.05, 4.6, 4.0, 4.55, 250_000),  # first real volume bar breaks
    ]
    df = _frame(day, rows)
    e = detect_from_frame(df, _cand(), ScanConfig(vol_expansion_mult=1.5), 3e6)
    assert e is not None
    assert "(no premarket volume baseline)" in e.reason
