# TRADE_SIMULATOR experiment log

One row per behavioral version: the hypothesis, the batch that tested it, the paired
result vs its baseline, and the promote/revert decision. Keeps future maintainers from
re-trying dead ends. Append newest at the top. See `IMPROVING.md` for the protocol.

Columns: **version** · **hypothesis** · **baseline→candidate batch tags** ·
**paired ΔR / sign-p** (`batchsim compare`) · **decision**.

---

### 5.12.0 — scanner-event-close causality correction  ⏳ VALIDATED WIRING — NOT PROMOTED
- **Why:** the market-data contract uses left-labelled five-minute bars. A
  scanner breakout labelled `09:35` is computed from the `09:35`–`09:39`
  interval, so it cannot be available at `09:35`. The earlier scanner-event
  candidates released that information four minutes early.
- **Change:** private indicator/5m warm-up still begins at 09:30, but a scanner
  event is released only on the completed bar's final minute (`09:39` for a
  `09:35` label). The event records its source time separately and excludes the
  historical prose reason, which embeds a non-PIT float snapshot. The entry,
  brackets, and management rules are otherwise unchanged from 5.11.
- **Data audit:** gap and RVOL are computed from the open and prior daily bars;
  the 5m detector is sequential and its volume/VWAP features are backward-only.
  Float remains a current snapshot in scanner selection, so this is a
  **conditional historical replay**, not a proof of a fully point-in-time
  universe. v5.12 does not consume float or the withheld prose reason in its
  decision policy.
- **Residual OOS:** all **12** unused regular-hours `(ticker,date)` rows left
  after excluding every prior Warrior test set were sealed as
  `testset_5x_causal_oos_12.json`. Batch
  `warrior-5.12.0-causal-close-oos12-final-20260723` completed **12/12**, had
  zero audit voids, traded **1/12**, and produced **+$10.23 / +0.02 effective
  R per setup**. The two-worker reproduction had byte-identical streams and
  decision logs, the same P&L, and zero audit voids.
- **Management-only diagnostic:** on the already-contaminated 100-row panel,
  restrict the 3.0 vs 5.11 comparison to the 15 setups with identical entry
  minute and average fill. v5.11 realized **8.78R** versus 3.0's **9.18R**
  (−0.40R); runner handling on JEM was the largest deficit, while v5 improved
  DTSS and STEM. This does not justify a rule edit on the inspected panel.
- **Decision:** retain the causal replay contract and do **not** promote any
  v5 candidate. The valid residual sample is only one trade, and the principal
  performance difference remains entry participation rather than management.
  Expand the point-in-time scanner universe before the next selection test.

### 5.10.0–5.11.0 — scanner-event immediate timing decomposition  ⚠️ TIMING-OPTIMISTIC — NOT PROMOTED
- **Why:** aligned 3.0/5.8 analysis showed 3.0 entered 0–4 minutes after the
  scanner event. 5.8's strict three-prior-five-minute gate routinely entered
  20–35 minutes late. 5.10 removed that delay with a five-minute 1m
  confirmation window.
- **5.10 test:** `warrior-5.10.0-immediate-dev100u-20260723`: **+$582.00 /
  +0.146 effective R per setup, 72 trades**, zero audit voids. Per-delay
  analysis isolated the decisive refinement: event-minute entries were +22.76R
  over 21 trades, while entries delayed 2–3 minutes lost −4.60R.
- **5.11 change:** permit a scanner-confirmed entry only on the scanner event
  minute; do not chase a later one-minute confirmation. It retains causal
  private warm-up, current price/VWAP/MACD/new-high checks, a one-minute
  structural stop, deterministic brackets, and deterministic exits.
- **Development:** `warrior-5.11.0-event-minute-dev100u-20260723`: **+$773.46
  / +0.194 effective R per setup**, 21 trades, 57.1% wins, zero audit voids.
  This is materially better than 5.10 but below the historical clean 3.0
  panel (+$988.08 / +0.25), whose agent runner has a different contract.
- **Untouched holdout:** `warrior-5.11.0-event-minute-holdout27-20260723`:
  **+$93.08 / +0.086 effective R per setup**, 4 trades, 75% wins, zero voids.
  A single-worker rerun was semantically identical across decisions, actions,
  and P&L and also voided zero leaves.
