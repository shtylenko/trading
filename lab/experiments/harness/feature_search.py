#!/usr/bin/env python3
"""Offline combinatorial feature search over the captured candidate ledger.

THE canonical search entry point. Consumes the rectangular capture ledger (one
row per admitted candidate, with its leak-free feature vector, gap ``score``,
``filled`` flag, and ``realized_r``) and asks: which small combination of
candidate-admission filters has a robust, multi-year edge? Because the capture
admits exactly the minimum universe, every filter combo is a SUBSET (row mask) of
the ledger — a fast offline scan, never a re-run.

Methodology (validation/EXPLORATION_PLAYBOOK.md, post-2026-06-15 reconciliation):
  - Objective = risk-adjusted DAILY-PORTFOLIO return: group filled trades by day,
    sum the day's top-N R, score annualized mean(daily R)/std(daily R) (info
    ratio). NOT mean-R-per-trade (a variance maximizer). Zero-trade days count
    (matches deployment = daily capital allocation). Hard trade-count floors keep
    tiny samples ineligible.
  - Arbiter = LEAVE-ONE-YEAR-OUT walk-forward: for each search year, select the
    best combo on the OTHER search years and score it on the held-out year. (NOT
    per-fold 1-year-train argmax — that tests selector stability across regimes,
    not edge existence, and manufactured a false negative in round 1.)
  - PBO via CSCV computed on the SAME daily-R matrix the objective uses.
  - Per-combo permutation p is NEVER a gate (selection makes the winner's p
    meaningless). The honest gates are LOO walk-forward + PBO.
  - 2025 (OOS_YEAR) is NEVER read here — it is the sealed confirmatory holdout.
  - Grid is PRE-REGISTERED and LOCKED before scoring; do not widen it in reaction
    to results (alpha-spending; round 1 = k<=2).

A search PASS only nominates a combo for the pre-registered sealed-OOS test
(phase_b_oos_preregistration.md) + engine cross-check — it is not a promotion.

Usage:
    python3 -m trading.lab.experiments.harness.feature_search \
        --ledger trading/lab/experiments/_data/_capture_2022_2025.parquet \
        --top-n 10 --k 2 --seed 7
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.storage.duckdb import connect, init_db
from trading.lab.validation.cscv import pbo_from_matrix
from trading.lab.validation.deflated_sharpe import (
    deflated_sharpe_ratio, effective_n_trials,
)

DSR_GATE = 0.95   # selection-bias-adjusted significance required to PROMOTE

# ── PRE-REGISTERED search grid (LOCKED) ──────────────────────────────────────
# Each predicate is a thesis-bounded, one-sided cut on a single feature. Coarse
# (1–2 cut points each). Round 1 searches combos of k<=2. Do NOT widen in reaction
# to results — that laundering is exactly what PBO is meant to catch.
GRID: dict[str, tuple[str, float]] = {
    "gap_floor_3":        ("ge", 3.0),          # gap_pct_vs_prior_high >= 3
    "gap_ceiling_12":     ("le", 12.0),         # gap_pct_vs_prior_high <= 12
    "rvol_min_1_5":       ("ge", 1.5),          # opening_rv >= 1.5
    "atr_frac_max_0_5":   ("le", 0.5),          # first_range_atr_frac <= 0.5
    "close_pos_max_0_9":  ("le", 0.9),          # first_close_pos <= 0.9
    "spy_weak_regime":    ("eq", 1.0),          # spy_below_50d_sma == 1
    "sector_weak_regime": ("eq", 1.0),          # sector_below_50d_sma == 1
    "price_min_10":       ("ge", 10.0),         # first_open >= 10
    "adv_min_1m":         ("ge", 1_000_000.0),  # avg_daily_volume >= 1e6
}
PREDICATE_FEATURE = {
    "gap_floor_3": "gap_pct_vs_prior_high", "gap_ceiling_12": "gap_pct_vs_prior_high",
    "rvol_min_1_5": "opening_rv", "atr_frac_max_0_5": "first_range_atr_frac",
    "close_pos_max_0_9": "first_close_pos", "spy_weak_regime": "spy_below_50d_sma",
    "sector_weak_regime": "sector_below_50d_sma", "price_min_10": "first_open",
    "adv_min_1m": "avg_daily_volume",
}
ALLOWED_SAME_FEATURE_PAIRS = {frozenset({"gap_floor_3", "gap_ceiling_12"})}

SEARCH_YEARS = [2022, 2023, 2024]   # used for search/selection/WF/PBO
OOS_YEAR = 2025                     # SEALED — never read in this script
MIN_TRADES_TOTAL = 50
MIN_TRADES_PER_QTR = 20
TOP_K_TAIL = 5
ANN = float(np.sqrt(252))


# ── masks / enumeration ──────────────────────────────────────────────────────

def _predicate_mask(df: pd.DataFrame, name: str) -> pd.Series:
    op, thr = GRID[name]
    col = df[PREDICATE_FEATURE[name]]
    if op == "ge":
        return col >= thr
    if op == "le":
        return col <= thr
    if op == "eq":
        return col == thr
    raise ValueError(op)


def _combo_mask(df: pd.DataFrame, combo: tuple[str, ...], pred_masks: dict) -> pd.Series:
    m = pd.Series(True, index=df.index)
    for name in combo:
        m &= pred_masks[name]
    return m


def enumerate_combos(k: int) -> list[tuple[str, ...]]:
    """All filter combos of size 0..k (0 = unfiltered baseline), excluding
    nonsensical same-feature pairs (except the gap floor+ceiling band)."""
    names = list(GRID)
    combos: list[tuple[str, ...]] = [()]
    for size in range(1, k + 1):
        for c in itertools.combinations(names, size):
            feats = [PREDICATE_FEATURE[n] for n in c]
            if len(set(feats)) < len(feats) and frozenset(c) not in ALLOWED_SAME_FEATURE_PAIRS:
                continue
            combos.append(c)
    return combos


def apply_top_n(df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Deployment cap: keep each day's top-N admitted rows by gap ``score``."""
    if top_n is None or top_n <= 0:
        return df
    return df.sort_values("score", ascending=False).groupby("trade_date", sort=False).head(top_n)


