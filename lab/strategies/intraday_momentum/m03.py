"""m03 — Intraday Momentum, penultimate-half-hour (r12) predictor (Stage 0).

Strategy identity:
    Name: Intraday Momentum
    Alias: intraday_momentum
    Letter: m
    Release: m03

Why m03 (sibling of m02, different predictor):
    Gao, Han, Li & Zhou (RFS 2018) predict the last half-hour return (r13) from
    TWO terms: the first half-hour (r1) AND the penultimate half-hour (r12 =
    15:00–15:30). m02 tested r1 faithfully and it was negative even gross on 2024
    ETFs. r12 is the secondary published term and in several replications carries
    more of the signal (recent-interval continuation into the close). m03 tests
    it, so the family is judged on BOTH published predictors before any verdict.

Research thesis: a positive 15:00–15:30 return tends to continue in the last
    half-hour (intraday underreaction near the close). Long-only, same-day, flat
    by close. Documented strongest at the index/sector-ETF level (etf_liquid_pit).

Data requirements:
    - 5-minute regular-hours OHLCV bars for the trade date (always loaded).

Entry rules (Stage 0, bare — NO extra filters):
    - Need the six 15:00–15:25 (start-indexed) 5-minute bars. r12 = last(15:25
      close) / first(15:00 open) − 1. Admit LONG when r12 is positive.
    - Signal time = the 15:25 bar; entry trigger = the 15:25 close → fill at the
      start of the last half-hour (~15:30). Rank / cap by r12 strength.

Exit and risk rules:
    - Hold the last half-hour only; flatten at 15:55 ET.
    - Risk unit = the r12-window (15:00–15:30) range, a per-name volatility scale
      (comparable R to m02). Stop = entry − risk (far for a 25-min hold, so R
      measures the predicted move, not a stop game). Target unreachable.

Known limitations (addressed only via the pre-registered search, never hand-tuned):
    - "Trade through the 15:25 close" entry is a mild confirmation vs an
      unconditional 15:30 market order; rare no-fills.
    - Uses r12 alone (ignores r1 and any volume/volatility conditioning).
    - Independent-trade simulation overstates a correlated ETF book.
"""

from __future__ import annotations

from trading.lab.strategies.base import StrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt


def _r12_window(bars):
    """The six 15:00–15:25 (start-indexed) 5-minute bars, or None if incomplete."""
    if bars is None or bars.empty:
        return None
    window = bars.between_time("15:00", "15:25", inclusive="both")
    if len(window) < 6:
        return None
    return window


class Release(StrategyRelease):
    release_id = "m03"
    strategy_letter = "m"
    strategy_alias = "intraday_momentum"
    strategy_name = "Intraday Momentum"
    description = (
        "Penultimate-half-hour predictor: long when the 15:00–15:30 return is "
        "positive, enter ~15:30, hold the last half-hour to 15:55."
    )

    min_r12_return_pct = 0.0  # bare: any positive penultimate-half-hour return

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            window = _r12_window(bars)
            if window is None:
                continue
            first_open = float(window.iloc[0]["open"])
            last_close = float(window.iloc[-1]["close"])
            if first_open <= 0:
                continue
            ret_pct = (last_close - first_open) / first_open * 100.0
            if ret_pct <= self.min_r12_return_pct:
                continue
            rows.append(
                Candidate(
                    ticker=ticker,
                    score=ret_pct,
                    reason="positive_penultimate_half_hour_return",
                    features={
                        "r12_return_pct": ret_pct,
                        "r12_high": float(window["high"].max()),
                        "r12_low": float(window["low"].min()),
                    },
                )
            )
        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        window = _r12_window(context.bars_5m.get(candidate.ticker))
        if window is None:
            return None
        sig_ts = window.index[-1]  # the 15:25 bar; entry fills on the next (15:30) bar
        entry = float(window.iloc[-1]["close"])
        risk = float(window["high"].max()) - float(window["low"].min())
        if risk <= 0 or entry <= 0:
            return None
        return Signal(
            ticker=candidate.ticker,
            setup_type="intraday_momentum",
            signal_time=sig_ts.to_pydatetime() if hasattr(sig_ts, "to_pydatetime") else sig_ts,
            entry_trigger=entry,
            stop_price=entry - risk,
            target_price=entry + 1000.0 * risk,
            metadata={**candidate.features, "release": self.release_id},
        )

    def exit_cutoff(self, context: StrategyContext):
        return ny_dt(context.trade_date, 15, 55)
