"""B — intraday entry detection (ACD / ORB flat-top breakout).

Encodes Cameron's *core* entry: the first 5-minute candle to make a **new high
out of a consolidation / opening range**, inside the morning window, with volume
expansion and price holding above VWAP. One primary entry per ticker per day.

This is a mechanical subset — it does not read Level 2 / tape / chart
"cleanliness". Those are proxied by: a real consolidation pause before the
break, a volume-expansion gate, and a VWAP filter (uptrend confirmation).

Source: ``fetch_bars(..., "5min", session="extended", adjustment="raw")``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from trading.marketdata import fetch_bars

from trading.llm_trader.indicators import prepare_detection_frame, session_vwap
from trading.llm_trader.models import Entry

from .config import ScanConfig
from .screen import GapCandidate


def _fmt_float(f: Optional[float]) -> str:
    if f is None:
        return "float n/a"
    return f"float {f / 1e6:.1f}M"


def detect_entry(
    cand: GapCandidate,
    cfg: ScanConfig,
    float_shares: Optional[float],
) -> Optional[Entry]:
    """Detect the first ACD/ORB breakout for one gap candidate, or None.

    Fetches the day's 5-minute extended bars and delegates the (pure) breakout
    logic to :func:`detect_from_frame`. Returns None if intraday bars for the
    day are unavailable (e.g. on-demand fetch blocked by provider access).
    """
    day = cand.day
    start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    df = fetch_bars(
        cand.ticker, "5min", start=start, end=end, session="extended", adjustment="raw"
    )
    if df is None or df.empty:
        return None
    return detect_from_frame(df, cand, cfg, float_shares)


def detect_from_frame(
    df: pd.DataFrame,
    cand: GapCandidate,
    cfg: ScanConfig,
    float_shares: Optional[float],
) -> Optional[Entry]:
    """Pure ACD/ORB detection over a single day's 5-minute frame.

    ``df`` is OHLCV with a DatetimeIndex (any tz; localized to ET here). Kept
    separate from :func:`detect_entry` so the breakout logic is unit-testable
    without a data provider.
    """
    day = cand.day
    df = prepare_detection_frame(df, day, vol_avg_window=cfg.vol_avg_window)
    if df.empty:
        return None

    w0, w1 = cfg.entry_window_et
    win = df.between_time(w0, w1, inclusive="left")
    if win.empty:
        return None

    # Running high seeded from session start so a premarket run is the
    # consolidation reference, not a phantom first-bar breakout.
    pre = df[df.index < win.index[0]]
    running_high = float(pre["high"].max()) if not pre.empty else float(win["high"].iloc[0])
    bars_since_new_high = cfg.consolidation_min_bars  # allow an immediate ORB break

    for row in win.itertuples():
        ts = row.Index
        hi = float(row.high)
        if hi <= running_high:
            bars_since_new_high += 1
            continue

        # new high — does it qualify as a consolidation breakout?
        breakout_level = running_high
        running_high = hi  # update before any continue so state stays correct

        if bars_since_new_high < cfg.consolidation_min_bars:
            bars_since_new_high = 0
            continue
        bars_since_new_high = 0

        close = float(row.close)
        if close <= float(row.open):           # require a green breakout bar
            continue
        vol_avg = row.vol_avg
        has_vol_base = pd.notna(vol_avg) and vol_avg > 0
        vol_mult = float(row.volume / vol_avg) if has_vol_base else None
        # If we have a baseline, enforce expansion; if not (thin/empty premarket),
        # we can't disprove it — let the setup through and flag the gap in the reason.
        if vol_mult is not None and vol_mult < cfg.vol_expansion_mult:
            continue
        vwap = float(row.vwap) if pd.notna(row.vwap) else None
        if cfg.require_above_vwap and (vwap is None or close < vwap):
            continue

        t_et = ts.strftime("%H:%M")
        vol_phrase = (
            f"on {vol_mult:.1f}× bar-volume" if vol_mult is not None
            else "(no premarket volume baseline)"
        )
        reason = (
            f"ACD/ORB breakout: gapped +{cand.gap_pct:.1f}% on {cand.rvol:.1f}× RVOL, "
            f"{_fmt_float(float_shares)}; first 5-min new high at {t_et} ET cleared "
            f"consolidation high ${breakout_level:.2f} {vol_phrase}"
            + (", close above VWAP." if vwap is not None else ".")
        )
        return Entry(
            ticker=cand.ticker,
            day=day,
            time_et=t_et,
            pattern="acd_orb",
            entry_px=round(breakout_level, 4),
            bar_close=round(close, 4),
            gap_pct=round(cand.gap_pct, 2),
            rvol=round(cand.rvol, 2),
            float_shares=float_shares,
            bar_vol_mult=round(vol_mult, 2) if vol_mult is not None else None,
            reason=reason,
            strategy="warrior",
        )

    return None
