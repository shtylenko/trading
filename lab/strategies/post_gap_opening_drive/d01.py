"""d01 — Post-Gap Opening Drive P0 baseline.

Strategy identity:
    Name: Post-Gap Opening Drive
    Alias: post_gap_opening_drive
    Letter: d
    Release: d01

Research thesis:
    A stock that opens materially above the prior day's high can continue
    higher during the morning if the opening auction confirms aggressive
    buyer demand. This P0 release validates the basic long-only gap-and-go
    mechanics before adding premarket and execution-quality filters.

Data requirements:
    - 5-minute regular-hours OHLCV bars for the trade date.
    - Daily raw (unadjusted) bars for prior-high gap detection — consistent
      in price scale with the raw intraday bars.
    - Extended-hours data is not required for d01, but later releases should
      use `strategy_lab.marketdata` with `session="extended"` for premarket volume
      and gap-hold checks.

Entry rules:
    - The first regular-hours 5-minute candle must exist.
    - The first candle must close green.
    - The opening price must gap at least 1% above the prior trading day's
      daily high.
    - The latest daily close must be at least $5.
    - Entry trigger is the high of the first 5-minute candle.
    - The simulator may only fill on bars after the opening-drive bar.

Exit and risk rules:
    - Stop is the low of the first 5-minute candle.
    - Target is 1R above the entry trigger.
    - Any open position is flattened at 11:30 New York time.
    - P0 uses percent-return comparison only; position sizing arrives later.

Known limitations:
    - No premarket volume or relative-volume filter yet.
    - No 50% gap-hold validation before the open.
    - No stop-limit offset, 2R target, scale-out, or 9 EMA trailing remainder.
    - No event-day, SPY VWAP, or market-regime filter yet.

Next intended releases:
    - d02: add premarket volume and gap-hold filters.
    - d03: add 2R/scale-out/EMA trailing management.
    - d04+: add common market-regime and execution-quality filters.
"""

from __future__ import annotations

from trading.lab.strategies.base import StrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.research.filters import first_regular_5m_bar, first_regular_5m_candle, green_first_candle, min_price


class Release(StrategyRelease):
    release_id = "d01"
    strategy_letter = "d"
    strategy_alias = "post_gap_opening_drive"
    strategy_name = "Post-Gap Opening Drive"
    description = "P0 gap-and-go baseline: gap above prior high, green first 5m candle, breakout, stop at low, 1R target."

    min_gap_pct = 1.0

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            daily = context.daily.get(ticker)
            first = first_regular_5m_candle(bars)
            if first is None or daily is None or len(daily) < 2:
                continue
            if not min_price(daily, 5.0, context.trade_date):
                continue
            if not green_first_candle(bars):
                continue
            prior_daily = daily[daily.index.date < context.trade_date]
            if prior_daily.empty:
                continue
            prior = prior_daily.iloc[-1]
            open_price = float(first["open"])
            prior_high = float(prior["high"])
            if prior_high <= 0:
                continue
            gap_pct = (open_price - prior_high) / prior_high * 100.0
            if gap_pct < self.min_gap_pct:
                continue
            rows.append(
                Candidate(
                    ticker=ticker,
                    score=gap_pct,
                    reason="gap_above_prior_high_green_open",
                    features={
                        "gap_pct_vs_prior_high": gap_pct,
                        "prior_high": prior_high,
                        "first_open": open_price,
                        "first_high": float(first["high"]),
                        "first_low": float(first["low"]),
                        "first_close": float(first["close"]),
                        "first_volume": float(first.get("volume", 0.0)),
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
        first_ts, first = first_bar
        high = float(first["high"])
        low = float(first["low"])
        risk = high - low
        if risk <= 0:
            return None
        return Signal(
            ticker=candidate.ticker,
            setup_type="post_gap_opening_drive",
            signal_time=first_ts.to_pydatetime() if hasattr(first_ts, "to_pydatetime") else first_ts,
            entry_trigger=high,
            stop_price=low,
            target_price=high + risk,
            metadata={**candidate.features, "release": self.release_id},
        )

    def exit_cutoff(self, context: StrategyContext):
        return ny_dt(context.trade_date, 11, 30)
