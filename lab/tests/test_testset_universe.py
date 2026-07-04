from __future__ import annotations

from datetime import date

from trading.lab.data.testsets import list_testsets, load_testset
from trading.lab.data.universes import load_universe_tickers


def test_load_standalone_strategy_lab_testset():
    testset = load_testset("smoke_april_2024_sample")

    assert testset.name == "smoke_april_2024_sample"
    assert testset.universe == "sp500_sample_pit"
    assert testset.universe_policy == "point_in_time"
    assert testset.date_ranges[0].role == "smoke"


def test_list_testsets_includes_strategy_lab_samples():
    names = set(list_testsets())

    assert "smoke_april_2024_sample" in names
    assert "gap_drive_smoke_april_2024" in names


def test_point_in_time_universe_snapshot_resolution():
    tickers = load_universe_tickers("sp500_sample_pit", date(2024, 4, 1))

    assert "AAPL" in tickers
    assert "SPY" in tickers
    assert tickers == sorted(tickers)
