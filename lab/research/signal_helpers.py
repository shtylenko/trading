#!/usr/bin/env python3
"""Shared signal-construction helpers for intraday breakout strategies.

Extracts the copy-pasted pattern from o01, o02, and d01: get the first
regular 5-minute bar, extract high/low, validate risk > 0, return the
raw components. Each release then constructs its own Signal with its
specific sizing, exit, and metadata rules.
"""

from __future__ import annotations

import pandas as pd

from trading.lab.research.filters import first_regular_5m_bar


def breakout_signal_params(
    bars_5m: pd.DataFrame | None,
) -> dict | None:
    """Extract breakout signal parameters from the first 5-minute bar.

    Returns a dict with keys ``first_ts``, ``high``, ``low``, ``risk``
    or None if the opening bar is missing or risk ≤ 0.

    Usage::

        p = breakout_signal_params(context.bars_5m.get(ticker))
        if p is None:
            return None
        return Signal(
            ticker=ticker,
            entry_trigger=p["high"],
            stop_price=p["low"],
            target_price=p["high"] + p["risk"],  # or ATR-based
            ...
        )
    """
    first_bar = first_regular_5m_bar(bars_5m)
    if first_bar is None:
        return None
    first_ts, first = first_bar
    high = float(first["high"])
    low = float(first["low"])
    risk = high - low
    if risk <= 0:
        return None
    return {
        "first_ts": first_ts,
        "high": high,
        "low": low,
        "risk": risk,
        "open": float(first["open"]),
        "close": float(first["close"]),
        "volume": float(first.get("volume", 0.0)),
    }