# ── canonical scoring: risk-adjusted daily-portfolio return ──────────────────

def _apply_roster(df: pd.DataFrame, combo, pred_masks, top_n: int, mode: str) -> pd.DataFrame:
    """A combo's traded book under a roster mode.

    'replace' (deployment): filter, then take the day's top-N by gap.
    'remove'  (isolation):  baseline top-N first, then drop rows failing the
        filter — the filter can only subtract, never promote a substitute.
        replace-vs-remove gap = the top-N "substitution" effect.
    """
    if mode == "replace":
        return apply_top_n(df[_combo_mask(df, combo, pred_masks)], top_n)
    base = apply_top_n(df, top_n)
    return base[_combo_mask(base, combo, pred_masks)]


def daily_portfolio(df_window_all: pd.DataFrame, combo, pred_masks, top_n: int,
                    mode: str = "replace") -> dict:
    """Daily-portfolio metrics for a combo over a window.

    Daily R = sum of the day's traded (top-N, filled) realized R; the series spans
    EVERY opportunity-day in the window (0 on days the combo doesn't trade) so
    sparsity and correlated stop-outs both show up in std. ``ir`` is the selection
    objective (annualized mean/std of daily R), −inf when constraints unmet.
    """
    all_days = pd.Index(sorted(df_window_all["trade_date"].dt.normalize().unique()))
    book = _apply_roster(df_window_all, combo, pred_masks, top_n, mode)
    filled = book[book["filled"] == True]  # noqa: E712
    r = filled["realized_r"].astype(float)
    n = int(len(r))
    if n == 0:
        return {"trades": 0, "eligible": False, "ir": float("-inf"), "ir_raw": 0.0,
                "sum_r": 0.0, "daily_mean": 0.0, "daily_std": 0.0, "tstat": 0.0,
                "win_rate": 0.0, "top_k_share": None, "trades_per_qtr_min": 0,
                "worst_qtr_r": 0.0}
    by_day = filled.groupby(filled["trade_date"].dt.normalize())["realized_r"].sum()
    daily = by_day.reindex(all_days, fill_value=0.0).astype(float)
    dmean, dstd = float(daily.mean()), float(daily.std(ddof=1))
    ir = (dmean / dstd * ANN) if dstd > 0 else 0.0
    tstat = (dmean / dstd * np.sqrt(len(daily))) if dstd > 0 else 0.0
    qn = filled.groupby(filled["trade_date"].dt.to_period("Q")).size()
    qr = filled.groupby(filled["trade_date"].dt.to_period("Q"))["realized_r"].sum()
    sum_r = float(r.sum())
    top_k = float(r.nlargest(TOP_K_TAIL).sum())
    eligible = n >= MIN_TRADES_TOTAL and int(qn.min()) >= MIN_TRADES_PER_QTR
    return {
        "trades": n, "eligible": eligible, "ir": ir if eligible else float("-inf"),
        "ir_raw": ir, "sum_r": sum_r, "daily_mean": dmean, "daily_std": dstd,
        "tstat": tstat, "win_rate": float((r > 0).mean() * 100),
        "top_k_share": (top_k / sum_r) if sum_r > 0 else None,
        "trades_per_qtr_min": int(qn.min()), "worst_qtr_r": float(qr.min()),
    }


