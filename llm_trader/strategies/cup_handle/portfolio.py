"""Deterministic chronological portfolio replay for cup-handle batch leaves.

Each sealed leaf already contains an audited deterministic action stream.  A
portfolio cannot simply add those independent leaves: multiple leaves may hold
the same ticker or exceed a shared risk/capital budget.  This module replays the
recorded fills in chronological order and accepts/rejects *entries* under an
explicit portfolio contract.  It never changes a recorded fill price or invents
an unrecorded exit.

Scope is intentionally narrow: one completed deterministic cup-handle batch,
whose per-leaf action sequence has no add-on buys.  An unsupported or internally
inconsistent action sequence is an error, not an optimistic approximation.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any


CONTRACT_ID = "cup_handle_portfolio_actions_v1"
_MONEY_TOLERANCE = 0.02


class PortfolioReplayError(ValueError):
    """A selected leaf cannot support an auditable portfolio replay."""


@dataclass(frozen=True)
class PortfolioConfig:
    """Explicit portfolio limits for a deterministic cup-handle replay.

    Defaults match the existing $50k swing configuration while limiting gross
    initial risk to 3% of buying power (three $500-risk positions).  They are
    stored in every artifact; callers should pass explicit values for research
    comparisons rather than relying on defaults implicitly.
    """

    max_open_positions: int = 3
    max_open_risk: float = 1_500.0
    max_gross_notional: float = 50_000.0
    max_positions_per_ticker: int = 1

    def validate(self) -> None:
        if self.max_open_positions < 1:
            raise PortfolioReplayError("max_open_positions must be at least 1")
        if self.max_positions_per_ticker != 1:
            raise PortfolioReplayError(
                "cup_handle portfolio replay currently requires max_positions_per_ticker=1"
            )
        if not math.isfinite(self.max_open_risk) or self.max_open_risk <= 0:
            raise PortfolioReplayError("max_open_risk must be finite and positive")
        if not math.isfinite(self.max_gross_notional) or self.max_gross_notional <= 0:
            raise PortfolioReplayError("max_gross_notional must be finite and positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: object, label: str, *, positive: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise PortfolioReplayError(f"{label} must be numeric, got {value!r}") from exc
    if not math.isfinite(result) or (positive and result <= 0):
        qualifier = "finite and positive" if positive else "finite"
        raise PortfolioReplayError(f"{label} must be {qualifier}, got {value!r}")
    return result


def _iso_date(value: object, label: str) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError) as exc:
        raise PortfolioReplayError(f"{label} must be YYYY-MM-DD, got {value!r}") from exc


def _hhmm(value: object, label: str) -> str:
    text = str(value or "")
    if len(text) != 5 or text[2] != ":" or not text.replace(":", "").isdigit():
        raise PortfolioReplayError(f"{label} must be HH:MM, got {value!r}")
    hour, minute = int(text[:2]), int(text[3:])
    if hour > 23 or minute > 59:
        raise PortfolioReplayError(f"{label} must be HH:MM, got {value!r}")
    return text


def _event_key(event: dict) -> tuple:
    # Exits happen before entries on a shared daily timestamp, allowing an
    # unambiguous completed position to release its capital/risk.  Same-timestamp
    # entries use a stable causal priority: setup date, ticker, then sealed leaf id.
    return (
        event["date"],
        event["time"],
        event["phase"],
        event["setup_day"],
        event["ticker"],
        event["sid"],
        event["action_index"],
    )


def _prepare_leaf(leaf: dict) -> dict | None:
    """Validate one leaf and return its replayable event payload.

    ``None`` means a clean no-trade leaf.  A traded leaf must have fully dated
    actions whose realized deltas reproduce its persisted ``pnl.json`` exactly
    within cent rounding; otherwise portfolio aggregation fails closed.
    """
    sid = str(leaf.get("sid") or "")
    ticker = str(leaf.get("ticker") or "").upper()
    setup_day = _iso_date(leaf.get("setup_day"), f"{sid or ticker}.setup_day")
    pnl = leaf.get("pnl")
    actions = leaf.get("actions")
    if not isinstance(pnl, dict):
        raise PortfolioReplayError(f"{sid or ticker}: pnl must be an object")
    if not pnl.get("traded"):
        if actions not in (None, []):
            raise PortfolioReplayError(f"{sid or ticker}: no-trade leaf has action records")
        return None
    if not sid or not ticker:
        raise PortfolioReplayError("traded leaf requires sid and ticker")
    if not isinstance(actions, list) or not actions:
        raise PortfolioReplayError(f"{sid}: traded leaf has no action records")

    normalized: list[dict] = []
    first_buy_index: int | None = None
    for i, raw in enumerate(actions):
        if not isinstance(raw, dict):
            raise PortfolioReplayError(f"{sid}: actions[{i}] must be an object")
        side = str(raw.get("side") or "").lower()
        if side not in {"buy", "sell"}:
            raise PortfolioReplayError(f"{sid}: actions[{i}].side must be buy or sell")
        action = {
            "date": _iso_date(raw.get("date"), f"{sid}.actions[{i}].date"),
            "time": _hhmm(raw.get("time"), f"{sid}.actions[{i}].time"),
            "side": side,
            "price": _number(raw.get("price"), f"{sid}.actions[{i}].price", positive=True),
            "shares": _number(raw.get("shares"), f"{sid}.actions[{i}].shares", positive=True),
            "position_after": _number(
                raw.get("position_after"), f"{sid}.actions[{i}].position_after"
            ),
            "realized_delta": _number(
                raw.get("realized_delta", 0.0), f"{sid}.actions[{i}].realized_delta"
            ),
            "action_index": i,
        }
        if action["position_after"] < 0:
            raise PortfolioReplayError(f"{sid}: actions[{i}].position_after cannot be negative")
        if side == "buy":
            if first_buy_index is not None:
                raise PortfolioReplayError(
                    f"{sid}: add-on buys are unsupported by {CONTRACT_ID}; "
                    "replay would otherwise alter the recorded leaf P&L"
                )
            first_buy_index = i
        normalized.append(action)
    if first_buy_index != 0:
        raise PortfolioReplayError(f"{sid}: first action must be the opening buy")
    if normalized[-1]["side"] != "sell" or normalized[-1]["position_after"] != 0:
        raise PortfolioReplayError(f"{sid}: traded leaf must end flat with a sell action")

    previous_key: tuple[str, str] | None = None
    for action in normalized:
        key = (action["date"], action["time"])
        if previous_key is not None and key < previous_key:
            raise PortfolioReplayError(f"{sid}: action records are not chronological")
        previous_key = key

    realized = sum(action["realized_delta"] for action in normalized)
    persisted = _number(pnl.get("realized_pnl"), f"{sid}.pnl.realized_pnl")
    if abs(realized - persisted) > _MONEY_TOLERANCE:
        raise PortfolioReplayError(
            f"{sid}: action realized deltas ${realized:.2f} do not match pnl ${persisted:.2f}"
        )
    return {
        "sid": sid,
        "ticker": ticker,
        "setup_day": setup_day,
        "initial_risk": _number(pnl.get("initial_risk"), f"{sid}.pnl.initial_risk", positive=True),
        "r_multiple": _number(pnl.get("r_multiple"), f"{sid}.pnl.r_multiple"),
        "realized_pnl": persisted,
        "actions": normalized,
    }


def replay(leaves: list[dict], config: PortfolioConfig) -> dict[str, Any]:
    """Replay completed deterministic leaves through one portfolio contract."""
    config.validate()
    if not leaves:
        raise PortfolioReplayError("portfolio replay requires at least one leaf")

    prepared: list[dict] = []
    no_trade = 0
    for leaf in leaves:
        candidate = _prepare_leaf(leaf)
        if candidate is None:
            no_trade += 1
        else:
            prepared.append(candidate)

    events: list[dict] = []
    for candidate in prepared:
        for action in candidate["actions"]:
            is_entry = action["action_index"] == 0
            events.append({
                **action,
                "sid": candidate["sid"],
                "ticker": candidate["ticker"],
                "setup_day": candidate["setup_day"],
                "phase": 1 if is_entry else 0,
                "is_entry": is_entry,
                "candidate": candidate,
            })

    active: dict[str, dict] = {}
    active_tickers: set[str] = set()
    rejected: set[str] = set()
    accepted: list[dict] = []
    skipped: list[dict] = []
    realized_pnl = 0.0
    daily_pnl: dict[str, float] = defaultdict(float)
    max_positions = 0
    max_open_risk = 0.0
    max_gross_notional = 0.0

    def totals() -> tuple[float, float]:
        return (
            sum(position["risk"] for position in active.values()),
            sum(position["book_notional"] for position in active.values()),
        )

    for event in sorted(events, key=_event_key):
        sid = event["sid"]
        candidate = event["candidate"]
        if event["is_entry"]:
            open_risk, gross_notional = totals()
            entry_notional = event["shares"] * event["price"]
            reason = None
            if event["ticker"] in active_tickers:
                reason = "ticker_position_limit"
            elif len(active) >= config.max_open_positions:
                reason = "max_open_positions"
            elif open_risk + candidate["initial_risk"] > config.max_open_risk + _MONEY_TOLERANCE:
                reason = "max_open_risk"
            elif gross_notional + entry_notional > config.max_gross_notional + _MONEY_TOLERANCE:
                reason = "max_gross_notional"
            if reason is not None:
                rejected.add(sid)
                skipped.append({
                    "sid": sid,
                    "ticker": event["ticker"],
                    "setup_day": event["setup_day"],
                    "entry_day": event["date"],
                    "reason": reason,
                    "initial_risk": round(candidate["initial_risk"], 2),
                    "entry_notional": round(entry_notional, 2),
                })
                continue
            active[sid] = {
                "ticker": event["ticker"],
                "risk": candidate["initial_risk"],
                "shares": event["shares"],
                "book_notional": entry_notional,
                "candidate": candidate,
            }
            active_tickers.add(event["ticker"])
            accepted.append({
                "sid": sid,
                "ticker": event["ticker"],
                "setup_day": event["setup_day"],
                "entry_day": event["date"],
                "entry_time": event["time"],
                "initial_risk": round(candidate["initial_risk"], 2),
                "entry_notional": round(entry_notional, 2),
                "r_multiple": round(candidate["r_multiple"], 3),
                "realized_pnl": round(candidate["realized_pnl"], 2),
            })
        elif sid not in active:
            # A rejected leaf's later actions are intentionally ignored.  Any
            # other orphaned action means the sealed leaf is structurally invalid.
            if sid not in rejected:
                raise PortfolioReplayError(f"{sid}: action appears before an accepted entry")
            continue
        else:
            position = active[sid]
            if event["side"] != "sell":  # _prepare_leaf rejects later buys.
                raise PortfolioReplayError(f"{sid}: unsupported active action {event['side']!r}")
            if event["shares"] > position["shares"] + _MONEY_TOLERANCE:
                raise PortfolioReplayError(f"{sid}: sell shares exceed open position")
            prior_shares = position["shares"]
            position["shares"] -= event["shares"]
            position["book_notional"] *= max(0.0, position["shares"] / prior_shares)
            if abs(position["shares"] - event["position_after"]) > _MONEY_TOLERANCE:
                raise PortfolioReplayError(f"{sid}: action position_after is inconsistent with shares")
            if event["position_after"] == 0:
                active_tickers.remove(position["ticker"])
                del active[sid]

        # Only accepted actions affect portfolio realized P&L.  The opening
        # action includes its commission as a small negative delta; scaling and
        # exit actions include their own fills/fees, exactly as sealed.
        if sid not in rejected:
            realized_pnl += event["realized_delta"]
            daily_pnl[event["date"]] += event["realized_delta"]
            open_risk, gross_notional = totals()
            max_positions = max(max_positions, len(active))
            max_open_risk = max(max_open_risk, open_risk)
            max_gross_notional = max(max_gross_notional, gross_notional)

    if active:
        remaining = ", ".join(sorted(f"{p['ticker']}:{sid}" for sid, p in active.items()))
        raise PortfolioReplayError(f"portfolio replay ended with open positions: {remaining}")

    accepted_r = sum(row["r_multiple"] for row in accepted)
    raw_pnl = sum(candidate["realized_pnl"] for candidate in prepared)
    raw_r = sum(candidate["r_multiple"] for candidate in prepared)
    cumulative = 0.0
    realized_curve = []
    peak = 0.0
    max_drawdown = 0.0
    for day in sorted(daily_pnl):
        cumulative += daily_pnl[day]
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
        realized_curve.append({
            "date": day,
            "realized_pnl_delta": round(daily_pnl[day], 2),
            "cumulative_realized_pnl": round(cumulative, 2),
        })

    return {
        "schema_version": 1,
        "portfolio_contract": CONTRACT_ID,
        "config": config.to_dict(),
        "summary": {
            "setups": len(leaves),
            "raw_trades": len(prepared),
            "no_trade": no_trade,
            "accepted_trades": len(accepted),
            "skipped_entries": len(skipped),
            "raw_independent_pnl": round(raw_pnl, 2),
            "raw_independent_effective_r": round(raw_r / len(leaves), 3),
            "portfolio_realized_pnl": round(realized_pnl, 2),
            "portfolio_effective_r": round(accepted_r / len(leaves), 3),
            "portfolio_trade_avg_r": round(accepted_r / len(accepted), 3) if accepted else None,
            "max_open_positions": max_positions,
            "max_open_risk": round(max_open_risk, 2),
            "max_gross_notional": round(max_gross_notional, 2),
            "realized_pnl_max_drawdown": round(max_drawdown, 2),
        },
        "accepted": accepted,
        "skipped": skipped,
        "realized_pnl_curve": realized_curve,
    }
