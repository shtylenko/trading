# Strategy Lab Code Audit
**Date:** 2026-06-18  
**Scope:** whole-tree correctness audit of `trading/lab/`

## Executive Summary
The shared intraday execution path is generally careful about same-bar look-ahead, shifted VWAP admission, duplicate candidates, and R-based metrics. The highest shared-code issue was in funnel evaluation: the OOS artifact check existed in `gate_oos()` but never received the in-sample sum-R it needs, so suspiciously strong holdout results could auto-promote. I fixed that, registered `x03`, hydrated swing `spy_daily` for swing releases, logged swing daily fetch failures, and replaced a naive UTC lifecycle timestamp. The remaining high-risk items are in shipped release modules or release-family semantics and are report-only under the immutability rule.

## HIGH Severity

### 1. Fixed: OOS artifact gate was dead in lifecycle evaluation
- **File:** `trading/lab/validation/funnel_eval.py:158`
- **Evidence:** `GateInput.is_sum_r` is defined and `gate_oos()` checks it, but `evaluate_release()` built OOS gate inputs without setting it. OOS results more than 3x in-sample sum-R could pass instead of stopping for review.
- **Fix applied:** Carry broad in-sample `sum_r` forward and inject it into the OOS `GateInput`; added `test_evaluate_oos_artifact_check_uses_broad_is_sum_r`.
- **Anti-goal:** overfitting / universe-selection artifacts.

### 2. Fixed: `x03` release existed but was not registered
- **File:** `trading/lab/strategies/__init__.py:43`
- **Evidence:** `x03.py` was present but absent from `RELEASES`, so `get_release_class("x03")` failed and the engine could not run the release.
- **Fix applied:** Registered `x03` and extended the registry test.
- **Anti-goal:** silent bugs / reproducibility.

### 3. Fixed: swing runner did not hydrate SPY daily context
- **File:** `trading/lab/runner/swing_pipeline.py:98`
- **Evidence:** Swing releases receive only `context.daily`; `x03` declares `requires_spy_daily=True` and fails closed when `context.spy_daily` is missing, yielding zero candidates.
- **Fix applied:** Fetch split-adjusted SPY daily once per swing date range when required and pass a rebalance-date-sliced frame into `StrategyContext`.
- **Anti-goal:** filter-until-zero / silent bugs.

### 4. Report-only: `x03` residual-momentum window does not match its pre-registered offline definition
- **File:** `trading/lab/strategies/xsec_momentum/x03.py:77`
- **Evidence:** `_resid_mom()` uses `ri[-MIN_RET:-SKIP]` with `MIN_RET=273`, producing 252 formation returns. The release docstring says it matches the offline script, but the referenced offline script uses `rets.iloc[di-252:di-21]`, a different 231-return window.
- **Fix:** Do not edit `x03.py` in place. Create `x04` that mirrors the offline window exactly, or explicitly re-register validation for the changed formation definition.
- **Anti-goal:** reproducibility / overfitting.

### 5. Report-only: old dominance-flip variant fetches SPY inside strategy code
- **File:** `trading/lab/strategies/dominance_flip_reversal/variants.py:45`
- **Evidence:** `spy_above_200sma()` imports `fetch_daily_context()` inside strategy code. `f02` reaches this path, bypassing runner hydration, `--force-data`, and run data lineage.
- **Fix:** Use/keep successor `f06` behavior that declares `requires_spy_daily` and reads `context.spy_daily`; do not mutate shipped `f02` semantics.
- **Anti-goal:** data contamination / reproducibility.

### 6. Report-only: `d12` silently degrades sector gating to SPY fallback
- **File:** `trading/lab/strategies/post_gap_opening_drive/d12.py:115`, `trading/lab/strategies/post_gap_opening_drive/d12.py:133`
- **Evidence:** A missing `sector_map.yaml` becomes `{}`, making every ticker use SPY fallback. Mapped tickers with missing/short ETF history also fall back to SPY, silently changing d12 into d11-like behavior.
- **Fix:** New release should fail fast on missing map and skip/log mapped tickers with missing ETF history; fallback should only apply to explicitly unmapped tickers.
- **Anti-goal:** silent bugs / universe-selection artifacts.

### 7. Report-only: ORB ML releases can use in-sample model artifacts
- **File:** `trading/lab/strategies/stocks_in_play_orb/o03.py:92`, `trading/lab/strategies/stocks_in_play_orb/o10.py:65`
- **Evidence:** `o03` can load an artifact trained on full 2024 for any backtest date. `o10` disables ML only before 2024, so 2024 dates still use an in-sample model despite the exclusion policy.
- **Fix:** New releases must read artifact train-start/train-end metadata and disable ML for dates inside or before the training window.
- **Anti-goal:** look-ahead / overfitting.

