I’m treating the uploaded brief as the full spec: current incumbent is **top-35 CAPM residual information-ratio momentum**, and the kill list rules out most generic factor, sizing, timing, stop, hedge, and diversifier ideas. 

My bias: **do not search for “another factor.”** You already learned that generic long-only factors collapse into beta. The better research direction is: keep residual momentum, but make the selected winners less exposed to **hidden beta, hidden sector/theme crowding, stale momentum, crash-state reversal, and accounting/event-quality traps.**

## 1. Down-market residual strength

**Idea:** Rank residual momentum using only **SPY-down days** or heavily penalize names whose residual alpha disappears on market-down days.

**Mechanism / thesis:** A lot of “residual” momentum can still be disguised bull-market participation. If a stock’s residual drift is positive even when SPY is down, that is stronger evidence of true stock-specific sponsorship. This directly targets your main issue: the book still has β≈1.08 and behaves a lot like plain momentum.

**Closest dead-end it avoids:** Defensive market timing / 200-day overlays. This is not timing the market or moving to cash; it is a **cross-sectional ranking change** while staying fully long.

**Why it survives your failure modes:** It should not become a high-beta tilt, because the signal is measured when beta is least helpful. It also avoids fragile overlays because exposure stays 1.0× and the rebalance/hold structure stays unchanged.

**How to test it:**
At each rebalance, compute CAPM residuals as usual over the 252-day window skipping 21 days. Then compute:

```text
down_day_residual_IR = mean(ε | SPY_return < 0) / std(ε | SPY_return < 0)
```

Test either:

```text
score = 0.7 * baseline_residual_IR + 0.3 * down_day_residual_IR
```

or simpler: rank by baseline residual IR, then exclude the worst quintile by down-day residual IR.

**Decisive metric:** Same CAGR or slightly lower CAGR, but materially lower max drawdown and lower beta, with Sharpe improvement in walk-forward.

**What would kill it:** If drawdown only improves because returns collapse, or if the selected book still has similar crash behavior in 2009 / 2020 / 2021–22-style momentum reversals.

---

## 2. Momentum-crash beta filter

**Idea:** Estimate each candidate’s sensitivity to a **momentum-crash proxy** and avoid names that lose when prior losers violently rebound.

**Mechanism / thesis:** Your biggest unresolved risk is not normal volatility; it is momentum crash. Build a daily “loser rebound” factor from your own universe:

```text
crash_factor = return_of_prior_loser_decile - return_of_prior_winner_decile
```

When this factor is strongly positive, the classic momentum trade is getting hurt. For each candidate, regress its residual returns on this crash factor. Prefer residual winners that have less negative exposure to that state.

**Closest dead-end it avoids:** VIX/tail-trigger de-risking. This does not use a market-level trigger or exit rule. It measures **cross-sectional crash fragility** before selection.

**Why it survives your failure modes:** It is not another long-only factor like value or quality. It is a diagnostic of whether a residual winner is secretly just a crowded momentum-crash candidate. It also does not change sizing, leverage, stops, or exits.

**How to test it:**
Monthly, using only the formation window:

1. Form prior momentum winner/loser deciles from eligible stocks.
2. Compute daily crash factor: loser decile return minus winner decile return.
3. Regress each stock’s CAPM residuals on this factor.
4. Penalize candidates with bad crash exposure:

```text
score = baseline_residual_IR + λ * crash_beta
```

where positive crash_beta is good if the crash factor is defined as loser-minus-winner.

Use a very coarse λ or simply exclude the worst quintile by crash sensitivity.

**Decisive metric:** Improvement in max drawdown and worst 3-month return, without major Sharpe decay.

**What would kill it:** If the filter mostly removes the highest-return names and does not improve the specific momentum-crash windows.

---

## 3. Cross-sectionally “purified” residual momentum

**Idea:** Rank by the part of residual momentum that is **not explained by raw momentum, beta, volatility, and liquidity/size proxies**.

**Mechanism / thesis:** You said residual momentum is still ~0.95 correlated with plain momentum. That means the current score may still be mostly “better-shaped raw momentum.” Instead of changing the time-series residual regression, do a second step cross-sectionally:

