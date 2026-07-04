# Strategy Overview — x03, Residual (Idiosyncratic) Momentum

*A from-scratch description for external review. Assumes finance literacy but no prior
knowledge of this system. Last updated 2026-06-21.*

---

## 1. One-paragraph summary

x03 is a **long-only, monthly-rebalanced US equity momentum strategy**. Once a month it
ranks a liquid universe of stocks by their **market-adjusted ("idiosyncratic") momentum**
over the past ~11 months, buys the **top 50 equal-weight**, holds for ~one month, and
repeats. The novel part is *what* it ranks on: instead of raw past return (which quietly
becomes a leveraged bet on the overall market), it ranks on the portion of each stock's
return that is **specific to the stock** after stripping out its co-movement with the
market (the S&P 500). The goal is the same well-documented momentum premium, but
engineered to carry less market risk and shallower drawdowns.

---

## 2. The intuition (plain English)

**Momentum** is one of the most robust, widely-replicated anomalies in finance: stocks
that have outperformed over the past 6–12 months tend to keep outperforming over the next
month or so. A naive way to harvest it is "buy the biggest winners." The problem: in a
rising market the biggest winners are often just the **highest-beta** names — they went up
the most because the market went up and they amplify the market. So a plain momentum book
secretly becomes "be extra-long the market," which feels great until the market turns and
that leverage works against you (momentum's notorious crashes, e.g. 2009, are largely
this).

**Residual momentum** fixes the diagnosis. For each stock we ask: *after removing the part
of its return that's just the market moving, how strong and how steady is the leftover,
stock-specific drift?* We rank on **that**. This keeps the genuine "winners keep winning"
signal while shedding the accidental market-leverage. The result (in testing) is similar
returns with **lower market beta and smaller drawdowns** — a better risk-adjusted version
of the same edge, not a different edge.

---

## 3. The investable universe (eligibility gates)

Before ranking, a stock must clear three feasibility filters on the rebalance date. These
are not predictive signals — they just keep the book tradable and the math valid:

| Gate | Threshold | Purpose |
|---|---|---|
| Price | last close **≥ $5** | exclude penny stocks |
| Liquidity | 20-day average **dollar volume ≥ $10M** (avg of close × volume) | must be enterable/exitable at size |
| History | **≥ 273** aligned daily returns | enough data for the lookback; excludes recent IPOs |

Anything failing a gate is dropped from consideration that month.

---

## 4. The selection signal (the one ranking indicator)

Every eligible stock gets a single score. Higher = more attractive. It is computed as
follows, using **daily, split-adjusted** prices.

**Step 1 — Define the formation window.** Look back **252 trading days (~12 months)** but
**skip the most recent 21 trading days (~1 month)**. This "skip-month" is standard in
momentum research: the most recent month tends to *reverse* (short-term mean reversion), so
including it adds noise. So the window is days `[d−252, d−21]` relative to the rebalance
date `d`.

**Step 2 — Strip out the market.** Over that window, regress the stock's daily returns on
the S&P 500's daily returns (a one-factor CAPM regression):

```
r_stock(t)  =  α  +  β · r_SPY(t)  +  ε(t)
```

- `β` (beta) = how much the stock moves with the market.
- `ε(t)` = the **residual** — the daily return that is *not* explained by the market. This
  is the stock-specific ("idiosyncratic") return.

**Step 3 — Score = the residual information ratio:**

```
score  =  mean(ε)  /  std(ε)
```

The numerator is the *average* idiosyncratic drift over the window (is the stock-specific
part trending up?); the denominator is the *volatility* of that idiosyncratic part
(scaling by it rewards **steady** drift over **lucky/jumpy** drift). A high score means
strong, consistent stock-specific momentum — independent of how much the stock simply rode
the market.

**Step 4 — Rank and select.** Rank all eligible stocks by score, descending. Take the
**top 50**.

> In the live UI, the **"Score" column is exactly this number** (`mean(ε)/std(ε)`), and
> "Rank" is its position in that ordering. Sector/industry is **never an input** — any
> sector concentration you see is an emergent by-product of where idiosyncratic momentum
> happened to be strongest that month.

---

## 5. Portfolio construction

| Parameter | Value |
|---|---|
| Direction | **Long only** (no shorting) |
| Holdings | **Top 50** names |
| Weighting | **Equal weight** (~2% each) |
| Rebalance cadence | every **20 trading days** (~monthly) |
| Hold period | **20 trading days** per entry |
| Entry | at the **rebalance close** |
| Exit | **pure time exit** at the end of the hold — *no profit target, no stop-loss* |
| Lookback data needed | ~420 calendar days of daily bars per name + SPY |

Two deliberate design choices worth flagging to a reviewer:

- **No stop-loss / no profit target.** The validated edge is a *time-based* rebalance, not
  a price-triggered one. Adding stops would change the strategy into something that wasn't
  tested. (Risk is managed at the portfolio level — equal weight, 50 names, monthly turnover
  — not per-trade.)
