"""s01 — SMMA-Stop ATR Breakout P0 baseline.

Strategy identity:
    Name: SMMA-Stop ATR Breakout
    Alias: smma_atr_breakout
    Letter: s
    Release: s01

Research thesis:
    Faithful long-only adaptation of the "medium complexity" strategy Lisa
    Forex described as her best performer in the 50,865-strategy study
    (transcript_HYnXpdMQ9Wk). Her recipe — the only one with concrete,
    re-implementable mechanics in that video — is:

        - one trend indicator: a SMOOTHED moving average (SMMA / Wilder MA),
        - one volatility indicator: ATR, used both as a tradeability gate and
          as the multiplier that sizes the profit target and stop loss,
        - a STOP order placed relative to the SMMA value (you enter only once
          price breaks out through the smoothed trend line, never on a limit
          inside it),
        - a fixed ATR-multiple stop loss and ATR-multiple profit target,
        - an "exit after N bars" time-decay flush for positions that never
          resolve.

    She trades it symmetrically (long + short); strategy_lab is long-only, so
    s01 keeps only the long leg: when intraday price is ABOVE its SMMA (uptrend
    bias) and the name carries enough ATR to be worth trading, arm a buy-stop a
    fraction of an ATR above the SMMA and ride the breakout to an ATR-multiple
    target, an ATR-multiple stop, or an N-bar timeout — whichever comes first.

    This is a momentum/continuation setup and is intentionally orthogonal to the
    proposed m01 SMA mean-reversion family (which buys BELOW its average). It
    sits closest to the d-family gap-and-go but keys off a smoothed trend line
    plus an ATR breakout band rather than a prior-day gap.

Data requirements:
    - 5-minute regular-hours OHLCV bars for the trade date (always loaded).
    - Daily raw (unadjusted) bars for the ATR14 gate / stop / target scale and
      the $5 price floor (always loaded).
    - ``historical_5m`` (10 calendar days) to SEED the SMMA so the trend value
      at the open reflects a real smoothed average rather than a single bar.

Entry rules:
    - Latest daily close >= $5 (penny-stock floor, shared SIP convention).
    - Daily ATR14 >= $0.50 (enough range to clear costs; same floor m01/l01
      propose). ATR is in dollars, consistent with the raw daily bars.
    - SMMA(``smma_period``) of 5-minute closes, computed over prior-session
      history seeded through today's first regular bar, must sit BELOW that
      first bar's close (price above its smoothed trend = long bias).
    - Buy-stop trigger = SMMA + ``entry_atr_mult`` x ATR14, and the trigger
      must sit strictly ABOVE the first bar's close so the fill is a genuine
      forward breakout (a stop order, never an already-triggered level). If the
      breakout band is already below price, the move is extended — skip.
    - The simulator only fills on bars AFTER the opening bar (no look-ahead).

Exit and risk rules:
    - Stop loss  = entry_trigger − ``stop_atr_mult``   x ATR14.
    - Profit tgt = entry_trigger + ``target_atr_mult`` x ATR14.
      Planned R = stop_atr_mult x ATR14; reward:risk = target_mult / stop_mult.
    - Time-decay flush: ``max_hold_bars`` 5-minute bars after entry, any still
      -open position is flattened at that bar's open (the video's "exit after
      bars"). s01 declares no 1-minute data, so the simulator runs on 5m bars
      and one held bar == 5 real minutes.
    - Hard session cutoff at 15:55 NY as a backstop.

Known limitations:
    - SMMA is evaluated once, at the open, from seeded history; it is not
      re-walked bar-by-bar through the session, so the breakout band is fixed
      for the day rather than trailing the live SMMA. A later release can make
      the trigger track the rolling intraday SMMA.
    - No relative-volume / "in play" gate, no SPY-regime filter, no premarket
      context — deliberately omitted to keep the P0 honest and wide.
    - ATR is daily-derived (one figure per name per day); an intraday ATR would
      tighten the band but adds a 1m/5m volatility model not yet shared.
    - Long-only by construction: the short half of Lisa's symmetric strategy is
      dropped, so any genuine edge that lived on the short side is invisible.

Next intended releases:
    - s02: relative-volume "in play" gate (only break out on climactic volume).
    - s03: trail the trigger off the live rolling intraday SMMA each bar.
    - s04: sweep entry_atr_mult / stop / target / max_hold as pre-registered
      one-lever variants in variants.py before the screen funnel.
"""

from __future__ import annotations

import pandas as pd

from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.research.filters import (
    daily_atr_14,
    first_regular_5m_bar,
    min_price,
)
from trading.lab.strategies.base import StrategyRelease


