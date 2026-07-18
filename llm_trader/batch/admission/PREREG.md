# Pre-registration — structural short-hold gates (2026-07-18)

**Purpose:** Test Lance *No Man's Land* + desk portfolio concurrency as **structural**
overlays on sealed `micro_pullback` and `vwap_pullback` multi-year entries.
**Not** a detector retune.

## Universe / baseline

- Same sealed entry DBs from multi-year runs (59 liquid names, 2022–2025).
- Same path sim (1 bps fee + 2 bps slip each way).
- Gates: pooled effR > 0 and ≥2 of 4 years > 0.

## NML v0.1.0 (frozen)

| Param | Value | Rationale |
|---|---|---|
| lookback_bars | 24 | ~2h of 5m context |
| min_bars | 12 | need a real range |
| mid_lo / mid_hi | 0.30 / 0.70 | mid-range = NML |
| upper_edge_frac | 0.70 | long only at high edge |
| breakout_close_frac | 0.60 | breakout must hold upper half |
| tight_width_pct | 0.35 | Lance tight-coil exception (still long-edge only) |

**Long admit iff** upper edge **or** breakout of prior lookback high (with close strength).
**Reject** mid-range and lower-range longs.

## Portfolio v0.1.0 (frozen)

| Param | Value |
|---|---|
| max_concurrent | 3 |
| max_per_day | 5 |
| selection | chronological; tie-break higher RVOL then gap |

## Variants

1. `baseline` — sealed trades as-is  
2. `nml_only` — drop NML rejects  
3. `portfolio_only` — concurrency/day caps only  
4. `nml_plus_portfolio` — both  

## Success criteria (pre-registered)

- NML is a **keep** if `nml_only` still passes gates and effR ≥ baseline − 0.005
  (does not destroy the edge) **or** clearly improves effR/years+.
- Portfolio is packaging: pass-with-lower-n is acceptable; do not optimize for max n.
- **No post-hoc mid_lo/mid_hi search** on this result set.
