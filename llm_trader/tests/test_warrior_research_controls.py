"""Integrity contracts for Warrior's non-PIT historical research path."""

from __future__ import annotations

import json
from datetime import date

from trading.llm_trader import batchsim
from trading.llm_trader.strategies.warrior.forward_shadow import ForwardShadowLedger
from trading.llm_trader.strategies.warrior.screen import GapCandidate


def test_warrior_historical_tier_is_explicitly_non_promotable(tmp_path):
    provenance, tier = batchsim._warrior_research_tier(
        tmp_path / "historical.json", [{"ticker": "TEST"}]
    )
    assert tier == "exploratory_non_pit_float"
    assert provenance["point_in_time_float"] is False
    assert provenance["warning"] == "NON_PIT_FLOAT"


def test_forward_shadow_ledger_captures_contemporaneous_float_inputs(tmp_path):
    ledger = ForwardShadowLedger(tmp_path / "forward.jsonl")
    candidate = GapCandidate(
        "TEST", date(2026, 7, 23), 5.0, 4.0, 25.0, 4.0, 250_000, 1_000_000
    )
    record = ledger.record_candidate(
        scan_id="frozen-window-1",
        candidate=candidate,
        float_snapshot={
            "value": 4_000_000,
            "source": "float",
            "fetched_at": "2026-07-23T13:30:00+00:00",
            "as_of": "retrieval_time_current_snapshot",
            "point_in_time": False,
            "fallback_used": False,
        },
        float_gate_passed=True,
        config={"float_max": 20_000_000, "rvol_lookback": 20},
    )
    persisted = json.loads((tmp_path / "forward.jsonl").read_text().strip())
    assert persisted["record_sha256"] == record["record_sha256"]
    assert persisted["scanner_inputs"]["prior_day_volume_ratio"] == 4.0
    assert persisted["research_tier"] == "forward_shadow_pending_outcomes"
