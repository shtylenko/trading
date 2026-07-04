# Peer review — additive multi-day SWING engine path (strategy_lab)

You are reviewing a code change to a long-only US-equity backtesting harness before we
run a **sealed out-of-sample (2025) engine cross-check** on a validated cross-sectional
momentum strategy. We want bugs — especially **look-ahead/leakage**, simulation
correctness, and anything that would make the engine result spuriously match (or
diverge from) the offline result. Be adversarial and specific.

## Context

The existing engine is **intraday / same-day only**: a runner loops over trade-dates,
and for each date simulates a trade entirely within that session's 5-minute bars,
exiting at an intraday cutoff. Positions cannot span days.

We have an offline-validated edge: **12-1 cross-sectional momentum** (rank liquid names
by `close[d-21]/close[d-252] − 1`, hold top-50 equal-weight 20 trading days, monthly
rebalance). It passed our offline pipeline (8-yr in-sample DSR 0.997, pooled
non-overlapping t +2.61) AND a sealed-OOS 2025 test (per-period net **+3.98%**,
annualized Sharpe **+1.08**, cross-sectional premium **+2.78%** = top-50 net minus
eligible-universe gross). An independent re-implementation reproduced it (+3.46% /
Sharpe 0.92 / premium +2.12% — differences are sampling, not bugs).

Now we built an **additive "swing" engine path** to run this through the REAL engine
(DuckDB ledger / funnel), without touching the intraday engine. We want to confirm the
engine reproduces the offline numbers (direction + magnitude; not bit-identity).

## The offline rule the engine must faithfully reproduce

- Per rebalance date `d` (every 20 trading days, non-overlapping):
  - eligible = in the point-in-time universe as of `d` AND `close(d) ≥ $5` AND
    `mean(close·volume, 20d through d) ≥ $10M`.
  - rank eligible by `mom_12_1 = close(d−21)/close(d−252) − 1`; take **top 50**.
  - per name, outcome = `close(d+20)/close(d) − 1`; portfolio return = equal-weight mean.
  - offline charged a flat **10 bps round-trip** per held name.
- All FEATURES use data through `d`'s close; the only future quantity is the forward
  return. 2025 is the survivorship-honest sealed year.

## The change under review (key code inlined)

### 1. `core/execution.py` — `simulate_daily_hold` (new; intraday sims untouched)

```python
def simulate_daily_hold(daily_bars, signal, entry_date, hold_days, config,
                        use_close_stop=False, direction="long"):
    # date-index, normalize; require entry_date present and >= hold_days forward bars
    idx = pd.DatetimeIndex(daily_bars.index).normalize()
    bars = daily_bars.copy(); bars.index = idx
    ed = pd.Timestamp(entry_date).normalize()
    if ed not in idx: return None
    i = idx.get_loc(ed)
    if i + hold_days >= len(bars): return None
    closes = bars["close"].astype(float).values
    highs  = bars["high"].astype(float).values if "high" in bars else closes
    lows   = bars["low"].astype(float).values  if "low"  in bars else closes
    entry_raw = closes[i]
    sign = -1.0 if direction=="short" else 1.0
    entry_price = entry_raw * (1.0 + sign*config.entry_slippage_bps/1e4)   # long pays up
    exit_j, reason = i + hold_days, "TIME_EXIT"
    if use_close_stop and signal.stop_price:
        for j in range(i+1, i+hold_days+1):
            if (closes[j] <= signal.stop_price) if direction=="long" else (closes[j] >= signal.stop_price):
                exit_j, reason = j, "STOP_CLOSE"; break
    exit_price = closes[exit_j] * (1.0 - sign*config.exit_slippage_bps/1e4) # long receives less
    # mfe/mae over (i, exit_j]; then _trade() computes gross/pnl/realized_r, slippage baked in
    return _trade(signal, idx[i], entry_price, idx[exit_j], exit_price, reason, mfe, mae, config, direction)
```

(`_trade`: `gross = sign*(exit-entry)/entry*100`; `pnl = gross − fees`; `fees =
fees_bps_per_side*2/100`; slippage is informational only, already baked into fills.)

### 2. `strategies/base.py` — `SwingStrategyRelease(StrategyRelease)`

Adds class attrs `is_swing=True, hold_days, rebalance_cadence_days, top_n,
use_close_stop`; provides a concrete `exit_cutoff` returning `None` (unused for swing)
so subclasses implement only `build_candidates` + `build_signal`.

### 3. `strategies/xsec_momentum/x01.py` — the momentum release

