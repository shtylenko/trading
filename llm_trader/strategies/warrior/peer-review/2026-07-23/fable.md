# Peer Review: Warrior v4/v5 — Fable

**Method note:** rather than reason only from the prompt's own framing, I read the
implementation directly — `screen.py`, `floats.py`, `patterns.py`,
`candlebars/detectors.py`, `step.py`, `replay.py`, `execution.py`, `policy.py` (+
`policy_v2`…`policy_v11`), `indicators.py`, `skills/CHANGELOG.md`, `skills/RULE_TRACE.md`,
`skills/IMPROVING.md`, the Cameron canon, and the actual `batch/warrior/testset_*.json`
files (to check the 100/27/12-row disjointness claims by set difference, not by trusting
the prose). Line numbers below are real, not illustrative. Where I disagree with the
document's own framing or go further than it does, I say so explicitly.

---

## 1. Three most serious validity problems, ranked

### Rank 1 — The float gate is a survivorship filter dressed as a universe-selection caveat

The document already flags non-PIT float as "the principal unresolved data limitation,"
but frames it as float *magnitude* drift (a stock's float today isn't its float in 2024).
That's true, but the code contains a second, sharper mechanism that's easy to miss and
that the document doesn't call out:

- `FloatCache.passes()` (`floats.py:53-64`) treats an **unknown** float as a **hard fail**
  when a gate is active: *"Cameron will not trade a name he can't confirm is low-float."*
- `_fetch_float()` (`floats.py:81-98`) queries **current** `yfinance` info. If
  `floatShares` is absent it falls back to `sharesOutstanding` (`floats.py:93-95`), which
  is systematically larger than true float (it includes insider/restricted shares) — this
  biases toward *false exclusion* of exactly the extreme-low-float names Cameron's edge
  targets.
- The cache has a 30-day TTL (`floats.py:22`) and **is not versioned per scanner run** —
  there is no snapshot-date field recorded alongside each scanner row, so which float
  value gated a given historical `(ticker, date)` row depends on when the scan happened
  to be run, not on the date being replayed.

Put together: any small-cap ticker that has since been delisted, gone bankrupt, been
acquired, reverse-merged, or otherwise dropped out of a live data provider's coverage is
very likely to return no usable `yfinance` info today — and is therefore **hard-excluded
from the historical universe**, regardless of what its float actually was on the
historical date. This is not merely "float drifted" (bidirectional, arguably random-ish
noise); it is **directional**: the surviving universe is biased toward names that are
still listed and still liquid enough for a live retail data API to describe them today.
For a strategy whose entire thesis is "extreme moves in obscure, often short-lived
micro-caps," this is close to worst-case survivorship bias, and it contaminates every one
of the 139 regular-hours rows, not a distinguishable subset. I'd rank this above the
magnitude-drift framing in the document because it changes the character of the bias from
"noisy" to "one-directional and probably large."

### Rank 2 — The evaluation budget is smaller than stated, and it is still shrinking

The document is honest that 127/139 rows were consumed by development, leaving 12. I
verified this directly: `testset_100u.json` (100), `testset_5x_holdout_27.json` (27), and
`testset_5x_causal_oos_12.json` (12) are pairwise disjoint by ticker/date key. So the
127/12 split is real.

What the document doesn't say — and what I think is the sharper point — is that the
27-row "holdout" was itself **queried twice** across the version history, not once:

- v5.5.0 used it to fail the high-score sweep: *"5.5 stood down on 27/27 ... $0.00 / 0.00
  effective R"* (`CHANGELOG.md`, 5.3.0–5.6.0 entry).
- v5.11.0 later re-used the *same file* and reports it as an *"Untouched holdout"*
  (`CHANGELOG.md`, 5.10.0–5.11.0 entry) producing +$93.08 / +0.086R on 4 trades.

