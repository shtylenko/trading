from __future__ import annotations

import json
import subprocess

import pytest

from trading.ytexplorer.metadata_screening import parse_screen_response
from trading.ytexplorer.llm_engine import (
    ExtractionError,
    HermesExtractor,
    build_evidence_fragments,
    promote_needs_detail,
    select_relevant_excerpt,
)
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


def test_hermes_repairs_a_paraphrased_quote_without_relaxing_provenance(tmp_path):
    store = _store_with_transcript(tmp_path)
    payload = {
        "disposition": "reference", "rationale": "A sourced rule.",
        "claims": [{"claim_type": "setup", "summary": "VWAP reclaim", "evidence_quote": "reclaim VWAP after pullback",
                    "horizon": "intraday", "trigger_rule": "reclaim", "invalidation_rule": "stop",
                    "required_data": ["OHLCV"], "missing_fields": [], "extract_confidence": 0.8}],
        "candidate": None,
    }
    repaired = payload | {"claims": [payload["claims"][0] | {
        "evidence_quote": "Wait for price to reclaim VWAP after a pullback."
    }]}
    responses = iter([json.dumps(payload), json.dumps(repaired)])

    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=next(responses), stderr="")

    result = HermesExtractor(store, runner=runner).extract("v1")
    assert result.status == "ok"
    assert store.claims_for_video("v1")[0]["evidence_quote"] == repaired["claims"][0]["evidence_quote"]


def test_missing_candidate_assumptions_becomes_needs_detail_with_repair(tmp_path):
    store = _store_with_transcript(tmp_path)
    payload = {
        "disposition": "candidate", "rationale": "Rules are substantially specified.",
        "claims": [{"claim_type": "setup", "summary": "VWAP reclaim", "evidence_quote": "Wait for price to reclaim VWAP after a pullback.",
                    "horizon": "intraday", "trigger_rule": "reclaim VWAP", "invalidation_rule": "stop below pullback",
                    "required_data": ["OHLCV"], "missing_fields": ["exit"], "extract_confidence": 0.8}],
        "candidate": {"claim_index": 0, "title": "VWAP reclaim", "summary": "Test reclaim.", "priority": 20,
                      "feasibility": "testable", "data_requirements": "intraday OHLCV", "prior_art": "unknown",
                      "structural_difference": "unknown"},
    }
    responses = iter([json.dumps(payload), json.dumps({"assumption_register": ["Freeze the exit rule."]})])

    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=next(responses), stderr="")

    result = HermesExtractor(store, runner=runner).extract("v1")
    candidate = store.get_candidate(result.candidate_id)
    assert candidate["status"] == "needs-detail"
    assert "Research assumption: Freeze the exit rule." in candidate["assumption_register"]


def test_recovery_promotes_stored_needs_detail_evidence_to_queue(tmp_path):
    store = _store_with_transcript(tmp_path)
    claim_id = store.add_claim(
        video_id="v1", claim_type="setup", summary="VWAP reclaim", evidence_quote="Wait for price to reclaim VWAP after a pullback.",
        trigger_rule="reclaim VWAP", required_data=["OHLCV"], missing_fields=["exit"], extract_confidence=0.8,
    )
    parsed = {"disposition": "needs-detail", "rationale": "Exit rule is missing.", "claims": []}
    store.record_extraction(video_id="v1", transcript_hash="hash", model=None, skill_hash="skill", prompt_hash="prompt",
                            status="ok", parsed=parsed)
    promoted = promote_needs_detail(store)
    candidate = store.get_candidate(promoted[0])
    assert candidate["claim_id"] == claim_id
    assert candidate["status"] == "needs-detail"
    assert "Freeze before testing: exit." in candidate["assumption_register"]


def test_relevant_excerpt_is_bounded_and_prefers_rule_dense_passage():
    bland = "general market commentary " * 1000
    useful = "entry trigger strategy stop loss VWAP pullback " * 250
    excerpt = select_relevant_excerpt(bland + useful, max_chars=9000)
    assert len(excerpt) <= 9000
    assert "entry trigger strategy" in excerpt


def test_evidence_fragments_are_exact_and_stable():
    text = "First source rule. " * 80
    fragments = build_evidence_fragments(text, max_chars=100)
    assert fragments[0]["id"] == "F001"
    assert all(fragment["text"] in text for fragment in fragments)


def test_metadata_screening_requires_one_valid_decision_per_video():
    raw = json.dumps({"decisions": [
        {"video_id": "a", "verdict": "process", "score": 80, "reason": "Explicit entry and stop in title."},
        {"video_id": "b", "verdict": "defer", "score": 20, "reason": "Generic course."},
    ]})
    decisions = parse_screen_response(raw, {"a", "b"})
    assert decisions["a"]["score"] == 80
    with pytest.raises(ValueError, match="every supplied video"):
        parse_screen_response(json.dumps({"decisions": []}), {"a"})


def test_extractor_accepts_json_fenced_by_model_commentary(tmp_path):
    store = _store_with_transcript(tmp_path)
    payload = {"disposition": "reference", "rationale": "Generic education.", "claims": [], "candidate": None}

    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout="Reasoning first.\n```json\n" + json.dumps(payload) + "\n```\nDone.", stderr="")

    assert HermesExtractor(store, runner=runner).extract("v1").status == "ok"


def test_extractor_keeps_first_three_valid_claims_when_model_exceeds_cap(tmp_path):
    store = _store_with_transcript(tmp_path)
    claim = {
        "claim_type": "setup", "summary": "VWAP reclaim", "evidence_quote": "Wait for price to reclaim VWAP after a pullback.",
        "horizon": "intraday", "trigger_rule": "reclaim", "invalidation_rule": "stop",
        "required_data": ["OHLCV"], "missing_fields": [], "extract_confidence": 0.8,
    }
    payload = {"disposition": "reference", "rationale": "Repeated evidence.", "claims": [claim, claim, claim, claim], "candidate": None}

    def runner(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    assert HermesExtractor(store, runner=runner).extract("v1").status == "ok"
    assert len(store.claims_for_video("v1")) == 3