- **Equal weight, not score-weight.** Simpler, more robust, avoids over-betting the
  single highest-scoring name on a noisy point estimate.

---

## 6. Why residual momentum instead of plain momentum

This strategy is the successor to a plain "12-month-minus-1-month total return" momentum
book (internally, "x01"). The motivation for the change, from in-sample testing on
2017–2024:

| Metric | Plain momentum (x01) | Residual momentum (x03) |
|---|---|---|
| Book beta to market | ~1.45 (a leveraged market bet) | ~1.08 |
| Max drawdown | ~ −36% | ~ −23% |
| Sharpe ratio | ~0.81 | ~0.89 |

Same family of returns, materially less market risk and a shallower worst-case. The honest
framing: **x03 is better-engineered momentum, not a new source of alpha.** Its
market-orthogonal alpha is still modest and not strongly statistically significant — the
win is *risk reduction*, not extra return.

---

## 7. Evidence & validation status (read this carefully)

We separate "the momentum family is real" from "this specific variant is independently
proven," because they have different strengths of evidence.

**The momentum family** (plain 12-1) is the most thoroughly validated edge the research
program has produced: it passed an in-sample multi-year walk-forward, survived
overfitting/robustness checks, and **passed a pre-registered out-of-sample (OOS) test on a
held-out year (2025)** plus an independent re-implementation cross-check. Realistic
magnitude is **modest — annualized Sharpe ~1.0** — with intrinsic momentum crash risk.

**x03 specifically** is the **residual, risk-improved variant** of that family. It was
**pre-registered** and tested in-sample over 8 years (2017–2024), where it cleanly beat
plain momentum on beta and drawdown (table above) with strong in-sample selection
statistics. **Caveat:** the available clean OOS years have already been "spent" validating
the family, so x03 has *not yet* had its own untouched sealed-OOS confirmation — a fresh
holdout year (~2027) is the next true test. Treat x03 today as *"a validated family + a
pre-registered, in-sample-confirmed risk improvement on it,"* not *"independently
sealed-OOS on its own."*

**The number that matters for expectations:** this is a **modest, real, long-horizon
equity premium (~1.0 Sharpe, long-only)** — not a high-octane strategy. Its value is steady
risk-adjusted participation plus lower drawdown than naive momentum.

---

## 8. Key risks & limitations

- **Single-factor (CAPM) only.** We strip out the *market* but not size/value/sector. Some
  of what we label "idiosyncratic" may still be a small-cap or style tilt. A multi-factor
  (e.g. Fama-French 3-factor) residual is a candidate future version.
- **Highly correlated with plain momentum (~0.95).** It is a refinement of momentum, so it
  shares momentum's regimes — including **momentum crash risk** (sharp losses when prior
  losers violently rebound, e.g. early 2009, parts of 2021–22).
- **Long-only.** No ability to profit from or hedge the short side; full market exposure in
  a downturn (beta ~1.08).
- **Survivorship caveat pre-2022.** The longest backtests are partly survivorship-lifted in
  earlier years; the cleanest data is recent.
- **OOS not yet independently sealed for x03** (see §7).
- **Capacity / liquidity.** A 50-name equal-weight book needs enough capital that each ~2%
  slice clears the liquidity of the names; sizing must respect that.

---

## 9. What this strategy explicitly does NOT do

- It does **not** time the market or rotate to cash/bonds in downturns (a defensive overlay
  was tested and *hurt* risk-adjusted returns — it deploys best standalone).
- It does **not** use chart patterns, technical indicators, fundamentals, news, or
  sentiment. The sole signal is residual price momentum.
- It does **not** short, use leverage, or use options.
- It does **not** apply per-trade stops or targets.

---

## 10. Glossary

- **Momentum:** the tendency of past winners (6–12 mo) to keep outperforming short-term.
- **Beta (β):** sensitivity of a stock's return to the market's return (β=1 moves with the
  market; β=1.4 amplifies it).
- **Residual / idiosyncratic return (ε):** the part of a stock's return left after removing
  the market component — what's specific to that company.
- **CAPM regression:** the one-factor regression of a stock's returns on the market's,
  whose slope is β and whose leftover is ε.
- **Information ratio (here):** mean residual ÷ standard deviation of residual — drift per
  unit of idiosyncratic risk.
- **Skip-month:** excluding the most recent ~21 days from the lookback to avoid short-term
  reversal contaminating the momentum signal.
- **Walk-forward / OOS / sealed test:** validation methods that test on data not used to
  design the strategy; a "sealed" OOS year is one never looked at during development — the
  strongest evidence a backtest can offer.
- **Sharpe ratio:** return per unit of volatility; ~1.0 is a solid, realistic figure for a
  long-only equity strategy.
