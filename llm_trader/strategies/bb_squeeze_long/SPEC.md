# BB squeeze long — short-hold SPEC (v0.1.1)

**Thesis (Lance):** Band squeeze (low vol) often precedes expansion; long only on
expansion with green close above mid-band (never short upper-band stretch).

**Horizon:** same-day 5m RTH; flat EOD.

## Rules

1. Daily: liquid + RVOL ≥ 1.15  
2. 5m BB(20,2): prior bar bandwidth in bottom 25% of trailing ≤36 bars  
   (causal past-only percentile; min ~half lookback finite widths)  
3. Signal bar: width expands, green, close > mid, close > prior high  
4. Entry: next bar open; stop under 6-bar low; 1R/2R; EOD 15:55  

## Fix log

- **v0.1.0 → v0.1.1:** detection loop no longer waits for `bb_period + lookback`
  bars before scanning (that started at ~15:10, after `entry_window_end` 14:30 →
  systematic multi-year n=0). Lookback 48→36; pctile max 0.20→0.25.
