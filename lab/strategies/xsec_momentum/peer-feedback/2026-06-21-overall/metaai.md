Here’s how I read your x03 write-up — not as a pitch, but as an engineering note — and where it sits in the broader momentum literature.

## The big picture

You’re doing classic cross-sectional momentum (Jegadeesh-Titman 12-1), but you rank on the stock-specific drift instead of raw return. That’s exactly the “residual momentum” idea from Blitz, Huij, and Martens (2011). They showed that ranking on residual returns cuts the time-varying exposures to the Fama-French factors, and as a consequence “residual momentum earns risk-adjusted profits that are about twice as large as those associated with total return momentum”. In their paper the Sharpe ratio is “approximately double that of total return momentum, mainly due to lower return variability”.

Your implementation mirrors that logic, with a few clean choices:
- **Skip the most recent month** — that’s standard to avoid short-term reversal, “it is common to skip 1 month between the formation and holding period to isolate momentum from the short-term reversal effect (e.g., Jegadeesh and Titman (1993), Carhart (1997))”
- **Single-factor residual (CAPM vs SPY)** — simpler than the original 3-factor version, but directionally the same: strip market co-movement, then score mean(ε)/std(ε)
- **Liquidity and price gates ($5, $10M ADV, 273 days)** — keeps it tradable and avoids the micro-cap lottery tickets that drive a lot of backtest inflation
- **Equal-weight top 50, monthly hold** — avoids over-betting a noisy point estimate, and matches the literature’s typical 1-month holding

So conceptually, x03 isn’t claiming a new anomaly. It’s claiming better engineering of the same anomaly — lower beta, smoother path.

## What the evidence actually says

**For the family:** momentum is the most replicated cross-sectional effect. The twist you use has independent support: Blitz et al. find residual momentum “delivers higher risk-adjusted performance than a conventional momentum strategy”, and later work finds it “is more consistent over time; and less concentrated in the extremes”.

**For x03 specifically:** you’re admirably honest in §7. You have strong in-sample results (2017-2024, beta ~1.08 vs 1.45, drawdown -23% vs -36%, Sharpe 0.89 vs 0.81), but no sealed out-of-sample year yet. That matters because momentum’s edge has decayed in some samples. A recent Latin America study, for example, finds “conventional momentum produces zero risk-adjusted returns. Residual and model-based momentum strategies are also unable to deliver positive and significant risk-adjusted performance”. It’s one region, but it reminds us the premium isn’t guaranteed everywhere, all the time.

## Risks you’ve already flagged — and a couple to stress-test

1. **It’s still momentum.** You note ~0.95 correlation to plain momentum. That means you inherit the crash regime. Daniel and Moskowitz show “the returns to momentum strategies are negatively skewed: they experience infrequent but strong and persistent strings of negative returns. These momentum crashes are partly forecastable. They occur in what we term ‘panic’ states – following market declines and when market volatility is high”. Residual helps, but doesn’t eliminate it.

2. **Single-factor residual leaves factor bleed.** You strip SPY, but not size/value/profitability. Blitz’s original used Fama-French residuals for a reason — plain momentum loads time-varying on those factors. Your beta ~1.08 is better than 1.45, but some of the “idiosyncratic” drift may still be small-cap or quality tilt.

3. **Long-only, no timing.** You tested a defensive overlay and it hurt — fair. But that means in a 2008 or 2020 drawdown you’re riding ~1x market with a momentum tilt. The strategy document is clear on this, which is good discipline.

4. **Implementation frictions.** You don’t model costs in the summary. With 50 names turning over monthly, expect 60-100% annual turnover in practice. At $10M ADV minimum, a 2% position in a $50M book is $1M — that’s 10% of ADV, so you’ll need VWAP slicing or you’ll eat spread. Taxes in a taxable account will also bite monthly rebalancing.

5. **Survivorship and data mining.** You note pre-2022 survivorship lift. That’s the right caveat. Also, the information ratio ranking (mean/std of residuals) is a sensible risk adjustment, but it adds a second layer of estimation noise on top of beta. In thin-history names, std(ε) can be unstable.

## Where I’d push the design if you want to harden it

- **Run the sealed OOS you mention (2027).** Pre-register the exact universe, rebalance dates, and execution assumptions now, then don’t peek. That’s the cleanest way to move from “in-sample improvement” to “independent confirmation.”

- **Test a 3-factor residual as a sibling.** Keep x03 as-is, but run x03-FF3 in parallel (regress on Mkt-Rf, SMB, HML). If the IR ranking collapses, you know much of your edge was factor tilt; if it holds, you’ve got a purer idiosyncratic signal.

- **Add a crash-aware overlay, but as a separate sleeve.** Daniel/Moskowitz show a dynamic version “achieves an unconditional Sharpe ratio twice that of static strategies” by forecasting mean and variance. You don’t have to bake stops into x03 — keep it pure — but a volatility-scaled overlay (reduce gross exposure when prior 3-month market return is negative and VIX is high) could live alongside it.

- **Cost accounting.** Simulate with 5-10 bps one-way for large caps, 20-30 bps for mid-caps, plus short-term cap gains if taxable. If Sharpe 0.89 becomes 0.6 after costs, that’s still interesting, but it changes position sizing.

- **Capacity check.** Your $10M ADV filter is good. For a $20M book, 2% = $400k per name, ~4% of ADV — comfortable. Scale to $200M and you’re at 40% of ADV on the smaller names; you’d need to widen to top 100 or raise the ADV threshold.

## Bottom line for x03

It’s a disciplined, literature-grounded refinement of momentum — not a new factor, but a cleaner way to harvest the old one. The core idea (rank on residual, not raw return) has academic support for roughly doubling risk-adjusted returns versus total-return momentum in long histories, largely by cutting factor timing risk.

Your own backtest lines up: similar returns, lower beta, shallower drawdown. The honest limitation you state is the key — it’s in-sample on the variant, and momentum crashes still live in the distribution, especially in panic states following market declines.

If you treat x03 as “momentum with better risk engineering” rather than “alpha that beats the market in all regimes,” the design choices make sense. The next credibility step is exactly what you wrote: a fresh, untouched out-of-sample year, with costs and taxes modeled, and a parallel 3-factor residual to see how much is truly idiosyncratic.

Want me to help you draft the pre-registration spec for that 2027 test — universe definition, rebalance calendar, and cost assumptions — so you can lock it in before the data exists?