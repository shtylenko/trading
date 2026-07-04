"""x04 — Residual Momentum (CAPM), top-35 concentration variant.

Strategy identity:
    Name: Residual Momentum (CAPM) — concentrated
    Alias: xsec_momentum
    Letter: x
    Release: x04

    NOTE on the x04 number: six earlier x04 *candidates* (FIP, FF3-residual, ATR-exit, value,
    overlapping construction, quality/GP sleeve — see validation/multiday_x04_*_preregistration.md
    + backlog.md kill-table) were each pre-registered and KILLED before shipping, so the id was
    repeatedly freed. This concentration variant is the FIRST x04 candidate to survive to a
    shipped release, so it keeps the number (immutability binds only once shipped).

Research thesis:
    Identical signal and pipeline to x03 (CAPM-residual momentum, mean(ε)/std(ε) over the
    11-month formation, monthly rebalance, 20-day hold) — the ONLY lever changed is the book
    width: top_n 50 → 35. Motivation: an exploratory threshold study
    (scripts/multiday_residmom_absthresh.py) showed x03's relative top-50 carries a weak-score
    tail; trimming it modestly improves risk-adjusted return. The improvement is real but small
    and NOT robustly locatable:
      - %cash ≈ 0 at this width → it is genuine CONCENTRATION, not a 2022 cash-timing overlay.
      - An ABSOLUTE score cutoff was rejected: it is regime-fragile (score distributions drift,
        so a fixed cutoff swings the held count and pushes to cash in calm regimes) and the
        winning cutoff is cherry-picked. Relative top-N auto-normalizes — the right mechanism.
      - The concentration curve is NON-MONOTONIC and DISAGREES across windows (2022–24 favored
        ~top-15; 2009–16 favored ~top-35; BOTH dipped at top-10, and top-5 is a lottery-ticket
        artifact). The ONLY slice both windows agree on is a gentle trim to ~top-35 — hence 35.
    Pooled diagnostics at top-35 vs top-50: 2022–24 Sharpe 1.59→1.70; 2009–16 Sharpe
    1.18→1.23 (α-t 1.20→1.39). A marginal tweak (~0.1 Sharpe), pre-registered as a CHALLENGER
    to x03; it has NOT earned promotion (needs the forward-sealed 2026 read, ~2027).

Data requirements:
    - Identical to x03: daily SPLIT-ADJUSTED bars (~420d lookback) + SPY daily (CAPM market leg).

Entry rules (P0, UNCONDITIONED):
    - Identical to x03 except top_n = 35 (eligible: close ≥ $5 AND 20d $-vol ≥ $10M; need
      ≥ 273 aligned returns; rank by resid_mom = mean(ε)/std(ε), ε = r_i − β·r_SPY over
      [d−252, d−21]; long the top 35 equal-weight, enter at the rebalance-date close).

Exit / risk rules:
    - Identical to x03: hold 20 trading days, equal weight, pure time exit; nominal stop at
      RISK_FRAC below entry (realized_r scaling only).

Known limitations:
    - The in-sample edge over x03 is small (~0.1 Sharpe) and the optimal width is regime-
      unstable; 35 is the robust-agreed value, not a true optimum. Fewer names = slightly
      higher idiosyncratic variance / marginally deeper drawdowns in some windows.
    - Inherits every x03 limitation: CAPM single-factor, survivorship-lifted pre-2022,
      long-only, ~0.95 correlated with x01/x03 (beta-trimmed momentum, not orthogonal alpha).
    - Both sealed years (2025, 2026-H1) are spent → clean OOS confirmation waits for ~2027.

Next intended releases:
    - none planned; x04 is a single-lever challenger to x03. If the forward-sealed read does
      not separate them, x03 (wider, more diversified) is the default keeper.
"""

from __future__ import annotations

from trading.lab.strategies.xsec_momentum.x03 import Release as _X03Release


class Release(_X03Release):
    release_id = "x04"
    strategy_name = "Residual Momentum (CAPM) — concentrated"
    description = ("CAPM-residual (idiosyncratic) momentum, concentrated top-35 variant of x03: "
                   "rank the liquid universe by the standardized residual info-ratio over the "
                   "11-month formation, long top-35 equal-weight, monthly rebalance, 20-day "
                   "hold. Single-lever challenger to x03 (top_n 50→35).")

    top_n = 35
