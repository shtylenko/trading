# SwingTrader — Two-Tier Long-Only Swing System

## Overview

Two-tier architecture:

```
Tier 1: Weekly Prioritization Scanner
  600+ tickers → score by swing potential → top 50 watchlist

Tier 2: Daily TradingView Monitoring (Buy)
  50-stock watchlist → TV alerts on buy setups → Hermes → Telegram → you execute

Tier 3: Daily TradingView Monitoring (Sell)
  Open positions → TV alerts on exit conditions → Hermes → Telegram → you close
```

The scanner finds candidates. TradingView watches them. You execute.

---

## Tier 1 — Weekly Prioritization Scanner

**Runs:** Sunday evening (or on demand).  
**Input:** SP500 + Nasdaq 100 (~600 tickers)  
**Output:** Ranked top 50 stocks for the week ahead  
**Data:** `trading.marketdata` (daily bars, last 250 days)

### Pre-filters (remove noise)

| Filter | Threshold |
|--------|-----------|
| Price | > $10 |
| Avg daily volume (20d) | > 500K |
| Market cap | > $2B |

### Scoring — "Swing Potential" (0-100)

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| Trend strength | 25 | EMA 20 > 50 > 100 > 200 = max. Partial alignment = partial score. |
| Pullback proximity | 20 | How close price is to EMA 20. Closer = better entry imminent. |
| RSI health | 15 | RSI in 40-55 range = reset but not broken. Below 30 = penalty. |
| MACD posture | 15 | Histogram above zero and rising = max. Below zero = penalty. |
| Volatility (ATR%) | 10 | Lower ATR/price ratio = calmer, more predictable. |
| Volume profile | 10 | Declining volume during pullback = orderly. Spikes = penalty. |
| Distance from 52w high | 5 | Not too extended (within 15% of high = bonus). |

### Output

```yaml
# swingtrader/watchlist.yaml (auto-generated)
week: 2026-W26
generated: 2026-06-22T18:00:00
stocks:
  - ticker: AAPL
    score: 87
    price: 195.30
    ema20: 192.10
    ema50: 185.40
    rsi: 44
    atr: 3.20
  - ticker: MSFT
    score: 83
    ...
```

---

## Tier 2 — Daily TV Monitoring

**Runs:** Continuously (alerts fire when conditions met)  
**Input:** The top 50 watchlist  
**Output:** Buy alerts via TradingView → Hermes notification

### Alert Conditions (per stock)

An alert fires when ALL of the following are true on the **daily** timeframe:

| # | Condition | What it means |
|---|-----------|---------------|
| 1 | Price crosses above EMA 20 **OR** closes within 1% of EMA 20 | Pullback entry zone reached |
| 2 | RSI(14) between 35 and 55 | Momentum is reset, not crashed |
| 3 | MACD histogram > previous bar's histogram | Momentum improving (turning up) |
| 4 | Today's volume < 1.5x 20d avg volume | No distribution panic |

### TV Alert Setup (per stock)

Each stock on the watchlist gets a TradingView alert with:
- **Condition:** The 4 rules above encoded as a Pine Script alertcondition()
- **Action:** Webhook → Hermes (or email, or TV notification)
- **Frequency:** Once per bar close (daily)

### When alert fires

Hermes receives the alert and delivers:

> **BUY SIGNAL: AAPL**  
> Price: $195.30 | EMA 20: $192.10 | RSI: 42  
> Setup: Pullback to EMA 20, RSI reset from 68, MACD histogram turning up  
> Suggested stop: EMA 50 at $185.40 | ATR: $3.20

You decide whether to execute through your broker.

## Tier 3 — Daily Exit Monitoring

**Runs:** Continuously (alerts fire when exit conditions met)  
**Input:** Open positions (tracked in `positions.yaml`)  
**Output:** Sell alerts via TradingView → Hermes → Telegram

### Exit Conditions (per open position)

An exit alert fires when ANY of these triggers on the **daily** timeframe:

| # | Condition | What it means |
|---|-----------|---------------|
| 1 | Price closes below EMA 50 | Intermediate trend broken. The swing thesis is invalid. |
| 2 | RSI(14) rises above 75 | Overbought — time to take profits. |
| 3 | MACD histogram crosses below zero and is declining | Momentum has flipped bearish. |
| 4 | Price hits 2x ATR above entry (trailing) | Profit target reached — secure gains. |

OR conditions (any one fires the alert). Buy signals are AND (all must be true). Exit signals are OR (any one means get out).

### Position Tracking

A `positions.yaml` file tracks what we're holding:

