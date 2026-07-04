"""o01 — Stocks-in-Play Opening Range Breakout P0 baseline.

Strategy identity:
    Name: Stocks-in-Play Opening Range Breakout
    Alias: stocks_in_play_orb
    Letter: o
    Release: o01

Research thesis:
    The opening 5-minute range is useful only when the stock is receiving
    abnormal early-session attention. This P0 release does not yet implement
    full stocks-in-play relative-volume ranking; instead, it proves the core
    mechanics of a same-day long-only opening-range breakout in the generic
    strategy_lab runner.

Data requirements:
    - 5-minute regular-hours OHLCV bars for the trade date.
    - Daily raw (unadjusted) bars for price and volume eligibility checks
      consistent with intraday price scales.

Entry rules:
    - The first regular-hours 5-minute candle must exist.
    - The first candle must close green.
    - The latest daily close must be at least $5.
    - Entry trigger is the high of the first 5-minute candle.
    - The simulator may only fill on bars after the opening-range bar.

Exit and risk rules:
    - Stop is the low of the first 5-minute candle.
    - Target is 1R above the entry trigger.
    - Any open position is flattened at 15:55 New York time.
    - P0 uses percent-return comparison only; position sizing arrives later.

Known limitations:
    - No true relative-volume calculation yet.
    - No top-N stock-in-play ranking by historical opening volume.
    - No ATR stop, EOD-only targetless variant, or realistic bid/ask model.
    - Static/sample universes are acceptable for smoke tests only.

Next intended releases:
    - o02: add 14-day opening-bar relative-volume ranking.
    - o03: add ATR stop and targetless EOD exit.
    - o04+: add stronger liquidity/range-width/common-market filters.
"""

from __future__ import annotations

from trading.lab.strategies.base import StrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.research.filters import first_regular_5m_bar, first_regular_5m_candle, green_first_candle, min_price


class Release(StrategyRelease):
    release_id = "o01"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "Stocks-in-Play Opening Range Breakout"
    description = "P0 ORB baseline: green first 5m candle, breakout above high, stop at low, 1R target."

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            daily = context.daily.get(ticker)
            first = first_regular_5m_candle(bars)
            if first is None:
                continue
            if not min_price(daily, 5.0, context.trade_date):
                continue
            if not green_first_candle(bars):
                continue
            score = float(first.get("volume", 0.0))
            rows.append(
                Candidate(
                    ticker=ticker,
                    score=score,
                    reason="green_opening_range",
                    features={
                        "first_open": float(first["open"]),
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
            setup_type="opening_range_breakout",
            signal_time=first_ts.to_pydatetime() if hasattr(first_ts, "to_pydatetime") else first_ts,
            entry_trigger=high,
            stop_price=low,
            target_price=high + risk,
            metadata={**candidate.features, "release": self.release_id},
        )

    def exit_cutoff(self, context: StrategyContext):
        return ny_dt(context.trade_date, 15, 55)
