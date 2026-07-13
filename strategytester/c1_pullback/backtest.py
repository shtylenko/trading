"""Daily trade simulation for C1_MR and C1_PB (separate systems).

Decisions locked for v1
-----------------------
* **C1_MR entry:** ``next_open`` (signal close used only for the screen; fill
  next session open). Optional ``signal_close`` for optimistic MOC comparison.
* **C1_PB entry:** daily proxy — buy stop at ``signal_high * (1 + buffer)`` on
  the next session (not full 15m VWAP/OR reclaim).
* **Costs:** fixed bps per side on entry and exit prices.
* **Stops:** if the open gaps through the stop, fill at the open.
* **Same-bar OHLC ambiguity:** stop checked before target (conservative).
* **Overlap:** at most one open position per ticker (configurable).
* **No scale-in / no averaging down.**
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
import yaml

from trading.swing_screener.c1_pullback.rules import C1Config, load_config
from trading.swing_screener.data.panel import load_enriched_panel

logger = logging.getLogger("trading.swing_screener.c1_pullback.backtest")

_DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "c1_pullback.yaml"


@dataclass(frozen=True)
class MRBacktestConfig:
    entry_mode: str = "next_open"  # next_open | signal_close
    stop_atr_mult: float = 2.0
    stop_pct_cap: float = 0.08
    rsi2_exit: float = 65.0
    max_hold_days: int = 5


@dataclass(frozen=True)
class PBBacktestConfig:
    entry_stop_buffer: float = 0.01
    max_gap_atr: float = 0.75
    pullback_lookback: int = 5
    stop_atr_buffer: float = 0.10
    max_stop_atr: float = 1.25
    target_r: float = 2.0
    max_hold_days: int = 7
    no_progress_days: int = 2


@dataclass(frozen=True)
class BacktestConfig:
    cost_bps_per_side: float = 5.0
    one_position_per_ticker: bool = True
    mr: MRBacktestConfig = field(default_factory=MRBacktestConfig)
    pb: PBBacktestConfig = field(default_factory=PBBacktestConfig)


def load_backtest_config(path: str | Path | None = None) -> BacktestConfig:
    p = Path(path) if path else _DEFAULT_CONFIG
    raw: dict[str, Any] = {}
    if p.exists():
        loaded = yaml.safe_load(p.read_text()) or {}
        raw = (loaded.get("backtest") or {}) if isinstance(loaded, dict) else {}
    mr = raw.get("mr") or {}
    pb = raw.get("pb") or {}
    return BacktestConfig(
        cost_bps_per_side=float(raw.get("cost_bps_per_side", 5.0)),
        one_position_per_ticker=bool(raw.get("one_position_per_ticker", True)),
        mr=MRBacktestConfig(
            entry_mode=str(mr.get("entry_mode", "next_open")),
            stop_atr_mult=float(mr.get("stop_atr_mult", 2.0)),
            stop_pct_cap=float(mr.get("stop_pct_cap", 0.08)),
            rsi2_exit=float(mr.get("rsi2_exit", 65.0)),
            max_hold_days=int(mr.get("max_hold_days", 5)),
        ),
        pb=PBBacktestConfig(
            entry_stop_buffer=float(pb.get("entry_stop_buffer", 0.01)),
            max_gap_atr=float(pb.get("max_gap_atr", 0.75)),
            pullback_lookback=int(pb.get("pullback_lookback", 5)),
            stop_atr_buffer=float(pb.get("stop_atr_buffer", 0.10)),
            max_stop_atr=float(pb.get("max_stop_atr", 1.25)),
            target_r=float(pb.get("target_r", 2.0)),
            max_hold_days=int(pb.get("max_hold_days", 7)),
            no_progress_days=int(pb.get("no_progress_days", 2)),
        ),
    )


def _session_dates(index: pd.DatetimeIndex | pd.Index) -> np.ndarray:
    idx = pd.to_datetime(index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    # numpy datetime64[D]
    return idx.normalize().to_numpy(dtype="datetime64[D]")


def _cost_mult(side_bps: float) -> float:
    return side_bps / 10_000.0


def _apply_entry_cost(price: float, bps: float) -> float:
    return price * (1.0 + _cost_mult(bps))


def _apply_exit_cost(price: float, bps: float) -> float:
    return price * (1.0 - _cost_mult(bps))


def _r_multiple(entry: float, exit_: float, risk: float) -> float:
    if risk <= 0 or not np.isfinite(risk):
        return float("nan")
    return (exit_ - entry) / risk


@dataclass
class _BarFrame:
    dates: np.ndarray  # datetime64[D]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    rsi2: np.ndarray
    sma5: np.ndarray
    atr14: np.ndarray
    date_to_i: dict[date, int]

    @classmethod
    def from_df(cls, df: pd.DataFrame) -> "_BarFrame":
        need = ["open", "high", "low", "close", "rsi2", "sma5", "atr14"]
        missing = [c for c in need if c not in df.columns]
        if missing:
            raise ValueError(f"enriched frame missing columns: {missing}")
        dates = _session_dates(df.index)
        date_to_i: dict[date, int] = {}
        for i, d in enumerate(dates):
            py = pd.Timestamp(d).date()
            date_to_i[py] = i  # last bar wins if duplicates
        return cls(
            dates=dates,
            open=df["open"].to_numpy(dtype=float),
            high=df["high"].to_numpy(dtype=float),
            low=df["low"].to_numpy(dtype=float),
            close=df["close"].to_numpy(dtype=float),
            rsi2=df["rsi2"].to_numpy(dtype=float),
            sma5=df["sma5"].to_numpy(dtype=float),
            atr14=df["atr14"].to_numpy(dtype=float),
            date_to_i=date_to_i,
        )


def simulate_mr_trades(
    bars: _BarFrame,
    signal_dates: Sequence[date],
    *,
    ticker: str,
    cfg: BacktestConfig,
    rules_version: str,
) -> list[dict[str, Any]]:
    """Simulate C1_MR trades for one ticker given signal session dates."""
    mcfg = cfg.mr
    bps = cfg.cost_bps_per_side
    trades: list[dict[str, Any]] = []
    flat_after_i = -1  # last exit bar index (inclusive); free after this

    for sig in sorted(set(signal_dates)):
        si = bars.date_to_i.get(sig)
        if si is None:
            continue

        if mcfg.entry_mode == "signal_close":
            ei = si
            raw_entry = float(bars.close[si])
        elif mcfg.entry_mode == "next_open":
            ei = si + 1
            if ei >= len(bars.close):
                continue
            raw_entry = float(bars.open[ei])
        else:
            raise ValueError(f"Unknown MR entry_mode: {mcfg.entry_mode}")

        if cfg.one_position_per_ticker and ei <= flat_after_i:
            continue

        atr_s = float(bars.atr14[si])
        if not np.isfinite(atr_s) or atr_s <= 0 or not np.isfinite(raw_entry) or raw_entry <= 0:
            continue

        entry = _apply_entry_cost(raw_entry, bps)
        stop_dist = min(mcfg.stop_atr_mult * atr_s, mcfg.stop_pct_cap * entry)
        if stop_dist <= 0:
            continue
        stop = entry - stop_dist
        risk = entry - stop
        if risk <= 0:
            continue

        exit_i = None
        exit_raw = None
        reason = None
        last_i = min(ei + mcfg.max_hold_days - 1, len(bars.close) - 1)

        for d in range(ei, last_i + 1):
            day_num = d - ei + 1
            o, h, l, c = (
                float(bars.open[d]),
                float(bars.high[d]),
                float(bars.low[d]),
                float(bars.close[d]),
            )
            # Stop (gap through → open)
            if l <= stop:
                exit_raw = o if o < stop else stop
                exit_i = d
                reason = "stop"
                break
            # Signal exits (close-based) — not on entry day for next_open if same bar? allowed
            rsi = float(bars.rsi2[d])
            sma5 = float(bars.sma5[d])
            if np.isfinite(rsi) and rsi > mcfg.rsi2_exit:
                exit_raw = c
                exit_i = d
                reason = "rsi2_exit"
                break
            if np.isfinite(sma5) and c > sma5:
                exit_raw = c
                exit_i = d
                reason = "sma5_exit"
                break
            if day_num >= mcfg.max_hold_days:
                exit_raw = c
                exit_i = d
                reason = "time"
                break

        if exit_i is None or exit_raw is None:
            continue

        exit_px = _apply_exit_cost(float(exit_raw), bps)
        rr = _r_multiple(entry, exit_px, risk)
        hold = exit_i - ei + 1
        trades.append(
            {
                "ticker": ticker,
                "variant": "C1_MR",
                "signal_date": sig,
                "entry_date": pd.Timestamp(bars.dates[ei]).date(),
                "exit_date": pd.Timestamp(bars.dates[exit_i]).date(),
                "entry_price": entry,
                "exit_price": exit_px,
                "stop_price": stop,
                "risk_per_share": risk,
                "realized_r": rr,
                "pnl_pct": (exit_px / entry - 1.0) if entry else float("nan"),
                "hold_days": hold,
                "exit_reason": reason,
                "entry_mode": mcfg.entry_mode,
                "rules_version": rules_version,
                "cost_bps_per_side": bps,
            }
        )
        flat_after_i = exit_i

    return trades


def simulate_pb_trades(
    bars: _BarFrame,
    signal_dates: Sequence[date],
    *,
    ticker: str,
    cfg: BacktestConfig,
    rules_version: str,
) -> list[dict[str, Any]]:
    """Simulate C1_PB daily-proxy trades for one ticker."""
    pcfg = cfg.pb
    bps = cfg.cost_bps_per_side
    trades: list[dict[str, Any]] = []
    flat_after_i = -1

    for sig in sorted(set(signal_dates)):
        si = bars.date_to_i.get(sig)
        if si is None:
            continue
        ei = si + 1  # attempt entry next session
        if ei >= len(bars.close):
            continue
        if cfg.one_position_per_ticker and ei <= flat_after_i:
            continue

        atr_s = float(bars.atr14[si])
        sig_high = float(bars.high[si])
        if not np.isfinite(atr_s) or atr_s <= 0 or not np.isfinite(sig_high):
            continue

        trigger = sig_high * (1.0 + pcfg.entry_stop_buffer)
        o1 = float(bars.open[ei])
        h1 = float(bars.high[ei])
        # Chase skip: gap too far above trigger
        if o1 > trigger + pcfg.max_gap_atr * atr_s:
            continue
        if h1 < trigger:
            # stop not reached — no fill
            continue
        raw_entry = o1 if o1 >= trigger else trigger

        # Pullback low: min low over lookback ending on signal day
        lo = max(0, si - pcfg.pullback_lookback + 1)
        pb_low = float(np.nanmin(bars.low[lo : si + 1]))
        stop = pb_low - pcfg.stop_atr_buffer * atr_s
        entry = _apply_entry_cost(raw_entry, bps)
        risk = entry - stop
        if risk <= 0:
            continue
        if risk > pcfg.max_stop_atr * atr_s:
            continue  # skip wide stops

        target = entry + pcfg.target_r * risk
        exit_i = None
        exit_raw = None
        reason = None
        last_i = min(ei + pcfg.max_hold_days - 1, len(bars.close) - 1)
        saw_higher_close = False

        for d in range(ei, last_i + 1):
            day_num = d - ei + 1
            o, h, l, c = (
                float(bars.open[d]),
                float(bars.high[d]),
                float(bars.low[d]),
                float(bars.close[d]),
            )
            if c > entry:
                saw_higher_close = True

            # Conservative: stop before target if both print
            if l <= stop:
                exit_raw = o if o < stop else stop
                exit_i = d
                reason = "stop"
                break
            if h >= target:
                exit_raw = target
                # if open gapped above target, fill open
                if o >= target:
                    exit_raw = o
                exit_i = d
                reason = "target"
                break

            # No progress: after no_progress_days closes, still never closed higher
            if day_num >= pcfg.no_progress_days and not saw_higher_close:
                exit_raw = c
                exit_i = d
                reason = "no_progress"
                break

            if day_num >= pcfg.max_hold_days:
                exit_raw = c
                exit_i = d
                reason = "time"
                break

        if exit_i is None or exit_raw is None:
            continue

        exit_px = _apply_exit_cost(float(exit_raw), bps)
        rr = _r_multiple(entry, exit_px, risk)
        trades.append(
            {
                "ticker": ticker,
                "variant": "C1_PB",
                "signal_date": sig,
                "entry_date": pd.Timestamp(bars.dates[ei]).date(),
                "exit_date": pd.Timestamp(bars.dates[exit_i]).date(),
                "entry_price": entry,
                "exit_price": exit_px,
                "stop_price": stop,
                "risk_per_share": risk,
                "realized_r": rr,
                "pnl_pct": (exit_px / entry - 1.0) if entry else float("nan"),
                "hold_days": exit_i - ei + 1,
                "exit_reason": reason,
                "entry_mode": "next_day_buy_stop",
                "rules_version": rules_version,
                "cost_bps_per_side": bps,
            }
        )
        flat_after_i = exit_i

    return trades


def _normalize_signal_date(v: Any) -> date:
    if isinstance(v, date) and not isinstance(v, pd.Timestamp):
        return v
    return pd.Timestamp(v).date()


def run_backtest(
    candidates: pd.DataFrame,
    *,
    cfg: C1Config | None = None,
    bt_cfg: BacktestConfig | None = None,
    variants: Sequence[str] = ("C1_MR", "C1_PB"),
    end_pad_calendar_days: int = 30,
    workers: int = 1,
    progress_every: int = 100,
) -> pd.DataFrame:
    """Simulate trades for candidate rows.

    Parameters
    ----------
    candidates
        Output of the C1 screen (needs asof_date, ticker, variant).
    """
    cfg = cfg or load_config()
    bt_cfg = bt_cfg or load_backtest_config()
    if candidates is None or candidates.empty:
        return pd.DataFrame()

    df = candidates.copy()
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["variant"] = df["variant"].astype(str)
    df["asof_date"] = df["asof_date"].map(_normalize_signal_date)
    variants_set = set(variants)
    df = df[df["variant"].isin(variants_set)]
    if df.empty:
        return pd.DataFrame()

    tickers = sorted(df["ticker"].unique())
    min_d = min(df["asof_date"])
    max_d = max(df["asof_date"])
    fetch_end = max_d + timedelta(days=end_pad_calendar_days)

    logger.info(
        "backtest load panel: %d tickers, signals %s..%s",
        len(tickers),
        min_d,
        max_d,
    )
    panel = load_enriched_panel(
        tickers,
        min_d,
        fetch_end,
        adjustment=cfg.adjustment,
        warmup_calendar_days=cfg.warmup_calendar_days,
        workers=workers,
        progress_every=progress_every,
    )

    all_trades: list[dict[str, Any]] = []
    for i, ticker in enumerate(tickers, 1):
        bars_df = panel.get(ticker)
        if bars_df is None or bars_df.empty:
            continue
        try:
            bars = _BarFrame.from_df(bars_df)
        except ValueError as e:
            logger.warning("%s: %s", ticker, e)
            continue
        sub = df[df["ticker"] == ticker]
        if "C1_MR" in variants_set:
            sigs = sub.loc[sub["variant"] == "C1_MR", "asof_date"].tolist()
            if sigs:
                all_trades.extend(
                    simulate_mr_trades(
                        bars,
                        sigs,
                        ticker=ticker,
                        cfg=bt_cfg,
                        rules_version=cfg.rules_version,
                    )
                )
        if "C1_PB" in variants_set:
            sigs = sub.loc[sub["variant"] == "C1_PB", "asof_date"].tolist()
            if sigs:
                all_trades.extend(
                    simulate_pb_trades(
                        bars,
                        sigs,
                        ticker=ticker,
                        cfg=bt_cfg,
                        rules_version=cfg.rules_version,
                    )
                )
        if progress_every and i % progress_every == 0:
            logger.info("simulated %d/%d tickers (%d trades)", i, len(tickers), len(all_trades))

    if not all_trades:
        return pd.DataFrame()
    out = pd.DataFrame(all_trades)
    out = out.sort_values(["variant", "entry_date", "ticker"]).reset_index(drop=True)
    logger.info("total trades: %d", len(out))
    return out


def summarize_trades(trades: pd.DataFrame) -> pd.DataFrame:
    """Win rate, expectancy, and exit mix by variant and year."""
    if trades is None or trades.empty:
        return pd.DataFrame()
    t = trades.copy()
    t["year"] = pd.to_datetime(t["entry_date"]).dt.year
    t["win"] = t["realized_r"] > 0

    rows = []
    for (year, variant), g in t.groupby(["year", "variant"]):
        n = len(g)
        wins = int(g["win"].sum())
        r = g["realized_r"].astype(float)
        rows.append(
            {
                "year": int(year),
                "variant": variant,
                "n_trades": n,
                "n_wins": wins,
                "win_rate": wins / n if n else float("nan"),
                "avg_r": float(r.mean()),
                "median_r": float(r.median()),
                "expectancy_r": float(r.mean()),
                "sum_r": float(r.sum()),
                "avg_win_r": float(r[r > 0].mean()) if (r > 0).any() else float("nan"),
                "avg_loss_r": float(r[r <= 0].mean()) if (r <= 0).any() else float("nan"),
                "profit_factor": (
                    float(r[r > 0].sum() / abs(r[r <= 0].sum()))
                    if (r <= 0).any() and r[r <= 0].sum() != 0
                    else float("nan")
                ),
                "avg_hold_days": float(g["hold_days"].mean()),
                "stop_pct": float((g["exit_reason"] == "stop").mean()),
                "time_pct": float((g["exit_reason"] == "time").mean()),
            }
        )
    # Overall per variant
    for variant, g in t.groupby("variant"):
        n = len(g)
        wins = int(g["win"].sum())
        r = g["realized_r"].astype(float)
        rows.append(
            {
                "year": 0,  # overall
                "variant": variant,
                "n_trades": n,
                "n_wins": wins,
                "win_rate": wins / n if n else float("nan"),
                "avg_r": float(r.mean()),
                "median_r": float(r.median()),
                "expectancy_r": float(r.mean()),
                "sum_r": float(r.sum()),
                "avg_win_r": float(r[r > 0].mean()) if (r > 0).any() else float("nan"),
                "avg_loss_r": float(r[r <= 0].mean()) if (r <= 0).any() else float("nan"),
                "profit_factor": (
                    float(r[r > 0].sum() / abs(r[r <= 0].sum()))
                    if (r <= 0).any() and r[r <= 0].sum() != 0
                    else float("nan")
                ),
                "avg_hold_days": float(g["hold_days"].mean()),
                "stop_pct": float((g["exit_reason"] == "stop").mean()),
                "time_pct": float((g["exit_reason"] == "time").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["variant", "year"]).reset_index(drop=True)