- **Causality correction:** the scan detector consumes left-labelled completed
  five-minute bars, but these versions exposed the resulting event at the bar's
  label rather than its close. Their results are useful timing diagnostics only,
  not valid causal performance evidence; v5.12 supersedes their event-release
  contract.
- **Decision:** ❌ do **not** promote. Preserve the results for diagnosis only;
  evaluate future candidates under v5.12's bar-close release contract.

### 5.8.0 — private warm-up / scanner-event-first candidate  ⏳ SMOKE-VALIDATED — NOT PROMOTED
- **Why:** 5.7 correctly delayed the scanner data until its trigger minute, but
  still exposed the full 09:30→trigger tape to the policy. That is not direct
  scanner parity: a real scanner-selected workflow begins making decisions when
  the scanner fires.
- **Change:** pre-trigger minutes now warm indicators and completed-five-minute
  structure privately. The first published decision tick is the scanner event
  itself (`i=0`); it includes the trigger, RVOL, and reason. All subsequent
  scoring remains the same deterministic v5.7 policy.
- **Test:** replay regression proves the first visible tick is the scanner event
  while causal warm-up is retained. `warrior-5.8.0-scanner-start-smoke-20260723`
  completed 10/10 leaves: 3 trades, +$23.10 / +0.06 effective R per setup, no
  audit voids. Persisted-stream validation found zero leaves with a pre-event
  visible tick.
- **Decision:** ⏳ hold; this is the correct contract for a broad 3.0 parity
  evaluation, not a profitability claim.

### 5.7.0 — causal scanner-event parity candidate  ⏳ SMOKE-VALIDATED — NOT PROMOTED
- **Why:** 3.0 received the scanner event itself (timestamp, trigger level,
  RVOL, and reason), while 5.x only received a scanner-selected ticker/date and
  had to rediscover the event from the open. This made their entry contracts
  materially different.
- **Change:** v5.7 still begins at 09:30 with neutral metadata, but releases a
  one-time `scanner_event` only on its recorded trigger minute. The policy
  stores that event causally, refuses all entries before it, and requires price
  to remain at or above its trigger alongside deterministic confluence scoring.
- **Causality test:** replay regression proves no scanner event exists before
  the trigger tick. In the 10-row smoke, all three entries occurred after their
  persisted scanner events; zero leaves were voided by audit.
- **Smoke:** `warrior-5.7.0-scanner-event-smoke-20260723`: 3 trades, +$23.10
  / +0.06 effective R per setup. This is only a wiring/correctness smoke,
  not a comparison or promotion result.
- **Decision:** ⏳ hold. Run the larger development panel before interpreting
  profitability or comparing with 3.0.

### 5.3.0–5.6.0 — high-score/early-only selection sweep  ❌ REJECT — HOLDOUT NO-TRADE
- **Development sequence:** Starting from the complete-five-minute contract,
  5.2 limited entries to before 10:00 ET; 5.3 raised the score floor to 85;
  5.4 raised it to 90; 5.5 raised exit-pressure from 50 to 70; and 5.6 tested
  80. Every batch used the same pinned 100-row `testset_100u.json` and a
  deterministic no-LLM runner.
- **Development results:** 5.2: −$14.60 (19 trades); 5.3: −$0.44 (14);
  5.4: +$66.09 / +1.65R (4); 5.5: **+$81.07 / +2.03R (4)**; 5.6: +$70.19
  / +1.76R (4). The 5.5 single-worker rerun was semantically identical for
  decisions, actions, and P&L across all 100 leaves. A full batch audit voided
  zero leaves.
- **Holdout:** the untouched `testset_5x_holdout_27.json` is the 27-row
  difference between `testset_100.json` and the 100u development panel. On
  `warrior-5.5.0-holdout27-20260723`, 5.5 stood down on **27/27** and earned
  **$0.00 / 0.00 effective R**. Its audit also voided zero leaves.
- **Decision:** ❌ **REJECT / DO NOT PROMOTE.** The development gain came from
  an entry filter too selective to demonstrate out-of-sample participation.
  3.0.0 remains the active strategy. Retain the deterministic replay and
  complete-five-minute reliability work, but do not claim that any v5 setting
  is more profitable or more reliable than 3.0.0.

