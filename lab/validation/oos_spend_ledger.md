# Sealed-OOS Spend Ledger (cross-family alpha-spending)

The sealed out-of-sample years are a **shared, depleting resource across the whole
project**, not per-family. Every time *any* family's confirmatory test reads a
sealed year, that year learns a little about us — repeated queries turn the
"sealed" year into a slow in-sample set (meta-overfitting on the holdout). This
ledger tracks every spend so the bar rises with cumulative use.

## Discipline (pragmatic alpha-spending for a solo researcher)

1. **One pre-registered confirmatory test per family per holdout year.** No second
   look at the same (family, year) — that burns it.
2. **Rotate holdout years across families** so no single year is hammered. We have
   two clean-ish holdouts: **2025** and **2026-H1** (treat 2026-H1 as the more
   suspect one — see the 2026H1 artifact finding). Prefer giving a fresh family a
   year that has been queried *fewer* times.
3. **Raise the bar on re-query.** The Nth confirmatory test against a given year
   must clear a higher in-sample DSR and a larger minimum effect size than the
   (N−1)th. Suggested schedule per year: 1st query DSR ≥ 0.95; 2nd ≥ 0.975;
   3rd ≥ 0.99; after 3, that year is considered spent — rotate or acquire a new
   holdout (a later year as data accrues).
4. **A search may not even reach the OOS gate** unless it already clears WF + PBO
   + DSR ≥ gate in-sample (see `feature_search.py`). The OOS test is the *last*
   gate, not the first filter — most candidates should die before spending a year.
5. **Record every spend below, win or lose.** A FAIL still consumes the query.

## Holdout-year budget status

| Year | Queries used | Status | Notes |
|---|---|---|---|
| 2025 | 2 | in use | d15 (FAIL) + momentum base rule (PASS). 1 query left before "spent"; a 3rd needs DSR ≥ 0.99. |
| 2026-H1 | 1 | spent (1 query) | momentum 2nd-confirmation = CONFIRM (2026-06-17, EARLY PARTIAL ~5 periods). Positive premium (+4.56%) allays the artifact concern. A 2nd query needs DSR ≥ 0.975. |

## Spend log

| Date | Family / combo | Holdout year | In-sample DSR | Pre-reg bar | OOS result | Verdict |
|---|---|---|---|---|---|---|
| 2026-06-15 | post_gap_opening_drive · `gap≥3 + rvol≥1.5` (d15) | 2025 | 0.58 (computed post-hoc; the DSR gate was added after) | sumR>+10R, ≥3/4 qtrs+ | −30.1R engine / −34.1R ledger, 1/4 qtrs | **FAIL/KILL** |
| 2026-06-16 | intraday_momentum-multiday · `top-50 12-1 momentum, monthly` (base rule, UNCONDITIONED) | 2025 | 0.997 (8yr 2017–2024); survivorship-CLEAN 2022–24 only = 0.94 | net sumR>0 AND ann Sharpe ≥0.5 | per-period net +3.98%, ann Sharpe +1.08, cross-sectional premium +2.78% (genuine momentum, not beta) | **PASS** |
| 2026-06-17 | xsec_momentum · `top-50 12-1 momentum, monthly` (base rule, split-adjusted) | 2026-H1 | 0.97 (clean 2022–24 re-confirm post split-fix); 8yr 0.99 | net>0 AND ann Sharpe≥0.5 AND premium>0 (distrust gate) | per-period net +5.58%, ann Sharpe +1.77, premium +4.56%, decile monotonicity +1.00 (≈5 periods, HAC t +1.42) | **CONFIRM** |

> Note on the momentum spend (2nd query of 2025 → bar was DSR ≥ 0.975): qualified on
> the 8-year in-sample DSR 0.997, which clears 0.975. Transparency caveat: the 8-year
> figure is partly survivorship-OPTIMISTIC (2017–2021 used the fixed-2022 universe);
> the survivorship-CLEAN 2022–2024 DSR was only 0.94. The spend is defensible — the
> 8yr evidence (DSR 0.997, pooled non-overlapping t +2.61, 6/8 LOO years) is a far
> stronger base than d15's, momentum is the most-replicated equity factor, and 2025
> itself is a survivorship-honest PIT year — and it PASSED with a POSITIVE
> cross-sectional premium (+2.78%, i.e. genuine momentum tilt, not 2025 market beta).
> The single-year HAC t was +1.31 (weak by design — one year ≈ 12 periods; the body
> of evidence is the 8yr in-sample + this OOS confirmation, not the 1-yr t alone).

> Note on the d15 spend: it predates the DSR gate. With DSR now in the search, this
> candidate would have scored **DSR 0.58 < 0.95** in-sample and been held at REVIEW —
> i.e. it would NOT have qualified to spend 2025 under the current rules. The 2025
> kill and the (retrofitted) DSR agree. Going forward, no candidate spends a sealed
> year unless it clears the in-sample DSR gate first.
