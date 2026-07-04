"""Parametrized base for the f02–f05 dominance-flip variant releases.

Four pre-registered, one-lever-each hypotheses about where the f01
capitulation-reversal baseline leaves edge on the table. Each was named and
frozen together (2026-06-13) BEFORE any was run, and all are judged by the
same funnel f01 uses: ``screen_2022_2026_sampled`` first (kill: sum R < 0 or
pooled sign-flip p > 0.5), full eval gauntlet for survivors only.

Every variant inherits f01's detection and execution unchanged and flips a
single dimension, mapped to one audit caveat (2026-06-13):

  f02  require_spy_uptrend  — macro trend filter (spec §10.1): only buy
       capitulation when SPY closed above its 200-day SMA. Attacks the
       falling-knife risk of a long-only buyer with no regime alignment.
  f03  warm_start           — seed indicators from prior 5m days so flips
       are tradable from the open (~9:35) instead of ~12:10. Attacks the
       tiny, afternoon-only opportunity set.
  f04  max_hold_bars        — N-bar time-decay abort (spec §8.3). Attacks
       dead "time-correction" trades that drift to the 15:55 exit.
  f05  target_atr_mult      — push the target past the mean by k·ATR.
       Attacks the inverted R:R of a flip-bar entry into a near-mean target.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.research.filters import min_avg_daily_volume, min_price
from trading.lab.strategies.dominance_flip_reversal.common import detect_dominance_flip
from trading.lab.strategies.dominance_flip_reversal.f01 import Release as F01Release


def spy_above_200sma(trade_date: date, sma_period: int = 200) -> bool:
    """Macro trend gate (spec §10.1): True when SPY's most recent daily
    close strictly before *trade_date* is above its ``sma_period``-day SMA.

    Conservative on missing data: fewer than ``sma_period`` daily bars → do
    not trade. Uses raw (unadjusted) daily bars, consistent with the rest of
    the lab; a trend gate is insensitive to the split-scale offset.
    """
    from trading.lab.data.market_data import fetch_daily_context

    # lookback_days is calendar days; ~1.6× covers the trading-day shortfall.
    daily = fetch_daily_context("SPY", trade_date, lookback_days=int(sma_period * 1.6))
    if daily is None or len(daily) < sma_period:
        return False
    close = daily["close"].astype(float).to_numpy()
    sma = close[-sma_period:].mean()
    return bool(close[-1] > sma)


class FlipVariant(F01Release):
    """f01 with single-lever hypothesis knobs (see module docstring)."""

    # ── Hypothesis knobs (overridden per release) ─────────────────────
    require_spy_uptrend: bool = False     # f02: SPY > 200-day SMA gate
    warm_start: bool = False              # f03: seed indicators from history
    warm_start_lookback_days: int = 2     # prior 5m days to prepend when warm
    max_hold_bars: int | None = None      # f04: N-bar time-decay abort
    target_atr_mult: float = 0.0          # f05: push target k·ATR past mean

    def regime_ok(self, context: StrategyContext) -> bool:
        if self.require_spy_uptrend:
            return spy_above_200sma(context.trade_date)
        return True

    def _detect_for(self, context: StrategyContext, ticker, bars):
        """Run detection, warm-starting from prior 5m days when enabled."""
        if not self.warm_start:
            return self._detect(bars)
        hist = context.historical_5m.get(ticker)
        if hist is None or hist.empty:
            return self._detect(bars)
        combined = pd.concat([hist, bars])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        flip_after = hist.index[-1]
        return detect_dominance_flip(
            combined,
            z_extreme=self.z_extreme,
            min_stretch_bars=self.min_stretch_bars,
            min_divergence_separation=self.min_divergence_separation,
            vol_climax_z=self.vol_climax_z,
            stop_atr_mult=self.stop_atr_mult,
            sma_period=self.sma_period,
            rsi_period=self.rsi_period,
            vol_period=self.vol_period,
            atr_period=self.atr_period,
            flip_after=flip_after,
        )

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        from trading.lab.core.time_utils import ny_dt

        if not self.regime_ok(context):
            return []
        latest_flip = ny_dt(context.trade_date, self.latest_flip_hour, self.latest_flip_minute)
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            daily = context.daily.get(ticker)
            if not min_price(daily, self.min_last_close, context.trade_date):
                continue
            if not min_avg_daily_volume(daily, self.min_avg_volume, 14, context.trade_date):
                continue
            setup = self._detect_for(context, ticker, bars)
            if setup is None:
                continue
            if setup["flip_time"] > latest_flip:
                continue
            rows.append(
                Candidate(
                    ticker=ticker,
                    score=abs(setup["z_min"]),
                    reason="z_flip_back_after_stretch_with_divergence",
                    features=setup,
                )
            )
        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        signal = super().build_signal(context, candidate)
        if signal is None:
            return None
        # f05: push the target k·ATR past the mean (raises target only, so the
        # stop < entry < target ordering f01 already enforced still holds).
        if self.target_atr_mult > 0.0:
            f = candidate.features
            atr = float(f.get("atr_5m", 0.0))
            new_target = float(f["sma_at_flip"]) + self.target_atr_mult * atr
            if new_target > signal.entry_trigger:
                signal.target_price = new_target
                signal.metadata["target_price"] = new_target
                signal.metadata["target_atr_mult"] = self.target_atr_mult
        # f04: N-bar time-decay abort handled by the simulator via metadata.
        if self.max_hold_bars is not None:
            signal.metadata["max_hold_bars"] = int(self.max_hold_bars)
        return signal
