# Positive-Control Strategy Request — validating a long-only same-day equity pipeline

## Why I'm asking (the actual problem)

I've built a deliberately strict validation pipeline for systematic trading
strategies (broad leak-free feature capture → pre-registered combinatorial filter
search → leave-one-year-out walk-forward → Probability-of-Backtest-Overfitting →
Deflated-Sharpe gate → one sealed out-of-sample year). It has been run on several
strategy families and has **killed every one of them**.

That is a problem of *unknown type*. A validator that only ever rejects is
untrustworthy — I cannot distinguish "these strategies genuinely have no edge"
from "my pipeline is so conservative it would reject a real edge too" (a false-
negative machine). I need a **POSITIVE CONTROL**: a strategy with a *known,
documented, robust* edge that SHOULD pass, so I can confirm the pipeline has real
detection power. If a known-good edge dies in my pipeline, the pipeline is broken.

## The framework the strategy MUST fit (hard constraints)

- **Long-only, same-day (intraday) US equities.** Positions open after 09:30 ET
  and are **closed by the regular-session close** — no overnight holds, no shorts.
- **Decision at a fixed intraday time** (≈09:35 ET, after the first 5-minute bar),
  using ONLY data knowable then: prior daily bars, ~30 prior intraday sessions,
  the first 5-min bar, and prior SPY/sector data. Strictly leak-free.
- **Point-in-time liquid universe** (~1,000–1,500 US names/day).
- **Mechanical** entry / stop / target / time-exit. Outcome measured in **R**
  (multiples of risk per trade). Each day trades a **capped number of names**
  (e.g. top-10 by a ranking signal).
- Evaluated on **2022–2024** (search) with **2025** sealed as the one-shot holdout.

## What I need

A ranked shortlist of **proven, confident** edges. Modest profitability is fine —
even *preferred*: a small, stable, low-Sharpe-but-reliably-positive effect tests
the pipeline's sensitivity better than a big fragile one. Each must be
implementable in the mold above.

## Selection criteria (please rank by these)

1. **Documented & replicated** — academic citation or widely reproduced; ideally
   survived OUT-OF-SAMPLE *after* publication (not just in-sample in one paper).
2. **Fits long-only same-day intraday** — or state the *minimal* adaptation.
   Reject anything that fundamentally needs overnight/multi-day holds or shorting.
3. **Robust > large** — prefer modest and stable over high and fragile.
4. **Low cost/capacity sensitivity** — survives realistic slippage on liquid names.
5. **Clear economic mechanism** — why the edge exists and why it persists.
6. **Leak-free implementable** from daily + intraday bars only.

## For each candidate, give me

- **Name** + one-line economic mechanism.
- **The exact rule in my mold:** admission/ranking signal (computable at 09:35),
  entry trigger, stop, target, time-exit.
- **Evidence it's real:** citation / replication / post-publication track record;
  a rough effect-size order of magnitude (daily Sharpe, win rate, or R/trade).
- **Known failure modes / regime dependence / decay over time.**
- **Fit grade:** native / minor-adaptation / forced — and the adaptation needed.

## The two hard questions I most want answered

1. **Do ANY robustly-proven equity edges actually fit long-only same-day
   intraday?** Or do the bulletproof effects (cross-sectional momentum, value,
   post-earnings drift, the overnight/close-to-open premium, short-term reversal)
   live in holding-period or long/short regimes my framework structurally cannot
   express? If it's the latter, say so plainly — that tells me whether my
   framework is aimed at a regime where durable edges are inherently thin (which
   would explain why everything gets killed, and would itself be the finding).

2. **Would you instead (or also) recommend a SYNTHETIC positive control** — inject
   a known, modest, leak-free predictive signal into the historical dataset and
   verify the pipeline recovers it and passes it all the way through the sealed
   year — as a cleaner test of the *validator's detection power* with exact ground
   truth? Argue for or against vs a real-world control.

Be concrete and skeptical. I would rather hear "nothing proven fits your mold,
here's why" than a confident list of effects that won't survive intraday on
liquid names after costs.
