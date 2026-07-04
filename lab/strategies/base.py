from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from trading.lab.core.models import Candidate, Signal, StrategyContext


class StrategyRelease(ABC):
    release_id: str
    strategy_letter: str
    strategy_alias: str
    strategy_name: str
    description: str
    requires_extended_1m: bool = False
    requires_rth_1m: bool = False
    requires_spy_daily: bool = False
    # Calendar-day lookback the runner uses when hydrating context.spy_daily.
    # The default (40) suffices for short SPY windows (e.g. a 20-day ATR); a
    # release needing a long history (200-day SMA, 1-year ATR median) raises
    # this so it can read context.spy_daily instead of calling providers
    # directly from strategy code.
    spy_daily_lookback_days: int = 40
    # Calendar-day lookback for the PER-TICKER daily context (context.daily).
    # Default 40 covers a prior-high + ATR14; a release needing the stock's own
    # 50/200-day SMA, 60-day beta, etc. raises this (the feature-capture variant
    # uses ~420 for a 200-trading-day window). Read from context, never fetched
    # in strategy code.
    daily_lookback_days: int = 40
    historical_5m_lookback_days: int = 0
    # Extra non-traded daily series (e.g. sector ETFs, breadth proxies) the
    # runner fetches and hydrates into context.extra_daily, keyed by symbol.
    # Uses spy_daily_lookback_days for the window. Releases read these for
    # regime gates; they never call providers directly. Default: none.
    extra_daily_symbols: list[str] = []
    entry_style: str = "breakout_stop"  # "breakout_stop" or "pullback_limit"

    @classmethod
    def signature_inputs(cls) -> list[tuple[str, bytes]]:
        """Extra (label, bytes) folded into the run code signature beyond the
        module sources.

        Releases that ship a binary artifact (e.g. an ML model pickle) or pick
        an execution mode at runtime override this so two runs that actually
        executed different strategies never share a code signature. Default:
        nothing extra.
        """
        return []

    @abstractmethod
    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        raise NotImplementedError

    @abstractmethod
    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        raise NotImplementedError

    @abstractmethod
    def exit_cutoff(self, context: StrategyContext) -> datetime:
        raise NotImplementedError


class SwingStrategyRelease(StrategyRelease):
    """Base for MULTI-DAY (swing) releases run by the additive swing runner
    (runner/swing_pipeline.py) — NOT the intraday per-session engine.

    A swing release rebalances every ``rebalance_cadence_days`` trading days, holds
    the top-``top_n`` ranked candidates ``hold_days`` trading days, equal weight, on
    DAILY bars. It reuses the standard two-method contract:
      - ``build_candidates(context)`` ranks the book at a rebalance date. The swing
        runner hydrates ``context.daily[ticker]`` with bars THROUGH the rebalance date
        (inclusive — the close is the decision point), unlike the intraday loader's
        strictly-prior daily.
      - ``build_signal(context, candidate)`` returns the entry (rebalance close) +
        a nominal stop (for R scaling; swing R is secondary to pnl_pct).
    ``exit_cutoff`` is unused for swing (the hold is ``hold_days``); a concrete default
    is provided so subclasses needn't implement it.
    """

    is_swing: bool = True
    hold_days: int = 20            # trading-day hold / rebalance horizon
    rebalance_cadence_days: int = 20  # non-overlapping rebalance every N trading days
    top_n: int = 50                # names held per rebalance, equal weight
    use_close_stop: bool = False   # pure time exit by default
    # SPLIT-ADJUSTED daily bars (unlike the intraday engine's raw convention). A
    # multi-day hold CAN straddle a split, and a split inside the momentum lookback
    # corrupts the rank — both ranking and P&L must be on a split-continuous series.
    # Raw is correct only for same-day intraday trades that can never span a split.
    daily_adjustment: str = "split"

    def exit_cutoff(self, context: StrategyContext):  # noqa: D401 - unused for swing
        return None
