# Momentum Burst Trading Strategy
## Creator: Pradeep Bonde (StockBee) | Used by: Kristjan Qullamaggie

### Overview
Pradeep Bonde, founder of StockBee, developed the Momentum Burst strategy after 20+ years of trading. He mentored Kristjan Qullamaggie ($5K → $100M+). The core insight: **stocks move in short-term momentum bursts of 3-5 days**, where they can make 8-40% moves. Between bursts, stocks pause or consolidate.

### Core Concept
Markets don't move in straight lines. Stocks move in a stair-step pattern:
1. **Range Expansion Day** — First day of the burst, signaled by a 4%+ move on increased volume
2. **Follow Through** — Next 2-3 days of continued upward price action
3. **Pause/Consolidation** — Stock rests, volume dries up
4. **Next Burst** — Pattern repeats

### Complete Setup Criteria (2Lynch Framework)
Pradeep Bonde's 2Lynch framework:

- **2** — Stock should NOT be up 2 days in a row before the breakout
- **L** — Linearity: Price must move linearly (no choppy action) in prior trend
- **y** — Not used (mnemonic)
- **n** — Negative/Narrow: Day before breakout should be negative or very narrow range
- **c** — Consolidation quality: Orderly consolidation with low volume; volatility contraction
- **h** — High close: Stock should close near its high on breakout day

**Variation with long consolidation:** Use 2Lynch + CV
- **C** — Catalyst needed for long consolidation breakouts
- **V** — Volume must surge 1.5-2x the 50-day average

### The 8-Point Criteria Checklist
1. **Range expansion** on breakout day (bigger than previous 3-5 days)
2. **Volume** on breakout day higher than previous day
3. **Day before** breakout should be narrow range or negative day
4. **No big breakdowns** or large-range moves during pre-breakout consolidation
5. **Linearity** in prior uptrend before consolidation period
6. **Orderly consolidation** during the entire move
7. **Lower/orderly volume** during consolidation
8. **Close near high** on breakout day

### Entry Rules

**4% Breakout Scan:** `c/c1>=1.04 and v>v1 and v>=100000`

**Entry Methods:**
1. **Breakout Entry** — Enter when stock moves 4-6% on the day
2. **Opening Range Breakout** — Enter on break of first 1-min or 5-min candle high
3. **Dollar Breakout** — For high-priced stocks: look for $5-50 move instead of 4%

**Entry Timing:** First hour of trading is best. Sometimes must enter in first 10-15 minutes.

### Stop Loss Placement
- Primary: **Low of the breakout day**
- Tighter: **Half the entry day's range** (if low is too far)
- Typical risk: **3% or less per trade**
- If stopped out, may re-enter if stock sets up again same day

### Profit Taking
- **Hold period:** 3-5 days (sometimes 8-10 days in rare cases)
- **Exit into strength:** Don't wait for reversal; sell while momentum is still strong
- **Trailing stop:** Once up 12%+, move stop to protect profits
- **Time stop:** If stock hasn't moved significantly in 3-5 days, exit

### Situational Awareness (Critical!)
This is Pradeep Bonde's most important concept. Before trading momentum bursts, ask:
- **"Are breakouts likely to work today?"**
- Check: Market Monitor (StockBee), sector analysis, index trends
- When most Market Monitor columns are green = good time to buy breakouts
- When first few columns are red = choppy, don't force trades

### Risk Management
- Per trade risk: **0.25-1%** of account (Qullamaggie uses 0.25-0.5%)
- Position size = (Account risk) / (Stop distance per share)
- Max position: 30% of account overnight (10-20% typical)
- Win rate: 25-35% (Qullamaggie says 25-30%)
- Average win: 5-8% per trade (up to 20-40% on best trades)
- Average loss: 3% or less

### Scanner Setup (TC2000)
**4% Breakout Scan:**
```
c/c1>=1.04 and v>v1 and v>=100000
```

**20%+ Movers (Study):**
```
c/c5>=1.2 and minv3.1>100000 and c>=5
```

**Dollar Breakout Scan:**
```
c-c5>=20 and minv3.1>=100000
```

### Adapting for $25-100k Account
- Focus on stocks $10-200/share for good liquidity
- Use 20-50 shares per trade ($2,000-5,000 position)
- Risk 0.5-1% per trade ($250-1,000 max loss)
- Limit to 3-5 open positions at a time
- Scan 100-200 stocks daily with Finviz/TradingView

### Common Mistakes
1. Buying stocks up 3+ days in a row (chasing)
2. Ignoring situational awareness (market filter)
3. Using too-wide stops (defeats the purpose)
4. Not exiting on time (momentum dies after 5 days)
5. Trading in choppy market conditions
6. Not using volume confirmation

### Resources
- StockBee Blog: stockbee.blogspot.com
- Qullamaggie: qullamaggie.net
- Financial Wisdom: financialwisdomtv.com
