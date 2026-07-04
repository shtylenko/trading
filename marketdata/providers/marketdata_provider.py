"""MarketData.app REST API provider implementation."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from ..calendar import clip_to_session_close
from ..provider import Provider, ProviderCapabilities
from ..errors import ConnectionTimeoutError, ProviderError
from ..retry import CircuitBreaker, retry_on_connection_error

logger = logging.getLogger("strategy_lab.marketdata.marketdata")

# Shared across workers — fail fast during outages instead of every worker
# burning its own retry budget against a dead endpoint.
_BREAKER = CircuitBreaker("marketdata", failure_threshold=5, window_seconds=300.0)


def _load_token() -> str:
    """Load MARKETDATA_TOKEN from .env files."""
    module_dir = Path(__file__).resolve().parent
    strategy_lab_dir = module_dir.parents[1]
    engine_dir = module_dir.parents[2]
    project_root = module_dir.parents[3]
    for dotfile in (
        project_root / ".env",
        engine_dir / ".env",
        strategy_lab_dir / ".env",
        Path.home() / ".hermes" / ".env",
    ):
        if dotfile.exists():
            load_dotenv(dotfile)
    return os.getenv("MARKETDATA_TOKEN", "")


# Map our timeframe to MarketData's API path segment
_TF_TO_MD = {
    "1min": 1,
    "5min": 5,
    "15min": 15,
    "1day": "D",
}

_TZ_NY = "America/New_York"


class MarketDataProvider(Provider):
    """MarketData.app REST API provider for OHLCV bars.

    Supports 1min, 5min, 15min, and daily timeframes.
    Provides ``raw`` adjustment only (actual traded prices).
    No chunking needed — single request covers any range.
    """

    def __init__(self):
        self._token = _load_token()

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name="marketdata",
            priority=2,
            timeframes={"1min", "5min", "15min", "1day"},
            sessions={"rth", "extended"},
            adjustments={"raw"},
            max_lookback_days=None,
            requires_auth=True,
            is_free=False,
        )

    def fetch_bars(
        self,
        ticker: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        session: str = "rth",
        adjustment: str = "raw",
    ) -> pd.DataFrame:
        """Fetch OHLCV bars from MarketData.app.

        Returns raw (unadjusted) prices only.  If the caller requests
        ``split`` or ``all`` adjustment, this provider is skipped
        (returns empty DataFrame).

        HTTP errors (4xx, 5xx — auth, rate limit, server faults) raise
        ``ProviderError`` so the fetcher records them as provider failures
        (short-TTL negative cache) instead of "confirmed no data" (24h).
        """
        if not self._token:
            raise ProviderError("MarketData token not configured")

        if adjustment not in ("raw",):
            logger.debug("MarketData only supports raw adjustment")
            return pd.DataFrame()

        md_key = _TF_TO_MD.get(timeframe)
        if md_key is None:
            logger.debug("Unsupported timeframe %s for MarketData", timeframe)
            return pd.DataFrame()

        # Build URL
        start_str = start.astimezone(timezone.utc).strftime("%Y-%m-%d")
        end_str = end.astimezone(timezone.utc).strftime("%Y-%m-%d")
        url = (
            f"https://api.marketdata.app/v1/stocks/candles/{md_key}/"
            f"{ticker.upper()}/?from={start_str}&to={end_str}"
        )

        def _execute_request():
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {self._token}")
            req.add_header("User-Agent", "strategy_lab.marketdata/1.0")
            with urllib.request.urlopen(req, timeout=30) as response:
                body = response.read()
                if response.status == 204 or not body:
                    # 204 No Content = confirmed empty range, not an error
                    return {"s": "no_data"}
                return json.loads(body.decode("utf-8"))

        try:
            data = retry_on_connection_error(_execute_request, circuit_breaker=_BREAKER)
        except ConnectionTimeoutError:
            raise  # network is down — abort, don't fall through
        except urllib.error.HTTPError as e:
            # MarketData signals "no data" with s != "ok" in a 200 body
            # (and 204 for some endpoints); a 4xx/5xx is a genuine failure
            # (auth, rate limit, server error) and must not be mistaken
            # for an empty-range confirmation.
            logger.warning("[MarketData] %s %s–%s: HTTP %s",
                           ticker, start_str, end_str, e.code)
            raise ProviderError(
                f"MarketData HTTP {e.code} for {ticker} {start_str}–{end_str}"
            ) from e
        except Exception as e:
            logger.warning("[MarketData] %s %s–%s: %s", ticker, start_str, end_str, e)
            raise ProviderError(
                f"MarketData request failed for {ticker} {start_str}–{end_str}: {e}"
            ) from e

        if data.get("s") != "ok" or not data.get("t"):
            logger.debug("[MarketData] %s: no data for %s–%s", ticker, start_str, end_str)
            return pd.DataFrame()

        timestamps = data.get("t", [])
        if not timestamps:
            return pd.DataFrame()

        df = pd.DataFrame({
            "open": [float(x) for x in data.get("o", [])],
            "high": [float(x) for x in data.get("h", [])],
            "low": [float(x) for x in data.get("l", [])],
            "close": [float(x) for x in data.get("c", [])],
            "volume": [int(x) for x in data.get("v", [])],
        }, index=pd.to_datetime(timestamps, unit="s", utc=True))
        df.index.name = "timestamp"

        # Filter to requested session (skip for daily bars — timestamps at
        # midnight ET would be dropped by ``between_time``).
        # Left-closed [open, 16:00) — exclude the 16:00 closing-auction label
        # to stay consistent with the calendar's expected-bar set.
        if timeframe != "1day":
            if session == "rth":
                # RTH: 09:30–15:59 ET
                df_ny = df.tz_convert(_TZ_NY)
                df_ny = df_ny.between_time("09:30", "15:59")
                df = clip_to_session_close(df_ny.tz_convert("UTC"))
            elif session == "extended":
                # Extended: 04:00–15:59 ET
                df_ny = df.tz_convert(_TZ_NY)
                df_ny = df_ny.between_time("04:00", "15:59")
                df = clip_to_session_close(df_ny.tz_convert("UTC"))

        # Remove rows where any OHLCV is NaN — partial rows (e.g. NaN close
        # but valid high/low) poison ATR/feature math downstream.
        df = df.dropna(subset=["open", "high", "low", "close", "volume"], how="any")
        return df.sort_index()
