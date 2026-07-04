---
name: strategy-evolution-prompt
description: >-
  Given a strategy family or release (e.g. "x04", "xsec_momentum", "x"), assemble a
  self-contained, copy-pasteable prompt for SOLICITING NEW improvement ideas from an
  external AI (ChatGPT / Gemini / Grok / etc.). The prompt explains the strategy and its
  evolution in plain terms, states the hard constraints, includes a distilled "already
  tried — do NOT repeat" ledger drawn from the family backlog, and asks for novel,
  non-overlapping, testable ideas to improve risk-adjusted profitability. Use when the
  user wants to brainstorm a strategy's next evolution across several top AIs.
---

# strategy-evolution-prompt

Produce an **external idea-solicitation prompt** for one strategy family. The output is a
single markdown file the user will paste into several frontier AIs to harvest *new*
profitability-improvement ideas. The whole value of this skill is that the generated prompt
(a) explains the strategy's evolution clearly to an outsider, and (b) hands the AI the
**full list of what's already been tried and ruled out**, so the ideas it returns do not
overlap with dead ends.

## Argument

`$ARGUMENTS` is a family selector. Accept any of:
- a release id — `x04`, `x03`, `o05`
- a family alias / directory — `xsec_momentum`, `post_gap_opening_drive`
- a family letter — `x`, `o`, `d`, `f`

