---
name: analyst-radar-trade-ideas
description: Scan recent analyst predictions for actionable trade ideas — consensus signals, price targets with implied upside, and conflicting analyst views.
---

# Analyst Radar — Trade Ideas

Trigger: User says "trade ideas", "what should I trade", "any trade setups from analysts", etc.
**RULES: Work through every step in order. Do not skip. Do not ask questions unless blocked.**

All commands run from: `/Users/shtylenko/Hermes/projects`
Database: `/Users/shtylenko/Hermes/projects/trading/analyst_radar/data/analyst_radar.db`

---

## 1. Pull recent predictions with tickers (last 30 days)

```python
import sqlite3
from datetime import date, timedelta

conn = sqlite3.connect('trading/analyst_radar/data/analyst_radar.db')
conn.row_factory = sqlite3.Row

cutoff = (date.today() - timedelta(days=30)).isoformat()

rows = conn.execute("""
    SELECT
        p.id, p.prediction_text, p.prediction_type, p.direction,
        p.confidence, p.time_horizon, p.raw_quote, p.created_at,
        a.name  AS analyst_name,
        a.firm  AS analyst_firm,
        i.title AS interview_title,
        i.published_date,
        GROUP_CONCAT(t.ticker, ',') AS tickers
    FROM predictions p
    JOIN analysts a    ON a.id = p.analyst_id
    JOIN interviews i  ON i.id = p.interview_id
    LEFT JOIN prediction_tickers pt ON pt.prediction_id = p.id
    LEFT JOIN tickers t             ON t.id = pt.ticker_id
    LEFT JOIN prediction_outcomes po ON po.prediction_id = p.id
    WHERE p.created_at >= ?
      AND po.id IS NULL          -- unscored (outcome not yet recorded)
    GROUP BY p.id
    ORDER BY i.published_date DESC
""", (cutoff,)).fetchall()

print(f"Total unscored predictions (last 30d): {len(rows)}")
for r in rows:
    print(dict(r))
```

If there are zero rows → report "No unscored predictions in the last 30 days" and stop.

---

## 2. Group by ticker and compute consensus

For each ticker that appears in the results, collect:
- All predictions referencing it
- Direction breakdown: bullish count, bearish count, neutral count
- Confidence breakdown: high / medium / low counts
- Analysts who made calls on it
- Any explicit price targets (prediction_type = "price_target")
- Time horizons mentioned

Mentally build a table like:

| Ticker | Bullish | Bearish | Neutral | High-conf | Analysts |
|--------|---------|---------|---------|-----------|----------|
| NVDA   |    3    |    1    |    0    |     2     | Dan Ives, Tom Lee, Josh Brown |
| GLD    |    0    |    4    |    1    |     3     | Chris Vermeulen, David Rosenberg |

Predictions with NO ticker (macro_call, sector_call without a specific symbol) are grouped
separately under "Macro / Sector calls" and handled in step 4.

---

## 3. Fetch current prices for tickers with directional signals

For each ticker with at least one bullish or bearish prediction:

```python
import sys
sys.path.insert(0, '/Users/shtylenko/Hermes/projects')

from datetime import date, timedelta
from trading.marketdata.providers.yfinance_provider import YFinanceProvider

provider = YFinanceProvider()
end   = date.today()
start = end - timedelta(days=5)

# Fetch last close for each ticker
for ticker in tickers_with_signal:
    bars = provider.fetch_bars(ticker, '1day', start, end)
    if bars is not None and not bars.empty:
        last_close = bars['close'].iloc[-1]
        print(f"{ticker}: ${last_close:.2f}")
    else:
        print(f"{ticker}: price unavailable")
```

For price_target predictions, compute the implied upside/downside:
```
implied_move = (price_target - last_close) / last_close * 100
```

---

## 4. Identify the strongest setups

Score each ticker setup using this logic (your judgment, not Python):

**Strong signal** (worth surfacing):
- 2+ analysts agree on direction **and** at least one is high-confidence
- A price target with meaningful implied upside (>10% bullish) or downside (>10% bearish)
- A recent call (published in the last 7 days) with a near-term horizon (weeks to 3 months)

**Weak / skip**:
- Single analyst, low confidence, vague horizon ("sometime this year")
- Consensus is neutral or split (equal bullish/bearish)
- Implied move < 5%

**Red flag — conflicting signals**:
- Multiple credible analysts disagree (e.g., 2 bullish, 2 bearish on the same ticker)
- Surface these separately — they are NOT trade ideas but worth knowing

---

## 5. Score each ticker and store in the database

