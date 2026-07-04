# dominance_flip_reversal (f-series) — Backlog

Updated 2026-06-13.

## ⛔ FAMILY VERDICT (2026-06-13): killed — breakeven-by-luck, no edge

f01 audited (sound, no look-ahead, 7/7 tests) then run with four one-lever
variants on `screen_2022_2026_sampled` (108 days, 1m-irrelevant; flip stops
are far so 5m sim is honest). Pre-registered kill rule (sum R < 0 OR pooled
sign-flip p > 0.5): **all five fail.**

| Rel | Lever | Trades | Sum R | Win% | avg R | p | Gate |
|---|---|---:|---:|---:|---:|---:|:--:|
| f01 | baseline | 423 | −41.8 | 50.4 | −0.099 | 0.84 | KILL |
| f02 | +SPY 200d trend filter | 296 | −1.6 | 55.4 | −0.005 | 0.51 | KILL |
| f03 | warm-start (morning flushes) | 541 | −53.9 | — | — | 0.85 | KILL |
| f04 | 6-bar time-decay abort | 423 | −50.3 | — | — | 0.92 | KILL |
| f05 | mean + 0.5·ATR overshoot target | 423 | −38.5 | — | — | 0.78 | KILL |

**One real finding — the falling-knife diagnosis was correct.** f02's 200-day
trend filter removed ~95% of the loss (−41.8R → −1.6R) and lifted win rate
50→55%, exactly in the bear buckets the audit flagged (2022H1 −15.3→−6.6,
2022H2 −8.3→0.0, 2023H1 −19.0→−2.0). f01 genuinely bled by buying capitulation
against the macro downtrend.

**But it's breakeven-by-luck, not edge:** f02 avg R ≈ −0.005 (the filter
removed losses, didn't add wins), p = 0.51 (coin flip), and the *entire family*
is carried by a single bucket — 2026H1 (+29 to +34R every variant), negative
almost everywhere else. Same single-period dependence that killed ORB.

The other levers disprove a hidden edge: warm-start (f03) made it WORSE (more
morning flushes = more of the same losing distribution → no hidden edge);
abort (f04) worse; overshoot (f05) ~neutral.

**Conclusion: dominance_flip is exhausted. Keeper insight = the 200d trend
filter** (bank for any future long-only mean-reversion work). Do NOT chase a
combined f02+f05 — still 2026H1-carried with p>0.5. Per "rethink, don't tune,"
move off both classic setups on this universe.

## Status (historical)

- `f01` — dominance flip reversal strategy (exists as code). Detects capitulation via SMA stretch and RSI divergence.

## Relationship to l01

`l01` (Liquidation Cascade Reversal) is a simpler, volume-based alternative to f01 without the RSI divergence requirement. See `strategies/liquidation_cascade_reversal/backlog.md`.

High overlap with f01 — l01 may not add independent edge. Test as a fast ablation (2-hour script) to measure overlap before committing to a full release.

## Open

- No active backlog items. Revisit if l01 ablation shows convergence with f01.

## Audit-driven releases (2026-06-13) — UNRUN

From the 3-reviewer codebase audit. Added as NEW releases (f02/f05 are frozen):

- **f06** (audit H2): f02's 200-day-SMA macro-trend gate, but read from
  runner-hydrated `context.spy_daily` (new `spy_daily_lookback_days=320`)
  instead of a direct `fetch_daily_context` call — fixes the architecture
  violation while keeping the identical gate.
- **f07** (audit M11): f05's mean + 0.5·ATR(5m) overshoot target, but candidates
  whose ATR(5m) is missing/non-finite are SKIPPED (with a warning) instead of
  silently reverting to f01's mean-touch target (which inflated f05's trade
  count with disguised-f01 trades).

Neither has been through the screen funnel yet.

## Audit follow-up (2026-06-18 codebase review) — needs fix-forward releases

From the 2026-06-18 whole-tree audit. Immutable code (`common.py`, `variants.py`,
shipped releases) → fix forward, never in place. (That audit was only ~half-reliable;
items tagged with check status.)

- **H2 — `spy_above_200sma()` direct provider call** (CORROBORATED; f06 already the
  forward fix). `variants.py:37-53` reads SPY via `fetch_daily_context()` in strategy
  code instead of `context.spy_daily`. f06 is the contract-compliant forward path; f02
  remains on the direct-fetch path. Listed for traceability — no new release needed
  beyond f06.
- **M4 — tz-aware vs naive comparison risk** (`f01.py:128-139`, `variants.py:100-111`).
  `setup["flip_time"] > latest_flip` where `latest_flip` is tz-aware (`ny_dt()`) and
  `flip_time` comes off the DataFrame index. The runner's `ensure_ny_index()` normalizes
  indices today, so it works, but the release code carries no guard of its own. Add an
  explicit tz check in a future f-release rather than relying on the loader.
- **M10 — `warm_start_lookback_days` is dead** (VERIFIED). `variants.py:62` declares it
  and `f03.py:29` sets it to 2, but it is never read — the real warm-start path is
  `historical_5m_lookback_days = 2` (`f03.py:30`), which the runner uses to hydrate
  `context.historical_5m`. No runtime effect; remove/deprecate it in the next f-release.
- **L5 — z-scores use `ddof=0`** (`common.py:45, 56`). Population stdev in
  `compute_flip_indicators`; a defensible design choice, minor impact. Note only.
