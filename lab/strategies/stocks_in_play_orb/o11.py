"""o11 — o07 volatility-regime gate, sourced from the hydrated SPY context.

Strategy identity:
    Name: Stocks-in-Play Opening Range Breakout
    Alias: stocks_in_play_orb
    Letter: o
    Release: o11

Why this release exists (audit L4, 2026-06-13):
    o07 gates on the same frozen rule — trade only when SPY's 14-day ATR% is
    above its ~1-year median — but computes it by calling ``fetch_daily_context``
    DIRECTLY from strategy code. That bypasses the StrategyContext contract:
    the runner's data hydration, ``--force-data``, and per-run data lineage all
    miss the SPY daily pull, and the release can't be tested without a live
    provider. o11 declares ``requires_spy_daily`` with a long lookback so the
    runner hydrates the SPY daily history, then reads ``context.spy_daily`` —
    no provider calls in release logic.

    The regime rule itself is bit-for-bit the o07 frozen rule (Wilder ATR(14),
    ATR% = ATR/close, current value vs the median of the trailing 252 valid
    values, conservative on thin data). Same data, same formula → o11 is "o07
    done within the contract", not a new hypothesis.

Entry / exit / sizing: inherited unchanged from the o04 SIP-ORB spec
    (SipOrbVariant): price > $5, ADV >= 1M, ATR > $0.50, RV >= 2.0 gate,
    5-minute OR, stop-entry on the break, 0.10·ATR stop, 1% risk / 4x cap,
    15:59 close, RV ranking (no ML).
"""

from __future__ import annotations

import numpy as np

from trading.lab.core.models import StrategyContext
from trading.lab.strategies.stocks_in_play_orb.variants import SipOrbVariant

# o07's frozen window: median over ~252 trading days; ~1.6× covers the
# trading-day-to-calendar-day shortfall so context.spy_daily holds enough bars.
_REGIME_LOOKBACK = 252


def _spy_atr_regime_hot_from_daily(daily, lookback_days: int = _REGIME_LOOKBACK) -> bool:
    """Frozen o07 rule, computed from an already-fetched SPY daily frame.

    Returns True when SPY's most recent 14-day Wilder ATR% (strictly before
    the trade date — the runner hydrates context.spy_daily with prior bars
    only) is above its median over the trailing ``lookback_days`` valid values.
    Conservative on missing data: too few bars → do not trade.
    """
    if daily is None or len(daily) < 60:
        return False
    h = daily["high"].astype(float).to_numpy()
    l = daily["low"].astype(float).to_numpy()
    c = daily["close"].astype(float).to_numpy()
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = np.full_like(tr, np.nan)
    atr[13] = tr[:14].mean()
    for i in range(14, len(tr)):
        atr[i] = (atr[i - 1] * 13 + tr[i]) / 14.0
    atr_pct = atr / c
    valid = atr_pct[~np.isnan(atr_pct)]
    if len(valid) < 30:
        return False
    window = valid[-lookback_days:]
    return bool(window[-1] > np.median(window))


class Release(SipOrbVariant):
    release_id = "o11"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "SIP ORB v3 — volatility-regime gated (context-sourced)"
    description = (
        "o07's frozen rule (trade only when SPY 14d ATR% is above its 1-year "
        "median) computed from the runner-hydrated context.spy_daily instead of "
        "a direct provider call (long only, RV-ranked, no ML)."
    )

    top_n = None
    min_rv = 2.0
    requires_spy_daily = True
    # ~1.6 × the 252-trading-day window so the hydrated frame has enough bars.
    spy_daily_lookback_days = int(_REGIME_LOOKBACK * 1.6)

    def regime_ok(self, context: StrategyContext) -> bool:
        return _spy_atr_regime_hot_from_daily(context.spy_daily)
