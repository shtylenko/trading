# Cup-and-Handle Pattern Library

> Comprehensive research archive on the cup-and-handle (cup-with-handle) pattern for stock swing trading.
> Last updated: 2026-07-16

---

## Table of Contents

1. [Origins & Canonical Definition](#1-origins--canonical-definition)
2. [Bulkowski's Empirical Statistics](#2-bulkowskis-empirical-statistics)
3. [Academic Research](#3-academic-research)
4. [VCP Comparison (Minervini)](#4-vcp-comparison-minervini)
5. [Entry Timing & Breakout Confirmation](#5-entry-timing--breakout-confirmation)
6. [Stop-Loss Optimization](#6-stop-loss-optimization)
7. [Profit Targets & Exit Strategies](#7-profit-targets--exit-strategies)
8. [Market Regime & Sector Filters](#8-market-regime--sector-filters)
9. [Volume Analysis](#9-volume-analysis)
10. [Cup Shape & Geometry Quantification](#10-cup-shape--geometry-quantification)
11. [Handle Quality Metrics](#11-handle-quality-metrics)
12. [Improving Filters (Position Sizing, RS, Fundamentals)](#12-improving-filters)
13. [Machine Learning / Quantitative Approaches](#13-machine-learning--quantitative-approaches)
14. [Known Failure Modes](#14-known-failure-modes)
15. [PineScript & TradingView Implementations](#15-pinescript--tradingview-implementations)
16. [Backtest Performance Across Markets](#16-backtest-performance-across-markets)
17. [Position Sizing & Risk Management](#17-position-sizing--risk-management)
18. [Comparison to Current Implementation](#18-comparison-to-current-implementation)

---

## 1. Origins & Canonical Definition

### William O'Neil — CAN SLIM / IBD (1950s–present)

- **Founder:** William J. O'Neil, "How to Make Money in Stocks" (1988, 4th ed. 2009)
- **Concept:** The cup-with-handle is a bullish continuation pattern representing institutional accumulation followed by a final shakeout of weak holders
- **Base types:** cup, cup-with-handle, double bottom, flat base, ascending base, saucer, saucer-with-handle, IPO base

### O'Neil's Original Rules

| Component | O'Neil Rule | Source |
|-----------|-------------|--------|
| Prior uptrend | 30%+ rally before the cup begins | How to Make Money in Stocks |
| Cup shape | Rounded U-shape, NOT V-shaped | IBD / MarketSmith |
| Cup duration | 7–65 weeks (weekly chart) | How to Make Money in Stocks |
| Cup depth | 12–35% correction (ideally 15–30%) | IBD research |
| Cup rims | Left and right rims near same price level | MarketSmith |
| Handle position | Upper 1/3 of cup (above midpoint) | IBD |
| Handle duration | 1–4 weeks (weekly chart) | How to Make Money in Stocks |
| Handle slope | Downward drift or flat (NOT rising) | IBD |
| Handle depth | ≤ 1/3 of cup depth | O'Neil |
| Breakout | Close above handle high (pivot point) | IBD |
| Breakout volume | ≥ 1.5× avg (ideally 2×) | IBD |
| RS rating | ≥ 70 (ideally 90+) | IBD / CAN SLIM |
| EPS growth | ≥ 18–25% YoY quarterly | CAN SLIM |
| Market direction | Bull market (M in CAN SLIM) | CAN SLIM |

### Psychological Basis (per DXP Analytics)

1. Stock rallies → late buyers at top panic on pullback
2. Institution quietly accumulates during dip → rounded bottom
3. Price recovers to near prior high → breakeven sellers exit ("Thank God I'm out even")
4. This creates the handle — last shakeout of weak hands
5. When sellers exhausted, one push of buying breaks out → short covering + breakout orders

---

## 2. Bulkowski's Empirical Statistics

### Source: Thomas Bulkowski, Encyclopedia of Chart Patterns (3rd ed., 2021)
### Database: 913 perfect cup-with-handle patterns, 500 stocks, bull market

### Overall Rankings (out of 39 patterns, bull market upward breakouts)

| Metric | Rank | Value |
|--------|------|-------|
| Performance rank (1=best) | **#3** out of 39 | 54% avg rise |
| Failure rate rank (1=best) | **#2** out of 39 | 5% breakeven failure |
| Overall rank | Top-5 pattern | — |

### Key Statistics

| Statistic | Value |
|-----------|-------|
| Break-even failure rate | **5%** |
| Average rise after breakout | **54%** |
| Throwback rate | **62%** |
| Percentage meeting price target | **61%** |
| Sample size | 913 patterns |

### Identification Guidelines (Bulkowski)

| Characteristic | Rule |
|---------------|------|
| Price trend | Rising into cup start |
| Shape | Rounded U-turn with handle on right |
| Cup shape | U-shaped (not V-shaped) |
| Handle | Required on right side |
| Cup duration | 7–65 weeks |
| Handle duration | ≥ 1 week, upper half of cup |
| Cup rims | Near same price level (flexible) |

### Trading Tips

| Tactic | Detail |
|--------|--------|
| Measure rule | Cup depth (right lip to valley) × 61% + breakout price |
| Inner cup | Trade inner cup when price rises above handle |
| Trendline | Down-sloping trendline along handle peaks → early buy |
| Stop | Handle low |
| Short handles | Handles shorter than median (22 days) → superior post-breakout performance |
| Throwbacks | Throwbacks hurt performance (62% of patterns throw back) |

### Post-Breakout Retrace Study (300 patterns, 1990–2024)

- **47%** of cup-with-handle patterns dropped substantially within 2 months of breakout
- **23%** saw price rise no more than 15% before dropping
- These retracements can be 15%+ declines

### Variants Performance

| Variant | Performance Rank | Failure Rank |
|---------|-----------------|--------------|
| Cup with handle (bullish) | #3 | #2 |
| Cup with handle, inverted (bearish) | #6 | #7 |
| Cup without handle (rounding bottom) | #7 | #1 (best failure rate) |

### Time Performance Trend

- Cup-with-handle average rise: 49% (1990s) → 54% (overall) → 55% (recent)
- Consistently one of the top-performing patterns across decades

### Bulkowski's Rank — Top 10 Reversals & Continuations

| Rank | Pattern | Avg Rise |
|------|---------|----------|
| 1 | Cup with handle | **54%** |
| 2 | Rounded top | 51% |
| 3 | Three rising valleys | 51% |
| 4 | Rectangle top | 51% |
| 5 | Rounded bottom | 48% |
| 6 | Diamond bottom | 47% |
| 7 | Scallop inverted and ascending | 45% |
| 8 | Scallop inverted and descending | 44% |
| 9 | Ascending triangle | 43% |
| 10 | Ascending scallop | 42% |

---

## 3. Academic Research

### 3.1 O'Neil Global Advisors — "Breakouts: Pump up the Volume" (2022)

- **Period:** Jan 1995 – Sep 2021
- **Sample:** ~197,000 breakout events from O'Neil patterns
- **Universe:** US stocks, excluding bottom 50% liquidity

#### Key Findings — Monotonic Volume-Performance Relationship

| Volume % Change | 63d Cumul Return | 63d Cumul Alpha | Hit Rate | Avg Gain | Avg Loss |
|----------------|-----------------|----------------|----------|----------|----------|
| <50% | 2.61% | 0.67% | 57.68% | 12.91% | -11.42% |
| 50–100% | 3.01% | 0.89% | 56.85% | 14.97% | -12.75% |
| 100–150% | 3.12% | 1.11% | 57.10% | 15.89% | -13.87% |
| **>150%** | **5.04%** | **2.79%** | 56.86% | **19.90%** | -14.53% |

**Conclusion:** Alpha rises monotonically with breakout volume. Volume >150% (2.5× avg) produces 2.8% excess alpha over 63 days — statistically significant at 99% confidence.

### 3.2 SVM-Based Cup Detection (Fudan University, 2023)

- SVM with Gaussian RBF kernel on S&P 500 data (60-day windows)
- R² = 0.7 for true labels vs 0.2 for random labels
- Proves ML can detect cup patterns with reasonable accuracy

### 3.3 CAN SLIM Academic Studies

**Lutey & Mukherjee (2023)** — "Towards a Simplified CAN SLIM Model"
- CAN SLIM ranked #1 among 4 Wizard models (Buffett, Graham, Greenblatt, O'Neil)
- CAN SLIM performance: 16.01% annualized, alpha 10.87%, beta 0.71
- Max drawdown: -47.01% over 1999–2023
- Total return: 3,558% vs S&P 500 405%

**Live Out-of-Sample Testing of CAN SLIM (2014–2017)**
- Outperformed S&P 500 by 20%, Nasdaq by 9%
- Portfolios: 4/5 stocks gained 100%+ (Google +146.65%, Facebook +227.20%, Skyworks +156.04%)
- Sharpe ratio: favorable

**AAII CAN SLIM Screen (1998–2026)**
- Annual gain: 13.4% vs S&P 500 7.3%
- YTD 2026: +10.6% vs S&P 500 +0.6%

**China A-Share CAN SLIM (2015–2025)**
- Cumulative return: 4,000%+ (ChiNext50)
- Win rate: 60%+ for 100-day holding period
- Used HP filter + GARCH(1,1) for market regime, ARIMA for pattern recognition

### 3.4 Pattern Frequency Study (Bulkowski, 500 stocks 1991–1996)

Cup-with-handle: rank #3 for upward breakouts out of 35 patterns by frequency
- Pipe bottoms (#1), Ascending triangles (#2), Cup (#3)

### 3.5 Stock Data Analytics — 370,000 Patterns Analysis

Cup & Handle performance from systematic scan:
- **60% market beat rate** (vs S&P 500)
- **8.3% average return on win** (highest avg return among 16 pattern types)
- **Only 0.1 detections/day** (rarest pattern — only 1.2% of total detections)
- Patterns with 2 resistance touches: 55% beat rate; 3-4 touches: 48%; 5+: 42% — diminishing returns on repeated tests

---

## 4. VCP Comparison (Minervini)

### Mark Minervini's Volatility Contraction Pattern

Minervini developed VCP as a refinement of O'Neil's cup-with-handle. The key difference: VCP adds **progressive volatility contraction** — each pullback is shallower than the last.

### VCP Criteria (Seven Essential Components)

| # | Criterion | Specification |
|---|-----------|--------------|
| 1 | Progressive contractions | 2–4 phases, each shallower (e.g., 18%→12%→6%) |
| 2 | Volume dry-up during pullbacks | Volume contracts with each tightening phase |
| 3 | Volume expansion on rallies | Demand building between contractions |
| 4 | Stage 2 uptrend | Price > 50/150/200 SMA, MAs trending up |
| 5 | RS rank | >70 (ideally 90+) |
| 6 | Earnings growth | 20%+ YoY quarterly, expanding margins |
| 7 | Market environment | Major indices in uptrend |

### Typical VCP Contraction Sequence

| Phase | Price Depth | Volume | What It Signals |
|-------|-------------|--------|-----------------|
| T1 | 15–25% | Elevated | Initial profit-takers exiting |
| T2 | 8–15% | Declining | Weaker sellers being exhausted |
| T3 | 4–8% | Near dry | Only committed holders remain |
| T4 (optional) | 2–4% | Minimal | Final squeeze before breakout |

### VCP Performance Data

| Source | Win Rate | PF | Sharpe | Trades | Market |
|--------|----------|----|--------|--------|--------|
| Sharpely (India stocks) | **59.46%** | — | 1.68 | 185 | NSE India |
| PineScriptForge (ZB bonds) | **53.0%** | 1.45 | 1.91 | 266 | ZB Futures |
| EasySwing (US stocks) | **65–72%** | — | — | 48+ | US equities |
| FinancialWisdomTV (top 100) | **36% of winners** | — | — | 36 | US stocks |
| BreakoutDB (recent 20) | — | — | — | 15 | US stocks |
| All 7 criteria met | **~91%** | — | — | — | — |

**Key numbers from specific studies:**

- **Sharpely VCP (2023–2026):** ₹1Cr → ₹2.77Cr (+177% vs benchmark +45%), Sharpe 1.68, Sortino 2.42, Alpha 23.26%, Avg Win 20.05%, Avg Loss -11.58%
- **FinancialWisdomTV:** Among top 100 performing stocks, only 36 had clean VCPs. Avg risk 6%, avg gain 69%, avg R:R 11:1
- **PineScriptForge ZB VCP (266 trades):** 53% WR, 1.45 PF, 1.91 Sharpe, 9.8% max DD
- **BreakoutDB:** 15 recent breakouts, avg gain 40.9%, avg duration 15.3 days, avg R:R 11.3:1

### VCP vs Classic Cup-and-Handle: Key Differences

| Dimension | Classic Cup-Handle | VCP (Minervini) |
|-----------|-------------------|-----------------|
| Handle concept | Single handle drift | 2–4 sequential contractions |
| Depth progression | Handle < 1/3 cup depth | Each contraction shallower than prior |
| Volume requirement | Handle vol < cup avg vol | Progressive vol dry-up, then 40–50% surge |
| Entry trigger | Break handle high | Break pivot of final contraction |
| Fundamental filter | CAN SLIM | SEPA (earnings + RS + industry) |
| Stop placement | Below handle low | Below T3/T4 low |
| Market regime | Off by default | Required (indices in uptrend) |

### The Sector Factor (FinermarketPoints Research)

- 60–73% of momentum profits derive from sector-level factors (Moskowitz & Grinblatt, 1999)
- Strong stocks in weak sectors: only **51.3% win rate** (barely better than random)
- Even moderate setups in leading sectors significantly outperform perfect setups in lagging sectors
- **Three-stage filter:** sector momentum → fundamental quality → technical VCP pattern

---

## 5. Entry Timing & Breakout Confirmation

### Entry Methods Compared

| Method | Description | Win Rate | R:R | Miss Rate |
|--------|-------------|----------|-----|-----------|
| Aggressive trendline | Buy when price closes above down-sloping handle trendline | ~55% | ~3:1 | Low |
| Classic handle high | Buy when price closes above handle high | 55–65% | 2.5:1–4:1 | Low |
| Volume-confirmed | Wait for price break + volume ≥1.5× avg | 60–70% | 2.5:1–4:1 | ~10% of breakouts excluded |
| Pullback/retest | Enter on retest of breakout level after initial break | 65–75% | 3:1–5:1 | ~40% (patterns without pullback) |
| Gap-up | Enter on gap above handle high with heavy volume | 70%+ | 3:1–5:1 | Very high |

### O'Neil Breakout Statistics (OGA, 197,000 events, 1995–2021)

- All breakouts: 1.1% alpha, 3.2% return over 63 days
- Volume >150%: 2.8% alpha, 5.0% return
- Hit rate: ~57% regardless of volume level

### Volume Confirmation Thresholds

| Source | Required Multiplier | Notes |
|--------|-------------------|-------|
| O'Neil (IBD) | ≥ 1.5× avg (ideally 2×) | Non-negotiable |
| OGA Research | >150% vol change (= 2.5× avg) | Most alpha |
| EasySwing | ≥ 40% above 50d avg | 1.4× |
| LuxAlgo | ≥ 40–50% above avg | 1.4–1.5× |
| TradingSim | ≥ 40–50% above 20d avg | 1.4–1.5× |
| DXP Analytics | ≥ 50% above 20d avg (ideally 2×) | 1.5× minimum |
| ChartGuys | ≥ 40–50% above avg | 1.4–1.5× |

**Consensus:** Minimum 1.4× avg volume on breakout. 2×+ volume = institutional quality.

### Price Confirmation

- Close above handle high (not just intraday wick) — **consensus**
- Some: Close in upper 1/3 of day's range
- Some: 2–3% above handle high for additional buffer
- DXP: 1% above pivot → enter
- MarketSmith backtest: entry at 1% above pivot

### Prebreak Arm vs Confirmed Breakout

Your `prebreak_arm` mode is well-validated by research:
- Bulkowski: 62% throwback rate means buying breakouts often sees immediate retrace
- OGA: breakouts with volume >150% still see MAE of -14%
- Arm strategy (buy-stop at handle high for later session) avoids poor intraday fills and gap risk

---

## 6. Stop-Loss Optimization

### Stop Placement Methods

| Method | Typical Distance | Pros | Cons |
|--------|-----------------|------|------|
| Below handle low | 5–8% below entry | Natural invalidation point | May be too tight for volatile stocks |
| Below handle low + ATR buffer | Handle low − 0.5–1× ATR | Accounts for noise | Wider stop |
| ATR-based (1.5× ATR) | 1.5× ATR below entry | Adapts to volatility | May not align with structure |
| ATR-based (2–3× ATR) | 2–3× ATR below entry | Survives normal noise | Wide; small position size |
| Below cup midpoint | ~8–15% below entry | Very forgiving | Huge losses if triggered |
| Below handle + support | Varies | Best of both | Needs individual calc |

### Current Implementation: 1.5× ATR Stop

- Research support: TradeAlgo shows 1.5–2× ATR stops produce best risk-adjusted returns for 3–15 day holds
- Tighter than 1× ATR → triggered by noise
- Wider than 3× ATR → too much exposure for swing
- **Consensus:** 1.5–2.5× ATR is the sweet spot

### Stop Distance Benchmarks

| Source | Stop | Notes |
|--------|------|-------|
| Bulkowski | Below handle low | 5–8% typical |
| Minervini | Below T3/T4 low | 7–8% max |
| EasySwing | 1.5 ATR below entry | ~1R |
| TradeAlgo | 1.5–2× ATR + support | ~5–10% |
| O'Neil | Below handle low | ~5–8% typical |

### Post-Entry Stop Management

| Phase | Action | Source |
|-------|--------|--------|
| After T1 hit | Move stop to breakeven | Market consensus |
| After 1× ATR in your favor | Tighten to 1× ATR trail | TradeAlgo |
| Below SMA50 | EXIT_CLOSE on expanding downside volume | Your 0.6.0 skill |

---

## 7. Profit Targets & Exit Strategies

### Measured Move Target

**Formula:** `Target = Breakout Price + Cup Depth`

Consensus across all sources: This is the standard target.

**Bulkowski:** 61% of patterns meet measured move target
**DXP:** 65–70% hit rate with proper volume confirmation

### Target Levels Comparison

| Source | T1 | T2 | Extended |
|--------|----|----|----------|
| Your implementation | 0.50 × cup depth | 0.80 × cup depth | — |
| O'Neil | 20–25% above pivot | — | Measured move |
| Minervini | 2× ATR (1.3R) | 4× ATR (2.7R) | Trailing |
| Bulkowski | Measured move × 61% | — | — |
| LuxAlgo | 62% Fib (0.62 × cup depth) | 100% (full measure) | 161.8% Fib |
| Quantum-Algo | 1× measured move (50%) | 1.618× Fib (30%) | Trailing (20%) |
| TradingSim | Cup depth | 1.5× cup depth | Trailing stop |

**Key insight:** Your T1=0.50 and T2=0.80 × cup depth is close to the LuxAlgo Fibonacci targets and more conservative than full measured move. This aligns with the 62% throwback rate — taking partial profits before the full target reduces volatility.

### Average Hold Period

- Minervini-style: ~50 calendar days (7 weeks)
- EasySwing VCP: ~11 days (for VCP)
- BreakoutDB: ~15.3 days
- Cup-handle swing: 6–40 trading days (your max)

### Scaling Out Strategy (from Quantum-Algo)

1. Sell 50% at measured move target
2. Sell 30% at 1.618× Fibonacci extension
3. Trail remaining 20%

### Trailing Stop Methods

| Method | When to Activate | How |
|--------|-----------------|-----|
| 10-day EMA | For stocks with ADR > 10% | Exit when close below 10 EMA |
| Swing low | After 1R profit | Trail below most recent swing low |
| 1.5× ATR | After entry | Trail at 1.5× ATR below highest close |
| Parabolic SAR | On entry | Auto-trail |

---

## 8. Market Regime & Sector Filters

### Market Regime Impact

| Condition | Pattern Success | Source |
|-----------|----------------|--------|
| Major indices above 10-month EMA (200-day SMA) | **90.77%** success rate | FinermarketPoints (VCP research) |
| Major indices in correction | Significantly lower | Minervini |
| SPY above SMA50 | Higher win rate | Consensus |
| Bull market | 65–80% | TradingSim |
| Bear market | <50% | Multiple sources |

### Your Implementation: SPY above SMA50 (off by default)

- Research strongly supports making this ON by default or at a minimum recommending it
- LuxAlgo: "Filtering out patterns below declining 200d MA cuts failure rates nearly in half"

### Sector Filter Impact

| Filter | Win Rate Impact | Source |
|--------|-----------------|--------|
| No sector filter | ~55–60% baseline | Multiple |
| Sector ETF above SMA50 | +5–10% | DXP |
| Top-quintile sector | **60–73%** of momentum return | Moskowitz & Grinblatt |
| Bottom-quintile sector | 51.3% (barely above random) | FinermarketPoints |
| Sector + pattern combined | 73%+ | Moskowitz (trending) |

### Recommended Sector Filter Implementation

1. Check sector ETF (XLK, XLF, XLV, etc.) > SMA50
2. Alternatively: check RS rank of sector vs all sectors
3. Only enter cup-handle when sector is in top 50% of RS rank
4. This should be the DEFAULT filter, not optional

---

## 9. Volume Analysis

### Volume Pattern Throughout Formation

| Phase | Expected Volume | Warning Sign |
|-------|----------------|--------------|
| Cup left side (decline) | Elevated, then declining | Volume spikes during decline |
| Cup bottom | Below average, drying up | Irregular volume increases |
| Cup right side (recovery) | Gradually increasing | Consistently low volume |
| Handle formation | Lower than cup average | Volume HIGHER than cup |
| Breakout | **>1.5× avg** (ideally 2×+) | Flat or declining volume |

### Volume Direction vs Magnitude Insight

**StockDataAnalytics finding (370K patterns):** Volume DIRECTION matters more than volume MAGNITUDE:
- If 3+ of top-5 volume days in 20-day window are UP days → significantly more likely to break upward
- A stock with 1.5–2× volume on up days is BETTER than a stock with 3–5× volume on down days
- Created metric: **Net Distribution** = % of top quartile volume days that were up days

### O'Neil Volume Study (OGA, 2022)

Monotonic relationship: every step up in breakout volume % produces higher returns.
- **<50% vol change:** 0.67% alpha
- **50–100%:** 0.89% alpha
- **100–150%:** 1.11% alpha
- **>150%:** 2.79% alpha

### Volume Considerations for Your Implementation

| Your Current Setting | Research Benchmark | Suggestion |
|---------------------|-------------------|------------|
| `require_breakout_volume: True` | Universal consensus | Keep |
| `breakout_vol_mult: 1.3` | Consensus: 1.4–2.0× | Consider raising to **1.5** |
| `handle_vol_frac_max: 0.85` | Handle vol < cup avg | Good |
| `rvol_lookback: 20` | 20–50d | Good (20d is standard) |

### Net Distribution Signal

Research shows that a better volume signal than raw RVOL is:
- In a 20-day window, count the top-5 volume days
- If 3+ of those were UP days (close > open), bullish signal
- If 3+ were DOWN days, distribution = bearish signal

This could be added as an additional filter to the `_prep_daily` enrichment step.

---

## 10. Cup Shape & Geometry Quantification

### U-Shape vs V-Shape Detection

| Method | Description | Source |
|--------|-------------|--------|
| Quadratic regression | Fit parabola to cup, check R² ≥ 0.75 | Abiroid Cup & Handle |
| Concavity check | a ≥ 0 for bullish cups (upward opening) | Abiroid |
| Peak shift | Parabola vertex within ±0.5 of center | Abiroid |
| Symmetry | Left side ≥ 25%, right side ≥ 25% of width | Abiroid |
| Near-trough bars | ≥2 bars within 3% of trough low | **Your implementation ✓** |
| 2nd trough check | No distinct 2nd low (would be double bottom) | DXP |

### Quadratic Regression Parameters (Abiroid)

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| Min R² | 0.75 | 0.5–0.95 | Shape fit quality |
| Peak shift max | 0.50 | 0.2–1.0 | Cup centering |
| Min side asymmetry | 25% | 10–40% | Balance |
| Concavity | ≥ 0 | — | Bull cup |

### Cup Depth Sweet Spot

| Depth | Success Rate | Context | Source |
|-------|-------------|---------|--------|
| 8–12% | 65–70% | Strong stock, strong market | DXP |
| **12–20%** | **70–75%** | **Ideal** — shakes weak holders | DXP |
| 20–35% | 60–65% | Valid but deeper | DXP |
| 35–50% | 45–55% | Borderline — too much damage | DXP |
| 50%+ | <40% | Not a cup; bear market decline | DXP |

**Your implementation:** 12–35% — matches research perfectly ✓

### Cup Duration

| Source | Min | Max | Sweet Spot |
|--------|-----|-----|-----------|
| Bulkowski | 7 weeks | 65 weeks | — |
| O'Neil | 7 weeks | 65 weeks | 6–12 weeks |
| DXP | 4 weeks | 6 months | 6–12 weeks |
| **Your impl** | **20 bars (~4 weeks)** | **90 bars (~18 weeks)** | — |

**Note:** Your 20–90 bar range for daily charts translates to ~4–18 weeks. The low end (20 bars) allows cups as short as 4 weeks — research suggests cups <5–6 weeks are less reliable. Consider raising `cup_min_bars` to 30–35.

### Lip Alignment

| Source | Tolerance |
|--------|-----------|
| Your implementation | 5% |
| Bulkowski | Flexible — rims near same level |
| O'Neil | Near same price level |
| Abiroid | Max P1/P3 difference configurable |

Your 5% lip tolerance is slightly stricter than O'Neil. This is good — tighter lips = cleaner breakout.

### Inner Cup Detection

Bulkowski's finding: Cups often form within cups (multi-timeframe nested patterns). Trade the inner cup breakout for high-probability entries. Your formation_key deduplication already prevents double-counting the same geometry.

---

## 11. Handle Quality Metrics

### Handle Depth as % of Cup Depth

| Source | Max Handle / Cup Depth | Notes |
|--------|----------------------|-------|
| Your implementation | 40% | `handle_depth_max_frac: 0.40` |
| Bulkowski | — | Handle forms in upper half |
| O'Neil | ~33% (1/3) | Handle ≤ 1/3 cup depth |
| DXP | 12–15% of cup height | More restrictive |
| Q-Algo | 33% (1/3) | Stricter = better |
| Minervini (VCP) | ~20% | Each contraction shallower |

**Research suggests:** 33% (O'Neil's 1/3 rule) is the standard. Your 40% allows slightly deeper handles. Consider tightening to **0.33** for higher reliability.

### Handle Duration

| Source | Min | Max | Notes |
|--------|-----|-----|-------|
| Your implementation | 3 bars | 15 bars | ~0.6–3 weeks on daily |
| O'Neil | 1 week | 4 weeks | Weekly chart |
| Bulkowski | ≥ 1 week | No max (22-day median) | Short handles outperform |
| LuxAlgo | 1 week | 4 weeks | — |

Your 3–15 day range on daily bars (~0.6–3 weeks) is slightly shorter than O'Neil's 1–4 week recommendation. Consider expanding `handle_min_bars` to 5 to ensure at least 1 week of handle formation.

### Handle Volume

| Source | Rule |
|--------|------|
| Your implementation | Handle avg vol ≤ 85% of cup avg vol |
| DXP | Volume MUST be declining in handle |
| LuxAlgo | Lower volume than cup |
| Consensus | Handle volume must contract |

Your 85% threshold is consistent with research. ✓

### Handle Position (Upper Cup)

- O'Neil: Handle must be in upper 1/3 of cup
- Bulkowski: Upper half of cup
- Your check: `handle_high > max(left_lip, right_lip) × 1.01` → handle under the lips ✓
- DXP: If handle forms below midpoint → invalid

### Handle Slope

- Downward drift or flat → valid
- Rising handle → bearish (rising wedge within cup)
- Steep downward handle → aggressive selling
- Your implementation doesn't check slope — consider adding gentle slope constraint

---

## 12. Improving Filters

### Price / Liquidity Filters

| Filter | Your Setting | Research Consensus | Suggestion |
|--------|-------------|-------------------|------------|
| Min price | $20 | $15–20 | ✓ Good |
| Min avg volume | 2,000,000 | 200K–1M | ✓ Very high bar (good) |
| Exchanges | NASDAQ, NYSE, AMEX | Major US exchanges | ✓ |

### Relative Strength

O'Neil CAN SLIM requires RS rating ≥ 70 (ideally 90+). Your implementation currently has NO RS filter.

**Recommendation:** Add an RS rank filter. For each ticker, compute trailing 12-month return vs S&P 500. Rank all stocks in universe. Only accept cup-handle breakouts from stocks with RS > 50 (or 70).

### Earnings / Fundamental Filters

Your spec explicitly lists these as "out of scope (v0)". Research shows they add significant edge:
- O'Neil: EPS growth ≥ 18–25% YoY quarterly
- Minervini: EPS growing, 20%+ YoY
- CAN SLIM CAGR: 16% annually (AAII 1998–2026)

### Float / Institutional Ownership

- O'Neil: Winning stocks had median 4.6M shares outstanding
- 95% of winners had <25M shares
- Institutional sponsorship (accumulation days, 13F) improves success

### Sector Group Rank

Add sector rank filter (top 10 sectors by trailing RS):
- Only enter when ticker's sector is in top 10/40 GICS sectors
- Or: check sector ETF (XLK, XLF, etc.) > SMA50

### Multi-Timeframe Confirmation

| Approach | Description | Source |
|----------|-------------|--------|
| Weekly confirmation | Cup must show on weekly chart | O'Neil |
| Daily entry | Entry on daily chart after weekly confirmation | O'Neil |
| Nested pattern | 1H/4H cup inside daily handle | Q-Algo |
| Ichimoku filter | Price above Ichimoku Cloud | TradingSim |

---

## 13. Machine Learning / Quantitative Approaches

### SVM for Cup Detection (Fudan, 2023)

- Goal: Classify 60-day windows as cup-handle (1) or not (0)
- SVM + Gaussian RBF kernel
- R² = 0.7 (true labels) vs 0.2 (random labels)
- Limitation: 60-day window may miss longer patterns

### CNN for Pattern Recognition (2026 Tutorial)

- Classify 5 patterns: H&S, Double Top, Triangle, Bull Flag, Cup-and-Handle
- CNN with 3 Conv2D layers (32→64→128 filters)
- Input: 128×128 candlestick chart images
- Heuristic labeling approach for training data

### YOLO for Real-Time Pattern Detection

- Object detection on chart images
- Bounding boxes around cup-and-handle structures
- Confidence scores per pattern
- Used in swing trading automation platforms

### Quadratic Regression + Slope Analysis (Abiroid)

- Fit y = ax² + bx + c to normalized cup prices
- R² ≥ 0.75 → U-shape validated
- a ≥ 0 → cup opens upward (bullish)
- Peak shift ≤ 0.5 → centered trough
- Each side ≥ 25% of total width → symmetrical

### Feature Engineering for Cup Quality (MarketSmith)

Features that improve prediction:
- % of up bars during cup formation (buying pressure)
- % of up volume (institutional accumulation)
- Volume on breakout day
- Cup volatility (ATR or std dev) — lower = smoother base
- Prior uptrend strength (height & length of pre-cup rally)

### Net Distribution Metric (StockDataAnalytics)

In a rolling 20-bar window:
1. Find the top 5 days by volume
2. Count how many of those 5 were UP days (close > open or close > previous close)
3. If 3+ are up days → bullish accumulation
4. If 3+ are down days → distribution (bearish)

---

## 14. Known Failure Modes

| Failure Mode | Description | Frequency | Mitigation |
|-------------|-------------|-----------|------------|
| V-shaped cup | Sharp recovery without rounded base | Common | Require trough roundness (≥2 bars near low) |
| Handle too deep | Handle > 40% of cup depth | Common | Hard limit at 33% of cup depth |
| Low-volume breakout | Breakout without sufficient volume | Very common | Require 1.5×+ avg volume |
| Throwback (62%) | Price retests after breakout | **Very common (62%)** | Arm strategy; entry below handle high works |
| Sector headwind | Sector rolling over | Moderate | Sector ETF > SMA50 filter |
| Market correction | SPY drops 5%+ during formation | Occasional | Regime filter (SPY > SMA50) |
| Breakout below handle | Price never reaches handle high | Occasional | Prebreak arm avoids this |
| Handle too long | Handle exceeds 4 weeks | Occasional | Hard limit on handle duration |
| Multiple resistance touches | 5+ tests of same level | Diminishing returns | After 3 touches, skip |
| Earnings gap | Gap down on earnings after entry | Occasional | Avoid entry before earnings |
| Institution thesis change | Cup took 6+ months; fund moved on | Occasional | Limit cup max duration |

### StockDataAnalytics Finding

Patterns with 2 resistance touches → 55% beat rate
Patterns with 3–4 touches → 48% beat rate
Patterns with 5+ touches → 42% beat rate

**Each additional resistance touch degrades performance.** Don't assume repeated tests = stronger.

---

## 15. PineScript & TradingView Implementations

### Cup & Handle Finder [theUltimator5]

- Strict detection: uses ideal cup algorithm with upper/lower bounds
- User-defined margin of error
- Quadratic regression fit
- Failed handle labels (green for confirmed, red for rejected)
- Configurable: lookback range, breakout source, contained bar rate

### Abiroid Cup & Handle Indicator

- Quadratic regression for mathematical U-shape validation
- V-bottom rejection via concavity check
- Cup symmetry via parabola vertex position
- Handle quality: slope, depth (Fib), length validated
- Up to 3 nested cups
- Optional "require breakout" mode (pattern only shown after confirmed)

**Recommended settings:**
```
Price Type: PRICE_HIGH_LOW
Min Cup R²: 0.75
Min Cup Width: 15 bars
Max Cup Width: 200 bars
Trigger: Horizontal at P3
Require breakout: true
Overlap priority: Best Match (R²)
```

### PineScriptForge Cup-and-Handle (Futures)

**YM Futures (304 trades, Jan 2023 – Mar 2026)**
- Win Rate: **59.5%**
- Profit Factor: **2.68**
- Sharpe: **2.50**
- Max DD: **2.5%**
- Net Profit: +451.5% ($10K → $45K)

**PL Platinum (304 trades)**
- Win Rate: **59.5%**
- Profit Factor: **2.98**
- Sharpe: **2.50**
- Max DD: **2.1%**
- Net Profit: +727.8%

**RTY Russell 2000 (380 trades)**
- Win Rate: **45.5%**
- Profit Factor: **1.85**
- Sharpe: **1.77**
- Max DD: **8.6%**

**6A Aussie Dollar (304 trades)**
- Win Rate: **46.1%**
- Profit Factor: **1.06** (barely positive)
- Max DD: **39.8%**

**Key insight:** Cup-and-handle works excellently on index futures (YM, PL, NQ, ES) but poorly on FX (6A). Performance varies dramatically by instrument.

---

## 16. Backtest Performance Across Markets

### Summary Table

| Market/Strategy | Win Rate | PF | Sharpe | Max DD | Trades | Period |
|----------------|----------|----|--------|--------|--------|--------|
| YM Cup-Handle Futures | **59.5%** | 2.68 | 2.50 | 2.5% | 304 | 2023–2026 |
| PL Platinum Futures | **59.5%** | 2.98 | 2.50 | 2.1% | 304 | 2023–2026 |
| RTY Russell Futures | 45.5% | 1.85 | 1.77 | 8.6% | 380 | 2023–2026 |
| RC Coffee Futures | 43.6% | 1.29 | 1.46 | 15.0% | 342 | 2023–2026 |
| 6A AUD Futures | 46.1% | **1.06** | 0.44 | **39.8%** | 304 | 2023–2026 |
| ZB VCP Futures | **53.0%** | 1.45 | 1.91 | 9.8% | 266 | 2023–2026 |
| Sharpely VCP (India) | **59.5%** | — | 1.68 | — | 185 | 2023–2026 |
| Minervini NDX-100 | — | 1.84 | 0.39 | 24% | — | 5 years |
| CAN SLIM (AAII) | — | — | — | 47% | — | 1998–2026 |
| CAN SLIM (AAII 1999–2023) | — | — | 0.97 | 47% | — | 1999–2023 |

### Key Takeaways

1. **Best performers:** YM and PL futures (WR 59.5%, PF 2.68–2.98)
2. **Worst performers:** FX pairs (6A: PF 1.06, Max DD 39.8%)
3. **Equities in trending markets:** Sharpely VCP shows Sharpe 1.68
4. **Minervini on NDX-100:** Underperformed QQQ on return but lower DD (24% vs 36%)
5. **CAN SLIM long-term:** Beats S&P 500 (13.4% vs 7.3%) but with high DD (47%)

---

## 17. Position Sizing & Risk Management

### Professional Standards

| Rule | Standard | Source |
|------|----------|--------|
| Risk per trade | **1%** (0.5–2% range) | All professional sources |
| Portfolio heat | ≤6% total open risk | TradeAlgo |
| Max positions | 4–10 | Consensus |
| Sizing method | Fixed fractional (% risk) | Professional standard |
| Stop method | ATR-based + structural | Consensus |

### Position Size Formula

```
Shares = (Account × Risk%) / (Entry − Stop)
```

**Example:** $50K account, 1% risk ($500), entry $50, stop $47 ($3 risk per share)
→ **Shares = $500 / $3 = 166 shares** ($8,300 position, but only $500 risk)

### Volatility-Adjusted Sizing

```
Shares = (Account × Risk%) / (ATR × ATR_Multiplier)
```

- ATR multiplier: 1.5–3× for swing trading
- Higher volatility → smaller position
- Lower volatility → larger position (within fixed-fractional cap)

### R-Multiple Framework (Van Tharp)

- R = dollar amount risked per trade
- R-multiple = profit/loss ÷ R
- Expectancy = (Win% × AvgWin_R) − (Loss% × AvgLoss_R)
- A strategy with 40% win rate and 3:1 avg R:R → positive expectancy

### Regime-Adjusted Sizing

| Regime | Risk/Trade | Portfolio Heat |
|--------|-----------|----------------|
| Strong bull | 1–2% | ≤6% |
| Choppy / neutral | 0.5–1% | ≤4% |
| Bear / correction | 0–0.5% | ≤2% |
| High VIX (>25) | 0–0.25% | ≤2% |

---

## 18. Comparison to Current Implementation

### What's Already Well-Supported by Research ✓

| Feature | Your Setting | Research | Verdict |
|---------|-------------|----------|---------|
| Prebreak arm mode | Default | Covers 62% throwback rate | ✓ Excellent |
| SMA20/50/200 trend | Required | O'Neil Stage 2 | ✓ |
| Cup depth 12–35% | 12–35% | 12–35% sweet spot | ✓ Perfect |
| Lip tolerance 5% | 5% | 5% is fine | ✓ Good |
| Handle vol < cup vol | 85% threshold | Handle vol must decline | ✓ Good |
| ATR-based stop | 1.5× ATR | 1.5–2× is consensus | ✓ Good |
| Dual targets | 50% / 80% of cup | Similar to Fib targets | ✓ Good |
| Price/volume filters | $20 / 2M vol | Conservative | ✓ Good |

### What Could Be Improved 🔧

| Area | Current | Suggested | Rationale |
|------|---------|-----------|-----------|
| `breakout_vol_mult` | **1.3** | **1.5** | Research consensus: 1.4–2.0×. OGA shows monotonic improvement |
| `handle_depth_max_frac` | **0.40** | **0.33** | O'Neil: handle ≤ 1/3 cup depth. DXP: 12–15% of cup height |
| `handle_min_bars` | **3** | **5** | O'Neil: 1 week minimum handle. 3 bars = 0.6 weeks |
| SPY regime filter | **Off by default** | **On by default** | 90.77% success when indices above 200d MA |
| RS rank filter | **Not implemented** | **Add RS > 50–70** | O'Neil CAN SLIM requirement |
| Sector filter | **Not implemented** | **Add sector ETF > SMA50** | Moskowitz: 60–73% of momentum from sector |
| Cup shape quantification | Near-trough bars | Quadratic regression | R² check prevents V-shaped cups |
| Handle slope check | Not implemented | Gentle downward drift | Rising handle = bearish; steep = aggressive selling |
| Net Distribution signal | Not implemented | Top-5 volume day analysis | Better signal than raw RVOL |
| Cup min_bars | **20** | **30–35** | ~6 weeks minimum for reliable cup |
| Earnings/fundamental filter | Out of scope (v0) | Consider CAN SLIM EPS | Adds significant edge per AAII data |

### Highest-Impact Improvements (Ranked)

1. **SPY/Sector regime filter (ON by default)** — 90.77% success rate change
2. **Breakout volume mult 1.3 → 1.5** — OGA monotonic alpha improvement
3. **Handle depth max 0.40 → 0.33** — O'Neil's 1/3 rule
4. **Add RS rank filter** — O'Neil CAN SLIM requirement
5. **Cup shape quantification** — Quadratic regression to reject V-shaped cups
6. **Handle min bars 3 → 5** — One week minimum handle

---

## Sources

1. Bulkowski, T. — Encyclopedia of Chart Patterns (3rd ed.), thepatternsite.com/cup.html
2. O'Neil, W. — How to Make Money in Stocks (4th ed., 2009)
3. O'Neil Global Advisors — "Breakouts: Pump up the Volume" (2022), 197K events
4. FinermarketPoints — Sector & VCP Research, VCP Complete Guide
5. DXP Analytics — Cup and Handle Pattern: The O'Neil Breakout System
6. PineScriptForge — Cup and Handle Backtests: YM, PL, RTY, 6A, RC, ZB
7. Sharpely — VCP Backtest (India stocks), 185 trades
8. EasySwing.trading — VCP/cup research, Performance page
9. StockDataAnalytics — 370,000 Chart Patterns Analysis
10. LuxAlgo — Cup and Handle Pattern Success Rates & Common Errors
11. TradingSim — Cup and Handle 3 Strategies
12. Quantum-Algo — Cup and Handle Complete Guide
13. TradeAlgo — Swing Trading Risk Management
14. ChartGuys — Cup and Handle Trading Guide
15. The5ers — How to Avoid Fake Cup and Handle
16. FinancialWisdomTV — VCP Top 100 Study
17. Lutey & Mukherjee (2023) — Towards a Simplified CAN SLIM Model
18. AAII — CAN SLIM: Seven Attributes (1998–2026)
19. Fudan (2023) — Research on Cup and Handle Based on SVM
20. BreakoutDB — VCP Pattern Statistics
21. Abiroid — Cup & Handle Indicator (quadratic regression approach)
22. Investopedia — Cup and Handle Pattern
23. tastytrade — How to Trade the Cup and Handle
24. IndicatorHub — Cup and Handle Pattern Guide
# YouTube Research: Cup-and-Handle Pattern

> 184 video transcripts from 25 search queries, 2,635,094 total chars.
> Last updated: 2026-07-16

---

## Search Queries Executed

| # | Query | Results |
|---|-------|---------|
| 1-5 | cup and handle pattern strategy backtest, swing trading rules, O'Neil explained, VCP Minervini backtest, breakout entry strategy | Original batch |
| 6-10 | cup pattern stock performance, stop loss profit target, scan setup TradingView, best filters win rate, quantitative analysis | Original batch |
| 11 | cup and handle trading strategy stock market | Batch 2 |
| 12 | William O'Neil cup handle breakout | Batch 2 |
| 13 | cup handle pattern stocks backtest performance | Batch 2 |
| 14 | swing trading cup handle base breakout | Batch 2 |
| 15 | cup and handle scanner screener | Batch 2 |
| 16 | best cup handle setups 2024 2025 2026 | Batch 2 |
| 17 | cup handle pattern entry stop target rules | Batch 2 |
| 18 | how to trade cup handle pattern stocks | Batch 2 |
| 19 | cup with handle trading strategy backtested | Batch 2 |
| 20 | cup handle pattern win rate statistics | Batch 2 |
| 21 | rounded bottom cup handle trading | Batch 2 |
| 22 | technical analysis cup pattern | Batch 2 |
| 23 | cup handle fail fake breakout avoid | Batch 2 |
| 24 | stage 2 uptrend cup base breakout | Batch 2 |
| 25 | institutional accumulation cup pattern | Batch 2 |
| 26 | cup handle pattern python detection | Batch 2 |
| 27 | trader cup handle daily chart swing | Batch 2 |
| 28 | cup handle example stock analysis | Batch 2 |
| 29 | O'Neil base types cup flat double bottom | Batch 2 |
| 30 | cup handle relative strength volume breakout | Batch 2 |

---

## Top Relevant Videos (by views, sorted)

### Tier 1: 100K+ Views

| Views | Title | Key Content |
|-------|-------|-------------|
| 1,014,470 | I made a Market Simulation to see if Patterns are Real (Krafer) | Cup-and-handle showed statistically significant edge with volume confirmation; shape alone insufficient |
| 434,854 | My 2 Swing Trading Strategies which helped me DOUBLE my Portfolio in 6 Months | 89,226 chars — detailed swing trading walkthrough with specific setups |
| 205,059 | 2 Swing Trading Strategies & the Right Mindset | Swing trading framework, regime awareness |
| 188,744 | Trading the Cup and Handle - Stock Chart Pattern | Direct cup-handle trade walkthrough |
| 181,682 | The Best Chart Patterns To Trade (Reliability Study) | Pattern reliability comparison |
| 174,288 | EXPERT Cup And Handle Chart Pattern Trading Strategy (For Pros Only) — Wysetrade | 13,648 chars — detailed entry/stop/target rules |
| 172,383 | Reading Charts with William O'Neil | Direct O'Neil methodology |
| 170,672 | WILLIAM O'NEIL - How to Make Money in Stocks - Cup and Handle — Financial Wisdom | 12,326 chars — O'Neil's original cup-handle rules |
| 162,888 | Mark Minervini explains his ANF trade | 6,055 chars — direct Minervini trade analysis |
| 148,626 | Why Most Breakouts Fail | Real Reason Behind Chart Pattern Traps | 42,726 chars — failure analysis, false breakout avoidance |
| 136,079 | FALSE BREAKOUT in PRICE ACTION Trading (3 RULES That WORK) | 14,721 chars — false breakout rules |
| 125,128 | Backtest 100+ TRADING Strategy for FREE | 41,182 chars — backtest methodology |
| 122,452 | cup and handle EXPLAINED | 11,269 chars — cup-handle explanation |
| 121,535 | Chart Patterns Free Course | 54,457 chars — comprehensive course |
| 103,678 | +50% in 20 Days - How to Trade Breakouts with VCP — TraderLion | 12,004 chars — VCP breakout strategy |

### Tier 2: 10K-100K Views

| Views | Title | Key Content |
|-------|-------|-------------|
| 87,398 | CUP & HANDLE Chart Pattern — Big Profit Trading Strategy | 6,873 chars |
| 84,135 | Profitable Trading Strategy: Master VCP (Minervini) | 8,509 chars |
| 82,700 | 3 Must-Know Algorithms for Automating Chart Pattern Trading in Python — neurotrader | 10,377 chars — Python DTW + peak detection |
| 61,525 | Cup With Handle Pattern - Common Mistake | 7,706 chars |
| 48,672 | Cup and Handle Pattern: Day Trading Strategy for Beginners | 4,879 chars |
| 36,734 | Automatically Detect Cup and Handle Patterns: New Feature | 6,582 chars |
| 33,877 | Chart Patterns: Cup With Handle — Investor's Business Daily (Official) | 6,762 chars |
| 23,247 | I Studied the Top 100 Stocks... The Results Shocked Me (VCP Pattern) | 8,071 chars |
| 19,273 | ADVANCED Cup and Handle Chart Pattern Trading Strategy — Asia Forex Mentor | 12,537 chars |
| 9,764 | The Pattern Behind the Market's Biggest Winners — Financial Wisdom | 8,411 chars |

---

## Key Statistical Findings from YouTube Research

### 1. Financial Wisdom — Top 100 Stocks VCP Study
- 36 of 100 top performers had clean VCPs
- Avg risk: 6%, avg return: 69%, avg R:R: 11:1
- Best examples: SNDK (46× R:R), MRVL (56× R:R), DELL (21× R:R)

### 2. Krafer — Market Simulation (1M views)
- Cup-and-handle one of few patterns with statistically significant edge
- **The edge comes from volume confirmation, not the shape alone**
- Patterns without volume confirmation: no edge over random

### 3. IBD Official — Cup With Handle
- Cup depth: 15-30%
- Handle: downward drift on declining volume
- Buy point: handle high + $0.10
- Volume requirement: 40-50% above avg on breakout

### 4. Wysetrade — EXPERT Cup and Handle Strategy
- Multi-timeframe approach for higher probability
- Uses Fibonacci retracement levels to validate handle depth
- Handle should retrace 0.382-0.5 of cup depth
- Breakout must close above, not just intraday wick

### 5. Asia Forex Mentor — ADVANCED Cup and Handle
- 80% of profitable cup-handle trades happen when overall market is in uptrend
- Handle must NOT go below 50% of cup depth
- Cup depth sweet spot: 20-30%

### 6. neurotrader — Python Algorithm
- Uses scipy.signal.find_peaks for price extremum detection
- Dynamic Time Warping (DTW) for pattern matching
- Cup-and-handle shows above-chance predictive power in US equities

### 7. False Breakout Analysis (multiple videos)
- Main causes of false breakouts:
  - Low volume breakout (most common)
  - Handle too deep
  - Market context wrong (bear market)
  - Breakout that closes back inside handle same day
- Solution: Wait for close above handle high on 1.5×+ volume

---

## All Transcripts

Available at `/Users/shtylenko/Projects/trading/library/cup_handle/yt_*.txt`

184 transcript files, 2,635,094 total characters. To search:

```bash
cd /Users/shtylenko/Projects/trading/library/cup_handle
grep -l -i "win rate\|stop loss\|breakout\|VCP\|O'Neil" yt_*.txt | head -20
```
