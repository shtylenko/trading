"""Deterministic, conservative OHLC execution for simulator intent records.

The simulator agent records *intent* (enter at a close, arm a buy stop, set a
protective stop, scale at a limit, exit at a close).  This module is the sole
authority that turns those intents into fills, sizes, costs, and P&L.  It is
deliberately replayable: given the revealed bars, decisions, and configuration,
it always produces the same blotter.

The source data is one-minute OHLCV, not ticks.  When a bar could have reached
both a favourable limit and a protective stop, the engine resolves it stop-first.
That adverse convention is intentional: it avoids manufacturing an optimistic
intra-bar path that OHLC data cannot prove.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil, floor
from typing import Any, Optional


EXECUTION_MODEL = "deterministic_ohlc_v1"


@dataclass(frozen=True)
class ExecutionConfig:
    """Explicit, versioned execution assumptions for one simulated session."""

    risk_budget: float
    buying_power: float
    entry_slippage_bps: float = 10.0
    exit_slippage_bps: float = 10.0
    commission_per_share: float = 0.005
    max_participation_rate: float = 0.10
    tick_size: float = 0.01

    @classmethod
    def from_session_config(cls, config: dict[str, Any]) -> "ExecutionConfig":
        execution = config.get("execution", {}) or {}
        profile = config.get("profile", "small")
        # The old skill documents $12k of small-account buying power.  Keep the
        # main profile deliberately explicit rather than silently unlimited.
        default_bp = 12_000.0 if profile == "small" else 100_000.0
        return cls(
            risk_budget=float(config.get("risk_budget") or 40.0),
            buying_power=float(config.get("buying_power") or default_bp),
            entry_slippage_bps=float(execution.get("entry_slippage_bps", 10.0)),
            exit_slippage_bps=float(execution.get("exit_slippage_bps", 10.0)),
            commission_per_share=float(execution.get("commission_per_share", 0.005)),
            max_participation_rate=float(execution.get("max_participation_rate", 0.10)),
            tick_size=float(execution.get("tick_size", 0.01)),
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


INTENT_ACTIONS = {
    "OBSERVE",
    "STAND_DOWN",
    "ENTER_CLOSE",
    "ARM_BUY_STOP",
    "CANCEL_ENTRY",
    "SET_STOP",
    "SCALE_LIMIT",
    "ADD_CLOSE",
    "EXIT_CLOSE",
}


class ExecutionEngine:
    """Long-only execution state machine for bar-close decisions.

    Decisions on bar ``i`` are close-confirmed and therefore execute after any
    orders that were already active at the start of that bar.  An armed buy-stop
    or scale limit placed on bar ``i`` becomes active on bar ``i + 1``.
    """

    def __init__(self, config: ExecutionConfig) -> None:
        self.config = config
        self.shares = 0
        self.avg_entry = 0.0
        self.realized = 0.0
        self.fees = 0.0
        self.stop: Optional[float] = None
        self.armed: Optional[dict[str, Any]] = None
        self.targets: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []
        self.timeline: list[dict[str, Any]] = []
        self.entry_i: Optional[int] = None
        self.entry_avg: Optional[float] = None
        self.entry_shares: Optional[int] = None
        self.initial_risk: Optional[float] = None
        self.max_shares = 0
        self.worst_price_vs_entry = 0.0
        self._last_bar: Optional[dict[str, Any]] = None

    # ── price, liquidity, and position primitives ─────────────────────────

    def _round_price(self, price: float, *, buy: bool) -> float:
        tick = self.config.tick_size
        if tick <= 0:
            return round(price, 4)
        units = price / tick
        rounded = ceil(units - 1e-12) if buy else floor(units + 1e-12)
        return round(rounded * tick, 4)

    def _buy_price(self, price: float) -> float:
        return self._round_price(
            price * (1.0 + self.config.entry_slippage_bps / 10_000.0), buy=True
        )

    def _sell_price(self, price: float) -> float:
        return self._round_price(
            price * (1.0 - self.config.exit_slippage_bps / 10_000.0), buy=False
        )

    def _bar_capacity(self, bar: dict[str, Any]) -> int:
        volume = max(0, int(bar.get("v") or 0))
        return max(0, floor(volume * self.config.max_participation_rate))

    def _open_risk(self, stop: Optional[float] = None) -> float:
        stop = self.stop if stop is None else stop
        if self.shares <= 0 or stop is None:
            return 0.0
        return max(0.0, self.shares * (self.avg_entry - stop))

    def _entry_qty(self, price: float, stop: float, capacity: int, *, add: bool) -> int:
        if stop >= price:
            raise ValueError("protective stop must be below the simulated buy price")
        available_risk = self.config.risk_budget - self._open_risk(stop) if add else self.config.risk_budget
        # Reserve a commission for both the entry and an eventual protective exit.
        per_share_risk = (price - stop) + 2 * self.config.commission_per_share
        risk_qty = floor(max(0.0, available_risk) / per_share_risk)
        used_notional = self.shares * self.avg_entry
        buying_power_qty = floor(max(0.0, self.config.buying_power - used_notional) / price)
        return max(0, min(risk_qty, buying_power_qty, capacity))

    def _append_fill(
        self,
        bar: dict[str, Any],
        *,
        action: str,
        buy: bool,
        shares: int,
        price: float,
        reason: str,
    ) -> Optional[dict[str, Any]]:
        if shares <= 0:
            return None
        if not buy and shares > self.shares:
            shares = self.shares
        if shares <= 0:
            return None

        fee = round(shares * self.config.commission_per_share, 4)
        realized_delta = 0.0
        if buy:
            if self.shares == 0:
                if self.entry_i is None:
                    self.entry_i = int(bar["i"])
                if self.entry_avg is None:
                    self.entry_avg = price
                if self.entry_shares is None:
                    self.entry_shares = shares
                if self.initial_risk is None and self.stop is not None:
                    self.initial_risk = round(
                        shares * (price - self.stop) + 2 * fee, 2
                    )
            total = self.shares + shares
            self.avg_entry = (self.avg_entry * self.shares + price * shares) / total
            self.shares = total
            self.max_shares = max(self.max_shares, self.shares)
            realized_delta = -fee
        else:
            realized_delta = shares * (price - self.avg_entry) - fee
            self.shares -= shares
            if self.shares == 0:
                self.avg_entry = 0.0

        self.realized += realized_delta
        self.fees += fee
        row = {
            "i": int(bar["i"]),
            "time": bar.get("time"),
            "action": action,
            "side": "buy" if buy else "sell",
            "price": round(price, 4),
            "shares": shares,
            "commission": round(fee, 4),
            "position_after": self.shares,
            "avg_entry": round(self.avg_entry, 4) if self.shares else None,
            "realized_delta": round(realized_delta, 2),
            "reason": reason,
            "execution_model": EXECUTION_MODEL,
        }
        self.actions.append(row)
        return row

    def _mark_mae(self, bar: dict[str, Any]) -> None:
        if self.shares <= 0 or self.entry_i is None or int(bar["i"]) <= self.entry_i:
            return
        low = bar.get("l")
        if low is None:
            return
        adverse = float(low) - self.avg_entry
        if adverse < self.worst_price_vs_entry:
            self.worst_price_vs_entry = adverse

    # ── order resolution ───────────────────────────────────────────────────

    def _resolve_open_orders(self, bar: dict[str, Any]) -> None:
        capacity = self._bar_capacity(bar)

        # Stop protection deliberately wins any ambiguous OHLC bar.  This is
        # conservative: without tick ordering, a target-before-stop path is not
        # knowable and must not be assumed.
        if self.shares > 0 and self.stop is not None and float(bar["l"]) <= self.stop:
            price = self._sell_price(min(float(bar["o"]), self.stop))
            # A protective stop gets the conservative gap price for the full
            # position.  Applying the ordinary participation cap here would leave
            # an already-triggered stop partially open and understate tail risk.
            self._append_fill(
                bar, action="EXIT", buy=False, shares=self.shares, price=price,
                reason="protective stop (gap-aware; stop-first on ambiguous OHLC)",
            )
            return

        # Limit scales are active only after the bar on which they were placed.
        if self.shares > 0:
            for target in list(self.targets):
                if capacity <= 0 or float(bar["h"]) < target["target"]:
                    continue
                wanted = target.get("remaining")
                if wanted is None:
                    wanted = max(1, floor(self.shares * target["fraction"]))
                qty = min(self.shares, wanted, capacity)
                price = self._sell_price(max(float(bar["o"]), target["target"]))
                filled = self._append_fill(
                    bar, action="SCALE", buy=False, shares=qty, price=price,
                    reason=f"scale limit ${target['target']:.4f}",
                )
                if filled is None:
                    continue
                capacity -= filled["shares"]
                remaining = wanted - filled["shares"]
                if remaining <= 0 or self.shares == 0:
                    self.targets.remove(target)
                else:
                    target["remaining"] = remaining

        # An armed entry is evaluated after pre-existing long protection.  It
        # cannot be placed while long, so this only runs from a flat state.
        if self.shares == 0 and self.armed is not None and int(bar["i"]) > self.armed["placed_i"]:
            armed = self.armed
            if float(bar["h"]) >= armed["trigger"]:
                price = self._buy_price(max(float(bar["o"]), armed["trigger"]))
                self.stop = armed["stop"]
                qty = self._entry_qty(price, self.stop, capacity, add=False)
                filled = self._append_fill(
                    bar, action="ENTER", buy=True, shares=qty, price=price,
                    reason=f"armed buy-stop ${armed['trigger']:.4f}",
                )
                self.armed = None
                if filled is not None:
                    capacity -= filled["shares"]
                    # If both the entry and stop are reachable, use the adverse
                    # entry-then-stop path.  The bar does not reveal their order.
                    if float(bar["l"]) <= self.stop:
                        stop_price = self._sell_price(min(float(bar["o"]), self.stop))
                        self._append_fill(
                            bar, action="EXIT", buy=False, shares=self.shares,
                            price=stop_price,
                            reason="same-bar armed-entry/stop ambiguity (adverse stop-first policy)",
                        )

    def _apply_decision(self, bar: dict[str, Any], decision: dict[str, Any]) -> None:
        action = decision["action"]
        capacity = self._bar_capacity(bar)
        if action in {"OBSERVE", "STAND_DOWN"}:
            return
        if action == "CANCEL_ENTRY":
            self.armed = None
            return
        if action == "SET_STOP":
            new_stop = float(decision["stop"])
            if self.shares <= 0:
                raise ValueError("SET_STOP requires an open position")
            if self.stop is not None and new_stop < self.stop:
                raise ValueError("SET_STOP may not loosen a protective stop")
            self.stop = new_stop
            return
        if action == "ARM_BUY_STOP":
            if self.shares > 0:
                raise ValueError("ARM_BUY_STOP requires a flat position")
            trigger, stop = float(decision["trigger"]), float(decision["stop"])
            if stop >= trigger:
                raise ValueError("ARM_BUY_STOP stop must be below its trigger")
            self.armed = {"trigger": trigger, "stop": stop, "placed_i": int(bar["i"])}
            return
        if action == "ENTER_CLOSE":
            if self.shares > 0:
                raise ValueError("ENTER_CLOSE requires a flat position")
            self.stop = float(decision["stop"])
            price = self._buy_price(float(bar["c"]))
            qty = self._entry_qty(price, self.stop, capacity, add=False)
            self._append_fill(
                bar, action="ENTER", buy=True, shares=qty, price=price,
                reason="close-confirmed entry",
            )
            return
        if action == "ADD_CLOSE":
            if self.shares <= 0:
                raise ValueError("ADD_CLOSE requires an open position")
            new_stop = float(decision["stop"])
            if self.stop is not None and new_stop < self.stop:
                raise ValueError("ADD_CLOSE may not loosen a protective stop")
            price = self._buy_price(float(bar["c"]))
            if price < self.avg_entry:
                raise ValueError("ADD_CLOSE may not average down")
            self.stop = new_stop
            maximum = self._entry_qty(price, self.stop, capacity, add=True)
            qty = floor(maximum * float(decision["risk_fraction"]))
            self._append_fill(
                bar, action="ADD", buy=True, shares=qty, price=price,
                reason="close-confirmed pyramid",
            )
            return
        if action == "SCALE_LIMIT":
            if self.shares <= 0:
                raise ValueError("SCALE_LIMIT requires an open position")
            target = float(decision["target"])
            if target <= self.avg_entry:
                raise ValueError("SCALE_LIMIT target must be above average entry")
            self.targets.append({
                "target": target,
                "fraction": float(decision["fraction"]),
                "placed_i": int(bar["i"]),
                "remaining": None,
            })
            return
        if action == "EXIT_CLOSE":
            price = self._sell_price(float(bar["c"]))
            self._append_fill(
                bar, action="EXIT", buy=False, shares=min(self.shares, capacity), price=price,
                reason="close-confirmed exit",
            )
            return
        raise ValueError(f"unsupported deterministic action {action!r}")

    def _timeline_row(self, bar: dict[str, Any], decision: dict[str, Any], start_actions: int) -> None:
        fills = self.actions[start_actions:]
        qty = sum(a["shares"] if a["side"] == "buy" else -a["shares"] for a in fills)
        last_fill = fills[-1]["price"] if fills else None
        close = float(bar["c"])
        self.timeline.append({
            "i": int(bar["i"]),
            "t": None,
            "time": bar.get("time"),
            "action": decision["action"],
            "thought": decision.get("thought", ""),
            "note": decision.get("note"),
            "fill_px": last_fill,
            "shares_delta": qty or None,
            "stop": self.stop,
            "close": round(close, 4),
            "position_shares": self.shares,
            "avg_entry": round(self.avg_entry, 4) if self.shares else None,
            "unrealized": round(self.shares * (close - self.avg_entry), 2) if self.shares else 0.0,
            "realized_to_date": round(self.realized, 2),
            "execution_model": EXECUTION_MODEL,
        })

    def run(
        self,
        bars: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        *,
        through_i: Optional[int] = None,
        end_close: Optional[float] = None,
        force_close: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        by_i = {d["i"]: d for d in decisions if through_i is None or d.get("i", -1) <= through_i}
        for bar in sorted(bars, key=lambda b: b["i"]):
            if through_i is not None and int(bar["i"]) > through_i:
                break
            self._last_bar = bar
            self._resolve_open_orders(bar)
            self._mark_mae(bar)
            decision = by_i.get(bar["i"])
            if decision is not None:
                before = len(self.actions)
                self._apply_decision(bar, decision)
                self._timeline_row(bar, decision, before)

        forced = False
        if force_close and self.shares > 0 and self._last_bar is not None:
            raw_close = end_close if end_close is not None else float(self._last_bar["c"])
            self._append_fill(
                self._last_bar, action="EXIT", buy=False, shares=self.shares,
                price=self._sell_price(float(raw_close)), reason="auto-flat at session end (position left open)",
            )
            forced = True

        peak = None
        if self.entry_i is not None:
            highs = [float(b["h"]) for b in bars if int(b.get("i", -1)) >= self.entry_i]
            peak = max(highs) if highs else None
        mfe_ps = round(peak - self.entry_avg, 4) if peak is not None and self.entry_avg is not None else None
        cap_ps = (peak - self._blended_entry()) if peak is not None and self._blended_entry() is not None else None
        mfe_dollars = cap_ps * self.max_shares if cap_ps is not None and self.max_shares else None
        actual_r = round(self.realized / self.initial_risk, 2) if self.initial_risk else None
        pnl = {
            "realized_pnl": round(self.realized, 2),
            "risk_budget": self.config.risk_budget,
            "r_multiple": round(self.realized / self.config.risk_budget, 2) if self.config.risk_budget else None,
            "initial_risk": self.initial_risk,
            "r_multiple_actual": actual_r,
            "win": self.realized > 0,
            "traded": self.entry_i is not None,
            "n_fills": len(self.actions),
            "entry_index": self.entry_i,
            "entry_avg": self._blended_entry(),
            "entry_shares": self.entry_shares,
            "max_shares": self.max_shares or None,
            "mfe_per_share": mfe_ps,
            "mfe_pct": round(mfe_ps / self._blended_entry() * 100, 2) if mfe_ps and self._blended_entry() else None,
            "mfe_capture": round(self.realized / mfe_dollars, 3) if mfe_dollars and mfe_dollars > 0 else None,
            "mae_per_share": round(-self.worst_price_vs_entry, 4) if self.worst_price_vs_entry < 0 else None,
            "mae_pct": round(-self.worst_price_vs_entry / self._blended_entry() * 100, 2)
                        if self.worst_price_vs_entry < 0 and self._blended_entry() else None,
            "forced_exit": forced,
            "execution_model": EXECUTION_MODEL,
            "execution_config": self.config.to_dict(),
            "fees": round(self.fees, 2),
            "assumptions": (
                "deterministic OHLC: configured slippage/commissions, volume participation cap, "
                "gap-aware stops, and stop-first resolution for ambiguous stop/target bars"
            ),
        }
        return self.actions, self.timeline, pnl

    def _blended_entry(self) -> Optional[float]:
        buys = [a for a in self.actions if a["side"] == "buy"]
        if not buys:
            return None
        shares = sum(a["shares"] for a in buys)
        return round(sum(a["price"] * a["shares"] for a in buys) / shares, 4) if shares else None

    def snapshot(self, current_i: Optional[int] = None) -> dict[str, Any]:
        """State exposed to the agent after resolving a revealed tick."""
        events = [a for a in self.actions if current_i is None or a["i"] == current_i]
        return {
            "execution_model": EXECUTION_MODEL,
            "i": current_i,
            "fills": events,
            "position_shares": self.shares,
            "avg_entry": round(self.avg_entry, 4) if self.shares else None,
            "stop": self.stop,
            "open_risk": round(self._open_risk(), 2),
            "realized_pnl": round(self.realized, 2),
            "fees": round(self.fees, 2),
            "armed_entry": self.armed,
            "scale_orders": self.targets,
        }
