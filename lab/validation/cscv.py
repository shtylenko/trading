"""Combinatorially-Symmetric Cross-Validation (CSCV) → Probability of Backtest
Overfitting (PBO), after López de Prado (2014).

The feature search ranks N candidate filter-combinations by an in-sample
objective and picks the best. With N large, the winner can be in-sample noise.
PBO answers: *across many symmetric IS/OOS splits of the timeline, how often does
the IS-best combo land in the bottom half out-of-sample?* PBO ≳ 0.5 means the
selection procedure is overfitting and NO combo it picks is trustworthy.

Mechanics (the standard CSCV construction):
  - Slice the pooled timeline into ``S`` equal, contiguous blocks (S even).
  - Enumerate every way to choose S/2 blocks as IS (the rest OOS) — C(S, S/2)
    splits, symmetric by construction (each IS half has a complementary OOS half).
  - For each split: rank all combos by IS performance, take the top one, find its
    OOS rank; map its OOS relative rank ``w ∈ (0,1)`` to a logit
    ``λ = ln(w/(1-w))``. PBO = fraction of splits with ``λ < 0`` (IS-best below
    the OOS median).

Input is a **performance matrix** M of shape (T, N): T time-slices (rows) ×
N combos (cols), each cell the combo's per-slice objective contribution (here:
summed realized R on that slice). Block performance is the mean over the block's
rows, so IS/OOS scores are averages of per-slice performance — scale-free in T.
Purely numeric; no project deps, so it unit-tests in isolation.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np


def block_bounds(n_rows: int, n_blocks: int) -> list[tuple[int, int]]:
    """Contiguous, near-equal [start, end) row ranges for ``n_blocks`` blocks."""
    edges = np.linspace(0, n_rows, n_blocks + 1).astype(int)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(n_blocks)]


def pbo_from_matrix(
    perf: np.ndarray,
    n_blocks: int = 16,
    higher_is_better: bool = True,
    embargo: int = 1,
) -> dict:
    """PBO via CSCV on a (T_slices × N_combos) performance matrix.

    ``embargo`` trims that many rows from BOTH edges of every block before
    averaging, so adjacent blocks never share an immediately-neighbouring
    observation — a symmetric generalization of the López de Prado embargo that
    severs the boundary autocorrelation regardless of which side a block lands on
    in a given IS/OOS split. (Set 0 to disable.) With daily data, embargo=1 drops
    one trading day per block edge.

    Returns ``pbo`` plus diagnostics: the logit distribution, the count of
    splits evaluated, and the fraction of splits where the IS-best is also the
    OOS-best (a sanity counterpoint to PBO).
    """
    perf = np.asarray(perf, dtype=float)
    if perf.ndim != 2:
        raise ValueError("perf must be 2-D (time-slices × combos)")
    T, N = perf.shape
    if n_blocks % 2 != 0:
        raise ValueError("n_blocks must be even")
    if T < n_blocks or N < 2:
        return {"pbo": float("nan"), "n_splits": 0, "logits": [],
                "is_best_also_oos_best_rate": float("nan"),
                "note": "insufficient rows or combos for CSCV"}

    bounds = block_bounds(T, n_blocks)

    def _block_mean(a: int, b: int) -> np.ndarray:
        lo, hi = a + embargo, b - embargo
        if hi <= lo:                      # block too thin for the embargo → use it whole
            lo, hi = a, b
        return perf[lo:hi].mean(axis=0)

    # Per-block mean performance for every combo: (n_blocks × N).
    block_perf = np.vstack([_block_mean(a, b) for a, b in bounds])
    sign = 1.0 if higher_is_better else -1.0

    half = n_blocks // 2
    all_idx = set(range(n_blocks))
    logits: list[float] = []
    is_best_also_oos_best = 0

    for is_blocks in combinations(range(n_blocks), half):
        oos_blocks = sorted(all_idx - set(is_blocks))
        is_score = sign * block_perf[list(is_blocks)].mean(axis=0)
        oos_score = sign * block_perf[oos_blocks].mean(axis=0)
        best = int(np.argmax(is_score))
        # OOS relative rank of the IS-best combo: w = rank/(N+1) in (0,1).
        # average-rank handling of ties via (#below + (#equal+1)/2).
        oos_best = oos_score[best]
        below = int(np.sum(oos_score < oos_best))
        equal = int(np.sum(oos_score == oos_best))
        rank = below + (equal + 1) / 2.0  # 1..N, fractional on ties
        w = rank / (N + 1.0)
        w = min(max(w, 1e-12), 1 - 1e-12)
        logits.append(float(np.log(w / (1.0 - w))))
        if int(np.argmax(oos_score)) == best:
            is_best_also_oos_best += 1

    logits_arr = np.array(logits)
    pbo = float(np.mean(logits_arr < 0.0))  # IS-best below OOS median
    return {
        "pbo": pbo,
        "n_splits": len(logits),
        "n_blocks": n_blocks,
        "logits": logits,
        "logit_mean": float(logits_arr.mean()),
        "is_best_also_oos_best_rate": is_best_also_oos_best / len(logits),
    }
