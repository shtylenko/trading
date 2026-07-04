"""Mocked tests for FloatCache and universe symbol fetch (no real network)."""

from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest

from trading.llm_trader.floats import FloatCache, _fetch_float
from trading.llm_trader.universe import fetch_symbols, _CACHE_TTL_S


def test_float_cache_passes_and_miss(tmp_path, monkeypatch):
    # Isolate cache file
    cache_file = tmp_path / "float_cache.json"
    monkeypatch.setattr("trading.llm_trader.floats._CACHE", cache_file)

    with patch("trading.llm_trader.floats._fetch_float",
               return_value=(8_000_000, "float")):
        fc = FloatCache()
        assert fc.get("LOWFLOAT") == 8_000_000
        assert fc.passes("LOWFLOAT", 20_000_000) is True
        assert fc.passes("LOWFLOAT", 5_000_000) is False
        # provenance is recorded in the cache entry
        assert fc._data["LOWFLOAT"]["source"] == "float"

    # Unknown float must FAIL the gate when active
    with patch("trading.llm_trader.floats._fetch_float",
               return_value=(None, None)):
        fc2 = FloatCache()
        assert fc2.passes("UNKNOWN", 10_000_000) is False
        assert fc2.passes("UNKNOWN", None) is True  # gate disabled


def test_float_fetch_falls_back_and_swallows_errors():
    yf_mock = MagicMock()
    ticker = MagicMock()
    ticker.info = {"sharesOutstanding": 123456}
    yf_mock.Ticker.return_value = ticker

    # Patch at sys.modules level because _fetch_float does a local "import yfinance as yf"
    import sys
    with patch.dict(sys.modules, {"yfinance": yf_mock}):
        # falls back to sharesOutstanding and tags the source accordingly
        assert _fetch_float("ANY") == (123456.0, "shares_outstanding")

    # true floatShares wins over sharesOutstanding and is tagged "float"
    real = MagicMock()
    rt = MagicMock()
    rt.info = {"floatShares": 5_000_000, "sharesOutstanding": 9_000_000}
    real.Ticker.return_value = rt
    with patch.dict(sys.modules, {"yfinance": real}):
        assert _fetch_float("REAL") == (5_000_000.0, "float")

    # force exception path inside the try: provide a module whose Ticker raises
    bad_yf = MagicMock()
    bad_yf.Ticker.side_effect = RuntimeError("boom from yf")
    with patch.dict(sys.modules, {"yfinance": bad_yf}):
        assert _fetch_float("BAD") == (None, None)


def test_universe_fetch_and_cache(tmp_path, monkeypatch):
    cache = tmp_path / "universe_symbols.json"
    monkeypatch.setattr("trading.llm_trader.universe._CACHE", cache)
    monkeypatch.setattr("trading.llm_trader.universe.DATA_DIR", tmp_path)

    fake_rows = [
        {"symbol": "AAOI", "type": "Common Stock", "mic": "XNAS"},
        {"symbol": "STEM", "type": "Common Stock", "mic": "XNAS"},
        {"symbol": "AAPL.W", "type": "Common Stock", "mic": "XNAS"},  # should be dropped (.)
        {"symbol": "XYZ", "type": "ETF", "mic": "XNAS"},  # dropped
    ]

    with patch("trading.llm_trader.universe.requests.get") as get:
        resp = MagicMock()
        resp.json.return_value = fake_rows
        resp.raise_for_status = lambda: None
        get.return_value = resp

        with patch.dict("os.environ", {"FINNHUB_API_KEY": "dummy"}):
            syms = fetch_symbols(("XNAS",), force=True)
            assert syms == ["AAOI", "STEM"]
            # cache written
            data = json.loads(cache.read_text())
            assert data["symbols"] == ["AAOI", "STEM"]


def test_universe_uses_cache_when_fresh(tmp_path, monkeypatch):
    cache = tmp_path / "universe_symbols.json"
    monkeypatch.setattr("trading.llm_trader.universe._CACHE", cache)
    monkeypatch.setattr("trading.llm_trader.universe.DATA_DIR", tmp_path)

    cache.write_text(json.dumps({
        "exchanges": ["XNAS"],
        "fetched_at": 9999999999,  # far future
        "symbols": ["CACHED"]
    }))

    with patch("trading.llm_trader.universe.requests.get") as get:
        syms = fetch_symbols(("XNAS",), force=False)
        assert syms == ["CACHED"]
        get.assert_not_called()