### 5.2.0 — early-session entry selection  ✅ DEV-PANEL IMPROVEMENT — HOLDOUT PENDING
- **Why:** on the 100-row from-open deterministic 5.1.0 development panel, the
  09:xx entry cohort averaged +0.042R/trade while the 10:xx cohort averaged
  −0.073R/trade. This is a narrowly scoped timing-selection hypothesis, not a
  claim that late-morning breakouts are intrinsically invalid.
- **Change:** retain the v5.1 complete-five-minute feed contract, all entry-score
  weights, brackets, stops, scales, and exits; prohibit new entries at or after
  10:00 ET. Existing positions still receive the unchanged management policy.
- **Test:** `warrior-5.2.0-dev100u-before1000-20260723`, exact same 100-row
  `testset_100u.json`, deterministic no-LLM runner: **19 trades, 81 stand-downs,
  −$14.60 / −0.004 effective R per setup**, versus v5.1's 47 trades, 53
  stand-downs, **−$56.43 / −0.014**. The 28 deliberately omitted v5.1 trades
  summed **−$41.83 / −1.05R**; the 19 retained leaves had byte-identical outcomes.
  The runner contracts differ by design, so `batchsim compare` correctly does
  not treat this as a formal paired statistical result.
- **Decision:** ✅ retain as the current development branch; **do not promote**.
  It still loses on the full panel and needs further isolated development work,
  followed by the untouched 27-name holdout and reproducibility audit.

### 5.1.0 — complete-five-minute data contract  ✅ RELIABILITY FIX — NO ALPHA CLAIM
- **Why:** legacy replay could label a clock-aligned five-minute candle complete
  even when a constituent 1-minute bar was absent. That lets a causal policy act
  on synthetic structural evidence.
- **Change:** emit an eligible 5-minute candle only if all five constituent
  minutes are observed; preserve legacy behavior unless a skill opts into this
  contract.
- **Test:** replay regression coverage for gapped buckets plus
  `warrior-5.1.0-dev100u-complete5m-20260723`: 47 trades, **−$56.43**, versus
  v5.0's 54 trades, **−$49.98**. It rejected seven gap-dependent v5.0 trades;
  their net result was +$5.26, so the integrity correction is not an alpha win.
- **Decision:** ✅ keep the feed contract for every later candidate because it is
  required for valid backtests; do not cite it as performance improvement.

### 5.0.0 — deterministic Warrior pattern policy  ⏳ MAJOR CANDIDATE — NOT YET VALIDATED
- **Why:** the 4.1 DRUG smoke exposed two separable problems: the agent entered
  before three prior five-minute candles actually existed, and it stopped while
  long, allowing a forced end-of-day close to appear as a large profitable result.
  More broadly, identical indicator/pattern evidence should not produce different
  entry, bailout, or scale decisions from one model run to another.
- **Change:** `warrior_pattern_score_v1` moves the 4.1 entry and exit cards into a
  causal Python state machine. It makes one entry attempt, attaches engine-owned
  +1R/+2R thirds, promotes the stop to break-even mechanically, repeats capped
  exits until flat, and forces a policy-authored flat intent by 15:55. Batchsim
  uses the no-agent deterministic-policy runner and exact replay audit.
- **Data compatibility:** a new opt-in `strict_prior_three_context` field publishes
  `prior_3_count` and withholds all `prior_3_*` aggregates until count three.
  Sealed 4.x versions retain their legacy stream contract.
- **Type:** major decision-path and execution-interface rebaseline. Pattern weights
  and 75/50 thresholds remain experimental guardrails, not Cameron numbers.
- **Test:** focused/unit integration passed; cached DRUG smoke entered only after
  three true prior 5-minute bars, exited by policy (not forced), and repeated with
  byte-identical decisions: +$86.42 / +2.16 planned R. On the exact 10-row
  `testset_isolation_smoke_10u.json` bytes, 5.0 traded 5 and stood down on 5:
  +$23.11 / +0.058 effective R per setup versus the historical clean 3.0
  contract-smoke's +$213.23 / +0.534. Paired mean delta was −0.476R/setup;
  5 improved / 5 worsened / 0 tied, sign-p 1.0. The two largest deficits were
  stand-downs on 3.0 winners DTSS (+1.62R) and GRPN (+2.22R). One 3.0 OLOX
  winner (+3.08R) used a forced 15:59 close; even treating that leaf as 0R leaves
  3.0 ahead (+0.226 versus +0.058 effective R).
