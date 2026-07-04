"""Strategy validation toolkit: Monte Carlo permutation tests.

Implements the four-step development gauntlet from Timothy Masters'
"Permutation and Randomization Tests for Trading System Development"
(as popularized by neurotrader):

1. In-sample excellence       — bar-level returns, profit factor / Sharpe
2. In-sample permutation test — was the optimum found in patterns or noise?
3. Walk-forward test          — periodic re-optimization on unseen data
4. Walk-forward permutation test — could a worthless strategy have done this?

A strategy passes only with very low p-values on BOTH permutation tests
(in-sample < 1%; walk-forward ≤ 5% on one year, < 1% on two or more).
"""

from .gates import (
    PermutationTestResult,
    insample_permutation_test,
    walkforward_permutation_test,
)
from .metrics import position_returns, profit_factor, sharpe_ratio, signal_profit_factor
from .permutation import permute_bars
from .run_stats import validate_daily_r
from .walkforward import walk_forward_signal

__all__ = [
    "PermutationTestResult",
    "insample_permutation_test",
    "walkforward_permutation_test",
    "permute_bars",
    "position_returns",
    "profit_factor",
    "sharpe_ratio",
    "signal_profit_factor",
    "validate_daily_r",
    "walk_forward_signal",
]
