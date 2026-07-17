"""Development-only report for causal cup-handle setup diagnostics.

This module intentionally describes feature/outcome relationships without
selecting, filtering, or reordering trades.  Its output is evidence for one
subsequent pre-registered portfolio hypothesis; it must never be mistaken for
an out-of-sample result or a new v0.7 decision rule.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from trading.llm_trader import batchsim, recorder
from trading.llm_trader.fsutils import atomic_write_json


QUALITY_BANDS = (
    ("low_<0.50", 0.0, 0.50),
    ("mid_0.50_to_<0.70", 0.50, 0.70),
    ("high_>=0.70", 0.70, 1.000001),
)


def _clean_session(session: dict[str, Any]) -> bool:
    return (
        session.get("status") == "complete"
        and not session.get("void")
        and not session.get("out_of_credits")
        and not session.get("timed_out")
        and not session.get("finalize_error")
        and not session.get("no_decision_log")
        and not session.get("agent_abandoned")
    )


def _new_group() -> dict[str, float | int]:
    return {
        "setups": 0,
        "trades": 0,
        "wins": 0,
        "independent_pnl": 0.0,
        "independent_r_sum": 0.0,
        "portfolio_accepted_trades": 0,
        "portfolio_accepted_pnl": 0.0,
        "portfolio_accepted_r_sum": 0.0,
        "portfolio_skipped_trades": 0,
    }


def _add_independent(group: dict[str, float | int], pnl: dict[str, Any]) -> None:
    group["setups"] += 1
    traded = bool(pnl.get("traded"))
    group["trades"] += int(traded)
    group["wins"] += int(traded and bool(pnl.get("win")))
    group["independent_pnl"] += float(pnl.get("realized_pnl") or 0.0)
    if traded:
        r_multiple = pnl.get("r_multiple")
        if not isinstance(r_multiple, (int, float)):
            raise RuntimeError("completed traded setup is missing numeric r_multiple")
        group["independent_r_sum"] += float(r_multiple)


def _add_portfolio(
    group: dict[str, float | int],
    portfolio_row: Optional[dict[str, Any]],
    skipped: bool,
) -> None:
    if skipped:
        group["portfolio_skipped_trades"] += 1
        return
    if portfolio_row is None:
        return
    group["portfolio_accepted_trades"] += 1
    group["portfolio_accepted_pnl"] += float(portfolio_row["realized_pnl"])
    group["portfolio_accepted_r_sum"] += float(portfolio_row["r_multiple"])


def _finalize(groups: dict[str, dict[str, float | int]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, group in sorted(groups.items()):
        setups = int(group["setups"])
        trades = int(group["trades"])
        result[name] = {
            "setups": setups,
            "trades": trades,
            "wins": int(group["wins"]),
            "win_rate": round(100 * int(group["wins"]) / trades, 1) if trades else None,
            "independent_pnl": round(float(group["independent_pnl"]), 2),
            "independent_effective_r": round(
                float(group["independent_r_sum"]) / setups, 3
            ) if setups else None,
            "portfolio_accepted_trades": int(group["portfolio_accepted_trades"]),
            "portfolio_accepted_pnl": round(float(group["portfolio_accepted_pnl"]), 2),
            # Keep the deployment denominator fixed at all setups, as in the
            # batch report.  A group with 0 accepted trades is therefore 0R.
            "portfolio_effective_r": round(
                float(group["portfolio_accepted_r_sum"]) / setups, 3
            ) if setups else None,
            "portfolio_skipped_trades": int(group["portfolio_skipped_trades"]),
        }
    return result


def _quality_band(score: float) -> str:
    for name, lower, upper in QUALITY_BANDS:
        if lower <= score < upper:
            return name
    raise RuntimeError(f"formation_quality score outside [0, 1]: {score}")


def _calendar_quarter(day: str) -> str:
    try:
        month = int(day[5:7])
        quarter = (month - 1) // 3 + 1
        if len(day) != 10 or month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"setup day must be YYYY-MM-DD, got {day!r}") from exc
    return f"{day[:4]}-Q{quarter}"


def _development_testset(meta: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(meta.get("testset") or ""))
    if not path.exists():
        raise RuntimeError("batch has no readable pinned testset")
    try:
        testset = json.loads(path.read_text(encoding="utf-8"))
        cohort = testset["cohort"]
        end = str(cohort["end"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("batch testset lacks a readable cohort contract") from exc
    if end > "2025-12-31":
        raise RuntimeError(
            "feature report is development-only and refuses a cohort after 2025-12-31"
        )
    return {"path": str(path), "cohort": cohort}


def _features_for_setups(db_path: Path, setups: set[tuple[str, str]]) -> dict[tuple[str, str], dict]:
    if not db_path.exists():
        raise RuntimeError(f"entry database does not exist: {db_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT ticker, date, features_json
            FROM entries
            WHERE strategy='cup_handle' AND pattern='cup_handle'
            """
        ).fetchall()
    finally:
        conn.close()
    features: dict[tuple[str, str], dict] = {}
    for ticker, day, raw in rows:
        key = (str(ticker).upper(), str(day))
        if key not in setups:
            continue
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid features_json for {key[0]} {key[1]}") from exc
        if key in features:
            raise RuntimeError(f"entry database has duplicate cup-handle setup {key}")
        features[key] = parsed
    missing = sorted(setups - set(features))
    if missing:
        sample = ", ".join(f"{ticker}_{day}" for ticker, day in missing[:5])
        raise RuntimeError(f"entry database is missing batch setup features: {sample}")
    return features