- **Comparison caveat:** batchsim correctly refuses its formal paired comparison
  because 3.0 is an agent runner beginning at the recorded trigger while 5.0 is
  deterministic and starts at the open. The shared test-set hash makes this a
  useful end-to-end diagnostic, not a controlled policy-only estimate.
- **Decision:** ⏳ HOLD / DO NOT PROMOTE — deterministic reproducibility is proven,
  but this 10-name diagnostic gives no performance evidence for replacing 3.0.0.
  Keep 3.0.0 active; next isolate the missed-winner gates or run the full 100-row
  descriptive panel before changing thresholds.

---

### 4.1.0 — deterministic candlebars + entry/exit confluence scoring  ⏳ SAMPLE CANDIDATE — NOT YET VALIDATED
- **Why:** the transcript teaches reading repeatable price patterns together with
  volume, VWAP, EMA, and MACD, while treating topping tails and failed breakouts as
  management evidence. Leaving those shapes to free-form model vision would make
  identical OHLCV bars produce non-reproducible evidence.
- **Change:** opt-in replay context now emits causal deterministic events for
  candle-over-candle, micro-pullback break, bull-flag break, bearish topping tail,
  and bearish breakout failure on completed 1-minute and 5-minute bars. The 4.1
  skill retains every 4.0 completed-5-minute hard entry gate, then requires a
  documented 75/100 pattern-volume-trend-candle-time score. Management preserves
  the immediate failed-break bailout and adds a 50/100 exit-pressure score that
  combines bearish geometry with VWAP, red-volume, MACD, or stalled-price evidence.
- **Type:** experimental operationalization + replay contract. Detector quality is
  explicitly geometry in `[0,1]`, not probability; correlated patterns do not
  stack. The 75/50 thresholds and weights are engineering hypotheses, not Cameron
  quotes, and must not be tuned against the known 100-set.
- **Compatibility:** `candlebar_context` is frontmatter-opt-in. Historical versions
  receive their original JSON stream, so their sealed behavior does not change.
- **Test:** focused unit/regression coverage plus a cached replay smoke test. Next,
  run a paired repeated 4.0.0 → 4.1.0 batch on the pinned set, inspect decision-score
  distributions and event frequency, then validate any retained hypothesis on a
  disjoint holdout.
- **Decision:** ⏳ HOLD — sample candidate only; 3.0.0 remains the active baseline.

---

### 3.4.0 — parametrized §C re-entry budget + cutoff time  ⏳ CANDIDATE — NOT YET VALIDATED
- **Why:** §C hard-capped re-entries at **one** and stopped the loop the moment the
  agent went flat after using it, so a choppy morning with several distinct A-setups
  could only ever produce two round trips. We want to *measure* whether allowing more
  second-leg entries (bounded by the clock) helps or just adds churn.
- **Change:** the re-entry cap and a trading cutoff are now **run parameters**, not skill
  constants. Skill §C, the loop-stop rule (b), the state var, and the guardrails read an
  injected **budget** (`re_entries_used` caps at it; default **1**) and optional **cutoff
  time** (no new/re-entry at/after it). `batchsim run` gains `--max-reentries N` and
  `--trade-until HH:MM` (with `--no-reentry` = `--max-reentries 0`); both are recorded in
  `batch.json` and inherited on `--resume`. **No entry/exit/sizing/friction rule changed.**
- **Parity anchor:** with `--max-reentries 1` and no cutoff, 3.4.0's behaviour is intended
  to be identical to 3.0.0 — that equivalence is the first thing to verify before testing
  a raised budget.
- **Type:** capability generalization + simulator/CLI plumbing; the re-entry *count* moves
  from a hardcoded skill constant to a run knob. Not an alpha-rule tweak.
- **Test:** ⏳ pending. First confirm `--max-reentries 1` ≈ 3.0.0 on the shared 100-set,
  then sweep budget/cutoff (e.g. 3 until 11:30) as its own paired comparison.
- **Decision:** ⏳ HOLD — 3.0.0 remains the active baseline.

