#!/usr/bin/env python3
"""x02 vol-scaled / risk-managed momentum — pre-registered comparison runner.

Implements the LOCKED spec `validation/multiday_x02_volscaled_preregistration.md`:
the ONLY lever vs the validated base 12-1 rule is how the top-N momentum book is
weighted. Three schemes scored side by side on the SAME non-overlapping periods:

  base : equal weight (x01's construction) — the bar to beat.
  V1   : inverse-vol weights  w_i ∝ 1/vol_20d_i  (normalized, long-only, sum 1).
  V2   : constant-target-vol scaling — equal weights, gross exposure scaled by
         min(1, σ_target / σ_book,t). σ_book,t = mean vol_20d of the book (a
         leak-safe per-rebalance vol PROXY; ignores cross-name correlation).
         σ_target = OPTION B: mean σ_book,t over the FIRST search year (2022) ONLY,
         fixed forward — no later year informs earlier exposure (zero look-ahead).

Period return = weighted mean of (fwd_H − cost) over the book (V2 × exposure, cash 0).
Reports per scheme: per-period mean/Sharpe/t, leave-one-year-out per-fold signs,
a 20-phase Sharpe-stability sweep, and the Deflated Sharpe (deflated across the 3
pre-registered schemes). Decision rule per the spec: a variant PROMOTES only if it
beats base on DSR AND Sharpe and is phase-robust; else equal-weight x01 wins.

2025 is hard-sealed out (already spent); 2026 is never read. Usage:
    python3 -m trading.lab.experiments.multiday.multiday_volscale \
        --ledger trading/lab/experiments/_data/_capture_multiday_2022_2025_split.parquet \
        --horizon 20 --top-n 50 --cost-bps 10
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
from trading.lab.validation.deflated_sharpe import deflated_sharpe_ratio

VOL_FLOOR = 0.005          # 0.5%/day floor on vol_20d for 1/σ weights (avoid blow-up)
SCHEMES = ("base", "V1_invvol", "V2_targetvol")


def _book_for_day(day_df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """Top-N eligible names by mom_12_1 on one rebalance day, with finite vol."""
    b = day_df[day_df["eligible"] & day_df["mom_12_1"].notna() & day_df["vol_20d"].notna()]
    b = b[b["vol_20d"] > 0]
    return b.sort_values("mom_12_1", ascending=False).head(top_n)


def _period_returns(df: pd.DataFrame, rebal_days, top_n: int, sigma_target: float | None):
    """Per-rebalance weighted return for each scheme. Returns (DataFrame indexed by
    rebalance date with one column per scheme, sigma_book series)."""
    rows, sig_rows = {}, {}
    for d in rebal_days:
        book = _book_for_day(df[df["trade_date"] == d], top_n)
        if book.empty:
            continue
        r = book["realized_r"].astype(float).to_numpy()
        vol = book["vol_20d"].astype(float).clip(lower=VOL_FLOOR).to_numpy()
        n = len(r)
        # base: equal weight
        base = float(np.mean(r))
        # V1: inverse-vol weights
        w = (1.0 / vol); w /= w.sum()
        v1 = float(np.dot(w, r))
        # V2: equal weight × exposure(min(1, sigma_target/sigma_book))
        sigma_book = float(np.mean(vol))
        sig_rows[d] = sigma_book
        if sigma_target is None:
            v2 = np.nan
        else:
            exposure = min(1.0, sigma_target / sigma_book) if sigma_book > 0 else 0.0
            v2 = exposure * base
        rows[d] = {"base": base, "V1_invvol": v1, "V2_targetvol": v2}
    out = pd.DataFrame.from_dict(rows, orient="index").sort_index()
    sig = pd.Series(sig_rows).sort_index()
    return out, sig


def _stats(series: np.ndarray, H: int) -> dict:
    r = np.asarray(series, dtype=float)
    r = r[np.isfinite(r)]
    n = len(r)
    mean, sd = float(r.mean()), float(r.std(ddof=1)) if n > 1 else 0.0
    ann = float(np.sqrt(252.0 / H))
    return {"n": n, "mean": mean, "std": sd,
            "sharpe_ann": (mean / sd * ann) if sd > 0 else float("nan"),
            "tstat": (mean / sd * np.sqrt(n)) if sd > 0 else float("nan")}


def main() -> None:
    p = argparse.ArgumentParser(description="x02 vol-scaled momentum pre-registered comparison")
    p.add_argument("--ledger", required=True)
    p.add_argument("--horizon", type=int, default=20)
    p.add_argument("--top-n", type=int, default=50)
    p.add_argument("--cost-bps", type=float, default=10.0)
    args = p.parse_args()
    H = args.horizon

    path = Path(args.ledger)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    df = pd.read_parquet(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.normalize()
    fwd = f"fwd_{H}"
    df = df[df["eligible"] & df[fwd].notna()].copy()
    df["realized_r"] = df[fwd].astype(float) - args.cost_bps / 10000.0
    df["year"] = df["trade_date"].dt.year
    df = df[df["year"] != fs.OOS_YEAR].copy()             # hard seal 2025
    df = df[df["year"].isin(fs.SEARCH_YEARS + [y for y in df["year"].unique()
                                              if y < min(fs.SEARCH_YEARS)])].copy()
    all_days = sorted(df["trade_date"].unique())
    years = sorted(df["year"].unique())

    print(f"Vol-scale comparison: {path.name}, H={H}d, top_n={args.top_n}, "
          f"cost={args.cost_bps:.0f}bps, years {years[0]}–{years[-1]} (2025 sealed)")

    # ── σ_target (Option B): mean σ_book over FIRST search year (2022) only ──────
    first_year = min(fs.SEARCH_YEARS)
    rebal0 = all_days[0::H]
    _, sig_all = _period_returns(df, rebal0, args.top_n, sigma_target=None)
    sig_2022 = sig_all[[pd.Timestamp(d).year == first_year for d in sig_all.index]]
    sigma_target = float(sig_2022.mean())
    print(f"σ_target (Option B, {first_year}-only mean book vol, fixed forward) = "
          f"{sigma_target*100:.3f}%/day\n")

    # ── phase-0 headline ────────────────────────────────────────────────────────
    per, _ = _period_returns(df, rebal0, args.top_n, sigma_target)
    per["year"] = [pd.Timestamp(d).year for d in per.index]
    print("=== PHASE-0 NON-OVERLAPPING PERIODS (headline) ===")
    print(f"{'scheme':14} {'nPer':>4} {'perPeriod%':>10} {'annSharpe':>10} {'t':>6}  LOO per-year sum%")
    dsr_inputs = {}
    sharpes = {}
    for s in SCHEMES:
        srs = per[s].to_numpy()
        st = _stats(srs, H)
        sharpes[s] = st["sharpe_ann"]
        dsr_inputs[s] = per[s].dropna().to_numpy()
        yearly = per.groupby("year")[s].sum()
        ystr = " ".join(f"{y}:{v*100:+.1f}" for y, v in yearly.items())
        print(f"{s:14} {st['n']:>4} {st['mean']*100:>+10.3f} {st['sharpe_ann']:>+10.2f} "
              f"{st['tstat']:>+6.2f}  {ystr}")

    # ── Deflated Sharpe, deflated across the 3 pre-registered schemes ───────────
    # sr_variance = variance of per-period Sharpe across the 3 schemes; n_trials = 3.
    per_sr = [np.nanmean(dsr_inputs[s]) / np.nanstd(dsr_inputs[s], ddof=1)
              for s in SCHEMES if np.nanstd(dsr_inputs[s], ddof=1) > 0]
    sr_var = float(np.var(per_sr, ddof=1)) if len(per_sr) > 1 else 0.0
    print("\n=== DEFLATED SHARPE (deflated across the 3 pre-registered schemes, n_trials=3) ===")
    dsr_vals = {}
    for s in SCHEMES:
        d = deflated_sharpe_ratio(dsr_inputs[s], sr_var, 3.0)
        dsr_vals[s] = d["dsr"]
        print(f"  {s:14} DSR={d['dsr']:.3f}  (per-period SR={d['sr_observed']:+.3f}, "
              f"hurdle {d['sr_hurdle']:+.3f}, n={d['n_obs']})")

    # ── 20-phase Sharpe-stability sweep ─────────────────────────────────────────
    print(f"\n=== {H}-PHASE SHARPE STABILITY (each phase = a different rebalance offset) ===")
    phase_sh = {s: [] for s in SCHEMES}
    for ph in range(H):
        rebal = all_days[ph::H]
        perp, _ = _period_returns(df, rebal, args.top_n, sigma_target)
        for s in SCHEMES:
            phase_sh[s].append(_stats(perp[s].to_numpy(), H)["sharpe_ann"])
    for s in SCHEMES:
        a = np.array([x for x in phase_sh[s] if np.isfinite(x)])
        beats = np.mean(a > np.median(phase_sh["base"])) if s != "base" else float("nan")
        print(f"  {s:14} annSharpe  min {a.min():+.2f}  median {np.median(a):+.2f}  "
              f"max {a.max():+.2f}  (#phases>0: {(a>0).sum()}/{len(a)})")

    # ── verdict vs the pre-registered bar ───────────────────────────────────────
    print("\n>>> x02 READOUT vs base equal-weight (spec bar: DSR≥0.95 AND DSR>base AND Sharpe>base AND phase-robust)")
    base_sh, base_dsr = sharpes["base"], dsr_vals["base"]
    for s in ("V1_invvol", "V2_targetvol"):
        med = np.median([x for x in phase_sh[s] if np.isfinite(x)])
        base_med = np.median([x for x in phase_sh["base"] if np.isfinite(x)])
        phase_robust = med > base_med
        passes = (dsr_vals[s] >= 0.95 and dsr_vals[s] > base_dsr
                  and sharpes[s] > base_sh and phase_robust)
        print(f"  {s}: Sharpe {sharpes[s]:+.2f} vs base {base_sh:+.2f} | "
              f"DSR {dsr_vals[s]:.3f} vs base {base_dsr:.3f} | "
              f"phase-median {med:+.2f} vs {base_med:+.2f} → "
              f"{'PROMOTE-CANDIDATE' if passes else 'does NOT beat base'}")
    print("\n(2025 sealed-out; 2026 never read. Clean evidence is in-sample only until 2026 accrues.)")


if __name__ == "__main__":
    main()
