"""Unit tests for micro_pullback paper book packaging."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

from trading.llm_trader.admission.portfolio import PortfolioLimits
from trading.llm_trader.admission.short_hold_paper import (
    apply_portfolio_to_pairs,
    write_short_hold_paper_book,
)
from trading.llm_trader.models import Entry
from trading.llm_trader.strategies.micro_pullback.config import MicroPullbackConfig
from trading.llm_trader.strategies.micro_pullback.paper import PAPER_CONTRACT, write_paper_book
from trading.llm_trader.strategies.micro_pullback.patterns import SimTrade
from trading.llm_trader.strategies.vwap_pullback.config import VwapPullbackConfig
from trading.llm_trader.strategies.vwap_pullback.paper import (
    PAPER_CONTRACT as VWAP_CONTRACT,
)
from trading.llm_trader.strategies.vwap_pullback.paper import write_paper_book as vwap_write


def _pair(ticker: str, day: date, et: str, xt: str, r: float = 0.1):
    e = Entry(
        ticker=ticker,
        day=day,
        time_et=et,
        pattern="micro_pullback",
        entry_px=100.0,
        bar_close=100.0,
        reason="t",
        strategy="micro_pullback",
        gap_pct=1.0,
        rvol=1.5,
        features={"stop_px": 99.0, "target1_px": 101.0, "target2_px": 102.0},
    )
    t = SimTrade(
        ticker=ticker,
        day=day,
        entry_time=et,
        entry_px=100.0,
        stop_px=99.0,
        target1_px=101.0,
        target2_px=102.0,
        exit_time=xt,
        exit_px=101.0,
        exit_reason="TARGET2",
        r_multiple=r,
        pnl_usd=r * 100,
        shares=10,
    )
    return e, t


def test_apply_portfolio_skips_over_capacity():
    d = date(2024, 6, 3)
    pairs = [
        _pair("A", d, "10:00", "11:00"),
        _pair("B", d, "10:05", "11:00"),
        _pair("C", d, "10:10", "11:00"),
        _pair("D", d, "10:15", "11:00"),
    ]
    kept, rej = apply_portfolio_to_pairs(
        pairs, PortfolioLimits(max_concurrent=3, max_per_day=5)
    )
    assert len(kept) == 3
    assert len(rej) == 1
    assert rej[0][0].ticker == "D"


def test_write_paper_book_md(tmp_path: Path):
    result = {
        "contract": PAPER_CONTRACT,
        "strategy": "micro_pullback",
        "nml_gate": False,
        "portfolio": {"max_concurrent": 3, "max_per_day": 5, "version": "port_v0.1.0"},
        "config": {
            "fee_bps_one_way": 1.0,
            "slippage_bps_one_way": 2.0,
            "risk_budget": 100.0,
        },
        "raw": {
            "n_entries": 10,
            "n_sim": 8,
            "pooled": {"n": 8, "win_pct": 50.0, "eff_r": 0.02, "pnl": 16.0},
            "years": {},
            "gates": {
                "pooled_eff_r_gt_0": True,
                "years_positive": 2,
                "years_total": 2,
                "pass": True,
            },
        },
        "paper": {
            "n_taken": 5,
            "n_skipped_portfolio": 3,
            "pooled": {"n": 5, "win_pct": 60.0, "eff_r": 0.03, "pnl": 15.0},
            "years": {"2024": {"n": 5, "win_pct": 60.0, "eff_r": 0.03, "pnl": 15.0}},
            "gates": {
                "pooled_eff_r_gt_0": True,
                "years_positive": 1,
                "years_total": 1,
                "pass": False,
            },
        },
        "cost_stress_on_taken": None,
        "trades": [],
        "rejected_sample": [],
        "rejected_total": 0,
        "completed_at": "2026-07-18T00:00:00+00:00",
        "promotion": {"status": "research_paper_optional", "notes": "test"},
    }
    j, m = write_paper_book(result, tmp_path)
    assert j.exists() and m.exists()
    text = m.read_text()
    assert "NML gate" in text
    assert PAPER_CONTRACT in text


def test_vwap_write_paper_book(tmp_path: Path):
    result = {
        "contract": VWAP_CONTRACT,
        "strategy": "vwap_pullback",
        "nml_gate": False,
        "portfolio": {"max_concurrent": 3, "max_per_day": 5, "version": "port_v0.1.0"},
        "config": {"fee_bps_one_way": 1.0, "slippage_bps_one_way": 2.0, "risk_budget": 100.0},
        "raw": {
            "n_entries": 5,
            "n_sim": 5,
            "pooled": {"n": 5, "win_pct": 40.0, "eff_r": 0.01, "pnl": 5.0},
            "years": {},
            "gates": {
                "pooled_eff_r_gt_0": True,
                "years_positive": 2,
                "years_total": 2,
                "pass": True,
            },
        },
        "paper": {
            "n_taken": 4,
            "n_skipped_portfolio": 1,
            "pooled": {"n": 4, "win_pct": 50.0, "eff_r": 0.02, "pnl": 8.0},
            "years": {"2024": {"n": 4, "win_pct": 50.0, "eff_r": 0.02, "pnl": 8.0}},
            "gates": {
                "pooled_eff_r_gt_0": True,
                "years_positive": 1,
                "years_total": 1,
                "pass": False,
            },
        },
        "cost_stress_on_taken": None,
        "trades": [],
        "rejected_sample": [],
        "rejected_total": 0,
        "completed_at": "2026-07-18T00:00:00+00:00",
        "promotion": {"status": "research_paper_optional", "notes": "vwap test"},
    }
    j, m = vwap_write(result, tmp_path)
    assert j.exists() and "VWAP" in m.read_text()


def test_config_paper_defaults():
    cfg = MicroPullbackConfig()
    assert cfg.nml_gate is False
    assert cfg.paper_portfolio is True
    assert cfg.paper_max_concurrent == 3
    assert cfg.paper_max_per_day == 5
    vcfg = VwapPullbackConfig()
    assert vcfg.nml_gate is False
    assert vcfg.paper_portfolio is True
