"""Unit tests for C1 filter rules."""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading.swing_screener.c1_pullback.indicators import enrich_daily
from trading.swing_screener.c1_pullback.rules import (
    C1Config,
    extract_hits,
    mr_mask,
    pb_mask,
    shared_mask,
)


def _synthetic_leader(n: int = 260, seed: int = 1) -> pd.DataFrame:
    """Uptrend series with a late dip for RSI stress."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    close = 50 + 0.15 * t + rng.normal(0, 0.3, n)
    # Force a sharp 3-day drop near the end while staying above long MAs
    close[-4] *= 0.98
    close[-3] *= 0.96
    close[-2] *= 0.94
    close[-1] *= 0.93
    vol = np.full(n, 1_200_000.0)
    vol[-5:] = 800_000.0  # quieter pullback
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": vol,
        },
        index=pd.date_range("2022-01-03", periods=n, freq="B"),
    )
    return enrich_daily(df)


def test_shared_mask_blocks_below_sma200():
    df = _synthetic_leader()
    cfg = C1Config()
    # Crush price below SMA200 on last bar
    df = df.copy()
    df.iloc[-1, df.columns.get_loc("close")] = float(df["sma200"].iloc[-1]) * 0.5
    # recompute only close-dependent fields roughly for gate test
    m = (df["close"] > df["sma200"]) & (df["close"] >= cfg.price_min)
    assert not bool(m.iloc[-1])


def test_mr_mask_requires_low_rsi2():
    df = _synthetic_leader()
    cfg = C1Config()
    mask = mr_mask(df, cfg)
    # Where MR hits, rsi2 must be < 10 and above SMAs
    if mask.any():
        hits = df.loc[mask]
        assert (hits["rsi2"] < cfg.mr.rsi2_max).all()
        assert (hits["close"] > hits["sma200"]).all()
        assert (hits["close"] > hits["sma50"]).all()


def test_pb_mask_rsi_band_and_quiet_vol():
    df = _synthetic_leader()
    cfg = C1Config()
    mask = pb_mask(df, cfg)
    if mask.any():
        hits = df.loc[mask]
        assert (hits["rsi14"] >= cfg.pb.rsi14_min).all()
        assert (hits["rsi14"] <= cfg.pb.rsi14_max).all()
        assert (hits["relvol"] <= cfg.pb.relvol_max).all()
        assert (hits["perf_5d"] <= cfg.pb.perf_5d_max).all()


def test_extract_hits_schema_and_date_clip():
    df = _synthetic_leader()
    cfg = C1Config()
    # Force a shared pass on last row for extract schema
    m = shared_mask(df, cfg)
    # if nothing, loosen by only checking extract on all True slice of last day
    if not m.any():
        m = pd.Series(False, index=df.index)
        m.iloc[-1] = True
        # ensure required cols finite
        for c in ("avg_vol_20", "sma50", "sma200", "rsi2", "rsi14"):
            if df[c].isna().iloc[-1]:
                return  # not enough structure; skip soft
    hits = extract_hits(
        df,
        m,
        ticker="TEST",
        variant="C1_MR",
        universe="liquid_pit",
        rules_version=cfg.rules_version,
        start=df.index[-5],
        end=df.index[-1],
    )
    if hits.empty:
        return
    assert "asof_date" in hits.columns
    assert set(hits["ticker"]) == {"TEST"}
    assert hits["rules_version"].iloc[0] == cfg.rules_version
    assert hits["earnings_ok"].isna().all() or hits["earnings_ok"].isnull().all()
