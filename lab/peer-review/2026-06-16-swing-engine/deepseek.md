# Adversarial code review — swing engine path

## 1. Look-ahead / leakage

**No leak found.** The slicing is correct on every path:

- `ctx_daily[t] = b[b.index <= rebal_ts].tail(300)` — data ends at rebalance close, strictly ≤. ✓
- `build_candidates` reads only `context.daily` — never sees forward bars. ✓
- `simulate_daily_hold` receives the **full** `bars` (including forward) but only to realize the hold; entry index is determined by `rebal_ts` (a date, not a price condition). ✓
- Off-by-one check on `c.iloc[-22] / c.iloc[-253]`: with `upto` ending at `d` (rebalance date), `iloc[-1]=d`, `iloc[-22]=d−21`, `iloc[-253]=d−252`. Matches `close[d−21]/close[d−252]−1`. ✓
- Eligibility `(c*v).iloc[-20:].mean() >= 10M` and `close_d >= $5` both use only ≤d data. ✓

**Severity: none.** But flag one fragility:

> **`b[b.index <= rebal_ts]` has no `.normalize()` call**, unlike `simulate_daily_hold` which explicitly normalizes both sides. If `b.index` carries tz-aware timestamps and `rebal_ts` is tz-naive (or vice versa), the comparison silently produces empty slices → tickers dropped from candidate pool. This would cause **universe shrinkage**, not look-ahead, but could spuriously depress returns if it hits liquid names asymmetrically. **Low severity, easy fix:** normalize both sides in the runner, not just in `simulate_daily_hold`.

## 2. Entry/exit realism

**Entry:** `closes[i]` = rebalance-date close. This is a MOC (market-on-close) assumption — you observe the close, compute rankings, and "enter" at that same close. Standard for academic momentum backtests (Jegadeesh-Titman style). Acceptable for a research harness. The offline methodology uses the same assumption (`close(d+20)/close(d)−1`), so the engine faithfully reproduces it. ✓

**Exit indexing:**
```python
exit_j = i + hold_days          # default
for j in range(i+1, i+hold_days+1):   # checks i+1 … i+H inclusive
```
`range(i+1, i+H+1)` in Python yields `i+1, i+2, …, i+H`. The exit bar `i+H` IS checked for stop. If no stop triggers, `exit_j = i+H`. Correct — exit at close of `d+H`. ✓

**Boundary guard:**
```python
if i + hold_days >= len(bars): return None
```
Requires `i+H < len(bars)`, i.e., at least `H+1` bars including entry. The exit bar at index `i+H` must exist. Correct. ✓

**Stop loop:**
- Uses `closes[j]` (daily close), not `lows[j]`. A stock that gaps below stop intraday and recovers by close does NOT trigger. This is a close-only stop model — intentional per `use_close_stop` parameter. Acceptable given the 10% stop is wide and rarely hit.
- For longs: `closes[j] <= signal.stop_price`. Uses `<=` (not `<`). The stop price is `close_d * 0.90`. If the close equals the stop exactly, it triggers. This is correct.

**Severity: none.** The execution model is internally consistent and matches the offline methodology.

## 3. Cost model mismatch — expected divergence

| Component | Offline | Engine (default) |
|-----------|---------|------------------|
| Round-trip cost | 10 bps (flat subtraction) | ~5 bps (2+2 slippage baked into fills + 0.5+0.5 fees) |
| Application | `ret − 0.0010` (additive) | Multiplicative via `entry*(1+s)` and `exit*(1−s)` |

**Direction:** Engine should print **higher** net returns than offline +3.98% by ~5 bps per trade. Over ~12 rebalances, ~60 bps annualized tailwind.

**For apples-to-apples:** Set `entry_slippage_bps=5, exit_slippage_bps=5, fees_bps_per_side=0`. This bakes exactly 10 bps round-trip into fills. (Multiplicative vs additive difference is negligible at monthly return magnitudes — third-order, sub-1bp.)

**Severity: expected divergence, not a bug.** Must be adjusted before comparing to offline benchmark.

## 4. Rebalance-phase / universe alignment

Two potential divergence sources:

**(a) Phase shift.** Offline uses `all_days[::20]`; engine uses `trading_days[::cadence]`. If the anchor trading day differs (different data start, different calendar), the rebalance grid shifts by 1–19 days. A 1-day phase shift changes:
- Which names are eligible (slightly different close and volume filters)
- The 12-1 momentum ranking (different `d−21` and `d−252` reference closes)
- The forward return window

