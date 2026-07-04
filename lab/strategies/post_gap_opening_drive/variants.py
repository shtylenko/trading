"""Parametrized base for the d02–d04 post-gap-opening-drive variants.

Three pre-registered, one-lever-each improvements over the d01 gap-and-go
baseline (gap > 1% above prior high, green first 5m candle, breakout of the
first-candle high, stop at the first-candle low = 1R, 1R target, 11:30 exit).
Named and frozen together (2026-06-13) BEFORE any was run, judged by the same
funnel the o/f families use: ``screen_2022_2026_sampled`` first (kill: sum
R < 0 or pooled sign-flip p > 0.5), full eval for survivors only.

Each maps to a documented d01 limitation (see d01.py "Next intended"):

  d02  min_rv       — opening relative-volume "in play" filter. d01 fires on
       EVERY 1% gap-up; this keeps only climactic-volume gaps (RV >= 2), the
       core stocks-in-play quality gate d01 omits.
  d03  uncapped     — remove the 1R target and let winners run to the cutoff.
       The gap-and-go thesis is tail-driven; a symmetric 1R cap structurally
       clips the right tail that is supposed to pay for the losers.
  d04  full session — hold to 15:55 instead of flattening at 11:30, so a drive
       that keeps trending past late morning is not cut short.
"""

from __future__ import annotations

import pandas as pd

from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.research.filters import (
    daily_atr_14,
    first_regular_5m_candle,
    has_split_like_jump,
)
from trading.lab.strategies.post_gap_opening_drive.d01 import Release as D01Release


def opening_relative_volume(hist_5m: pd.DataFrame | None, first_volume: float,
                            min_hist_days: int = 10) -> float | None:
    """First-bar volume vs the historical mean opening-bar volume.

    Mirrors the stocks-in-play RV definition: average the 09:30–09:35 bar's
    volume across prior sessions (one bar per day) and divide today's opening
    volume by it. Returns None when history is insufficient.
    """
    if hist_5m is None or hist_5m.empty:
        return None
    h = hist_5m.tz_convert("America/New_York") if hist_5m.index.tz is not None else hist_5m
    opening = h.between_time("09:30", "09:35", inclusive="both")
    opening = opening.groupby(opening.index.date).first()
    if len(opening) < min_hist_days:
        return None
    mean_open_vol = float(opening["volume"].mean())
    if mean_open_vol <= 0:
        return None
    return first_volume / mean_open_vol


class DriveVariant(D01Release):
    """d01 with single-lever hypothesis knobs (see module docstring)."""

    # ── Hypothesis knobs (overridden per release) ─────────────────────
    min_rv: float | None = None              # d02: opening relative-volume gate
    uncapped: bool = False                   # d03: drop the 1R target, ride to cutoff
    exit_hour: int = 11                      # d04: hold-window end (NY)
    exit_minute: int = 30
    split_guard: bool = False                # d05: drop raw-price split/glitch days
    require_above_vwap: bool = False          # d06: only fill breakouts above session VWAP
    max_gap_pct: float | None = None         # d07: reject exhaustion gaps above this
    min_rel_spy_gap: float | None = None     # d08: gap >= this * SPY's gap %
    max_candle_atr_frac: float | None = None # d09: first-candle range <= frac*ATR14
    min_candle_atr_frac: float | None = None # d10: first-candle range >= frac*ATR14
    max_first_close_pos: float | None = None # d13/d14: reject first bars that closed
                                             # at/near their high (close-position decile)

    def _spy_gap_pct(self, context: StrategyContext) -> float | None:
        """SPY's own gap % (open vs prior daily high), for relative strength."""
        spy5, spyd = context.spy_5m, context.spy_daily
        if spy5 is None or spyd is None or spyd.empty:
            return None
        first = first_regular_5m_candle(spy5)
        if first is None:
            return None
        prior = spyd[spyd.index.date < context.trade_date]
        if prior.empty:
            return None
        ph = float(prior.iloc[-1]["high"])
        if ph <= 0:
            return None
        return (float(first["open"]) - ph) / ph * 100.0

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        cands = super().build_candidates(context)
        spy_gap = self._spy_gap_pct(context) if self.min_rel_spy_gap is not None else None
        kept: list[Candidate] = []
        for c in cands:
            # Work on (and persist) a private copy so the gate-derived keys
            # below (rv, spy_gap_pct, candle_atr_frac) never mutate a features
            # dict that some other holder of the pre-filter candidate might
            # still reference. Reassigning keeps the added keys on the candidate.
            f = dict(c.features)
            c.features = f
            gap = float(f.get("gap_pct_vs_prior_high", 0.0))
            # d05 — raw-price split / data-glitch guard (>40% jump in the
            # trailing window or open-vs-prior-close). Expected ~no-op control.
            if self.split_guard and has_split_like_jump(
                context.daily.get(c.ticker), context.trade_date,
                open_price=float(f.get("first_open", 0.0)),
            ):
                continue
            # d02 — opening relative-volume gate
            if self.min_rv is not None:
                rv = opening_relative_volume(
                    context.historical_5m.get(c.ticker), float(f.get("first_volume", 0.0))
                )
                if rv is None or rv < self.min_rv:
                    continue
                f["rv"] = rv
            # d07 — exhaustion-gap ceiling
            if self.max_gap_pct is not None and gap > self.max_gap_pct:
                continue
            # d08 — relative strength vs SPY's gap (conservative: skip if no SPY data)
            if self.min_rel_spy_gap is not None:
                if spy_gap is None or gap < self.min_rel_spy_gap * spy_gap:
                    continue
                f["spy_gap_pct"] = spy_gap
            # d09 / d10 — first-candle range as a fraction of daily ATR14
            if self.max_candle_atr_frac is not None or self.min_candle_atr_frac is not None:
                atr = daily_atr_14(context.daily.get(c.ticker), 14, context.trade_date)
                rng = float(f.get("first_high", 0.0)) - float(f.get("first_low", 0.0))
                if atr is None or atr <= 0:
                    continue
                frac = rng / atr
                if self.max_candle_atr_frac is not None and frac > self.max_candle_atr_frac:
                    continue
                if self.min_candle_atr_frac is not None and frac < self.min_candle_atr_frac:
                    continue
                f["candle_atr_frac"] = frac
            # d13 / d14 — first-bar close position within its own range. A bar
            # that closed at its high (pos -> 1.0) is exhaustion: the breakout
            # entry above it chases an already-extended move. We keep breakouts
            # whose first bar closed lower in range but still reclaimed the high
            # to trigger (real demand). All inputs are known at 09:35, pre-entry.
            if self.max_first_close_pos is not None:
                fh = float(f.get("first_high", 0.0))
                fl = float(f.get("first_low", 0.0))
                rng = fh - fl
                if rng > 0:  # degenerate zero-range bars are not the target — keep
                    close_pos = (float(f.get("first_close", 0.0)) - fl) / rng
                    f["first_close_pos"] = close_pos
                    if close_pos > self.max_first_close_pos:
                        continue
            kept.append(c)
        for idx, c in enumerate(kept, start=1):  # preserve gap% order from super
            c.rank = idx
        return kept

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        signal = super().build_signal(context, candidate)
        if signal is None:
            return None
        if self.uncapped:
            signal.target_price = None
            signal.metadata["target_price"] = None
        if self.require_above_vwap:
            signal.metadata["require_above_vwap"] = True
        return signal

    def exit_cutoff(self, context: StrategyContext):
        return ny_dt(context.trade_date, self.exit_hour, self.exit_minute)
