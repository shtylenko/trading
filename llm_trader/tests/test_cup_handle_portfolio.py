"""Tests for the deterministic cup-handle shared-portfolio replay."""

from __future__ import annotations

import pytest

from trading.llm_trader.strategies.cup_handle.portfolio import (
    PortfolioConfig,
    PortfolioReplayError,
    replay,
)


def _leaf(
    sid: str,
    ticker: str,
    setup_day: str,
    entry_day: str,
    exit_day: str,
    *,
    risk: float = 500.0,
    pnl: float = 100.0,
    shares: int = 100,
    entry_price: float = 10.0,
) -> dict:
    """One complete two-fill leaf whose action deltas exactly reproduce P&L."""
    entry_fee = -0.5
    return {
        "sid": sid,
        "ticker": ticker,
        "setup_day": setup_day,
        "pnl": {
            "traded": True,
            "initial_risk": risk,
            "r_multiple": pnl / risk,
            "realized_pnl": pnl,
        },
        "actions": [
            {
                "date": entry_day,
                "time": "16:00",
                "side": "buy",
                "price": entry_price,
                "shares": shares,
                "position_after": shares,
                "realized_delta": entry_fee,
            },
            {
                "date": exit_day,
                "time": "16:00",
                "side": "sell",
                "price": entry_price + (pnl - entry_fee) / shares,
                "shares": shares,
                "position_after": 0,
                "realized_delta": pnl - entry_fee,
            },
        ],
    }


def test_replay_enforces_ticker_limit_and_releases_capacity_after_exit():
    result = replay(
        [
            _leaf("aaa-1", "AAA", "2025-01-01", "2025-01-02", "2025-01-10", pnl=100),
            _leaf("aaa-2", "AAA", "2025-01-03", "2025-01-05", "2025-01-12", pnl=300),
            _leaf("bbb-1", "BBB", "2025-01-03", "2025-01-05", "2025-01-06", pnl=-100),
            _leaf("ccc-1", "CCC", "2025-01-10", "2025-01-11", "2025-01-13", pnl=200),
        ],
        PortfolioConfig(max_open_positions=2, max_open_risk=1_000, max_gross_notional=5_000),
    )

    assert [row["sid"] for row in result["accepted"]] == ["aaa-1", "bbb-1", "ccc-1"]
    assert result["skipped"] == [{
        "sid": "aaa-2", "ticker": "AAA", "setup_day": "2025-01-03",
        "entry_day": "2025-01-05", "reason": "ticker_position_limit",
        "initial_risk": 500.0, "entry_notional": 1000.0,
    }]
    summary = result["summary"]
    assert summary["portfolio_realized_pnl"] == 200.0
    assert summary["accepted_trades"] == 3
    assert summary["max_open_positions"] == 2


def test_replay_uses_stable_entry_priority_for_shared_capacity():
    result = replay(
        [
            _leaf("bbb-1", "BBB", "2025-01-01", "2025-01-02", "2025-01-04"),
            _leaf("aaa-1", "AAA", "2025-01-01", "2025-01-02", "2025-01-04"),
        ],
        PortfolioConfig(max_open_positions=1, max_open_risk=1_000, max_gross_notional=5_000),
    )

    assert [row["sid"] for row in result["accepted"]] == ["aaa-1"]
    assert result["skipped"][0]["sid"] == "bbb-1"
    assert result["skipped"][0]["reason"] == "max_open_positions"


def test_replay_fails_closed_when_action_pnl_does_not_match_persisted_leaf():
    leaf = _leaf("aaa-1", "AAA", "2025-01-01", "2025-01-02", "2025-01-04")
    leaf["pnl"]["realized_pnl"] = 123.0

    with pytest.raises(PortfolioReplayError, match="do not match"):
        replay([leaf], PortfolioConfig())
