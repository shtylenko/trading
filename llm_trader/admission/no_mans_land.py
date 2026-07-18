"""No Man's Land admission — long-only edge filter (Lance).

Thesis: after a leg, the mid-range of a consolidation is negative EV ("paper cuts").
Only admit longs at the **upper edge** of the recent range or on a clean **breakout**
of that range. Support-bounce longs and mid-range VWAP chops are rejected.

This is a *structural* gate, not a family-parameter retune. Parameters below are
**pre-registered** for the short-hold A/B (see batch/admission/PREREG.md).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class NmlConfig:
    """Frozen structural defaults — change only with a new pre-reg version."""

    lookback_bars: int = 24          # ~2h of 5m; uses session-so-far if shorter
    min_bars: int = 12
    # Mid-range = (mid_lo, mid_hi); longs inside without breakout → reject
    mid_lo: float = 0.30
    mid_hi: float = 0.70
    # Upper-edge long: position in range ≥ this
    upper_edge_frac: float = 0.70
    # Breakout long: high > prior lookback high AND close position ≥ this
    breakout_close_frac: float = 0.60
    # Lance exception: exceptionally tight box (width/price) may trade either edge
    tight_width_pct: float = 0.35    # 0.35% of mid price
    version: str = "nml_v0.1.0"


@dataclass
class NmlDecision:
    admit: bool
    reason: str
    position: float                  # 0 = at range low, 1 = at range high
    range_high: float
    range_low: float
    range_width_pct: float
    is_breakout: bool
    is_upper_edge: bool
    is_tight: bool
    config_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_long_edge(
    df: pd.DataFrame,
    signal_i: int,
    entry_px: float,
    cfg: Optional[NmlConfig] = None,
) -> NmlDecision:
    """Decide whether a long at ``entry_px`` on bar ``signal_i`` is at a range edge.

    ``df`` must be RTH bars for the session, indexed chronologically, with high/low/close.
    Only bars ``[:signal_i+1]`` are used (causal).
    """
    cfg = cfg or NmlConfig()
    ver = cfg.version

    if df is None or len(df) == 0 or signal_i < 0 or signal_i >= len(df):
        return NmlDecision(
            admit=False,
            reason="invalid_frame",
            position=float("nan"),
            range_high=0.0,
            range_low=0.0,
            range_width_pct=0.0,
            is_breakout=False,
            is_upper_edge=False,
            is_tight=False,
            config_version=ver,
        )

    # Lookback window ending at signal (inclusive)
    j0 = max(0, signal_i + 1 - cfg.lookback_bars)
    win = df.iloc[j0 : signal_i + 1]
    if len(win) < cfg.min_bars:
        return NmlDecision(
            admit=False,
            reason="insufficient_bars",
            position=float("nan"),
            range_high=0.0,
            range_low=0.0,
            range_width_pct=0.0,
            is_breakout=False,
            is_upper_edge=False,
            is_tight=False,
            config_version=ver,
        )

    r_high = float(win["high"].max())
    r_low = float(win["low"].min())
    width = r_high - r_low
    mid = 0.5 * (r_high + r_low)
    width_pct = (width / mid * 100.0) if mid > 0 else 0.0
    is_tight = width_pct > 0 and width_pct <= cfg.tight_width_pct

    if width <= 0 or not np.isfinite(entry_px):
        return NmlDecision(
            admit=False,
            reason="degenerate_range",
            position=float("nan"),
            range_high=r_high,
            range_low=r_low,
            range_width_pct=width_pct,
            is_breakout=False,
            is_upper_edge=False,
            is_tight=is_tight,
            config_version=ver,
        )

    pos = float((entry_px - r_low) / width)
    pos = max(0.0, min(1.0, pos))

    # Breakout: signal high clears prior window high (exclude signal bar)
    prior = df.iloc[j0:signal_i]
    is_breakout = False
    if len(prior) >= max(4, cfg.min_bars // 2):
        prior_high = float(prior["high"].max())
        sig_high = float(df.iloc[signal_i]["high"])
        sig_close = float(df.iloc[signal_i]["close"])
        close_pos = (sig_close - r_low) / width
        is_breakout = sig_high > prior_high + 1e-9 and close_pos >= cfg.breakout_close_frac

    is_upper_edge = pos >= cfg.upper_edge_frac
    in_mid = cfg.mid_lo < pos < cfg.mid_hi

    # Tight-box exception (Lance): allow either edge of an exceptionally tight coil
    if is_tight:
        if pos >= cfg.upper_edge_frac or pos <= (1.0 - cfg.upper_edge_frac) or is_breakout:
            # Long-only: still require upper edge or breakout (not lower-edge long)
            if is_upper_edge or is_breakout:
                return NmlDecision(
                    True,
                    "tight_upper_or_breakout",
                    pos,
                    r_high,
                    r_low,
                    width_pct,
                    is_breakout,
                    is_upper_edge,
                    True,
                    ver,
                )
            return NmlDecision(
                False,
                "tight_but_not_long_edge",
                pos,
                r_high,
                r_low,
                width_pct,
                is_breakout,
                is_upper_edge,
                True,
                ver,
            )

    if is_breakout:
        return NmlDecision(
            True, "breakout", pos, r_high, r_low, width_pct, True, is_upper_edge, False, ver
        )
    if is_upper_edge:
        return NmlDecision(
            True, "upper_edge", pos, r_high, r_low, width_pct, False, True, False, ver
        )
    if in_mid:
        return NmlDecision(
            False, "mid_range_nml", pos, r_high, r_low, width_pct, False, False, False, ver
        )
    # Lower third without breakout — not a long edge setup under this gate
    return NmlDecision(
        False, "lower_range_not_long_edge", pos, r_high, r_low, width_pct, False, False, False, ver
    )


def find_signal_index(df: pd.DataFrame, time_et: str) -> int:
    """Return bar index for ``HH:MM`` time_et, or -1."""
    times = [ts.strftime("%H:%M") for ts in df.index]
    try:
        return times.index(time_et)
    except ValueError:
        return -1
