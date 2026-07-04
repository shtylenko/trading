"""m01 — Market Intraday Momentum P0 baseline (Stage 0 triage).

Strategy identity:
    Name: Intraday Momentum
    Alias: intraday_momentum
    Letter: m
    Release: m01

Research thesis:
    Market intraday momentum (Gao, Han, Li & Zhou, RFS 2018, and follow-ons):
    the FIRST half-hour return of the session predicts the LAST half-hour
    return — an intraday underreaction driven by late-informed traders and
    infrequent institutional rebalancing. The effect is documented strongest at
    the index / sector-ETF level (hence the etf_liquid_pit universe), is modest
    and long-expressible, and has been replicated post-publication and across
    markets — exactly the "low but confident" profile sought for a real-world
    positive control of the validation pipeline.

    This is a DIFFERENT signal from the gap-and-go drives (d-family): there the
    OPENING drive faded after 11:30 (d04 kill). Here the morning return is a
    predictor of the CLOSE, so holding into the close is the thesis, not a
    refuted lever.

Data requirements:
    - 5-minute regular-hours OHLCV bars for the trade date (always loaded).
    - No daily history, SPY, or extended hours needed for the P0 baseline.

Entry rules (Stage 0, deliberately bare — NO extra filters):
    - Need the first six regular 5-minute bars (09:30–09:55, i.e. the first
      half hour). The morning return = last(09:55 close) / first(09:30 open) − 1.
    - Admit LONG when the first-half-hour return is positive (> min threshold).
    - Signal time = the 09:55 bar; entry trigger = the 09:55 close, so the
      simulator fills around 10:00 (the first bar after the signal). Rank /
      deployment-cap by morning-return strength (score).

Exit and risk rules:
    - Stop = the low of the first half hour (morning-range invalidation).
    - Target = unreachable (entry + 1000R) so the position RIDES to the close —
      the effect is about the late-session move, not a quick scalp.
    - Flatten at 15:55 ET (time exit is the intended exit).

Known limitations (to be addressed only via the pre-registered search, never by
hand-tuning here — this is Stage-0 triage + baseline):
    - Entry is a "break the 09:55 close" mechanic (the engine is breakout-stop),
      a mild continuation confirmation vs an unconditional 10:00 market entry; a
      faithful market entry is a later refinement if Stage 0 warrants it.
    - No volume/RVOL, SPY-direction, or volatility filter; no penultimate-half-
      hour predictor (Gao's second term).
    - Independent-trade simulation overstates a correlated ETF book (all longs
      on one tape) — a PASS owes a portfolio re-check.

Next intended work:
    - Stage 0 baseline on etf_liquid_pit; if there is signal, capture (broad) +
      pre-registered feature search per validation/EXPLORATION_PLAYBOOK.md.
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


class Release(StrategyRelease):
    release_id = "m01"
    strategy_letter = "m"
    strategy_alias = "intraday_momentum"
    strategy_name = "Intraday Momentum"
    description = (
        "P0 baseline: long when the first-half-hour (09:30–10:00) return is "
        "positive, enter ~10:00, ride to the 15:55 close, stop at the morning low."
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
                        "first30_close": last_close,
                    },
                )
            )
        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        window = _first_half_hour(context.bars_5m.get(candidate.ticker))
        if window is None:
            return None
        sig_ts = window.index[-1]  # the 09:55 bar; entry fills on the next (10:00) bar
        entry = float(window.iloc[-1]["close"])
        stop = float(window["low"].min())
        risk = entry - stop
        if risk <= 0:
            return None
        return Signal(
            ticker=candidate.ticker,
            setup_type="intraday_momentum",
            signal_time=sig_ts.to_pydatetime() if hasattr(sig_ts, "to_pydatetime") else sig_ts,
            entry_trigger=entry,
            stop_price=stop,
            target_price=entry + 1000.0 * risk,  # unreachable → ride to the time exit
            metadata={**candidate.features, "release": self.release_id},
        )

    def exit_cutoff(self, context: StrategyContext):
        return ny_dt(context.trade_date, 15, 55)
