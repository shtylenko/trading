# Proposed Strategy Releases — 2026-06-18 Audit

These are proposed new numbered releases to fix HIGH/MEDIUM findings in immutable strategy code. Since release files cannot be edited (they become part of the run's code signature), bugs are fixed forward with new releases.

---

## HIGH Priority

### o12 — NaN propagation guards (fixes H1)

**Bug**: Two NaN-related bugs in `build_sip_base` (common.py) and `SipOrbVariant.build_signal` (variants.py):
1. `rv = first_vol / mean_opening_volume` produces NaN when volume is NaN, and `NaN < min_rv` is False → candidate passes gate
2. `risk_per_share = abs(NaN)` passes `<= 0` check → `int(NaN)` crashes

**Fix**:
- Parent: o11 (or whichever is the tip of the chain)
- In `build_sip_base`, after computing `rv`: add `if not math.isfinite(rv): return None`
- In `build_signal`, before `int(qty)`: add `if not math.isfinite(risk_per_share): return None`
- These are implementation details, not knobs — override the full methods.

**Expected impact**: Prevents silent phantom candidates and runtime crashes from NaN data.

---

### o13 — Code signature fix for o10/o11 (fixes H4)

**Bug**: `_gate_year` is set lazily during `build_candidates`, but `signature_inputs()` runs at class construction when it's `None`. ML model hash is always included in signature.

**Fix**:
- Parent: o11
- Set `_gate_year` in `signature_inputs()` itself: read the model artifact's train-end date, determine the gate year, return the appropriate label.
- Or: return an empty list when ML is disabled, and only the model hash when ML is active.

**Expected impact**: Correct code signatures — pre-2024 runs show as "fresh" with fallback, 2024+ runs correctly track model versions.

---

## MEDIUM Priority

### f08 — Remove dead `warm_start_lookback_days` attribute (fixes M10/L7)

**Bug**: `warm_start_lookback_days` is declared but never read. f03 sets it to 2 but it has no effect — the actual warm-start mechanism uses `historical_5m_lookback_days`.

**Fix**:
- Parent: f07
- Simply don't set `warm_start_lookback_days = 2`. Don't declare it at all.
- Or: deprecate the attribute with a comment and keep `historical_5m_lookback_days = 2` as the sole mechanism.

**Expected impact**: No runtime change. Removes confusing dead attribute.

---

### o14 — Stop calling deprecated `first_regular_5m_candle` (fixes L2)

**Bug**: o01 calls the deprecated `first_regular_5m_candle` which delegates to `first_regular_5m_bar`. Once all consumers are migrated, the deprecated function can be removed.

**Fix**:
- Parent: o01 (first in chain)
- Change `first_regular_5m_candle(bars_5m)` → use `first_regular_5m_bar(bars_5m)` directly and extract the Series.
- Since o01 is the root release and immutable, this requires rebasing the entire o-family chain. **Not recommended** — instead, add a new o14 that overrides only the method using the deprecated call with the non-deprecated equivalent.

**Expected impact**: Removes technical debt. Allows eventual removal of `first_regular_5m_candle`.

---

## LOW Priority (Documentation Fixes)

### d-family docstring updates

Several d-family files have stale "Next intended releases" sections:
- d01.py predicts d02–d04 as the next batch (all built + killed)
- d11.py predicts d12 (built)
- d12.py predicts d13 (built)
- d14.py predicts d15 (built)

The drive family is effectively retired (d14 killed on broad eval, d15 killed on OOS). Update docstrings to reflect actual status vs planned.

### Docstring warnings for architecture violations

Add explicit `# WARNING` comments in:
- `dominance_flip_reversal/variants.py:37-53` — `spy_above_200sma()` calls provider directly; use f06+ which reads `context.spy_daily`
- `stocks_in_play_orb/variants.py:179-207` — `spy_atr_regime_hot()` calls provider directly; use o11+ which reads `context.spy_daily`

---

## Verification

After each new release:
```bash
PYTHONPATH=engine python3 -c "from trading.lab.strategies import RELEASES; print(list(RELEASES.keys()))"
PYTHONPATH=engine python3 -m pytest trading/lab/tests/ -x -q --timeout=30 -k "not network"
```
