# RULE_TRACE — TRADE_SIMULATOR rule → Ross Cameron canon

Every **behavioral** rule in `trade_skills/<version>.md` must trace to the canon
(`library/ross_cameron/all_content_structured.md`). **Update this table on every
behavioral version bump** (it's a gate — see `IMPROVING.md` §1, §4).

> **Accepted baseline = 2.4.1** (the live skill). Notes tagged **"2.7.0 cand"** (exit-side
> objectification) or **"2.8.0 cand"** (entry-side tightening) are **un-promoted candidates**
> from the 2.6.0-REJECT decomposition (see CHANGELOG) — archived, awaiting a paired `compare`.
> They describe rules *as they would be if promoted*, not the accepted ruleset. The superseded
> 2.5.0/2.6.0 bundles are not separately tracked here.
> **3.0.0 is an unpromoted major execution-model candidate**; it deliberately does
> not share an expectancy baseline with the reported-fill v2.x sessions.

**Type** legend:
- **direct** — the rule is Cameron's, stated ~as taught.
- **operationalization** — our precise translation of a Cameron idea onto the 1-min
  sealed feed (must say *how it maps* and, if it narrows his discretion, *why*).
- **sim-constraint** — imposed by the simulator (fills, no L2, one position).
- **guardrail** — empirical safety rail, not from the canon.

| Rule (stable id) | Skill location | Canon cite | Type | Note / how it maps | Since |
|---|---|---|---|---|---|
| `select.5pillars_grade` | Step 0.5 grading | §2 pillars (`all_content_structured.md` §2, price/float/RVOL/gap thresholds) | direct + operationalization | Grades on the 4 *measurable* pillars from the meta line; catalyst & rate-of-change are unavailable → inferred. C = hard gate. **2.8.0 cand:** Grade B's "pass decisively" pinned to the two non-binary boxes — volume `green_vol ≥ 1.3× red_vol` (+ `rvol_bar ≥ 2.0` if populated), wick `h−c < (h−l)/4`; binary boxes pass at nominal values (previously a meta-instruction invited overriding true/false fields). 1.3×/¼ are **declared narrowing choices**, not canon numbers. | 2.2.0 |
| `entry.trigger_bar` | §A "Which bar is the breakout?" | §3.1 first-candle-new-high / ACD; §18 "let it break, hold, then enter" | operationalization | 1-min proxy for the 5-min ACD: trigger = **first revealed bar where every entry box is simultaneously true**. Removes the "which new-high bar?" ambiguity (LLM reproducibility). | 2.3.0 |
| `entry.volume_null_rvol` | §A volume-expansion box | §2 RVOL; §9 green-vol > red-vol | operationalization | `rvol_bar` is a trailing-20-bar ratio → null early; when null the **green>red dominance test is the volume gate**. Prevents missing the prime-window breakout. **2.8.0 cand:** window made exact — last **5 completed** bars (all revealed if <5), was "~5"; rvol threshold single-valued `≥ 1.5`, was "≳1.5–2×". MACD box also made strictly binary (`macd_hist ≥ 0`; "clearly negative" carve-out removed). | 2.3.0 |
| `entry.confirmed_close_vs_arm` | §A entry modes | §3.1 "the moment price breaks… I don't wait for the candle to close" | operationalization + sim-constraint | Armed buy-stop = his immediate-break entry (touch-fill at trigger); confirmed-close is the fallback when confirmation only completes on the bar. | 2.1.0 |
| `stop.initial_formula` | §A "Where the stop goes" | §3.1 / §22 "my stop is the low of that pullback, it's as simple as that" | operationalization | `stop = min(trigger-bar low, prior-bar low) − $0.01`. **Not a Cameron quote** — a 1-min two-bar-structure translation of "low of the pullback." **Narrows** his discretion to kill noise-tight stops that inflate size (see `IMPROVING.md` §7). `anchor_px` (5-min level) banned from placement. (An explicit confirmed-close-vs-armed scope note was drafted in 2.6.0 but **left out of the 2.7.0/2.8.0 decomposition** to avoid confounding the split — 2.4.1's existing wording already covers it; fold in only if a decomposed candidate is promoted.) | 2.4.0 |
| `size.risk_over_stop` | Step 3 | §5 "Position Size = Max $ Risk ÷ Risk per Share"; §20.1 stops are a $ cap | direct | `shares = min(risk_budget/stop_dist, buying_power/entry)`; wide stop ⇒ small size (accept it), not a tighter stop. | ≤2.0 |
| `manage.breakout_or_bailout` | §B per-bar procedure | §4 breakout-vs-bailout; "almost immediate resolution" | direct | Walk the priority list; act on the first item that applies. | ≤2.0 |
| `manage.soft_bailout_ladder` | §B.2 predicate ladder (a)–(d) | §4 breakout-or-bailout tree; §3.1 entry-candle-closes-green-and-above-level; §8.2 lost-VWAP; §4 "almost immediate resolution" time stop | operationalization | Objectifies the prose OR-chain into 4 ordered boolean predicates over revealed bars + own state: (a) failed break `c<break_level` while `k≤1`; (b) lost VWAP `c<vwap` while `k≥2`; (c) topping-tail (red, tested new high, `upper_wick≥2×body` and `≥0.5×stop_dist`); (d) time stop (`k≥5`, no new high, `<¼R` green). **Narrows** discretion for LLM reproducibility (see `IMPROVING.md` §2). MACD explicitly excluded from exits (§4 confirmation only). **2.7.0 cand (bug fix):** `break_level` for a confirmed-close entry = `avg_entry` (the 2.5.0 draft said "breakout bar's high", which made (a) fire on the fill bar itself — self-contradiction caught in external clarity review); `made_nh_since_entry` = any `k≥1` bar with `c >` entry-bar `h` (own arithmetic, not the tick's `new_high` flag, which is session-anchored and breaks for §C re-entries). | 2.5.0 |
| `manage.free_trade_be` | §B.3 | §4 "up at least 10 cents within the first minute → stop at break-even, free trade" | operationalization | Single predicate on every completed bar: `stop < avg_entry` ∧ `high_water ≥ avg_entry + min($0.10, stop_dist/3)` → stop to BE. **2.7.0 cand:** removed the fuzzy "first bar or two" window (contradicted the §B procedure list, which had none) and the unmeasured "price holds" condition — `high_water` touch is the whole test. | ≤2.0 |
| `manage.scale_thirds` | §B.4 | §4 / §10 scale out in thirds into strength | direct | 1/3 at ~+1R, 1/3 extended, runner. | ≤2.0 |
| `manage.runner_exit_5min` | §B.5 | §4 "first red candle that closes below the prior green candle's low"; §9/§20.8 5-min primary | operationalization | Runner exit judged on **rolling 5-min** candles (Cameron's primary chart), not every 1-min bar. **2.7.0 cand:** "prior green" pinned = **most recent completed green candle, skipping intervening reds** (literal reading of the canon phrase; the adjacency reading would create a dead zone where a 2-red collapse never fires the exit). | 2.1.0 |
| `manage.pyramid` | §B.6 | §10 scale into winners, never average down | direct | Add only to a green, confirmed continuation; re-anchor stop. | 2.1.0 |
| `reentry.sub_vwap_trap` | §C | §3.7 washout long; §8.2 sub-VWAP trap (his favorites) | direct | Reclaim-VWAP or fresh-base second leg; ≤1 re-entry. | 2.1.0 |
| `reentry.cooldown` | §C cooldown | §4 "I can always get back in if there's another setup" (not revenge) | operationalization + guardrail | ≥3 bars flat + fresh base before re-entry; kills same-chop revenge re-entry. **2.7.0 cand:** "fresh base" made checkable — above-VWAP closes (or, sub-VWAP trap: cooldown-bar lows hold ≥ tracked `washout_low`, replacing the undefined "completed washout structure") + the exact §A 5-bar green>red volume test. | 2.2.0 |
| `risk.time_of_day` | §A time box | §1/§17 first 2 hrs prime; stop by ~10:30–11:00; never fresh after 12:00 | direct + operationalization | **2.8.0 cand:** numeric ladder — `<10:30` pass; `10:30–<12:00` only on an **A+ bar** (all boxes + `rvol_bar ≥ 2.0`; previously "A+" was undefined and the window was a 30-min range); `≥12:00` hard fail. The 10:30 cut and 2.0× floor **narrow** Cameron's "~10:30–11:00" range to one number for reproducibility. | ≤2.0 |
| `execution.intent_contract` | 3.0 "Execution model" + logging | — | sim-constraint | **3.0.0 cand:** agent records order intent only; recorder validates the revealed tick and derives all fills/shares. Prevents agent-selected prices or size from entering P&L. | 3.0.0 cand |
| `fill.model` | §A/§B execution model | — | sim-constraint | v2.x: hard levels touch-fill with no costs. **3.0.0 cand:** configured slippage/commission, buying-power and volume-participation caps, gap-aware stops; an OHLC bar that reaches stop and target resolves stop-first, and an armed entry/stop same-bar path resolves entry then stop. This is a **major** rebaseline. | 3.0.0 cand |

## When a rule has no clean canon cite

If a proposed rule can't cite the canon, it is a **guardrail** (label it so) or it
doesn't belong. Do not smuggle a fitted 100-set threshold in as "Cameron."
