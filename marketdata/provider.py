"""Abstract provider interface, capabilities model, and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd


@dataclass
class ProviderCapabilities:
    """Declares what data a provider can supply.

    Attributes
    ----------
    name : str
        Human-readable provider name (e.g. ``\"alpaca\"``, ``\"marketdata\"``).
    priority : int
        Lower number = tried first in the routing chain.
    timeframes : set[str]
        Supported timeframes (e.g. ``{\"1min\", \"5min\", \"1day\"}``).
    sessions : set[str]
        Supported sessions (e.g. ``{\"rth\", \"extended\"}``).
    adjustments : set[str]
        Supported adjustment modes (e.g. ``{\"raw\", \"split\", \"all\"}``).
    max_lookback_days : int or None
        Maximum historical days the provider can serve.  ``None`` = unlimited.
    requires_auth : bool
        Whether the provider needs API credentials.
    is_free : bool
        Whether the provider is free to use.
    authoritative : bool
        The provider serves the full consolidated tape: when it responds
        successfully, bars it does not return genuinely do not exist
        (e.g. minutes with no trades on thin tickers), so the router must
        not fall through to lower-priority providers chasing them.
        Fallthrough still happens when the provider errors or is not
        configured.
    """

    name: str
    priority: int
    timeframes: set[str] = field(default_factory=lambda: {"1day"})
    sessions: set[str] = field(default_factory=lambda: {"rth"})
    adjustments: set[str] = field(default_factory=lambda: {"raw"})
    max_lookback_days: Optional[int] = None
    requires_auth: bool = True
    is_free: bool = False
    authoritative: bool = False


class Provider(ABC):
    """Abstract base for any market data provider.

    Subclasses must implement ``capabilities`` and ``fetch_bars``.
    """

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        ...

    @abstractmethod
    def fetch_bars(
        self,
        ticker: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        session: str = "rth",
        adjustment: str = "raw",
    ) -> pd.DataFrame:
        """Return OHLCV data for the given parameters.

        Returns an empty DataFrame (not None) when the provider has no data
        for the requested range.  The caller iterates through the provider
        chain; an empty result triggers a fallthrough, not an error.

        The returned DataFrame must have:
        - A ``\"timestamp\"`` column (or a ``DatetimeIndex`` named
          ``\"timestamp\"``) as tz-aware UTC.
        - Columns ``open``, ``high``, ``low``, ``close`` (float64),
          ``volume`` (int64).
        - Optionally ``trade_count`` (int64), ``vwap`` (float64).
        """
        ...


# ── Registry ──────────────────────────────────────────────────────────────────

_PROVIDER_REGISTRY: list[Provider] = []


def register_provider(provider: Provider) -> None:
    """Register a provider.  The list is sorted by priority on insertion."""
    _PROVIDER_REGISTRY.append(provider)
    _PROVIDER_REGISTRY.sort(key=lambda p: p.capabilities.priority)


def get_providers_for_timeframe(
    timeframe: str,
    session: str = "rth",
    adjustment: str = "raw",
) -> list[Provider]:
    """Return registered providers that support *timeframe*, in priority order.

    Parameters
    ----------
    timeframe : str
        One of ``1min``, ``5min``, ``15min``, ``1day``.
    session : str
        Filter by session support.
    adjustment : str
        Filter by adjustment mode.

    Returns
    -------
    list[Provider]
        Providers that support the timeframe, ordered by priority.
    """
    return [
        p
        for p in _PROVIDER_REGISTRY
        if timeframe in p.capabilities.timeframes
        and session in p.capabilities.sessions
        and adjustment in p.capabilities.adjustments
    ]
