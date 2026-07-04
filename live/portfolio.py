"""Target-portfolio reconciliation (pure functions — the testable core).

x03 is a dated, EQUAL-WEIGHT book with a fixed time hold (DESIGN §5). Given the
ranked target names, the current broker positions, and account equity, produce the
buy/sell orders that move the book toward target. NO price stops — the validated
exit is the time hold; do not invent one here.
"""
from __future__ import annotations

from datetime import date

from trading.live.broker import Account, OrderRequest, Position
from trading.live.config import LiveConfig


def _held_days(entry_date: str | None, asof: date) -> int:
    if not entry_date:
        return 0
    try:
        from pandas import Timestamp
        return int((Timestamp(asof) - Timestamp(entry_date)).days)
    except Exception:
        return 0


def reconcile(target_tickers: list[str],
              positions: dict[str, Position],
              account: Account,
              hold_days: int,
              asof: date,
              config: LiveConfig,
              prices: dict[str, float]) -> list[OrderRequest]:
    """Diff held vs target into orders. Sells first, then equal-weight buys.

    Exit rule (x03): a held name leaves the book only once it has reached ``hold_days``
    AND is no longer in today's target. Names in both, still inside the hold window,
    are left untouched (no churn). Entries are equal-weight to usable equity / n_target.
    """
    target = list(dict.fromkeys(target_tickers))   # de-dup, keep order
    target_set = set(target)
    orders: list[OrderRequest] = []

    # ── Exits: matured holds that fell out of the target book ──
    for ticker, pos in positions.items():
        if ticker in target_set:
            continue
        if _held_days(pos.entry_date, asof) >= hold_days:
            qty = abs(pos.qty)
            if qty > 0:
                orders.append(OrderRequest(ticker, "sell", qty,
                                           reason=f"time exit: held≥{hold_days}d, off-book"))

    # ── Entries: size each NEW name to the whole-book equal-weight slice ──
    # The book is equal-weight across ALL target names, so each name targets
    # equity/len(target) — NOT buying_power/len(new), which would massively
    # overweight the few new names when most of the book is already held.
    #
    # The sizing basis is the portfolio's CONFIGURED capital (config.capital), not the
    # raw broker-account equity: one broker account may fund several portfolios, so each
    # portfolio must size to its own allocation. Fall back to account.equity only when no
    # capital is configured. The cash budget is always capped by real buying power so we
    # never propose more than the account can actually fund.
    to_enter = [t for t in target if t not in positions]
    if to_enter and target:
        equity_basis = config.capital if config.capital > 0 else account.equity
        per_name = (equity_basis * (1.0 - config.cash_reserve_pct)) / len(target)
        budget = (min(equity_basis, account.buying_power)
                  * (1.0 - config.cash_reserve_pct))      # cash cap
        for ticker in to_enter:
            px = prices.get(ticker, 0.0)
            if px <= 0:
                continue
            notional = min(per_name, budget)         # never exceed available buying power
            qty = notional / px if config.fractional else int(notional // px)
            if qty and qty > 0:
                orders.append(OrderRequest(ticker, "buy", qty,
                                           style=config.entry_order_style,
                                           reason="enter: target book (equal weight)"))
                budget -= (qty * px)

    # sells before buys so exits free buying power for entries
    orders.sort(key=lambda o: 0 if o.side == "sell" else 1)
    return orders
