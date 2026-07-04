"""Tests for the Deflated Sharpe Ratio module + the CSCV embargo."""
from __future__ import annotations

import numpy as np

from trading.lab.validation.deflated_sharpe import (
    _norm_cdf, _norm_ppf, deflated_sharpe_ratio, effective_n_trials,
    expected_max_sharpe,
)
from trading.lab.validation.cscv import pbo_from_matrix


def test_norm_cdf_ppf_roundtrip():
    for x in (-2.5, -1.0, 0.0, 0.7, 2.0):
        assert abs(_norm_ppf(_norm_cdf(x)) - x) < 1e-6
    assert abs(_norm_cdf(0.0) - 0.5) < 1e-12
    assert abs(_norm_ppf(0.975) - 1.959964) < 1e-4


def test_expected_max_sharpe_grows_with_trials():
    v = 0.04
    assert expected_max_sharpe(v, 1) == 0.0          # <2 trials → no inflation
    e10 = expected_max_sharpe(v, 10)
    e1000 = expected_max_sharpe(v, 1000)
    assert 0 < e10 < e1000                            # more trials → higher null hurdle


def test_effective_n_trials_correlation_structure():
    rng = np.random.default_rng(0)
    T = 400
    indep = rng.normal(size=(T, 10))                  # ~orthogonal columns
    assert effective_n_trials(indep) > 7              # ≈ 10
    base = rng.normal(size=(T, 1))
    identical = np.repeat(base, 10, axis=1)           # all the same
    assert effective_n_trials(identical) < 1.5        # ≈ 1


def test_dsr_penalizes_more_trials():
    rng = np.random.default_rng(1)
    # a modest positive daily series
    r = rng.normal(0.03, 1.0, 500)
    few = deflated_sharpe_ratio(r, sr_variance=0.02, n_trials=3)["dsr"]
    many = deflated_sharpe_ratio(r, sr_variance=0.02, n_trials=500)["dsr"]
    assert few > many                                 # bigger search → lower DSR
    assert 0.0 <= many <= few <= 1.0


def test_dsr_strong_series_high_few_trials():
    rng = np.random.default_rng(2)
    r = rng.normal(0.25, 1.0, 750)                    # strong edge (~0.25 daily SR)
    # small search (few, tight trials) → low null hurdle → a real edge clears 0.95
    d = deflated_sharpe_ratio(r, sr_variance=0.0025, n_trials=5)
    assert d["dsr"] > 0.95
    assert d["sr_observed"] > d["sr_hurdle"]


def test_dsr_degenerate_inputs():
    assert np.isnan(deflated_sharpe_ratio(np.zeros(5), 0.02, 10)["dsr"])   # too few obs
    assert np.isnan(deflated_sharpe_ratio(np.ones(100), 0.02, 10)["dsr"])  # zero variance


def test_cscv_embargo_runs_and_discriminates():
    rng = np.random.default_rng(0)
    T, N = 64, 40
    perf = rng.normal(0, 1, (T, N))
    half = T // 2
    off = rng.normal(0, 4, N)
    perf[:half] += off; perf[half:] -= off            # overfit (anti-correlated halves)
    hi = pbo_from_matrix(perf, n_blocks=8, embargo=1)
    assert hi["pbo"] > 0.6
    robust = rng.normal(0, 1, (T, N)); robust[:, 0] += 5.0
    lo = pbo_from_matrix(robust, n_blocks=8, embargo=1)
    assert lo["pbo"] < 0.05
    # embargo=0 vs 1 both valid; thin blocks fall back gracefully (no crash)
    assert not np.isnan(pbo_from_matrix(robust, n_blocks=8, embargo=3)["pbo"])