```text
residual_IR_i = a + b1*raw_12_1_mom_i + b2*beta_i + b3*vol_i + b4*log_ADV_i + u_i
```

Then rank by `u_i`, optionally requiring baseline residual IR to be positive.

This asks: “Which stocks have unusually strong residual momentum **given their raw momentum and risk profile**?”

**Closest dead-end it avoids:** FF3 / size residual momentum. That was time-series factor residualization of returns. This is different: it is **cross-sectional de-biasing of the score**.

**Why it survives your failure modes:** It directly attacks the “new signal becomes beta tilt” problem by removing the part of the signal mechanically associated with beta/raw momentum. It is not timing, sizing, or exiting.

**How to test it:**
At each rebalance:

1. Compute baseline residual IR.
2. Compute raw 12-1 return, CAPM beta, residual volatility, total volatility, log dollar volume.
3. Run robust cross-sectional regression.
4. Rank by the residual `u_i`.
5. Buy top 35, equal-weight, same hold.

Test two versions:

```text
A: rank all eligible stocks by u_i
B: first require baseline residual_IR > universe median, then rank by u_i
```

**Decisive metric:** Lower correlation to plain momentum while maintaining Sharpe near or above baseline.

**What would kill it:** If return collapses. That would mean the “alpha” was mostly the raw momentum component you stripped out.

---

## 4. Residual-correlation de-crowding

**Idea:** Select high-scoring names while limiting exposure to the same hidden residual cluster.

**Mechanism / thesis:** Equal-weighting 35 names does not guarantee diversification. If the top residual names are all AI-semiconductors, energy squeezes, biotech themes, or rate-sensitive cyclicals, the book is really one hidden bet. CAPM residualization removes SPY, not shared non-market themes.

**Closest dead-end it avoids:** Concentration sweep / top-N testing. This is not “15 vs 35 vs 50 names.” It changes **which 35** by avoiding correlated residual clusters.

**Why it survives your failure modes:** It is still selection, not timing/sizing. It does not chase low-vol or defensive names mechanically; it only prevents one hidden residual theme from dominating.

**How to test it:**
For the top 100 residual momentum candidates:

1. Compute residual-return correlation matrix over the formation window.
2. Cluster names using simple hierarchical clustering or correlation thresholding.
3. Select top names greedily by score, but cap each cluster at, say, 20–25% of the book.
4. Keep 35 names, equal-weight.

Avoid overfitting the cluster cap. Test only a few coarse caps: none, 25%, 20%, 15%.

**Decisive metric:** Same or slightly lower return, but lower drawdown and lower worst-month loss.

**What would kill it:** If it just diversifies away the edge and Sharpe falls, especially if drawdown does not improve.

---

## 5. Beta-instability and downside-beta penalty

**Idea:** Penalize residual winners whose CAPM beta is unstable or whose downside beta is much higher than upside beta.

**Mechanism / thesis:** Your whole signal depends on the regression residual being meaningful. If a stock’s beta is unstable, then the residual may be polluted by unmodeled market exposure. A stock can look like it has stock-specific residual momentum simply because the single beta estimate is stale or too low.

**Closest dead-end it avoids:** Static beta hedge and FF3 residualization. This does not hedge beta or add noisy factors. It asks whether the **single-factor residual estimate is trustworthy** for each stock.

**Why it survives your failure modes:** It targets beta leakage inside the signal, not portfolio-level timing. It should reduce high-beta false positives without forcing the whole book defensive.

**How to test it:**
For each stock in the formation window:

```text
beta_full = CAPM beta over 252 days
beta_first_half = beta over first 126 days
beta_second_half = beta over second 126 days
beta_instability = abs(beta_second_half - beta_first_half)

beta_down = beta on SPY-down days
beta_up = beta on SPY-up days
downside_beta_gap = beta_down - beta_up
```

Test:

```text
score = baseline_residual_IR - penalty(beta_instability) - penalty(max(0, downside_beta_gap))
```