### 4.0.0 — from-open, completed-five-minute entry  ⏳ CANDIDATE — NOT YET VALIDATED
- **Why:** v3 supplied the agent with the scanner's historical five-minute trigger
  time, level, final-day RVOL, and retrospective reason, then began replay at that
  trigger. That is not how a trader experiences a scanner-selected name.
- **Change:** the scanner still selects the ticker/date (its point-in-time selection
  work remains deferred), but the trader starts at 09:30 ET. The visible meta stream
  hides scanner `entry_time`, `entry_px`, `anchor_px`, final-day `rvol`, and reason.
  It exposes one sequential minute at a time and an authoritative completed
  clock-aligned five-minute candle at `:04/:09/...`. The only entry is a completed
  five-minute break of the preceding three completed candles, with green upper-third
  close, above-VWAP, 1.5× five-minute volume, and non-negative MACD.
- **Guardrails:** recorder rejects an entry that is not on a completed five-minute
  candle; 4.0 forbids armed entries, adds, and re-entries. A flat agent must observe
  through 11:00 ET before it may stop.
- **Known limitation:** this removes trigger knowledge from the trading session but
  does **not** alter scanner selection or solve its whole-day-volume leakage. That
  point-in-time scan/replay parity work remains intentionally deferred.
- **Test:** establish a new 4.0.0 repeated control panel. Do not compare its raw P&L
  to 3.0.0: the information/timing contract changed, so this is a major rebaseline.
- **Decision:** ⏳ HOLD — 3.0.0 remains the active baseline.

---

### 3.3.0 — engine-managed starter/add pyramid  ⏳ CANDIDATE — NOT YET VALIDATED
- **Why:** diagnostics across the three 3.0.0 DeepSeek control runs found only two
  filled adds total. The written pyramid rule is effectively absent because an
  agent has only one management intent per bar and stop/scale actions consume it.
- **Change:** every entry carries a mandatory plan: about one-third starter size,
  then at most two equal-share engine adds. Add #1 is queued after a green close
  above actual average entry; add #2 after a green new-high continuation with
  supportive MACD and volume. An add fills at the next open only while above average
  entry. After every add the engine raises the stop as necessary to keep the whole
  position within the original $40 open-risk cap. Stops, scales, and discretionary
  exits cancel the plan; the agent cannot submit a competing `ADD_CLOSE`.
- **Type:** canon-grounded operationalization of the three-step pyramid; a
  deterministic execution/position-plan change, not a fill-model relaxation.
- **Test:** unit coverage covers starter sizing, delayed next-open adds, no averaging
  down, stop re-anchoring under the risk cap, and required intent validation.
  **Next:** run three DeepSeek candidate batches and compare their panel with the
  three-run 3.0.0 control through `compare-repeats`.
- **Decision:** ⏳ HOLD — 3.0.0 remains the active baseline.

---

### 3.2.0 — $3 minimum entry price  ⏳ CANDIDATE — NOT YET VALIDATED
- **Why:** the v3 dev baseline's 23 below-$3 trades produced −$45.49 / effective
  R −0.048. The $3–$5 and $5–$10 bands were positive. Low-priced shares face a
  larger percentage burden from the one-cent tick, per-share fees, and adverse
  slippage.
- **Change:** one selection rule only: Grade C / stand down when `entry_px < $3`.
  The existing $20 upper bound, RVOL gate, entry and exit rules, deterministic
  fill model, participation cap, buying power, and $40 risk budget are unchanged.
- **Type:** empirical guardrail, not a claimed Cameron threshold. The known 100-set
  was used to form this hypothesis, so it is dev evidence only.
- **Test:** run the same pinned 100-set against 3.0.0, then require a disjoint
  holdout before promotion.
- **Decision:** ⏳ HOLD — 3.0.0 remains the v3 control.

---

### 3.1.0 — engine-managed entry brackets  ❌ REJECTED
- **Why:** the 3.0.0 management contract permits one intent per bar. A break-even
  `SET_STOP` can therefore delay a `SCALE_LIMIT` until after its +1R/+2R level has
  already traded. In the stamped v3 dev baseline (`3.0.0-20260710201028`), 30/56
  scale intents were placed after their target traded; four never filled. This is
  an execution-interface defect, not a thesis to weaken fills or filters.
