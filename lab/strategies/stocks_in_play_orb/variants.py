"""Parametrized base for the o04–o08 SIP-ORB variant releases.

Five pre-registered hypotheses about where the SIP-ORB edge might live,
defined together BEFORE any was run (2026-06-12) and judged by the same
funnel: screen_2022_2026_sampled first (kill: sum R < 0 or sign-flip
p > 0.5), full eval_*_broad gauntlet for survivors only.

All variants share the paper-style mechanics: SIP filter gauntlet
(price > $5, ADV >= 1M, ATR > $0.50, RV gate), 5-minute opening range,
STOP entry on the OR break, stop at 0.10 x ATR14, EOD 15:59 exit, 1% risk
sizing with a 4x leverage cap, RV ranking (no ML). They differ only in
the dimension their hypothesis tests.
"""

from __future__ import annotations

from datetime import date, timedelta

from trading.lab.strategies.base import StrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.research.filters import first_regular_5m_bar
from trading.lab.strategies.stocks_in_play_orb.common import build_sip_base

STOP_OFFSET_ATR = 0.10
ACCOUNT_CAPITAL = 100_000.0
RISK_FRACTION = 0.01
LEVERAGE_CAP = 4.0


class SipOrbVariant(StrategyRelease):
    """Stop-entry SIP ORB with hypothesis knobs (see module docstring)."""

    historical_5m_lookback_days = 14
    entry_style = "breakout_stop"
    # 1-minute sim fidelity is mandatory here: the 0.10 ATR stop is ~1/3 of
    # a 5m bar's range, so 5m simulation overstates losses ~40% via the
    # conservative same-bar stop rule (measured on o04, 2026-06-12).
    requires_rth_1m = True

    # ── Hypothesis knobs (overridden per release) ─────────────────────
    top_n: int | None = None          # None = no cap beyond testset limit
    min_rv: float = 2.0
    min_gap_abs: float | None = None  # |gap| filter, e.g. 0.03
    max_open_price: float | None = None
    allow_short: bool = False         # trade gap-downs short (red candle)
    time_stop_at: str | None = None   # "HH:MM" NY
    time_stop_min_r: float | None = None
    stop_offset_atr: float = STOP_OFFSET_ATR  # stop distance as ATR fraction
    stop_beyond_or: bool = False      # widen stop past the opposite OR extreme

    def regime_ok(self, context: StrategyContext) -> bool:
        """Day-level regime gate; variants may override. Default: trade."""
        return True

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        if not self.regime_ok(context):
            return []
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            for direction, candle in self._directions():
                base = build_sip_base(
                    ticker,
                    bars,
                    context.daily.get(ticker),
                    context.historical_5m.get(ticker),
                    context.trade_date,
                    min_rv=self.min_rv,
                    candle=candle,
                )
                if base is None:
                    continue
                if self.min_gap_abs is not None and abs(base.gap_pct) < self.min_gap_abs:
                    continue
                if self.max_open_price is not None and base.first_open > self.max_open_price:
                    continue
                # Shorts only on gap-downs, longs only on gap-ups when the
                # variant trades both sides (direction of the opening drive).
                if self.allow_short:
                    if direction == "short" and base.gap_pct >= 0:
                        continue
                    if direction == "long" and base.gap_pct < 0:
                        continue
                rows.append(
                    Candidate(
                        ticker=ticker,
                        score=base.rv,
                        reason=f"sip_orb_{self.release_id}_{direction}",
                        features={
                            "direction": direction,
                            "rv": base.rv,
                            "gap_pct": base.gap_pct,
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
                break  # a ticker qualifies for at most one direction

        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        if self.top_n is not None:
            rows = rows[: self.top_n]
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows

    def _directions(self) -> list[tuple[str, str]]:
        if self.allow_short:
            return [("long", "green"), ("short", "red")]
        return [("long", "green")]

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        bars = context.bars_5m.get(candidate.ticker)
        first_bar = first_regular_5m_bar(bars)
        if first_bar is None:
            return None
        first_ts, first = first_bar
        atr = candidate.features["daily_atr_14"]
        direction = candidate.features.get("direction", "long")

        if direction == "short":
            entry_trigger = float(first["low"])
            stop_price = entry_trigger + self.stop_offset_atr * atr
            if self.stop_beyond_or:
                stop_price = max(stop_price, float(first["high"]))
        else:
            entry_trigger = float(first["high"])
            stop_price = entry_trigger - self.stop_offset_atr * atr
            if self.stop_beyond_or:
                # The OR span is the morning's demonstrated noise band: a
                # stop inside it is by construction inside the noise. Take
                # the WIDER of (offset, opposite OR extreme) so risk is at
                # least stop_offset_atr AND clear of the band.
                stop_price = min(stop_price, float(first["low"]))

        risk_per_share = abs(entry_trigger - stop_price)
        if risk_per_share <= 0:
            return None

        qty = ACCOUNT_CAPITAL * RISK_FRACTION / risk_per_share
        max_capital = ACCOUNT_CAPITAL * LEVERAGE_CAP
        if qty * entry_trigger > max_capital:
            qty = max_capital / entry_trigger
        qty = max(1, int(qty))

        metadata = {
            **candidate.features,
            "release": self.release_id,
            "direction": direction,
            "account_capital": ACCOUNT_CAPITAL,
            "risk_per_share": risk_per_share,
            "shares": qty,
            "leverage": (qty * entry_trigger) / ACCOUNT_CAPITAL,
        }
        if self.time_stop_at is not None:
            metadata["time_stop_at"] = self.time_stop_at
            metadata["time_stop_min_r"] = self.time_stop_min_r or 0.0

        return Signal(
            ticker=candidate.ticker,
            setup_type=f"orb_stop_{direction}_{self.release_id}",
            signal_time=first_ts.to_pydatetime() if hasattr(first_ts, "to_pydatetime") else first_ts,
            entry_trigger=entry_trigger,
            stop_price=stop_price,
            target_price=None,
            metadata=metadata,
        )

    def exit_cutoff(self, context: StrategyContext):
        return ny_dt(context.trade_date, 15, 59)


def spy_atr_regime_hot(trade_date: date, lookback_days: int = 252) -> bool:
    """Frozen o07 regime rule (pre-registered 2026-06-12, do not refit):

    Trade only when SPY's 14-day ATR%, computed on daily bars strictly
    before the trade date, is above its median over the past ~252 trading
    days. Conservative on missing data: no data -> do not trade.
    """
    import numpy as np
    from trading.lab.data.market_data import fetch_daily_context

    daily = fetch_daily_context("SPY", trade_date,
                                lookback_days=int(lookback_days * 1.6))
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
