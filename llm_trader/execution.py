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
from math import ceil, floor, isfinite
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
    # Multi-horizon: day-trade families force flat at session end; swing does not.
    same_day_only: bool = True
    max_hold_bars: Optional[int] = None

    @classmethod
    def from_session_config(cls, config: dict[str, Any]) -> "ExecutionConfig":
        execution = config.get("execution", {}) or {}
        profile = config.get("profile", "small")
        # Profile defaults (overridable by risk_budget / buying_power / execution.*).
        if profile == "swing":
            default_bp = 50_000.0
            default_risk = 500.0
        elif profile == "main":
            default_bp = 100_000.0
            default_risk = 1350.0
        else:
            default_bp = 12_000.0
            default_risk = 40.0
        same_day = execution.get("same_day_only", config.get("same_day_only", True))
        if isinstance(same_day, str):
            same_day = same_day.strip().lower() in ("1", "true", "yes")
        max_hold = execution.get("max_hold_bars", config.get("max_hold_bars"))
        if max_hold is not None and max_hold != "":
            max_hold = int(max_hold)
        else:
            max_hold = None
        return cls(
            risk_budget=float(config.get("risk_budget") or default_risk),
            buying_power=float(config.get("buying_power") or default_bp),
            entry_slippage_bps=float(execution.get("entry_slippage_bps", 10.0)),
            exit_slippage_bps=float(execution.get("exit_slippage_bps", 10.0)),
            commission_per_share=float(execution.get("commission_per_share", 0.005)),
            max_participation_rate=float(execution.get("max_participation_rate", 0.10)),
            tick_size=float(execution.get("tick_size", 0.01)),
            same_day_only=bool(same_day),
            max_hold_bars=max_hold,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


INTENT_ACTIONS = {
    "OBSERVE",
    "STAND_DOWN",
    "ENTER_CLOSE",
    "ENTER_NEXT_OPEN",
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
    orders that were already active at the start of that bar.  An armed buy-stop,
    scale limit, or entry-attached bracket placed on bar ``i`` becomes active on
    bar ``i + 1``.
    """

    def __init__(self, config: ExecutionConfig) -> None:
        self.config = config
        self.shares = 0
        self.avg_entry = 0.0
        self.realized = 0.0
        self.fees = 0.0
        self.stop: Optional[float] = None
        self.armed: Optional[dict[str, Any]] = None
        # A close-confirmed decision cannot transact at that already-completed
        # bar's close.  This order is submitted after bar i and may first fill
        # at bar i+1's open.
        self.next_open_entry: Optional[dict[str, Any]] = None
        self.targets: list[dict[str, Any]] = []
        self.pyramid: Optional[dict[str, Any]] = None
        self.order_events: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []
        self.timeline: list[dict[str, Any]] = []
        self.entry_i: Optional[int] = None
        self.entry_avg: Optional[float] = None
        self.entry_shares: Optional[int] = None
        self.initial_risk: Optional[float] = None
        self.max_shares = 0
        self.worst_price_vs_entry = 0.0
        # Set when the position returns to flat — bounds in-position MFE.
        self.exit_i: Optional[int] = None
        self.exit_reason: Optional[str] = None
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
                # First flat after a trade bounds MFE (ignore later re-entries' open).
                if self.exit_i is None:
                    self.exit_i = int(bar["i"])
                    self.exit_reason = reason

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

    @staticmethod
    def in_position_peak_high(
        bars: list[dict[str, Any]],
        entry_i: Optional[int],
        exit_i: Optional[int],
        exit_reason: Optional[str] = None,
    ) -> Optional[float]:
        """Peak bar high while the *first* position was open.

        Includes the entry bar (you were long after fill). Excludes bars after
        the flat exit. On a protective-stop exit bar, the high is excluded
        under the engine's stop-first OHLC convention (same rule as
        ``batchsim._in_position_mfe``).
        """
        if entry_i is None:
            return None
        reason = exit_reason or ""
        protective = (
            "protective stop" in reason
            or "armed-entry/stop" in reason
            or "stop-first" in reason
        )
        highs: list[float] = []
        for b in bars:
            i = int(b.get("i", -1))
            if i < entry_i:
                continue
            if exit_i is not None and i > exit_i:
                continue
            if exit_i is not None and i == exit_i and protective:
                continue
            h = b.get("h")
            if h is not None:
                highs.append(float(h))
        return max(highs) if highs else None

    @staticmethod
    def _bracket_scales(decision: dict[str, Any]) -> list[dict[str, float]]:
        """Validate and normalize an optional entry-attached scale ladder.

        A bracket deliberately names R multiples rather than dollar prices: the
        engine cannot know an entry's actual fill until it applies slippage and
        tick rounding.  Deriving the targets here keeps the agent on the intent
        side of the contract and makes the ladder reproducible.
        """
        bracket = decision.get("bracket")
        if bracket is None:
            return []
        if not isinstance(bracket, dict):
            raise ValueError("entry bracket must be an object")
        scales = bracket.get("scales")
        if not isinstance(scales, list) or not scales:
            raise ValueError("entry bracket requires a non-empty 'scales' list")

        normalized: list[dict[str, float]] = []
        previous_r = 0.0
        total_fraction = 0.0
        for scale in scales:
            if not isinstance(scale, dict):
                raise ValueError("each entry bracket scale must be an object")
            r_multiple = scale.get("r_multiple")
            fraction = scale.get("fraction")
            if (not isinstance(r_multiple, (int, float)) or isinstance(r_multiple, bool)
                    or float(r_multiple) <= 0):
                raise ValueError("entry bracket scale 'r_multiple' must be positive")
            if (not isinstance(fraction, (int, float)) or isinstance(fraction, bool)
                    or not 0 < float(fraction) <= 1):
                raise ValueError("entry bracket scale 'fraction' must be in (0, 1]")
            r_multiple, fraction = float(r_multiple), float(fraction)
            if r_multiple <= previous_r:
                raise ValueError("entry bracket scales must have strictly increasing R multiples")
            previous_r = r_multiple
            total_fraction += fraction
            normalized.append({"r_multiple": r_multiple, "fraction": fraction})
        if total_fraction > 1.0 + 1e-12:
            raise ValueError("entry bracket scale fractions may not total more than 1")
        return normalized

    def _attach_bracket(
        self,
        decision: dict[str, Any],
        *,
        fill: Optional[dict[str, Any]],
        placed_i: int,
    ) -> None:
        """Stage scale targets derived from an actual initial-entry fill.

        The bracket is not eligible on the entry bar: orders are created after
        that bar's close decision (or armed-entry resolution) and become active
        on the next bar.  This intentionally preserves the no-retroactive-fill
        rule of the deterministic OHLC contract.
        """
        scales = self._bracket_scales(decision)
        if fill is None or not scales:
            return
        if self.stop is None:
            raise ValueError("entry bracket requires an active protective stop")
        risk_per_share = fill["price"] - self.stop
        if risk_per_share <= 0:
            raise ValueError("entry bracket requires a stop below the actual fill")
        for scale in scales:
            self.targets.append({
                "target": round(fill["price"] + scale["r_multiple"] * risk_per_share, 4),
                "fraction": scale["fraction"],
                "placed_i": placed_i,
                # Bracket tranches are fixed from the original fill so two
                # one-third targets really represent two thirds, rather than a
                # fraction of a position already reduced by the first target.
                "remaining": max(1, floor(fill["shares"] * scale["fraction"])),
                "bracket_r_multiple": scale["r_multiple"],
            })

    @staticmethod
    def _scanner_target_spec(decision: dict[str, Any]) -> Optional[dict[str, float]]:
        """Validate immutable absolute targets supplied by a scanner plan.

        Unlike an agent-authored ``SCALE_LIMIT``, these levels are sealed with the
        entry intent and are installed by the engine only after it knows the real
        entry fill.  This prevents duplicate targets or fractions calculated from
        a position that has already been scaled.
        """
        raw = decision.get("engine_targets")
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ValueError("engine_targets must be an object")
        target1, target2 = raw.get("target1"), raw.get("target2")
        if any(not isinstance(v, (int, float)) or isinstance(v, bool)
               or not isfinite(float(v)) or float(v) <= 0
               for v in (target1, target2)):
            raise ValueError("engine_targets requires finite positive target1 and target2")
        target1, target2 = float(target1), float(target2)
        if target2 <= target1:
            raise ValueError("engine_targets target2 must exceed target1")
        return {"target1": target1, "target2": target2}

    def _attach_scanner_targets(
        self,
        decision: dict[str, Any],
        *,
        fill: Optional[dict[str, Any]],
        placed_i: int,
    ) -> None:
        """Attach the scanner's fixed half/T1 + remainder/T2 exit ladder."""
        spec = self._scanner_target_spec(decision)
        if spec is None or fill is None:
            return
        if spec["target1"] <= fill["price"]:
            raise ValueError("engine-owned target1 must exceed the actual entry fill")
        total = int(fill["shares"])
        first = total // 2
        second = total - first
        if first:
            self.targets.append({
                "target": spec["target1"], "fraction": 0.0, "remaining": first,
                "placed_i": placed_i, "engine_owned": True,
                "move_stop_to_breakeven": True,
            })
        if second:
            self.targets.append({
                "target": spec["target2"], "fraction": 0.0, "remaining": second,
                "placed_i": placed_i, "engine_owned": True,
            })

    @staticmethod
    def _pyramid_spec(decision: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Validate the optional engine-managed starter/add plan on an entry."""
        pyramid = decision.get("pyramid")
        if pyramid is None:
            return None
        if not isinstance(pyramid, dict):
            raise ValueError("entry pyramid must be an object")
        starter = pyramid.get("starter_fraction")
        max_adds = pyramid.get("max_adds")
        if (not isinstance(starter, (int, float)) or isinstance(starter, bool)
                or not 0 < float(starter) <= 0.5):
            raise ValueError("entry pyramid 'starter_fraction' must be in (0, 0.5]")
        if not isinstance(max_adds, int) or isinstance(max_adds, bool) or max_adds not in {1, 2}:
            raise ValueError("entry pyramid 'max_adds' must be 1 or 2")
        return {"starter_fraction": float(starter), "max_adds": max_adds}

    @staticmethod
    def _starter_qty(full_qty: int, pyramid: Optional[dict[str, Any]]) -> int:
        if not pyramid or full_qty <= 0:
            return full_qty
        return min(full_qty, max(1, floor(full_qty * pyramid["starter_fraction"])))

    def _start_pyramid(self, decision: dict[str, Any], fill: Optional[dict[str, Any]]) -> None:
        spec = self._pyramid_spec(decision)
        if spec is None or fill is None:
            return
        self.pyramid = {
            "stage": 0,
            "max_adds": spec["max_adds"],
            # Every add is the same share count as the actual starter. This is
            # a position plan, not a second independent risk budget.
            "tranche_shares": fill["shares"],
            "queued": None,
        }

    def _queue_pyramid_add(self, bar: dict[str, Any]) -> None:
        """Queue a next-bar add from a completed confirmation/continuation bar."""
        plan = self.pyramid
        if (plan is None or self.shares <= 0 or plan["queued"] is not None
                or plan["stage"] >= plan["max_adds"] or self.entry_i is None
                or int(bar["i"]) <= self.entry_i):
            return
        green_above_cost = float(bar["c"]) >= float(bar["o"]) and float(bar["c"]) > self.avg_entry
        if plan["stage"] == 0:
            qualifies = green_above_cost
        else:
            rvol = bar.get("rvol_bar")
            rvol_ok = rvol is None or float(rvol) >= 1.5
            qualifies = (
                green_above_cost and bool(bar.get("new_high")) and rvol_ok
                and float(bar.get("macd_hist") or 0.0) >= 0.0
            )
        if qualifies:
            plan["queued"] = {
                "armed_i": int(bar["i"]),
                "remaining": plan["tranche_shares"],
                "stage": plan["stage"] + 1,
            }

    def _resolve_pyramid_add(self, bar: dict[str, Any], capacity: int) -> int:
        """Fill a previously queued add at this bar's open, never averaging down.

        The re-anchored stop is raised (never loosened) after the actual fill so
        the entire enlarged position remains within the original risk budget.
        """
        plan = self.pyramid
        queued = plan.get("queued") if plan else None
        if (queued is None or self.shares <= 0 or int(bar["i"]) <= queued["armed_i"]
                or capacity <= 0 or self.stop is None):
            return capacity
        price = self._buy_price(float(bar["o"]))
        if price <= self.avg_entry:
            # The continuation failed to hold into the next bar. Cancel this
            # add attempt but leave the plan available for a later clean signal.
            plan["queued"] = None
            return capacity
        buying_power_qty = floor(max(0.0, self.config.buying_power - self.shares * self.avg_entry) / price)
        qty = min(int(queued["remaining"]), capacity, buying_power_qty)
        if qty <= 0:
            plan["queued"] = None
            return capacity
        new_total = self.shares + qty
        new_avg = (self.avg_entry * self.shares + price * qty) / new_total
        required_stop = new_avg - self.config.risk_budget / new_total
        new_stop = max(self.stop, self._round_price(required_stop, buy=True))
        if new_stop >= new_avg:
            plan["queued"] = None
            return capacity
        filled = self._append_fill(
            bar, action="ADD", buy=True, shares=qty, price=price,
            reason=f"engine pyramid add #{queued['stage']} (confirmed continuation)",
        )
        if filled is None:
            return capacity
        self.stop = new_stop
        capacity -= filled["shares"]
        queued["remaining"] -= filled["shares"]
        if queued["remaining"] <= 0:
            plan["stage"] = queued["stage"]
            plan["queued"] = None
        return capacity

    # ── order resolution ───────────────────────────────────────────────────

    def _resolve_open_orders(self, bar: dict[str, Any]) -> None:
        capacity = self._bar_capacity(bar)

        # Execute a previously close-confirmed entry at the first subsequently
        # observable open.  This is distinct from ENTER_CLOSE: it deliberately
        # never manufactures a fill at the same bar close that supplied the
        # confirmation evidence.
        if (
            self.shares == 0
            and self.next_open_entry is not None
            and int(bar["i"]) > self.next_open_entry["placed_i"]
        ):
            pending = self.next_open_entry
            price = self._buy_price(float(bar["o"]))
            stop = float(pending["stop"])
            if price <= stop:
                self.order_events.append({
                    "i": int(bar["i"]),
                    "action": "CANCEL_ENTRY",
                    "reason": "next-open entry opened at or below its protective stop",
                })
                self.next_open_entry = None
            else:
                self.stop = stop
                qty = self._entry_qty(price, stop, capacity, add=False)
                filled = self._append_fill(
                    bar, action="ENTER", buy=True, shares=qty, price=price,
                    reason="close-confirmed next-open entry",
                )
                self.next_open_entry = None
                if filled is None:
                    self.stop = None
                    self.order_events.append({
                        "i": int(bar["i"]),
                        "action": "CANCEL_ENTRY",
                        "reason": (
                            "next-open entry resolved to zero shares "
                            "(capacity/buying-power/stop-distance)"
                        ),
                    })
                else:
                    capacity -= filled["shares"]
                    self._attach_bracket(pending, fill=filled, placed_i=int(bar["i"]))
                    self._start_pyramid(pending, filled)

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
            self.pyramid = None
            return

        # Limit scales are active only after the bar on which they were placed.
        if self.shares > 0:
            for target in list(self.targets):
                if (
                    capacity <= 0
                    or int(bar["i"]) <= int(target.get("placed_i", -1))
                    or float(bar["h"]) < target["target"]
                ):
                    continue
                wanted = target.get("remaining")
                if wanted is None:
                    wanted = max(1, floor(self.shares * target["fraction"]))
                qty = min(self.shares, wanted, capacity)
                price = self._sell_price(max(float(bar["o"]), target["target"]))
                filled = self._append_fill(
                    bar, action="SCALE", buy=False, shares=qty, price=price,
                    reason=(
                        f"entry bracket +{target['bracket_r_multiple']:.2f}R "
                        f"scale limit ${target['target']:.4f}"
                        if "bracket_r_multiple" in target
                        else f"scale limit ${target['target']:.4f}"
                    ),
                )
                if filled is None:
                    continue
                capacity -= filled["shares"]
                # Banking a scale invalidates the starter/add position plan.
                self.pyramid = None
                remaining = wanted - filled["shares"]
                if remaining <= 0 or self.shares == 0:
                    self.targets.remove(target)
                    if target.get("move_stop_to_breakeven") and self.shares > 0:
                        breakeven = self.avg_entry
                        if self.stop is None or breakeven > self.stop:
                            self.stop = breakeven
                            self.order_events.append({
                                "i": int(bar["i"]),
                                "action": "SET_STOP",
                                "reason": "engine moved stop to breakeven after scanner target1",
                            })
                else:
                    target["remaining"] = remaining

        # An armed entry is evaluated after pre-existing long protection.  It
        # cannot be placed while long, so this only runs from a flat state.
        if self.shares == 0 and self.armed is not None and int(bar["i"]) > self.armed["placed_i"]:
            armed = self.armed
            expiry_bars = armed.get("expiry_bars")
            if (
                expiry_bars is not None
                and int(bar["i"]) > int(armed["placed_i"]) + int(expiry_bars)
            ):
                self.order_events.append({
                    "i": int(bar["i"]),
                    "action": "CANCEL_ENTRY",
                    "reason": f"armed entry expired after {int(expiry_bars)} bar(s)",
                })
                self.armed = None
                return
            if float(bar["h"]) >= armed["trigger"]:
                max_gap_atr = armed.get("max_entry_gap_atr")
                atr_px = armed.get("atr")
                gap = float(bar["o"]) - float(armed["trigger"])
                if (
                    max_gap_atr is not None
                    and atr_px is not None
                    and gap > float(max_gap_atr) * float(atr_px)
                ):
                    self.order_events.append({
                        "i": int(bar["i"]),
                        "action": "CANCEL_ENTRY",
                        "reason": (
                            f"entry gap ${gap:.4f} exceeded "
                            f"{float(max_gap_atr):.2f}×ATR"
                        ),
                    })
                    self.armed = None
                    return
                price = self._buy_price(max(float(bar["o"]), armed["trigger"]))
                scanner_targets = armed.get("engine_targets")
                if scanner_targets is not None and float(scanner_targets["target1"]) <= price:
                    # A permissible gap can still consume the whole first measured
                    # move.  Do not manufacture an immediate target fill or crash
                    # after entering; cancel the stale plan before it becomes a
                    # non-positive-reward trade.
                    self.order_events.append({
                        "i": int(bar["i"]),
                        "action": "CANCEL_ENTRY",
                        "reason": "entry price reached scanner target1 before fill",
                    })
                    self.armed = None
                    return
                self.stop = armed["stop"]
                qty = self._entry_qty(price, self.stop, capacity, add=False)
                filled = self._append_fill(
                    bar, action="ENTER", buy=True, shares=qty, price=price,
                    reason=f"armed buy-stop ${armed['trigger']:.4f}",
                )
                self.armed = None
                if filled is not None:
                    capacity -= filled["shares"]
                    self._attach_bracket(armed, fill=filled, placed_i=int(bar["i"]))
                    self._attach_scanner_targets(armed, fill=filled, placed_i=int(bar["i"]))
                    self._start_pyramid(armed, filled)
                    # If both the entry and stop are reachable, use the adverse
                    # entry-then-stop path.  The bar does not reveal their order.
                    if float(bar["l"]) <= self.stop:
                        stop_price = self._sell_price(min(float(bar["o"]), self.stop))
                        self._append_fill(
                            bar, action="EXIT", buy=False, shares=self.shares,
                            price=stop_price,
                            reason="same-bar armed-entry/stop ambiguity (adverse stop-first policy)",
                        )
                        self.pyramid = None
                else:
                    # The trigger was reached but the order resolved to zero shares
                    # (participation cap, buying power, or a stop so wide that risk
                    # sizing yields nothing).  Record it explicitly and drop the
                    # phantom stop so this no-trade is traceable and never mistaken
                    # for an arm that was simply never triggered.
                    self.stop = None
                    self.order_events.append({
                        "i": int(bar["i"]),
                        "action": "CANCEL_ENTRY",
                        "reason": (
                            "armed trigger reached but resolved order size was zero "
                            "(capacity/buying-power/stop-distance)"
                        ),
                    })

        self._resolve_pyramid_add(bar, capacity)

    def _apply_decision(self, bar: dict[str, Any], decision: dict[str, Any]) -> None:
        action = decision["action"]
        capacity = self._bar_capacity(bar)
        if action in {"OBSERVE", "STAND_DOWN"}:
            return
        if action == "CANCEL_ENTRY":
            self.armed = None
            self.next_open_entry = None
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
            scanner_targets = self._scanner_target_spec(decision)
            if scanner_targets is not None and scanner_targets["target1"] <= trigger:
                raise ValueError("engine-owned target1 must exceed an armed-entry trigger")
            # Validate bracket shape at placement time, before a later trigger
            # could make an invalid order state actionable.
            self._bracket_scales(decision)
            self._pyramid_spec(decision)
            max_gap_atr = decision.get("max_entry_gap_atr")
            atr_px = decision.get("atr")
            if max_gap_atr is not None:
                if (not isinstance(max_gap_atr, (int, float))
                        or isinstance(max_gap_atr, bool) or float(max_gap_atr) < 0):
                    raise ValueError("ARM_BUY_STOP max_entry_gap_atr must be non-negative")
                if (not isinstance(atr_px, (int, float)) or isinstance(atr_px, bool)
                        or float(atr_px) <= 0):
                    raise ValueError("ARM_BUY_STOP gap guard requires positive atr")
            expiry_bars = decision.get("expiry_bars")
            if expiry_bars is not None:
                if (not isinstance(expiry_bars, int) or isinstance(expiry_bars, bool)
                        or expiry_bars < 1):
                    raise ValueError("ARM_BUY_STOP expiry_bars must be a positive integer")
            self.armed = {
                "trigger": trigger, "stop": stop, "placed_i": int(bar["i"]),
                "bracket": decision.get("bracket"),
                "pyramid": decision.get("pyramid"),
                "max_entry_gap_atr": float(max_gap_atr) if max_gap_atr is not None else None,
                "atr": float(atr_px) if atr_px is not None else None,
                "expiry_bars": expiry_bars,
                "engine_targets": scanner_targets,
            }
            return
        if action == "ENTER_CLOSE":
            if self.shares > 0:
                raise ValueError("ENTER_CLOSE requires a flat position")
            self.stop = float(decision["stop"])
            price = self._buy_price(float(bar["c"]))
            pyramid = self._pyramid_spec(decision)
            qty = self._starter_qty(self._entry_qty(price, self.stop, capacity, add=False), pyramid)
            filled = self._append_fill(
                bar, action="ENTER", buy=True, shares=qty, price=price,
                reason="close-confirmed entry",
            )
            self._attach_bracket(decision, fill=filled, placed_i=int(bar["i"]))
            self._start_pyramid(decision, filled)
            return
        if action == "ENTER_NEXT_OPEN":
            if self.shares > 0 or self.armed is not None or self.next_open_entry is not None:
                raise ValueError("ENTER_NEXT_OPEN requires a flat position with no active entry")
            stop = float(decision["stop"])
            self._bracket_scales(decision)
            self._pyramid_spec(decision)
            self.next_open_entry = {
                "stop": stop,
                "placed_i": int(bar["i"]),
                "bracket": decision.get("bracket"),
                "pyramid": decision.get("pyramid"),
            }
            return
        if action == "ADD_CLOSE":
            if self.pyramid is not None:
                raise ValueError("ADD_CLOSE is incompatible with an active engine pyramid")
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
            if any(target.get("engine_owned") for target in self.targets):
                raise ValueError("SCALE_LIMIT is unavailable while engine-owned scanner targets are active")
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
            self.pyramid = None
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
            self._queue_pyramid_add(bar)

        forced = False
        if force_close and self.shares > 0 and self._last_bar is not None:
            raw_close = end_close if end_close is not None else float(self._last_bar["c"])
            self._append_fill(
                self._last_bar, action="EXIT", buy=False, shares=self.shares,
                price=self._sell_price(float(raw_close)), reason="auto-flat at session end (position left open)",
            )
            forced = True

        entry_ref = self.entry_avg if self.entry_avg else self._blended_entry()
        peak = self.in_position_peak_high(
            bars, self.entry_i, self.exit_i, self.exit_reason
        )
        mfe_ps = (
            round(peak - entry_ref, 4)
            if peak is not None and entry_ref is not None
            else None
        )
        blended = self._blended_entry()
        cap_ps = (peak - blended) if peak is not None and blended is not None else None
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
            "exit_index": self.exit_i,
            "entry_avg": blended,
            "entry_shares": self.entry_shares,
            "max_shares": self.max_shares or None,
            "mfe_per_share": mfe_ps,
            "mfe_pct": round(mfe_ps / blended * 100, 2) if mfe_ps and blended else None,
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
        order_events = [
            event for event in self.order_events
            if current_i is None or event["i"] == current_i
        ]
        return {
            "execution_model": EXECUTION_MODEL,
            "i": current_i,
            "fills": events,
            "order_events": order_events,
            "position_shares": self.shares,
            "avg_entry": round(self.avg_entry, 4) if self.shares else None,
            "stop": self.stop,
            "open_risk": round(self._open_risk(), 2),
            "realized_pnl": round(self.realized, 2),
            "fees": round(self.fees, 2),
            "armed_entry": self.armed,
            "scale_orders": self.targets,
            "pyramid": self.pyramid,
        }
