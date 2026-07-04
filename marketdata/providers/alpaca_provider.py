"""Alpaca Market Data provider implementation."""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from ..calendar import clip_to_session_close
from ..provider import Provider, ProviderCapabilities
from ..errors import ConnectionTimeoutError, PartialDataError, ProviderError
from ..retry import CircuitBreaker, retry_on_connection_error

logger = logging.getLogger("strategy_lab.marketdata.alpaca")
_TZ_NY = "America/New_York"

# Shared across all workers: during an outage the first ~5 failures open
# the breaker and the remaining workers fail fast into the pipeline's
# connectivity-wait instead of each burning a full 15-minute retry budget.
_BREAKER = CircuitBreaker("alpaca", failure_threshold=5, window_seconds=300.0)


class _RateLimiter:
    """Process-wide token bucket pacing all workers under the API quota.

    Without this, 8+ parallel workers collectively exceed Alpaca's
    per-minute quota, every worker's individual Retry-After sleep loses the
    race to the others, and tickers fail out with "rate limit persisted".
    Pacing requests *before* sending keeps 429s near zero.

    The budget is per-process: when running several backtests concurrently
    against one API key, split the quota via ALPACA_RPM (e.g. two runs at
    ALPACA_RPM=90 on a 200/min plan).
    """

    def __init__(self, rpm: float):
        self.capacity = max(rpm, 1.0)
        self.tokens = self.capacity
        self.fill_rate = self.capacity / 60.0
        self.stamp = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(
                    self.capacity, self.tokens + (now - self.stamp) * self.fill_rate
                )
                self.stamp = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.fill_rate
            time.sleep(wait + random.uniform(0, 0.05))


_RATE_LIMITER = _RateLimiter(float(os.getenv("ALPACA_RPM", "180")))

# ── Attempt import ────────────────────────────────────────────────────────────

try:
    from alpaca.data.historical import StockHistoricalDataClient

    HAS_ALPACA = True
except ImportError:
    HAS_ALPACA = False
    StockHistoricalDataClient = None

# ── Chunk size ────────────────────────────────────────────────────────────────

_CHUNK_DAYS = 365


def _load_creds() -> tuple[str, str]:
    """Load Alpaca credentials from .env files."""
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
    return (
        os.getenv("ALPACA_API_KEY_ID", ""),
        os.getenv("ALPACA_SECRET_KEY", ""),
    )


