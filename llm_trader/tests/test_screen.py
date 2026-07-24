"""Mocked tests for daily gap screen (A1)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from trading.llm_trader.config import ScanConfig
from trading.llm_trader.screen import GapCandidate, screen_ticker


def _daily_frame(rows):
    """rows: (date_str, open, high, low, close, vol)"""
    idx = pd.DatetimeIndex(
        [pd.Timestamp(f"{d} 00:00", tz="UTC") for d, *_ in rows],
        name="timestamp",
    )
    return pd.DataFrame(
        {
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "volume": [r[5] for r in rows],
        },
        index=idx,
    )


def test_screen_filters_gap_rvol_price(tmp_path):
    cfg = ScanConfig(start=date(2025, 3, 10), end=date(2025, 3, 12), rvol_lookback=2,
                     gap_min_pct=5, price_min=2, price_max=20, avg_vol_min=100_000, rvol_min=2)

    # Provide enough history for rvol_lookback + 2 check inside screen_ticker
    frame = _daily_frame([
        ("2025-03-05", 4.0, 4.1, 3.9, 4.0, 200_000),
        ("2025-03-06", 4.0, 4.1, 3.9, 4.0, 210_000),
        ("2025-03-07", 4.0, 4.1, 3.9, 4.0, 190_000),
        # The prior full-day volume is the causal next-session ratio input.
        ("2025-03-09", 4.0, 4.1, 3.9, 4.0, 2_000_000),
        ("2025-03-10", 4.8, 5.1, 4.7, 5.0, 300_000),  # +20% gap
        ("2025-03-11", 5.1, 5.2, 5.0, 5.05, 300_000),
    ])

    with patch("trading.llm_trader.strategies.warrior.screen.fetch_bars", return_value=frame):
        cands = screen_ticker("GAP", cfg)
        assert len(cands) == 1
        c = cands[0]
        assert c.day == date(2025, 3, 10)
        assert c.gap_pct > 15
        assert c.prior_day_volume_ratio > 2


def test_runner_smoke_with_mocks(tmp_path):
    """End-to-end smoke of run_scan using heavy mocks (no real API calls)."""
    from trading.llm_trader.config import ScanConfig
    from trading.llm_trader.strategies.warrior.runner import run_scan

    db = tmp_path / "test.db"
    cfg = ScanConfig(start=date(2025, 3, 10), end=date(2025, 3, 10), db_path=db)

    fake_syms = ["TEST1", "TEST2"]
    mod = "trading.llm_trader.strategies.warrior.runner"

    with patch(f"{mod}.fetch_symbols", return_value=fake_syms), \
         patch(f"{mod}.screen_ticker") as mock_screen, \
         patch(f"{mod}.FloatCache") as MockFloat, \
         patch(f"{mod}.detect_entry") as mock_detect:

        # screen returns a candidate for first ticker only
        mock_screen.side_effect = lambda s, c: [GapCandidate(s, date(2025, 3, 10), 5.0, 4.0, 25.0, 5.0, 600000, 800000)] if s == "TEST1" else []
        mock_float_inst = MockFloat.return_value
        mock_float_inst.snapshot.return_value = {
            "value": 5_000_000,
            "source": "float",
            "fetched_at": "2026-07-23T00:00:00+00:00",
            "as_of": "retrieval_time_current_snapshot",
            "point_in_time": False,
            "fallback_used": False,
        }
        mock_float_inst.flush = MagicMock()

        from trading.llm_trader.patterns import Entry as E
        mock_detect.return_value = E(
            ticker="TEST1", day=date(2025, 3, 10), time_et="09:45",
            pattern="acd_orb", entry_px=5.2, bar_close=5.3,
            gap_pct=25.0, rvol=5.0, float_shares=5e6, bar_vol_mult=2.1,
            reason="test entry",
        )

        stats = run_scan(cfg, symbols=fake_syms)
        assert stats.entries_found == 1
        assert db.exists()
