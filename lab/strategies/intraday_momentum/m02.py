"""m02 — Market Intraday Momentum, faithful last-half-hour form (Stage 0).

Strategy identity:
    Name: Intraday Momentum
    Alias: intraday_momentum
    Letter: m
    Release: m02

Why m02 (one-lever change from m01):
    m01 held from ~10:00 to the close and was broadly negative (2024 baseline
    −206R, all four quarters red). But that is NOT the documented effect. Gao,
    Han, Li & Zhou (RFS 2018) is specifically: the FIRST half-hour return
    predicts the LAST half-hour return. The tradeable form takes a position at
    the start of the last half-hour and holds only into the close — NOT an
    all-day hold. m01 spent 5.5 hours exposed to mean-reversion/noise that was
    never part of the predictive relationship (and ate 969 morning-low stops).
    m02 expresses the actual thesis: signal in the morning, act at 15:30.

Research thesis (unchanged): intraday underreaction — a positive first-half-hour
    return tends to continue in the last half-hour. Long-only, same-day, flat by
    close. Documented strongest at the index/sector-ETF level (etf_liquid_pit).

Data requirements:
    - 5-minute regular-hours OHLCV bars for the trade date (always loaded).

Entry rules (Stage 0, bare — NO extra filters):
    - Need the first six regular 5-minute bars (09:30–09:55). Morning return =
      last(09:55 close) / first(09:30 open) − 1. Admit LONG when it is positive.
    - Act late: signal time = the 15:25 bar; entry trigger = the 15:25 close, so
      the simulator fills at the start of the last half-hour (~15:30). Rank /
      deployment-cap by morning-return strength.

Exit and risk rules:
    - Hold the LAST half-hour only; flatten at 15:55 ET (the intended exit).
    - Risk unit = the first-half-hour range (a per-name volatility scale, so R is
      comparable to m01). Stop = entry − risk: far enough below a 25-minute hold
      that it rarely interferes, so realized R measures the predicted late move
      rather than a stop game. Target unreachable (ride to the time exit).

Known limitations (addressed only via the pre-registered search, never hand-tuned):
    - "Trade through the 15:25 close" entry is a mild confirmation vs an
      unconditional 15:30 market order (the engine is breakout-stop); rare
      no-fills when price never revisits the 15:25 close.
    - Uses only Gao's first term (r1); ignores the penultimate-half-hour
      predictor (r12) and any volume/volatility conditioning.
    - Independent-trade simulation overstates a correlated ETF book.

Next intended work:
    - Stage-0 baseline on etf_liquid_pit; if there is signal, broad capture +
      pre-registered search per validation/EXPLORATION_PLAYBOOK.md.
"""

from __future__ import annotations

from trading.lab.strategies.base import StrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt


def _first_half_hour(bars):
    """The six 09:30–09:55 (start-indexed) 5-minute bars, or None if incomplete."""
    if bars is None or bars.empty:
        return None
    window = bars.between_time("09:30", "09:55", inclusive="both")
    if len(window) < 6:
        return None
    return window


def _bar_at(bars, hh, mm):
    """The single 5-minute bar starting at HH:MM (start-indexed), or None."""
    if bars is None or bars.empty:
        return None
    t = f"{hh:02d}:{mm:02d}"
    sel = bars.between_time(t, t, inclusive="both")
    if sel.empty:
        return None
    return sel.index[0], sel.iloc[0]


class Release(StrategyRelease):
    release_id = "m02"
    strategy_letter = "m"
    strategy_alias = "intraday_momentum"
    strategy_name = "Intraday Momentum"
    description = (
        "Faithful Gao form: long when the first-half-hour return is positive, but "
        "enter at the start of the last half-hour (~15:30) and hold only to 15:55."
    )

    min_morning_return_pct = 0.0  # bare: any positive first-half-hour return

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            window = _first_half_hour(bars)
            if window is None:
                continue
            first_open = float(window.iloc[0]["open"])
            last_close = float(window.iloc[-1]["close"])
            if first_open <= 0:
                continue
            ret_pct = (last_close - first_open) / first_open * 100.0
            if ret_pct <= self.min_morning_return_pct:
                continue
            rows.append(
                Candidate(
                    ticker=ticker,
                    score=ret_pct,
                    reason="positive_first_half_hour_return",
                    features={
                        "first30_return_pct": ret_pct,
                        "first30_high": float(window["high"].max()),
                        "first30_low": float(window["low"].min()),
                    },
                )
            )
        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        bars = context.bars_5m.get(candidate.ticker)
        window = _first_half_hour(bars)
        late = _bar_at(bars, 15, 25)  # last bar before the closing half-hour
        if window is None or late is None:
            return None
        late_ts, late_bar = late
        entry = float(late_bar["close"])
        risk = float(window["high"].max()) - float(window["low"].min())
        if risk <= 0 or entry <= 0:
            return None
        return Signal(
            ticker=candidate.ticker,
            setup_type="intraday_momentum",
            signal_time=late_ts.to_pydatetime() if hasattr(late_ts, "to_pydatetime") else late_ts,
            entry_trigger=entry,
            stop_price=entry - risk,             # far enough out for a 25-min hold
            target_price=entry + 1000.0 * risk,  # unreachable → ride to the time exit
            metadata={**candidate.features, "release": self.release_id},
        )

    def exit_cutoff(self, context: StrategyContext):
        return ny_dt(context.trade_date, 15, 55)
