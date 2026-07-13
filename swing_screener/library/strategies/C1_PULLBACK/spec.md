# C1_PULLBACK — Historical Candidate Screener Spec

**Status:** Implementation spec (v1)  
**Date:** 2026-07-12  
**Strategy ref:** `swing_screener/library/strategies/consolidated.md` § C1  
**Package:** `trading.swing_screener`  
**Bar source:** `trading.marketdata` only  

---

## 1. Goal

Build a **historical candidate screener** for **C1_PULLBACK** that, for every NYSE trading day in:

```text
2022-01-01 → 2026-06-30   (H1 2026)
```

emits names that would have passed the **end-of-day C1 filter set**, using daily OHLCV from `trading.marketdata`.

This is a **screen / research dataset**, not a full trade simulator. Entry fills, stops, and R-multiples are out of scope for v1 (phase 6+).

---

## 2. Locked product decisions (v1)

| Decision | Choice |
|----------|--------|
| Variants | **Both** `C1_MR` and `C1_PB` (separate rows; never pooled as one score) |
| Universe | `lab/universes/liquid_pit.yaml` via `trading.lab.data.universes` |
| Market cap | **Proxy only:** price + avg volume (+ dollar volume); no SEC shares × price |
| Earnings blackout | **Deferred** (`earnings_ok = null`); document as known gap |
| Output | **Candidates only** (no forward returns in v1) |
| Config | YAML under `swing_screener/config/c1_pullback.yaml` |
| Adjustment | Daily bars with `adjustment="split"` for SMA/RSI/perf |

---

## 3. Two variants (do not mix)

C1 is two systems that share trend gates. Codex review: treat as separate journal tags.

### 3.1 Shared gates (both)

| Filter | Default |
|--------|---------|
| In PIT universe for `asof_date` | `liquid_pit` |
| Close | ≥ `$10` |
| Avg volume (20 sessions) | ≥ `500_000` |
| Price above SMA50 | yes |
| Price above SMA200 | yes |

### 3.2 C1_MR — RSI(2) mean reversion (Claude / Connors)

| Filter | Default |
|--------|---------|
| RSI(2) | `< 10` |
| Perf ~21d (month) | `> 0` (optional leadership) |

**Interpretation:** signal-day close candidate. Trade entry mechanics (MOC vs next day) are **not** simulated in v1.

### 3.3 C1_PB — pullback zone (Codex / Grok)

| Filter | Default |
|--------|---------|
| RSI(14) | ∈ `[35, 50]` |
| Perf ~5d (week) | `≤ 0` |
| Close vs SMA20 | ≤ `+3%` above SMA20 (pullback zone) |
| Relative volume | `≤ 1.2` (quiet pullback preference) |

**Interpretation:** EOD pullback-zone candidate. Next-session reclaim (VWAP/OR) is phase 7, not v1.

---

## 4. Data dependencies

| Need | Source | v1 status |
|------|--------|-----------|
| Daily OHLCV | `trading.marketdata.fetch_bars(..., "1day", adjustment="split")` | Required |
| PIT liquid universe | `trading.lab.data.universes.load_universe_tickers("liquid_pit", d)` | Required |
| Price / vol / SMA / RSI / perf / RelVol | Derived from daily bars | Required |
| True market cap | SEC shares × price | Out of v1 |
| Earnings calendar | external | Out of v1 |
| Sector map / news | Finviz | Out of v1 |
| Intraday VWAP / OR | 1m/5m/15m | Out of v1 |

**Warmup:** fetch history from **2021-01-01** so SMA200 exists on 2022-01-03.

**Bias note:** `liquid_pit` is built from Alpaca *current* active assets → residual survivorship bias in early years (same limitation as lab). Document in outputs README.

---

## 5. Package layout

```text
trading/swing_screener/
  README.md
  __init__.py
  config/
    c1_pullback.yaml
  c1_pullback/
    __init__.py
    indicators.py       # SMA, RSI(n), ATR, RelVol, performance
    rules.py            # pure filters → bool + diagnostics
    screen.py           # historical scan orchestration
    universe.py         # liquid_pit wrapper + ticker union
  data/
    __init__.py
    panel.py            # load daily panel via marketdata
    store.py            # write parquet/csv
  scripts/
    __init__.py
    run_c1_screen.py    # CLI
  tests/
    test_indicators.py
    test_c1_rules.py
    test_screen_smoke.py
  library/              # research docs (existing)
  library/strategies/C1_PULLBACK/
    spec.md             # this file
  outputs/              # gitignored artifacts
    .gitignore
```

**Dependency direction:**

```text
swing_screener → marketdata          (required)
swing_screener → lab.data.universes  (PIT universe)
swing_screener ↛ lab.runner / strategies
```

---

## 6. Computation model

