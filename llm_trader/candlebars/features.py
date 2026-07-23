"""Causal, scale-independent features of individual OHLCV candle bars."""

from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED_OHLC = ("open", "high", "low", "close")


def candle_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Return a copy enriched with reusable ``cb_*`` candle features.

    A zero-range bar has zero body/wicks and a neutral close location of 0.5.
    That conservative convention prevents it from qualifying as a momentum or
    rejection candle merely because of a divide-by-zero artifact.
    """
    missing = [column for column in REQUIRED_OHLC if column not in bars.columns]
    if missing:
        raise ValueError(f"bars missing required OHLC column(s): {missing}")

    out = bars.copy()
    open_ = pd.to_numeric(out["open"], errors="coerce")
    high = pd.to_numeric(out["high"], errors="coerce")
    low = pd.to_numeric(out["low"], errors="coerce")
    close = pd.to_numeric(out["close"], errors="coerce")

    if (high < low).any():
        raise ValueError("bars contain high < low")

    bar_range = high - low
    body = (close - open_).abs()
    upper_wick = high - np.maximum(open_, close)
    lower_wick = np.minimum(open_, close) - low
    valid_range = bar_range.where(bar_range > 0)

    out["cb_range"] = bar_range
    out["cb_body"] = body
    out["cb_upper_wick"] = upper_wick.clip(lower=0)
    out["cb_lower_wick"] = lower_wick.clip(lower=0)
    out["cb_body_ratio"] = (body / valid_range).fillna(0.0)
    out["cb_upper_wick_ratio"] = (out["cb_upper_wick"] / valid_range).fillna(0.0)
    out["cb_lower_wick_ratio"] = (out["cb_lower_wick"] / valid_range).fillna(0.0)
    out["cb_close_location"] = ((close - low) / valid_range).fillna(0.5)
    out["cb_green"] = close > open_
    out["cb_red"] = close < open_
    return out