def objective(m: dict) -> float:
    """Selection objective = annualized daily-portfolio info ratio (−inf if the
    trade-count constraints are unmet)."""
    return m["ir"]


# ── leave-one-year-out walk-forward (the arbiter) ────────────────────────────

def walk_forward(df: pd.DataFrame, combos, pred_masks, top_n: int) -> dict:
    """Leave-one-year-out: select the best combo (by IR) on the OTHER search years,
    score it on the held-out year. Pass = aggregate OOS sum R > 0 AND positive in
    every held-out fold AND the per-quarter floor holds on every fold."""
    folds, agg, pos = [], 0.0, 0
    picks = set()
    for held in SEARCH_YEARS:
        train = df[df["year"].isin([y for y in SEARCH_YEARS if y != held])]
        test = df[df["year"] == held]
        best, best_obj = None, float("-inf")
        for c in combos:
            o = objective(daily_portfolio(train, c, pred_masks, top_n))
            if o > best_obj:
                best_obj, best = o, c
        tm = daily_portfolio(test, best, pred_masks, top_n)
        folds.append({"held_year": held, "selected": list(best), "test": tm})
        agg += tm["sum_r"]; pos += int(tm["sum_r"] > 0); picks.add(tuple(best))
    floor_ok = all(f["test"]["trades_per_qtr_min"] >= MIN_TRADES_PER_QTR for f in folds)
    return {
        "folds": folds, "agg_oos_sum_r": agg, "positive_folds": pos,
        "n_folds": len(SEARCH_YEARS), "pick_stable": len(picks) == 1,
        "qtr_floor_ok": floor_ok,
        "wf_pass": agg > 0 and pos == len(SEARCH_YEARS) and floor_ok,
    }


def build_perf_matrix(df: pd.DataFrame, combos, pred_masks, top_n: int) -> np.ndarray:
    """(search-day × combo) matrix of per-day summed top-N R, for CSCV/PBO. This is
    the same daily-R series the IR objective is built from, so PBO and the search
    objective are consistent. 2025 (OOS) excluded."""
    search = df[df["year"].isin(SEARCH_YEARS)]
    days = sorted(search["trade_date"].dt.normalize().unique())
    day_index = {d: i for i, d in enumerate(days)}
    perf = np.zeros((len(days), len(combos)))
    for j, combo in enumerate(combos):
        sub = apply_top_n(search[_combo_mask(search, combo, pred_masks)], top_n)
        sub = sub[sub["filled"] == True]  # noqa: E712
        if sub.empty:
            continue
        for d, v in sub.groupby(sub["trade_date"].dt.normalize())["realized_r"].sum().items():
            perf[day_index[d], j] = float(v)
    return perf


def _fmt(combo) -> str:
    return "+".join(combo) or "(baseline)"