def _diagnostic_fields(features: dict, key: tuple[str, str]) -> tuple[str, float]:
    market = features.get("market_regime")
    quality = features.get("formation_quality")
    if not isinstance(market, dict) or market.get("schema_version") != 1:
        raise RuntimeError(f"{key[0]} {key[1]} lacks market_regime schema v1")
    if not isinstance(quality, dict) or quality.get("definition") != "formation_quality_v1_diagnostics_only":
        raise RuntimeError(f"{key[0]} {key[1]} lacks formation_quality_v1 diagnostics")
    regime = market.get("regime")
    score = quality.get("score")
    if not isinstance(regime, str) or not isinstance(score, (int, float)):
        raise RuntimeError(f"{key[0]} {key[1]} has invalid market/quality diagnostic values")
    return regime, float(score)


def generate_feature_report(
    tag: str,
    *,
    db_path: str | Path | None = None,
    out: str | Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Generate a strict, descriptive report for one completed dev batch.

    The report fails if the batch is not complete and deterministic, if a leaf
    is not clean, if any setup has no persisted feature evidence, or if a trade
    is neither accepted nor explicitly skipped by the portfolio replay.
    """
    meta = batchsim._read_batch_meta(tag)
    if meta.get("strategy") != "cup_handle":
        raise RuntimeError("feature report is currently cup_handle-only")
    if meta.get("status") != "complete":
        raise RuntimeError(f"batch {tag!r} is not complete")
    if meta.get("decision_source") != "deterministic_policy":
        raise RuntimeError("feature report requires a deterministic-policy batch")
    testset = _development_testset(meta)
    raw_db_path = db_path or meta.get("entry_db")
    if not raw_db_path:
        raise RuntimeError("feature report requires an entry database path")
    resolved_db = Path(raw_db_path)

    leaves: dict[tuple[str, str], tuple[Path, dict, dict]] = {}
    bad_leaves: list[str] = []
    for sdir in batchsim._sessions_for_batch(tag):
        session = recorder._load_json(sdir / "session.json", {}) or {}
        if session.get("batch") != tag:
            continue
        ticker = str(session.get("ticker") or "").upper()
        day = str(session.get("historical_date") or "")
        if not ticker or not day:
            bad_leaves.append(f"{sdir.name}: no setup identity")
            continue
        if not _clean_session(session):
            bad_leaves.append(f"{ticker}_{day}: non-clean session")
            continue
        key = (ticker, day)
        if key in leaves:
            bad_leaves.append(f"{ticker}_{day}: duplicate clean session")
            continue
        leaves[key] = (sdir, session, recorder._load_json(sdir / "pnl.json", {}) or {})
    if bad_leaves:
        raise RuntimeError("batch leaf-integrity failure: " + "; ".join(bad_leaves[:8]))
    planned = int(meta.get("planned") or 0)
    if not leaves or len(leaves) != planned:
        raise RuntimeError(
            f"batch leaf-integrity failure: expected {planned} clean leaves, found {len(leaves)}"
        )

    feature_map = _features_for_setups(resolved_db, set(leaves))
    portfolio_path = batchsim.BATCH_LOGS / tag / "portfolio.json"
    if not portfolio_path.exists():
        raise RuntimeError("feature report requires a completed portfolio replay artifact")
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    if portfolio.get("source", {}).get("batch_tag") != tag:
        raise RuntimeError("portfolio artifact belongs to a different batch")
    accepted = {
        (str(row["ticker"]).upper(), str(row["setup_day"])): row
        for row in portfolio.get("accepted", [])
    }
    skipped = {
        (str(row["ticker"]).upper(), str(row["setup_day"]))
        for row in portfolio.get("skipped", [])
    }
    if set(accepted) & skipped:
        raise RuntimeError("portfolio artifact marks a trade both accepted and skipped")

    market_groups: dict[str, dict[str, float | int]] = defaultdict(_new_group)
    quality_groups: dict[str, dict[str, float | int]] = defaultdict(_new_group)
    quarter_groups: dict[str, dict[str, float | int]] = defaultdict(_new_group)
    scores: list[float] = []
    all_group = _new_group()
    unclassified_trades: list[str] = []
    for key, (_sdir, _session, pnl) in leaves.items():
        regime, score = _diagnostic_fields(feature_map[key], key)
        scores.append(score)
        groups = (
            all_group,
            market_groups[regime],
            quality_groups[_quality_band(score)],
            quarter_groups[_calendar_quarter(key[1])],
        )
        for group in groups:
            _add_independent(group, pnl)
        if pnl.get("traded"):
            if key in accepted:
                for group in groups:
                    _add_portfolio(group, accepted[key], skipped=False)
            elif key in skipped:
                for group in groups:
                    _add_portfolio(group, None, skipped=True)
            else:
                unclassified_trades.append(f"{key[0]}_{key[1]}")
    if unclassified_trades:
        raise RuntimeError(
            "portfolio artifact does not classify traded setup(s): "
            + ", ".join(unclassified_trades[:8])
        )

    report = {
        "schema_version": 1,
        "status": "development_only_descriptive_no_selection_rule",
        "warning": (
            "These are in-sample development relationships. No quality threshold, regime "
            "filter, or portfolio-priority rule is selected by this report."
        ),
        "feature_contract": {
            "market_regime": "SPY daily close/SMA50/SMA200 at setup close, schema v1",
            "formation_quality": "formation_quality_v1_diagnostics_only",
            "quality_bands": [
                {"name": name, "lower_inclusive": lower, "upper_exclusive": upper}
                for name, lower, upper in QUALITY_BANDS
            ],
        },
        "source": {
            "batch_tag": tag,
            "entry_db": str(resolved_db),
            "portfolio_artifact": str(portfolio_path),
            "testset": testset,
            "testset_hash": meta.get("testset_hash"),
            "runner_contract": meta.get("runner_contract"),
        },
        "all_setups": _finalize({"all": all_group})["all"],
        "by_market_regime": _finalize(market_groups),
        "by_formation_quality_band": _finalize(quality_groups),
        "by_setup_quarter": _finalize(quarter_groups),
        "formation_quality_score": {
            "n": len(scores),
            "min": round(min(scores), 4),
            "max": round(max(scores), 4),
            "mean": round(sum(scores) / len(scores), 4),
        },
    }
    artifact = Path(out) if out else batchsim.BATCH_LOGS / tag / "feature_analysis.json"
    atomic_write_json(artifact, report, indent=2, sort_keys=True)
    return report, artifact


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Describe causal cup-handle feature/outcome relationships.")
    parser.add_argument("--tag", required=True, help="completed deterministic development batch tag")
    parser.add_argument("--db", help="entry database; defaults to the batch-pinned path")
    parser.add_argument("--out", help="output JSON (defaults to simulations/_batch/<tag>/feature_analysis.json)")
    args = parser.parse_args(argv)
    try:
        report, artifact = generate_feature_report(args.tag, db_path=args.db, out=args.out)
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    print(
        f"feature report: {report['all_setups']['setups']} setups; "
        f"independent effective R {report['all_setups']['independent_effective_r']:+.3f}; "
        f"wrote {artifact}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
