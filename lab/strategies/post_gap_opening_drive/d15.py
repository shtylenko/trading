"""d15 — Post-Gap Opening Drive, gap≥3% + opening-RV≥1.5 (feature-search winner).

This release exists to BACKTEST, through the real engine, the combo that the
2022–2024 feature search nominated as gap-and-go's strongest, most stable signal:
admit only when the gap is ≥ 3% above the prior day's high AND opening 5-minute
relative volume is ≥ 1.5×. Two one-lever knobs over d01, both pre-existing:
``min_gap_pct = 3.0`` (a meaningful, not marginal, gap) and ``min_rv = 1.5``
(the gap is confirmed by real opening participation; volume-less gaps fade).

Provenance / status (2026-06-15):
    - In the offline search over the 2022–2025 capture ledger this combo was
      positive every search year (2022 +3.5R, 2023 +5.6R, 2024 +31.8R), selected
      by leave-one-year-out in 3/3 folds, and substitution-robust.
    - The PRE-REGISTERED confirmatory test on the sealed 2025 year KILLED it:
      −34.1R, only 1 of 4 quarters positive (validation/phase_b_oos_preregistration.md).
    - d15 therefore is a KILLED release. Its purpose now is twofold: (a) a permanent,
      honest record of the tested combo, and (b) a CROSS-CHECK that a real engine
      backtest on eval_2025_broad reproduces the ledger-derived −34R — i.e. that the
      offline subset-ledger methodology is faithful to the engine. It is NOT a
      promotion candidate.

Data requirements:
    - d01's (5m RTH + raw daily) PLUS 30 prior sessions of 5m history for the
      opening relative-volume baseline (``historical_5m_lookback_days = 30``, matching
      the capture run so the RV gate reproduces the ledger).

Entry rules:
    - All of d01's gap-and-go rules, with the gap floor raised 1% → 3%, AND the
      opening relative-volume gate ≥ 1.5 (d02's RV definition).

Exit / risk rules:
    - Unchanged from d01: stop at first-candle low (=1R), 1R target, 11:30 flatten.

Known limitations:
    - KILLED on 2025 OOS (above). The filters halve the unfiltered 2025 bleed
      (−34R vs −67R) by removing some bad trades, but "loses less" is not an edge.
    - RV history window (30d) is set to match the capture, not d02's 14d.
"""

from __future__ import annotations

from trading.lab.strategies.post_gap_opening_drive.variants import DriveVariant


class Release(DriveVariant):
    release_id = "d15"
    strategy_name = "Post-Gap Opening Drive — gap≥3% + opening-RV≥1.5"
    description = (
        "d01 gap-and-go with the gap floor raised to 3% and an opening "
        "relative-volume ≥ 1.5 gate — the 2022–2024 feature-search winner, "
        "killed on the 2025 OOS. Kept as record + engine cross-check."
    )

    min_gap_pct = 3.0                  # gap floor raised from d01's 1%
    min_rv = 1.5                       # opening relative-volume gate (d02 lever)
    historical_5m_lookback_days = 30   # RV baseline window — matches the capture run
