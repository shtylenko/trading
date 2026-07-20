from __future__ import annotations

from datetime import date

from trading.ytexplorer.cli import _launch_agent_payload, _web_launch_agent_payload
from trading.ytexplorer.pipeline import load_plan, rank_video_for_research, run_scheduled
from trading.ytexplorer.scope import long_only_scope
from trading.ytexplorer.store import ExplorerStore


def test_daily_plan_is_visible_and_dry_run_has_no_provider_side_effects(tmp_path):
    plan = load_plan()
    assert any(q.cadence == "daily" for q in plan["queries"])
    report = run_scheduled(ExplorerStore(tmp_path / "explorer.sqlite3"), cadence="daily", dry_run=True)
    assert report["mode"] == "dry-run"
    assert all(q["cadence"] == "daily" for q in report["queries"])


def test_due_run_includes_all_daily_queries(tmp_path):
    report = run_scheduled(ExplorerStore(tmp_path / "explorer.sqlite3"), cadence="due", dry_run=True,
                           as_of=date(2026, 7, 20))  # Monday
    cadences = {q["cadence"] for q in report["queries"]}
    assert cadences == {"daily"}
    assert len(report["queries"]) == 13


def test_launch_agent_payload_runs_the_workspace_wrapper(tmp_path):
    payload = _launch_agent_payload(tmp_path / "run_daily.sh", tmp_path / "logs", 6, 5)
    assert payload["Label"] == "com.trading.ytexplorer.daily"
    assert payload["StartCalendarInterval"] == {"Hour": 6, "Minute": 5}
    web = _web_launch_agent_payload(tmp_path / "run_web.sh", tmp_path / "logs")
    assert web["RunAtLoad"] is True
    assert web["KeepAlive"] is True


def test_metadata_ranker_favors_explicit_rules_over_promotional_language():
    rules_score, _ = rank_video_for_research({"title": "VWAP entry, exit and stop loss rules", "description": "backtest setup"})
    noise_score, _ = rank_video_for_research({"title": "Guaranteed 90% win trading signals", "description": ""})
    assert rules_score > noise_score


def test_long_only_scope_excludes_futures_options_and_short_selling():
    for title in ("VWAP futures strategy", "Options income strategy", "Short selling setup with stops"):
        assert long_only_scope({"title": title})[0] is False
    assert long_only_scope({"title": "Long-only stock swing trading strategy"})[0] is True
