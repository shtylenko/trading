# x05 — Residual-Purification of x03 (Sprint 1) — PRE-REGISTERED spec (LOCKED)

Locked 2026-06-24 **before running either arm.** Source: the 4-AI idea sweep
(`strategies/xsec_momentum/idea-solicitation/responses-2026-06-23/SYNTHESIS.md`) — the two
**4/4-convergent** directions, distilled in `backlog.md` → "external AI idea sweep" section.
Companion: `multiday_x03_residmom_preregistration.md` (the ranking these inherit unchanged).
**Narrow, pre-committed forms — no grids, no post-hoc re-tune. This is a 40-idea forking-paths
minefield; the whole point of locking is to pick ≤1 survivor on a rule fixed in advance.**

> x05-number lineage: follows the x04 convention — the id is *claimed* by the first candidate
> that survives to a shipped release and *freed* on every rejection. Both arms below compete
> for x05; a killed arm releases the number (as the six dead x04 candidates did).

## Thesis (ex-ante) — the exact weakness being attacked

x03 (CAPM-residual momentum, top-50 EW, monthly H=20) is the validated edge but still carries
**book β ≈ 1.08** and ~0.95 correlation to plain momentum — its market-orthogonal alpha on
clean 2022–24 is ≈ 0 (the win is risk engineering, not new alpha). Every *new factor* tried
collapsed to a high-β tilt (the META-FINDING). The sweep's convergent insight: don't add a
factor — **purify the residual we already compute** so the β leak shrinks. Two arms:

- **Arm A — β-estimate cleaning (zero new data; runs first).** The single CAPM β is estimated
  by OLS over one 252-day window; when it is **stale or unstable**, the residual ε is polluted
  with un-stripped market exposure → that name's "idiosyncratic momentum" is partly leveraged
  beta. Excluding names whose β estimate is untrustworthy should shrink the book's realized β
  and shallow the momentum-crash drawdown **without** adding a new factor.
- **Arm B — secondary fundamental veto on already-selected winners (DATA-GATED; see §Data).**
  Among residual winners, exclude those whose price strength rests on **net-share issuance** or
  **high accruals** (Sloan) — distinct corporate-action / earnings-quality anomalies, applied
  as a *post-selection exclusion*, NOT a primary ranking sleeve (which is what killed
  value/quality/earnings-momentum). Targets the left-tail "junk rally" reversal names.

**Settles:** does purifying the residual (A) and/or vetoing low-quality winners (B), holding
the x03 ranking + book width fixed, **lower realized β and max-drawdown at ~flat gross return
on BOTH in-sample windows** (→ a real risk improvement, candidate x05), or does it merely give
back return for lower vol / fail to move β (→ kill, keep x03)?

## Baseline (frozen)

x03 exactly: CAPM-residual score `mean(ε)/std(ε)`, ε = r_i − β·r_SPY over formation
`[d−252, d−21]`; eligible = close ≥ $5 AND 20d $-vol ≥ $10M AND ≥ 273 aligned returns; rank
desc, **top-50 EW**, monthly non-overlapping H=20, pure time exit, 10 bps, SPLIT-adjusted daily
bars, SPY market leg. **Book width stays 50 in every arm** (this is not the concentration lever
— that is x04). Ledgers: `_capture_multiday_2017_2025_split.parquet` (clean 2022–24) +
`_capture_multiday_2009_2016_yf.parquet` (2009–16, survivorship-lifted — relative comparison
only). Scripts to extend: `experiments/multiday/multiday_residmom.py` (the baseline book).

## Arm A — locked construction (ONE primary form + ONE pre-declared robustness check)

**Primary (LOCKED): β-stability pre-filter, then rank.**
For each eligible name at rebalance d, over the formation window `[d−252, d−21]`:
- `β_h1` = OLS beta on the **first half** (`[d−252, d−137]`), `β_h2` = on the **second half**
  (`[d−137, d−21]`); `instability = |β_h1 − β_h2|`.
- **Exclude the worst 20%** by `instability` (highest) from the eligible set — single
  pre-committed quantile, no sweep.
- Rank survivors by the **unchanged** x03 IR score; take **top-50 EW**. Everything else identical.

**Robustness check (pre-declared, SINGLE — not a grid):** replace the split-half instability
proxy with the OLS **standard error of β** (`se(β)` over the full 252-day window), same 20%
worst-excluded. Purpose: confirm a positive result is not an artifact of the specific proxy.
Reported alongside primary; does NOT change the verdict rule (primary decides).

## Arm B — locked construction (DATA-GATED, runs after Arm A)

Within the **top-90 by x03 IR** (a wider candidate pool so the veto still fills 50), exclude:
- **Issuance:** names with trailing-12m % change in split-adjusted shares outstanding in the
  **top quintile** (most dilutive), AND
- **Accruals:** names with Sloan accrual ratio `(ΔCA − ΔCash − ΔCL + ΔSTD − Dep) / avg Assets`
  in the **top quintile** (most accrual-heavy),

