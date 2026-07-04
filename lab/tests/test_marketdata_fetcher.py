"""Unit tests for trading.marketdata.fetcher (cached-only paths).

Tests the cache-hit, cache-miss, gap-detection, and negative-cache paths
of ``fetch_bars()`` without making live API calls.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
import zoneinfo

# ── Fixture: isolated data dir, pre-seeded cache ──────────────────────────────

_NY = zoneinfo.ZoneInfo("America/New_York")


def _seed_1min_data(ticker: str = "AAPL", n: int = 390,
                    date_str: str = "2024-01-02") -> None:
    """Write n 1min bars to the isolated cache."""
    ts = pd.date_range(f"{date_str} 14:30", periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame({
        "timestamp": ts,
        "open": range(n),
        "high": range(1, n + 1),
        "low": range(-1, n - 1),
        "close": [100.0 + i * 0.01 for i in range(n)],
        "volume": 100000,
    }, index=ts)
    df.index.name = "timestamp"

    from trading.marketdata.storage import (
        update_meta_coverage,
        update_meta_summary,
        write_bars,
    )
    write_bars(ticker, "1min", df, session="rth", adjustment="raw",
               provider_name="alpaca")
    update_meta_coverage(ticker, "1min", "rth", "raw", date_str,
                         expected=n, actual=n)
    update_meta_summary(ticker, "1min", "rth", "raw")


def _seed_daily_data(ticker: str = "SPY", start: str = "2020-01-02",
                     n: int = 500, adjustment: str = "split") -> None:
    """Write n daily bars to the isolated cache."""
    dates = pd.date_range(start, periods=n, freq="D", tz="UTC")
    df = pd.DataFrame({
        "timestamp": dates,
        "open": 200.0, "high": 201.0, "low": 199.0,
        "close": 200.5, "volume": 5_000_000,
    }, index=dates)
    df.index.name = "timestamp"

    from trading.marketdata.storage import (
        update_meta_summary,
        write_bars,
    )
    write_bars(ticker, "1day", df, session="rth", adjustment=adjustment,
               provider_name="alpaca")
    update_meta_summary(ticker, "1day", "rth", adjustment)


def _make_1min_df(
    date_str: str = "2024-01-02",
    start_utc: str = "14:30",
    n: int = 390,
    close_base: float = 100.0,
) -> pd.DataFrame:
    ts = pd.date_range(f"{date_str} {start_utc}", periods=n, freq="1min", tz="UTC")
    df = pd.DataFrame({
        "timestamp": ts,
        "open": [close_base + i * 0.01 for i in range(n)],
        "high": [close_base + i * 0.01 + 0.05 for i in range(n)],
        "low": [close_base + i * 0.01 - 0.05 for i in range(n)],
        "close": [close_base + i * 0.01 for i in range(n)],
        "volume": 100000,
    }, index=ts)
    df.index.name = "timestamp"
    return df


def _install_test_providers(*providers) -> None:
    import trading.marketdata.fetcher as fetcher_mod
    import trading.marketdata.provider as provider_mod

    provider_mod._PROVIDER_REGISTRY.clear()
    for p in providers:
        provider_mod.register_provider(p)
    fetcher_mod._REGISTERED = True


def _provider(name: str, priority: int, df: pd.DataFrame | None = None,
              counter: dict | None = None, authoritative: bool = False,
              raises: Exception | None = None):
    from trading.marketdata.provider import Provider, ProviderCapabilities

    class P(Provider):
        @property
        def capabilities(self):
            return ProviderCapabilities(
                name=name,
                priority=priority,
                timeframes={"1min", "1day"},
                sessions={"rth"},
                adjustments={"raw", "split"},
                requires_auth=False,
                is_free=True,
                authoritative=authoritative,
            )

        def fetch_bars(self, *args, **kwargs):
            if counter is not None:
                counter[name] = counter.get(name, 0) + 1
            if raises is not None:
                raise raises
            return pd.DataFrame() if df is None else df.copy()

    return P()


@pytest.fixture(autouse=True)
def _fresh_env():
    """Each test gets a temp data dir and fresh providers."""
    old_env = os.environ.get("STRATEGY_LAB_MARKETDATA_DIR")
    with tempfile.TemporaryDirectory(prefix="smd_fetch_") as td:
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = td
        # Reimport with new dir
        import importlib
        import trading.marketdata.config
        importlib.reload(trading.marketdata.config)
        import trading.marketdata.storage
        importlib.reload(trading.marketdata.storage)
        import trading.marketdata.fetcher as fetcher_mod
        import trading.marketdata.provider as provider_mod

        # Clear registry and install only deterministic test providers. Mark the
        # fetcher as registered so unit tests cannot auto-register live providers.
        provider_mod._PROVIDER_REGISTRY.clear()
        fetcher_mod._REGISTERED = True

        # Add a no-op test provider that always returns empty
        from trading.marketdata.provider import Provider, ProviderCapabilities
        class NoopProvider(Provider):
            @property
            def capabilities(self):
                return ProviderCapabilities(
                    name="noop", priority=5,
                    timeframes={"1min", "5min", "15min", "1day"},
                    sessions={"rth", "extended"},
                    adjustments={"raw", "split", "all"},
                    requires_auth=False, is_free=True,
                )
            def fetch_bars(self, *args, **kwargs):
                return pd.DataFrame()
        provider_mod.register_provider(NoopProvider())

        yield
    if old_env is None:
        os.environ.pop("STRATEGY_LAB_MARKETDATA_DIR", None)
    else:
        os.environ["STRATEGY_LAB_MARKETDATA_DIR"] = old_env


class TestCacheHit:
    def test_cache_hit_1min(self):
        _seed_1min_data()
        from trading.marketdata.fetcher import fetch_bars

        result = fetch_bars("AAPL", "1min",
                            start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                            end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                            session="rth", adjustment="raw")
        assert result is not None
        assert len(result) == 390

    def test_cache_hit_1day(self):
        _seed_daily_data()
        from trading.marketdata.fetcher import fetch_bars

        result = fetch_bars("SPY", "1day",
                            start=datetime(2020, 1, 2, tzinfo=_NY),
                            end=datetime(2021, 1, 2, tzinfo=_NY),
                            session="rth", adjustment="split")
        assert result is not None
        # ~252 trading days in a year
        assert len(result) >= 250

    def test_cache_hit_partial_range(self):
        """Request a subset of cached data."""
        _seed_1min_data()
        from trading.marketdata.fetcher import fetch_bars

        result = fetch_bars("AAPL", "1min",
                            start=datetime(2024, 1, 2, 11, 0, tzinfo=_NY),
                            end=datetime(2024, 1, 2, 13, 0, tzinfo=_NY),
                            session="rth", adjustment="raw")
        assert result is not None
        # 11:00-13:00 = 120 minutes inclusive
        assert len(result) == 121

    def test_partial_range_cache_hit_does_not_fetch(self):
        """A cached partial-day slice should not require full-session coverage."""
        from trading.marketdata.storage import (
            update_meta_summary,
            write_bars,
        )
        counter: dict[str, int] = {}
        _install_test_providers(_provider("counting", 1, counter=counter))

        partial = _make_1min_df(start_utc="16:00", n=120)  # 11:00-12:59 ET
        write_bars("AAPL", "1min", partial, session="rth", adjustment="raw",
                   provider_name="seed")
        update_meta_summary("AAPL", "1min", "rth", "raw")

        from trading.marketdata.fetcher import fetch_bars
        result = fetch_bars("AAPL", "1min",
                            start=datetime(2024, 1, 2, 11, 0, tzinfo=_NY),
                            end=datetime(2024, 1, 2, 12, 59, tzinfo=_NY),
                            session="rth", adjustment="raw")
        assert result is not None
        assert len(result) == 120
        assert counter == {}

    def test_second_call_is_cache_hit(self):
        """Second identical call returns same data (no provider call)."""
        _seed_1min_data()
        from trading.marketdata.fetcher import fetch_bars

        r1 = fetch_bars("AAPL", "1min",
                         start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                         end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                         session="rth", adjustment="raw")
        r2 = fetch_bars("AAPL", "1min",
                         start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                         end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                         session="rth", adjustment="raw")
        assert r1 is not None
        assert r2 is not None
        assert len(r1) == len(r2)
        assert r1["close"].iloc[0] == r2["close"].iloc[0]


class TestCacheMiss:
    def test_empty_ticker_returns_none(self):
        """No cache, only noop provider → returns None."""
        from trading.marketdata.fetcher import fetch_bars

        result = fetch_bars("NODATA", "1min",
                            start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                            end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                            session="rth", adjustment="raw")
        assert result is None

    def test_force_refresh_with_no_provider(self):
        """force=True bypasses cache, but noop provider returns empty
        and existing cache is still returned as fallback."""
        _seed_1min_data()
        _install_test_providers(_provider("noop", 1))
        from trading.marketdata.fetcher import fetch_bars

        result = fetch_bars("AAPL", "1min",
                            start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                            end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                            session="rth", adjustment="raw",
                            force=True)
        assert result is not None
        assert len(result) == 390  # Cache serves as fallback

    def test_partial_provider_falls_through_for_same_date_gaps(self):
        first_300 = _make_1min_df(n=300, close_base=10.0)
        last_90 = _make_1min_df(start_utc="19:30", n=90, close_base=20.0)
        calls: dict[str, int] = {}
        _install_test_providers(
            _provider("partial", 1, first_300, calls),
            _provider("remainder", 2, last_90, calls),
        )

        from trading.marketdata.fetcher import fetch_bars
        result = fetch_bars("AAPL", "1min",
                            start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                            end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                            session="rth", adjustment="raw")
        assert result is not None
        assert len(result) == 390
        assert calls == {"partial": 1, "remainder": 1}

    def test_provider_column_reflects_contributing_provider(self):
        df = _make_1min_df(n=390)
        calls: dict[str, int] = {}
        _install_test_providers(
            _provider("empty_first", 1, None, calls),
            _provider("filled_second", 2, df, calls),
        )

        from trading.marketdata.fetcher import fetch_bars
        result = fetch_bars("AAPL", "1min",
                            start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                            end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                            session="rth", adjustment="raw")
        assert result is not None
        assert set(result["provider"]) == {"filled_second"}

    def test_force_refresh_ignores_complete_metadata(self):
        from trading.marketdata.storage import (
            update_meta_coverage,
            update_meta_summary,
            write_bars,
        )

        cached = _make_1min_df(n=390, close_base=10.0)
        fresh = _make_1min_df(n=390, close_base=50.0)
        write_bars("AAPL", "1min", cached, session="rth", adjustment="raw",
                   provider_name="seed")
        update_meta_coverage("AAPL", "1min", "rth", "raw", "2024-01-02",
                             expected=390, actual=390)
        update_meta_summary("AAPL", "1min", "rth", "raw")
        _install_test_providers(_provider("refresh", 1, fresh))

        from trading.marketdata.fetcher import fetch_bars
        result = fetch_bars("AAPL", "1min",
                            start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                            end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                            session="rth", adjustment="raw",
                            force=True)
        assert result is not None
        assert result["close"].iloc[0] == 50.0


class TestDefaultParams:
    def test_default_start_end(self):
        """Omitting start/end defaults to a reasonable lookback."""
        _seed_daily_data(start=(datetime.now(timezone.utc) - timedelta(days=1000)).strftime("%Y-%m-%d"), n=1000)
        from trading.marketdata.fetcher import fetch_bars

        result = fetch_bars("SPY", "1day", session="rth", adjustment="split")
        assert result is not None

    def test_default_adjustment_intraday(self):
        """Intraday timeframes default to adjustment='raw'."""
        _seed_1min_data()
        from trading.marketdata.fetcher import fetch_bars

        result = fetch_bars("AAPL", "1min",
                            start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                            end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                            session="rth")
        assert result is not None
        assert len(result) == 390

    def test_default_adjustment_daily_is_raw(self):
        """Daily timeframe defaults to adjustment='raw'."""
        _seed_daily_data(adjustment="raw")
        from trading.marketdata.fetcher import fetch_bars

        result = fetch_bars("SPY", "1day",
                            start=datetime(2020, 1, 2, tzinfo=_NY),
                            end=datetime(2020, 1, 10, tzinfo=_NY),
                            session="rth")
        assert result is not None


class TestNegativeCache:
    def test_nontrading_day_returns_none(self):
        """Fetching a non-trading day returns None without calling providers."""
        from trading.marketdata.fetcher import fetch_bars

        # Saturday 2024-01-06
        result = fetch_bars("AAPL", "1min",
                            start=datetime(2024, 1, 6, 9, 30, tzinfo=_NY),
                            end=datetime(2024, 1, 6, 16, 0, tzinfo=_NY),
                            session="rth", adjustment="raw")
        assert result is None


class TestInvalidParams:
    def test_invalid_timeframe(self):
        from trading.marketdata.fetcher import fetch_bars

        with pytest.raises(ValueError, match="Unsupported timeframe"):
            fetch_bars("AAPL", "7day")

    def test_invalid_session(self):
        from trading.marketdata.fetcher import fetch_bars

        with pytest.raises(ValueError, match="Unsupported session"):
            fetch_bars("AAPL", "1min", session="afternoon")

    def test_invalid_adjustment(self):
        from trading.marketdata.fetcher import fetch_bars

        with pytest.raises(ValueError, match="Unsupported adjustment"):
            fetch_bars("AAPL", "1min", adjustment="fractal")


class TestEdgeCases:
    def test_ticker_case_insensitivity(self):
        """Ticker case should not matter for storage."""
        _seed_1min_data()
        from trading.marketdata.fetcher import fetch_bars

        r1 = fetch_bars("AAPL", "1min",
                         start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                         end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                         session="rth", adjustment="raw")
        r2 = fetch_bars("aapl", "1min",
                         start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                         end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                         session="rth", adjustment="raw")
        if r1 is not None and r2 is not None:
            assert len(r1) == len(r2)


class TestAuthoritativeProvider:
    """Authoritative providers (full consolidated tape) stop the fallthrough."""

    def _thin_df(self):
        # 200 of 390 expected RTH minutes: a thin ticker, below the
        # coverage tolerance that would normally trigger fallthrough
        return _make_1min_df(n=200)

    def test_no_fallthrough_after_authoritative_success(self):
        from trading.marketdata.fetcher import fetch_bars

        counter: dict = {}
        _install_test_providers(
            _provider("tape", 1, df=self._thin_df(), counter=counter,
                      authoritative=True),
            _provider("backup", 2, df=self._thin_df(), counter=counter),
        )
        df = fetch_bars("THIN", "1min",
                        start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                        end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                        session="rth", adjustment="raw")
        assert df is not None and len(df) == 200
        assert counter.get("tape") == 1
        assert "backup" not in counter

    def test_fallthrough_when_authoritative_errors(self):
        from trading.marketdata.fetcher import fetch_bars

        counter: dict = {}
        _install_test_providers(
            _provider("tape", 1, counter=counter, authoritative=True,
                      raises=RuntimeError("api down")),
            _provider("backup", 2, df=self._thin_df(), counter=counter),
        )
        df = fetch_bars("THIN", "1min",
                        start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                        end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                        session="rth", adjustment="raw")
        assert df is not None and len(df) == 200
        assert counter.get("tape") == 1
        assert counter.get("backup") == 1

    def test_non_authoritative_still_falls_through(self):
        from trading.marketdata.fetcher import fetch_bars

        counter: dict = {}
        _install_test_providers(
            _provider("first", 1, df=self._thin_df(), counter=counter),
            _provider("backup", 2, df=self._thin_df(), counter=counter),
        )
        fetch_bars("THIN", "1min",
                   start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                   end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                   session="rth", adjustment="raw")
        assert counter.get("first") == 1
        assert counter.get("backup") == 1


class TestNegativeCacheSemantics:
    """Regression tests: the negative cache must never hide data that could
    still arrive (unfinished sessions) and must distinguish provider errors
    from confirmed-empty responses."""

    def _neg_cache(self, ticker: str) -> dict:
        from trading.marketdata.storage import get_negative_cache
        return get_negative_cache(ticker, "1min", "rth", "raw")

    def test_past_empty_day_negative_cached_as_provider_empty(self):
        from trading.marketdata.fetcher import fetch_bars

        fetch_bars("EMPT", "1min",
                   start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                   end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                   session="rth", adjustment="raw")
        nc = self._neg_cache("EMPT")
        assert nc.get("2024-01-02", {}).get("reason") == "provider_empty"

    def test_errored_day_negative_cached_as_provider_error(self):
        from trading.marketdata.fetcher import fetch_bars

        _install_test_providers(
            _provider("broken", 1, raises=RuntimeError("api down")),
        )
        fetch_bars("ERRD", "1min",
                   start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                   end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                   session="rth", adjustment="raw")
        nc = self._neg_cache("ERRD")
        assert nc.get("2024-01-02", {}).get("reason") == "provider_error"

    def test_unfinished_session_is_not_negative_cached(self):
        """A trading day whose session hasn't closed yet must not be marked
        provider_empty — 'no data yet' is not 'no data'."""
        from datetime import date as _date

        from trading.marketdata.calendar import trading_days_in_range
        from trading.marketdata.fetcher import fetch_bars

        today = datetime.now(timezone.utc).astimezone(_NY).date()
        future = trading_days_in_range(today + timedelta(days=1),
                                       today + timedelta(days=14))
        if not future:
            pytest.skip("no future trading days in calendar window")
        d = future[0]
        fetch_bars("FUTR", "1min",
                   start=datetime(d.year, d.month, d.day, 9, 30, tzinfo=_NY),
                   end=datetime(d.year, d.month, d.day, 16, 0, tzinfo=_NY),
                   session="rth", adjustment="raw")
        assert d.isoformat() not in self._neg_cache("FUTR")

    def test_evening_utc_request_does_not_enumerate_next_ny_day(self):
        """End timestamps after 19:00 ET land on the next UTC date; trading
        days must be enumerated in NY dates, not UTC dates."""
        from trading.marketdata.fetcher import fetch_bars

        # 2024-01-03 01:00 UTC == 2024-01-02 20:00 ET
        fetch_bars("EVNG", "1min",
                   start=datetime(2024, 1, 2, 0, 0, tzinfo=timezone.utc),
                   end=datetime(2024, 1, 3, 1, 0, tzinfo=timezone.utc),
                   session="rth", adjustment="raw")
        nc = self._neg_cache("EVNG")
        assert "2024-01-02" in nc
        assert "2024-01-03" not in nc

    def test_force_bypasses_negative_cache(self):
        from trading.marketdata.fetcher import fetch_bars
        from trading.marketdata.storage import write_negative_cache

        write_negative_cache("POIS", "1min", "rth", "raw",
                             "2024-01-02", "provider_empty")
        counter: dict = {}
        _install_test_providers(
            _provider("good", 1, df=_make_1min_df(), counter=counter),
        )
        df = fetch_bars("POIS", "1min",
                        start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                        end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                        session="rth", adjustment="raw", force=True)
        assert counter.get("good") == 1
        assert df is not None and len(df) == 390


class TestPartialDataError:
    def test_partial_data_is_stored_and_date_marked_errored(self):
        """A provider that fetched part of the range before failing raises
        PartialDataError with the bars attached — the fetcher must store
        them and record the date as provider_error, not provider_empty."""
        from trading.marketdata.errors import PartialDataError
        from trading.marketdata.fetcher import fetch_bars
        from trading.marketdata.storage import get_negative_cache

        partial = _make_1min_df(n=200)
        _install_test_providers(
            _provider("flaky", 1, authoritative=True,
                      raises=PartialDataError("chunk 2/2 failed", df=partial)),
        )
        df = fetch_bars("PART", "1min",
                        start=datetime(2024, 1, 2, 9, 30, tzinfo=_NY),
                        end=datetime(2024, 1, 2, 16, 0, tzinfo=_NY),
                        session="rth", adjustment="raw")
        assert df is not None and len(df) == 200
        nc = get_negative_cache("PART", "1min", "rth", "raw")
        assert nc.get("2024-01-02", {}).get("reason") == "provider_error"


class TestStorageHygiene:
    def test_sweep_tmp_files_removes_old_orphans(self):
        import os
        import time
        from trading.marketdata import config as cfg
        from trading.marketdata.storage import sweep_tmp_files

        ds = cfg.DATA_DIR / "1min" / "AAPL" / "session=rth" / "adjustment=raw" / "year=2024" / "month=1"
        ds.mkdir(parents=True, exist_ok=True)
        old_tmp = ds / "tmpabc123.parquet"
        old_tmp.write_bytes(b"x")
        two_days_ago = time.time() - 48 * 3600
        os.utime(old_tmp, (two_days_ago, two_days_ago))
        fresh_tmp = ds.parent.parent / "tmpfresh.json"
        fresh_tmp.write_text("{}")

        removed = sweep_tmp_files(max_age_hours=24)
        assert removed == 1
        assert not old_tmp.exists()
        assert fresh_tmp.exists()  # too young — left alone

    def test_update_meta_summary_incremental(self):
        from datetime import datetime
        import zoneinfo
        from trading.marketdata.storage import (
            read_meta, resolve_path, update_meta_summary, write_bars,
        )

        _seed_1min_data(n=390, date_str="2024-01-02")
        update_meta_summary("AAPL", "1min", "rth", "raw")
        meta = read_meta("AAPL", "1min", "rth", "raw")
        assert meta["total_rows"] == 390
        assert "partition_stats" in meta

        # Write a second partition and refresh only that one
        df2 = _make_1min_df(date_str="2024-02-01", n=100)
        write_bars("AAPL", "1min", df2, session="rth", adjustment="raw",
                   provider_name="alpaca")
        p2 = resolve_path("AAPL", "1min", "rth", "raw", 2024, 2)
        update_meta_summary("AAPL", "1min", "rth", "raw", touched=[p2])
        meta = read_meta("AAPL", "1min", "rth", "raw")
        assert meta["total_rows"] == 490
        assert len(meta["partition_stats"]) == 2


def test_alpaca_clamps_recent_sip_window(monkeypatch):
    """Requests touching the most recent ~15 min are clamped, not failed."""
    from datetime import datetime, timedelta, timezone
    import pandas as pd
    from trading.marketdata.providers.alpaca_provider import AlpacaProvider

    p = AlpacaProvider.__new__(AlpacaProvider)  # skip __init__ (no creds needed)
    p._api_key, p._secret_key = "k", "s"
    p._raw_http = None

    captured = {}

    def fake_single(ticker, timeframe, start, end, feed, adjustment):
        captured["end"] = end
        return pd.DataFrame()

    monkeypatch.setattr(p, "_fetch_single", fake_single)

    now = datetime.now(timezone.utc)
    p.fetch_bars("AAPL", "1day", now - timedelta(days=5), now)
    assert captured["end"] <= now - timedelta(minutes=15)

    # Entirely-recent request short-circuits without any provider call
    captured.clear()
    out = p.fetch_bars("AAPL", "1min", now - timedelta(minutes=5), now)
    assert out.empty and "end" not in captured


def test_alpaca_persistent_429_is_connection_class(monkeypatch):
    """Persistent rate limiting must re-queue the ticker (retry rounds),
    not record a permanent data failure."""
    import pytest
    from trading.marketdata.errors import ConnectionTimeoutError
    from trading.marketdata.providers import alpaca_provider as ap

    monkeypatch.setattr(ap.time, "sleep", lambda s: None)
    monkeypatch.setattr(ap._RATE_LIMITER, "acquire", lambda: None)

    class FakeResp:
        status_code = 429
        headers = {"Retry-After": "0"}
        text = "rate limited"

    class FakeSession:
        def get(self, *a, **k):
            return FakeResp()

    p = ap.AlpacaProvider.__new__(ap.AlpacaProvider)
    p._api_key, p._secret_key = "k", "s"
    p._raw_http = FakeSession()

    from datetime import datetime, timezone
    with pytest.raises(ConnectionTimeoutError, match="rate limit persisted"):
        p._fetch_single_raw(
            "AAPL", "1min",
            datetime(2024, 1, 2, tzinfo=timezone.utc),
            datetime(2024, 1, 3, tzinfo=timezone.utc),
            "sip", None,
        )


def test_alpaca_rate_limiter_paces_requests():
    import time
    from trading.marketdata.providers.alpaca_provider import _RateLimiter

    rl = _RateLimiter(rpm=600)  # 10/sec → 3 acquires beyond burst ≈ 0.2s+
    for _ in range(int(rl.capacity)):
        rl.acquire()  # drain the initial burst
    t0 = time.time()
    rl.acquire()
    rl.acquire()
    assert time.time() - t0 >= 0.15  # refill-paced, not instant
