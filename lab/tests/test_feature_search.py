"""Tests for the feature-search harness (validation/cscv.py + scripts/feature_search.py).

Covers: PBO on a planted-overfit matrix (high PBO) vs a genuinely-robust one (low
PBO), CSCV block math, the subset/top-N scoring invariant, the grid enumerator's
same-feature rule, and a synthetic ledger with a PLANTED edge that walk-forward
should recover."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading.lab.validation.cscv import block_bounds, pbo_from_matrix
from trading.lab.experiments.harness import feature_search as fs


# ── CSCV / PBO ───────────────────────────────────────────────────────────────

def test_block_bounds_partition():
    b = block_bounds(100, 16)
    assert len(b) == 16
    assert b[0][0] == 0 and b[-1][1] == 100
    # contiguous, non-overlapping, covers everything
    assert all(b[i][1] == b[i + 1][0] for i in range(len(b) - 1))


def test_pbo_high_when_overfit():
    """Genuinely overfit structure: each combo's performance is ANTI-correlated
    across the timeline midpoint (whatever wins early loses late). The IS-best
    should land in the OOS bottom half → high PBO."""
    rng = np.random.default_rng(0)
    T, N = 64, 40
    perf = rng.normal(0, 1, (T, N))
    half = T // 2
    offsets = rng.normal(0, 4, N)
    perf[:half, :] += offsets          # combos that win in the first half...
    perf[half:, :] -= offsets          # ...lose by the same amount in the second
    res = pbo_from_matrix(perf, n_blocks=8)
    assert res["n_splits"] == 70  # C(8,4)
    assert res["pbo"] > 0.6  # selection is overfitting

    # discrimination: pure noise sits clearly above the robust case
    noise = pbo_from_matrix(rng.normal(0, 1, (T, N)), n_blocks=8)
    assert noise["pbo"] > 0.15


def test_pbo_low_when_robust():
    """One combo is genuinely better in EVERY slice → it should stay top OOS →
    PBO near 0."""
    rng = np.random.default_rng(1)
    T, N = 64, 40
    perf = rng.normal(0, 1, (T, N))
    perf[:, 0] += 5.0  # combo 0 dominates everywhere, every slice
    res = pbo_from_matrix(perf, n_blocks=8)
    assert res["pbo"] < 0.05
    assert res["is_best_also_oos_best_rate"] > 0.9


def test_pbo_insufficient_data():
    res = pbo_from_matrix(np.zeros((4, 1)), n_blocks=8)
    assert np.isnan(res["pbo"]) and res["n_splits"] == 0


# ── grid / enumeration ───────────────────────────────────────────────────────

def test_enumerate_combos_excludes_same_feature_pairs():
    combos = fs.enumerate_combos(2)
    assert () in combos  # unfiltered baseline present
    # gap floor+ceiling (same feature) IS allowed (a band)
    assert ("gap_floor_3", "gap_ceiling_12") in combos
    # two regime predicates on different features are fine
    assert ("spy_weak_regime", "sector_weak_regime") in combos
    # no combo repeats a single predicate
    assert all(len(set(c)) == len(c) for c in combos)


# ── scoring invariants ───────────────────────────────────────────────────────

def _synthetic_ledger(seed=0):
    """4 years × 60 days/yr × ~8 candidates/day. A PLANTED edge: rows with
    opening_rv>=1.5 have positive expected R; everything else is negative."""
    rng = np.random.default_rng(seed)
    rows = []
    for yr in (2022, 2023, 2024, 2025):
        days = pd.bdate_range(f"{yr}-01-01", periods=60)
        for d in days:
            for _ in range(8):
                rv = float(rng.uniform(0.5, 3.0))
                gap = float(rng.uniform(1.0, 15.0))
                edge = 0.25 if rv >= 1.5 else -0.20  # the planted signal
                r = float(rng.normal(edge, 1.0))
                rows.append({
                    "trade_date": d, "ticker": "X", "score": gap, "filled": True,
                    "realized_r": r, "opening_rv": rv,
                    "gap_pct_vs_prior_high": gap, "first_range_atr_frac": 0.3,
                    "first_close_pos": 0.5, "spy_below_50d_sma": 0.0,
                    "sector_below_50d_sma": 0.0, "first_open": 50.0,
                    "avg_daily_volume": 5e6,
                })
    df = pd.DataFrame(rows)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["year"] = df["trade_date"].dt.year
    return df


def test_apply_top_n_caps_per_day():
    df = _synthetic_ledger()
    day = df[df["trade_date"] == df["trade_date"].min()]
    assert len(fs.apply_top_n(day, top_n=0)) == 8    # uncapped
    assert len(fs.apply_top_n(day, top_n=3)) == 3     # capped to top-3 by gap/day


def test_daily_portfolio_objective_and_eligibility():
    df = _synthetic_ledger()
    pred = {n: fs._predicate_mask(df, n) for n in fs.GRID}
    m = fs.daily_portfolio(df[df["year"] == 2022], ("rvol_min_1_5",), pred, top_n=0)
    assert m["trades"] > 0 and m["eligible"] is True
    assert m["ir"] == m["ir_raw"]                     # eligible → objective is the raw IR
    assert fs.objective(m) == m["ir"]
    # the planted edge (rvol>=1.5) beats the unfiltered baseline on info ratio
    base = fs.daily_portfolio(df[df["year"] == 2022], (), pred, top_n=0)
    assert m["ir_raw"] > base["ir_raw"]


def test_walk_forward_recovers_planted_edge():
    df = _synthetic_ledger(seed=3)
    combos = fs.enumerate_combos(2)
    pred = {n: fs._predicate_mask(df, n) for n in fs.GRID}
    # loosen constraints for the small synthetic fixture
    orig = (fs.MIN_TRADES_TOTAL, fs.MIN_TRADES_PER_QTR)
    fs.MIN_TRADES_TOTAL, fs.MIN_TRADES_PER_QTR = 20, 1
    try:
        wf = fs.walk_forward(df, combos, pred, top_n=0)
    finally:
        fs.MIN_TRADES_TOTAL, fs.MIN_TRADES_PER_QTR = orig
    # every fold should select a combo containing the rvol predicate (the edge)
    for fo in wf["folds"]:
        assert "rvol_min_1_5" in fo["selected"], fo["selected"]
    assert wf["agg_oos_sum_r"] > 0
    assert wf["wf_pass"]


def test_perf_matrix_excludes_oos_year():
    df = _synthetic_ledger()
    combos = fs.enumerate_combos(1)
    pred = {n: fs._predicate_mask(df, n) for n in fs.GRID}
    perf = fs.build_perf_matrix(df, combos, pred, top_n=0)
    # rows = search-window days only (2022-2024), never 2025
    n_search_days = df[df["year"] != fs.OOS_YEAR]["trade_date"].dt.normalize().nunique()
    assert perf.shape[0] == n_search_days
    assert perf.shape[1] == len(combos)
