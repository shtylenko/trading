from __future__ import annotations

import pytest

pytest.importorskip("httpx", reason="FastAPI TestClient optional test dependency")

from fastapi.testclient import TestClient

from trading.ytexplorer.store import ExplorerStore
from trading.ytexplorer.web.app import create_app


def test_dashboard_and_candidate_page_share_store(tmp_path):
    path = tmp_path / "explorer.sqlite3"
    store = ExplorerStore(path)
    store.upsert_video({
        "video_id": "v1", "channel_identifier": "c1", "channel": "Channel One",
        "title": "Trading rules", "url": "https://example.test/v1",
    })
    claim = store.add_claim(video_id="v1", claim_type="setup", summary="Rule", evidence_quote="quoted rule")
    candidate = store.add_candidate(title="Candidate one", summary="A testable thesis", claim_id=claim, priority=42)
    client = TestClient(create_app(path))

    assert client.get("/").status_code == 200
    detail = client.get(f"/candidates/{candidate}")
    assert detail.status_code == 200
    assert "Candidate one" in detail.text
    response = client.post(f"/candidates/{candidate}/transition", data={"status": "parked", "rationale": "duplicate"})
    assert response.status_code == 200
    assert store.get_candidate(candidate)["status"] == "parked"