or simpler: exclude the worst quintile by beta instability/downside-beta gap.

**Decisive metric:** Lower realized beta and lower drawdown without lower residual alpha.

**What would kill it:** If it just becomes a low-beta filter and gives up too much return.

---

## 6. Filing-reaction-supported residual momentum

**Idea:** Prefer residual momentum that is confirmed by positive abnormal price reaction around recent SEC filing / earnings-information windows.

**Mechanism / thesis:** Price momentum backed by new fundamental information is more likely to persist than price momentum caused by sentiment, squeeze dynamics, or beta. You have point-in-time SEC filings, so you can use filing dates as an imperfect but usable information-event anchor.

**Closest dead-end it avoids:** Earnings momentum based on TTM net-income YoY. This is not ranking by accounting growth. It is ranking by **market underreaction to disclosed information**, closer to post-earnings-announcement drift.

**Why it survives your failure modes:** The event return is measured as residual abnormal return, so it should not be a simple high-beta tilt. It is not an exit or timing overlay; it only changes candidate selection.

**How to test it:**
For each stock, identify 10-Q / 10-K filing dates available before the rebalance. Around each filing:

```text
filing_residual_return = cumulative ε from filing day to filing day + 5
```

or use +10/+20 days.

Then test:

```text
score = baseline_residual_IR + 0.25 * filing_reaction_z
```

or require latest filing reaction to be positive before a stock can enter the top 35.

**Decisive metric:** Improvement in beta-adjusted return / residual alpha, not just drawdown.

**What would kill it:** If the filing component is noisy, sparse, or only works in one regime. Also kill it if performance is entirely from holding around event gaps and not robust to reasonable execution assumptions.

---

## 7. Fundamental acceleration confirmation

**Idea:** Keep residual momentum, but require recent fundamentals to be improving versus the company’s own trend.

**Mechanism / thesis:** Residual momentum can be purely price-based. The best candidates may be those where price strength is supported by improving business trajectory: revenue acceleration, gross margin stabilization, operating leverage, or net-income inflection. This is different from generic quality. You are not buying “high quality”; you are asking whether the momentum has a fundamental reason to continue.

**Closest dead-end it avoids:** Quality / gross-profitability and earnings momentum. This is not GP/assets or TTM net-income YoY. It is **fundamental acceleration or inflection as confirmation** for residual momentum.

**Why it survives your failure modes:** Used as a veto/confirmation layer, it should avoid becoming a standalone high-beta factor. It stays inside the ranking/selection stage.

**How to test it:**
Using PIT quarterly fundamentals, compute simple changes:

```text
revenue_growth_qoq_or_yoy
gross_margin_change
net_margin_change
revenue_growth_acceleration
gross_profit_growth_acceleration
```

Then test a conservative rule:

```text
eligible_for_top35 = baseline residual candidate AND not in worst 30% of fundamental acceleration
```

Do not optimize many weights. Use one or two coarse filters.

**Decisive metric:** Better Sharpe or lower drawdown with similar turnover and similar beta.

**What would kill it:** If it only helps in tech/growth regimes or if it becomes another high-beta growth tilt.

---

## 8. Accounting-risk veto: asset growth / accrual-like deterioration

**Idea:** Exclude residual momentum winners showing aggressive balance-sheet expansion or accounting-quality deterioration.

**Mechanism / thesis:** Some strong momentum names are “story stocks” funding growth aggressively. High asset growth, margin deterioration, or earnings unsupported by revenue/gross profit can precede sharp reversals. This should reduce left-tail blowups without trying to time exits.

**Closest dead-end it avoids:** Value and quality factors. This is not buying cheap or high-quality stocks. It is a **negative veto** against accounting-risk names inside an already-selected momentum universe.

**Why it survives your failure modes:** The filter is designed to remove likely false positives, not create a new long-only factor sleeve. It should not become beta by construction if used only after residual-momentum preselection.

**How to test it:**
Depending on available fields:

```text
asset_growth = total_assets_t / total_assets_t-4 - 1
gross_margin_change = gross_margin_t - gross_margin_t-4
net_income_quality_proxy = net_income_growth - revenue_growth
```

