"""Tests for the synthetic dose-response positive control (scripts/synthetic_control.py).

Light, deterministic checks of the injection contract and detection behavior:
  - m=0 reproduces the real realized_r EXACTLY (the null IS the real ledger),
  - injection is additive and lands only on the planted predicate's rows,
  - a large dose makes the planted-predicate combo the pooled winner and passes WF.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading.lab.experiments.harness import feature_search as fs
from trading.lab.experiments.harness import synthetic_control as sc


def _ledger(seed=0):
    """4 years × 60 bdays × 8 candidates/day of NOISE realized_r (no real edge),
    with grid features populated. opening_rv is uniform so ~half the rows qualify
    for the rvol_min_1_5 plant."""
    rng = np.random.default_rng(seed)
    rows = []
    for yr in (2022, 2023, 2024, 2025):
        for d in pd.bdate_range(f"{yr}-01-01", periods=60):
            for _ in range(8):
                rows.append({
                    "trade_date": d, "ticker": "X",
                    "score": float(rng.uniform(1.0, 15.0)), "filled": True,
                    "realized_r": float(rng.normal(0.0, 1.0)),  # pure noise
                    "opening_rv": float(rng.uniform(0.5, 3.0)),
                    "gap_pct_vs_prior_high": float(rng.uniform(1.0, 15.0)),
                    "first_range_atr_frac": 0.3, "first_close_pos": 0.5,
                    "spy_below_50d_sma": float(rng.integers(0, 2)),
                    "sector_below_50d_sma": 0.0, "first_open": 50.0,
                    "avg_daily_volume": 5e6,
                })
    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["_realized_r_real"] = df["realized_r"].astype(float)
    return df


def test_null_dose_reproduces_real_ledger_exactly():
    df = _ledger()
    out = sc.inject(df, 0.0, sc.PLANT_PREDICATE)
    pd.testing.assert_series_equal(
        out["realized_r"], df["_realized_r_real"], check_names=False
    )


def test_injection_is_additive_only_on_planted_rows():
    df = _ledger()
    m = 0.5
    out = sc.inject(df, m, sc.PLANT_PREDICATE)
    mask = fs._predicate_mask(df, sc.PLANT_PREDICATE)
    delta = out["realized_r"] - df["_realized_r_real"]
    # qualifying rows shifted by exactly m; the rest untouched
    assert np.allclose(delta[mask], m)
    assert np.allclose(delta[~mask], 0.0)


def test_large_dose_makes_planted_combo_win_and_passes_wf():
    df = _ledger(seed=3)
    combos = fs.enumerate_combos(2)
    orig = (fs.MIN_TRADES_TOTAL, fs.MIN_TRADES_PER_QTR)
    fs.MIN_TRADES_TOTAL, fs.MIN_TRADES_PER_QTR = 20, 1
    try:
        res = sc.run_pipeline(sc.inject(df, 0.40, sc.PLANT_PREDICATE), combos,
                              top_n=0, blocks=8)
    finally:
        fs.MIN_TRADES_TOTAL, fs.MIN_TRADES_PER_QTR = orig
    assert sc._found(res["winner"], sc.PLANT_PREDICATE), res["winner"]
    assert res["wf"]["wf_pass"]
    # every LOO fold should also recover the planted predicate
    for fo in res["wf"]["folds"]:
        assert sc.PLANT_PREDICATE in fo["selected"], fo["selected"]


def test_null_pipeline_does_not_promote_pure_noise():
    """The pure-noise null must not be PROMOTED (false-positive control)."""
    df = _ledger(seed=11)
    combos = fs.enumerate_combos(2)
    orig = (fs.MIN_TRADES_TOTAL, fs.MIN_TRADES_PER_QTR)
    fs.MIN_TRADES_TOTAL, fs.MIN_TRADES_PER_QTR = 20, 1
    try:
        res = sc.run_pipeline(sc.inject(df, 0.0, sc.PLANT_PREDICATE), combos,
                              top_n=0, blocks=8)
    finally:
        fs.MIN_TRADES_TOTAL, fs.MIN_TRADES_PER_QTR = orig
    assert res["verdict"] != "PROMOTE"
