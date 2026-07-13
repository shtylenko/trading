"""Tests for C1 portfolio capacity layer."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from trading.swing_screener.c1_pullback.portfolio import (
    PortfolioConfig,
    apply_portfolio,
)


def _trade(
    ticker: str,
    entry: date,
    hold: int = 3,
    r: float = 0.5,
    variant: str = "C1_MR",
    rsi2: float = 5.0,
) -> dict:
    return {
        "ticker": ticker,
        "variant": variant,
        "signal_date": entry - timedelta(days=1),
        "entry_date": entry,
        "exit_date": entry + timedelta(days=hold),
        "realized_r": r,
        "entry_price": 100.0,
        "exit_price": 101.0,
        "stop_price": 95.0,
        "risk_per_share": 5.0,
        "pnl_pct": 0.01,
        "hold_days": hold,
        "exit_reason": "time",
        "entry_mode": "next_open",
        "rules_version": "test",
        "cost_bps_per_side": 0.0,
        "rsi2": rsi2,
        "rsi14": 40.0,
        "sma20_ext": 0.01,
        "pullback_depth_atr": 1.0,
        "relvol": 0.8,
    }


def test_max_positions_respected():
    d0 = date(2025, 3, 3)
    trades = pd.DataFrame(
        [
            _trade("AAA", d0, rsi2=3.0, r=1.0),
            _trade("BBB", d0, rsi2=4.0, r=1.0),
            _trade("CCC", d0, rsi2=5.0, r=1.0),
            _trade("DDD", d0, rsi2=6.0, r=1.0),
            _trade("EEE", d0, rsi2=7.0, r=-1.0),  # should be skipped (5th)
        ]
    )
    # features already on trades — pass empty candidates
    sel, summary = apply_portfolio(
        trades,
        cfg=PortfolioConfig(max_positions=4, max_per_sector=4),
        candidates=None,
        sector_map={t: "XLK" for t in ["AAA", "BBB", "CCC", "DDD", "EEE"]},
    )
    assert len(sel) == 4
    assert set(sel["ticker"]) == {"AAA", "BBB", "CCC", "DDD"}  # lowest rsi2
    assert summary[summary.scope == "ALL"]["n_selected"].iloc[0] == 4


def test_prefers_lower_rsi2():
    d0 = date(2025, 6, 2)
    trades = pd.DataFrame(
        [
            _trade("HIGH", d0, rsi2=9.0, r=0.1),
            _trade("LOW", d0, rsi2=2.0, r=0.1),
        ]
    )
    sel, _ = apply_portfolio(
        trades,
        cfg=PortfolioConfig(max_positions=1, max_per_sector=4),
        sector_map={"HIGH": "XLK", "LOW": "XLK"},
    )
    assert list(sel["ticker"]) == ["LOW"]


def test_sector_cap():
    d0 = date(2025, 4, 1)
    trades = pd.DataFrame(
        [
            _trade("A1", d0, rsi2=1.0),
            _trade("A2", d0, rsi2=2.0),
            _trade("A3", d0, rsi2=3.0),
            _trade("B1", d0, rsi2=4.0),
        ]
    )
    smap = {"A1": "XLK", "A2": "XLK", "A3": "XLK", "B1": "XLF"}
    sel, _ = apply_portfolio(
        trades,
        cfg=PortfolioConfig(max_positions=4, max_per_sector=2),
        sector_map=smap,
    )
    assert len(sel) == 3  # 2 XLK + 1 XLF
    assert (sel[sel.ticker.str.startswith("A")].shape[0]) == 2
