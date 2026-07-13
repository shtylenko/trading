"""#01 Momentum Burst — StockBee/Qullamaggie (daily).

4%+ range-expansion day on rising volume, closing near the high, NOT already
up strongly the day before (no chase), in an uptrend, with the index bullish
(situational awareness). Enter next open, stop = breakout-day low, ride to the
time stop. Native burst is 3-5 days; validated best at a ~5-session hold.

`make_signals(**params)` exposes the thresholds so robustness can be checked
without editing the module; `signals` is the default (documented) config.
"""

from __future__ import annotations

import numpy as np

from trading.strategytester.common.engine import Signal
from trading.strategytester.common.signal_utils import aligned, dates

NAME = "momentum_burst"
HORIZON = "daily"
MAX_HOLD = 5          # native burst window (validated); was 3 under the hard mandate
COST_BPS = 5.0

DEFAULTS = dict(
    up_thresh=1.04,        # breakout-day range expansion
    vol_gt_prior=True,     # volume up vs prior day
    min_vol=100_000,       # liquidity floor (shares)
    prior_calm_max=0.02,   # prior day return <= this (no chase)
    close_pos_min=0.5,     # close in upper half of the day
    require_regime=True,   # apply the index regime filter
    regime_col="reg_bull_200",  # SPY 10>20 EMA AND SPY > 200-day SMA (bear filter)
    require_trend=True,    # close > sma20 & sma50
)


def make_signals(**overrides):
    p = {**DEFAULTS, **overrides}

    def _signals(ticker, df, ctx):
        n = len(df)
        if n < 210:
            return []
        o = df["open"].to_numpy(float); l = df["low"].to_numpy(float)
        c = df["close"].to_numpy(float); v = df["volume"].to_numpy(float)
        close_pos = df["close_pos"].to_numpy(float)
        ret1 = df["ret1"].to_numpy(float)
        sma20 = df["sma20"].to_numpy(float); sma50 = df["sma50"].to_numpy(float)
        bull = aligned(ctx, df, p["regime_col"], False)
        ds = dates(df)

        up = np.zeros(n, bool)
        cond = c[1:] / c[:-1] >= p["up_thresh"]
        if p["vol_gt_prior"]:
            cond = cond & (v[1:] > v[:-1])
        cond = cond & (v[1:] >= p["min_vol"])
        up[1:] = cond
        prior_calm = np.zeros(n, bool)
        prior_calm[1:] = ret1[:-1] <= p["prior_calm_max"]
        mask = up & prior_calm & (close_pos >= p["close_pos_min"])
        if p["require_trend"]:
            mask = mask & (c > sma20) & (c > sma50)
        if p["require_regime"]:
            mask = mask & bull

        out = []
        for i in np.where(mask)[0]:
            if i >= n - 1:
                continue
            stop = l[i]
            if stop >= c[i]:
                continue
            out.append(Signal(ticker, ds[i], stop=stop, target=None, entry="next_open"))
        return out

    return _signals


signals = make_signals()
