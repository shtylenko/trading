"""The two Monte Carlo permutation gates.

In-sample gate
    H0: the strategy is worthless; its in-sample excellence is data-mining
    bias (the optimizer found something in noise). Optimize on N
    permutations of the training data; the quasi p-value is the fraction
    of permutations whose optimized objective matched or beat the real
    one. Pass: p < 0.01 (with >= 1000 permutations; 100 is a hard floor).

Walk-forward gate
    H0: the walk-forward result is luck — a worthless strategy could have
    done as well on data it never trained on. Permute only the bars after
    the first training fold, walk the same process forward on each
    permutation. Pass: p <= 0.05 on one year of OOS data, p < 0.01 on two
    or more (~200 permutations is typical; this test is slow).

Run the in-sample gate FIRST. It costs no out-of-sample data: every peek
at validation data stacks selection bias that no later test can remove.
Do not iterate a strategy against these p-values — a measure that becomes
a target stops being a measure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from .metrics import position_returns, profit_factor
from .permutation import permute_bars
from .walkforward import OptimizeFn, SignalFn, walk_forward_signal

logger = logging.getLogger("strategy_lab.validation")


@dataclass
class PermutationTestResult:
    test: str
    real_objective: float
    permuted_objectives: list[float] = field(default_factory=list)
    n_better_or_equal: int = 0

    @property
    def n_permutations(self) -> int:
        return len(self.permuted_objectives)

    @property
    def p_value(self) -> float:
        if not self.permuted_objectives:
            return float("nan")
        return self.n_better_or_equal / self.n_permutations

    def summary(self) -> str:
        perm = np.asarray(self.permuted_objectives, dtype=float)
        finite = perm[np.isfinite(perm)]
        lines = [
            f"{self.test} permutation test",
            f"  real objective:      {self.real_objective:.4f}",
            f"  permutations:        {self.n_permutations}"
            f"  (mean {finite.mean():.4f}, max {finite.max():.4f})"
            if finite.size else f"  permutations:        {self.n_permutations}",
            f"  p-value:             {self.p_value:.4f}"
            f"  ({self.n_better_or_equal} matched or beat real)",
        ]
        return "\n".join(lines)


def insample_permutation_test(
    ohlc: pd.DataFrame,
    optimize_objective_fn: Callable[[pd.DataFrame], float],
    n_permutations: int = 1000,
    seed: int | None = None,
    progress: bool = False,
) -> PermutationTestResult:
    """Gate 2: is in-sample excellence just data-mining bias?

    ``optimize_objective_fn`` runs the FULL optimization (grid search,
    model fit, ...) on the given bars and returns the best objective
    value found. It is invoked once on real data and once per permutation.
    """
    rng = np.random.default_rng(seed)
    real = float(optimize_objective_fn(ohlc))
    result = PermutationTestResult("in-sample", real)
    for i in range(n_permutations):
        perm = permute_bars(ohlc, seed=rng)
        obj = float(optimize_objective_fn(perm))
        result.permuted_objectives.append(obj)
        if obj >= real:
            result.n_better_or_equal += 1
        if progress and (i + 1) % 50 == 0:
            print(f"  in-sample permutations: {i + 1}/{n_permutations} "
                  f"(p so far {result.p_value:.4f})", flush=True)
    return result


def walkforward_permutation_test(
    ohlc: pd.DataFrame,
    optimize_fn: OptimizeFn,
    signal_fn: SignalFn,
    train_lookback: int,
    train_step: int,
    n_permutations: int = 200,
    objective_fn: Callable[[pd.Series], float] = profit_factor,
    seed: int | None = None,
    progress: bool = False,
) -> PermutationTestResult:
    """Gate 4: could a worthless strategy match the walk-forward result?

    Only bars after the first training fold are permuted
    (``start_index=train_lookback``), so every permutation trains its
    first fold on the same real data the strategy did — what varies is
    whether the "future" contains real patterns or noise.
    """
    rng = np.random.default_rng(seed)

    def wf_objective(bars: pd.DataFrame) -> float:
        sig = walk_forward_signal(bars, optimize_fn, signal_fn,
                                  train_lookback, train_step)
        return float(objective_fn(position_returns(bars["close"], sig)))

    real = wf_objective(ohlc)
    result = PermutationTestResult("walk-forward", real)
    for i in range(n_permutations):
        perm = permute_bars(ohlc, start_index=train_lookback, seed=rng)
        obj = wf_objective(perm)
        result.permuted_objectives.append(obj)
        if obj >= real:
            result.n_better_or_equal += 1
        if progress and (i + 1) % 10 == 0:
            print(f"  walk-forward permutations: {i + 1}/{n_permutations} "
                  f"(p so far {result.p_value:.4f})", flush=True)
    return result
