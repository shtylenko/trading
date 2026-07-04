"""Build a live ``StrategyContext`` that MATCHES the swing backtest's context.

Parity is the whole point (DESIGN §2). This mirrors
``runner/swing_pipeline.py::_run_swing_session``: daily bars through the rebalance
close (inclusive) on the release's ``daily_adjustment`` grid, plus ``spy_daily`` on
the same grid when the release requires it. Same loader (``data/market_data.py``),
same shape → same ``build_candidates`` output as a same-day backtest.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from trading.lab.core.models import StrategyContext
from trading.lab.data.market_data import fetch_daily_range
from trading.live.config import LiveConfig


def _load_daily(tickers, start, end, adjustment):
    out = {}
    for t in sorted(tickers):
        df = fetch_daily_range(t, start, end, force=False, adjustment=adjustment)
        if df is not None and not df.empty:
            d = df.copy()
            d.index = pd.DatetimeIndex(d.index).normalize().tz_localize(None)
            out[t] = d[~d.index.duplicated(keep="last")].sort_index()
    return out


def build_live_context(release, asof: date, universe_tickers: list[str],
                       config: LiveConfig) -> StrategyContext:
    """Hydrate the same context the swing runner builds, for ``asof`` (today's close).

    ``asof`` must be a settled trading day (the runner's freshness gate guarantees it).
    Returns a context with ``daily`` through ``asof`` and ``spy_daily`` when required.
    """
    adjustment = getattr(release, "daily_adjustment", "split")
    asof_ts = pd.Timestamp(asof).normalize()
    lookback = max(int(getattr(release, "daily_lookback_days", 420)), 420)
    start = asof - timedelta(days=int(lookback * 1.6) + 10)

    bars = _load_daily(universe_tickers, start, asof, adjustment)
    ctx_daily = {}
    for t, b in bars.items():
        upto = b[b.index <= asof_ts]
        if len(upto) >= 253:                       # match swing_pipeline minimum
            ctx_daily[t] = upto.tail(300)

    ctx_spy = None
    if getattr(release, "requires_spy_daily", False):
        spy = fetch_daily_range("SPY", start, asof, force=False, adjustment=adjustment)
        if spy is not None and not spy.empty:
            spy = spy.copy()
            spy.index = pd.DatetimeIndex(spy.index).normalize().tz_localize(None)
            spy = spy[~spy.index.duplicated(keep="last")].sort_index()
            upto = spy[spy.index <= asof_ts]
            if len(upto) >= 253:
                ctx_spy = upto.tail(300)

    return StrategyContext(
        trade_date=asof, release_id=release.release_id, testset=None,
        bars_5m={}, daily=ctx_daily, spy_daily=ctx_spy,
    )
