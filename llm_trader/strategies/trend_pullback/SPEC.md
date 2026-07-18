# Trend pullback — SPEC (v0)

**Goal:** Scan for Lance-style **trending pullback to the 20 EMA** (long only) and
paper-trade them with a deterministic auto-arm policy under sealed multi-day daily
replay — same platform path as `cup_handle`.

**Status:** Fourth / last iteration (0.4.0). SMA50 pullback + 0.2 construction; no profitability claim.

## Thesis

In a daily uptrend, pullbacks to the rising 20 EMA often resume. Wait for the
pullback to **tag** the EMA and **reclaim** it (close back above). Arm a buy-stop
above the reclaim-day high; stop under the pullback low; targets at prior swing
high and measured move.

## Mechanical checklist

| # | Question | Gate |
|---|---|---|
| 1 | Strong uptrend? | Close > SMA50 and SMA200; SMA50 rising vs 20 bars ago |
| 2 | Pullback to MA? | Within last 3–15 bars, **low ≤ pullback MA** (default **SMA50** in 0.4.0; EMA20 in 0.2.0) and ≥1 **close ≤ MA** |
| 3 | Reclaim confirmed? | Setup close ≥ MA and not extended > **4%** above MA |
| 4 | Meaningful depth? | Pullback depth vs prior swing high in **[4%, 18%]** |
| 5 | Liquidity? | Price ≥ $10, 20d avg volume ≥ 1M |
| 6 | Market regime? | **SPY close > SMA50** (0.2.0 default on) |

**Signal:** `prebreak_arm` at 16:00 on the reclaim day — plan only, no same-bar fill.

| Level | Rule (0.3.0) |
|---|---|
| Trigger | **Close** of reclaim day (`entry_trigger_mode=reclaim_close`) |
| Stop | Pullback low − `stop_buffer_atr` × ATR(14) |
| T1 | Trigger + **1R** (R = trigger − stop) |
| T2 | Trigger + **2R** |
| Expiry | `arm_expiry_bars` (default 5) |
| Gap guard | Cancel if open gaps beyond `max_entry_gap_atr` × ATR |

Legacy (0.1–0.2): trigger = setup high; T1/T2 = prior high / measured move — still
selectable via config for ablations.

## Pipeline

```
universe (or --symbols)
  → daily OHLCV + SMA/EMA/ATR
  → causal reclaim plan → EntryStore (strategy=trend_pullback)
  → batchsim / sealed daily replay + deterministic auto-arm policy
```

## Out of scope (v0)

- 50 SMA as alternate pullback line (config stub only)
- Intraday timing on the entry day
- News / catalyst filter
- SPY regime gate (optional config; off by default)

## Research validity

- Same causal contract as cup_handle: no `ENTER_CLOSE` on the plan bar.
- Deterministic skill `0.1.0` + policy `trend_pullback_auto_arm_v1`.
- Fail closed on incomplete SMA200 warm-up in the visible replay window.
