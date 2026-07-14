"""b02 — Momentum Burst + breakout-low stop (one-lever add over b01).

Strategy identity:
    Name: Momentum Burst
    Alias: momentum_burst
    Letter: b
    Release: b02

Research thesis:
    b01 shipped the Stage-0 baseline: the bare StockBee 4% range-expansion rule
    with a PURE TIME EXIT (no per-name stop). Its honest-universe 2024 read was
    thin — passed the funnel sum-R gate but PF ~0.99 / ~-4 bps/trade, dragged by
    an uncapped left tail (a single -88% loser). The sandbox strategy always
    carried a stop = breakout-day low; b01 deliberately omitted it so the number
    was the raw edge. b02 adds EXACTLY that one lever back — the breakout-day-low
    stop — and changes nothing else, so the A/B vs b01 isolates "does capping the
    left tail turn the flat %-economics positive?" This is the single-lever
    discipline of the EXPLORATION_PLAYBOOK: one change per release, clean
    attribution.

Data requirements:
    - Daily SPLIT-ADJUSTED bars, ~420-day lookback (200-day SMA + prior bars).
    - SPY daily (requires_spy_daily=True, 420-day window) for the regime gate:
      SPY 10-EMA > 20-EMA AND SPY close > 200-day SMA (the "bear filter").

Entry rules (IDENTICAL to b01, evaluated every rebalance = every trading close):
    - Global regime gate: enter ONLY when SPY 10>20 EMA and SPY > 200-day SMA.
    - Eligible name (all through the rebalance close, NaN-safe):
        close >= $5, 20-day dollar-volume >= $5M,
        range-expansion:  close/prev_close - 1 >= 0.04,
        volume up vs prior day AND >= 100k shares,
        prior day calm:   prev-day return <= +2% (no chase),
        strong close:     (close-low)/(high-low) >= 0.5,
        uptrend:          close > 20-SMA and close > 50-SMA.
    - Rank eligible names by breakout magnitude (that day's % gain); take top_n.
    - Enter at the rebalance-date (breakout-day) close.

Exit / risk rules (THE ONLY CHANGE vs b01):
    - use_close_stop = True. Exit early on the first daily CLOSE at or below the
      breakout-day low (signal.stop_price), else the hold_days (5) time exit.
    - IMPORTANT modeling note: the lab swing engine's stop is CLOSE-based (it
      triggers when a daily *close* breaches the stop, per
      core.execution.simulate_daily_hold), NOT the sandbox's intraday-low touch.
      A close-stop is strictly MORE LENIENT — it lets a name wick below the
      breakout low intraday and recover by the close without stopping out — so
      b02 will trigger fewer, later exits than the sandbox proxy. Expect a
      smaller left-tail cut than the sandbox's intraday stop showed; that gap is
      the honest cost of daily-bar execution, documented here rather than hidden.

Known limitations:
    - The day-3 no-progress exit (part of the sandbox recipe) is NOT expressible
      through the current SwingStrategyRelease contract: the engine consumes only
      hold_days + a single close-stop price, with no per-day exit hook. Adding it
      would require a shared-engine change (an exit callback), which would touch
      every swing release and is out of scope for a one-lever release. Deferred
      to b03, and only after an engine hook exists — bundling it here would muddy
      the stop's attribution.
    - Stop is close-based, not intraday (see Exit rules) — a known softness.
    - Enters at breakout-day close vs the sandbox's next-open proxy. Ranking by
      raw % gain is a first cut; discretionary chart quality is not modeled.
    - Sandbox edge was survivorship-lifted; this lab PIT-universe run is honest.

Next intended releases:
    - b03: day-3 no-progress exit (needs a core.execution exit-hook first) and/or
      an intraday-low stop; then liquidity / price-tier sensitivity.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from trading.lab.strategies.base import SwingStrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext

RISK_FRAC_FALLBACK = 0.08     # nominal stop if breakout-day low is unusable


def _ema(s: pd.Series, n: int) -> float:
    return float(s.ewm(span=n, min_periods=n, adjust=False).mean().iloc[-1])


def _regime_bull(spy: pd.DataFrame) -> bool:
    """SPY 10-EMA > 20-EMA AND SPY close > 200-day SMA (through rebalance close)."""
    if spy is None or "close" not in getattr(spy, "columns", []) or len(spy) < 205:
        return False
    c = spy["close"].astype(float)
    ema10, ema20 = _ema(c, 10), _ema(c, 20)
    sma200 = float(c.to_numpy()[-200:].mean())
    close = float(c.iloc[-1])
    if not np.isfinite([ema10, ema20, sma200, close]).all():
        return False
    return (ema10 > ema20) and (close > sma200)


class Release(SwingStrategyRelease):
    release_id = "b02"
    strategy_letter = "b"
    strategy_alias = "momentum_burst"
    strategy_name = "Momentum Burst (4% range-expansion) + breakout-low stop"
    description = ("b01 momentum burst with the breakout-day-low close-stop added back "
                   "(use_close_stop=True): buy a >=4% range-expansion day (rising volume, "
                   "strong close, prior-day calm, uptrend) in a bull regime (SPY 10>20 EMA & "
                   ">200d SMA); rank by magnitude, top-N equal weight, 5-day hold, exit early "
                   "on the first close at/below the breakout low. One-lever add over b01.")

    daily_lookback_days = 420
    spy_daily_lookback_days = 420
    requires_spy_daily = True
    hold_days = 5
    rebalance_cadence_days = 1       # event-driven: evaluate every trading day
    top_n = 25                       # strongest breakouts per day (capacity cap)
    use_close_stop = True            # THE lever: breakout-low close-stop (vs b01)

    min_price = 5.0
    min_dollar_vol = 5_000_000.0
    up_thresh = 1.04
    min_vol = 100_000.0
    prior_calm_max = 0.02
    close_pos_min = 0.5

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        if not _regime_bull(context.spy_daily):
            return []                # fail CLOSED — no longs outside the bull regime
        thresh = self.up_thresh - 1.0
        rows: list[Candidate] = []
        for ticker, daily in context.daily.items():
            if daily is None or len(daily) < 205 or "volume" not in daily.columns:
                continue
            cv = daily["close"].to_numpy()
            close_d = float(cv[-1]); prev_c = float(cv[-2])
            if prev_c <= 0:
                continue
            # cheapest gate first (range expansion) → most names exit here
            gain = close_d / prev_c - 1.0
            if not (gain >= thresh) or close_d < self.min_price:
                continue
            vv = daily["volume"].to_numpy()
            vlast = float(vv[-1])
            if not (vlast > float(vv[-2]) and vlast >= self.min_vol):
                continue
            if not (prev_c / float(cv[-3]) - 1.0 <= self.prior_calm_max):   # prior day calm
                continue
            lv = daily["low"].to_numpy(); hv = daily["high"].to_numpy()
            low_d = float(lv[-1]); rng = float(hv[-1]) - low_d
            close_pos = (close_d - low_d) / rng if rng > 0 else 0.0
            if not (close_pos >= self.close_pos_min):
                continue
            # tail-slice means (identical to rolling().iloc[-1], far cheaper)
            if float((cv[-20:] * vv[-20:]).mean()) < self.min_dollar_vol:
                continue
            if not (close_d > cv[-20:].mean() and close_d > cv[-50:].mean()):
                continue
            rows.append(Candidate(
                ticker=ticker, score=gain, reason="momentum_burst_4pct",
                features={"gain": gain, "close": close_d, "low": low_d, "close_pos": close_pos},
            ))
        rows.sort(key=lambda r: r.score or 0.0, reverse=True)
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
        low_d = float(candidate.features.get("low", close_d * (1.0 - RISK_FRAC_FALLBACK)))
        stop = low_d if 0 < low_d < close_d else close_d * (1.0 - RISK_FRAC_FALLBACK)
        ts = daily.index[-1]
        return Signal(
            ticker=candidate.ticker,
            setup_type="momentum_burst",
            signal_time=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
            entry_trigger=close_d,
            stop_price=stop,
            target_price=None,
            metadata={**candidate.features, "release": self.release_id},
        )