Crude but testable rule:

```text
from top 100 residual candidates, remove worst quintile by accounting-risk composite, then buy top 35
```

**Decisive metric:** Reduction in worst-name losses and max drawdown, with no meaningful hit to CAGR.

**What would kill it:** If the removed names are exactly the winners and the filter lowers return without reducing crash loss.

---

## 9. Residual downside-tail penalty

**Idea:** Penalize stocks whose residual momentum has bad left-tail behavior, even if their mean/std looks good.

**Mechanism / thesis:** Standard residual IR treats upside and downside volatility symmetrically. Momentum crashes are asymmetric. A stock with strong average residual drift but repeated large residual down days may be a worse candidate than a smoother name with the same IR.

**Closest dead-end it avoids:** Risk-adjusted momentum and path-quality / frog-in-the-pan. This is not return/vol and not generic smoothness. It specifically measures **left-tail residual loss**.

**Why it survives your failure modes:** It should not become beta if applied to residuals, and it is not a stop or timing rule. It changes the initial basket only.

**How to test it:**
For each stock:

```text
residual_CVaR_5 = average of worst 5% daily residual returns
residual_tail_ratio = abs(residual_CVaR_5) / residual_vol
```

Then:

```text
score = baseline_residual_IR - λ * residual_tail_ratio
```

or exclude the worst quintile by residual tail ratio.

**Decisive metric:** Lower worst-month and lower max drawdown with similar CAGR.

**What would kill it:** If it just re-creates a low-vol tilt or if the penalty removes too many true momentum winners.

---

## 10. Residual momentum lifecycle / signal-age filter

**Idea:** Prefer residual momentum that is persistent but not stale: avoid one-month wonders and over-aged crowded winners.

**Mechanism / thesis:** Momentum has a lifecycle. Very fresh signals may be noise or event overreaction. Very old winners may be crowded and vulnerable to reversal. The sweet spot may be stocks whose residual score has recently become strong and stayed strong for a few months, but has not been top-ranked forever.

**Closest dead-end it avoids:** Rebalance cadence, hold length, and top-N sweeps. This does not change when you rebalance or exit. It changes whether a stock’s signal is **early, confirmed, or stale**.

**Why it survives your failure modes:** It is still a ranking/selection feature, not timing/sizing. It also avoids generic factor overlap because it uses the history of the residual signal itself.

**How to test it:**
At each rebalance, track for each stock:

```text
months_in_top_decile_residual_score
months_since_first_entering_top_decile
change_in_residual_score_percentile_over_last_3_rebalances
```

Simple test:

```text
exclude names with 0 prior months in top decile
exclude names with > 9 consecutive months in top decile
```

or prefer names with 2–6 months of confirmed residual strength.

**Decisive metric:** Lower reversal losses and improved walk-forward Sharpe.

**What would kill it:** If the “best age” is regime-dependent or if it overlaps too much with arbitrary turnover control.

---

## 11. Abnormal-volume / attention-risk filter

**Idea:** Avoid residual momentum names whose signal is accompanied by extreme recent abnormal volume or attention-like trading bursts.

**Mechanism / thesis:** In liquid stocks, some residual winners are driven by crowded attention, retail mania, short-covering, or single-theme excitement. Extreme volume spikes can identify names where residual momentum is less durable and more crash-prone.

**Closest dead-end it avoids:** Path quality and 52-week-high proximity. This is not about price shape or distance from highs. It uses **participation/attention intensity**.

**Why it survives your failure modes:** It does not create a separate long-only volume factor. It is a sanity filter on residual momentum candidates. It also avoids timing/exits.

**How to test it:**
Use daily dollar volume:

```text
abnormal_volume = current_20d_dollar_volume / median_252d_dollar_volume
volume_spike_z = zscore(log(abnormal_volume))
```

Test:

```text
from top 100 residual candidates, exclude top 5–10% by abnormal-volume spike, then buy top 35
```

Do not penalize moderate volume confirmation; only remove extremes.