then take the **top-50 EW** of survivors. Two pre-committed quintile gates, no sweep. If the
veto leaves < 50, fill back up the IR ranking (documented, not re-tuned).

## Decision rule (LOCKED — judged on BETA-ADJUSTED alpha, both windows)

For each arm vs the frozen baseline, on **clean 2022–24** AND **2009–16**, compute the book's
per-period returns and regress them on SPY per-period returns (PIT trailing β) → read **α and
its t-stat** (Bar A), plus realized β, Sharpe, max-DD, gross CAGR, and corr to the baseline.

**PASS (→ claim x05, advance to a future sealed-2027 confirmation):** on BOTH windows —
1. realized **β strictly lower** than baseline (the stated goal), AND
2. **max-DD shallower** (≥ ~2pp) OR Sharpe higher, AND
3. **α not worse** than baseline (t-stat no more negative), AND
4. **gross CAGR within ~1pp of baseline** — the anti-trap guardrail.

**KILL** if on either window: β does not fall, OR the DD/Sharpe gain comes only with gross
CAGR collapsing (the disguised low-vol-tilt that killed ATR-exit / leverage / vol-target), OR
α goes more negative, OR corr to baseline > 0.99 with no β/DD movement (no-op).

**REVIEW** (one window passes, one is flat): report, do NOT promote, do NOT spend a sealed year.

## Hard constraints honored

No sealed year spent — **in-sample triage only** (2022–24 + 2009–16). 2025 and 2026-H1 stay
spent/sealed; a PASS earns a single pre-registered ~2027 sealed read later, not now. Long-only,
1.0×, top-50 width fixed. No look-ahead: β-halves, issuance, and accruals all use only data
through d (issuance/accruals are PIT via the EDGAR adapter's `filed ≤ d` rule).

## Data readiness (gates Arm B, NOT Arm A)

- **Arm A: READY.** Price + SPY only; recompute β-halves from the existing split ledger. No
  new capture.
- **Arm B: NOT READY — data lift required.** The current fundamentals capture
  (`_capture_fundamentals_2017_2024.parquet`) holds only `gp_assets`, `ni_yoy`.
  - *Issuance* (small lift): the SEC adapter already exposes `CommonStockSharesOutstanding` /
    `EntityCommonStockSharesOutstanding` — re-capture adding the shares series.
  - *Accruals* (larger lift): `data/sec_fundamentals.py` must be extended with working-capital +
    cash-flow tags (current assets/liabilities, cash, short-term debt, D&A, operating cash
    flow) before the Sloan ratio is computable, then re-capture.
  Arm B is locked in design now (so it cannot be re-tuned after the data arrives) but executes
  only after the capture exists. **Sequence: run Arm A first.**

## Sequence

1. Arm A primary + se(β) robustness → verdict (no new data). 2. If Arm A informative, do the
issuance re-capture → Arm B issuance-only veto. 3. If warranted, extend the adapter for accruals
→ full Arm B. Each step's result logged to `backlog.md`; the x05 id resolves on the first PASS
or is freed on KILL.

---

## ADDENDUM (2026-06-24, after Arm A) — Arm B narrowed to ISSUANCE-ONLY, locked

**Arm A KILLED** (split-half primary failed both windows; se(β)'s β↓/Sharpe↑ was the low-vol
confound the CAGR guardrail caught — see `backlog.md` kill-table). The β≈1.08 is structural, so
the "purify the residual" half is closed. Per operator decision, Arm B proceeds **issuance-only**
(the cheap, distinct mechanism); the **accruals** leg is NOT built unless issuance shows signal.

**Locked issuance definition (no re-tune):**
- **NSI (split-adjusted, PIT):** `adj_shares(d)/adj_shares(d−365cal) − 1`, where
  `adj_shares = raw_cover-page_shares × f`, `f = raw_close / split_adjusted_close` at that date.
  Raw shares = SEC DEI `EntityCommonStockSharesOutstanding` ∪ us-gaap `CommonStockSharesOutstanding`,
  latest **filed ≤ d** (`sec_fundamentals.shares_union` + `asof_instant`). **The split adjustment
  is mandatory** — momentum winners are exactly the names that split; raw deltas would book a
  split as huge issuance.
- **Veto rule:** within the **top-90 by IR**, exclude the **top quintile** (≥80th pct) by NSI
  among the pool, take **top-50 EW**. Missing-NSI names are KEPT (documented fallback); if the
  veto leaves < 50, backfill down the IR ranking. Single pre-committed pool (90) + quintile (80%).
- **Decision rule + windows: unchanged** (β-adjusted alpha, both windows, CAGR guardrail).
- Scripts: `experiments/capture/capture_issuance.py` (ledger) +
  `experiments/multiday/multiday_residpurify_veto.py` (test). No sealed year touched.

**Prior (stated ex-ante):** LOW. Arm A's failure is mild evidence the β leak is intrinsic;
issuance attacks a *different* failure (left-tail dilution/junk-rally reversal), so it's a fair
final cheap shot — but a KILL here means the sweep is honestly exhausted → bank x03.
