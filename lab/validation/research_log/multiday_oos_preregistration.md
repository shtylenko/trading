# Sealed-OOS Pre-Registration — Multi-Day Momentum (2025)

LOCKED 2026-06-16 BEFORE reading 2025. Per EXPLORATION_PLAYBOOK §6 + the cross-family
OOS spend ledger. 2025 is read EXACTLY ONCE; the result below is binding regardless of
outcome. No parameter is tuned to 2025.

## Why this candidate earned the spend

12-1 long-only cross-sectional momentum is confirmed real in-sample over 2017–2024:
DSR 0.997, pooled non-overlapping t = +2.61, ann Sharpe ≈ 1.0, 6/8 LOO years positive,
positive in the survivorship-clean 2022–2024 PIT window. The edge is the BASE rule
(conditioning grid is dead, PBO 0.92), so the confirmatory candidate carries ~no
selection bias. 2025 is a survivorship-honest PIT year → a clean out-of-sample test.

## The EXACT rule (no free parameters; nothing tuned to 2025)

- Universe: `liquid_pit` point-in-time, as of each rebalance date in 2025.
- Eligibility: close ≥ $5 AND 20-day dollar-volume ≥ $10M (rule, from bars).
- Signal: `mom_12_1` = close(d−21)/close(d−252) − 1 (12-month return, skip last month).
- Selection: each rebalance, go long the **top 50** eligible names by mom_12_1, equal
  weight. UNCONDITIONED (no grid filter — the conditioning was shown to be noise).
- Rebalance: **monthly, H = 20 trading days, NON-OVERLAPPING** (the confirmed horizon).
- Hold: 20 trading days; outcome per name = close(d+20)/close(d) − 1.
- Cost: 10 bps round-trip per held name per rebalance (conservative ≈ full turnover).
- Metric series: per-rebalance net portfolio return = mean over the 50 held names,
  minus cost. 2025 yields ~12 non-overlapping periods.

## Pre-committed binary criteria (decided before the read)

Primary (tradeability of the long book, net of cost):
- **PASS**  if 2025 net sum return > 0 AND annualized Sharpe ≥ 0.5.
- **REVIEW** if net sum return > 0 but annualized Sharpe in [0, 0.5).
- **FAIL**  if 2025 net sum return ≤ 0.

Secondary (ALPHA confirmation — momentum, not just 2025 beta), reported alongside:
- top-50 momentum mean return − eligible-universe mean return (the cross-sectional
  premium). Positive = genuine momentum tilt; ~zero = the long book was just market
  beta. This does NOT override the primary verdict but qualifies it (a PASS that is
  pure beta is a weaker result than a PASS with a positive cross-sectional premium).
- Decile monotonicity in 2025 (Spearman of decile vs forward return), for color.
- HAC (Newey-West) t-stat on the daily-formation overlapping 2025 cohorts, for a
  more stable single-year significance read (one year ≈ 12 independent periods is a
  small sample — the t-stat is expected to be weak; it is color, not a gate).

## Caveats recorded up front

- One year ≈ 12 independent monthly periods → low power; a single year cannot by
  itself promote a factor, only confirm/deny direction. A PASS here + the 8-year
  in-sample is the body of evidence; it is NOT a standalone proof.
- The simulation is optimistic (independent equal-weight, fixed cost, no portfolio
  correlation/capacity). A PASS still owes a real swing-engine cross-check + a
  portfolio/capacity/borrow review before capital.
- Long-only momentum has intrinsic crash risk (2021–22 in-sample); 2025 is one draw.

## Disposition

After the read, record the outcome here + in `oos_spend_ledger.md` (2025 spent on the
`momentum` family, win or lose). PASS → build the multi-day-hold engine path for the
cross-check, then the normal funnel + the next sealed year (2026-H1) for the second
confirmation. FAIL/REVIEW → record the clean result; momentum is then "real but
modest / did not confirm OOS" and the long/short version is the next lever.

---

## DISPOSITION (read 2026-06-16, ONE SHOT, binding)

**VERDICT: PASS.**
- per-period net mean = **+3.98%**, annualized **Sharpe +1.08** (≥ 0.5) → PASS on the
  pre-registered primary criteria.
- Cross-sectional premium (top-50 net − eligible-universe gross) = **+2.78%** →
  POSITIVE = genuine momentum tilt, NOT just 2025 market beta (the key alpha qualifier).
- Decile monotonicity in 2025 = +0.56 (holds OOS). HAC t = +1.31 (weak, as
  pre-registered — one year ≈ 12 independent periods; color, not a gate).

**Reading:** 12-1 long-only momentum CONFIRMS out-of-sample on the survivorship-honest
2025 PIT year, with a positive cross-sectional premium — the project's first sealed-OOS
PASS. It is a real, MODEST edge (Sharpe ~1.0). This + the 8-year in-sample is the body
of evidence; one year is not standalone proof. Per disposition: next = build the
multi-day-hold engine path for the cross-check, then the normal funnel, then the
**2026-H1** sealed year for the second (independent) confirmation. The simulation is
optimistic → a portfolio/capacity/borrow review is owed before any capital. 2025 is now
2/3 spent (oos_spend_ledger.md).
