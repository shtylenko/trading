"""Reconciliation — broker truth vs the live ledger (DESIGN §10.2).

Run before every rebalance and after fills. Compares per-symbol quantity (and, when
available, that the symbol sets match) within explicit tolerances. On mismatch the
engine BLOCKS trading for that portfolio until a fresh reconcile.ok. Pure: takes the
two position views, returns a report; the engine does the I/O + blocking.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PositionDiff:
    ticker: str
    broker_qty: float
    ledger_qty: float

    @property
    def delta(self) -> float:
        return self.broker_qty - self.ledger_qty


@dataclass
class ReconcileReport:
    ok: bool
    diffs: list[PositionDiff] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ok": self.ok,
                "diffs": [{"ticker": d.ticker, "broker_qty": d.broker_qty,
                           "ledger_qty": d.ledger_qty, "delta": d.delta} for d in self.diffs]}


def reconcile_positions(broker_positions: dict, ledger_positions: dict, *,
                        qty_tol: float = 1e-4) -> ReconcileReport:
    """Compare {ticker: qty-bearing object/dict} from broker vs ledger.

    Accepts broker Position objects (``.qty``) or dicts (``["qty"]``) on either side.
    """
    def _q(v) -> float:
        if v is None:
            return 0.0
        return float(v["qty"] if isinstance(v, dict) else getattr(v, "qty", 0.0))

    tickers = set(broker_positions) | set(ledger_positions)
    diffs: list[PositionDiff] = []
    for t in sorted(tickers):
        bq = _q(broker_positions.get(t))
        lq = _q(ledger_positions.get(t))
        if abs(bq - lq) > qty_tol:
            diffs.append(PositionDiff(t, bq, lq))
    return ReconcileReport(ok=(len(diffs) == 0), diffs=diffs)
