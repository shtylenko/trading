from __future__ import annotations

from datetime import date

from trading.lab.core.models import StrategyContext
from trading.lab.strategies import get_release_class, list_releases

from .conftest import make_5m_bars, make_daily_bars


def _context(
    bars=None,
    daily=None,
    release_id: str = "o01",
) -> StrategyContext:
    return StrategyContext(
        trade_date=date(2024, 4, 1),
        release_id=release_id,
        testset="unit",
        bars_5m={"AAPL": bars if bars is not None else make_5m_bars()},
        daily={"AAPL": daily if daily is not None else make_daily_bars()},
    )


def test_strategy_registry_exposes_p0_releases():
    # Shippable strategy releases (research-only "capture_*" variants excluded).
    strategy_releases = [r for r in list_releases() if not r.startswith("capture_")]
    assert strategy_releases == [
        "d01", "d02", "d03", "d04", "d05", "d06", "d07", "d08", "d09", "d10",
        "d11", "d12", "d13", "d14", "d15",
        "f01", "f02", "f03", "f04", "f05", "f06", "f07",
        "m01", "m02", "m03",
        "o01", "o02", "o03", "o04", "o05", "o06", "o07", "o08", "o09", "o10", "o11",
        "s01",
        "x01", "x03", "x04",
    ]

    orb = get_release_class("o01")()
    drive = get_release_class("d01")()
    flip = get_release_class("f01")()
    mom = get_release_class("m01")()
    resid_mom = get_release_class("x03")()

    assert orb.strategy_alias == "stocks_in_play_orb"
    assert orb.strategy_letter == "o"
    assert drive.strategy_alias == "post_gap_opening_drive"
    assert drive.strategy_letter == "d"
    assert flip.strategy_alias == "dominance_flip_reversal"
    assert flip.strategy_letter == "f"
    assert mom.strategy_alias == "intraday_momentum"
    assert mom.strategy_letter == "m"
    assert resid_mom.strategy_alias == "xsec_momentum"
    assert resid_mom.strategy_letter == "x"


def test_o01_builds_opening_range_breakout_signal():
    release = get_release_class("o01")()
    context = _context(release_id="o01")

    candidates = release.build_candidates(context)
    signal = release.build_signal(context, candidates[0])

    assert len(candidates) == 1
    assert candidates[0].ticker == "AAPL"
    assert signal is not None
    assert signal.entry_trigger == 101.0
    assert signal.stop_price == 99.5
    assert signal.target_price == 102.5
    assert signal.signal_time == context.bars_5m["AAPL"].index[0].to_pydatetime()


def test_o01_rejects_red_first_candle():
    release = get_release_class("o01")()
    bars = make_5m_bars(first_open=100.0, first_close=99.9)
    context = _context(bars=bars, release_id="o01")

    assert release.build_candidates(context) == []


def test_d01_builds_gap_drive_signal_using_prior_day_high():
    release = get_release_class("d01")()
    context = _context(
        daily=make_daily_bars(prior_high=98.2, latest_close=99.2),
        release_id="d01",
    )

    candidates = release.build_candidates(context)
    signal = release.build_signal(context, candidates[0])

    assert len(candidates) == 1
    assert candidates[0].features["gap_pct_vs_prior_high"] > 1.0
    assert signal is not None
    assert signal.setup_type == "post_gap_opening_drive"
    assert signal.entry_trigger == 101.0
    assert signal.stop_price == 99.5


def test_d01_rejects_when_gap_is_too_small():
    release = get_release_class("d01")()
    context = _context(
        daily=make_daily_bars(prior_high=100.0, latest_close=100.5),
        release_id="d01",
    )

    assert release.build_candidates(context) == []
