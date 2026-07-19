from __future__ import annotations

from trading.ytexplorer.cli import _launch_agent_payload
from trading.ytexplorer.pipeline import load_plan, run_scheduled
from trading.ytexplorer.store import ExplorerStore


def test_daily_plan_is_visible_and_dry_run_has_no_provider_side_effects(tmp_path):
    plan = load_plan()
    assert any(q.cadence == "daily" for q in plan["queries"])
    report = run_scheduled(ExplorerStore(tmp_path / "explorer.sqlite3"), cadence="daily", dry_run=True)
    assert report["mode"] == "dry-run"
    assert all(q["cadence"] == "daily" for q in report["queries"])


def test_launch_agent_payload_runs_the_workspace_wrapper(tmp_path):
    payload = _launch_agent_payload(tmp_path / "run_daily.sh", tmp_path / "logs", 6, 5)
    assert payload["Label"] == "com.trading.ytexplorer.daily"
    assert payload["StartCalendarInterval"] == {"Hour": 6, "Minute": 5}
