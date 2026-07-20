# Opp E — boring baseline scoreboard v0.1.0

**Pre-reg:** `batch/boring_baseline/PREREG_v010.md`
**Window:** 2025-07-01 → 2026-06-30
**Sizing:** $5000 notional / trade (WeBull: mega 2 bps slip for beta; select_A 15 bps small-tier)

## Gates

| Gate | Result |
|---|---|
| Best boring baseline | `spy_green_open` mean **+8.15 bps** / pnl **$+488** |
| select_A mean bps | **+230.02** |
| select_A total pnl @$5k | **$+1,725** |
| **Clever wins scoreboard** | **YES** |

## Boring baselines (WeBull mega)

| Variant | n | win% | mean bps | total pnl |
|---|---:|---:|---:|---:|
| `spy_oc` | 251 | 48.6 | -3.36 | $-397 |
| `qqq_oc` | 251 | 52.2 | -2.79 | $-294 |
| `spy_green_open` | 131 | 60.3 | +8.15 | $+488 |
| `spy_gap_nonneg` | 152 | 45.4 | -8.21 | $-599 |

### Baseline by year (best + SPY OC)

**`spy_green_open`**

| Year | n | mean bps | pnl |
|---|---:|---:|---:|
| 2025 | 67 | +3.36 | $+97 |
| 2026 | 64 | +13.17 | $+391 |

**`spy_oc`**

| Year | n | mean bps | pnl |
|---|---:|---:|---:|
| 2025 | 128 | -5.70 | $-343 |
| 2026 | 123 | -0.93 | $-54 |

## select_A (Opp B) on same window

n=15 win%=46.7 mean_bps=+230.02 total_pnl=$+1,725 mean_effR=+0.2707

| Year | n | mean bps | pnl | effR |
|---|---:|---:|---:|---:|
| 2025 | 5 | +51.50 | $+129 | +0.0140 |
| 2026 | 10 | +319.28 | $+1,596 | +0.3991 |

## Verdict

**select_A beats** best boring (`spy_green_open`) on mean bps and total PnL under stated costs. Still **no live capital** — n is tiny; use as license for **forward zero-capital shadow** only, not size.

