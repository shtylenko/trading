"""Profitability metrics + a realistic equal-weight capped portfolio curve.

Ranking is driven by %-return-per-trade statistics (net of costs) — these are
directly comparable across strategies regardless of stop convention. R-multiple
stats are kept only as reference (they are distorted for strategies whose stop
distance varies widely and that rarely exit at the stop).

The portfolio curve = greedy N-slot, equal-weight (1/N of equity per position),
exit-order compounding. With <=3-session holds this closely tracks realized
per-trade returns and cannot blow up from leverage, so CAGR sign always agrees
with mean per-trade return.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _years(trades: pd.DataFrame) -> float:
    d = pd.to_datetime(trades["entry_date"])
    return max((d.max() - d.min()).days / 365.25, 1e-6)


def trade_metrics(trades: pd.DataFrame) -> dict:
    if trades is None or trades.empty:
        return {"n_trades": 0}
    r = trades["pnl_pct"].to_numpy(float)          # net %-return per trade
    rr = trades["realized_r"].to_numpy(float)      # net R (reference only)
    wins = r[r > 0]
    losses = r[r < 0]
    n = len(r)
    tpy = n / _years(trades)
    std = r.std(ddof=1) if n > 1 else np.nan
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf
    t_stat = r.mean() / (std / np.sqrt(n)) if std and std > 0 else np.nan
    ann_sharpe = (r.mean() / std * np.sqrt(tpy)) if std and std > 0 else np.nan
    # day-clustered t-stat: trades on the same calendar day are cross-sectionally
    # correlated (one market move), so the iid t-stat overstates significance.
    # Equal-weight each entry_date, then t-test the daily-mean series.
    dm = trades.groupby("entry_date")["pnl_pct"].mean().to_numpy(float)
    nd = len(dm)
    dstd = dm.std(ddof=1) if nd > 1 else np.nan
    t_stat_day = dm.mean() / (dstd / np.sqrt(nd)) if dstd and dstd > 0 else np.nan
    return {
        "n_trades": int(n),
        "trades_per_year": round(tpy, 1),
        "win_rate": round(float((r > 0).mean()), 4),
        "avg_ret_net": round(float(r.mean()), 5),          # %/trade, net of costs
        "median_ret": round(float(np.median(r)), 5),
        "avg_win": round(float(wins.mean()), 5) if len(wins) else 0.0,
        "avg_loss": round(float(losses.mean()), 5) if len(losses) else 0.0,
        "profit_factor": round(float(pf), 3),
        "t_stat": round(float(t_stat), 2) if t_stat == t_stat else np.nan,
        "t_stat_day": round(float(t_stat_day), 2) if t_stat_day == t_stat_day else np.nan,
        "n_days": int(nd),
        "ann_sharpe": round(float(ann_sharpe), 2) if ann_sharpe == ann_sharpe else np.nan,
        "expectancy_R": round(float(rr.mean()), 4),        # reference
        "avg_hold_days": round(float(trades["hold_days"].mean()), 2),
        "pct_stop": round(float(trades["exit_reason"].isin(["stop", "stop_gap"]).mean()), 3),
        "pct_time_exit": round(float((trades["exit_reason"] == "time").mean()), 3),
        "pct_target": round(float((trades["exit_reason"] == "target").mean()), 3),
    }


def portfolio_metrics(trades: pd.DataFrame, *, max_concurrent: int = 8) -> dict:
    """Greedy N-slot, equal-weight, exit-order compounding equity curve."""
    if trades is None or trades.empty:
        return {"cagr": 0.0, "sharpe_m": np.nan, "max_dd": 0.0, "n_taken": 0, "fill_rate": 0.0}
    t = trades.sort_values("entry_date").reset_index(drop=True)
    open_exits: list = []
    taken = []
    for _, row in t.iterrows():
        ed = pd.Timestamp(row["entry_date"])
        open_exits = [x for x in open_exits if x >= ed]
        if len(open_exits) < max_concurrent:
            open_exits.append(pd.Timestamp(row["exit_date"]))
            taken.append(row)
    tk = pd.DataFrame(taken).sort_values("exit_date")
    if tk.empty:
        return {"cagr": 0.0, "sharpe_m": np.nan, "max_dd": 0.0, "n_taken": 0, "fill_rate": 0.0}

    w = 1.0 / max_concurrent
    eq = 1.0
    rows = []
    for _, row in tk.iterrows():
        eq *= (1.0 + w * float(row["pnl_pct"]))
        rows.append((pd.Timestamp(row["exit_date"]), eq))
    cur = pd.Series({d: e for d, e in rows}).groupby(level=0).last()
    monthly = cur.resample("ME").last().ffill()
    mret = monthly.pct_change().dropna()
    yrs = _years(t)
    cagr = eq ** (1.0 / yrs) - 1.0 if eq > 0 else -1.0
    sharpe = (mret.mean() / mret.std(ddof=1) * np.sqrt(12)) if mret.std(ddof=1) else np.nan
    run_max = cur.cummax()
    max_dd = float(((cur - run_max) / run_max).min())
    return {
        "cagr": round(float(cagr), 4),
        "sharpe_m": round(float(sharpe), 2) if sharpe == sharpe else np.nan,
        "max_dd": round(max_dd, 4),
        "final_equity": round(float(eq), 3),
        "n_taken": int(len(tk)),
        "fill_rate": round(len(tk) / len(t), 3),
    }


def summarize(name: str, trades: pd.DataFrame, *, horizon: str = "daily", **pkw) -> dict:
    m = {"strategy": name, "horizon": horizon}
    m.update(trade_metrics(trades))
    if trades is not None and not trades.empty:
        m.update(portfolio_metrics(trades, **pkw))
    return m
