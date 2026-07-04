"""capture_d_features — feature-capture variant for the gap-and-go feature search.

NOT a numbered/shippable release. This is the max-recall capture run of
validation/feature_search_spec.md: it uses d01's MINIMUM admission (gap > 1%
above prior high, green first 5m candle, breakout-of-first-high entry) and
annotates every admitted candidate with the full leak-free feature vector from
``research.features`` (so the offline subset search has everything it needs).

It admits exactly what d01 admits — it adds NO filter — so realized R per
candidate is identical to d01's, and any admission-filter combination is a pure
subset of this one run's ledger. MUST be run uncapped (``candidate_limit=None``):
the broad eval deploys with a top-10-by-gap cap, so the search re-applies that
top-N AFTER filtering using the stored ``score`` (gap %); capturing capped would
break the subset invariant.

Data hydrated (declared so the runner loads it; strategy code never fetches):
    - d01's 5m RTH + per-ticker daily, but with ``daily_lookback_days=420`` so
      the stock's own 50/200-day SMA and 60-day beta are computable.
    - SPY daily + the 11 SPDR sector ETFs (``spy_daily_lookback_days=420``) for
      market/sector regime + relative strength; SPY 5m is always hydrated.
    - 30 days of historical 5m for opening relative-volume.
"""

from __future__ import annotations

from trading.lab.core.models import Candidate, StrategyContext
from trading.lab.research.features import features_from_context
from trading.lab.research.filters import has_split_like_jump
from trading.lab.strategies.post_gap_opening_drive.d01 import Release as D01Release
from trading.lab.strategies.post_gap_opening_drive.d12 import (
    Release as D12Release,
    _SPDR_ETFS,
)


class Release(D01Release):
    release_id = "capture_d_features"
    strategy_name = "Gap-and-go feature capture (research, not shippable)"
    description = (
        "d01 minimum admission with the full research.features vector attached "
        "to every candidate; max-recall capture for the offline feature search."
    )

    requires_spy_daily = True
    spy_daily_lookback_days = 420   # SPY + sector ETF window: 60d beta, 50d SMA
    daily_lookback_days = 420       # per-ticker: own 200d SMA needs ~200 sessions
    historical_5m_lookback_days = 30  # opening relative-volume baseline
    extra_daily_symbols = _SPDR_ETFS

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        cands = super().build_candidates(context)
        if not cands:
            return []
        sector_map = D12Release._load_sector_map()
        kept: list[Candidate] = []
        for c in cands:
            # Data-integrity gate: a split / reverse-split / glitch on the trade
            # date makes today's raw open a different price scale than the prior
            # bars, manufacturing a giant phantom gap that d01 would admit with a
            # meaningless realized R. Exclude such rows from the capture ledger
            # (passing today's open catches the overnight reverse split). This
            # deviates from raw d01 admission ONLY on data-integrity events.
            daily = context.daily.get(c.ticker)
            first_open = float(c.features.get("first_open", 0.0)) or None
            if has_split_like_jump(daily, context.trade_date, lookback=252,
                                   open_price=first_open):
                continue
            etf = sector_map.get(c.ticker)
            feats = features_from_context(context, c.ticker, sector_symbol=etf)
            # d01 already set the gap features; the library recomputes them
            # identically and adds the rest. Keep sector_etf for traceability.
            c.features = {**c.features, **feats, "sector_etf": etf}
            kept.append(c)
        for idx, c in enumerate(kept, start=1):  # re-rank after the integrity drop
            c.rank = idx
        return kept