def main() -> None:
    p = argparse.ArgumentParser(description="Canonical feature search over the capture ledger")
    p.add_argument("--ledger", required=True)
    p.add_argument("--top-n", type=int, default=10, help="per-day deployment cap")
    p.add_argument("--k", type=int, default=2, help="max simultaneous filters (round 1 = 2)")
    p.add_argument("--blocks", type=int, default=16, help="CSCV blocks (even)")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--no-store", action="store_true")
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["year"] = df["trade_date"].dt.year
    if (df["year"] == OOS_YEAR).any():
        df = df[df["year"] != OOS_YEAR].copy()  # HARD seal: never read OOS here
    search = df[df["year"].isin(SEARCH_YEARS)].copy()

    combos = enumerate_combos(args.k)
    pred = {n: _predicate_mask(df, n) for n in GRID}
    print(f"Ledger {path.name}: {len(search)} rows, search years {SEARCH_YEARS} "
          f"(OOS {OOS_YEAR} sealed). {len(combos)} combos, top_n={args.top_n}")
    print("Objective: annualized daily-portfolio info ratio. Arbiter: leave-one-year-out.\n")

    base = daily_portfolio(search, (), pred, args.top_n)
    print(f"Baseline (unfiltered top-{args.top_n}, {SEARCH_YEARS}): "
          f"{base['trades']} trades, sumR {base['sum_r']:+.1f}, IR {base['ir_raw']:+.2f}")

    # Pooled in-sample ranking (descriptive — identifies the global winner).
    pooled = sorted(((c, daily_portfolio(search, c, pred, args.top_n)) for c in combos),
                    key=lambda x: x[1]["ir"], reverse=True)
    print("\nTop combos by pooled 2022–2024 info ratio (descriptive):")
    for c, m in pooled[:8]:
        print(f"  {_fmt(c):40} IR={m['ir_raw']:+.2f} sumR={m['sum_r']:+7.1f} "
              f"n={m['trades']} worstQ={m['worst_qtr_r']:+.1f} tail={m['top_k_share']}")

    # Leave-one-year-out walk-forward (the arbiter) + PBO.
    wf = walk_forward(df, combos, pred, args.top_n)
    print("\n=== LEAVE-ONE-YEAR-OUT WALK-FORWARD (arbiter) ===")
    for fo in wf["folds"]:
        t = fo["test"]
        print(f"  hold {fo['held_year']}: pick [{_fmt(fo['selected'])}] → "
              f"sumR={t['sum_r']:+.1f} IR={t['ir_raw']:+.2f} n={t['trades']} "
              f"qtrMin={t['trades_per_qtr_min']}")
    print(f"  aggregate OOS sumR={wf['agg_oos_sum_r']:+.1f}  positive folds="
          f"{wf['positive_folds']}/{wf['n_folds']}  pick-stable={wf['pick_stable']}  "
          f"qtr-floor={'ok' if wf['qtr_floor_ok'] else 'FAIL'}")
    print(f"  WF verdict: {'PASS' if wf['wf_pass'] else 'FAIL'}")

    perf = build_perf_matrix(df, combos, pred, args.top_n)
    pbo = pbo_from_matrix(perf, n_blocks=args.blocks, higher_is_better=True)
    print(f"\n=== PBO (CSCV + embargo, same daily-R metric) ===  PBO={pbo['pbo']:.3f} "
          f"over {pbo['n_splits']} splits (S={args.blocks})")

    # Deflated Sharpe of the pooled winner — selection-bias-adjusted significance.
    # Per-period (daily) Sharpe of every combo → variance across the search space;
    # effective independent trials via the combos' return-correlation participation
    # ratio (NOT the raw 46, which over-penalizes correlated combos).
    daily_sr = []
    for j in range(perf.shape[1]):
        col = perf[:, j]
        sd = col.std(ddof=1)
        if sd > 0:
            daily_sr.append(col.mean() / sd)
    sr_var = float(np.var(daily_sr, ddof=1)) if len(daily_sr) > 1 else 0.0
    n_eff = effective_n_trials(perf)
    winner_daily = perf[:, combos.index(pooled[0][0])]
    dsr = deflated_sharpe_ratio(winner_daily, sr_var, n_eff)
    print(f"\n=== Deflated Sharpe (selection-bias gate) ===")
    print(f"  winner [{_fmt(pooled[0][0])}]: DSR={dsr['dsr']:.3f}  "
          f"(obs daily SR={dsr['sr_observed']:+.3f} vs null hurdle {dsr['sr_hurdle']:+.3f}; "
          f"skew={dsr['skew']:+.2f} kurt={dsr['kurtosis']:.1f}; "
          f"effective trials={n_eff:.1f} of {len(combos)})")

    wf_ok, pbo_ok, dsr_ok = wf["wf_pass"], pbo["pbo"] < 0.5, dsr["dsr"] >= DSR_GATE
    if wf_ok and pbo_ok and dsr_ok:
        verdict = "PROMOTE-CANDIDATE → sealed-OOS test"
    elif wf_ok and pbo_ok:
        verdict = f"REVIEW — path-robust but DSR {dsr['dsr']:.2f} < {DSR_GATE} (selection bias not cleared)"
    else:
        verdict = "NO ROBUST EDGE"
    print(f"\n>>> SEARCH VERDICT: {verdict}")
    print(f"    gates: WF={'pass' if wf_ok else 'fail'}  PBO={pbo['pbo']:.2f}"
          f"{'<0.5' if pbo_ok else '≥0.5'}  DSR={dsr['dsr']:.2f}{'≥' if dsr_ok else '<'}{DSR_GATE}")
    if wf_ok and pbo_ok and dsr_ok:
        print(f"    candidate [{_fmt(pooled[0][0])}] — pre-register + spend a sealed year ONCE "
              f"(phase_b_oos_preregistration.md). Mind the cross-family OOS budget "
              f"(validation/oos_spend_ledger.md).")

    if not args.no_store:
        _store(args, pooled, wf, pbo, dsr, n_eff)


