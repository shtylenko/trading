# C2_BREAKOUT — 52-Week High Base Breakout Spec

**Status:** Implementation v1 (Finviz-free)  
**Date:** 2026-07-12  
**Package:** `trading.swing_screener.c2_breakout`  
**Bar source:** `trading.marketdata` only  

---

## Goal

Historical candidate screen + trade sim + capacity portfolio for **quality 52-week-high base breakouts**, long-only, hold ≤ 8–10 trading days. No Finviz dependency.

## Locked decisions (v1)

| Item | Choice |
|------|--------|
| Universe | `liquid_pit` |
| Adjustment | `split` daily bars |
| Base discovery vs trigger | **Single-pass trigger day**: base quality *and* breakout confirmation on signal day (prior bars define base/pivot) |
| Entry | **Next open** after signal close above pivot (no same-close look-ahead) |
| RelVol | ≥ 1.5 on **signal (breakout) day only**; base window prefers dry-up |
| Quality fundamentals | Deferred (no EDGAR join in v1) |
| Earnings blackout | Deferred |
| Costs | 5 bps/side |
| Portfolio | max 4 positions, max 2/sector (reuse C1 portfolio helper pattern) |

## Signal rules (daily)

Shared liquidity / trend:

- price ≥ $10  
- avg vol 20 ≥ 500k  
- close > SMA20, SMA50, SMA200  
- RSI(14) ∈ [50, 75]  
- perf 63d (quarter) ≥ +10%  
- perf 21d (month) ≥ 0  
- close within `near_52w_pct` of 252d high (default 10%)  
- not extended: close ≤ SMA20 × 1.10  

Base (lookback `base_lookback`, default 15 sessions ending *yesterday*):

- pivot = max(high) over base window (prior bars only)  
- base depth (pivot − min low in window) / ATR14 ≤ 2.5  
- base range % (pivot − min low) / pivot ≤ 12%  
- mean volume in right half of base ≤ mean volume in left half (dry-up preference)  

Breakout (today = signal day):

- close > pivot  
- high ≥ pivot  
- RelVol ≥ 1.5  
- optional: close − pivot ≤ 0.75 × ATR (reject vertical chase bars)  
- RS vs SPY over 21d ≥ 0 (stock perf − SPY perf)  

## Trade sim

| Param | Default |
|-------|---------|
| Entry | next session open; skip if open > pivot + 0.75 ATR |
| Stop | base_low − 0.10×ATR; skip if risk > 1.25 ATR or > 8% of entry |
| Target | +2.5R |
| Failed breakout | daily close < pivot → exit at close |
| No progress | after 3 sessions, unrealized R < 0.5 → exit close |
| Time stop | day 8 close |
| Same-bar | stop before target (conservative) |
| Overlap | one position per ticker |

## Portfolio

Same as C1: max 4 concurrent, max 2/sector, rank by proximity to 52w high then RelVol.

## Explicit non-goals (v1)

- Finviz patterns / Maps  
- 15m VWAP reclaim entry  
- EDGAR quality filters  
- Earnings calendar blackout  