This alone could explain **0.5–1.5% annual return difference** — the strategy has moderate turnover, so ranking is somewhat sensitive to the exact reference dates.

**(b) PIT universe membership.** Offline uses "eligible universe as of d" from a survivorship-honest grid. Engine uses PIT membership per rebalance date. If the membership sources differ (e.g., different index inclusion methodology), the candidate pool differs → different top-50 selection.

**Severity: medium.** Not a bug but a calibration issue. The review document should (1) log the exact rebalance dates used by both, (2) compare PIT member counts per date, (3) attribute any divergence to phase/universe before concluding "engine bug."

## 5. End-of-range truncation bias

```python
if i + hold_days >= len(bars): return None   # silently dropped
```

Late-2025 rebalances whose forward window extends past the data boundary are dropped. For 2025 with ~252 trading days and 20-day cadence, this affects **1–2 rebalances** (mid-December, possibly late-November depending on exact calendar). That's 8–17% of observations.

**Direction of bias:** Unknown a priori — depends on whether the dropped period(s) would have been positive or negative. But any systematic drop of end-of-sample observations creates a subtle survivorship bias (you only count periods with full outcome data).

**Severity: low for this specific test** (1–2 periods won't flip the sign), but:
- **Must be reported transparently** — count of dropped rebalances, which dates, how many names.
- For production: extend the data range by `H` days past the last rebalance date, or compute partial returns for truncated periods.

## 6. Blast radius — intraday families

**Safe.** The new `SwingStrategyRelease` subclass:
- Adds `is_swing=True` (defaults `False` in base — intraday releases unaffected)
- Overrides `exit_cutoff` to return `None` (swing-specific)
- Requires subclasses to implement `build_candidates` + `build_signal`

The CLI dispatch branches on `is_swing` — intraday strategies never enter the swing path. Shared persistence (same tables) writes the same schema (candidate/signal/order/trade/fills) — no schema migration needed.

**One caution:** If both swing and intraday strategies are run in the same backtest and write to the same tables, downstream analytics must filter by strategy or `exit_cutoff` to avoid mixing 20-day holds with intraday scalps. Not a code bug, but a data-hygiene note.

**Severity: none.** Intraday path is untouched.

## 7. Reproduction prediction & most likely divergence cause

**Baseline expectation** (after matching costs to 10 bps):
- Direction: **net positive** ✓
- Magnitude: **+3.0–5.0%** net (overlapping with offline +3.98%)
- Sharpe: **0.8–1.1** (overlapping with offline 1.08)
- Premium: **+2.0–3.5%** (overlapping with offline +2.78%)

The engine should reproduce the signal — the implementation is faithful.

**Single most likely cause of spurious divergence (EITHER direction):**

> **Rebalance phase misalignment.** If the engine's `trading_days[::20]` selects a different set of rebalance dates than the offline `all_days[::20]`, every downstream quantity shifts — ranking scores, selected names, and forward returns all change. This is not a bug but an alignment issue that can produce differences of ±1–2% annualized, easily swamping the cost-model difference. It can push the engine result EITHER above or below offline, depending on whether the shifted dates happen to be more or less favorable for the momentum signal in 2025.

**Runners-up:**
- **Cost model mismatch** (predictable direction: engine higher if unadjusted) — fixable
- **PIT universe differences** (harder to predict, likely smaller than phase shift)
- **End-of-range truncation** (small effect, unpredictable direction)

---

## Verdict

| Question | Answer |
|----------|--------|
| **(a) Correctness/leak bugs?** | No look-ahead or leakage. One fragility: `b.index <= rebal_ts` without `.normalize()` — fix by normalizing in the runner (low severity). No execution-indexing bugs found. |
| **(b) Run as-is or fix first?** | **Fix two things first:** (1) Set cost config to `entry_slippage=5, exit_slippage=5, fees_per_side=0` for fair comparison. (2) Log the exact rebalance dates + PIT member counts per date so any divergence can be attributed to phase/universe rather than bugs. The `normalize()` fragility is cosmetic but worth fixing. Then run. |
| **(c) Engine cost config for fair comparison?** | `entry_slippage_bps=5, exit_slippage_bps=5, fees_bps_per_side=0` → 10 bps round-trip baked into fills, matching offline. |