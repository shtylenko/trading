"""Pure target-book planner (DESIGN §17 — the testable core, no I/O).

Given a hydrated ``StrategyContext``, the validated release, and a denylist, produce
the target book: run the EXACT ``release.build_candidates`` (parity), take the top-N,
then apply the buy-side tradability/denylist gate (DESIGN §8). No broker, no orders,
no network — the engine (engine.py) does the I/O around this.

Buys are gated; the planner never blocks an exit (exits are handled at reconcile time
against held positions, which the planner doesn't touch).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from trading.live.denylist import Denylist, TradabilityInputs, buy_blocked_reason


@dataclass(frozen=True)
class BookEntry:
    ticker: str
    rank: int
    score: float | None
    close: float | None
    reason: str = ""


@dataclass(frozen=True)
class BlockedEntry:
    ticker: str
    rank: int
    reason: str


@dataclass
class TargetBook:
    release_id: str
    asof: date
    entries: list[BookEntry] = field(default_factory=list)     # buy-eligible, in rank order
    blocked: list[BlockedEntry] = field(default_factory=list)  # ranked but denied (with reason)
    ranked_count: int = 0                                       # candidates before top-N cut

    @property
    def tickers(self) -> list[str]:
        return [e.ticker for e in self.entries]


def _tradability_inputs(candidate, tradability: dict[str, TradabilityInputs] | None) -> TradabilityInputs:
    if tradability and candidate.ticker in tradability:
        return tradability[candidate.ticker]
    # Default in the no-broker P0 path: assume tradable/not-halted; price from features.
    close = candidate.features.get("close") if candidate.features else None
    return TradabilityInputs(tradable=True, halted=False, price=close)


def build_target_book(release, context, denylist: Denylist, *, asof: date,
                      top_n: int | None = None,
                      tradability: dict[str, TradabilityInputs] | None = None) -> TargetBook:
    """Rank via the validated release, cut to top-N, apply the buy-side gate."""
    candidates = release.build_candidates(context)
    ranked_count = len(candidates)
    n = top_n or int(getattr(release, "top_n", 50))

    entries: list[BookEntry] = []
    blocked: list[BlockedEntry] = []
    rank = 0
    for cand in candidates:
        if len(entries) >= n:
            break
        rank += 1
        t = _tradability_inputs(cand, tradability)
        reason = buy_blocked_reason(cand.ticker, asof, denylist, t)
        if reason:
            blocked.append(BlockedEntry(cand.ticker, rank, reason))
            continue  # denied names don't consume a target slot; next candidate fills in
        entries.append(BookEntry(
            ticker=cand.ticker, rank=rank,
            score=getattr(cand, "score", None),
            close=(cand.features or {}).get("close"),
            reason=getattr(cand, "reason", "") or "",
        ))

    return TargetBook(release_id=release.release_id, asof=asof,
                      entries=entries, blocked=blocked, ranked_count=ranked_count)
