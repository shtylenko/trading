"""Daily trade simulation for C2_BREAKOUT."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Sequence

import numpy as np
import pandas as pd

from trading.swing_screener.c2_breakout.indicators import enrich_c2
from trading.swing_screener.c2_breakout.rules import C2Config, load_config
from trading.swing_screener.c2_breakout.screen import _load_spy_perf_21d
from trading.swing_screener.data.panel import load_enriched_panel

logger = logging.getLogger("trading.swing_screener.c2_breakout.backtest")


def _cost_entry(px: float, bps: float) -> float:
    return px * (1.0 + bps / 10_000.0)


def _cost_exit(px: float, bps: float) -> float:
    return px * (1.0 - bps / 10_000.0)


def _session_dates(index) -> np.ndarray:
    idx = pd.to_datetime(index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    return idx.normalize().to_numpy(dtype="datetime64[D]")


def simulate_c2_trades(
    df: pd.DataFrame,
    signal_dates: Sequence[date],
    *,
    ticker: str,
    cfg: C2Config,
) -> list[dict[str, Any]]:
    bt = cfg.backtest
    bps = bt.cost_bps_per_side
    dates = _session_dates(df.index)
    date_to_i = {pd.Timestamp(d).date(): i for i, d in enumerate(dates)}
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    atr = df["atr14"].to_numpy(dtype=float)
    pivot_a = df["pivot"].to_numpy(dtype=float)
    base_low_a = df["base_low"].to_numpy(dtype=float)

    trades: list[dict[str, Any]] = []
    flat_after = -1

    for sig in sorted(set(signal_dates)):
        si = date_to_i.get(sig)
        if si is None:
            continue
        ei = si + 1 if bt.entry_mode == "next_open" else si
        if ei >= len(c):
            continue
        if bt.one_position_per_ticker and ei <= flat_after:
            continue

        pivot = float(pivot_a[si])
        base_low = float(base_low_a[si])
        atr_s = float(atr[si])
        if not all(np.isfinite(x) for x in (pivot, base_low, atr_s)) or atr_s <= 0:
            continue

        if bt.entry_mode == "next_open":
            raw_entry = float(o[ei])
            if raw_entry > pivot + bt.max_gap_atr * atr_s:
                continue  # chase skip
        else:
            raw_entry = float(c[si])
            ei = si

        entry = _cost_entry(raw_entry, bps)
        # Prefer structural base_low stop; if wider than risk cap, tighten to cap
        # (small-account rule) rather than skipping every deep base.
        structural_stop = base_low - bt.stop_atr_buffer * atr_s
        cap_stop = entry - bt.max_stop_atr * atr_s
        pct_stop = entry * (1.0 - bt.max_stop_pct)
        stop = max(structural_stop, cap_stop, pct_stop)
        risk = entry - stop
        if risk <= 0 or not np.isfinite(risk):
            continue

        target = entry + bt.target_r * risk
        last_i = min(ei + bt.max_hold_days - 1, len(c) - 1)
        exit_i = exit_raw = reason = None

        for d in range(ei, last_i + 1):
            day_num = d - ei + 1
            od, hd, ld, cd = float(o[d]), float(h[d]), float(l[d]), float(c[d])

            # stop first
            if ld <= stop:
                exit_raw = od if od < stop else stop
                exit_i = d
                reason = "stop"
                break
            # target
            if hd >= target:
                exit_raw = od if od >= target else target
                exit_i = d
                reason = "target"
                break
            # failed breakout: close back below pivot
            if cd < pivot:
                exit_raw = cd
                exit_i = d
                reason = "failed_breakout"
                break
            # no progress
            if day_num >= bt.no_progress_days:
                unreal_r = (cd - entry) / risk
                if unreal_r < bt.no_progress_min_r:
                    exit_raw = cd
                    exit_i = d
                    reason = "no_progress"
                    break
            if day_num >= bt.max_hold_days:
                exit_raw = cd
                exit_i = d
                reason = "time"
                break

        if exit_i is None or exit_raw is None:
            continue

        exit_px = _cost_exit(float(exit_raw), bps)
        rr = (exit_px - entry) / risk
        trades.append(
            {
                "ticker": ticker,
                "variant": "C2_BREAKOUT",
                "signal_date": sig,
                "entry_date": pd.Timestamp(dates[ei]).date(),
                "exit_date": pd.Timestamp(dates[exit_i]).date(),
                "entry_price": entry,
                "exit_price": exit_px,
                "stop_price": stop,
                "pivot": pivot,
                "risk_per_share": risk,
                "realized_r": rr,
                "pnl_pct": exit_px / entry - 1.0,
                "hold_days": exit_i - ei + 1,
                "exit_reason": reason,
                "entry_mode": bt.entry_mode,
                "rules_version": cfg.rules_version,
                "cost_bps_per_side": bps,
            }
        )
        flat_after = exit_i
    return trades


def run_backtest(
    candidates: pd.DataFrame,
    *,
    cfg: C2Config | None = None,
    end_pad_calendar_days: int = 30,
    workers: int = 1,
    progress_every: int = 100,
) -> pd.DataFrame:
    cfg = cfg or load_config()
    if candidates is None or candidates.empty:
        return pd.DataFrame()

    df = candidates.copy()
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["asof_date"] = pd.to_datetime(df["asof_date"]).dt.date
    tickers = sorted(df["ticker"].unique())
    min_d = min(df["asof_date"])
    max_d = max(df["asof_date"])
    fetch_end = max_d + timedelta(days=end_pad_calendar_days)

    logger.info("C2 backtest panel: %d tickers %s..%s", len(tickers), min_d, max_d)
    panel = load_enriched_panel(
        tickers,
        min_d,
        fetch_end,
        adjustment=cfg.adjustment,
        warmup_calendar_days=cfg.warmup_calendar_days,
        workers=workers,
        progress_every=progress_every,
    )
    spy_perf = _load_spy_perf_21d(
        min_d, fetch_end, cfg.warmup_calendar_days, cfg.adjustment
    )

    all_trades: list[dict[str, Any]] = []
    for i, ticker in enumerate(tickers, 1):
        raw = panel.get(ticker)
        if raw is None or raw.empty:
            continue
        cols = [c for c in ("open", "high", "low", "close", "volume") if c in raw.columns]
        en = enrich_c2(
            raw[cols], base_lookback=cfg.base_lookback, spy_perf_21d=spy_perf
        )
        sigs = df.loc[df["ticker"] == ticker, "asof_date"].tolist()
        all_trades.extend(
            simulate_c2_trades(en, sigs, ticker=ticker, cfg=cfg)
        )
        if progress_every and i % progress_every == 0:
            logger.info("simulated %d/%d (%d trades)", i, len(tickers), len(all_trades))

    if not all_trades:
        return pd.DataFrame()
    out = pd.DataFrame(all_trades)
    return out.sort_values(["entry_date", "ticker"]).reset_index(drop=True)
