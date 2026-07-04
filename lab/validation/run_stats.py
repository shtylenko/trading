"""Statistical validation of a stored run's daily realized-R series.

Sign-flip permutation test, bootstrap confidence intervals, and tail
dependence on the daily R series of a backtest run. All vectorized numpy,
so the whole bundle runs in a few milliseconds for ~10k iterations over a
few hundred days — cheap enough to compute live inside a web request.

This is the SAME sign-flip gate used in the screen funnel (kill: sum R < 0
OR pooled p > 0.5). Shared by ``scripts/validate_run.py`` (CLI, supports
pooling several runs) and ``scripts/dashboard.py`` (per-run panel).
"""

from __future__ import annotations

import numpy as np

TRADING_DAYS_PER_YEAR = 252

# (date, realized_r) pairs, as returned by the trades query.
TradeRows = list


def daily_r_series(trades: TradeRows, n_days: int) -> np.ndarray:
    """Sum realized R per trade date, zero-padding no-trade days.

    Days that completed without any trade contribute 0 R but still count
    toward the series length, so the permutation null sees the real
    fraction of flat days.
    """
    by_day: dict = {}
    for d, r in trades:
        by_day[d] = by_day.get(d, 0.0) + float(r)
    vals = list(by_day.values())
    vals += [0.0] * max(0, n_days - len(vals))
    return np.asarray(vals, dtype=float)


def permutation_null(daily: np.ndarray, iters: int, rng) -> np.ndarray:
    """Null distribution of total R under random daily sign flips.

    Null hypothesis: the strategy has no directional edge, so each day's
    R magnitude is equally likely to have come out positive or negative.
    """
    signs = rng.choice([-1.0, 1.0], size=(iters, daily.size))
    return (signs * np.abs(daily)).sum(axis=1)


def permutation_pvalue(daily: np.ndarray, iters: int, rng) -> float:
    """One-sided sign-flip p-value: P(null total R >= observed).

    Uses the add-one (Davison & Hinkley) finite-sample correction
    ``(#exceed + 1) / (iters + 1)`` so a Monte-Carlo run with zero
    exceedances reports a small positive p-value rather than an
    impossible ``p = 0``.
    """
    observed = daily.sum()
    null = permutation_null(daily, iters, rng)
    return float((np.sum(null >= observed) + 1) / (iters + 1))


def bootstrap_ci(daily: np.ndarray, iters: int, rng, alpha: float = 0.05):
    """Bootstrap CIs for annualized R pace and daily R std."""
    idx = rng.integers(0, daily.size, size=(iters, daily.size))
    samples = daily[idx]
    pace = samples.mean(axis=1) * TRADING_DAYS_PER_YEAR
    sd = samples.std(axis=1, ddof=1)
    lo, hi = 100 * alpha / 2, 100 * (1 - alpha / 2)
    return (
        (float(np.percentile(pace, lo)), float(np.percentile(pace, hi))),
        (float(np.percentile(sd, lo)), float(np.percentile(sd, hi))),
    )


def tail_stats(trades: TradeRows, top_k: int = 5):
    """Total R, the top-k trades' R, their share of total, and total without them."""
    rs = np.asarray([float(r) for _, r in trades])
    total = rs.sum()
    top = np.sort(rs)[::-1][:top_k]
    without = total - top.sum()
    share = top.sum() / total if total != 0 else float("nan")
    return total, float(top.sum()), share, float(without)


def histogram(values: np.ndarray, bins: int = 40) -> dict:
    """Bin a 1-D array into {centers, counts} for a bar-chart histogram."""
    counts, edges = np.histogram(np.asarray(values, dtype=float), bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2.0
    return {
        "centers": [round(float(c), 4) for c in centers],
        "counts": [int(c) for c in counts],
        "bin_width": round(float(edges[1] - edges[0]), 6),
    }


def validate_daily_r(
    trades: TradeRows,
    n_days: int,
    iters: int = 10_000,
    top_k: int = 5,
    seed: int = 7,
    hist_bins: int = 40,
) -> dict:
    """Full sign-flip validation bundle for a (possibly pooled) trade series.

    Returns a JSON-ready dict with scalar stats plus the permutation null
    histogram and the observed total R, so a UI can draw the null
    distribution with the observed value marked.
    """
    rng = np.random.default_rng(seed)
    daily = daily_r_series(trades, n_days)
    observed = float(daily.sum())
    null = permutation_null(daily, iters, rng)
    # add-one finite-sample correction (see permutation_pvalue)
    p_value = float((np.sum(null >= observed) + 1) / (iters + 1))
    (pace_lo, pace_hi), (sd_lo, sd_hi) = bootstrap_ci(daily, iters, rng)
    total, top_sum, share, without = tail_stats(trades, top_k)

    return {
        "n_trades": len(trades),
        "n_days": int(daily.size),
        "observed_r": round(observed, 4),
        "annualized_pace_r": round(float(daily.mean() * TRADING_DAYS_PER_YEAR), 2),
        "daily_r_std": round(float(daily.std(ddof=1)) if daily.size > 1 else 0.0, 4),
        "p_value": p_value,
        "iters": iters,
        "pace_ci": [round(pace_lo, 2), round(pace_hi, 2)],
        "sd_ci": [round(sd_lo, 4), round(sd_hi, 4)],
        "top_k": top_k,
        "top_k_r": round(top_sum, 4),
        "top_k_share": None if not np.isfinite(share) else round(float(share), 4),
        "r_without_top_k": round(without, 4),
        "null_hist": histogram(null, hist_bins),
        "null_mean": round(float(null.mean()), 4),
    }
