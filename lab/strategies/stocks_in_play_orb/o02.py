"""o02 — Stocks-in-Play Opening Range Breakout Phase v1.

Strategy identity:
    Name: Stocks-in-Play Opening Range Breakout
    Alias: stocks_in_play_orb
    Letter: o
    Release: o02

Research thesis:
    Replicates Zarattini, Barbon, and Aziz (2024) paper.
    Opening range breakout (ORB) momentum is highly persistent when restricted
    strictly to "Stocks in Play" (SIP) experiencing abnormal, fundamental-driven
    institutional trading volume (RV >= 2.0).

Data requirements:
    - 5-minute regular-hours OHLCV bars for the trade date.
    - Historical 5-minute bars for the preceding 14 trading days.
    - Daily raw (unadjusted) bars for daily average volume, price, and ATR —
      consistent in scale with the raw intraday bars; trailing windows that
      span a split-like jump are skipped (see common.build_sip_base).

Entry rules:
    - The first regular-hours 5-minute candle must exist.
    - The first candle must close green (bullish confirmation).
    - The opening price of the trade date must be > $5.00.
    - Trailing 14-day daily ATR > $0.50.
    - Trailing 14-day average daily volume >= 1,000,000.
    - Relative Volume (RV) of opening bar >= 2.0.
    - Top 20 stocks ranked by RV are selected.
    - Entry trigger is the high of the first 5-minute candle.
    - Buy stop order placed at the high.

Exit and risk rules:
    - Stop is placed at Entry - 0.10 * daily_atr_14.
    - Settle position size based on 1% risk of account capital ($100k capital),
      enforcing a hard 4x leverage cap.
    - Exit position entirely at 15:59 New York time (strict EOD close).
    - No targets and no trailing stops.
"""

from __future__ import annotations

from trading.lab.strategies.base import StrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.research.filters import first_regular_5m_bar
from trading.lab.strategies.stocks_in_play_orb.common import build_sip_base


class Release(StrategyRelease):
    release_id = "o02"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "Stocks-in-Play Opening Range Breakout v1"
    description = "Phase v1 SSRN replication: price > $5, vol >= 1M, ATR > 0.50, green 1st candle, RV >= 2.0, top 20, 10% ATR stop, 1% capital risk, 4x leverage cap, MOC close at 15:59."
    historical_5m_lookback_days = 14

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            base = build_sip_base(
                ticker,
                bars,
                context.daily.get(ticker),
                context.historical_5m.get(ticker),
                context.trade_date,
            )
            if base is None:
                continue

            rows.append(
                Candidate(
                    ticker=ticker,
                    score=base.rv,
                    reason="stocks_in_play_ssrn",
                    features={
                        "rv": base.rv,
                        "daily_atr_14": base.daily_atr_14,
                        "mean_opening_volume": base.mean_opening_volume,
                        "first_open": base.first_open,
                        "first_high": base.first_high,
                        "first_low": base.first_low,
                        "first_close": base.first_close,
                        "first_volume": base.first_volume,
                        "or_start_minute": base.or_start_minute,
                    },
                )
            )

        # Rank candidates by RV descending and select top 20
        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        rows = rows[:20]
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
        atr = candidate.features["daily_atr_14"]

        entry_trigger = high
        stop_price = entry_trigger - (0.10 * atr)

        risk_per_share = entry_trigger - stop_price
        if risk_per_share <= 0:
            return None

        # Position sizing: 1% risk of account capital ($100,000 capital)
        account_capital = 100_000.0
        risk_budget = account_capital * 0.01
        qty = risk_budget / risk_per_share

        # Enforce hard 4x leverage cap
        max_capital = account_capital * 4.0
        required_capital = qty * entry_trigger
        if required_capital > max_capital:
            qty = max_capital / entry_trigger

        qty = max(1, int(round(qty)))

        metadata = {
            **candidate.features,
            "release": self.release_id,
            "account_capital": account_capital,
            "risk_per_share": risk_per_share,
            "shares": qty,
            "leverage": (qty * entry_trigger) / account_capital,
        }

        return Signal(
            ticker=candidate.ticker,
            setup_type="opening_range_breakout_ssrn",
            signal_time=first_ts.to_pydatetime() if hasattr(first_ts, "to_pydatetime") else first_ts,
            entry_trigger=entry_trigger,
            stop_price=stop_price,
            target_price=None,  # No target (EOD close only)
            metadata=metadata,
        )

    def exit_cutoff(self, context: StrategyContext):
        # Flatten exactly at 15:59 New York time (strict EOD close)
        return ny_dt(context.trade_date, 15, 59)
