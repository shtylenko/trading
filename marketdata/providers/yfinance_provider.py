"""YFinance provider implementation — free, always-available daily data fallback."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from ..provider import Provider, ProviderCapabilities
from ..errors import ConnectionTimeoutError
from ..retry import retry_on_connection_error

logger = logging.getLogger("strategy_lab.marketdata.yfinance")

try:
    import yfinance as yf

    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    yf = None

_TZ_NY = "America/New_York"


class YFinanceProvider(Provider):
    """YFinance provider — daily-only, always-available fallback.

    Supports ``split`` and ``all`` adjustment modes.
    No credentials needed.
    Last resort only — no intraday, rate-limited at ~2 req/s.
    """

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name="yfinance",
            priority=99,  # Always last
            timeframes={"1day"},
            sessions={"rth"},
            adjustments={"split", "all"},
            max_lookback_days=None,
            requires_auth=False,
            is_free=True,
        )

    def fetch_bars(
        self,
        ticker: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        session: str = "rth",
        adjustment: str = "split",
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars from yfinance.

        Uses ``auto_adjust=True`` for ``all`` adjustment.
        Uses per-ticker download with ``auto_adjust=False`` for split-only.
        Returns empty DataFrame if yfinance is not installed or data is
        unavailable.
        """
        if not HAS_YFINANCE or yf is None:
            logger.debug("yfinance is not installed")
            return pd.DataFrame()

        if timeframe != "1day":
            logger.debug("yfinance only supports daily timeframe")
            return pd.DataFrame()

        if adjustment not in ("split", "all"):
            logger.debug("yfinance supports split/all adjustment only")
            return pd.DataFrame()

        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")
        auto_adj = adjustment == "all"

        try:
            df = retry_on_connection_error(
                lambda: yf.download(
                    tickers=ticker,
                    start=start_str,
                    end=end_str,
                    progress=False,
                    auto_adjust=auto_adj,
                )
            )

            if df is None or df.empty:
                logger.debug("[YFinance] %s: no data for %s–%s", ticker, start_str, end_str)
                return pd.DataFrame()

            # yfinance returns MultiIndex columns when downloading a single ticker
            if isinstance(df.columns, pd.MultiIndex):
                df = df.xs(ticker.upper(), level=1, axis=1)

            df = df.rename(columns={c: str(c).lower() for c in df.columns})
            df.index = pd.to_datetime(df.index)
            df.index.name = "timestamp"

            # Always tz-aware UTC
            if df.index.tz is None:
                df.index = df.index.tz_localize("America/New_York").tz_convert("UTC")

            # Keep only our required columns
            keep = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
            if not keep:
                return pd.DataFrame()

            result = df[keep].copy()
            if "volume" in result.columns:
                result["volume"] = result["volume"].fillna(0).astype("int64")

            return result.sort_index()
        except ConnectionTimeoutError:
            raise  # network is down — abort, don't fall through
        except Exception as e:
            logger.warning("[YFinance] %s %s–%s: %s", ticker, start_str, end_str, e)
            return pd.DataFrame()
