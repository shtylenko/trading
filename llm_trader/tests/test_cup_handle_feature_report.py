"""Contracts for the development-only cup-handle feature report."""

from __future__ import annotations

import json
from datetime import date

from trading.llm_trader.models import Entry
from trading.llm_trader.store import EntryStore


def test_feature_report_requires_complete_feature_and_portfolio_evidence(tmp_path, monkeypatch):
    from trading.llm_trader import batchsim
    from trading.llm_trader.strategies.cup_handle import feature_report

    tag = "dev-fixture"
    testset = tmp_path / "dev.json"
    testset.write_text(json.dumps({"cohort": {"start": "2025-01-01", "end": "2025-12-31"}}))
    db = tmp_path / "entries.db"
    with EntryStore(db) as store:
        store.upsert(Entry(
            ticker="AAA", day=date(2025, 2, 3), time_et="16:00", pattern="cup_handle",
            entry_px=10.0, bar_close=9.9, reason="fixture", strategy="cup_handle",
            features={
                "market_regime": {"schema_version": 1, "regime": "above_sma50_and_sma200"},
                "formation_quality": {
                    "definition": "formation_quality_v1_diagnostics_only", "score": 0.75,
                },
            },
        ))
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    (session_dir / "session.json").write_text(json.dumps({
        "batch": tag, "ticker": "AAA", "historical_date": "2025-02-03", "status": "complete",
    }))
    (session_dir / "pnl.json").write_text(json.dumps({
        "traded": True, "win": True, "realized_pnl": 525.0, "r_multiple": 1.05,
    }))
    batch_root = tmp_path / "batch"
    (batch_root / tag).mkdir(parents=True)
    (batch_root / tag / "portfolio.json").write_text(json.dumps({
        "source": {"batch_tag": tag},
        "accepted": [{
            "ticker": "AAA", "setup_day": "2025-02-03", "realized_pnl": 525.0,
            "r_multiple": 1.05,
        }],
        "skipped": [],
    }))

    monkeypatch.setattr(batchsim, "BATCH_LOGS", batch_root)
    monkeypatch.setattr(batchsim, "_sessions_for_batch", lambda _tag: [session_dir])
    monkeypatch.setattr(batchsim, "_read_batch_meta", lambda _tag: {
        "strategy": "cup_handle", "status": "complete", "decision_source": "deterministic_policy",
        "planned": 1, "testset": str(testset), "entry_db": str(db), "testset_hash": "fixture",
    })

    report, artifact = feature_report.generate_feature_report(tag, out=tmp_path / "report.json")

    assert artifact.exists()
    assert report["status"] == "development_only_descriptive_no_selection_rule"
    assert report["all_setups"] == {
        "setups": 1, "trades": 1, "wins": 1, "win_rate": 100.0,
        "independent_pnl": 525.0, "independent_effective_r": 1.05,
        "portfolio_accepted_trades": 1, "portfolio_accepted_pnl": 525.0,
        "portfolio_effective_r": 1.05, "portfolio_skipped_trades": 0,
    }
    assert report["by_market_regime"]["above_sma50_and_sma200"]["setups"] == 1
    assert report["by_formation_quality_band"]["high_>=0.70"]["setups"] == 1
