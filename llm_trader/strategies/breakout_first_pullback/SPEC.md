# Breakout first pullback — SPEC (v0.1.0)

**Goal:** Lance swing #2 — after a multi-week base breaks out, buy the **first
pullback** that holds the breakout level as support.

**Status:** First iteration. Mechanical subset; no profitability claim.

## Thesis

Chasing the initial breakout is lower EV. Waiting for the first retest of the
breakout level (prior resistance → support) gives a tighter stop and cleaner
invalidation.

## Mechanical checklist

| # | Gate |
|---|---|
| 1 | Base 15–60 bars, range 4–18% of base high |
| 2 | Breakout: green close clears base high by ≥0.15%, volume ≥1.3× 20d avg |
| 3 | Within 1–12 bars after breakout: first tag of base high (low within 1.5%) |
| 4 | Setup close holds above base high; extension ≤6% above base high |
| 5 | Pullback depth 2–15% from post-break swing high |
| 6 | Trend: close > SMA50, SMA50 rising; SPY > SMA50 (default on) |

**Signal:** `prebreak_arm` at 16:00 on reclaim/hold day.

| Level | Rule |
|---|---|
| Trigger | Setup day high |
| Stop | Pullback low − 0.15×ATR |
| T1 | Post-breakout swing high |
| T2 | T1 + 1.0 × base height |
| Expiry | 5 bars |
| Max hold | 25 trading days |

## Pipeline

```
universe → daily OHLCV → base/breakout/first-pullback geometry
  → EntryStore (strategy=breakout_first_pullback)
  → sealed daily replay + deterministic auto-arm
```

## Out of scope (v0)

- Intraday entry timing
- Second/third pullbacks
- Short side
- Cup-handle geometry (separate family)