- **Change:** `ENTER_CLOSE` and `ARM_BUY_STOP` now carry a standard bracket intent:
  one-third at +1R and one-third at +2R. After the actual, cost-adjusted fill, the
  engine derives target prices from that fill plus the structural stop, fixes each
  tranche from the original filled position, and activates them only on the next
  bar. A later stop update does not delay/cancel the targets. Target/stop ambiguity
  remains stop-first; volume caps, fees, slippage, buying power, and gap-aware stop
  behavior are unchanged.
- **Type:** execution-interface correction / simulator constraint implementing the
  existing scale-in-thirds canon rule; this is not a scanner, selection, or friction
  model change.
- **Test:** paired 3.0.0 `3.0.0-20260710201028` → 3.1.0
  `3.1.0-20260710211138`, 100 shared setups: mean ΔR **−0.037**, median 0,
  24 better / 26 worse / 50 unchanged, sign-p **0.8877**, P&L **$838.47 vs
  $988.08**. Zero voids in both batches; candidate stood down 11 versus 7.
- **Decision:** ❌ **REJECT.** The fixed +1R/+2R bracket did not improve the
  baseline. Keep 3.0.0 as the control; do not retry this exact rule.

---

### 3.0.0 — deterministic OHLC execution baseline  ✅ PROMOTED
- **Why:** prior sessions let the executing model supply its own fills, shares, and
  stops. That makes P&L dependent on unverified agent arithmetic and permits
  impossible OHLC fills, unbounded participation, and hidden stop-gap risk.
- **Change:** the candidate skill at `trade_skills/3.0.0.md` records intent only
  (`ENTER_CLOSE`, `ARM_BUY_STOP`, `SET_STOP`, `SCALE_LIMIT`, `ADD_CLOSE`,
  `EXIT_CLOSE`). `execution.py` derives size from planned risk/buying power/bar
  volume, applies commissions/slippage, uses gap-aware stops, and resolves an
  OHLC bar that can hit both a target and a stop as **stop first**. `recorder
  resolve` exposes the authoritative state after every revealed tick.
- **Type:** simulator/execution-model change, not an alpha-rule tweak. It is a
  **major rebaseline**: all pre-3.0 reported-fill R comparisons are incommensurate.
- **Test:** deterministic unit coverage covers stop gaps, same-bar armed
  entry/stop ambiguity, stop-vs-target ambiguity, buying-power/participation
  sizing, and recorder rejection of agent-supplied fills. Three clean DeepSeek
  baseline batches on the same 100-set completed at $988.08, $836.01, and
  $751.42 with zero voids. This establishes substantial normal agent variation.
- **Decision:** ✅ **PROMOTE as the active default baseline on 2026-07-11.**
  2.4.1 remains the historical reported-fill v2 baseline; it must not be used to
  rank future deterministic-OHLC candidates. Future v3 candidates must be
  evaluated against repeated 3.0.0 DeepSeek runs, not a single lucky run.