**Decisive metric:** Fewer large single-name losses and lower drawdown with flat Sharpe or better.

**What would kill it:** If abnormal volume is actually the institutional accumulation signal and removing it lowers return.

---

## 12. Peer-cluster-relative residual momentum

**Idea:** Residualize stocks not only against SPY, but also against a dynamic peer cluster return, then rank on what remains.

**Mechanism / thesis:** CAPM residual momentum can still be sector/theme momentum. If the entire semiconductor cluster is ripping, many names may look like stock-specific residual winners even though the real bet is one cluster. A peer-cluster residual asks: “Is this stock outperforming its actual neighbors, not just SPY?”

**Closest dead-end it avoids:** FF3 / size residual momentum. This does add another benchmark, but not generic academic factors. It uses a stock’s own return-based peer cluster, which may capture the specific hidden theme better than FF3.

**Why it survives your failure modes:** If done carefully, it should reduce hidden sector/theme beta rather than introduce market beta. It remains a ranking-signal change.

**How to test it:**
Each month:

1. Use formation-window correlations to assign stocks to clusters.
2. For each stock, build a leave-one-out equal-weight cluster return.
3. Estimate:

```text
r_stock = α + β1*SPY + β2*cluster_return_leave_one_out + ε_cluster
```

4. Rank by `mean(ε_cluster) / std(ε_cluster)`.

**Decisive metric:** Lower correlation to plain momentum and lower drawdown, while preserving enough return.

**What would kill it:** If return drops sharply. That would imply sector/theme momentum is load-bearing and should not be neutralized.

---

# Triage table

| Idea                                         | Mechanism class                               |                     Data needed | Cheap to test? | Conviction | Closest dead-end avoided              |
| -------------------------------------------- | --------------------------------------------- | ------------------------------: | -------------: | ---------: | ------------------------------------- |
| Down-market residual strength                | Beta-leakage control inside ranking           |              Daily prices + SPY |            Yes |          H | Defensive timing / 200-day overlays   |
| Momentum-crash beta filter                   | Direct crash-state exposure control           |  Daily prices, universe returns |            Yes |          H | VIX/tail-trigger de-risking           |
| Cross-sectionally purified residual momentum | Remove raw momentum/beta component from score |   Daily prices, volume optional |            Yes |          H | FF3 / size residual momentum          |
| Residual-correlation de-crowding             | Hidden theme/crowding reduction               |              Daily prices + SPY |            Yes |        H/M | Top-N concentration sweep             |
| Beta-instability / downside-beta penalty     | Reliability filter for CAPM residuals         |              Daily prices + SPY |            Yes |        M/H | Static beta hedge                     |
| Filing-reaction-supported residual momentum  | Event-underreaction confirmation              | Daily prices + SEC filing dates |         Medium |          M | TTM earnings momentum                 |
| Fundamental acceleration confirmation        | Business inflection confirmation              |      PIT quarterly fundamentals |         Medium |          M | Quality / GP-assets                   |
| Accounting-risk veto                         | Avoid story-stock / aggressive-growth blowups |                PIT fundamentals |         Medium |          M | Value / quality factors               |
| Residual downside-tail penalty               | Asymmetric crash-risk filter                  |              Daily prices + SPY |            Yes |          M | Risk-adjusted momentum / path quality |
| Residual momentum lifecycle filter           | Avoid noisy/stale signal phases               |    Daily prices, signal history |            Yes |        M/L | Cadence / hold-length variants        |
| Abnormal-volume attention-risk filter        | Avoid squeeze / mania candidates              |            Daily price + volume |            Yes |        M/L | 52-week-high / path quality           |
| Peer-cluster-relative residual momentum      | Remove hidden sector/theme momentum           |              Daily prices + SPY |         Medium |        L/M | FF3 / size residual momentum          |

My top 4 to actually spend cycles on: **down-market residual strength, momentum-crash beta, cross-sectional purification, and residual-correlation de-crowding.** Those are the most structurally different from your failed tests and most directly aimed at the real weakness: the strategy is still a high-correlation cousin of plain momentum, not a clean orthogonal alpha engine.
