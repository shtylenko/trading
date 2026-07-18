# Multi-year validation — breakout_first_pullback 0.1.0

**Rules:** frozen v0.1.0 (base → breakout → first pullback hold).
**Universe:** 60 liquid large-caps.
**Window:** 2022-01-01 → 2025-12-31.

## Pre-registered gates (before reading results)

1. Pooled (2022–2025) effective R > 0.
2. Effective R > 0 in ≥ 2 of 4 calendar years.
3. Flag if one year > 2/3 of pooled ΣR (tail dominance).

PASS requires (1) and (2). Else FAIL / park or iterate.
