"""Shared fixtures for trading.live P0 tests — an isolated env per test (no network)."""
from __future__ import annotations

import pytest

from trading.live.config import EnvConfig, load_env_config


@pytest.fixture()
def env(tmp_path, monkeypatch) -> EnvConfig:
    """A dev EnvConfig rooted in a temp dir (own DB, logs, state)."""
    monkeypatch.setenv("TRADING_ENV", "dev")
    monkeypatch.setenv("TRADING_LIVE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("TRADING_LIVE_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TRADING_LIVE_DB", str(tmp_path / "state" / "live.db"))
    return load_env_config()


@pytest.fixture()
def prod_env(tmp_path, monkeypatch) -> EnvConfig:
    monkeypatch.setenv("TRADING_ENV", "prod")
    monkeypatch.setenv("TRADING_LIVE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("TRADING_LIVE_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("TRADING_LIVE_DB", str(tmp_path / "state" / "live.db"))
    return load_env_config()


class FakeCandidate:
    def __init__(self, ticker, score, close, reason="r"):
        self.ticker = ticker
        self.score = score
        self.reason = reason
        self.features = {"close": close}


class FakeRelease:
    """Minimal release: returns a fixed ranked list, ignores the context."""
    release_id = "fake"
    strategy_letter = "z"
    strategy_alias = "fake_alias"
    top_n = 3

    def __init__(self, candidates):
        self._candidates = candidates

    def build_candidates(self, context):
        return list(self._candidates)

    def signature_inputs(self):
        return []


@pytest.fixture()
def fake_release():
    return FakeRelease([
        FakeCandidate("AAA", 0.9, 100.0),
        FakeCandidate("BBB", 0.8, 50.0),
        FakeCandidate("CCC", 0.7, 25.0),
        FakeCandidate("DDD", 0.6, 10.0),
    ])
