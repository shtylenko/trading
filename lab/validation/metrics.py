"""Bar-granularity strategy returns and objective functions.

Per Masters ("Testing and Tuning Market Trading Systems"): computing
objectives from a return per *bar* instead of per *trade* feeds them far
more data, making profit factor / Sharpe estimates much more stable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def position_returns(close: pd.Series, signal: pd.Series) -> pd.Series:
    """Per-bar log returns attributable to a position signal.

    ``signal`` is the position held *after* each bar (1 long, -1 short,
    0 flat — fractional sizes are fine). It earns the close-to-close log
    return of the following bar; the final bar earns nothing.
    """
    log_ret = np.log(close).diff().shift(-1)
    return (signal * log_ret).fillna(0.0)


def profit_factor(returns: pd.Series) -> float:
    """Gross positive returns / gross negative returns (0 if no losses... inf-safe)."""
    r = np.asarray(returns, dtype=float)
    gains = r[r > 0].sum()
    losses = -r[r < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)


def sharpe_ratio(returns: pd.Series, bars_per_year: float = 252.0) -> float:
    r = np.asarray(returns, dtype=float)
    sd = r.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(r.mean() / sd * np.sqrt(bars_per_year))


def signal_profit_factor(ohlc: pd.DataFrame, signal: pd.Series) -> float:
    """Convenience objective: profit factor of a position signal on bars."""
    return profit_factor(position_returns(ohlc["close"], signal))