`IMPROVING.md` §6 already has a quarantine rule: *"if you opened a setup's chart/decisions
to form a hypothesis, that setup is dev forever and cannot count as holdout evidence for
that rule."* That rule is scoped to "for that rule" — which is presumably why the team
felt licensed to reuse the file for a different hypothesis (event-minute timing, not score
threshold). But once a researcher has seen that this specific 27-row set stands down
100% of the time under an over-selective policy, that knowledge shapes every subsequent
design decision on *all* later rules, not just the one that was formally tested against
it — the set has stopped being exchangeable with a fresh 27 rows the moment its aggregate
behavior became known, independent of which rule triggered the look. I'd tighten the
quarantine rule to "spent on first aggregate outcome observed, full stop," not "spent
per-rule."

Net effect: across roughly a dozen dev/holdout rounds spanning v2.x–v5.12, the only
genuinely untouched evidence produced by this entire research program is **one trade**
(the single fill in the 12-row `testset_5x_causal_oos_12.json` batch). That one trade is
too precious to spend on anything other than a wiring smoke test — which is exactly how
the document treats it, and I'd endorse that, but I'd be more blunt: there is currently
**zero** valid historical out-of-sample evidence for or against any v4/v5 hypothesis, and
the path to getting more is data acquisition (grow `entries.db` past its current
2025-01…2026-06 window — flagged as backlog item `DX` in `IMPROVING.md` §6), not further
in-repo iteration.

### Rank 3 — Entries decide and fill on the same bar's own close, at the exact minute liquidity is worst

Q11/Q12 in the document ask about the `:39` release timing and fill sensitivity
separately; I think they're actually the same defect, and it's more specific than either
question implies. Tracing the code:

- `replay.py:872-875`: the scanner event is attached to the tick whose timestamp equals
  `setup.entry_time + scanner_event_release_delay_minutes` (4 minutes for v5.12,
  hard-asserted in `policy_v11.py:80-81`). For a `09:35`-labelled breakout this is
  `09:39` — correct, since the left-labelled 5-minute bar isn't complete until then.
- `policy.py:287`: `scanner_event_confirmation_bars=0` for v5.12 means the entry
  assessment (`_scanner_event_entry_assessment`, `policy.py:268-322`) is only permitted
  on **that same `09:39` tick** — the trigger-tolerance, VWAP, MACD, new-session-high, and
  candlebar-veto checks are all evaluated using that bar's own `o/h/l/c`.
- `policy.py:522-527`: an eligible assessment emits `ENTER_CLOSE`.
- `execution.py:709-719`: `ENTER_CLOSE` fills at `self._buy_price(float(bar["c"]))` —
  **the same bar's own close**, adjusted only by a flat `entry_slippage_bps` (default 10
  bps, `execution.py:31,65,135-138`).

