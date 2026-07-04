#!/usr/bin/env python3
"""Ablation grid + slippage stress for the Phase v2 simulation.

Uses artifacts/oos_scored.parquet produced by train_and_simulate.py.
Each variant differs in (ranking key, entry policy, K, sizing).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SCORED = os.path.join(HERE, "artifacts", "oos_scored.parquet")

FEES = 0.00005
CAPITAL0 = 100_000.0
BASE_RISK = 0.01
LEV_CAP = 4.0
THETA_HIGH = 0.60
THETA_MID = 0.45


def net_r(row, entry_col, r_col, entry_slip, exit_slip):
    risk = row["risk_per_share"]
    entry_px = row[entry_col]
    gross_r = row[r_col]
    exit_px = entry_px + gross_r * risk
    cost = entry_px * (entry_slip + FEES) + exit_px * (exit_slip + FEES)
    return gross_r - cost / risk


def entry_plan(r, policy, taker_slip):
    """Return (entry_col, r_col, filled, entry_slip) for a row under a policy."""
    if policy == "stop":
        return "entry_stop_px", "realized_r_stop_entry", bool(r["breached"]), taker_slip
    if policy == "pb05":
        return "entry_pb05_loose_px", "realized_r_pb05_loose", bool(r["pb05_loose_filled"]), 0.0
    if policy == "pb02":
        return "entry_pb02_loose_px", "realized_r_pb02_loose", bool(r["pb02_loose_filled"]), 0.0
    if policy == "pb05s":
        return "entry_pb05_strict_px", "realized_r_pb05_strict", bool(r["pb05_strict_filled"]), 0.0
    if policy == "pb02s":
        return "entry_pb02_strict_px", "realized_r_pb02_strict", bool(r["pb02_strict_filled"]), 0.0
    if policy == "conf":
        p = r["prob"]
        if p >= THETA_HIGH:
            return "entry_stop_px", "realized_r_stop_entry", bool(r["breached"]), taker_slip
        if p >= THETA_MID:
            return "entry_pb02_loose_px", "realized_r_pb02_loose", bool(r["pb02_loose_filled"]), 0.0
        return "entry_pb05_loose_px", "realized_r_pb05_loose", bool(r["pb05_loose_filled"]), 0.0
    raise ValueError(policy)


def run_variant(sdf, rank_key, policy, k, conf_sizing, taker_slip=0.0002, label=""):
    days = sorted(sdf["day"].unique())
    eq = CAPITAL0
    rets = []
    n_trades = 0
    rs = []
    for d in days:
        rows = sdf[sdf["day"] == d].nlargest(k, rank_key)
        plans = []
        for _, r in rows.iterrows():
            entry_col, r_col, filled, e_slip = entry_plan(r, policy, taker_slip)
            if not filled:
                continue
            mult = float(np.clip(1.0 + (r["prob"] - 0.5) / 0.5, 0.25, 2.0)) if conf_sizing else 1.0
            risk_dollars = eq * BASE_RISK * mult
            shares = risk_dollars / r["risk_per_share"]
            plans.append((r, entry_col, r_col, e_slip, shares, shares * r[entry_col]))
        notional = sum(p[5] for p in plans)
        scale = min(1.0, LEV_CAP * eq / notional) if notional > 0 else 1.0
        pnl = 0.0
        for r, entry_col, r_col, e_slip, shares, _ in plans:
            rn = net_r(r, entry_col, r_col, e_slip, taker_slip)
            pnl += shares * scale * r["risk_per_share"] * rn
            rs.append(rn)
            n_trades += 1
        rets.append(pnl / eq)
        eq += pnl
    rets = pd.Series(rets)
    eqc = (1 + rets).cumprod()
    total = eqc.iloc[-1] - 1
    ann = (1 + total) ** (252 / len(rets)) - 1
    dd = (eqc / eqc.cummax() - 1).min()
    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0
    rs = np.array(rs)
    print(
        f"{label:42s} ann={ann*100:8.1f}%  maxDD={dd*100:6.2f}%  sharpe={sharpe:5.2f}  "
        f"trades={n_trades:4d} avgR={rs.mean() if len(rs) else 0:+.3f} win={(rs>0).mean()*100 if len(rs) else 0:4.1f}%"
    )


def main():
    sdf = pd.read_parquet(SCORED)
    print(f"OOS rows={len(sdf)} days={sdf['day'].nunique()}\n")
    run_variant(sdf, "rv", "stop", 20, False, label="v1: top20 RV, stop entry")
    run_variant(sdf, "rv", "stop", 5, False, label="A: top5 RV, stop entry")
    run_variant(sdf, "rv", "pb05", 5, False, label="B: top5 RV, pb05 entry")
    run_variant(sdf, "prob", "stop", 5, False, label="C: top5 ML, stop entry")
    run_variant(sdf, "prob", "pb05", 5, False, label="D: top5 ML, pb05 entry")
    run_variant(sdf, "prob", "pb02", 5, False, label="E: top5 ML, pb02 entry")
    run_variant(sdf, "prob", "conf", 5, False, label="F: top5 ML, conf entry, flat size")
    run_variant(sdf, "prob", "conf", 5, True, label="G: full v2 (conf entry + conf size)")
    run_variant(sdf, "prob", "pb05", 5, True, label="H: top5 ML, pb05, conf size")
    run_variant(sdf, "rv", "pb05", 20, False, label="I: top20 RV, pb05 entry")
    run_variant(sdf, "rv", "pb05s", 5, False, label="J: top5 RV, pb05 STRICT fill")
    run_variant(sdf, "prob", "pb05s", 5, False, label="K: top5 ML, pb05 STRICT fill")
    run_variant(sdf, "prob", "pb02s", 5, False, label="L: top5 ML, pb02 STRICT fill")
    run_variant(sdf, "rv", "pb05s", 20, False, label="M: top20 RV, pb05 STRICT fill")
    print("\nslippage stress (strict fills, top5 RV pb05):")
    for slip in [0.0002, 0.0005, 0.001]:
        run_variant(sdf, "rv", "pb05s", 5, False, taker_slip=slip, label=f"  J @ taker slip {slip*1e4:.0f}bps")
    print("\nslippage stress (full v2):")
    for slip in [0.0002, 0.0005, 0.001]:
        run_variant(sdf, "prob", "conf", 5, True, taker_slip=slip, label=f"  v2 @ taker slip {slip*1e4:.0f}bps")
    print("\nhalf-year split (full v2):")
    sdf["d"] = pd.to_datetime(sdf["day"])
    run_variant(sdf[sdf["d"] < "2024-09-01"], "prob", "conf", 5, True, label="  v2 May-Aug")
    run_variant(sdf[sdf["d"] >= "2024-09-01"], "prob", "conf", 5, True, label="  v2 Sep-Dec")


if __name__ == "__main__":
    main()
