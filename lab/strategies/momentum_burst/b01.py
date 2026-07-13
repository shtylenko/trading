"""b01 — Momentum Burst (StockBee 4% range-expansion), multi-day swing baseline.

Strategy identity:
    Name: Momentum Burst
    Alias: momentum_burst
    Letter: b
    Release: b01

Research thesis:
    Pradeep Bonde's (StockBee) core claim: liquid stocks move in short 3-5 day
    momentum bursts kicked off by a range-expansion day (>=4% up on rising
    volume, closing strong), preceded by a calm/non-extended day (no chase), in
    an uptrend. Enter the burst, hold ~5 sessions, exit into the fade. Sandbox
    testing (trading/strategytester) found the truncated <=3d version had no
    day-clustered significance, but at a 5-day hold it reached day-clustered
    t=2.86 and passed an out-of-sample split + parameter-robustness + cost
    stress; adding a bull-AND-above-200d-SMA index regime filter cut the 2022
    bear loss ~2/3 (day-t 2.99). This release is the honest-universe engine
    cross-check of that sandbox result — Stage 0 (baseline/triage) of the
    EXPLORATION_PLAYBOOK: bare rule, pure time exit, no per-name stop, so the
    number is the raw edge before any tuning.

Data requirements:
    - Daily SPLIT-ADJUSTED bars, ~420-day lookback (200-day SMA + prior bars).
    - SPY daily (requires_spy_daily=True, 420-day window) for the regime gate:
      SPY 10-EMA > 20-EMA AND SPY close > 200-day SMA (the "bear filter").

Entry rules (evaluated at every rebalance = every trading-day close):
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

Exit / risk rules:
    - Hold hold_days (5) trading days, equal weight; PURE TIME EXIT (Stage-0
      baseline — no intraday stop). Nominal stop = breakout-day low, used only
      to scale realized_r; pnl_pct is primary.

Known limitations:
    - Stage-0 baseline: no per-name stop (b02 will add the breakout-low stop +
      the day-3 no-progress exit from the sandbox; a stop can only cap the left
      tail). Enters at breakout-day close vs the sandbox's next-open proxy.
    - Ranking by raw % gain is a first cut; StockBee's discretionary chart
      quality is not modeled. Liquidity floor ($5 / $5M) is deliberately modest.
    - Sandbox edge was survivorship-lifted (its panel was ~all survivors); this
      run on the lab PIT universe is the first honest-universe read.

Next intended releases:
    - b02: add breakout-low stop + day-3 no-progress exit (use_close_stop path).
    - b03: liquidity / price-tier sensitivity; ranking on relative volume.
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
    release_id = "b01"
    strategy_letter = "b"
    strategy_alias = "momentum_burst"
    strategy_name = "Momentum Burst (4% range-expansion)"
    description = ("StockBee momentum burst: buy a >=4% range-expansion day (rising volume, "
                   "strong close, prior-day calm, uptrend) in a bull regime (SPY 10>20 EMA & "
                   ">200d SMA); rank the day's breakouts by magnitude, top-N equal weight, "
                   "5-day hold, pure time exit. Stage-0 honest-universe baseline.")

    daily_lookback_days = 420
    spy_daily_lookback_days = 420
    requires_spy_daily = True
    hold_days = 5
    rebalance_cadence_days = 1       # event-driven: evaluate every trading day
    top_n = 25                       # strongest breakouts per day (capacity cap)
    use_close_stop = False           # pure time exit (baseline)

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
