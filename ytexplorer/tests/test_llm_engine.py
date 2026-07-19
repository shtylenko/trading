from __future__ import annotations

import json
import subprocess

import pytest

from trading.ytexplorer.llm_engine import ExtractionError, HermesExtractor
from trading.ytexplorer.store import ExplorerStore


def _store_with_transcript(tmp_path):
    store = ExplorerStore(tmp_path / "explorer.sqlite3")
    store.upsert_video({"video_id": "v1", "channel_identifier": "c1", "channel": "Channel One", "title": "Video"})
    store.set_transcript("v1", "Wait for price to reclaim VWAP after a pullback. Place the stop below the pullback low.")
    return store


def test_hermes_output_is_validated_then_becomes_claim_and_triage_candidate(tmp_path):
    store = _store_with_transcript(tmp_path)
    payload = {
        "disposition": "candidate", "rationale": "A stated trigger and invalidation are present.",
        "claims": [{
            "claim_type": "setup", "summary": "VWAP reclaim after pullback", "evidence_start": None,
            "evidence_end": None, "evidence_quote": "Wait for price to reclaim VWAP after a pullback.",
            "horizon": "intraday", "trigger_rule": "reclaim VWAP after pullback",
            "invalidation_rule": "stop below pullback low", "required_data": ["intraday OHLCV"],
            "missing_fields": ["exit"], "extract_confidence": 0.9,
        }],
        "candidate": {
            "claim_index": 0, "title": "VWAP reclaim", "summary": "Test a reclaim after pullback.",
            "priority": 40, "feasibility": "needs-detail", "data_requirements": "intraday OHLCV",
            "prior_art": "needs prior-art check", "structural_difference": "not established",
            "assumption_register": "Freeze exit rules before testing",
        },
    }
    seen = {}

    def runner(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    result = HermesExtractor(store, runner=runner).extract("v1", model="test-model")
    assert result.status == "ok"
    assert result.disposition == "candidate"
    assert "video-hypothesis-extractor" in seen["cmd"][2]
    assert len(store.claims_for_video("v1")) == 1
    assert store.get_candidate(result.candidate_id)["status"] == "triage"
    assert HermesExtractor(store, runner=runner).extract("v1").skipped is True


def test_hermes_cannot_cite_text_missing_from_transcript(tmp_path):
    store = _store_with_transcript(tmp_path)
    payload = {
        "disposition": "reference", "rationale": "Generic advice.",
        "claims": [{"claim_type": "setup", "summary": "Bad", "evidence_quote": "invented quote",
                    "horizon": "unknown", "trigger_rule": None, "invalidation_rule": None,
                    "required_data": [], "missing_fields": [], "extract_confidence": 0.5}],
        "candidate": None,
    }

    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    with pytest.raises(ExtractionError, match="not an exact transcript excerpt"):
        HermesExtractor(store, runner=runner).extract("v1")
    assert store.extractions_for_video("v1")[0]["status"] == "invalid"
