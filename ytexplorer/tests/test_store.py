from __future__ import annotations

from trading.ytexplorer.channel_audit import audit_samples, recommend_status
from trading.ytexplorer.store import ExplorerStore


def _video() -> dict:
    return {
        "video_id": "v1", "channel_identifier": "c1", "channel": "Channel One",
        "title": "A trading setup with VWAP", "url": "https://example.test/v1",
        "description": "Entry and stop rules", "published_date": "2026-07-18",
    }


def test_video_ingest_is_idempotent_and_creates_candidate_channel(tmp_path):
    store = ExplorerStore(tmp_path / "explorer.sqlite3")
    assert store.upsert_video(_video(), discovered_by="query:test") is True
    assert store.upsert_video(_video(), discovered_by="query:test") is False
    channel = store.get_channel("c1")
    assert channel and channel["status"] == "candidate"
    assert len(store.list_videos()) == 1


def test_claim_candidate_and_audit_workflow(tmp_path):
    store = ExplorerStore(tmp_path / "explorer.sqlite3")
    store.upsert_video(_video())
    store.set_transcript("v1", "Trading strategy entry, exit, risk and stop using VWAP")
    claim = store.add_claim(
        video_id="v1", claim_type="setup", summary="VWAP reclaim", evidence_quote="enter on reclaim",
        evidence_start=10, evidence_end=20, horizon="intraday", trigger_rule="reclaim", invalidation_rule="stop",
    )
    candidate = store.add_candidate(title="VWAP reclaim", summary="Testable after prior-art review", claim_id=claim, priority=10)
    store.transition_candidate(candidate, "data-blocked", actor="test", rationale="needs PIT data")
    assert store.get_candidate(candidate)["status"] == "data-blocked"
    assert store.candidate_events(candidate)[0]["rationale"] == "needs PIT data"

    sample = [_video() | {"transcript_text": "trading strategy entry exit stop risk"} for _ in range(12)]
    audit = audit_samples(sample)
    assert recommend_status(audit)[0] == "approved"
