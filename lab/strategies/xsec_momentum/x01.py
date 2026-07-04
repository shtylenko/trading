"""x01 — Cross-Sectional Momentum (12-1), multi-day swing P0.

Strategy identity:
    Name: Cross-Sectional Momentum
    Alias: xsec_momentum
    Letter: x
    Release: x01

Research thesis:
    The classic 12-1 cross-sectional momentum factor: rank the liquid universe by
    the 12-month return skipping the most recent month (close[d-21]/close[d-252]−1),
    hold the top-``top_n`` names equal-weight for ``hold_days`` trading days, rebalance
    monthly. This is the project's FIRST end-to-end validated edge — confirmed
    in-sample 2017–2024 (DSR 0.997, pooled non-overlapping t +2.61, 6/8 LOO years) and
    on the sealed-OOS 2025 (PASS: per-period net +3.98%, Sharpe +1.08, cross-sectional
    premium +2.78%) in the offline harness (validation/multiday_momentum_findings.md).
    x01 is the production engine release for the Stage-6 cross-check, run by the
    additive swing runner (runner/swing_pipeline.py) — the intraday engine is unchanged.

Data requirements:
    - Daily SPLIT-ADJUSTED bars; ~420-calendar-day lookback for the 252-day signal.
      (Multi-day holds can straddle a split and splits inside the lookback corrupt the
      rank — the raw/unadjusted convention is correct only for the intraday engine,
      whose same-day trades never span a split. Set via ``daily_adjustment="split"``.)
    - No intraday/extended/SPY data. The swing runner hydrates context.daily THROUGH
      the rebalance date (inclusive — the close is the decision/entry point).

Entry rules (P0, UNCONDITIONED — the conditioning grid was shown to be noise):
    - Eligible: close ≥ $5 AND 20-day dollar-volume ≥ $10M (computed through the
      rebalance close).
    - Rank eligible names by mom_12_1; take the top ``top_n``.
    - Enter at the rebalance-date close.

Exit / risk rules:
    - Hold ``hold_days`` (20) trading days, equal weight; pure time exit (no stop).
    - Nominal stop at ``RISK_FRAC`` below entry, used ONLY to scale realized_r — swing
      R is secondary; pnl_pct (the close-to-close return) is the primary metric and the
      one the offline ledger reports.

Known limitations:
    - Long-only (no short leg); modest magnitude (~1.0 Sharpe, survivorship-lifted
      pre-2022); intrinsic momentum-crash risk (2021–22). Independent-trade sim
      overstates a correlated book → owes a portfolio/capacity review before capital.

Next intended releases:
    - x02+: only after the 2026 sealed 2nd-confirmation (data-gated ~early 2027).
"""

from __future__ import annotations

from trading.lab.strategies.base import SwingStrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt

RISK_FRAC = 0.10   # nominal stop distance (for realized_r scaling only)


class Release(SwingStrategyRelease):
    release_id = "x01"
    strategy_letter = "x"
    strategy_alias = "xsec_momentum"
    strategy_name = "Cross-Sectional Momentum (12-1)"
    description = ("12-1 cross-sectional momentum: long the top-50 liquid names by "
                   "12-month-minus-1 return, monthly rebalance, 20-day equal-weight hold.")

    daily_lookback_days = 420
    hold_days = 20
    rebalance_cadence_days = 20
    top_n = 50
    use_close_stop = False

    min_price = 5.0
    min_dollar_vol = 10_000_000.0

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        rows: list[Candidate] = []
        for ticker, daily in context.daily.items():
            if daily is None or len(daily) < 253:
                continue
            if "volume" not in daily.columns:
                continue                       # liquidity is mandatory — fail CLOSED
            c = daily["close"].astype(float)
            v = daily["volume"].astype(float)
            close_d = float(c.iloc[-1])
            if not (close_d >= self.min_price):  # NaN-safe (NaN fails)
                continue
            dvol = float((c * v).iloc[-20:].mean())
            if not (dvol >= self.min_dollar_vol):  # NaN-safe (missing/NaN volume fails)
                continue
            mom = float(c.iloc[-22] / c.iloc[-253] - 1.0)   # close[d-21]/close[d-252]-1
            if mom != mom:  # NaN
                continue
            rows.append(Candidate(ticker=ticker, score=mom,
                                  reason="xsec_momentum_12_1",
                                  features={"mom_12_1": mom, "close": close_d}))
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
            stop_price=close_d * (1.0 - RISK_FRAC),   # nominal, R-scaling only
            target_price=None,
            metadata={**candidate.features, "release": self.release_id},
        )