1. Resolve **ticker union** across all `liquid_pit` snapshots with `effective_date` in/near the scan window.
2. Prefetch once per ticker: `fetch_bars(t, "1day", start=warmup, end=end, adjustment="split")`.
3. Compute indicators vectorized per ticker.
4. For each asof date in range, apply shared + variant masks using only bars with `date <= asof`.
5. Concatenate hits → parquet.

**Do not** call `fetch_bars` per (ticker, day).

---

## 7. Indicator definitions

| Name | Definition |
|------|------------|
| `sma_n` | Rolling mean of close, window `n`, min_periods=`n` |
| `rsi_n` | Wilder RSI: avg gain/loss EMA with alpha `1/n` (or standard Wilder RMA) on close-to-close changes; period `n` |
| `avg_vol_20` | Rolling mean volume, 20 |
| `relvol` | `volume / avg_vol_20` |
| `perf_5d` | `close / close.shift(5) - 1` |
| `perf_21d` | `close / close.shift(21) - 1` |
| `perf_126d` | `close / close.shift(126) - 1` (optional leadership) |
| `sma20_ext` | `close / sma20 - 1` |

NaN rows never pass filters.

---

## 8. Output schema

One row per `(asof_date, ticker, variant)`:

| Column | Type | Notes |
|--------|------|-------|
| `asof_date` | date | Signal session |
| `ticker` | str | Uppercase |
| `variant` | str | `C1_MR` or `C1_PB` |
| `close` | float | |
| `volume` | float | |
| `avg_vol_20` | float | |
| `relvol` | float | |
| `sma20`, `sma50`, `sma200` | float | |
| `rsi2`, `rsi14` | float | |
| `perf_5d`, `perf_21d`, `perf_126d` | float | |
| `sma20_ext` | float | |
| `universe` | str | e.g. `liquid_pit` |
| `rules_version` | str | config version string |
| `earnings_ok` | null/bool | null in v1 |

Artifacts:

```text
outputs/c1_pullback/candidates_{start}_{end}.parquet
outputs/c1_pullback/summary_by_year.parquet
```

---

## 9. CLI

```bash
# from monorepo root (/Users/shtylenko/Projects)
python3 -m trading.swing_screener.scripts.run_c1_screen \
  --start 2022-01-01 --end 2026-06-30 \
  --variant both \
  --universe liquid_pit \
  --config trading/swing_screener/config/c1_pullback.yaml \
  --out trading/swing_screener/outputs/c1_pullback
```

Options:

| Flag | Default |
|------|---------|
| `--start` / `--end` | required |
| `--variant` | `both` \| `C1_MR` \| `C1_PB` |
| `--universe` | `liquid_pit` |
| `--config` | package default yaml |
| `--out` | `swing_screener/outputs/c1_pullback` |
| `--tickers` | optional comma list (debug) |
| `--max-tickers` | optional cap for smoke runs |
| `--workers` | process pool size (default 1 or CPU-bound) |

---

## 10. Phases

| Phase | Deliverable | v1? |
|------|-------------|-----|
| 1 Indicators + unit tests | `indicators.py` | Yes |
| 2 Panel loader | marketdata prefetch | Yes |
| 3 Rules + historical screen → parquet | core ask | Yes |
| 4 Summary by year / sanity | counts | Yes |
| 5 Earnings blackout | join calendar | Later |
| 6 Forward returns / R-sim | `c1_pullback/backtest.py` + `run_c1_backtest` | **Yes (daily)** |
| 7 C1_PB intraday reclaim | 15m VWAP/OR | Later |

### Phase 6 simulation defaults

| Item | Choice |
|------|--------|
| MR entry | `next_open` (honest); `signal_close` optional in yaml |
| PB entry | Daily buy-stop at signal high × 1.01 next session |
| Costs | 5 bps per side |
| Overlap | One position per ticker |
| Metrics | Win rate, avg/median R, profit factor, exit mix by year |

---

## 11. Tests

- Synthetic OHLCV: known RSI(2) hit / miss; SMA200 gate blocks  
- RSI(14) band for PB  
- No look-ahead: indicators use only past closes  
- Smoke: small ticker set × short window → stable schema  

---

## 12. Explicit non-goals (v1)

- Full backtest / portfolio heat  
- Finviz API scraping  
- Averaging-down add rules  
- News / sector map automation  
- Mixing MR and PB into a single ranked “C1 score”  

---

## 13. Success criteria

1. CLI completes 2022–2026H1 on `liquid_pit` without provider thrash (cache-warm path).  
2. Parquet non-empty for each calendar year with plausible counts (orders of magnitude: dozens–thousands of hits/year depending on thresholds).  
3. Unit tests pass.  
4. Spec + config version recorded in every output row.  

---

*End of C1_PULLBACK historical screener spec.*
