#!/usr/bin/env python3
"""Walk-forward LightGBM training + Phase v2 portfolio simulation.

Pipeline:
  1. Load orb_ml_dataset.parquet (one row per ticker/date/OR-window).
  2. Select the OR window per day from the SPY volatility-regime rule.
  3. Walk-forward monthly retrain: train on all days < month M, score month M.
  4. Simulate the v2 portfolio on scored days: top-K by probability,
     confidence-based entry offset + sizing, 4x leverage cap, costs.
  5. Compare against the v1 baseline (top-20 by RV, stop entry, flat 1% risk).

Outputs metrics to stdout and saves the final model artifact.
"""
from __future__ import annotations

import json
import os
import pickle

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = os.path.join(HERE, "data", "orb_ml_dataset.parquet")
ARTIFACT_DIR = os.path.join(HERE, "artifacts")

FEATURES = [
    "rv",
    "gap_pct",
    "gap_abs",
    "atr_pct",
    "range_width_atr",
    "or_close_pos",
    "f5_body_ratio",
    "f5_ret",
    "log_dollar_vol",
    "vol_concentration",
    "prior_day_ret",
    "or_vol_ratio",
    "dow",
    "spy_gap",
    "spy_ret_5m",
    "spy_vwap_dist",
    "spy_vr",
    "window",
]

LGB_PARAMS = dict(
    objective="binary",
    max_depth=4,
    num_leaves=15,
    learning_rate=0.03,
    n_estimators=400,
    min_child_samples=100,
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    reg_lambda=5.0,
    verbosity=-1,
)

# execution-cost model (fractions of price)
TAKER_SLIP = 0.0002  # 2 bps spread-cross slippage
FEES = 0.00005  # 0.5 bps per side
CAPITAL0 = 100_000.0
BASE_RISK = 0.01
LEV_CAP = 4.0
TOP_K = 5
ALPHA = 1.0
THETA_HIGH = 0.60
THETA_MID = 0.45


def regime_window(spy_vr: float) -> int:
    if spy_vr >= 1.3:
        return 10
    if spy_vr < 0.8:
        return 3
    return 5


def net_r(row, entry_px_col, realized_r_col, entry_slip, exit_slip):
    """Realized R net of slippage and fees, in R units."""
    risk = row["risk_per_share"]
    entry_px = row[entry_px_col]
    gross_r = row[realized_r_col]
    exit_px = entry_px + gross_r * risk
    cost = entry_px * (entry_slip + FEES) + exit_px * (exit_slip + FEES)
    return gross_r - cost / risk


def simulate_v2(day_rows: pd.DataFrame, equity: float) -> tuple[float, list[dict]]:
    """One day of the v2 portfolio. Returns (pnl_dollars, trade_records)."""
    sel = day_rows.nlargest(TOP_K, "prob")
    trades = []
    # provisional sizing
    plans = []
    for _, r in sel.iterrows():
        p = r["prob"]
        mult = float(np.clip(1.0 + ALPHA * (p - 0.5) / 0.5, 0.25, 2.0))
        if p >= THETA_HIGH:
            entry_col, r_col, filled, e_slip = "entry_stop_px", "realized_r_stop_entry", True, TAKER_SLIP
        elif p >= THETA_MID:
            filled = bool(r["pb02_loose_filled"])
            entry_col, r_col, e_slip = "entry_pb02_loose_px", "realized_r_pb02_loose", 0.0
        else:
            filled = bool(r["pb05_loose_filled"])
            entry_col, r_col, e_slip = "entry_pb05_loose_px", "realized_r_pb05_loose", 0.0
        if not filled:
            continue
        risk_dollars = equity * BASE_RISK * mult
        shares = risk_dollars / r["risk_per_share"]
        notional = shares * r[entry_col]
        plans.append((r, entry_col, r_col, e_slip, shares, notional, mult))
    total_notional = sum(p[5] for p in plans)
    scale = min(1.0, (LEV_CAP * equity) / total_notional) if total_notional > 0 else 1.0
    pnl = 0.0
    for r, entry_col, r_col, e_slip, shares, notional, mult in plans:
        shares *= scale
        rnet = net_r(r, entry_col, r_col, e_slip, TAKER_SLIP)
        trade_pnl = shares * r["risk_per_share"] * rnet
        pnl += trade_pnl
        trades.append(
            dict(
                day=r["day"],
                ticker=r["ticker"],
                prob=r["prob"],
                mult=mult * scale,
                net_r=rnet,
                pnl=trade_pnl,
                notional=notional * scale,
            )
        )
    return pnl, trades


def simulate_v1(day_rows: pd.DataFrame, equity: float) -> float:
    """v1 baseline: top 20 by RV, stop entry, flat 1% risk, leverage cap."""
    sel = day_rows.nlargest(20, "rv")
    plans = []
    for _, r in sel.iterrows():
        shares = (equity * BASE_RISK) / r["risk_per_share"]
        plans.append((r, shares, shares * r["entry_stop_px"]))
    total_notional = sum(p[2] for p in plans)
    scale = min(1.0, (LEV_CAP * equity) / total_notional) if total_notional > 0 else 1.0
    pnl = 0.0
    for r, shares, _ in plans:
        rnet = net_r(r, "entry_stop_px", "realized_r_stop_entry", TAKER_SLIP, TAKER_SLIP)
        pnl += shares * scale * r["risk_per_share"] * rnet
    return pnl


