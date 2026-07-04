"""o10 — o03 with an automatic look-ahead-safe ML date gate.

Strategy identity:
    Name: Stocks-in-Play Opening Range Breakout
    Alias: stocks_in_play_orb
    Letter: o
    Release: o10

Why this release exists (audit M14, 2026-06-13):
    o03 ships a LightGBM ranker trained on 2024 walk-forward data. Applying
    that model to any backtest date in its training span (or earlier) is
    temporal look-ahead: the model has seen labels from the period being
    "predicted". o03 only avoids this if the operator remembers to set
    ``O03_DISABLE_ML=1`` for pre-2024 evals — a silent foot-gun. o10 is
    identical to o03 in every mechanic, except the ML ranker is disabled
    AUTOMATICALLY for any trade date in a year < the model's training start;
    those days fall back to the relative-volume ranking o03 documents as
    comparable. The manual ``O03_DISABLE_ML`` override still works.

    Everything else (SIP filter gauntlet, pullback-limit entry, 0.10·ATR
    stop, 1% risk / 4x cap, 15:59 close) is inherited unchanged from o03, so
    o10 on 2024+ dates is behaviourally equal to o03 with the model present.

Known limitations:
    - The gate is whole-year (``trade_date.year < TRAIN_START_YEAR``), not the
      exact training-window boundary; it is intentionally conservative.
    - A run spanning the cutoff mixes ML-ranked and RV-ranked days. That is
      correct (each day uses only information available then) but the pooled
      metrics blend two ranking regimes — segment by year when interpreting.
"""

from __future__ import annotations

import logging

from trading.lab.core.models import StrategyContext
from trading.lab.strategies.stocks_in_play_orb.o03 import Release as O03Release

logger = logging.getLogger("strategy_lab.strategies.o10")


class Release(O03Release):
    release_id = "o10"
    strategy_name = "Stocks-in-Play ORB v2 (ML + pullback) — look-ahead-safe ML date gate"
    description = (
        "o03 mechanics with the LightGBM ranker auto-disabled (RV fallback) on "
        "trade dates before the model's 2024 training span, removing the o03 "
        "look-ahead foot-gun without manual O03_DISABLE_ML."
    )

    # The model artifact is trained on 2024 walk-forward data; any date in an
    # earlier year must not be ranked by it.
    TRAIN_START_YEAR = 2024

    # Per-instance gate set at the top of each date's build_candidates and read
    # by model_payload (the date loop is single-threaded per release).
    _gate_year: int | None = None

    def build_candidates(self, context: StrategyContext):
        type(self)._gate_year = context.trade_date.year
        return super().build_candidates(context)

    @classmethod
    def model_payload(cls):
        if cls._gate_year is not None and cls._gate_year < cls.TRAIN_START_YEAR:
            logger.info(
                "o10: %d < %d training start — ML disabled, RV ranking (look-ahead guard)",
                cls._gate_year, cls.TRAIN_START_YEAR,
            )
            return None
        return super().model_payload()
