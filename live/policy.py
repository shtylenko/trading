"""Approval policy — classify each order auto vs needs-approval (DESIGN §7).

By risk *direction*, not just size: risk-reducing actions (exits) are safe to
automate; risk-increasing actions (new buys, oversized adds) earn scrutiny. Pure +
testable. New portfolios start fully manual (`auto_max_pct=0`).
"""
from __future__ import annotations

from dataclasses import dataclass

from trading.live.broker import OrderRequest


@dataclass(frozen=True)
class ApprovalPolicy:
    auto_max_pct: float = 0.0          # auto-execute buys/adds up to this % of equity (0 = none)
    auto_max_names: int = 0            # cap on how many names may auto-execute per run
    approval_ttl_minutes: int = 90     # pending approvals expire after this (DESIGN §7)
    auto_exits: bool = True            # risk-reducing sells auto unless anomaly


@dataclass(frozen=True)
class Decision:
    order: OrderRequest
    auto: bool
    reason: str


def classify(orders: list[OrderRequest], *, equity: float, held: set[str],
             policy: ApprovalPolicy, prices: dict[str, float],
             anomalies: set[str] | None = None) -> list[Decision]:
    """Return a Decision per order. Sells first keeps risk-reduction unblocked."""
    anomalies = anomalies or set()
    decisions: list[Decision] = []
    auto_buys_used = 0

    # process sells (risk-reducing) before buys
    for o in sorted(orders, key=lambda x: 0 if x.side == "sell" else 1):
        if o.ticker in anomalies:
            decisions.append(Decision(o, False, "anomaly flag → approval"))
            continue
        if o.side == "sell":
            decisions.append(
                Decision(o, policy.auto_exits, "exit auto" if policy.auto_exits else "exit → approval"))
            continue
        # buys / adds — risk-increasing
        notional = o.qty * prices.get(o.ticker, 0.0)
        pct = (notional / equity) if equity > 0 else 1.0
        is_new = o.ticker not in held
        if is_new:
            decisions.append(Decision(o, False, "new position → approval"))
        elif policy.auto_max_pct <= 0:
            decisions.append(Decision(o, False, "manual policy (auto_max_pct=0)"))
        elif pct > policy.auto_max_pct:
            decisions.append(Decision(o, False, f"size {pct:.1%} > band {policy.auto_max_pct:.1%}"))
        elif auto_buys_used >= policy.auto_max_names:
            decisions.append(Decision(o, False, "auto name budget exhausted → approval"))
        else:
            auto_buys_used += 1
            decisions.append(Decision(o, True, "add within band → auto"))
    return decisions
