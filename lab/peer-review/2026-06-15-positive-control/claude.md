# Positive-Control Theory

**Author:** Claude (Opus 4.8). My recommendation, to compare against the other models.

## The key reframe: two different questions, do them in order

"Find a strategy I know will work" actually bundles two distinct tests, and
conflating them is a trap:

- **Q1 — does the VALIDATOR have detection power?** (Can the pipeline pass a true
  edge at all?) This is about the *machinery*.
- **Q2 — does a real-world edge survive on MY universe + costs + mold?** This is
  about the *market*.

You can't cleanly answer Q2 until Q1 is settled — if a real strategy fails, you
won't know whether the edge isn't there or the pipeline can't see it. So:

## Tier 1 (do first): a SYNTHETIC positive control — exact ground truth

Inject a **known, modest, leak-free** signal into a capture-shaped ledger and run
the FULL pipeline (search → LOO walk-forward → PBO → DSR → sealed year) on it.
Concretely: take the real 2022–2025 ledger, and overwrite `realized_r` with a
construction where one captured feature genuinely (mildly) predicts R — e.g.
`realized_r = β·z(opening_rv) + noise`, with β chosen so the daily-portfolio
Sharpe is small-but-real (say annualized ~1.0), plus realistic fat-tailed noise.
Then verify the pipeline:
1. **recovers** the planted feature as the winning filter,
2. **passes** WF (positive every LOO fold), PBO < 0.5, **DSR ≥ 0.95**, and
3. **survives** the sealed 2025 year.

Why this is the right first move: it tests detection power with *zero market
ambiguity*. If the pipeline can't pass a known planted edge, it's broken — full
stop, and we'd know it's the machinery, not the world. We already have a
miniature of this (`test_walk_forward_recovers_planted_edge`); scaling it to a
full end-to-end run (incl. DSR and a sealed-year pass) is cheap and decisive.
Tune β downward until the pipeline *just barely* passes — that calibrates its
sensitivity floor (the smallest real edge it can confirm), which is exactly the
number you want to know about a validator that's been killing everything.

## Tier 2 (then): the best REAL-world fit — intraday momentum

If you want a market control, the strongest *proven* effect that natively fits
long-only same-day is **market/stock intraday momentum** (Gao, Han, Li & Zhou,
"Market Intraday Momentum," RFS 2018, and follow-ons): the first half-hour return
predicts the *last* half-hour return of the same session. It is:
- genuinely **same-day** (open-window signal → into-the-close hold),
- **long-expressible** (go long when the morning return is positive),
- **published + replicated + survived post-publication / across markets**,
- **modest and robust** (small daily Sharpe — exactly the "low but confident"
  profile you asked for), with a clear mechanism (late-informed traders +
  infrequent institutional rebalancing → intraday underreaction).

Implementation in the mold: admission = first-bar (or first-30-min) return > 0
(optionally require SPY intraday momentum > 0 too); rank by morning-return
strength; entry long; **time-exit at 15:55, not 11:30** (the effect is about the
close — this is a one-line `exit_cutoff` change, already supported by the d04
full-session variant); stop for risk control. If a faithful implementation of
*this* dies in the pipeline, suspect the implementation or the pipeline — not the
effect.

Honest caveats on Tier 2: the effect is documented strongest at the **index/ETF**
level and in aggregate; the single-stock, top-10 version is noisier and more
cost-sensitive, and it has likely decayed somewhat since 2018. So it's a *good* but
not *bulletproof* control — which is exactly why Tier 1 (synthetic) should come
first.

## The meta-point I'd flag regardless of the other models

Most bulletproof equity anomalies **do not fit long-only same-day intraday**:
- cross-sectional momentum / value / quality → multi-month holds,
- post-earnings-announcement drift → multi-day,
- the **overnight / close-to-open premium** → that's literally the window this
  framework *skips* (it holds intraday and is flat overnight),
- short-term reversal → cleanest version needs shorting.

That's not a side note — it may be the explanation for "everything gets killed."
The framework's mold (intraday-momentum-on-individual-stocks, long-only, after
costs, on a liquid universe) is a **genuinely thin regime**. The positive control
disambiguates the two stories:
- Synthetic passes **and** intraday-momentum passes → pipeline is sound and the
  negatives are trustworthy; the regime is just hard.
- Synthetic passes but intraday-momentum fails → the pipeline works; real intraday
  stock edges don't survive *your* universe/costs (a strategic finding — maybe
  widen to ETFs, or relax the same-day-flat constraint to capture the overnight
  premium).
- Synthetic **fails** → stop everything and fix the validator; every prior kill is
  suspect.

## Recommendation

Build the **synthetic end-to-end positive control first** (Tier 1) — it's the
fastest, most decisive check that the validator can confirm a true edge, and it
calibrates the minimum edge size it can detect. Then run **intraday momentum**
(Tier 2) as the real-world control. Treat the other models' lists mainly as input
to Tier 2 and to the meta-question (does anything proven really fit the mold).
