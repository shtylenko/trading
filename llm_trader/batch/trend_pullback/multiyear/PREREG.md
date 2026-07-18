# Multi-year validation — trend_pullback 0.4.0 (frozen)

**Rules:** SMA50 pullback, tight admission, setup_high, prior-high targets, SPY>SMA50.
**Universe:** 60 liquid large-cap names (same list as prior n30 work).
**Window:** 2022-01-01 → 2025-12-31.

## Pre-registered gates (before reading results)

1. **Pooled** (2022–2025 all setups): effective R > 0.
2. **By year:** effective R > 0 in **≥ 2 of 4** calendar years (2022, 2023, 2024, 2025).
3. **Fail if** a single year accounts for > 2/3 of pooled ΣR (tail dominance) — flag only, not hard kill.

PASS requires (1) and (2). Otherwise FAIL / park family.