If no argument is given, ask which family (don't guess).

## Step 1 — Resolve the family

The strategies live under `trading/lab/strategies/<alias>/`. The registry is
`trading/lab/strategies/__init__.py` (`RELEASES` maps release-id → module path; the alias is
the directory segment).

- Release id → look it up in `RELEASES`, take the directory segment as the alias.
- Alias → use directly. Letter → match the alias whose releases share that letter.
- Confirm the directory exists. If the arg was a release id (e.g. `x04`), that **specific
  release is the baseline to beat** — state its *exact* parameters crisply (don't hedge with
  a range), and present earlier releases as the lineage behind it. e.g. for `x04` the
  incumbent is **top-35**, with top-50 (x03) as its predecessor — say "top-35," not
  "top ~35–50."

## Step 2 — Read the living docs (only what exists)

Read, in this order, whichever are present in the family dir:
1. `STRATEGY_OVERVIEW.md` — the from-scratch external description (intuition, signal,
   construction, validation status, risks). **The richest source — lean on it.**
2. `backlog.md` — the research log. The **"Tried & KILLED" table**, the **META-FINDING(s)**,
   and any "current state" / "exhausted" notes are the source of the do-NOT-repeat ledger.
3. The target release `.py` header docstring (and 1–2 lineage releases, e.g. x01 → x03 →
   x04) — for the evolution timeline and exact current parameters.
4. `spec.md` if present.

If a family has only a thin `backlog.md` and no overview, still proceed — just build the
prompt from what's there and note (to the user, not in the prompt) that the overview is thin.

## Step 3 — Translate, don't dump

The internal docs are full of in-house shorthand (DSR, PBO, LOO-WF, sealed-OOS, "R", release
ids, file paths, ledger names). The external AI has none of that context. As you assemble the
prompt:
- **Translate jargon to plain finance English.** e.g. "DSR ≥ 0.95 / PBO" → "passed
  overfitting-robustness and a walk-forward"; "sealed-OOS 2025 PASS" → "confirmed on a
  held-out year never used in development"; "β≈1.4" → "moves ~1.4× the market."
- **Strip internal identifiers and file paths** (`multiday_x04_*.py`, `_capture_*.parquet`,
  release ids as such). Refer to the strategy by its plain name, not "x04".
- **Distill the kill table** into crisp one-line bullets grouped by theme (ranking signal /
  construction / sizing-leverage / exits / hedging-timing / diversifiers / universe). Each
  bullet: *what was tried → why it failed*, in one sentence. This is the most important
  section — it is what keeps the returned ideas non-overlapping.
- Keep the honest performance characterization (modest edge, real but not high-octane) — an
  AI given an inflated picture returns worse ideas.
- **Extract the POSITIVE meta-lessons, not just the kills.** Mine the backlog's "current
  state" / META-FINDING / cost-curve notes for what was *learned about where the lever is* —
  e.g. for xsec_momentum: "the ranking signal is the lever; sizing/timing/exit overlays are
  structurally fragile here," "cost is not the binding leak at realistic AUM (so
  turnover-reduction is low-value)," "the liquid universe is the binding constraint — it's
  *why* new signals collapse to beta." These positive steers kill whole classes of weak ideas
  up front and are as valuable as the kill ledger.
- **Set a concrete win-bar.** Pull the current baseline numbers so the prompt can state what
  magnitude/kind of improvement is worth a research cycle (the last accepted change bought
  only ~0.1 Sharpe; a pure drawdown reduction at flat return counts). Calibrated asks beat
  open-ended ones.

## Step 4 — Emit the prompt to a file (and print it)

Write to `trading/lab/strategies/<alias>/idea-solicitation/<YYYY-MM-DD>-<arg>-PROMPT.md`
(create the `idea-solicitation/` dir if needed; today's date from context). Then print the
full prompt back to the user so they can copy it immediately, and give the file path.

Use **exactly this structure** for the generated prompt (fill every section from the docs;
omit a section only if the family genuinely has no material for it):

```
# Brainstorm: new ideas to improve <Plain Strategy Name>

You are a senior quantitative researcher. I run the strategy below and want your help
finding NEW ways to improve its risk-adjusted profitability. I have already tested a long
list of variations (Section 7) — your ideas MUST NOT overlap with those. I am looking for
genuinely different angles, each concrete enough that I could backtest it.

## 1. What the strategy does
<plain-English summary: universe, signal, how it picks and weights, cadence, hold, exit.
 2–4 short paragraphs from STRATEGY_OVERVIEW §1–5. No jargon, no internal ids.>

## 2. How it evolved to here
<the lineage as a short narrative or timeline: the original version → each refinement and
 the SPECIFIC weakness it addressed → the current version. e.g. plain momentum (too much
 market leverage, deep crashes) → residual/market-neutral momentum (same return, lower
 market risk, shallower drawdown) → modest concentration tweak. End on the CURRENT version's
 EXACT rules (state precise params, no ranges) and why it's the incumbent to beat.>

## 3. Current performance & honest characterization
<the real numbers and an honest read: approx Sharpe, beta to market, max drawdown,
 correlation to plain momentum, and the candid framing (e.g. "a modest, real, long-only
 equity premium ~1.0 Sharpe — better-engineered momentum, not a new source of alpha; main
 win is risk reduction"). Include the key risks (crash risk, single-factor, long-only).>

## 4. What would count as a win
<state the baseline crisply and define the bar so ideas are calibrated, e.g.: "Baseline ≈ 1.0
 Sharpe / ~−23% max drawdown / β≈1.08. The last accepted refinement bought only ~0.1 Sharpe,
 so I want either (a) a step-change in risk-adjusted return, (b) a meaningful drawdown /
 crash-risk reduction even at flat return, or (c) a return gain that survives realistic costs.
 A marginal, regime-unstable +0.05 Sharpe is not worth a research cycle — be honest about
 expected magnitude." Pull the real baseline numbers from §3/the docs.>

## 5. Hard constraints (ideas must respect these)
<bulleted, drawn from the family's constraints. For xsec_momentum these include:
 - LONG ONLY — no shorting, no inverse instruments as a core leg.
 - No leverage, no options.
 - Liquid US-equity universe only (price ≥ $5, ≥ ~$10M/day dollar volume); illiquid/micro-cap
   data is unavailable and survivorship-biased, so "go smaller-cap" is out.
 - Self-funded signals only / data on hand (specify what data exists: daily split-adjusted
   bars + SPY; PIT fundamentals via EDGAR if that lift was done; note what is NOT available).
 - Validation discipline: any idea must be testable on history and survive a held-out year;
   prefer ideas that don't require exotic data.
 Pull the actual constraints from the docs — don't hardcode if they differ.>

## 6. What I've learned about where the lever is (and isn't)
<the POSITIVE meta-lessons distilled from the backlog — the steers that aren't kills but rule
 out whole classes. For xsec_momentum: "the RANKING SIGNAL is the lever — overlays on
 sizing/timing/exits are structurally fragile on this strategy and tend to give back the
 risk improvement"; "transaction cost is NOT the binding leak at realistic AUM, so
 turnover-reduction ideas are low-value"; "the liquid-universe constraint is binding — it is
 *why* every alternative long-only signal collapses into a high-beta tilt." Use whatever the
 docs actually establish; this section focuses the AI's creativity before it sees the kills.>

## 7. Already tried and ruled out — DO NOT re-propose these
<the distilled kill ledger, grouped by theme, one line each: what was tried → why it died.
 Include the META-FINDING(s) verbatim-in-spirit (e.g. "every alternative cross-sectional
 ranking signal tested — value, quality, path-quality, multi-factor residual — collapsed to
 a high-beta tilt with ~zero added alpha on this liquid universe"). Be thorough: this is the
 anti-overlap guardrail. Group suggestions:
   • Alternative ranking signals tried: …
   • Portfolio construction / weighting tried: …
   • Sizing / leverage / vol-targeting tried: …
   • Exits / stops tried: …
   • Hedging / regime-timing / defensive overlays tried: …
   • Diversifier sleeves / multi-strategy blends tried: …
   • Universe changes tried: …>

## 8. What I want from you
Propose **<N, default 8–12> distinct, novel ideas** to improve this strategy's risk-adjusted
profitability (per the §4 win-bar) — WITHOUT violating Section 5 and WITHOUT overlapping
Section 7.

For each idea give:
- **Idea** — one-line name.
- **Mechanism / thesis** — why it could add value *over residual momentum specifically*
  (not generic "momentum works"). Cite the market behavior or inefficiency it exploits.
- **Closest dead-end it avoids** — name the single nearest entry in Section 7 and say in one
  line why this is genuinely different, not a restatement. (If you can't name one, the idea is
  probably too generic.)
- **Why it survives my failure modes** — how it dodges the two patterns that killed most of
  Section 7: (i) "any new long-only signal here just becomes a high-beta tilt with no added
  alpha," and (ii) "timing/sizing/exit overlays are fragile and give back the risk gain."
- **How to test it** — the cleanest backtest, the data it needs (flag anything beyond daily
  bars + the fundamentals I have), and the single decisive metric.
- **What would kill it** — the result that should make me abandon it.

Then end with a **summary table** (one row per idea) so I can triage fast across the several
AIs I'm asking:

| Idea | Mechanism class | Data needed | Cheap to test? | Conviction (H/M/L) | Closest dead-end avoided |
|---|---|---|---|---|---|

**Rank by conviction.** Prioritize ideas that are *cheap to test and structurally different*
from Section 7. Be skeptical and specific — I would rather have 5 sharp, testable,
genuinely-new ideas than 12 restatements of standard momentum lore.
```

## Step 5 — Report back

Tell the user: the file path, that it's ready to paste into external AIs, and a one-line
note on how thorough the anti-overlap ledger came out (e.g. "captured ~20 dead ends across 7
themes"). Don't re-run anything or spawn agents. This skill only *produces the prompt* — the
user runs it externally and brings the answers back for Stage-0 triage.

## Notes / discipline
- This skill is **read-only over the strategy code**; it writes exactly one prompt file. It
  does not modify backlog, releases, or run backtests.
- Keep the generated prompt **self-contained** — an outsider with no repo access must
  understand it end to end. When in doubt, over-explain the strategy and over-list the kills.
- The honest characterization and the kill ledger are non-negotiable sections — they are what
  make the returned ideas useful rather than a list of things already tried.
