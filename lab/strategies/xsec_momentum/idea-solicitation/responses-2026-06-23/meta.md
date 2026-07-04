This is exactly the right problem to work on — your residual IR is already the cleanest version of long-only momentum you can run on liquid US names, and Section 7 shows why almost everything else collapses into "high-beta with extra steps."

Here are 10 ideas that stay inside your constraints (long-only, monthly, liquid, daily bars + SPY + point-in-time fundamentals), change the *ranking* not the timing, and are structurally different from what you killed.

### 1. Split-Half Residual Persistence
**Mechanism / thesis:** Momentum crashes are driven by winners that had one big residual jump early in the formation window then went flat. Compute IR over the first 126 days and the second 126 days (both skipping the last 21). Rank by `min(IR1, IR2)`, not the full-window IR. You are selecting stocks with *steady* idiosyncratic drift, not a single news spike.

**Closest dead-end it avoids:** Path quality / frog-in-pan. That used smoothness of raw returns; this uses persistence of the *residual* signal across two independent halves.

**Why it survives failure modes:** Still 100% residual-based, so no new beta load. It is a ranking filter, not a timing overlay.

**How to test:** Replace your score with min(IR1, IR2). Keep top 35, same rebalance. Data needed: daily bars + SPY only. Decisive metric: max drawdown and return in the 5 worst momentum-crash months (Mar-Apr 2009, Nov 2020, Jan 2021, etc.).

**What would kill it:** Correlation >0.97 to baseline and no reduction in those crash months.

### 2. Beta-Stability Filter
**Mechanism:** Your residual beta is still 1.08 because beta is not constant. Stocks where 63-day rolling beta wanders a lot during formation have contaminated residuals that leak market exposure. Filter them out.

**Closest dead-end:** FF3/size residual. You added factors; this adds *measurement quality*.

**Why it survives:** You are not adding a new factor, you are cleaning the CAPM residual you already use. Stable-beta names in the liquid universe are not a beta tilt.

**How to test:** Within top 70 by IR, compute std(beta_63d) over the 252d window. Drop the top 20% most unstable, then take top 35 by IR. Data: daily bars + SPY.

**What would kill it:** Portfolio beta stays 1.08 and drawdown unchanged.

### 3. Net Share Issuance Purge
**Mechanism:** In large caps, recent heavy issuance predicts reversal independent of momentum. Residual winners that just raised equity are the classic "momentum crash" fuel.

**Closest dead-end:** Value (book-to-market). That is a valuation level; this is a corporate action.

**Why it survives:** Issuance is weakly correlated with beta in your liquid universe, and you apply it *after* residual ranking, so you do not create a new standalone factor.

**How to test:** From point-in-time shares outstanding, compute 12m % change. Within top 70 IR, exclude >5% issuers, keep top 35. Data: fundamentals (shares outstanding).

**What would kill it:** Filter removes <10% of names or Sharpe delta <0.03.

### 4. Residual Skew Penalty
**Mechanism:** Positive skew in ε means the IR is driven by a few lottery up-days. Those names revert hardest in crashes. Penalize skew.

**Closest dead-end:** Risk-adjusted momentum (return/vol). That uses second moment; this uses third.

**Why it survives:** Skew of market-adjusted residuals is essentially beta-neutral in large caps.

**How to test:** Score = IR - 0.5 * skew(ε). Rank top 35. Data: daily bars + SPY.

**What would kill it:** No improvement in downside deviation.

### 5. Idiosyncratic Vol Compression
**Mechanism:** You want residual drift *with falling uncertainty*. Compute std(ε) first half vs second half. Require ratio <0.9.

**Closest dead-end:** Risk-adjusted momentum. That ranks by low vol level; this ranks by vol *trend*.

**Why it survives:** Still residual-based, no market timing.

**How to test:** Within top 70 IR, keep names with vol compression, take top 35. Data: daily bars + SPY.

**What would kill it:** Turnover jumps >30% or Sharpe falls.

### 6. Earnings-Jump Purity
**Mechanism:** Residual IR inflated by earnings-day jumps mean-reverts faster than IR earned in the other ~240 days. Keep drift that is broad-based.

**Closest dead-end:** Earnings momentum (TTM net-income YoY). That uses earnings *level*; this uses return attribution around filings.

**Why it survives:** It does not introduce a value or quality tilt, just cleans the momentum signal.

