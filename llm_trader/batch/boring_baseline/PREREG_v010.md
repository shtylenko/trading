# Pre-registration — Opp E boring baseline v0.1.0

**Before results.** Date: 2026-07-19.  
**Purpose:** Scoreboard. Any “clever” short-hold must beat a simple long process under **WeBull** costs.

## Thesis

If gap/micro selection cannot beat **owning liquid beta for the session**, it is not worth complexity or attention.

## Frozen baselines (evaluate all)

| Id | Rule |
|---|---|
| `spy_oc` | Every RTH day: buy **SPY** at official open (or first 5m open), sell at last RTH close (or 15:55 bar close) |
| `qqq_oc` | Same for **QQQ** |
| `spy_green_open` | Only days where first 5m bar is green; same hold to close |
| `spy_gap_nonneg` | Only days gap ≥ 0% vs prior close; open→close |

## Costs
- WeBull long equity, **MEGA** tier: commission 0, reg sell 0.5 bps, **slip 2 bps** one-way  
- Notional per trade: **$5,000** (matches research cap)

## Metrics (primary)
1. Mean **bps of notional** per day-trade (after costs)  
2. Total PnL on $5k  
3. Win%  
4. By calendar year 2025 / 2026 in window  

Also report intended-risk-style effR only if a stop is defined; for OC baseline use **bps** as primary.

## Comparison target
- Sealed Opp B `select_A` trades (n=15) on same window **2025-07-01 → 2026-06-30**  
- Convert select_A to mean bps of notional using actual shares×entry notional (or $5k if capped)

## Gates (scoreboard)

| Gate | Criterion |
|---|---|
| **Clever wins** | `select_A` mean bps > best boring baseline mean bps **and** select_A total PnL > that baseline’s total PnL on equal $5k sizing |
| **Clever loses** | Otherwise → treat select_A as **not better than beta session**; deprioritize until forward sample grows |
| Kill clever track | If select_A loses **and** n remains &lt; 30 after 3 more months of shadow → park |

## Window
**2025-07-01 → 2026-06-30** (same as Opp C probe).

## Outputs
- `batch/boring_baseline/scoreboard_v010/RESULTS.md`