def equity_metrics(daily: pd.Series, label: str) -> dict:
    eq = (1 + daily).cumprod()
    n = len(daily)
    total = eq.iloc[-1] - 1
    ann = (1 + total) ** (252 / n) - 1
    dd = (eq / eq.cummax() - 1).min()
    sharpe = daily.mean() / daily.std() * np.sqrt(252) if daily.std() > 0 else 0.0
    print(
        f"{label:28s} days={n:3d} total={total*100:7.2f}%  ann={ann*100:7.2f}%  "
        f"maxDD={dd*100:6.2f}%  sharpe={sharpe:5.2f}"
    )
    return dict(days=n, total=total, annualized=ann, max_dd=dd, sharpe=sharpe)


def main() -> None:
    df = pd.read_parquet(DATASET)
    df["day"] = pd.to_datetime(df["day"]).dt.date
    df["month"] = pd.PeriodIndex(pd.to_datetime(df["day"]), freq="M")
    df["label"] = df["hit_2r_before_stop"].astype(int)

    # adaptive window per day from SPY regime
    day_vr = df.groupby("day")["spy_vr"].first()
    chosen = {d: regime_window(v) for d, v in day_vr.items()}
    df["chosen_window"] = df["day"].map(chosen)
    adf = df[df["window"] == df["chosen_window"]].copy()
    print(f"dataset rows={len(df)}, adaptive-window rows={len(adf)}, days={adf['day'].nunique()}")
    print("window distribution:", adf.groupby("window")["day"].nunique().to_dict())

    months = sorted(adf["month"].unique())
    min_train_months = 4
    scored = []
    aucs = []
    for mi in range(min_train_months, len(months)):
        m = months[mi]
        # train on all OR windows (3x data); evaluate on the adaptive rows only
        tr = df[df["month"] < m]
        te = adf[adf["month"] == m].copy()
        if te.empty or len(tr) < 500:
            continue
        model = lgb.LGBMClassifier(**LGB_PARAMS)
        model.fit(tr[FEATURES], tr["label"])
        te["prob"] = model.predict_proba(te[FEATURES])[:, 1]
        if te["label"].nunique() > 1:
            aucs.append((str(m), roc_auc_score(te["label"], te["prob"]), len(te)))
        scored.append(te)
    sdf = pd.concat(scored, ignore_index=True)
    print("\nOOS months:", [str(m) for m, _, _ in aucs])
    for m, auc, nrows in aucs:
        print(f"  {m}: AUC={auc:.3f} n={nrows}")
    w = np.array([n for _, _, n in aucs])
    a = np.array([x for _, x, _ in aucs])
    print(f"weighted OOS AUC = {(a*w).sum()/w.sum():.3f}")

    # precision@K
    p_at_k = (
        sdf.sort_values("prob", ascending=False).groupby("day").head(TOP_K).groupby("day")["label"].mean()
    )
    base_rate = sdf.groupby("day")["label"].mean()
    print(f"precision@{TOP_K} = {p_at_k.mean():.3f}  vs base rate = {base_rate.mean():.3f}")

    # --- portfolio simulations on OOS days ---
    days = sorted(sdf["day"].unique())
    eq_v2, eq_v1 = CAPITAL0, CAPITAL0
    rets_v2, rets_v1 = [], []
    all_trades = []
    for d in days:
        rows = sdf[sdf["day"] == d]
        pnl2, trades = simulate_v2(rows, eq_v2)
        pnl1 = simulate_v1(rows, eq_v1)
        rets_v2.append(pnl2 / eq_v2)
        rets_v1.append(pnl1 / eq_v1)
        eq_v2 += pnl2
        eq_v1 += pnl1
        all_trades.extend(trades)
    rets_v2 = pd.Series(rets_v2, index=pd.to_datetime(days))
    rets_v1 = pd.Series(rets_v1, index=pd.to_datetime(days))
    print()
    m1 = equity_metrics(rets_v1, "v1 baseline (top20 RV)")
    m2 = equity_metrics(rets_v2, "v2 ML (top5, adaptive)")

    tdf = pd.DataFrame(all_trades)
    if not tdf.empty:
        print(
            f"\nv2 trades={len(tdf)} ({len(tdf)/len(days):.1f}/day) win={np.mean(tdf['net_r']>0)*100:.1f}% "
            f"avg netR={tdf['net_r'].mean():.3f}"
        )

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    final_model = lgb.LGBMClassifier(**LGB_PARAMS)
    final_model.fit(df[FEATURES], df["label"])
    with open(os.path.join(ARTIFACT_DIR, "lgbm_orb_v2.pkl"), "wb") as f:
        pickle.dump({"model": final_model, "features": FEATURES}, f)
    imp = sorted(zip(FEATURES, final_model.feature_importances_), key=lambda x: -x[1])
    print("\nfeature importance:", [(n, int(v)) for n, v in imp])
    with open(os.path.join(ARTIFACT_DIR, "oos_metrics.json"), "w") as f:
        json.dump({"v1": m1, "v2": m2}, f, indent=2, default=float)
    sdf.to_parquet(os.path.join(ARTIFACT_DIR, "oos_scored.parquet"), index=False)
    tdf.to_parquet(os.path.join(ARTIFACT_DIR, "v2_trades.parquet"), index=False)


if __name__ == "__main__":
    main()
