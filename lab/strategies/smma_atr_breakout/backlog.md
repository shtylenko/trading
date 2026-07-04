# smma_atr_breakout (letter `s`) — backlog

A long-only continuation-breakout family adapted from the "medium complexity"
strategy Lisa Forex named as her best live performer in the 50,865-strategy
study (`lisa_forex_transcripts/transcript_HYnXpdMQ9Wk_…`). It is the only recipe
in that video with concrete, re-implementable mechanics; everything else there
is component-checklist hand-waving.

## Why this family exists

Orthogonal-by-design to the proposed **m01 SMA mean-reversion** family: m01
buys *below* its average expecting reversion; `s` buys *above* its smoothed
average expecting continuation. Closest existing relative is the d gap-and-go,
but `s` keys off a smoothed trend line + an ATR breakout band rather than a
prior-day gap, so it can fire on names that never gapped.

## Source recipe → long-only mapping

| Video component | s01 implementation |
|---|---|
| SMMA / "SSMA" trend indicator | Wilder SMMA(20) on 5m closes, seeded from 10d history |
| ATR indicator | daily ATR14: tradeability gate **and** stop/target scale |
| stop order based on SMMA | buy-stop = SMMA + 0.25·ATR14, must be above current price |
| ATR-multiple stop loss | entry − 1.0·ATR14 (= 1R) |
| ATR-multiple profit target | entry + 2.0·ATR14 (2:1) |
| exit after N bars | `max_hold_bars = 12` (≈ 1h on 5m) via signal metadata |
| order expiry | implicit: no fill ⇒ NO_FILL by the 15:55 cutoff |
| short leg | **dropped** — strategy_lab is long-only |

## Releases

| Rel | Status | One-liner |
|---|---|---|
| s01 | **Proposed — not yet run** (2026-06-13) | P0 baseline, parameters above |

## Open questions before/while running

- **The 2026H1 trap.** Per auto-memory, the only positive bucket across 18
  releases / 3 families so far is 2026H1, and it may be a recent-liquid_pit
  snapshot artifact. Screen s01 on `screen_2022_2026_sampled` first; if it only
  carries on 2026H1, treat as suspect, not signal.
- **Trade count.** SMMA-above + ATR floor + forward-breakout band may be
  restrictive. Watch the funnel anti-goal: if it collapses to single digits per
  quarter, widen `entry_atr_mult` / drop the ATR floor before adding filters.
- **Bar-count vs time exit.** s01 declares no 1m data on purpose so the
  simulator runs on 5m and `max_hold_bars` counts 5m bars. If a later release
  turns on `requires_rth_1m`, the same N would mean N *minutes* — re-express.

## Next intended releases (pre-register together in variants.py before running)

- s02 — relative-volume "in play" gate (only break out on climactic volume).
- s03 — trail the trigger off the live rolling intraday SMMA each bar instead
  of freezing it at the open.
- s04 — one-lever sweep of entry_atr_mult / stop_atr_mult / target_atr_mult /
  max_hold_bars / smma_period.
