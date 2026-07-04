Here is an adversarial review of your swing engine implementation. 

**Verdict**: **DO NOT RUN the 2025 cross-check yet.** 
The implementation contains a critical survivorship bias bug, a calendar alignment bug, and a retroactive price look-ahead. If run as-is, the engine will not faithfully reproduce the offline model; it will likely print **spuriously higher returns** due to silently erasing bankrupted stocks and applying a cheaper cost model.

Here is the itemized breakdown.

### 1. CRITICAL: Survivorship Bias via Silent Drops (Delistings are erased)
* **Snippet**: `if i + hold_days >= len(bars): return None` (in `simulate_daily_hold`)
* **The Bug**: If you buy a stock on day `d` and it goes bankrupt, gets acquired, or is delisted on day `d+15`, it will not have `i+20` rows in its individual `bars` dataframe. This condition will evaluate to `True`, return `None`, and **silently drop the trade entirely**. You are perfectly dodging your worst losers (-100% hits), which will massively and falsely inflate your engine returns.
* **The Fix**: Do not rely on the stock's `len(bars)`. You must look up the exact market exit date (e.g. `exit_date = trading_calendar[entry_index + hold_days]`). If the stock has stopped trading before that date, you must exit the position at the last available closing price (and apply a recovery rate/penalty if it went bankrupt).

### 2. HIGH: Calendar Misalignment (Stock-Time vs. Market-Time)
* **Snippet**: `exit_j = i + hold_days` (in `simulate_daily_hold`)
* **The Bug**: `hold_days` is being added to the index `i` of the **stock's specific time series**. If a stock in your portfolio is halted for 3 days, `i+20` in its own dataframe pushes its exit date 3 market days *later* than the rest of the portfolio. The offline rule exited strictly at `d+20` across the board. 
* **The Fix**: Find the exit index using a global `trading_days` calendar, then locate that specific timestamp in the stock's bars: `exit_j = idx.get_loc(target_exit_date, method='ffill')`.

### 3. HIGH: Look-Ahead via Retroactively Adjusted Prices
* **Snippet**: `if close_d < 5.0: continue` (in `build_candidates`)
* **The Bug**: You are fetching `bars` ONCE over a massive range. Standard daily OHLC data is retroactively split-adjusted as of the *end* of the fetch window. If a $20 stock does a 5-for-1 forward split in late 2025, its historical adjusted price in early 2025 becomes $4. The engine will see `close_d < 5` and exclude it, even though it was point-in-time eligible. Conversely, reverse splits will illegally bring penny stocks into your universe. (Note: Dollar volume `c*v` is mathematically invariant to splits, so that filter is safe).
* **The Fix**: You must use **unadjusted** close prices for the `$5` filter, or ensure the upstream DuckDB query strictly returns point-in-time adjusted prices as of `rebal_ts`.

### 4. HIGH: Accidental Stop-Loss Divergence
* **Snippet**: `signal = Signal(..., stop_price=close_d*(1-0.10))` 
* **The Bug**: The offline rule did not have a stop loss (it blindly held to `d+20`). If `SwingStrategyRelease` sets `use_close_stop=True`, your engine will exit positions on any 10% dip. This fundamentally alters the strategy profile and makes the cross-check invalid.
* **The Fix**: Ensure `use_close_stop=False` in your swing configuration, or pass `stop_price=None`.

### 5. Cost Model Mismatch (Apples-to-Apples Config)
* **The Bug**: The offline model charged a flat 10 bps round-trip. The engine uses defaults: 2 bps entry slip + 2 bps exit slip + 0.5 bps/side fees = **5 bps round-trip**. By default, the engine will print higher net returns by 5 bps per trade (approx +0.63% annualized purely from cheaper costs).
* **The Fix**: Set the `ExecutionConfig` to exactly 10 bps round-trip. I recommend `entry_slippage_bps=5.0`, `exit_slippage_bps=5.0`, and fees to `0.0`. 

### Answers to Your Other Questions

* **End-of-range truncation**: Dropping the final trades of 2025 because they lack a full 20-day forward window is fine for evaluating *completed* trades. It slightly understates late-year exposure, but it does not aggressively bias the backtest like dropping mid-year delistings does.
* **Rebalance-phase alignment**: Yes, momentum is highly sensitive to the exact start date ("rebalance timing luck"). If `trading_days[::20]` shifts your rebalance dates by even 3–4 days compared to the offline `all_days[::20]`, you can easily see a +/- 1.0% annualized divergence simply from being out of phase. 
* **Off-by-one in Mom calc**: Your logic `c.iloc[-22] / c.iloc[-253]` is exactly correct. `-1` is `d`, so `-22` is `d-21` and `-253` is `d-252`.
* **MOC Assumption**: Entering at `close_d` after using `close_d` to rank is a classic MOC assumption. It is completely acceptable *for this replication*, since the offline model did exactly the same thing. 

**Reproduction Prediction**: 
If you run this code without changes, I predict the engine will yield a **significantly higher Sharpe and net return** (likely > +5.0% net) primarily because the `len(bars)` logic filters out all catastrophic individual stock bankruptcies, and the default execution config under-charges for slippage. 

Fix the exit calendar alignment and delisting drops, align the costs to 10 bps, remove the stop-loss, and ensure you are using unadjusted prices for the $5 filter. Then you are clear to run the out-of-sample seal.