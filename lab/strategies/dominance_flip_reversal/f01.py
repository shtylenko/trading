"""f01 — Dominance Flip Reversal P0 baseline.

Strategy identity:
    Name: Dominance Flip Reversal
    Alias: dominance_flip_reversal
    Letter: f
    Release: f01

    Note on the letter: the family spec was commissioned for letter "d",
    but "d" is owned by post_gap_opening_drive (d01). The family uses
    "f" (flip) instead.

Research thesis:
    See ``spec.md`` in this directory. An intraday capitulation flush that
    stretches a liquid stock far below its rolling mean without a mean
    touch, on climactic volume and with decaying downside momentum (bullish
    RSI divergence), marks a liquidity vacuum. The "dominance flip" — the
    z-score crossing back up out of the extreme zone — is the moment
    aggressive sellers exhaust and counter-party liquidity takes the tape.
    The trade is the long snap-back to the mean.

    This P0 release maps the (asset-agnostic, both-direction) family spec
    onto strategy_lab's long-only same-day harness: only the downside
    stretch / long reversal leg is implemented.

Data requirements:
    - 5-minute regular-hours OHLCV bars for the trade date (default load).
    - Daily context bars for the price/liquidity eligibility gauntlet.
    - All indicators are seeded from same-day bars only, so the earliest
      possible flip is around bar 32 (~12:10 New York time).

Entry rules (all on same-day 5-minute bars):
    - Eligibility: latest daily close >= $5 and 14-day average daily
      volume >= 1M shares (liquid large-cap restriction per spec §10.1).
    - Phase 1 — price stretch: at least 12 consecutive bars whose highs
      stay strictly below the 20-period SMA (no mean touch).
    - Phase 2 — RSI divergence: the lowest low of the stretch undercuts an
      earlier swing low (>= 3 bars before it) while the 14-period Wilder
      RSI prints higher at the deeper low.
    - Phase 3 — z-score extreme: the close z-score versus the 20-period
      SMA reaches <= -2.0, and the extreme-low bar shows a volume z-score
      >= +1.0 (liq-flow climax proxy).
    - Phase 4 — the flip: z-score crosses back above -2.0. That bar is the
      signal bar; the entry trigger is its high, filled by the breakout
      simulator only on later bars (no same-bar look-ahead).
    - Flips after 15:00 New York time are discarded — no room to work the
      reversion before the time exit.

Exit and risk rules:
    - Stop is the extreme flush low minus 0.5 x intraday ATR(14)
      (volatility-adaptive buffer below the liquidity-sweep wick, spec §9.1).
    - Target is the 20-period SMA value at the flip bar — a static
      approximation of the dynamic "mean-touch" exit (spec §8).
    - Setups where the trigger is not strictly between stop and target are
      discarded (mean already reclaimed or inverted risk).
    - Any open position is flattened at 15:55 New York time.
    - P0 uses percent-return comparison only; position sizing arrives later.

Known limitations:
    - Target is the SMA frozen at signal time, not the moving mean; a
      sideways "time correction" resolves via the 15:55 time exit instead.
    - No N-bar abort after entry (spec §8.3 suggests 5-8 bars); the
      simulator only supports stop/target/cutoff exits today.
    - Liq-flow is proxied by a volume z-score climax; no signed volume
      delta or order-flow absorption modeling.
    - Indicators are same-day only — late-morning flushes after an early
      mean touch are invisible until enough bars have printed.
    - Long-only: the short (blow-off top) leg of the spec is not expressible
      in the current harness.

Next intended releases:
    - f02: seed indicators with historical_5m_lookback_days so morning
      flushes are tradable; add signed-volume liq-flow delta.
    - f03: N-bar time-decay abort and trailing/mean-tracking exit.
    - f04+: market-regime filter (SPY trend), parameter sweeps over
      z-threshold and stretch length via the common search tooling.
"""

from __future__ import annotations

from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.research.filters import min_avg_daily_volume, min_price
from trading.lab.strategies.base import StrategyRelease
from trading.lab.strategies.dominance_flip_reversal.common import detect_dominance_flip


class Release(StrategyRelease):
    release_id = "f01"
    strategy_letter = "f"
    strategy_alias = "dominance_flip_reversal"
    strategy_name = "Dominance Flip Reversal"
    description = (
        "P0 long capitulation-reversal baseline: 12-bar stretch below the 20-SMA, "
        "bullish RSI divergence, z <= -2 with volume climax, entry on the z flip-back, "
        "ATR-buffered stop under the flush low, mean-touch target, 15:55 time exit."
    )

    min_last_close = 5.0
    min_avg_volume = 1_000_000
    sma_period = 20
    rsi_period = 14
    vol_period = 20
    atr_period = 14
    z_extreme = 2.0
    min_stretch_bars = 12
    min_divergence_separation = 3
    vol_climax_z = 1.0
    stop_atr_mult = 0.5
    latest_flip_hour = 15
    latest_flip_minute = 0

    def _detect(self, bars):
        return detect_dominance_flip(
            bars,
            z_extreme=self.z_extreme,
            min_stretch_bars=self.min_stretch_bars,
            min_divergence_separation=self.min_divergence_separation,
            vol_climax_z=self.vol_climax_z,
            stop_atr_mult=self.stop_atr_mult,
            sma_period=self.sma_period,
            rsi_period=self.rsi_period,
            vol_period=self.vol_period,
            atr_period=self.atr_period,
        )

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        latest_flip = ny_dt(context.trade_date, self.latest_flip_hour, self.latest_flip_minute)
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            daily = context.daily.get(ticker)
            if not min_price(daily, self.min_last_close, context.trade_date):
                continue
            if not min_avg_daily_volume(daily, self.min_avg_volume, 14, context.trade_date):
                continue
            setup = self._detect(bars)
            if setup is None:
                continue
            if setup["flip_time"] > latest_flip:
                continue
            rows.append(
                Candidate(
                    ticker=ticker,
                    score=abs(setup["z_min"]),
                    reason="z_flip_back_after_stretch_with_divergence",
                    features=setup,
                )
            )
        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        f = candidate.features
        if not f or "flip_time" not in f:
            return None
        flip_ts = f["flip_time"]
        return Signal(
            ticker=candidate.ticker,
            setup_type="dominance_flip_reversal",
            signal_time=flip_ts.to_pydatetime() if hasattr(flip_ts, "to_pydatetime") else flip_ts,
            entry_trigger=float(f["entry_trigger"]),
            stop_price=float(f["stop_price"]),
            target_price=float(f["target_price"]),
            metadata={**f, "release": self.release_id},
        )

    def exit_cutoff(self, context: StrategyContext):
        return ny_dt(context.trade_date, 15, 55)
