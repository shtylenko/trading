"""Compare Alpaca SIP vs MarketData raw OHLCV for META, then verify cache fidelity.

Test flow for each timeframe (1min, 15min):
  1. Fetch META bars from Alpaca SIP (direct provider, no cache).
  2. Fetch the same bars from MarketData (direct provider, no cache).
  3. Compare every bar — assert price differences are < 0.5%.
  4. Write the Alpaca data to the Parquet cache.
  5. Read back from cache and assert every OHLCV cell matches Alpaca.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import pandas as pd
import pytest

_TZ_NY = "America/New_York"
PRICE_TOLERANCE = 0.005       # 0.5% max price difference between providers
VOLUME_TOLERANCE = 0.20       # 20% max volume difference between providers


@pytest.fixture(autouse=True)
def _fresh_data_dir():
    """Isolated temp dir so cache is empty — all fetches come from providers."""
    old = os.environ.get("STRATEGY_LAB_MARKETDATA_DIR")
    with tempfile.TemporaryDirectory(prefix="smd_cross_") as td:
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = td
        import importlib
        import trading.marketdata.config
        importlib.reload(trading.marketdata.config)
        yield
    if old is None:
        os.environ.pop("STRATEGY_LAB_MARKETDATA_DIR", None)
    else:
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = old


def _compare_providers(ticker: str, timeframe: str, day: str) -> dict:
    """Fetch from Alpaca SIP and MarketData, compare, return aligned data."""
    ny = __import__("zoneinfo").ZoneInfo(_TZ_NY)
    start = datetime.strptime(f"{day} 09:30", "%Y-%m-%d %H:%M").replace(tzinfo=ny)
    end = datetime.strptime(f"{day} 16:00", "%Y-%m-%d %H:%M").replace(tzinfo=ny)

    from trading.marketdata.providers.alpaca_provider import AlpacaProvider
    from trading.marketdata.providers.marketdata_provider import MarketDataProvider

    ap = AlpacaProvider()
    a_raw = ap.fetch_bars(ticker, timeframe, start, end)
    assert a_raw is not None and not a_raw.empty, (
        f"Alpaca returned no {timeframe} data for {ticker} on {day}"
    )

    mdp = MarketDataProvider()
    m_raw = mdp.fetch_bars(ticker, timeframe, start, end, session="rth")
    assert m_raw is not None and not m_raw.empty, (
        f"MarketData returned no {timeframe} data for {ticker} on {day}"
    )

    # Normalise to ET for comparison
    a = a_raw.copy()
    a.index = a.index.tz_convert(ny)
    m = m_raw.copy()
    m.index = m.index.tz_convert(ny)

    return {"alpaca": a, "marketdata": m, "start": start, "end": end}


def _assert_providers_agree(data: dict, label: str) -> None:
    """Compare aligned Alpaca and MarketData DataFrames."""
    a = data["alpaca"]
    m = data["marketdata"]
    common = a.index.intersection(m.index)
    assert len(common) > 0, f"No common bars between providers for {label}"

    errors = []
    for ts in common:
        ar = a.loc[ts]
        mr = m.loc[ts]
        for col in ["open", "high", "low", "close"]:
            av, mv = float(ar[col]), float(mr[col])
            if av != 0:
                rd = abs(av - mv) / abs(av)
                if rd > PRICE_TOLERANCE:
                    errors.append(
                        f"  {ts.strftime('%H:%M')} {col}: "
                        f"Alpaca={av:.4f} MarketData={mv:.4f} "
                        f"({rd*100:.2f}%)"
                    )
    assert not errors, (
        f"Alpaca vs MarketData disagreement for {label}:\n"
        + "\n".join(errors[:10])
    )


def _assert_cache_matches_alpaca(data: dict, timeframe: str, label: str) -> None:
    """Write Alpaca data to Parquet cache and verify read-back."""
    a = data["alpaca"]
    ticker = "META"

    # Write to cache
    from trading.marketdata.storage import write_bars, update_meta_summary

    write_bars(ticker, timeframe, a, session="rth", adjustment="raw",
               provider_name="alpaca")
    update_meta_summary(ticker, timeframe, "rth", "raw")

    # Read back from cache
    from trading.marketdata.storage import read_bars

    cached = read_bars(ticker, timeframe,
                       start=data["start"], end=data["end"],
                       session="rth", adjustment="raw", tz=_TZ_NY)
    assert cached is not None and not cached.empty, (
        f"Cache empty after write for {label}"
    )

    # Compare every cell
    errors = []
    common = a.index.intersection(cached.index)
    for ts in common:
        ar = a.loc[ts]
        cr = cached.loc[ts]
        for col in ["open", "high", "low", "close", "volume"]:
            av = float(ar[col])
            cv = float(cr[col])
            if av != cv:
                errors.append(
                    f"  {ts.strftime('%H:%M')} {col}: "
                    f"Alpaca={av} Cache={cv}"
                )
    assert not errors, (
        f"Cache mismatch with Alpaca for {label}:\n"
        + "\n".join(errors[:10])
    )


# ── 1-minute tests ────────────────────────────────────────────────────────────


class Test1Min:
    """META 1min bars — Alpaca vs MarketData + cache fidelity."""

    DAY = "2026-03-02"
    @pytest.mark.network

    def test_providers_agree(self):
        data = _compare_providers("META", "1min", self.DAY)
        _assert_providers_agree(data, "META 1min")
    @pytest.mark.network

    def test_cache_fidelity(self):
        data = _compare_providers("META", "1min", self.DAY)
        _assert_cache_matches_alpaca(data, "1min", "META 1min")


# ── 15-minute tests ───────────────────────────────────────────────────────────


class Test15Min:
    """META 15min bars — Alpaca vs MarketData + cache fidelity."""

    DAY = "2026-03-02"
    @pytest.mark.network

    def test_providers_agree(self):
        data = _compare_providers("META", "15min", self.DAY)
        _assert_providers_agree(data, "META 15min")
    @pytest.mark.network

    def test_cache_fidelity(self):
        data = _compare_providers("META", "15min", self.DAY)
        _assert_cache_matches_alpaca(data, "15min", "META 15min")