### 2.7.0 / 2.8.0 — decompose the 2.6.0 REJECT into its two halves  ⏳ CANDIDATES — NOT YET VALIDATED
- **Why:** 2.6.0 (bundle) was REJECT (mean ΔR −0.046, more stand-downs). It conflated
  two independent changes; the gate can't attribute the regression. Both are rebuilt
  **off 2.4.1** (the accepted baseline) so `2.7.0 ⊕ 2.8.0 ≈ 2.6.0` — a clean partition.
  The `break_level` bug fix rides in 2.7.0 (it's a correctness fix, part of the ladder).
- **2.7.0 = 2.4.1 + EXIT-side only** (`archive/TRADE_SIMULATOR@2.7.0.md`): the §B.2
  4-predicate soft-bailout ladder (a failed-break `c<break_level` / b lost-VWAP / c
  topping-tail / d time-stop), `break_level`+`made_nh_since_entry` state, free-trade BE
  as an every-bar predicate, runner "prior green" = most-recent-completed-green, washout
  `washout_low` tracking. **Entry checklist is verbatim 2.4.1** (fuzzy ~5-bar volume,
  ≳1.5–2× rvol, "clearly negative" MACD, "A+ bar", Grade-B "decisively" all unchanged).
  *Isolates: do crisper EXITS alone help?* Hypothesis: cuts avg loser without the
  stand-down drag 2.6.0 added.
- **2.8.0 = 2.4.1 + ENTRY-side only** (`archive/TRADE_SIMULATOR@2.8.0.md`): exact 5-completed-bar
  volume window, single `rvol_bar ≥ 1.5`, numeric time ladder with **A+ = all boxes +
  `rvol_bar ≥ 2.0`**, strictly-binary MACD box, Grade-B "decisively" → `green_vol ≥ 1.3×
  red_vol` + wick `< (h−l)/4`. **Manage/exit is verbatim 2.4.1** (prose OR-chain, no
  ladder). *Isolates: does tighter entry SELECTION alone pay for its extra stand-downs?*
- **Test:** ⏳ pending. Each needs its §4.1 clarity-review pass, then `compare --a
  2.4.0-20260708181528 --b <cand-batch>` (100-set, deepseek-v4-flash). Whichever half
  (if either) shows mean ΔR > 0 broadly is the keeper; then consider recombining the
  winners. **2.4.1 remains the accepted baseline.**
- **Decision:** ⏳ HOLD — both are un-validated candidates; live skill stays at 2.4.1.

### 2.6.0 — clarity-review fixes (external LLM review of the skill text)  ⏳ CANDIDATE — NOT YET VALIDATED
- **Source:** an executing-model clarity review (prompt: `peer_reviews/skill_clarity_review_prompt.md`)
  returned 14 findings; all were judged genuine, ~half of the suggested fixes were modified.
- **Bug fix (the big one):** 2.5.0's `break_level` for a confirmed-close entry was defined as
  "the breakout bar's high" → ladder (a) `c < break_level` fired **on the fill bar itself**
  (`c < h` on any wicked candle). Now `break_level = avg_entry` for confirmed-close
  (`armed_trigger` for armed fills, where k=0 firing is correct).
- **Definitions pinned (were fuzzy → now single-reading):** `made_nh_since_entry` = any `k≥1`
  bar `c >` entry-bar `h` (not the session-anchored `new_high` flag); volume window = exactly
  the last 5 completed bars; `rvol_bar ≥ 1.5` (was "≳1.5–2×"); time gate = `<10:30` /
  `10:30–<12:00` A+ only / `≥12:00` never, with **A+ defined** (all boxes + `rvol_bar ≥ 2.0`);
  MACD box strictly binary (dropped "clearly negative"); free-trade BE = every-bar predicate
  `high_water ≥ avg_entry + min($0.10, stop_dist/3)` (dropped "first bar or two" + "price
  holds"); Grade B "decisively" = green_vol ≥ 1.3× red_vol + wick < ¼ range, binary boxes at
  nominal; runner "prior green" = most recent completed green 5-min candle (skip reds);
  re-entry "washout structure" = cooldown lows hold ≥ tracked `washout_low`; stop formula
  scoped to confirmed-close (armed keeps arm-time stop).
- **Rejected from the review:** 10%-parity caution flag (new tuned threshold); 2-consecutive-bar
  MACD entry rule (new rule, no canon warrant for entries); tick-`new_high` for
  `made_nh_since_entry` (breaks re-entries); adjacency reading of "prior green" (dead zone);
  "rvol ≥ 1.5 also satisfies" re-entry loosening.
- **Test:** ✅ **ran** (2026-07-09). `compare --a 2.4.0-20260708181528 --b 2.6.0-20260708224608`,
  100-set, deepseek-v4-flash, 94 paired keys: **mean ΔR −0.046, median +0.000, better/worse/≈
  17/30/47, sign-p 0.079, tail-guard top-3 = 55% of +ΔR (JEM +3.99 dominates).** Guardrails:
  avg loser **improved $−15→$−12**, but **stood-down rose 10→14**; void 1/1.
- **Decision:** ❌ **REJECT — 2.4.1 stays the accepted baseline.** Diagnosis (§7 pattern): the
  objectified exits *did* cut loser size, but (a) tighter entry gates (Grade-B "decisively"
  thresholds, A+ `rvol≥2.0`, binary MACD) raised stand-downs, booking some winners as 0R, and
  (b) 30 worse vs 17 better with only +4 stand-downs ⇒ most damage is the ladder **exiting
  trades earlier for less R** — clipping runners to save on losers, net slightly negative.
  The `break_level` bug fix and the de-ambiguification remain *correct*; they just don't lift
  expectancy as a bundle. **Next:** decompose — isolate the bailout-ladder (minus the entry-gate
  tightening) from the entry-gate changes, so we learn which half hurt (see BACKLOG 3A follow-up).
  2.6.0 stays archived as a REJECTED candidate; do not run it live.

### 2.5.0 — objectify the §B.2 soft-bailout OR-chain  ⚠️ SUPERSEDED by 2.6.0 (never batched; contained the `break_level` bug above)
- **Hypothesis:** after entry (2.3.0) and stop (2.4.0) were objectified, the last big
  feel-call multiplying R is the manage-step-2 exit. The prose OR-chain ("failed break /
  lost VWAP / topping tail / MACD rollover / time stop") let two runs disagree on *whether
  the break failed*, producing different exits from the same tape. Replace with an **ordered
  4-predicate ladder** over revealed fields + own state — (a) failed break `c<break_level`
  (`k≤1`); (b) lost VWAP `c<vwap` (`k≥2`); (c) topping-tail (red + tested new high +
  `upper_wick≥2×body` and `≥0.5×stop_dist`); (d) time stop (`k≥5`, no new high, `<¼R` green).
  MACD removed as a stand-alone exit (§4 confirmation only). New state: `break_level`,
  `made_nh_since_entry`.
- **Expected delta:** lower run-to-run exit variance; fewer premature MACD-noise bails
  (should *help* MFE-capture / median R); crisper failed-break exits (should cut avg loser).
- **Test:** ⏳ **pending.** Requires a paired 100-set batch vs the 2.4.x baseline through
  `batchsim compare` (blocked: hermes out of credits as of 2026-07-08). **2.4.1 remains the
  accepted baseline until this passes the gate.** Archived at `archive/TRADE_SIMULATOR@2.5.0.md`.
- **Decision:** ⏳ HOLD — do not treat as promoted; run `compare --a 2.4.x-<batch> --b 2.5.0-<batch>` first.

### 2.4.1 — fix broken canon path + report hygiene (non-behavioral)
- **Change:** point the skill's strategy-doc reference at the real path
  `library/ross_cameron/all_content_structured.md` (was a broken
  `library/analyst_warrior_trading_strategy.md`). No trading-decision change.
- **Test:** none required (reference/patch fix). Not a promotion event.
- **Decision:** keep.

### 2.4.0 — objective stop placement
- **Hypothesis:** the residual entry-price variance (after 2.3.0) lived in stop
  placement — "just-under-breakout-level" vs "under-entry-bar-low" gave 14× different
  size/R from the same entry. Replace with `stop = min(trigger low, prior low) − $0.01`.
- **Test:** baseline `2.2.1-20260707225900` → candidate `2.4.0-20260708181528`,
  100-set, model deepseek-v4-flash. `batchsim compare`:
  **mean ΔR +0.249, median +0.01, 42/20/34, sign-p 0.0071, tail-guard top-3 = 22%.**
  Guardrails: avg loser −$15 vs −$18; void 1 vs 0; stood-down 10 vs 12.
- **Decision:** ✅ **PROMOTE.** First broad, significant, non-tail-driven win.
  (Note: the 2.2.1 baseline here is the clean 100-set batch, not the lucky 30-set run.)

### 2.3.0 — objective entry trigger + null-rvol fix
- **Hypothesis:** entry-timing variance (one run enters bar 3 tight-stop, another chases
  bar 13 wide-stop) came from an undefined "first clean new high" and a null-`rvol_bar`
  trap. Define the trigger as the first bar all boxes align; don't fail the volume box on
  a null rvol.
- **Test:** measured on the 30-set only (pre-`compare`) — not a promotable comparison by
  the current gate; the effect was later confirmed inside the 2.4.0 vs 2.2.1 100-set run
  (CPSH −0.27R → reliable win). Kept as a stepping stone; superseded by 2.4.0.
- **Decision:** keep; folded into the 2.4.0 evaluation.

### ≤2.2.1 — pre-methodology
- 2.0.x–2.2.1 were evaluated on 30-set eyeballing before the paired gate existed. Their
  relative ranking is **not trustworthy** (tail-driven; see `IMPROVING.md` §10). Treat
  2.2.1 as the accepted baseline that 2.4.0 beat on the 100-set.
