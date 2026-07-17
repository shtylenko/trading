"""Development-only counterfactuals for explicit frozen-plan execution vetoes.

This evaluates a veto against the exact sealed baseline leaves.  It never
rescans the detector and therefore cannot introduce the cooldown/replacement
effect that a scanner-level filter would have.  A vetoed leaf becomes a 0R
stand-down while its original setup remains in the denominator.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Optional

from trading.llm_trader import batchsim, recorder
from trading.llm_trader.fsutils import atomic_write_json

from . import portfolio
from .feature_report import _clean_session, _development_testset, _features_for_setups


POLICY_ID = "spy_above_sma50_and_sma200_frozen_plan_veto_v1"


def _passes_veto(features: dict, key: tuple[str, str]) -> bool:
    market = features.get("market_regime")
    if not isinstance(market, dict) or market.get("schema_version") != 1:
        raise RuntimeError(f"{key[0]} {key[1]} lacks market_regime schema v1")
    values = (market.get("above_sma50"), market.get("above_sma200"))
    if not all(isinstance(value, bool) for value in values):
        raise RuntimeError(f"{key[0]} {key[1]} has incomplete SPY regime booleans")
    return all(values)


def replay_spy_above_both_veto(
    tag: str,
    *,
    db_path: str | Path | None = None,
    out: str | Path | None = None,
) -> tuple[dict[str, Any], Path]:
    """Evaluate the predeclared SPY>SMA50 and SPY>SMA200 frozen-plan veto.

    This is a development-only counterfactual.  It intentionally retains every
    baseline setup, converting vetoed setups into clean no-trades, so effective
    R remains comparable to the 569-setup baseline.  It must not be promoted or
    run on the untouched holdout until this policy is frozen.
    """
    meta = batchsim._read_batch_meta(tag)
    if meta.get("strategy") != "cup_handle" or meta.get("status") != "complete":
        raise RuntimeError("veto replay requires a completed cup_handle batch")
    if meta.get("decision_source") != "deterministic_policy":
        raise RuntimeError("veto replay requires a deterministic-policy batch")
    testset = _development_testset(meta)
    raw_db_path = db_path or meta.get("entry_db")
    if not raw_db_path:
        raise RuntimeError("veto replay requires an entry database path")
    resolved_db = Path(raw_db_path)

    chosen: dict[tuple[str, str], tuple[Path, dict, dict]] = {}
    errors: list[str] = []
    for sdir in batchsim._sessions_for_batch(tag):
        session = recorder._load_json(sdir / "session.json", {}) or {}
        if session.get("batch") != tag:
            continue
        ticker = str(session.get("ticker") or "").upper()
        setup_day = str(session.get("historical_date") or "")
        if not ticker or not setup_day or not _clean_session(session):
            errors.append(sdir.name)
            continue
        key = (ticker, setup_day)
        if key in chosen:
            errors.append(f"duplicate {ticker}_{setup_day}")
            continue
        chosen[key] = (sdir, session, recorder._load_json(sdir / "pnl.json", {}) or {})
    expected = int(meta.get("planned") or 0) // int(meta.get("repeats") or 1)
    if errors or len(chosen) != expected:
        detail = ", ".join(errors[:5]) if errors else f"found {len(chosen)}, expected {expected}"
        raise RuntimeError(f"veto replay requires one clean leaf per setup: {detail}")

    features = _features_for_setups(resolved_db, set(chosen))
    leaves: list[dict[str, Any]] = []
    vetoed: list[tuple[str, str]] = []
    for key in sorted(chosen):
        sdir, session, pnl = chosen[key]
        if _passes_veto(features[key], key):
            leaves.append({
                "sid": sdir.name,
                "ticker": session["ticker"],
                "setup_day": session["historical_date"],
                "pnl": pnl,
                "actions": recorder._load_json(sdir / "actions.json", []) or [],
            })
        else:
            # A plan-date veto writes no order. Preserve the baseline setup's
            # denominator, but do not replay its old actions or P&L.
            leaves.append({
                "sid": sdir.name,
                "ticker": session["ticker"],
                "setup_day": session["historical_date"],
                "pnl": {"traded": False},
                "actions": [],
            })
            vetoed.append(key)

    baseline_path = batchsim.BATCH_LOGS / tag / "portfolio.json"
    if not baseline_path.exists():
        raise RuntimeError("veto replay requires the baseline portfolio artifact")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    config = portfolio.PortfolioConfig(**dict(baseline.get("config") or {}))
    result = portfolio.replay(leaves, config)
    result["counterfactual"] = {
        "status": "development_only_not_a_strategy_change",
        "policy_id": POLICY_ID,
        "policy": "stand down when plan-date SPY is not above both SMA50 and SMA200",
        "evaluation": "frozen baseline plans only; vetoes do not permit replacement arms",
        "baseline_batch": tag,
        "vetoed_setups": len(vetoed),
        "retained_setups": len(leaves) - len(vetoed),
        "testset": testset,
    }
    result["baseline_summary"] = baseline.get("summary")
    artifact = Path(out) if out else batchsim.BATCH_LOGS / tag / f"{POLICY_ID}.json"
    atomic_write_json(artifact, result, indent=2, sort_keys=True)
    return result, artifact


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the frozen-plan SPY-above-both veto.")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--db", help="entry database; defaults to the batch-pinned path")
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    try:
        result, artifact = replay_spy_above_both_veto(args.tag, db_path=args.db, out=args.out)
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    summary = result["summary"]
    print(
        f"veto replay: {result['counterfactual']['vetoed_setups']} stand-downs; "
        f"portfolio P&L ${summary['portfolio_realized_pnl']:.2f}; "
        f"effective R {summary['portfolio_effective_r']:+.3f}; wrote {artifact}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
