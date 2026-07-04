"""Deflated Sharpe Ratio (DSR) — selection-bias-adjusted significance.

After Bailey & López de Prado (2014). The feature search picks the best of N
candidate combos; the best-of-N Sharpe is inflated even when the true edge is
zero (the False Strategy Theorem). DSR is the probability that the chosen
strategy's observed Sharpe is *real* after accounting for: (a) how many
(effectively independent) strategies were tried, (b) the sample length, and
(c) non-normality (skew/kurtosis) of the returns. A search winner should clear a
high DSR (e.g. >= 0.95) before the sealed-OOS budget is spent on it.

Self-contained: standard-normal CDF via math.erf, inverse-CDF via the Acklam
rational approximation — no scipy dependency.
"""
from __future__ import annotations

import math

import numpy as np

_EULER_GAMMA = 0.5772156649015329


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's algorithm, |err| < 1.2e-9)."""
    if p <= 0.0:
        return float("-inf")
    if p >= 1.0:
        return float("inf")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def expected_max_sharpe(sr_variance: float, n_trials: float) -> float:
    """Expected maximum (per-period) Sharpe of N unskilled trials whose Sharpe
    estimates have variance ``sr_variance`` (extreme-value approximation)."""
    if n_trials < 2 or sr_variance <= 0:
        return 0.0
    g = _EULER_GAMMA
    z1 = _norm_ppf(1.0 - 1.0 / n_trials)
    z2 = _norm_ppf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(sr_variance) * ((1.0 - g) * z1 + g * z2)


def effective_n_trials(perf_matrix: np.ndarray) -> float:
    """Effective number of *independent* trials from the per-period return matrix
    (T periods × K combos), via the participation ratio of the correlation matrix:
    ``(Σλ)² / Σλ²``. = K when combos are orthogonal, → 1 when all identical. The
    raw count K would be a draconian, naive penalty (combos are highly correlated);
    this is the defensible effective count."""
    m = np.asarray(perf_matrix, dtype=float)
    if m.ndim != 2 or m.shape[1] < 2:
        return float(max(1, m.shape[1] if m.ndim == 2 else 1))
    # keep non-degenerate columns (a combo that never trades has zero variance)
    var = m.var(axis=0)
    m = m[:, var > 0]
    if m.shape[1] < 2:
        return float(max(1, m.shape[1]))
    c = np.corrcoef(m, rowvar=False)
    c = np.nan_to_num(c, nan=0.0)
    eig = np.linalg.eigvalsh(c)
    eig = eig[eig > 0]
    if eig.size == 0:
        return 1.0
    return float((eig.sum() ** 2) / (eig ** 2).sum())


def deflated_sharpe_ratio(daily_returns: np.ndarray, sr_variance: float,
                          n_trials: float) -> dict:
    """DSR for one strategy's per-period (daily) return series.

    ``sr_variance`` = variance of the per-period Sharpe estimates ACROSS the
    trials searched; ``n_trials`` = (effective) number of trials. Returns the DSR
    probability plus the pieces (observed Sharpe, the selection-adjusted hurdle,
    skew, kurtosis, n).
    """
    r = np.asarray(daily_returns, dtype=float)
    r = r[np.isfinite(r)]
    n = int(r.size)
    out = {"dsr": float("nan"), "sr_observed": 0.0, "sr_hurdle": 0.0,
           "n_obs": n, "skew": 0.0, "kurtosis": 3.0, "n_trials": n_trials}
    if n < 10:
        return out
    mean, sd = float(r.mean()), float(r.std(ddof=1))
    if sd <= 0:
        return out
    sr = mean / sd                          # per-period (daily) Sharpe
    m2 = float(((r - mean) ** 2).mean())
    m3 = float(((r - mean) ** 3).mean())
    m4 = float(((r - mean) ** 4).mean())
    skew = m3 / (m2 ** 1.5) if m2 > 0 else 0.0
    kurt = m4 / (m2 ** 2) if m2 > 0 else 3.0   # non-excess (normal = 3)
    sr_star = expected_max_sharpe(sr_variance, n_trials)
    denom = math.sqrt(max(1e-12, 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr))
    dsr = _norm_cdf((sr - sr_star) * math.sqrt(n - 1) / denom)
    out.update({"dsr": float(dsr), "sr_observed": sr, "sr_hurdle": sr_star,
                "skew": skew, "kurtosis": kurt})
    return out