```python
def build_candidates(self, context):
    rows = []
    for ticker, daily in context.daily.items():          # context.daily sliced to <= rebalance close
        if daily is None or len(daily) < 253: continue
        c = daily["close"].astype(float); v = daily["volume"].astype(float)
        close_d = c.iloc[-1]
        if close_d < 5.0: continue
        if (c*v).iloc[-20:].mean() < 10_000_000.0: continue
        mom = c.iloc[-22] / c.iloc[-253] - 1.0           # close[d-21]/close[d-252]-1
        rows.append(Candidate(ticker, score=mom, ...))
    rows.sort(key=lambda c: c.score, reverse=True)         # rank desc; runner takes top_n
    return rows

def build_signal(self, context, candidate):
    close_d = context.daily[candidate.ticker]["close"].iloc[-1]
    return Signal(entry_trigger=close_d, stop_price=close_d*(1-0.10),  # nominal stop (R-scaling only)
                  target_price=None, signal_time=<rebalance date>, ...)
```

### 4. `runner/swing_pipeline.py` — the swing runner (per-rebalance session)

```python
# per range: rebal_days = trading_days[::cadence]; union of PIT members; fetch each
# ticker's daily bars ONCE over [range_start-600d, range_end + ~1.6*H]
def _run_swing_session(run_id, ..., rebal_ts, H, top_n, pit_members, bars, exec_cfg):
    ctx_daily = {}
    for t in pit_members:
        b = bars.get(t)
        if b is None or rebal_ts not in b.index: continue
        upto = b[b.index <= rebal_ts]                    # <-- THROUGH rebalance close, inclusive
        if len(upto) >= 253: ctx_daily[t] = upto.tail(300)
    context = StrategyContext(trade_date=rebal_ts.date(), daily=ctx_daily, bars_5m={}, ...)
    candidates = release.build_candidates(context)[:top_n]
    for cand in candidates:
        signal = release.build_signal(context, cand)
        trade  = simulate_daily_hold(bars.get(cand.ticker), signal, rebal_ts, H, exec_cfg, ...)
        # persist candidate/signal/order/trade/fills to the SAME tables as the intraday engine
```

`scripts/backtest.py` dispatches to the swing runner when the release `is_swing`.

## What to scrutinize (be specific; cite the snippet)

1. **Look-ahead / leakage.** Is the ranking/eligibility strictly ≤ rebalance close?
   `ctx_daily` slices `b[b.index <= rebal_ts]`; `build_candidates` reads only that;
   `simulate_daily_hold` gets the FULL `bars` (incl. forward) but only to realize the
   hold. Any path where future data influences selection or entry? Any off-by-one in
   `c.iloc[-22]/c.iloc[-253]` vs `close[d-21]/close[d-252]`?
2. **Entry/exit realism.** Entry at the same close used to *decide* (a MOC assumption).
   Acceptable? Exit at `close[i+H]`. Indexing of `exit_j`, the stop loop range
   `(i+1 .. i+H)`, and the mfe/mae slice `[i+1:exit_j+1]` — correct and consistent?
3. **Cost model mismatch (expected divergence).** Offline used a flat 10 bps round-trip;
   the engine uses `ExecutionConfig` default 2+2 bps slippage + 0.5 bps/side fees
   (≈5 bps round-trip) baked into fills. So the engine should print HIGHER net returns
   than the offline +3.98%. Is that the right read? What engine cost config makes the
   comparison apples-to-apples?
4. **Rebalance-phase / universe alignment.** Offline `all_days[::20]` over the eligible
   grid vs engine `trading_days[::cadence]` per range, PIT membership per date. Could
   phase or universe differences alone explain a sizable gap? How big could that be?
5. **End-of-range truncation.** Late-2025 rebalances lack a full 20-day forward window
   → `simulate_daily_hold` returns `None` (dropped). Does silently dropping them bias
   the result? Should they be reported?
6. **Additivity / blast radius.** Does anything here risk the working intraday families
   (the new `base.py` subclass, the CLI branch, shared persistence helpers)?
7. **Reproduction prediction.** Given all the above, do you expect the 2025 engine run
   to reproduce direction + magnitude (net positive, Sharpe ≈ 0.9–1.1, premium ≈ +2–3%)?
   Name the single most likely cause of a spurious divergence — in EITHER direction.

Please give: (a) any correctness/leak bug with severity, (b) whether you'd run the 2025
cross-check as-is or fix something first, (c) what engine cost config to use for a fair
comparison. Terse and concrete.
