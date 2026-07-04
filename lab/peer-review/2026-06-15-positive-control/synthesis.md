# Positive-Control Feedback — Synthesis (5 models)

Sources in this folder: `claude.md` (Opus 4.8), `chatgpt.md`, `gemini-simple.md`,
`gemini-deep-research.md`, `meta.md`. Synthesized 2026-06-15.

## Unanimous consensus

1. **Build the SYNTHETIC positive control first — mandatory.** All five agree it's
   the only clean test of the validator's *detection power* (exact ground truth).
   A real-world control can't disambiguate broken-pipeline vs decayed-edge vs
   hostile-window.
2. **"Everything gets killed" is most likely the REGIME, not a broken pipeline.**
   Long-only, same-day, flat-by-close, liquid names is a structurally thin slice:
   ~100% of the equity premium accrues OVERNIGHT (the window we skip); the
   bulletproof anomalies (X-sectional momentum, value, PEAD, short-term reversal)
   need multi-day holds or a short leg (both forbidden). A 100% kill rate is
   consistent with a correctly-calibrated validator on a hard regime.
3. **Synthetic design:** dose-response (null β=0 + increasing β), inject only into
   the post-09:35 outcome, keep pre-decision features clean, calibrate to a MODEST
   edge, run the FULL pipeline incl. the sealed year, produce a POWER CURVE
   (minimum detectable edge), not a binary pass/fail. Freeze the recipe/seed before
   running.
4. **Gate-calibration caveat** (gemini-deep-research, meta): DSR≥0.95 / PBO may be
   tuned for monthly-portfolio noise and be too punitive for intraday Sharpe
   scales. Use the synthetic control to CALIBRATE the gate to the horizon — find
   the threshold that admits a known modest edge; if a true Sharpe~1 edge fails,
   the gate (not the market) is the problem.

## Real-world controls (secondary; ranked, with the consensus caveats)

| Candidate | Consensus view |
|---|---|
| **Overnight gap-DOWN intraday reversal** (long the stabilizing overnight losers) | Best *real* fit, but published form is long/short + open-to-close; long-only 09:35 version is weak & cost-sensitive. It is the COMPLEMENT of the gap-up momentum we already killed. |
| **Intraday momentum** (Gao et al. 2018) | DOWNGRADED by 4/5: index/ETF-level not single-stock; 09:35 too early for the first-30-min signal; decayed post-2018. (I, Claude, had over-ranked this.) |
| **HKS same-time-of-day continuation** | Academically respectable, individual-stock, but interval-specific — dilutes badly open-to-close. |
| **RVOL-ORB "stocks in play"** (Zarattini/Barbon/Aziz 2024) | Fits mechanically but ≈ what we ALREADY KILLED (gap-and-go/ORB), and evidentially newer/weaker. Poor "known-good" control. |

## Decision tree (after running the synthetic control)

- **Null fails + signal passes at a reasonable β** → pipeline has correct detection
  power → prior kills are trustworthy → the regime is just thin. (Most likely.)
- **Signal fails even at large β** → pipeline is over-conservative → recalibrate the
  gates (likely DSR/PBO thresholds for the intraday horizon) BEFORE trusting any
  kill. Re-run the synthetic until a known modest edge passes; lock the calibrated
  thresholds.

## Strategic implication (the bigger finding)

The strongest cross-model message is about *scope*, not mechanics: durable
long-only same-day intraday equity edges are inherently thin. If the synthetic
control confirms the validator works, the highest-value pivots are structural, not
another setup on the same mold:
- **relax flat-overnight** to capture the overnight / close-to-open premium (where
  the premium actually lives), or
- **allow a short leg** (to express reversal / cross-sectional spreads), or
- **widen the universe to ETFs / sectors** (where intraday-momentum effects are
  documented strongest).

## Plan

1. Build the **synthetic dose-response control** end-to-end (search → LOO-WF → PBO →
   DSR → sealed 2025). Recover the planted feature; map β → which gates pass;
   report the minimum detectable edge and whether DSR≥0.95 is horizon-appropriate.
2. Interpret via the decision tree; recalibrate gates only if a known modest edge
   fails (transparently, recorded).
3. Only then, if desired, run the gap-DOWN reversal as a borderline real-world
   sanity check — expecting it to be marginal.
