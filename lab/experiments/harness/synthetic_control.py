#!/usr/bin/env python3
"""Synthetic dose-response POSITIVE CONTROL for the validation pipeline.

Proves the search → LOO-walk-forward → PBO → DSR → sealed-year machinery has
**detection power** (can confirm a true edge) and **false-positive control**
(rejects pure noise), and **calibrates** the minimum edge it can detect. See
`validation/synthetic_control_plan.md` and the 5-model consensus in
`peer-review/2026-06-15-positive-control/`.

THE INJECTION (ground truth)
    realized_r_synth(i) = realized_r_real(i) + m · 1{ planted_predicate(i) }

We reuse the REAL capture ledger (real features/dates/tickers/gap score/filled
flag) and superimpose a known per-trade edge `m` on the real realized R of the
rows passing a chosen grid predicate (default `rvol_min_1_5` = opening_rv ≥ 1.5).

  - m = 0 reproduces the REAL ledger EXACTLY → a free, perfect NULL / false-
    positive control (we know the pipeline KILLS the real ledger).
  - m > 0 superimposes a *known* edge on real noise (preserves fat tails /
    autocorrelation / regime structure). Deterministic — no RNG.
  - The planted predicate is a real, leak-free feature aligned with a grid
    predicate, so a working search MUST recover it ("found?" check).

WHAT IT TESTS / DOESN'T
  - Tests: the stats/selection machinery (funnel stages 2–5) on the ledger.
  - Does NOT test the capture/feature engine (stage 1) or execution (stage 6) —
    validated separately (feature tests; d15 engine cross-check) — nor edges
    OUTSIDE the pre-registered grid (a known, separate limitation).

NO DB writes, NO engine changes — calls the existing feature_search / cscv /
deflated_sharpe functions in-process.

Usage:
    python3 -m trading.lab.experiments.harness.synthetic_control \
        --ledger trading/lab/experiments/_data/_capture_2022_2025.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.lab.experiments.harness import feature_search as fs
from trading.lab.validation.cscv import pbo_from_matrix
from trading.lab.validation.deflated_sharpe import (
    deflated_sharpe_ratio, effective_n_trials,
)

# ── frozen design (set before running) ───────────────────────────────────────
PLANT_PREDICATE = "rvol_min_1_5"                  # opening_rv >= 1.5 (grid-aligned)
DOSE_GRID = [0.00, 0.02, 0.05, 0.10, 0.20]        # R per qualifying trade; 0.00 = NULL
# Right-feature-recovery check. MUST be a CROSS-SECTIONAL (within-day) predicate:
# the daily-portfolio IR objective structurally under-recovers DAY-LEVEL regime
# flags (spy/sector_weak_regime) because filtering on them drops whole days, and
# the resulting zero-days inflate the IR denominator — so a regime plant is not
# cleanly recovered even at large doses (a real finding, see results writeup).
REPLANT_PREDICATE = "close_pos_max_0_9"
REPLANT_DOSE = 0.10
ANN = float(np.sqrt(252))


def inject(df: pd.DataFrame, m: float, predicate: str) -> pd.DataFrame:
    """Return a copy with realized_r = real + m·1{predicate}. The predicate mask
    is on a leak-free feature, so the injected world has no look-ahead. m=0
    reproduces the real ledger exactly."""
    out = df.copy()
    mask = fs._predicate_mask(out, predicate).astype(float)
    out["realized_r"] = out["_realized_r_real"].astype(float) + m * mask
    return out


def run_pipeline(df: pd.DataFrame, combos, top_n: int, blocks: int) -> dict:
    """Run the full canonical pipeline on a (already-injected) ledger. Mirrors
    feature_search.main(): pooled winner → LOO walk-forward → PBO → DSR → sealed
    2025. WF and PBO self-restrict to SEARCH_YEARS; the sealed step reads 2025."""
    df = df.copy()
    df["year"] = df["trade_date"].dt.year
    pred = {n: fs._predicate_mask(df, n) for n in fs.GRID}
    search = df[df["year"].isin(fs.SEARCH_YEARS)]

    pooled = sorted(((c, fs.daily_portfolio(search, c, pred, top_n)) for c in combos),
                    key=lambda x: x[1]["ir"], reverse=True)
    winner = pooled[0][0]

    wf = fs.walk_forward(df, combos, pred, top_n)
    perf = fs.build_perf_matrix(df, combos, pred, top_n)
    pbo = pbo_from_matrix(perf, n_blocks=blocks, higher_is_better=True)

    # Deflated Sharpe of the pooled winner (identical recipe to feature_search.main).
    daily_sr = []
    for j in range(perf.shape[1]):
        col = perf[:, j]
        sd = col.std(ddof=1)
        if sd > 0:
            daily_sr.append(col.mean() / sd)
    sr_var = float(np.var(daily_sr, ddof=1)) if len(daily_sr) > 1 else 0.0
    n_eff = effective_n_trials(perf)
    dsr = deflated_sharpe_ratio(perf[:, combos.index(winner)], sr_var, n_eff)

    # Sealed-2025-synth: the promoted (pooled-winner) combo on injected 2025.
    sealed = fs.daily_portfolio(df[df["year"] == fs.OOS_YEAR], winner, pred, top_n)

    wf_ok, pbo_ok = wf["wf_pass"], pbo["pbo"] < 0.5
    dsr_ok = (dsr["dsr"] is not None) and (dsr["dsr"] >= fs.DSR_GATE)
    if wf_ok and pbo_ok and dsr_ok:
        verdict = "PROMOTE"
    elif wf_ok and pbo_ok:
        verdict = "REVIEW"
    else:
        verdict = "NO-EDGE"

    return {
        "winner": winner, "pooled_top": pooled[:5], "wf": wf, "pbo": pbo,
        "dsr": dsr, "n_eff": n_eff, "sealed": sealed, "verdict": verdict,
        "wf_ok": wf_ok, "pbo_ok": pbo_ok, "dsr_ok": dsr_ok,
    }


def _found(combo, predicate: str) -> bool:
    return predicate in combo


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ledger",
                   default="trading/lab/experiments/_data/_capture_2022_2025.parquet")
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--k", type=int, default=2)
    p.add_argument("--blocks", type=int, default=16)
    p.add_argument("--plant", default=PLANT_PREDICATE,
                   help=f"grid predicate to plant the edge on (default {PLANT_PREDICATE})")
    p.add_argument("--no-replant", action="store_true",
                   help="skip the right-feature-recovery robustness check")
    args = p.parse_args()

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["_realized_r_real"] = df["realized_r"].astype(float)
    combos = fs.enumerate_combos(args.k)

    plant_mask = fs._predicate_mask(df, args.plant)
    filled = df["filled"] == True  # noqa: E712
    n_plant = int((plant_mask & filled).sum())
    n_filled = int(filled.sum())
    print(f"Ledger {path.name}: {len(df)} rows, {n_filled} filled, "
          f"years {sorted(df['trade_date'].dt.year.unique())}.")
    print(f"Planted predicate: {args.plant} "
          f"({fs.PREDICATE_FEATURE[args.plant]} {fs.GRID[args.plant][0]} {fs.GRID[args.plant][1]}) "
          f"— {n_plant}/{n_filled} filled rows qualify ({100*n_plant/max(1,n_filled):.0f}%).")
    print(f"Doses (R/qualifying trade): {DOSE_GRID}   top_n={args.top_n} k={args.k} "
          f"blocks={args.blocks}\n")
    print("Injection: realized_r_synth = realized_r_real + m·1{planted}.  "
          "m=0 reproduces the real ledger (NULL).\n")

    # ── dose-response sweep ──────────────────────────────────────────────────
    header = (f"{'m':>5} | {'winner':38} | {'found':5} | {'WF sumR':>8} | "
              f"{'pos':>3} | {'PBO':>5} | {'DSR':>5} | {'dSR':>6} | "
              f"{'sealed':>7} | verdict")
    print("=== DOSE-RESPONSE POWER CURVE ===")
    print(header)
    print("-" * len(header))
    rows = []
    for m in DOSE_GRID:
        res = run_pipeline(inject(df, m, args.plant), combos, args.top_n, args.blocks)
        wf, dsr, sealed = res["wf"], res["dsr"], res["sealed"]
        dsr_val = dsr["dsr"] if dsr["dsr"] is not None else float("nan")
        rows.append({"m": m, **res})
        print(f"{m:5.2f} | {fs._fmt(res['winner']):38} | "
              f"{'YES' if _found(res['winner'], args.plant) else 'no ':5} | "
              f"{wf['agg_oos_sum_r']:+8.1f} | {wf['positive_folds']}/{wf['n_folds']:1} | "
              f"{res['pbo']['pbo']:5.2f} | {dsr_val:5.2f} | "
              f"{dsr['sr_observed']*ANN:+6.2f} | {sealed['sum_r']:+7.1f} | {res['verdict']}")
    print("\n  cols: found = search recovered the planted predicate; WF sumR = "
          "LOO-walk-forward aggregate; pos = positive folds; dSR = annualized "
          "daily Sharpe of the winner; sealed = pooled-winner sumR on injected 2025.")

    # ── readout: minimum detectable edge + gate calibration ──────────────────
    null = rows[0]
    promotes = [r for r in rows if r["verdict"] == "PROMOTE"]
    m_star = promotes[0]["m"] if promotes else None
    print("\n=== READOUT ===")
    print(f"  NULL (m=0): verdict={null['verdict']}  "
          f"(WF={'pass' if null['wf_ok'] else 'fail'}, PBO={null['pbo']['pbo']:.2f}, "
          f"DSR={null['dsr']['dsr']:.2f}) "
          f"— {'FALSE-POSITIVE CONTROL OK (null rejected)' if null['verdict'] != 'PROMOTE' else '*** NULL PROMOTED — false-positive BUG, STOP ***'}")
    if m_star is not None:
        ms = next(r for r in rows if r["m"] == m_star)
        sr_ann = ms["dsr"]["sr_observed"] * ANN
        print(f"  Minimum detectable edge m* = {m_star:.2f} R/trade "
              f"(annualized winner Sharpe ≈ {sr_ann:+.2f}) → first dose clearing all "
              f"gates. The pipeline CAN confirm a true edge; this is its sensitivity floor.")
    else:
        binding = []
        big = rows[-1]
        if not big["wf_ok"]:
            binding.append("WF")
        if not big["pbo_ok"]:
            binding.append("PBO")
        if not big["dsr_ok"]:
            binding.append(f"DSR ({big['dsr']['dsr']:.2f}<{fs.DSR_GATE})")
        print(f"  NO dose in the grid reached PROMOTE. At max dose m={big['m']:.2f} the "
              f"binding gate(s): {', '.join(binding) or 'none?'}.")
        print("  → If WF/PBO already pass at a modest dose but DSR alone blocks, the "
              "DSR≥0.95 gate may be too strict for the intraday Sharpe scale. "
              "PROPOSE a recalibration (do NOT silently change the gate); re-run.")

    # discovery quality across positive doses
    pos = [r for r in rows if r["m"] > 0]
    rec = sum(_found(r["winner"], args.plant) for r in pos)
    print(f"  Feature recovery: search picked the planted predicate in {rec}/{len(pos)} "
          f"positive doses.")

    # ── robustness: plant a DIFFERENT feature, confirm THAT one is recovered ──
    if not args.no_replant and REPLANT_PREDICATE != args.plant:
        print(f"\n=== ROBUSTNESS: right-feature recovery (replant on '{REPLANT_PREDICATE}' "
              f"at m={REPLANT_DOSE}) ===")
        rres = run_pipeline(inject(df, REPLANT_DOSE, REPLANT_PREDICATE),
                            combos, args.top_n, args.blocks)
        ok = _found(rres["winner"], REPLANT_PREDICATE)
        print(f"  winner=[{fs._fmt(rres['winner'])}]  recovered '{REPLANT_PREDICATE}': "
              f"{'YES' if ok else 'NO'}  (verdict {rres['verdict']})")
        print("  → confirms the search isn't just always picking rvol; it locks onto "
              "whichever feature actually carries the planted edge."
              if ok else
              "  → search did NOT recover the replanted feature — investigate "
              "selectivity/dilution of that predicate before trusting recovery claims.")

    # ── verdict ──────────────────────────────────────────────────────────────
    print("\n>>> SYNTHETIC-CONTROL VERDICT:")
    if null["verdict"] == "PROMOTE":
        print("    *** FALSE-POSITIVE: the pure real ledger (m=0) was PROMOTED. The gates "
              "are admitting noise — STOP and debug before trusting any kill. ***")
    elif m_star is not None:
        print(f"    SOUND. Null rejected; a known edge of m*={m_star:.2f} R/trade clears all "
              "gates. Detection power confirmed → prior kills are trustworthy; the "
              "long-only same-day regime is simply thin (the structural finding).")
    else:
        print("    OVER-CONSERVATIVE (or edge too small): the null is correctly rejected but "
              "NO grid dose reached PROMOTE. Inspect the binding gate above; if a "
              "modest-Sharpe edge can't pass, recalibrate the gate for the horizon "
              "(proposal-only) and re-run before trusting kills.")


if __name__ == "__main__":
    main()
