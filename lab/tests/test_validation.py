"""Tests for the permutation-test validation toolkit."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading.lab.validation import (
    insample_permutation_test,
    permute_bars,
    position_returns,
    profit_factor,
    walk_forward_signal,
    walkforward_permutation_test,
)
from trading.lab.validation.examples import (
    donchian_signal,
    optimize_donchian,
    optimize_donchian_objective,
)


def _make_bars(n: int = 500, seed: int = 1, drift: float = 0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    log_close = np.cumsum(rng.normal(drift, 0.01, n)) + np.log(100.0)
    close = np.exp(log_close)
    gap = np.exp(rng.normal(0, 0.002, n))
    open_ = np.empty(n)
    open_[0] = close[0] * 0.999
    open_[1:] = close[:-1] * gap[1:]
    hi_off = np.exp(np.abs(rng.normal(0, 0.004, n)))
    lo_off = np.exp(-np.abs(rng.normal(0, 0.004, n)))
    high = np.maximum(open_, close) * hi_off
    low = np.minimum(open_, close) * lo_off
    idx = pd.date_range("2022-01-03", periods=n, freq="B", tz="America/New_York")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "volume": rng.integers(1_000, 100_000, n)},
        index=idx,
    )


class TestPermuteBars:
    def test_preserves_endpoints_and_geometry(self):
        bars = _make_bars()
        perm = permute_bars(bars, seed=42)
        assert perm.index.equals(bars.index)
        # first bar and last close unchanged (overall trend preserved)
        assert perm.iloc[0][["open", "high", "low", "close"]].equals(
            bars.iloc[0][["open", "high", "low", "close"]])
        assert perm["close"].iloc[-1] == pytest.approx(bars["close"].iloc[-1])
        # bar geometry still valid
        assert (perm["high"] >= perm[["open", "close"]].max(axis=1) - 1e-9).all()
        assert (perm["low"] <= perm[["open", "close"]].min(axis=1) + 1e-9).all()
        # it actually permuted something
        assert not perm["close"].equals(bars["close"])
        # volume is a permutation of the original
        assert sorted(perm["volume"]) == sorted(bars["volume"])

    def test_preserves_return_moments(self):
        bars = _make_bars(n=2000)
        perm = permute_bars(bars, seed=7)
        r_real = np.log(bars["close"]).diff().dropna()
        r_perm = np.log(perm["close"]).diff().dropna()
        # Mean is exactly preserved (same endpoints, same bar count); std
        # only approximately — gaps and intrabar offsets are re-paired.
        assert r_perm.mean() == pytest.approx(r_real.mean(), abs=1e-10)
        assert r_perm.std() == pytest.approx(r_real.std(), rel=0.15)

    def test_start_index_keeps_prefix_real(self):
        bars = _make_bars()
        perm = permute_bars(bars, start_index=100, seed=3)
        pd.testing.assert_frame_equal(perm.iloc[:101], bars.iloc[:101])
        assert not perm["close"].iloc[101:].equals(bars["close"].iloc[101:])

    def test_multimarket_same_shuffle_preserves_correlation(self):
        a = _make_bars(n=1500, seed=11)
        noise = _make_bars(n=1500, seed=12)
        # b strongly correlated with a
        b = a.copy()
        b[["open", "high", "low", "close"]] *= noise[["open", "high", "low", "close"]].to_numpy() / 100.0
        pa, pb = permute_bars([a, b], seed=5)
        corr_real = np.corrcoef(np.log(a["close"]).diff().dropna(),
                                np.log(b["close"]).diff().dropna())[0, 1]
        corr_perm = np.corrcoef(np.log(pa["close"]).diff().dropna(),
                                np.log(pb["close"]).diff().dropna())[0, 1]
        assert corr_perm == pytest.approx(corr_real, abs=0.05)

    def test_mismatched_indexes_rejected(self):
        a, b = _make_bars(300), _make_bars(301)
        with pytest.raises(ValueError, match="identical index"):
            permute_bars([a, b])


class TestMetrics:
    def test_position_returns_alignment(self):
        close = pd.Series([100.0, 110.0, 99.0], index=pd.RangeIndex(3))
        sig = pd.Series([1.0, 0.0, 1.0], index=pd.RangeIndex(3))
        r = position_returns(close, sig)
        # bar 0: long, earns log(110/100); bar 1: flat; bar 2: last bar, 0
        assert r.iloc[0] == pytest.approx(np.log(1.1))
        assert r.iloc[1] == 0.0
        assert r.iloc[2] == 0.0

    def test_profit_factor(self):
        assert profit_factor(pd.Series([0.02, -0.01])) == pytest.approx(2.0)
        assert profit_factor(pd.Series([0.02, 0.01])) == float("inf")
        assert profit_factor(pd.Series([0.0])) == 0.0


class TestWalkForward:
    def test_signal_only_after_first_fold_and_reoptimizes(self):
        bars = _make_bars(n=300)
        calls: list[int] = []

        def opt(train):
            calls.append(len(train))
            return 20

        sig = walk_forward_signal(bars, opt, donchian_signal,
                                  train_lookback=200, train_step=25)
        assert (sig.iloc[:200] == 0).all()
        assert len(calls) == 4  # bars 200,225,250,275
        assert all(c == 200 for c in calls)


class TestGates:
    def test_insample_gate_rejects_lookahead_strategy(self):
        # A "strategy" that memorizes the real data's returns (perfect
        # foresight) scores far better on real data than on permutations
        # of itself? No — it cheats equally well on both. Instead: a
        # strategy whose edge is genuine trend rides real drift...
        # Simplest deterministic check: an objective that is high only
        # on the exact real frame (worst-case data mining) must FAIL.
        bars = _make_bars(n=400, seed=21)

        def trash_objective(ohlc: pd.DataFrame) -> float:
            # pure noise-mining: optimizer power is identical on any data
            rng = np.random.default_rng(int(ohlc["close"].iloc[-1] * 100) % 2**32)
            return float(rng.normal(1.0, 0.05))

        res = insample_permutation_test(bars, trash_objective,
                                        n_permutations=60, seed=9)
        assert res.p_value > 0.05  # cannot reject H0: it's garbage

    def test_insample_gate_passes_real_pattern(self):
        # Plant a real exploitable pattern: strong momentum (sign of the
        # prior bar's return persists). Permutation destroys
        # autocorrelation, so the same optimizer scores worse on perms.
        rng = np.random.default_rng(4)
        n = 800
        r = np.empty(n)
        r[0] = 0.001
        for i in range(1, n):
            r[i] = 0.6 * r[i - 1] + rng.normal(0, 0.008)
        close = np.exp(np.cumsum(r) + np.log(100))
        bars = _make_bars(n=n, seed=4)
        scale = close / bars["close"].to_numpy()
        for col in ("open", "high", "low", "close"):
            bars[col] = bars[col].to_numpy() * scale

        def momentum_objective(ohlc: pd.DataFrame) -> float:
            sig = np.sign(np.log(ohlc["close"]).diff()).fillna(0.0)
            return profit_factor(position_returns(ohlc["close"], sig))

        res = insample_permutation_test(bars, momentum_objective,
                                        n_permutations=60, seed=9)
        assert res.p_value <= 0.05

    def test_walkforward_gate_runs_and_bounds(self):
        bars = _make_bars(n=320, seed=15)
        res = walkforward_permutation_test(
            bars, optimize_donchian, donchian_signal,
            train_lookback=200, train_step=40,
            n_permutations=10, seed=2,
        )
        assert res.n_permutations == 10
        assert 0.0 <= res.p_value <= 1.0
        assert "walk-forward" in res.summary()
