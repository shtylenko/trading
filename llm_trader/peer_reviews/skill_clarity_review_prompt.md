# Skill clarity review — TRADE_SIMULATOR.md

> **Standing gate** — this review is a mandatory pre-batch step for every candidate
> version (`skills/IMPROVING.md` §4.1). Run it on the candidate text with a fresh LLM
> before spending on a validation batch. Track record: the first pass (2026-07-08)
> caught a structural `break_level` bug in the un-batched 2.5.0 draft plus 13
> ambiguities → folded into 2.6.0. Reviewer suggestions are findings, not patches —
> triage them against the constraints below.

You are reviewing an instruction document that **you yourself will execute**. Read it as
the agent who has to act on it, bar by bar, in real time.

## What the skill is

`/Users/shtylenko/Projects/trading/llm_trader/skills/TRADE_SIMULATOR.md` tells an LLM how
to paper-trade **one** recorded stock setup live: the day's 1-minute bars are revealed one
at a time (you never see the future — it is sealed), and on each revealed bar you decide
whether to enter, manage, or exit a long position using Ross Cameron momentum day-trading
rules. You keep your own running state, log one decision per bar, and finish flat.

## The goal of this review

Two things must both be true, and they are the *only* things I care about here:

1. **Accuracy / performance** — following the instructions leads to good trade decisions.
2. **Consistency (reproducibility)** — *two independent, competent runs of this skill, on
   the exact same tape, should reach the same decision on the same bar.* Run-to-run
   divergence is the main failure we are fighting: in the past, the same version on the
   same setup produced wildly different results because a judgment call ("is *this* the
   breakout bar?", "did the break fail?", "where exactly is the stop?") was left to feel.
   We have since converted several of these to explicit formulas. Your job is to find the
   ones that remain.

**The test to apply to every rule:** *"If I handed this line to five careful traders with
the same revealed bars and the same state, would all five take the identical action?"* If
not, it is ambiguous — flag it.

## What to look for

- **Ambiguous or subjective language** — "decisively", "meaningful", "strong", "clean",
  "into strength", "a big red candle", "if it just sits" — anything that requires a
  feel-call rather than a checkable condition over the revealed fields.
- **Underspecified thresholds** — a rule that says "close below the level" or "a large
  wick" without a number, tie-break, or precise field reference.
- **Contradictions or ordering gaps** — two rules that can both fire on the same bar with
  no stated priority; a "check this FIRST" that isn't reconciled with the surrounding list;
  a term used before it is defined.
- **State vs feed confusion** — places where it is unclear whether a quantity comes from
  the current tick, from your own tracked state, or from the setup's recorded metadata.
- **Fill / timing ambiguity** — when exactly a fill happens (touch vs close), which price,
  which bar, and off which reference level.
- **Wording that could simply be tighter** — same meaning, fewer ways to misread it.

## Constraints on your suggestions

- **Do not change the strategy.** This is an operationalization of the Ross Cameron canon
  (`library/ross_cameron/all_content_structured.md`). If a fix would make trading behavior
  *deviate* from that method (not just make it more precise), say so explicitly and treat
  it as out of scope — precision is in scope, re-designing the strategy is not.
- Prefer converting a feel-call into a **boolean/threshold over the revealed fields and
  tracked state** the skill already exposes (e.g. `c, o, h, l, vwap, macd_hist, high_water,
  stop_distance, bars_since_entry`), rather than adding new required data.
- Do not invent thresholds tuned to any particular outcome; propose the *simplest* precise
  reading that stays faithful to the rule's intent.

## Output format

Return a **prioritized list** (most impactful on consistency first). For each item:

1. **Location** — quote the exact phrase and note its section (e.g. §B.2, §A, "Fill model").
2. **Problem** — why two runs could diverge here, or why it could be misread. If you can,
   give a concrete example: "on a bar where …, one reading exits, another holds."
3. **Suggested rewrite** — the precise wording or predicate you'd use instead, or explicitly
   "flag only — fixing this would change strategy, needs a human decision."
4. **Type** — `ambiguity` / `underspecified-threshold` / `contradiction` / `ordering` /
   `wording` / `strategy-risk`.

Close with the **single highest-value change** you would make if you could make only one,
and why it most improves run-to-run consistency.