For every ticker that has at least one directional prediction (bullish or bearish),
compute a **bull/bear indicator** on the scale **−10 to +10** and write a
**~1000-word reasoning summary**.

### 5a. Scoring rubric

Start from 0 (neutral) and adjust:

| Signal | Adjustment |
|--------|-----------|
| Each additional bullish analyst | +1.5 |
| Each additional bearish analyst | −1.5 |
| High-confidence call | ×1.3 multiplier on that analyst's contribution |
| Low-confidence call | ×0.6 multiplier |
| Prediction < 7 days old | +0.5 bonus (bullish) or −0.5 (bearish) |
| Near-term horizon (< 3 months) | +0.3 (increases urgency) |
| Conflicting signals (bull + bear analysts) | dampen toward 0 proportionally |
| Single-source dominance (one analyst > 60% of calls) | cap magnitude at ±5 |

Clamp the final score to [−10, +10]. Round to one decimal place.

### 5b. Write the ~1000-word summary

Structure it as:

```
## [TICKER] — Analyst Sentiment Analysis

**Score: [X.X / 10]**   Updated: [today's date]

### What the analysts are saying
[2–3 paragraphs synthesizing the bullish thesis, bearish thesis, and any neutral/macro context.
Quote specific predictions with analyst names and firms. Mention time horizons and confidence levels.]

### Bull case
[Paragraph summarizing the strongest bullish arguments, citing analyst names and key quotes.]

### Bear case
[Paragraph summarizing the strongest bearish arguments. If no bears, state that explicitly.]

### Conflicts and uncertainties
[Any disagreements between analysts, caveats, single-source warnings, or macro dependencies.]

### Current price context
[Current price vs. any stated price targets. Implied upside/downside. Whether the price has
already moved toward the target.]

### Bottom line
[1–2 sentences: is this actionable? What would change the thesis?]
```

### 5c. Store via Python

```python
import sys
sys.path.insert(0, '/Users/shtylenko/Hermes/projects')
from trading.analyst_radar.db import get_db, update_ticker_sentiment

conn = get_db()

update_ticker_sentiment(
    conn,
    ticker="NVDA",           # exact ticker symbol
    indicator=7.5,           # your computed score, -10..+10
    summary="## NVDA — Analyst Sentiment Analysis\n\n...",  # ~1000 words
)
# Repeat for each ticker with directional predictions.
```

Storage is an upsert — re-running overwrites the previous score cleanly.

---

## 6. Report trade ideas in the conversation

Write a clean markdown report. Scores are already stored in the DB and visible in the
web UI at http://localhost:8082/tickers — this report is the human-readable summary.

```
## Analyst Radar — Trade Ideas  ({today's date})
_Based on {N} unscored predictions from the last 30 days_

---

### 🟢 Bullish setups

**{TICKER}** — {consensus_direction}, {bullish_count} analyst(s) bullish
- Current price: ${last_close}
- Price target: ${target} → implied upside: +{pct}%  _(if available)_
- Horizon: {time_horizon}
- Analysts: {analyst names and firms}
- Key quote: "{raw_quote}"

_(repeat for each strong bullish setup)_

---

### 🔴 Bearish setups

**{TICKER}** — {bearish_count} analyst(s) bearish
- Current price: ${last_close}
- Implied downside: -{pct}%  _(if price target available)_
- Horizon: {time_horizon}
- Analysts: {analyst names and firms}
- Key quote: "{raw_quote}"

---

### ⚠️ Conflicting signals (analysts disagree)

**{TICKER}**: {bullish_count} bullish ({names}) vs {bearish_count} bearish ({names})

---

### 📊 Macro / Sector calls (no specific ticker)

- "{prediction_text}" — {analyst_name}, {firm} ({published_date})
  Direction: {direction} | Confidence: {confidence} | Horizon: {time_horizon}

---

### Coverage gaps
Tickers with predictions but no price data available: {list}
```

---

## Notes

- **You are the analyst here.** Python pulls the data; you synthesize it. Do not let
  Python decide what's a "strong" setup — that judgment is yours.
- Do NOT fabricate price targets. If no price_target prediction exists for a ticker,
  say so — do not estimate implied move from vague directional calls.
- Chris Vermeulen dominates gold/silver predictions. Weight his calls accordingly —
  he is a technical trader with a gold/silver bias, not a broad macro economist.
- If a single analyst (e.g., Vermeulen) accounts for >50% of signals on a ticker,
  flag it: "Majority from one source — single-analyst signal."
- This is research output, not financial advice. All ideas require your own
  due diligence before acting.