So the entry price *is* the print that just confirmed the entry criteria, with no elapsed
time and 0.10% slippage. That's internally consistent with how "confirmed-close" fills
work everywhere else in this system (it's a documented, intentional simplification per
`RULE_TRACE.md`'s `fill.model` and `entry.confirmed_close_vs_arm` rows, not a new bug) —
but it is applied here at the single worst possible moment for it: the entry gate
requires a green, above-VWAP, new-session-high, volume-expanding breakout bar, which by
construction is exactly the kind of bar whose closing print tends to sit at or near the
local high of a fast, thin-book move. Assuming a fill *at* that print, with no latency and
10 bps of slippage, is the most optimistic possible assumption for a sub-$20, low-float
name in its breakout minute — real spread-crossing plus impact is much more likely to be
tens to low hundreds of bps, and the achievable price is the *next* transactable moment
(`09:40` open or later), not the `09:39` close itself. This compounds with, rather than
replaces, the general "10 bps flat slippage is too small for this asset class" point
Q12 is fishing for.

---

## 2. Is v4/v5 a sensible direction?

**Yes, on the execution/audit architecture. Not yet resolved on the decision-scoring
layer. And — separately from both — the empirical question "does Warrior have edge" is
currently unanswerable on this data no matter how good the architecture gets.**

On the positive side, worth stating plainly rather than just restating the document's
self-assessment: the causal-integrity engineering here is unusually rigorous for this
kind of project. `step.py`'s `IsolatedStreamGateway` — a one-tick Unix-socket gateway that
fingerprints every decision, digests the session manifest, and refuses to serve bar
`i+1` until bar `i`'s decision is immutably committed (`step.py:212-251`) — is a real
defense against an agent (or a careless human) rewriting history after seeing the future,
not just a naming convention. `indicators.py:153-160` computes `new_high` and `rvol_bar`
with explicit `.shift(1)` so a bar can't compare itself against a running max/average that
includes itself. I looked for exactly this class of subtle self-referential leak and
didn't find one in the core indicator/reveal path. The v4.1 failure mode that motivated
the v5 rewrite — the LLM silently stopping mid-position and letting a forced EOD
liquidation get misread as a policy-authored win — is a concrete, already-observed
argument against LLM-as-executor, not a hypothetical one, and it's a good reason on its
own to keep decision-making deterministic.

On the score layer, I'd go a step further than "fragile hand-built classifier." Reading
`candlebars/detectors.py` (e.g. `CandleOverCandle.detect`, lines 49-83: `score = 0.45 +
0.30*close_location + 0.25*min(1, break_distance/range)`) and
`policy.py:_scanner_event_entry_assessment` (lines 308-318) together, the weights were
never fit on data — which avoids one kind of overfitting — but most of the score's inputs
are **redundant with hard boolean gates already present in the same function**: above-VWAP,
non-negative MACD, new-session-high, and no-bearish-candlebar are each independently
`failures.append(...)`'d *and* re-encoded as score components (`trend`, `quality`). Once a
candidate has survived the hard gates, `trend` is always 20, `quality` is 15 or 0 only on
whether the candle is green, and the only genuinely continuous input is the small,
geometry-only `pattern` term. The 70-point threshold is therefore mostly gating on
"green + early + decent scanner/bar RVOL," which could be written as three more booleans
with the same selectivity and far less appearance of statistical sophistication. That
matters because a score that *looks* calibrated invites future maintainers to tune the
cutoff (75→90, as v5.2–5.6 literally did) as if it were a meaningful dial, when it's
functioning as a blunt AND-gate with extra steps.

The harder point, though: even a perfectly designed deterministic policy sitting on top
of this scanner cannot currently produce a valid edge estimate, because the universe it
selects from is tainted at the selection step for every row (Rank 1 above), not for a
carve-outable subset. Architecture work on entry/exit rules is worth continuing for
engineering reasons (auditability, reproducibility, a clean forward-testing harness), but
it is not the bottleneck on the actual research question right now, and no amount of
v5.13/5.14 iteration on the existing 139 rows changes that.

---

## 3. What's justified now vs. what must wait

| Recommendation | Classification | Why |
|---|---|---|
| Rename the scanner's `rvol` field away from "RVOL" (e.g. `prior_day_vol_ratio`) everywhere it surfaces — code, `Entry.reason` strings, reports | **Integrity fix** | It's a premarket liquidity proxy, not Cameron's live intraday RVOL. His own words describe RVOL as something you observe *while the stock is already up 20–30% and everyone's piling in* (`library/ross_cameron/all_content_structured.md:1197`) — i.e. an intraday, path-dependent quantity that literally cannot be known before the session starts. The current field is a defensible causal *substitute*, but calling it RVOL invites readers (including future you) to believe it's testing the mechanism Cameron describes when it's testing an adjacent, weaker one. |
| Stamp every historical run/report with a `NON_PIT_FLOAT` warning inline (not just in SPEC.md) | **Integrity fix** | Costs nothing, prevents the caveat from getting lost the first time someone skims a P&L table instead of the prose above it. |
| Record which float snapshot (value + fetch timestamp) gated each scanner row, instead of relying on an unversioned 30-day cache | **Integrity fix** | Right now two runs of the same historical scan a month apart can silently select a different universe with no record of why. This doesn't fix the survivorship problem, but it makes it auditable rather than silent. |
| Distinguish `floatShares`-sourced vs `sharesOutstanding`-fallback float provenance in any report that cites float (the code already tags `source`, `floats.py:82-95` — it's just not surfaced downstream) | **Integrity fix** | Cheap, and the fallback is a known-conservative-but-biased number that shouldn't be silently indistinguishable from a real float reading. |
| Flag or gate setups where `patterns.py:106-112`'s volume-expansion check had no premarket baseline (`vol_mult is None`) and was let through by default | **Integrity fix** | These are weaker-evidence setups masquerading as "volume expansion confirmed" in the `reason` string; at minimum they should be a separate, explicitly labeled bucket. |
| Retire `testset_100u.json` and `testset_5x_holdout_27.json` from any future evaluation role (rename to make "spent" unmissable, e.g. prefix `_spent_`) | **Integrity fix** | Per Rank 2 above — the holdout has already been queried twice for different hypotheses; treating it as available for a third use invites exactly the contamination `IMPROVING.md` §6 is trying to prevent. |
| Simplify the entry/exit score to explicit booleans, dropping the redundant weighted terms | **Integrity fix to implement, forward experiment to evaluate** | Implementing it is a code-clarity change that can happen immediately (it doesn't add new selectivity, per §2). But whether the *simplified* rule performs differently must only be checked on new forward data — re-running it against the spent 100/27-row sets to see whether it "still looks fine" is itself another dev-set query. |
| Any change to entry timing (e.g. a bounded post-event confirmation/pullback window instead of the current single-tick-only requirement) | **Forward experiment** | Directly implicated in Rank 3 and Q7 below; needs a sealed rule and a predeclared paper protocol, not a re-run against 12 residual rows. |
| Any change to scaling/exit rules (trailing stop, runner management, etc.) | **Forward experiment** | Same reasoning — and should be tested as its own sealed cohort, not bundled with an entry-timing change, or a forward failure can't be attributed. |
| Re-deriving the breakout from the revealed tape instead of consuming the scanner's historical trigger (see Q9) | **Forward experiment**, but note it's largely already built (v4.0) | This isn't a green-field proposal — v4.0's `entry.completed_5m_break` rule (`RULE_TRACE.md` line 34) already re-derives a breakout purely from revealed candles with no scanner-event dependency, and it recorded *more* participation (40/100) than any scanner-event-gated v5 variant. Testing whether that architecture, run through v5's deterministic exit machinery, beats the scanner-trigger-gated approach is a legitimate forward experiment; it does not need new engineering. |
| Historical requantification of the float gate with a true point-in-time float source | **Blocked** | No accessible vendor per the document; this is a procurement task, not a modeling one. |
| L2/tape/NBBO/halt/latency modeling to improve historical fill fidelity | **Blocked** | No data source. Sensitivity *reporting* against the existing flat-slippage assumption (see Q12) is not blocked and should be done now. |
| Growing `entries.db` beyond 2025-01…2026-06 to build a genuinely fresh dev/holdout split | **Neither, technically — a data-engineering task that unblocks everything else** | Already flagged as backlog `DX` in `IMPROVING.md` §6. This is the single highest-leverage non-forward-paper action available: it doesn't fix float, but it's the only lever that produces new *sample size* for testing the causal decision stream in isolation from the float question. |

---

## 4. Prioritized next-experiment plan

1. **Grow the historical setup pool (data engineering, not a rule change).** Extend
   `entries.db` beyond 2025-01…2026-06 and rebuild a fresh, disjoint dev/holdout split
   from the expanded pool, carrying the same non-PIT-float caveat forward explicitly.
   *Pass:* ≥150 new, disjoint, regular-hours rows assembled and hashed into a new pinned
   test-set file. *Fail:* if the underlying data provider can't extend the window at all,
   deprioritize further historical work entirely and go straight to forward paper.

2. **Sealed forward paper/shadow cohort of v5.12, unchanged code, real point-in-time
   float and scanner state captured at scan time.** This is the document's own stated
   "immediate productive path," and I agree it's the top priority above any further
   rule tweaking. Concretely:
   - Freeze the exact git SHA and `skill_versions.json` entry before the first scan.
   - Snapshot float, RVOL inputs, and every scanner-gate field at scan time, not
     reconstructed after the fact.
   - Given observed participation rates (21/100 on the 5.11 dev panel, 1/12 on the
     residual set — roughly 8–20% of scanner events convert to a trade), predeclare a
     **scanner-event count, not a trade count**: target on the order of 150–250 scanner
     events to have a realistic shot at 20–40 trades, the rough floor for a sign test to
     say anything.
   - *Pass:* effective R/trade materially positive with the paired sign-test significant
     at the predeclared count, and participation within the range seen in dev (so the
     result isn't an artifact of near-zero trades). *Fail / kill:* non-significant or
     negative effective R at the predeclared count, or participation collapsing toward
     single digits again (a repeat of the 5.5/5.12 over-selectivity pattern) — kill and
     do not extend the cohort "just a bit more" to chase significance.

3. **Only after (2) clears its bar, and as a separate sealed cohort:** test one
   pre-registered exit/management change (e.g., trail on the prior completed 5-minute
   low instead of the fixed 1R/2R bracket) against a fresh forward cohort. Do not test
   entry-timing and exit-rule changes in the same cohort — a fail can't be attributed to
   either.

4. **Track PIT float vendor acquisition as an ongoing blocked item**, revisited
   periodically (e.g. quarterly), not abandoned — it's the only path to ever validating
   anything on the existing 2024–2026 historical window.

---

## 5. Direct answers to the hard questions

**Research validity**

1. *Does the scanner create a selection-conditioned backtest even after event release is
   fixed?* Yes, and it's worse than a generic "look-ahead" framing suggests — see Rank 1.
   The event-release fix (v5.12) only addresses *when the policy learns about* a trigger
   already selected by a non-causal universe filter; it does nothing about *which*
   tickers were eligible to be selected in the first place. Information available at the
   start of the `09:35` bar: only bars through `09:34`. At its close (`09:39:59`): the
   full shape of that 5-minute candle, which is what the scanner and the score both use.
   At the following minute (`09:40`): the first point a real order could actually
   transact off that information — see Rank 3 for why the current fill model doesn't wait
   for it.

2. *Is prior-day-vol/20-day-avg "RVOL" misleading?* Yes — see the integrity-fix table.
   It's a legitimate, causal premarket liquidity proxy (`screen.py:56-60` computes it
   correctly, shifted to avoid same-day leakage), just not the thing Cameron's transcript
   describes, which is an intraday, path-dependent quantity. Rename it; keep it as a
   pre-screen gate; don't imply it substitutes for real intraday RVOL in any downstream
   text.

3. *Is current float only a selection defect, or does it invalidate historical claims
   entirely?* It invalidates them entirely, and via two mechanisms, not one: magnitude
   drift (bidirectional, the document's framing) plus the unknown-float-fails-closed
   survivorship channel (directional, Rank 1). There's no clean subset of the 139 rows to
   fall back on — every row passed through this gate.

4. *Are the 12 residual rows meaningful?* No — treat as a wiring/reproducibility smoke
   test only, exactly as the document does. I'd add: it's not just underpowered, it's the
   *only* uncontaminated data this entire program has left (Rank 2) — which is an
   argument for guarding it, not for finding one more untouched sliver to test v5.13
   against.

5. *What other biases should be audited?* Two concrete, code-specific ones beyond the
   generic list: (a) `screen.py` deliberately uses **raw, non-split-adjusted** daily bars
   (`screen.py:47-51`) to avoid rescaling penny names out of the price band — sensible,
   but a reverse split occurring a few days outside the exact gap day (not on it) would
   still distort the 20-day rolling average-volume baseline and price-band checks without
   producing the single-day "false gap" the existing `gap_max_pct` guard catches; worth a
   dedicated audit rather than assuming the guard covers it. (b) the float cache's
   unversioned 30-day TTL (Rank 1) is itself a reproducibility hazard for the *selection*
   step, distinct from the already-proven bit-reproducibility of the *decision/fill*
   pipeline — the two shouldn't be assumed to share the same reliability.

**Strategy design**

6. *Sound to make candle geometry deterministic while keeping a score layer?* The
   geometry-deterministic part is right and should stay. The score layer, per §2 above,
   is largely redundant with hard gates already in the same function — I'd remove the
   `trend` and `quality` components first (they add ~zero information beyond gates that
   already exist as hard fails) and keep the score to just the continuous geometry
   `pattern` term plus maybe `bar_volume`, or drop the score/threshold framing entirely in
   favor of explicit booleans, which is what the current gates are actually doing anyway.

7. *Is the event-minute-only requirement structurally sensible?* No — and the reason is
   more specific than "it chases tops": `scanner_event_confirmation_bars=0`
   (`policy_v11.py:20`) means five simultaneous conditions (trigger tolerance, VWAP, new
   high, MACD, no bearish pattern, score≥70) must *all* be true on one specific
   historical-trigger-defined minute, with zero tolerance for a one-bar miss. That's why
   participation collapsed from 40/100 (v4.0, tape-derived) to 21/100 (v5.11) to 1/12
   (v5.12). A causal alternative that doesn't chase already exists in this repo and has
   already been tested: v4.0's `entry.completed_5m_break` (`RULE_TRACE.md` line 34)
   re-derives the breakout from the revealed tape with no scanner-trigger dependency at
   all, and it participated more. The v5.7→v5.12 detour into scanner-event parity
   reproduced a chunk of the residual sample chasing a comparison (parity with v3's
   information contract) that the CHANGELOG itself repeatedly says isn't valid anyway.

8. *Does fixed 1R/2R scaling plus deterministic exit-pressure distort "breakout or
   bailout, then runner"?* Possibly, but this is squarely a forward-experiment question,
   not something to resolve by re-fitting on spent data. If anything is pre-registered:
   trail the runner tranche off the prior completed 5-minute low (already close to
   `manage.runner_exit_5min` in `RULE_TRACE.md`) rather than a fixed R-multiple, and test
   it as its own sealed cohort per the plan above.

9. *Should scanner-event trigger info be visible to a deterministic policy at all?* No —
   or at least, not as the sole entry gate. It should be an optional cross-check on top of
   a tape-derived breakout, not the timing gate itself. v4.0 already demonstrates the
   from-tape alternative works mechanically and participates more; the case for
   re-introducing scanner-trigger dependence (v5.7+) was "parity with v3," which the
   document's own CHANGELOG concedes isn't a valid comparison target in the first place.

10. *Is an LLM useful anywhere after deterministic pattern/execution work?* Not in the
    decision path — and this isn't a generic hallucination-risk argument, it's an
    observed failure: v4.1's LLM executor stopped producing decisions mid-position and a
    forced EOD close was nearly mistaken for a policy-authored win. Non-decisionary
    annotation (catalyst/news classification feeding a human, natural-language batch
    summaries) is fine, but even there, anything an LLM outputs that later feeds an
    unguarded boolean re-opens the same door — keep a hard-coded validator between any
    LLM output and anything that touches sizing, entries, or exits.

**Engineering and validation**

11. *Is `:39` release correct, or should execution begin next-minute/open?* The
    **information** release at `:39` is correct — a left-labelled `09:35` candle isn't
    knowable before its last constituent minute closes. The **execution** assumption is
    not: v5.12 both gates and fills on that same `09:39` bar's own close
    (`policy.py:287` + `execution.py:713`), which assumes zero-latency transacting at a
    price that, by the entry criteria's own construction, is likely near the local high of
    the move. Fix: keep the `:39` information release, but require the fill to occur no
    earlier than the `09:40` open (or later, under a slippage/impact model), not at the
    `09:39` close itself.

12. *Which fill assumptions matter most, and how to report sensitivity honestly?* The flat
    10 bps `entry_slippage_bps`/`exit_slippage_bps` (`execution.py:31,65`) combined with
    same-bar-close fills is the biggest one for this asset class — it's an order of
    magnitude too tight for a low-float breakout minute. Rather than pretending OHLC can
    model the book, report the *existing* historical diagnostics (they're diagnostics
    anyway, not proof of edge) across 2–3 slippage tiers (10 bps flat / next-open fill +
    50 bps / next-open fill + fill-at-bar-high for entries, fill-at-bar-low for stops) so
    a reader can see how much of any apparent edge survives a more adverse but still
    OHLC-honest assumption. This is a reporting change, not a P&L optimization — safe to
    do now.

13. *What forward-paper protocol would make a v5.12 result credible?* Frozen code SHA and
    skill version; float and all scanner-gate inputs captured at scan time, not
    reconstructed; a predeclared **scanner-event count** (not trade count) sized to the
    observed 8–20% conversion rate — see the plan in §4; comparison baseline is "no
    edge" (effective R ≤ 0), not v3 (different information contract, per the document's
    own repeated caveats); kill criteria set *before* the cohort starts, and honored even
    if the interim numbers look tempting to extend.

14. *What test cases are missing?* Concretely, given what I read: (a) a unit test
    asserting the entry fill price for `ENTER_CLOSE` differs from a hypothetical
    next-bar-open fill by more than the flat slippage assumption on at least one
    historical breakout bar, to make the Rank-3 optimism visible in CI rather than only in
    a code read; (b) a test that a ticker whose `yfinance` lookup fails (delisted/renamed)
    is explicitly logged as excluded-by-unknown-float, distinguishable from
    excluded-by-float-too-large, so the survivorship channel in Rank 1 is at least
    observable in `float_cache.json` rather than silent; (c) a reproducibility test that
    reruns a float-gated scan after forcing a cache miss (simulating the 30-day TTL
    boundary) and asserts the resulting `(ticker,date)` set is flagged as changed, not
    silently different; (d) a test asserting `testset_100u.json` /
    `testset_5x_holdout_27.json` cannot be passed to `batchsim compare` as a "holdout" a
    second time without an explicit `--i-know-this-is-spent` override, turning the Rank-2
    discipline into something enforced rather than documented.

---

## On the premise

The prompt asks me to challenge the premise if warranted, and I think part of it needs
challenging directly: **no further historical iteration on the existing 139-row universe
can produce valid evidence about Warrior's edge, no matter how good v6/v7's rules get**,
because the float-gated selection step taints every row, not a carve-outable subset
(Rank 1), and the remaining genuinely fresh sample is one trade (Rank 2). The
architecture work (deterministic execution, sealed reveal, audit reproducibility) has
real, keepable value as a *harness* — it's what makes a future forward-paper result
trustworthy in a way an LLM-executor version never could be — but it is solving a
different problem than "does this edge exist," and treating the next dev-panel tweak as
progress toward that second question is the mistake to avoid. The productive path really
is the frozen forward cohort the document already names as its own next step; I'd just
make the stopping/kill criteria and the scanner-event sample-size target explicit and
pre-declared before it starts, and treat the historical 100/27/12-row sets as fully spent
— not "spent for this rule," spent, period.
