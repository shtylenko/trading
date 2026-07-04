"""d12 — Post-Gap Opening Drive, SECTOR-trend regime gate.

One-lever change from d11. d11 gates the gap-and-go on the BROAD market's trend
(SPY < 50d SMA): a gap above the prior high is relative strength, which pays when
the tape is weak. d12 sharpens "weak relative to what" from the whole market to
the stock's OWN SECTOR: a stock gapping up while its sector is below its 50d
trend is a genuine standout on idiosyncratic demand; a gap-up inside a hot sector
is just sector beta and tends to be sold intraday.

Motivation: the d05/d11 2026H1 diagnostic showed the top contributors clustered
in semiconductors (SNDK, MU, MCHP, COHR) — a hint that sector trend, not just
market trend, conditions follow-through. d12 tests whether the per-sector gate
beats the market-wide one.

How the gate works:
    - Each candidate's ticker is mapped to a SPDR sector ETF via
      universes/sector_map.yaml (built by scripts.build_sector_map from yfinance
      sector classification). The 11 sector ETFs are hydrated as extra daily
      series (context.extra_daily) the same way SPY daily is.
    - Keep the candidate only if its sector ETF's prior-day close is BELOW that
      ETF's trailing 50-day SMA (sector in a downtrend / relative-strength
      regime), exactly mirroring d11's SPY math but per-sector.
    - FALLBACK: a ticker with no sector mapping (or whose ETF history is too
      short) is gated on the SPY market trend instead — so d12 degrades to d11's
      behaviour for unmapped names rather than silently dropping them.

Data requirements:
    - Everything d01 needs, PLUS the 11 SPDR sector ETFs' daily history and SPY
      daily (for the fallback). spy_daily_lookback_days = 90 (~62 trading days)
      covers the 50-day SMA for every series.

Entry / exit rules:
    - Entry: all of d01's gap-and-go rules, plus the per-sector (or fallback
      market) downtrend gate above.
    - Exit/risk: unchanged from d01 (stop at first-candle low = 1R, 1R target,
      flatten 11:30 NY).

Known limitations:
    - sector_map.yaml is built from yfinance's CURRENT sector classification —
      not strictly point-in-time. Sectors are stable so look-ahead risk is low,
      but it is a current-snapshot dependency (documented in the map header).
    - Like d11, a downtrend gate trades sparsely when most sectors are above
      their 50d trend (broad bull). Per-sector gating can ALSO thin counts
      further when only a few sectors are weak — watch the >20/quarter floor.
    - Single fixed threshold (50d). No breadth, no intraday sector confirmation.

Next intended releases:
    - d13: per-ticker relative-strength gate (stock vs its OWN 50d trend, and/or
      stock's gap vs its sector ETF's gap) — the finest-grained version.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from trading.lab.core.models import Candidate, StrategyContext
from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant

_SECTOR_MAP_PATH = (
    Path(__file__).resolve().parent.parent.parent / "universes" / "sector_map.yaml"
)
_SPDR_ETFS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLB", "XLRE", "XLU", "XLC"]


def _below_50d_sma(daily: pd.DataFrame | None, period: int = 50) -> bool | None:
    """True when *daily*'s last close is below its trailing N-day SMA.

    Returns None when the frame is missing or too short for the SMA, so the
    caller can fall back. Mirrors d11's SPY trend math.
    """
    if daily is None or daily.empty or "close" not in daily:
        return None
    closes = daily["close"].astype(float)
    if len(closes) < period:
        return None
    sma = float(closes.tail(period).mean())
    if sma <= 0:
        return None
    return float(closes.iloc[-1]) < sma


class Release(DriveVariant):
    release_id = "d12"
    strategy_name = "Post-Gap Opening Drive — sector-trend regime gate"
    description = (
        "d01 gap-and-go armed per-candidate only when the stock's SECTOR ETF "
        "closed below its 50-day SMA (relative strength vs a weak sector); "
        "unmapped tickers fall back to the SPY market gate."
    )

    requires_spy_daily = True
    spy_daily_lookback_days = 90
    extra_daily_symbols = _SPDR_ETFS

    sma_period = 50

    _sector_map: dict[str, str] | None = None

    @classmethod
    def _load_sector_map(cls) -> dict[str, str]:
        """Lazy-load ticker -> sector-ETF map; cache on the class.

        Missing file -> empty map -> every ticker uses the SPY fallback gate
        (i.e. d12 degrades to d11). Tolerant by design so a partial/in-progress
        map never crashes a run.
        """
        if cls._sector_map is None:
            try:
                data = yaml.safe_load(_SECTOR_MAP_PATH.read_text()) or {}
                raw = data.get("map", {}) or {}
                cls._sector_map = {t: e for t, e in raw.items() if e}
            except FileNotFoundError:
                cls._sector_map = {}
        return cls._sector_map

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        cands = super().build_candidates(context)
        if not cands:
            return []
        sector_map = self._load_sector_map()
        # Market fallback, computed once per day.
        spy_below = _below_50d_sma(context.spy_daily, self.sma_period)
        kept: list[Candidate] = []
        for c in cands:
            etf = sector_map.get(c.ticker)
            gate = None
            if etf is not None:
                gate = _below_50d_sma(context.extra_daily.get(etf), self.sma_period)
            used = "sector"
            if gate is None:  # unmapped ticker or missing/short ETF history
                gate, used = spy_below, "spy_fallback"
            if not gate:
                continue
            c.features = {
                **c.features,
                "sector_etf": etf,
                "regime_gate": used,
                "sector_below_50d_sma": True,
            }
            kept.append(c)
        for idx, c in enumerate(kept, start=1):
            c.rank = idx
        return kept
