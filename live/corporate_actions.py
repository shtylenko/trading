"""Corporate-actions job (DESIGN §10.3) — splits + dividends auto, the rest flagged.

Why this exists: x03 holds 50 names for weeks, so splits/dividends land mid-hold
routinely. A split doubles broker shares + halves price; if the ledger doesn't track
it, reconciliation flags a (false) mismatch and HALTS the portfolio, and P&L/parity
go wrong (the SEZL 6:1 phantom −86% precedent). Live + backtest must adjust the same
way (split-continuous), so this keeps our ledger in step with the broker's adjustment.

Scope (P2): SPLIT and DIVIDEND apply automatically to the ledger; MERGER and DELISTING
are recorded as ``flagged`` for manual approval (never auto-closed). The CA *source* is
injected (a list), so this is testable; a real ``trading.marketdata`` adapter is a thin
wrapper added when the data feed is wired.
"""
from __future__ import annotations

from dataclasses import dataclass

from trading.live import ledger
from trading.live.config import EnvConfig, load_env_config
from trading.live.logging import EventLogger

AUTO_TYPES = ("split", "dividend")
FLAG_TYPES = ("merger", "delisting")


@dataclass(frozen=True)
class CorporateAction:
    symbol: str
    ca_type: str               # split | dividend | merger | delisting
    ex_date: str               # YYYY-MM-DD
    ratio: float | None = None       # split: new/old (2.0 = 2:1; 0.1 = 1:10 reverse)
    cash_per_share: float | None = None  # dividend: $/share


@dataclass
class CAReport:
    applied: list[str]
    flagged: list[str]
    skipped: list[str]         # not held → nothing to do


def apply_actions(portfolio_id: str, actions: list[CorporateAction], *,
                  env: EnvConfig | None = None, log: EventLogger | None = None) -> CAReport:
    """Apply CAs to a portfolio's ledger positions. Only held names are affected."""
    env = env or load_env_config()
    log = log or EventLogger(env)
    ledger.init_db(env)
    held = ledger.get_positions(portfolio_id, env=env)
    rep = CAReport(applied=[], flagged=[], skipped=[])

    for ca in actions:
        if ca.symbol not in held:
            rep.skipped.append(ca.symbol)
            continue

        if ca.ca_type == "split" and ca.ratio:
            ledger.apply_split(portfolio_id, ca.symbol, ca.ratio, env=env)
            ledger.record_corp_action(portfolio_id, ca.symbol, "split",
                                      detail={"ratio": ca.ratio, "ex_date": ca.ex_date}, env=env)
            rep.applied.append(ca.symbol)
            log.emit("corporate_action.applied", component="corp_actions",
                     portfolio_id=portfolio_id,
                     data={"symbol": ca.symbol, "type": "split", "ratio": ca.ratio})

        elif ca.ca_type == "dividend" and ca.cash_per_share:
            qty = held[ca.symbol]["qty"]
            cash = qty * ca.cash_per_share
            ledger.credit_cash(portfolio_id, cash, f"dividend {ca.symbol}", env=env)
            ledger.record_corp_action(portfolio_id, ca.symbol, "dividend",
                                      detail={"per_share": ca.cash_per_share, "cash": cash}, env=env)
            rep.applied.append(ca.symbol)
            log.emit("corporate_action.applied", component="corp_actions",
                     portfolio_id=portfolio_id,
                     data={"symbol": ca.symbol, "type": "dividend", "cash": cash})

        elif ca.ca_type in FLAG_TYPES:
            ledger.record_corp_action(portfolio_id, ca.symbol, ca.ca_type,
                                      detail={"ex_date": ca.ex_date}, status="flagged", env=env)
            rep.flagged.append(ca.symbol)
            log.emit("reconcile.corp_action_mismatch", level="WARN", component="corp_actions",
                     portfolio_id=portfolio_id,
                     message=f"{ca.ca_type} on held {ca.symbol} — needs manual handling",
                     data={"symbol": ca.symbol, "type": ca.ca_type})

    return rep