## MEDIUM Severity

- **Fixed:** `trading/lab/runner/swing_pipeline.py:52` swallowed per-ticker daily fetch exceptions, silently shrinking swing universes. It now logs ticker/date/adjustment failures.
- **Fixed:** `trading/lab/storage/lifecycle.py:77` used `datetime.utcnow()`; it now uses `datetime.now(timezone.utc)`.
- **Report-only:** `trading/lab/strategies/xsec_momentum/x03.py:105` lacks a long `spy_daily_lookback_days`; the swing runner now compensates by using the larger of SPY and per-ticker daily lookbacks, but a successor release should declare it explicitly.
- **Report-only:** `trading/lab/strategies/dominance_flip_reversal/variants.py:76` warm-start variants silently fall back to non-warm detection when `historical_5m` is missing.
- **Report-only:** `trading/lab/strategies/dominance_flip_reversal/variants.py:78` prepends raw historical 5m bars to current raw bars without a split-scale guard.
- **Report-only:** `trading/lab/strategies/post_gap_opening_drive/d12.py:112` reads `sector_map.yaml` at runtime without including it in `signature_inputs()`.
- **Report-only:** `trading/lab/strategies/stocks_in_play_orb/common.py:55` defaults historical RV to 10 bars even for releases documenting 14-day RV windows.
- **Report-only:** `trading/lab/strategies/smma_atr_breakout/s01.py:148` uses raw historical 5m plus raw daily ATR without a split/glitch guard.

## LOW Severity

- `trading/lab/scripts/dashboard.py:2102` kills any process on the requested port before binding. Operationally convenient, but risky for a dashboard command.
- `trading/lab/scripts/dashboard.py` remains a very large mixed HTML/API/data-access file, making review and targeted tests harder.
- `trading/lab/scripts/report.py:102` swallows malformed metrics JSON; low impact because it only affects display.
- `trading/lab/core/execution.py` has long simulator functions with several exit modes inline; behavior is tested, but future edits are harder to audit.

## Unresolved From Prior Reviews

- **Still present from 2026-06-10 review:** ORB research/production drift around `o03` ML policy remains; this audit found the more severe training-window look-ahead version.
- **Still present from 2026-06-14 feature-implementation review:** `d12`/capture sector mapping remains a current-snapshot runtime artifact rather than a frozen PIT signed input.
- **Still present from 2026-06-18 review already in this directory:** dashboard broad exception handling remains low-severity. The earlier report's `requires_spy_5m` high findings were not re-reported as high here because the current runner hydrates SPY 5m unconditionally; the remaining problem is an explicit-contract gap, not current filter-until-zero behavior.

## Agent-Friendliness Scorecard

| File | Dimension | Score | Note |
|---|---:|---:|---|
| `core/execution.py` | fail-loud / tests | HIGH | Conservative alignment and gap-through handling are explicit and covered. |
| `runner/pipeline.py` | reproducibility | HIGH | Code signatures include engine and family helper modules. |
| `runner/swing_pipeline.py` | fail-loud | MEDIUM | Improved fetch logging; still has implicit row-count constants. |
| `validation/funnel_eval.py` | testability | MEDIUM | Gate input construction now covered for OOS artifact checks. |
| `scripts/dashboard.py` | single responsibility | LOW | Large mixed server, SQL, data hydration, HTML, JS surface. |

## Recommended Fix Order

1. Ship successor releases for ORB ML (`o12+`) that enforce artifact train-window metadata.
2. Ship a `d16` sector-gate release with frozen signed sector map behavior and no silent SPY fallback for mapped tickers.
3. Ship `x04` resolving the residual-momentum formation-window mismatch.
4. Retire or supersede `f02`/warm-start variants that bypass context or degrade when historical data is missing.
5. Add explicit SPY 5m requirement semantics to the strategy contract instead of relying on unconditional hydration.

## Verification

- Inventory: 185 Python files under `trading/lab`.
- Required baseline command: `python3 -m pytest trading/lab/tests/ -q --timeout=30 -k "not network"` failed before collection because `--timeout=30` is unsupported in this environment.
- Baseline fallback: `python3 -m pytest trading/lab/tests/ -q -k "not network"` -> 306 passed, 31 deselected, 7 warnings.
- Post-fix required command: same `--timeout=30` command failed for the same missing plugin reason.
- Post-fix fallback: `python3 -m pytest trading/lab/tests/ -q -k "not network"` -> 307 passed, 31 deselected, 7 warnings.