```yaml
# swingtrader/positions.yaml
positions:
  - ticker: AAPL
    entry_date: 2026-06-10
    entry_price: 189.40
    ema50_at_entry: 182.10
    atr_at_entry: 3.20
    status: open

  - ticker: MSFT
    entry_date: 2026-06-15
    entry_price: 420.00
    ema50_at_entry: 405.30
    atr_at_entry: 5.10
    status: closed
    exit_date: 2026-06-20
    exit_price: 435.00
    exit_reason: "Profit target hit (2x ATR)"
```

Updated manually after each trade, or auto-synced via Alpaca API (v2).

---

## Broker: Alpaca

- **Execution:** Alpaca Markets API (paper trading first, then live)
- **Flow:** Alert fires → Hermes sends Telegram notification → you review → you execute
  manually via Alpaca dashboard or mobile app
- **Future automation (v2):** Hermes can place orders directly via Alpaca API after your
  confirmation, tracking positions automatically
- **Paper trading URL:** https://app.alpaca.markets/paper-trading

---

## Alert Delivery Path

```
TradingView alert (Pine Script condition met)
  → Webhook to Hermes endpoint
    → Hermes processes alert (enriches with context: entry price, stop, ATR)
      → Telegram message to you
        → You execute via Alpaca
```

TV alerts use Pine Script `alert()` with a JSON payload. Hermes receives it, looks up the
stock's data from the watchlist, and crafts a human-readable Telegram message.

---

### Initial setup

1. Create a TradingView watchlist named "SwingTrader"
2. Weekly: after the prioritization scan, sync the watchlist to the top 50

### Sync flow

```
scanner.py → watchlist.yaml → tv_sync.py → TradingView MCP → updates TV watchlist
```

Using `ui_evaluate` or `watchlist_*` MCP tools to:
- Clear old watchlist entries
- Add new tickers
- Apply the alert template to each

---

## Project Structure

```
trading/swingtrader/
├── spec.md                  ← this file
├── config.yaml              ← thresholds, universe config, TV credentials
├── scanner.py               ← weekly prioritization (Tier 1)
├── scoring.py               ← swing potential scoring logic
├── signal.py                ← signal definitions (EMA pullback, future setups)
├── universe.py              ← SP500/Nasdaq100 loader + pre-filters
├── watchlist.yaml            ← auto-generated weekly top 50
├── positions.yaml            ← active positions (entry/exit tracking)
├── tv_sync.py               ← push watchlist to TradingView + set alerts
├── alert_handler.py         ← process incoming TV alerts → notification
├── reports/                 ← weekly priority reports
│   └── 2026-W26.md
└── tests/
    ├── test_scoring.py
    └── test_signal.py
```

### Dependencies

- `trading.marketdata` — daily bars
- `tradingview-mcp-jackson` — TV watchlist + alert management
- `pandas`, `numpy`, `pyyaml`
- Hermes cron (optional) — automate weekly scan + watchlist sync

---

## Weekly Workflow

```
Sunday 6pm ET:
  1. scanner.py runs → scores all 600 tickers → writes watchlist.yaml (top 50)
  2. tv_sync.py reads watchlist.yaml → pushes to TradingView "SwingTrader" watchlist
  3. Alerts auto-created for each stock with the 4-condition Pine Script template
  4. Weekly report written to reports/YYYY-Www.md

Monday–Friday:
  5. TV monitors the 50 stocks on daily close
  6. When alert fires → Hermes notifies you
  7. You review and execute through broker
```

---

## Risk Guardrails

| Rule | Value |
|------|-------|
| Max concurrent positions | 8 |
| Max per position | 5% of portfolio |
| Stop loss | EMA 50 or 2x ATR below entry (tighter) |
| Take profit | 2x ATR above entry (trailing) |
| No-go conditions | SPY below EMA 50 = skip all longs |
| Sector concentration | Max 3 positions per sector |
| Watchlist cap | 50 stocks (stays under TV/MCP rate limits, avoids bans) |

---

## Open Questions

1. **Daily re-scan for overnight movers?** The weekly scan sets the 50-stock watchlist Sunday.
   A quick daily scan could catch stocks that gapped into the setup zone overnight. Adds
   complexity — start without it, add if the weekly picks feel stale by Wednesday.

2. **Alert Pine Script:** One generic template applied to all 50 stocks, or individual
   scripts per stock with hardcoded EMA/RSI levels from the scanner output? Template is
   simpler to maintain; per-stock is more precise (uses actual EMA 20 price, not a percentage
   condition).

3. **Webhook endpoint:** Hermes needs an exposed HTTP endpoint to receive TV webhooks. Set
   this up via `hermes webhook` config, or use a Telegram bot as an intermediate relay?

4. **Paper vs live:** Start paper trading on Alpaca for 4-8 weeks to validate the signal
   quality before going live? Or go straight to live with small position sizes?