def smoothed_ma(closes: pd.Series, period: int) -> float | None:
    """Wilder's smoothed moving average (SMMA), returning the latest value.

    Seeded with the simple mean of the first ``period`` closes, then advanced
    recursively: ``smma_i = (smma_{i-1} * (period - 1) + close_i) / period``.
    This is the same smoothing Wilder uses for ATR — a slower, less twitchy
    average than the EMA, which is what "SSMA"/SMMA refers to in the source
    video. Returns None when there are fewer than ``period`` closes.
    """
    vals = [float(c) for c in closes.tolist() if c == c]  # drop NaN
    if len(vals) < period or period <= 0:
        return None
    smma = sum(vals[:period]) / period
    for price in vals[period:]:
        smma = (smma * (period - 1) + price) / period
    return float(smma)


class Release(StrategyRelease):
    release_id = "s01"
    strategy_letter = "s"
    strategy_alias = "smma_atr_breakout"
    strategy_name = "SMMA-Stop ATR Breakout"
    description = (
        "Long-only SMMA stop-breakout: price above its smoothed MA, arm a "
        "buy-stop entry_atr_mult*ATR14 above the SMMA, ATR-multiple stop and "
        "target, flush after N bars (Lisa Forex medium-complexity recipe)."
    )

    # Seed the SMMA from prior sessions so the open-time trend value is real.
    historical_5m_lookback_days = 10

    # ── Parameters (frozen for s01; sweep them in s04/variants.py) ───────
    smma_period = 20          # SMMA length, in 5-minute bars
    min_price_dollars = 5.0   # penny-stock floor
    min_atr_dollars = 0.50    # tradeability gate (daily ATR14, dollars)
    entry_atr_mult = 0.25     # buy-stop sits this many ATRs above the SMMA
    stop_atr_mult = 1.0       # stop = entry − stop_atr_mult * ATR14  (= 1R)
    target_atr_mult = 2.0     # target = entry + target_atr_mult * ATR14 (2:1)
    max_hold_bars = 12        # exit-after-N-bars flush (12 * 5m ≈ 1 hour)

    def _smma_at_open(self, context: StrategyContext, ticker: str,
                      first_close: float) -> float | None:
        """SMMA of 5m closes through today's first regular bar (seeded)."""
        hist = context.historical_5m.get(ticker)
        hist_closes = (
            hist["close"] if hist is not None and not hist.empty
            and "close" in hist else pd.Series(dtype=float)
        )
        closes = pd.concat([hist_closes, pd.Series([first_close])], ignore_index=True)
        return smoothed_ma(closes, self.smma_period)

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            daily = context.daily.get(ticker)
            first_bar = first_regular_5m_bar(bars)
            if first_bar is None or daily is None or len(daily) < 2:
                continue
            if not min_price(daily, self.min_price_dollars, context.trade_date):
                continue
            atr = daily_atr_14(daily, 14, context.trade_date)
            if atr is None or atr < self.min_atr_dollars:
                continue
            _, first = first_bar
            first_close = float(first["close"])
            smma = self._smma_at_open(context, ticker, first_close)
            if smma is None or smma <= 0:
                continue
            # Long bias: price must be above its smoothed trend line.
            if first_close <= smma:
                continue
            trigger = smma + self.entry_atr_mult * atr
            # Must be a forward breakout: the buy-stop has to sit above current
            # price, otherwise the level is already triggered (move extended).
            if trigger <= first_close:
                continue
            # Score by how far price already leads its SMMA, in ATRs — a
            # crude trend-strength rank, richest leaders first.
            score = (first_close - smma) / atr
            rows.append(
                Candidate(
                    ticker=ticker,
                    score=score,
                    reason="price_above_smma_atr_breakout",
                    features={
                        "smma": smma,
                        "atr14": atr,
                        "first_close": first_close,
                        "entry_trigger": trigger,
                        "lead_atrs": score,
                    },
                )
            )
        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        bars = context.bars_5m.get(candidate.ticker)
        first_bar = first_regular_5m_bar(bars)
        if first_bar is None:
            return None
        first_ts, _ = first_bar
        f = candidate.features
        atr = float(f["atr14"])
        trigger = float(f["entry_trigger"])
        stop = trigger - self.stop_atr_mult * atr
        target = trigger + self.target_atr_mult * atr
        if trigger - stop <= 0:
            return None
        return Signal(
            ticker=candidate.ticker,
            setup_type="smma_atr_breakout",
            signal_time=first_ts.to_pydatetime() if hasattr(first_ts, "to_pydatetime") else first_ts,
            entry_trigger=trigger,
            stop_price=stop,
            target_price=target,
            metadata={
                **f,
                "release": self.release_id,
                "max_hold_bars": self.max_hold_bars,
            },
        )

    def exit_cutoff(self, context: StrategyContext):
        return ny_dt(context.trade_date, 15, 55)
