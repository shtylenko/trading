"""Executor — submit approved orders to a broker, idempotently (DESIGN §9, §11).

Sells before buys (free buying power). Every order gets a deterministic
``client_order_id`` so a retry/crash-resume never double-submits — the executor skips
any order whose intent was already submitted, and the broker also dedups on the same
id. Fills update the intent + the positions ledger (hold-day authority).

Partial fills are recorded as-is; the unfilled remainder is left for the next cycle
(P1). An unknown post-submit state blocks that order and is surfaced for reconciliation.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from trading.live import ledger
from trading.live.broker import BrokerBase, OrderRequest
from trading.live.config import EnvConfig
from trading.live.logging import EventLogger


def client_order_id(portfolio_id: str, ticker: str, side: str, asof: date) -> str:
    """Deterministic idempotency key: same (portfolio, ticker, side, date) → same id."""
    raw = f"{portfolio_id}|{ticker}|{side}|{asof.isoformat()}"
    return "co_" + hashlib.sha256(raw.encode()).hexdigest()[:24]


@dataclass
class ExecReport:
    submitted: int = 0
    filled: int = 0
    partial: int = 0
    rejected: int = 0
    skipped: int = 0          # idempotent skips (already submitted)
    unknown: int = 0


def execute(orders: list[OrderRequest], *, broker: BrokerBase, portfolio_id: str,
            run_id: str, asof: date, env: EnvConfig, log: EventLogger) -> ExecReport:
    """Submit orders (sells first). Idempotent + fill-aware. Returns a summary."""
    rep = ExecReport()
    ordered = sorted(orders, key=lambda o: 0 if o.side == "sell" else 1)
    for o in ordered:
        coid = o.client_order_id or client_order_id(portfolio_id, o.ticker, o.side, asof)
        o.client_order_id = coid

        # idempotency: never re-submit an order already sent (anti double-submit)
        if ledger.has_submitted_intent(coid, env=env):
            rep.skipped += 1
            log.emit("order.skipped", component="executor", run_id=run_id,
                     portfolio_id=portfolio_id, data={"ticker": o.ticker, "coid": coid,
                                                      "why": "already submitted"})
            continue

        ledger.record_intent(coid, run_id=run_id, portfolio_id=portfolio_id,
                             ticker=o.ticker, side=o.side, qty=o.qty, reason=o.reason, env=env)
        log.emit("order.intent", component="executor", run_id=run_id, portfolio_id=portfolio_id,
                 data={"ticker": o.ticker, "side": o.side, "qty": o.qty, "coid": coid})

        try:
            bo = broker.submit_order(o)
        except Exception as exc:                      # unknown post-submit state → block
            ledger.update_intent(coid, status="unknown", env=env)
            rep.unknown += 1
            log.emit("order.unknown_state", level="ERROR", component="executor", run_id=run_id,
                     portfolio_id=portfolio_id, data={"ticker": o.ticker, "coid": coid},
                     error={"type": type(exc).__name__, "detail": str(exc)})
            continue

        ledger.update_intent(coid, status=bo.status, broker_order_id=bo.broker_order_id,
                             filled_qty=bo.filled_qty, filled_avg_price=bo.filled_avg_price, env=env)
        rep.submitted += 1
        log.emit("order.submitted", component="executor", run_id=run_id, portfolio_id=portfolio_id,
                 data={"ticker": o.ticker, "coid": coid, "status": bo.status,
                       "broker_order_id": bo.broker_order_id})

        if bo.status in ("filled", "partially_filled") and bo.filled_qty > 0:
            ledger.record_fill(coid, portfolio_id=portfolio_id, ticker=o.ticker, side=o.side,
                               qty=bo.filled_qty, price=bo.filled_avg_price or 0.0, env=env)
            log.emit("order.filled", component="executor", run_id=run_id, portfolio_id=portfolio_id,
                     data={"ticker": o.ticker, "coid": coid, "filled_qty": bo.filled_qty,
                           "price": bo.filled_avg_price, "partial": bo.status == "partially_filled"})
            if bo.status == "filled":
                rep.filled += 1
            else:
                rep.partial += 1
        elif bo.status == "rejected":
            rep.rejected += 1
            log.emit("order.rejected", level="WARN", component="executor", run_id=run_id,
                     portfolio_id=portfolio_id, data={"ticker": o.ticker, "coid": coid,
                                                      "reason": bo.reason})
    return rep
