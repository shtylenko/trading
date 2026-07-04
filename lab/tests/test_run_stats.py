"""Regression tests for the run-level R-series validation stats.

Covers two peer-review findings:
  H6 — sign-flip p-value uses the add-one finite-sample correction, so a
       Monte-Carlo run with zero exceedances can never report p == 0.
  H3 — pooling several runs keeps each run's daily series distinct (built
       per-run then concatenated) instead of merging shared calendar dates
       into a single observation and fabricating zero-pad days.
"""

from __future__ import annotations

import numpy as np

from trading.lab.validation.run_stats import (
    daily_r_series,
    permutation_pvalue,
    validate_daily_r,
)


def test_pvalue_never_zero_add_one_correction():
    # A strongly positive series: with few iterations the null may never
    # exceed the observed total, which under the naive estimator would give
    # p == 0. The add-one correction floors it at 1 / (iters + 1).
    daily = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    rng = np.random.default_rng(0)
    iters = 50
    p = permutation_pvalue(daily, iters, rng)
    assert p >= 1.0 / (iters + 1)
    assert p > 0.0

    bundle = validate_daily_r([("2024-01-02", 1.0)] * 5, n_days=5, iters=iters)
    assert bundle["p_value"] > 0.0


def test_daily_r_series_sums_per_day_and_pads():
    trades = [("2024-01-02", 1.0), ("2024-01-02", -0.25), ("2024-01-03", 0.5)]
    series = daily_r_series(trades, n_days=4)
    # Two trade-days collapse to their per-day sums; remaining days zero-pad.
    assert sorted(series.tolist()) == sorted([0.75, 0.5, 0.0, 0.0])
    assert series.size == 4


def test_pooling_keeps_overlapping_dates_distinct():
    # Two runs each trade once on the SAME calendar date.
    run_a = [("2024-01-02", 1.0)]
    run_b = [("2024-01-02", -0.25)]

    # Correct (post-fix) pooling: build each run's series, then concatenate.
    pooled = np.concatenate([daily_r_series(run_a, 1), daily_r_series(run_b, 1)])
    assert sorted(pooled.tolist()) == [-0.25, 1.0]
    assert pooled.size == 2

    # The old behaviour merged by calendar date and padded to the summed day
    # count, destroying the two real observations.
    merged = daily_r_series(run_a + run_b, n_days=2)
    assert sorted(merged.tolist()) == [0.0, 0.75]

    # The distinction matters: the two have different variance.
    assert pooled.std(ddof=1) != merged.std(ddof=1)
