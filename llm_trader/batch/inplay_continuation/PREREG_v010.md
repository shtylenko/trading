# Pre-registration — `inplay_continuation` v0.1.0 (Opp C)

**Before code results.** Date: 2026-07-19.  
**Broker economics:** WeBull long equity (`costs/webull.py`).

## Thesis

Liquid take-all micro/VWAP failed under causal screens. Edge, if any for retail
long-only on WeBull, is more likely in **gap / in-play names** with **honest costs**
(high slip), not mega-cap 2 bps fantasy.

## Frozen rules v0.1.0

### Universe / window
- Window: **2025-07-01 → 2026-06-30** (~12m; current-float caveat OK)
- Price open: **$2–$50**
- Gap: **≥ 5%** and ≤ 80%
- ADV (prior 20d): **≥ 500_000** shares
- Float: **&lt; 50M** current snapshot when available; unknown float **allowed** for v0.1
  (documented bias); prefer cached low-float when scanning broad universe
- Symbols: cached float&lt;50M and/or warrior-like list; max universe size logged

### Screen causality
- RVOL = **prior-day volume / prior 20d avg** (same E0 fix) · **rvol_min = 2.0**
- No full-day volume in admission

### Pattern (one only)
Same geometry as liquid micro, re-homed:
1. Impulse: ≥2 up bars, open→high ≥ **0.8%**, close ≥ session VWAP  
2. Pullback: 1–3 bars, no new impulse high, depth ≤ 55% of impulse, lows ≥ VWAP  
3. Signal: green close &gt; pullback high, still ≥ VWAP  
4. Window: **09:45–13:30** ET  
5. Entry: next 5m open; stop under pb low − 0.05%; T1/T2 = 1R/2R half scale; EOD 15:55  

### Costs (WeBull)
- Commission 0; regulatory sell ~0.5 bps proxy  
- **Baseline slip 15 bps one-way** (SMALL tier)  
- Stress: slip 10 / 20 / 30 / 50 one-way (pre-registered grid)

### Portfolio packaging
- Max 3 concurrent, max 5 new/day (same port_v0.1.0)
- NML OFF

## Gates (kill)

| Gate | Criterion |
|---|---|
| 1 | Pooled effR > 0 at **baseline slip 15** |
| 2 | If ≥2 calendar years in window: ≥1 year > 0 **and** pooled > 0; if single year-span, pooled > 0 and win rate not required |
| 3 | At slip **30** one-way: pooled effR must be **> −0.05** (not a catastrophe); if ≤ −0.05 → cost-killed |
| **Hard kill** | Fail gate 1 → park Opp C v0.1.0; no threshold nibble |

**Not success:** pass only at slip≤2 (mega fantasy); pass after changing gap/rvol/pb after seeing results.

## Outputs
- `batch/inplay_continuation/probe_12m/RESULTS.md`
- Construction tag: `v0.1.0_inplay_continuation`
