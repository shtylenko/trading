"""x03 — Residual (Idiosyncratic) Momentum, multi-day swing.

Strategy identity:
    Name: Residual Momentum (CAPM)
    Alias: xsec_momentum
    Letter: x
    Release: x03

Research thesis:
    Plain 12-1 total-return momentum (x01) has unstable factor loadings — in a bull it
    morphs into a high-beta tilt (x01 book beta ≈ 1.4; its market-orthogonal alpha was
    insignificant, t≈+0.3). Residual momentum (Blitz, Huij & Martens 2011) ranks on the
    IDIOSYNCRATIC return: regress each name's daily returns on the market (CAPM, SPY) over
    the 11-month formation window and rank by the standardized residual information ratio
    mean(ε)/std(ε). This strips the beta ride IN the ranking. Pre-registered + tested
    in-sample (validation/multiday_x03_residmom_preregistration.md): vs x01 on 2017–2024
    it cut beta (1.45→1.08) and max drawdown (−36%→−23%) and raised Sharpe (0.81→0.89,
    DSR 0.99) — a RISK-improved version of the same edge (the market-orthogonal alpha is
    still modest/insignificant; x03 is better-engineered momentum, not a new alpha source).
    This release is the swing-engine cross-check of that offline result.

Data requirements:
    - Daily SPLIT-ADJUSTED bars (multi-day; see daily_adjustment), ~420-day lookback.
    - SPY daily (requires_spy_daily=True) — the market leg of the CAPM residual; the swing
      runner hydrates context.spy_daily on the same split-adjusted grid as the book bars.

Entry rules (P0, UNCONDITIONED):
    - Eligible: close ≥ $5 AND 20-day dollar-volume ≥ $10M (through the rebalance close).
    - Need ≥ 273 aligned daily returns (252 formation + 21 skip); names with less history
      (recent IPOs) are excluded.
    - Rank eligible names by resid_mom = mean(ε)/std(ε), ε = r_i − β·r_SPY over [d−252,d−21]
      (β = OLS slope); take the top ``top_n``. Enter at the rebalance-date close.

Exit / risk rules:
    - Hold ``hold_days`` (20) trading days, equal weight; pure time exit (no stop).
    - Nominal stop at ``RISK_FRAC`` below entry (realized_r scaling only; pnl_pct primary).

Known limitations:
    - CAPM single-factor only (FF3 / size-factor residual untested — some of x01's "beta"
      is small-cap tilt). 8yr in-sample is survivorship-lifted pre-2022. Long-only, no short.
    - Still ~0.95 correlated with x01 (it is beta-trimmed momentum, not orthogonal alpha).
    - Both sealed years (2025, 2026-H1) are spent → a clean OOS confirmation waits for a new
      holdout (~2027). This release is the in-sample engine cross-check, NOT a sealed test.

Next intended releases:
    - x04+: FF3 / size-factor residual; or x03 + modest vol-target sizing (the lower
      drawdown revives sizing, which was counterproductive on x01).
"""

from __future__ import annotations

import numpy as np

from trading.lab.strategies.base import SwingStrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext

RISK_FRAC = 0.10            # nominal stop distance (for realized_r scaling only)
FORM = 252                  # formation lookback (trading-day returns)
SKIP = 21                   # skip-month
MIN_RET = FORM + SKIP       # minimum aligned returns needed


def _resid_mom(close_i, close_spy) -> float | None:
    """Standardized CAPM-residual momentum mean(ε)/std(ε) over [d-252, d-21].

    ε = r_i − β·r_SPY (β = OLS slope on the formation window). Matches the offline
    scripts/multiday_residmom.py so the engine reproduces the pre-registered result.
    """
    import pandas as pd
    df = pd.concat([close_i.astype(float), close_spy.astype(float)], axis=1, join="inner").dropna()
    if len(df) < MIN_RET + 1:
        return None
    ri = df.iloc[:, 0].pct_change().values[1:]
    rs = df.iloc[:, 1].pct_change().values[1:]
    if len(ri) < MIN_RET:
        return None
    wi = ri[-MIN_RET:-SKIP]                 # 252 formation returns (skip last month)
    ws = rs[-MIN_RET:-SKIP]
    spd = ws - ws.mean()
    var_sp = float((spd * spd).sum())
    if var_sp <= 0:
        return None
    beta = float((wi * spd).sum() / var_sp)  # OLS slope (intercept cancels via demeaned spd)
    resid = wi - beta * ws
    sd = float(resid.std(ddof=1))
    if sd <= 0:
        return None
    return float(resid.mean() / sd)


class Release(SwingStrategyRelease):
    release_id = "x03"
    strategy_letter = "x"
    strategy_alias = "xsec_momentum"
    strategy_name = "Residual Momentum (CAPM)"
    description = ("CAPM-residual (idiosyncratic) momentum: rank the liquid universe by the "
                   "standardized residual info-ratio over the 11-month formation, long top-50 "
                   "equal-weight, monthly rebalance, 20-day hold. Beta-trimmed x01.")

    daily_lookback_days = 420
    hold_days = 20
    rebalance_cadence_days = 20
    top_n = 50
    use_close_stop = False
    requires_spy_daily = True            # market leg of the CAPM residual

    min_price = 5.0
    min_dollar_vol = 10_000_000.0

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        spy = context.spy_daily
        if spy is None or "close" not in getattr(spy, "columns", []) or len(spy) < MIN_RET + 1:
            return []                    # fail CLOSED — residual needs the market series
        spy_close = spy["close"]
        rows: list[Candidate] = []
        for ticker, daily in context.daily.items():
            if daily is None or len(daily) < MIN_RET + 1:
                continue
            if "volume" not in daily.columns:
                continue                 # liquidity is mandatory — fail CLOSED
            c = daily["close"].astype(float)
            v = daily["volume"].astype(float)
            close_d = float(c.iloc[-1])
            if not (close_d >= self.min_price):       # NaN-safe
                continue
            dvol = float((c * v).iloc[-20:].mean())
            if not (dvol >= self.min_dollar_vol):     # NaN-safe
                continue
            score = _resid_mom(c, spy_close)
            if score is None or score != score:       # None / NaN
                continue
            rows.append(Candidate(ticker=ticker, score=score,
                                  reason="xsec_residual_momentum",
                                  features={"resid_mom": score, "close": close_d}))
        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        for i, row in enumerate(rows, start=1):
            row.rank = i
        return rows

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        daily = context.daily.get(candidate.ticker)
        if daily is None or daily.empty:
            return None
        close_d = float(daily["close"].astype(float).iloc[-1])
        if close_d <= 0:
            return None
        ts = daily.index[-1]
        return Signal(
            ticker=candidate.ticker,
            setup_type="xsec_momentum",
            signal_time=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
            entry_trigger=close_d,
            stop_price=close_d * (1.0 - RISK_FRAC),
            target_price=None,
            metadata={**candidate.features, "release": self.release_id},
        )