def _store(args, pooled, wf, pbo, dsr, n_eff) -> None:
    init_db()
    search_id = f"fsearch_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    config = {
        "ledger": str(args.ledger), "top_n": args.top_n, "k": args.k, "seed": args.seed,
        "blocks": args.blocks, "grid": {n: list(GRID[n]) for n in GRID},
        "search_years": SEARCH_YEARS, "oos_year": OOS_YEAR,
        "objective": "daily_portfolio_info_ratio", "arbiter": "leave_one_year_out",
        "min_trades_total": MIN_TRADES_TOTAL, "min_trades_per_qtr": MIN_TRADES_PER_QTR,
        "walk_forward": {k: v for k, v in wf.items() if k != "folds"}, "wf_folds": wf["folds"],
        "pbo": {k: v for k, v in pbo.items() if k != "logits"},
        "deflated_sharpe": dsr, "effective_n_trials": n_eff, "dsr_gate": DSR_GATE,
    }
    with connect() as conn:
        conn.execute(
            "INSERT INTO search_runs (search_id, release_id, testset, started_at, "
            "completed_at, objective, config_json, status) VALUES (?,?,?,?,?,?,?,?)",
            [search_id, "capture_d_features", "feature_search", datetime.now(),
             datetime.now(), "daily_portfolio_ir|loo_wf|pbo", json.dumps(config, default=str),
             "completed"],
        )
        for rank, (combo, m) in enumerate(pooled, 1):
            conn.execute(
                "INSERT INTO search_results (search_id, result_rank, filters_json, "
                "trade_count, total_pnl_pct, profit_factor, win_rate, metrics_json) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [search_id, rank, json.dumps(list(combo)), int(m["trades"]),
                 float(m["sum_r"]), None, float(m["win_rate"]),
                 json.dumps({"ir": m["ir_raw"], "tstat": m["tstat"],
                             "top_k_share": m["top_k_share"],
                             "trades_per_qtr_min": m["trades_per_qtr_min"],
                             "worst_qtr_r": m["worst_qtr_r"]}, default=str)],
            )
    print(f"\nStored as search_id={search_id} ({len(pooled)} combos).")


if __name__ == "__main__":
    main()
