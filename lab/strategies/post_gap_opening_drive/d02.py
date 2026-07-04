"""d02 — Post-gap opening drive + relative-volume "in play" filter.

One-lever change from d01: keep only gaps whose opening 5m bar trades at
>= 2x the stock's historical mean opening volume. d01 fires on every 1%
gap-up regardless of participation; this adds the core stocks-in-play
quality gate — a gap-and-go without climactic volume is just a quiet gap.
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d02"
    strategy_name = "Post-Gap Opening Drive — relative-volume filter"
    description = (
        "d01 gap-and-go gated to climactic opening volume (RV >= 2x the "
        "14-day mean opening-bar volume): only trade gaps that are 'in play'."
    )

    min_rv = 2.0
    historical_5m_lookback_days = 14  # tells the pipeline to load RV history