class AlpacaProvider(Provider):
    """Alpaca Market Data provider for OHLCV bars.

    Supports 1min, 5min, 15min, and daily timeframes.
    """

    def __init__(self):
        if not HAS_ALPACA or StockHistoricalDataClient is None:
            raise RuntimeError("alpaca-py is not installed")

        self._api_key, self._secret_key = _load_creds()
        self._raw_http = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name="alpaca",
            priority=1,
            timeframes={"1min", "5min", "15min", "1day"},
            sessions={"rth", "extended"},
            adjustments={"raw", "split", "all"},
            max_lookback_days=None,
            requires_auth=True,
            is_free=False,
            # SIP feed = full consolidated tape; missing bars are
            # no-trade minutes, not data holes
            authoritative=True,
        )

    def _has_creds(self) -> bool:
        return bool(self._api_key and self._secret_key)

    @staticmethod
    def _filter_session(df: pd.DataFrame, session: str) -> pd.DataFrame:
        """Filter provider bars to the requested session."""
        if df.empty:
            return df
        if df.index.tz is None:
            df = df.tz_localize("UTC")
        # Left-closed [open, 16:00): a 16:00-labeled bar is the closing
        # auction print, which the calendar's expected-bar set never
        # contains — keep providers and calendar consistent.
        if session == "rth":
            df_ny = df.tz_convert(_TZ_NY).between_time("09:30", "15:59")
            return clip_to_session_close(df_ny.tz_convert("UTC"))
        if session == "extended":
            df_ny = df.tz_convert(_TZ_NY).between_time("04:00", "15:59")
            return clip_to_session_close(df_ny.tz_convert("UTC"))
        return df

    def _fetch_single(
        self,
        ticker: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        feed: str,
        adjustment: str,
    ) -> pd.DataFrame:
        """Fetch one non-chunked range from Alpaca."""
        # Map adjustment to Alpaca API parameter
        adj_param = adjustment if adjustment != "raw" else None

        return self._fetch_single_raw(ticker, timeframe, start, end, feed, adj_param)

    _TF_RAW = {"1min": "1Min", "5min": "5Min", "15min": "15Min", "1day": "1Day"}

    def _raw_session(self):
        if self._raw_http is None:
            import requests

            s = requests.Session()
            s.headers.update(
                {
                    "APCA-API-KEY-ID": self._api_key,
                    "APCA-API-SECRET-KEY": self._secret_key,
                    "Accept": "application/json",
                }
            )
            self._raw_http = s
        return self._raw_http

    def _fetch_single_raw(
        self,
        ticker: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        feed: str,
        adj_param: str | None,
    ) -> pd.DataFrame:
        """Fetch bars via the raw REST API, bypassing alpaca-py's response
        parsing.

        alpaca-py builds a pydantic model per bar; on bulk prefetches
        (~100k bars per ticker-year) that parsing is GIL-bound and caps
        whole-process throughput at roughly one ticker per worker-minute.
        Building the DataFrame straight from the JSON arrays is ~10x
        cheaper and returns the identical canonical frame.
        """
        session = self._raw_session()
        tf_str = self._TF_RAW[timeframe]
        url = f"https://data.alpaca.markets/v2/stocks/{ticker.upper()}/bars"

        def _iso(dt: datetime) -> str:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()

        params = {
            "timeframe": tf_str,
            "start": _iso(start),
            "end": _iso(end),
            "feed": feed,
            "limit": 10000,
        }
        if adj_param:
            params["adjustment"] = adj_param

        bars: list[dict] = []
        page_token = None
        rate_limit_hits = 0
        while True:
            if page_token:
                params["page_token"] = page_token
            elif "page_token" in params:
                del params["page_token"]
            _RATE_LIMITER.acquire()
            resp = session.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                rate_limit_hits += 1
                if rate_limit_hits > 8:
                    # Connection-class error ("Connection timeout" string):
                    # the prefetch re-queues the ticker for a retry round
                    # instead of recording a permanent data failure and
                    # punting the date to fallback providers mid-simulation.
                    raise ConnectionTimeoutError(
                        f"Connection timeout: Alpaca rate limit persisted "
                        f"for {ticker} after {rate_limit_hits} attempts"
                    )
                # Jittered exponential backoff so parallel workers don't
                # retry in lockstep; honor Retry-After as the floor.
                retry_after = float(resp.headers.get("Retry-After", 0) or 0)
                backoff = min(max(retry_after, 2.0 ** rate_limit_hits), 60.0)
                time.sleep(backoff + random.uniform(0, backoff / 4))
                continue
            if resp.status_code != 200:
                raise ProviderError(
                    f"Alpaca HTTP {resp.status_code} for {ticker}: {resp.text[:200]}"
                )
            payload = resp.json()
            bars.extend(payload.get("bars") or [])
            page_token = payload.get("next_page_token")
            if not page_token:
                break

        if not bars:
            return pd.DataFrame()

        idx = pd.DatetimeIndex(
            pd.to_datetime([b["t"] for b in bars], utc=True), name="timestamp"
        )
        df = pd.DataFrame(
            {
                "open": [b["o"] for b in bars],
                "high": [b["h"] for b in bars],
                "low": [b["l"] for b in bars],
                "close": [b["c"] for b in bars],
                "volume": [b["v"] for b in bars],
                "trade_count": [b.get("n") for b in bars],
                "vwap": [b.get("vw") for b in bars],
            },
            index=idx,
        )
        df["volume"] = df["volume"].fillna(0).astype("int64")
        return df

    def fetch_bars(
        self,
        ticker: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        session: str = "rth",
        adjustment: str = "raw",
    ) -> pd.DataFrame:
        """Fetch OHLCV bars from Alpaca SIP (consolidated feed only).

        Splits long ranges into 365-day chunks and concatenates.
        Falls through to the next provider in the chain on any error.
        Does NOT fall back to IEX — IEX is exchange-only and gives
        incomplete data.
        """
        if not self._has_creds():
            raise ProviderError("Alpaca credentials not configured")

        if timeframe not in self._TF_RAW:
            logger.warning("Unsupported timeframe %s for Alpaca", timeframe)
            return pd.DataFrame()

        # The subscription 403s on SIP queries touching the most recent
        # ~15 minutes, which would fail the WHOLE chunk and push the full
        # range to lower-priority providers (mixing a different tape into
        # the cache). Clamp instead: only genuinely-recent bars are
        # excluded, and they become fetchable on the next call.
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=16)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end > recent_cutoff:
            end = recent_cutoff
        if start >= end:
            return pd.DataFrame()

        feed = "sip"
        chunks: list[pd.DataFrame] = []
        cursor = start
        chunk_errors: list[Exception] = []
        attempted_chunks = 0

        while cursor < end:
            chunk_end = min(cursor + timedelta(days=_CHUNK_DAYS), end)
            attempted_chunks += 1
            try:
                df = retry_on_connection_error(
                    lambda: self._fetch_single(ticker, timeframe, cursor, chunk_end, feed, adjustment),
                    circuit_breaker=_BREAKER,
                )
                if not df.empty:
                    chunks.append(df)
            except ConnectionTimeoutError:
                raise  # network is down — abort, don't fall through
            except Exception as e:
                logger.warning("[Alpaca SIP] %s %s–%s: %s", ticker,
                               cursor.date(), chunk_end.date(), e)
                chunk_errors.append(e)
            # Half-open ranges: the next chunk starts exactly at chunk_end.
            # Advancing by chunk_end + 1 day skipped one full day of bars at
            # every 365-day boundary; the overlap bar is deduplicated below.
            cursor = chunk_end

        if not chunks:
            if chunk_errors and len(chunk_errors) == attempted_chunks:
                # Every chunk errored — surface the failure instead of
                # returning an empty frame, so the fetcher can distinguish
                # "provider confirmed no data" from "provider failed".
                raise ProviderError(
                    f"Alpaca: all {attempted_chunks} chunk(s) failed for "
                    f"{ticker} {timeframe}: {chunk_errors[-1]}"
                ) from chunk_errors[-1]
            return pd.DataFrame()

        combined = pd.concat(chunks)
        combined = combined[~combined.index.duplicated(keep="first")]
        # Session filtering: daily bars span the full trading day and their
        # timestamps are at midnight ET — ``between_time`` would drop them.
        if timeframe != "1day":
            combined = self._filter_session(combined.sort_index(), session)
        combined = combined.sort_index()

        if chunk_errors:
            # Some chunks succeeded and some failed. Returning the partial
            # frame as a normal response would let the fetcher negative-cache
            # the failed chunk's dates as "confirmed empty" for 24h. Raise
            # with the data attached so the caller can store what we got
            # while still treating the provider as errored.
            raise PartialDataError(
                f"Alpaca: {len(chunk_errors)}/{attempted_chunks} chunk(s) "
                f"failed for {ticker} {timeframe}: {chunk_errors[-1]}",
                df=combined,
            ) from chunk_errors[-1]
        return combined