**How to test:** Using point-in-time filing dates, compute fraction of cumulative ε earned in [-1,+1] day windows around earnings. Keep <30%. Data: fundamentals with filing dates + daily bars.

**What would kill it:** Filter is too tight (<5% of universe passes) or no crash improvement.

### 7. Accruals Quality Screen
**Mechanism:** High accruals = low-quality earnings = junk rallies that die in reversals. This is different from profitability level.

**Closest dead-end:** Quality / GP/Assets. That is a level; accruals is a *quality-of-earnings* measure.

**Why it survives:** In liquid large caps, low accruals is not a high-beta growth tilt (it actually leans slightly defensive).

**How to test:** Compute Sloan accruals from point-in-time quarterly balance sheet and cash flow: (ΔCA - ΔCash - ΔCL + ΔSTD - Dep)/AvgAssets. Within top 70 IR, keep bottom 40% accruals, take top 35. Data: fundamentals.

**What would kill it:** No change in alpha in 2009 or 2020-22.

### 8. Residual Autocorrelation Filter
**Mechanism:** Mild positive AR(1) in ε indicates slow information diffusion; negative AR(1) indicates noise.

**Closest dead-end:** Path quality. That looked at jumps; this looks at serial dependence.

**Why it survives:** Autocorrelation of residuals is orthogonal to market beta by construction.

**How to test:** Keep stocks with 0.05 < rho1(ε) < 0.30 within top 70 IR. Data: daily bars + SPY.

**What would kill it:** Correlation with baseline >0.99.

### 9. Residual Maximum Drawdown Penalty
**Mechanism:** A large interim drawdown in the cumulative residual curve signals fragility even if final IR is high.

**Closest dead-end:** Path quality again, but this is a specific drawdown metric on residuals, not raw returns.

**Why it survives:** Penalizes path risk without changing the factor.

**How to test:** Score = IR / (1 + MDD_cumε). Rank top 35. Data: daily bars + SPY.

**What would kill it:** No reduction in portfolio MDD.

### 10. Operating Margin Expansion Confirmation
**Mechanism:** Residual price momentum backed by improving gross margin is less speculative. You tried net-income YoY; margin expansion is different because it scales by sales and captures unit economics.

**Closest dead-end:** Earnings momentum. This uses Δ(gross profit / revenue), not Δ net income.

**Why it survives:** Applied as a secondary filter within residual winners, it does not become a standalone growth tilt.

**How to test:** Compute YoY change in gross margin from point-in-time quarters. Within top 70 IR, keep top 50% by margin Δ, then take top 35 by IR. Data: fundamentals.

**What would kill it:** Portfolio ends up with higher beta (>1.15) or sector concentration in tech.

---

## Summary table

| Idea | Mechanism class | Data needed | Cheap to test? | Conviction (H/M/L) | Closest dead-end avoided |
|---|---|---|---|---|---|
| Split-Half Residual Persistence | Residual consistency | Daily bars + SPY | Yes | H | Path quality / frog-in-pan |
| Beta-Stability Filter | Measurement cleaning | Daily bars + SPY | Yes | H | FF3/size residual |
| Net Share Issuance Purge | Corporate action filter | Fundamentals (shares out) | Yes | H | Value (book-to-market) |
| Residual Skew Penalty | Higher moment filter | Daily bars + SPY | Yes | M | Risk-adjusted momentum |
| Idiosyncratic Vol Compression | Vol trend filter | Daily bars + SPY | Yes | M | Risk-adjusted momentum |
| Earnings-Jump Purity | Event attribution | Fundamentals filing dates + daily | Medium | M | Earnings momentum |
| Accruals Quality Screen | Earnings quality | Fundamentals (BS/CF) | Medium | M | Quality / GP/Assets |
| Residual Autocorrelation Filter | Serial dependence | Daily bars + SPY | Yes | L | Path quality |
| Residual Max Drawdown Penalty | Path risk | Daily bars + SPY | Yes | L | Path quality |
| Operating Margin Expansion | Fundamental confirmation | Fundamentals (revenue, COGS) | Medium | L | Earnings momentum |

My honest base rate: none of these is likely to give you +0.3 Sharpe. The three H-conviction ideas are the only ones with a plausible mechanism to shave 3 to 5 points off max drawdown while keeping return, which is the win you defined in Section 4b. Start with 1, 2, and 3 — they are cheap, use data you have, and directly address why residual momentum still crashes.