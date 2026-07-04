"""The evaluation ladder — the staged funnel every strategy release climbs.

A release moves up a fixed ladder of *rungs*. Each rung has a canonical
testset (or set of aliases) and a *gate*: a pure predicate over that rung's
result that returns ``pass`` / ``kill`` / ``review``. Cheap, statistically
weak checks sit at the bottom; expensive, precious-data checks sit at the top.

The golden rule encoded here: **out-of-sample data (2025+) is untouchable
until everything in-sample has passed.** OOS rungs carry ``is_oos=True`` and a
``prereq_stage``; the runner refuses to spend them on a release that has not
yet cleared the in-sample rungs (see the backtest entry point). You only get
to spend the holdout once per strategy — every premature peek stacks selection
bias no later test can remove.

This module is the *protocol* (versioned in git). A release's current position
on the ladder is mutable state and lives in the ``release_lifecycle`` DuckDB
table (see ``storage/lifecycle.py``); the evaluator that reads runs, applies
these gates, and writes that table lives alongside it.

Gates are pure functions of a :class:`GateInput` so they unit-test without a
database. The fuzzy rungs (robustness, tradeability, portfolio) intentionally
return ``review`` rather than auto-passing: a human confirms them, but the
ladder still records that the release reached that rung.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

# --------------------------------------------------------------------------
# Tunable gate thresholds. Tweaking these is a code-reviewed change, on
# purpose — "pass" is a precise predicate, not a per-run judgment call.
# --------------------------------------------------------------------------

# Screen rung: the existing coarse kill filter.
MIN_TRADES_SCREEN = 30          # below this the verdict is noise, not signal
SIGN_FLIP_P_KILL = 0.5          # pooled sign-flip p above this => no edge

# Broad / OOS rungs: a real edge must clear a tighter bar than "not dead".
SIGN_FLIP_P_EDGE = 0.05         # p at/below this = credible edge
MIN_TRADES_PER_QUARTER = 20     # the >20/quarter "enough trades" goal
# A bucket (regime/half-year) this far below zero flags a one-bucket carry
# even when the pooled total is positive — the 2024-only / 2026H1-carry trap.
WORST_BUCKET_R_FLOOR = -5.0
# OOS result wildly better than in-sample smells like an artifact, not alpha.
OOS_OVER_IS_ARTIFACT_RATIO = 3.0


class Verdict(str, Enum):
    PASS = "pass"      # cleared this rung; advance
    KILL = "kill"      # failed a hard gate; terminal for this release
    REVIEW = "review"  # reached the rung; needs a human call (fuzzy gate)


@dataclass(frozen=True)
class GateResult:
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class GateInput:
    """Everything a gate may inspect, assembled from a release's latest run
    on the rung's testset. Fields a given gate doesn't need are simply left
    at their defaults so callers (and tests) only populate what matters.
    """

    sum_r: float = 0.0
    trade_count: int = 0
    p_value: float = 1.0            # sign-flip p on the daily-R series
    trades_per_quarter: float = 0.0
    worst_bucket_r: float = 0.0     # most-negative per-bucket sum R
    is_sum_r: float | None = None   # in-sample sum R, for the OOS artifact check
    integrity_ok: bool = True       # smoke: no NaN R, no entry-before-signal
    ran_clean: bool = True          # the run completed without error


# --------------------------------------------------------------------------
# Gates — one pure function per rung.
# --------------------------------------------------------------------------

def gate_smoke(g: GateInput) -> GateResult:
    """Rung 0 — correctness, not alpha. Did it run cleanly with sane trades?

    Note: 0 trades is NOT a kill. A smoke testset is often a single quiet day
    where a release legitimately finds no setup; killing on that would bury a
    perfectly functional strategy before it ever reaches the screen (which has
    its own <N-trades floor for "never trades"). Smoke only kills on a real
    failure: the run crashed, or trade integrity is broken.
    """
    if not g.ran_clean:
        return GateResult(Verdict.KILL, "run did not complete cleanly")
    if not g.integrity_ok:
        return GateResult(Verdict.KILL, "trade integrity check failed (NaN R / entry-before-signal)")
    return GateResult(Verdict.PASS, f"ran clean, {g.trade_count} trades")


def gate_screen(g: GateInput) -> GateResult:
    """Rung 1 — the coarse kill filter (the existing screen rule)."""
    if g.trade_count < MIN_TRADES_SCREEN:
        return GateResult(Verdict.KILL, f"{g.trade_count} < {MIN_TRADES_SCREEN} trades (too few to judge)")
    if g.sum_r < 0:
        return GateResult(Verdict.KILL, f"sum R {g.sum_r:.1f} < 0")
    if g.p_value > SIGN_FLIP_P_KILL:
        return GateResult(Verdict.KILL, f"sign-flip p {g.p_value:.2f} > {SIGN_FLIP_P_KILL}")
    return GateResult(Verdict.PASS, f"sum R {g.sum_r:.1f}, p {g.p_value:.2f}")


def gate_broad_is(g: GateInput) -> GateResult:
    """Rung 2 — full in-sample edge with adequate volume across regimes."""
    if g.sum_r <= 0:
        return GateResult(Verdict.KILL, f"sum R {g.sum_r:.1f} <= 0 on full in-sample")
    if g.p_value > SIGN_FLIP_P_KILL:
        return GateResult(Verdict.KILL, f"sign-flip p {g.p_value:.2f} > {SIGN_FLIP_P_KILL}")
    if g.trades_per_quarter < MIN_TRADES_PER_QUARTER:
        return GateResult(Verdict.KILL, f"{g.trades_per_quarter:.0f} trades/quarter < {MIN_TRADES_PER_QUARTER}")
    if g.worst_bucket_r < WORST_BUCKET_R_FLOOR:
        return GateResult(Verdict.REVIEW, f"worst bucket {g.worst_bucket_r:.1f}R — check one-bucket carry")
    if g.p_value > SIGN_FLIP_P_EDGE:
        return GateResult(Verdict.REVIEW, f"positive but weak (p {g.p_value:.2f} > {SIGN_FLIP_P_EDGE})")
    return GateResult(Verdict.PASS, f"sum R {g.sum_r:.1f}, p {g.p_value:.2f}, {g.trades_per_quarter:.0f}/qtr")


def gate_robustness(g: GateInput) -> GateResult:
    """Rung 3 — param-perturbation, honest universe, regime split. Fuzzy:
    surfaced for a human call rather than auto-passed."""
    return GateResult(Verdict.REVIEW, "robustness checks (param/universe/regime) need manual sign-off")


def gate_oos(g: GateInput) -> GateResult:
    """Rung 4 — the holdout. Survive data it never saw; suspiciously *better*
    than in-sample is a red flag, not a win."""
    if g.sum_r <= 0:
        return GateResult(Verdict.KILL, f"OOS sum R {g.sum_r:.1f} <= 0")
    if g.p_value > SIGN_FLIP_P_KILL:
        return GateResult(Verdict.KILL, f"OOS sign-flip p {g.p_value:.2f} > {SIGN_FLIP_P_KILL}")
    if (g.is_sum_r is not None and g.is_sum_r > 0
            and g.sum_r > OOS_OVER_IS_ARTIFACT_RATIO * g.is_sum_r):
        return GateResult(Verdict.REVIEW, f"OOS {g.sum_r:.1f}R >> in-sample {g.is_sum_r:.1f}R — artifact smell")
    if g.p_value > SIGN_FLIP_P_EDGE:
        return GateResult(Verdict.REVIEW, f"OOS positive but weak (p {g.p_value:.2f})")
    return GateResult(Verdict.PASS, f"OOS sum R {g.sum_r:.1f}, p {g.p_value:.2f}")


def gate_tradeability(g: GateInput) -> GateResult:
    """Rung 5 — cost/capacity/concurrency stress. Fuzzy, manual sign-off."""
    return GateResult(Verdict.REVIEW, "cost/capacity/concurrency stress needs manual sign-off")


def gate_portfolio(g: GateInput) -> GateResult:
    """Rung 6 — complementarity vs the promoted set. Fuzzy, manual sign-off."""
    return GateResult(Verdict.REVIEW, "portfolio complementarity needs manual sign-off")


# --------------------------------------------------------------------------
# The ladder.
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Rung:
    index: int
    name: str
    purpose: str
    gate: Callable[[GateInput], GateResult]
    # Testset names whose runs count as a result for this rung. A rung with an
    # empty set is evaluated off-band (no single canonical testset, e.g.
    # robustness pulls from several) and only ever reaches REVIEW.
    testsets: frozenset[str] = field(default_factory=frozenset)
    is_oos: bool = False
    # Minimum stage a release must have reached before a run on this rung's
    # testset is permitted. Enforced for OOS rungs at the backtest entry point.
    prereq_stage: int = 0


FUNNEL: tuple[Rung, ...] = (
    Rung(
        index=0, name="smoke",
        purpose="Runs clean, fills sanely, produces trades — correctness, not edge.",
        gate=gate_smoke,
        testsets=frozenset({
            "smoke_april_2024_sample", "gap_drive_smoke_april_2024", "smoke_2022_01_11",
        }),
    ),
    Rung(
        index=1, name="screen",
        purpose="Any signal at all, cheaply, across years.",
        gate=gate_screen,
        testsets=frozenset({"screen_2022_2026_sampled"}),
    ),
    Rung(
        index=2, name="broad_is",
        purpose="Edge holds on full in-sample data with volume, not one-bucket-carried.",
        gate=gate_broad_is,
        testsets=frozenset({
            "eval_2022_broad", "eval_2023_broad",
            "eval_2024_h1_broad", "eval_2024_h2_broad",
        }),
    ),
    Rung(
        index=3, name="robustness",
        purpose="Param-perturbation, honest universe, regime split — is the edge real?",
        gate=gate_robustness,
    ),
    Rung(
        index=4, name="oos",
        purpose="Survives data it never saw. The one-shot holdout.",
        gate=gate_oos,
        testsets=frozenset({"eval_2025_broad", "eval_2026_h1_broad"}),
        is_oos=True,
        prereq_stage=2,  # must have cleared broad in-sample before spending OOS
    ),
    Rung(
        index=5, name="tradeability",
        purpose="Survives realistic cost / capacity / concurrency.",
        gate=gate_tradeability,
    ),
    Rung(
        index=6, name="portfolio",
        purpose="Adds something the promoted set doesn't already have.",
        gate=gate_portfolio,
    ),
)

# Disposition values stored in release_lifecycle.disposition.
DISPOSITION_ACTIVE = "active"
DISPOSITION_KILLED = "killed"
DISPOSITION_PROMOTED = "promoted"
DISPOSITION_ARCHIVED = "archived"


def rung_by_index(index: int) -> Rung:
    return FUNNEL[index]


def rung_for_testset(testset: str | None) -> Rung | None:
    """The rung a run on ``testset`` belongs to, or None if it is off-funnel
    (an ad-hoc testset that should not move a release's lifecycle)."""
    if not testset:
        return None
    for rung in FUNNEL:
        if testset in rung.testsets:
            return rung
    return None


def max_index() -> int:
    return FUNNEL[-1].index
