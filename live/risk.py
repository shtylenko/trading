"""Per-portfolio pre-trade risk policy (DESIGN §7).

Runs BEFORE approval classification. Two outcomes:
  - **portfolio halt** — a daily-loss / drawdown breach trips auto-pause: block the
    whole rebalance (no orders) and alert.
  - **forced approval** — a single order that would breach a position/concentration
    limit can't auto-execute; it's downgraded to needs-approval with a stated reason.

Pure + testable. Defaults are permissive (all limits off) so a portfolio only gets
the limits you opt into.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from trading.live.broker import Account, OrderRequest, Position


@dataclass(frozen=True)
class RiskPolicy:
    max_single_position_pct: float | None = None   # e.g. 0.12 — per-name cap (% equity)
    max_top_n_concentration_pct: float | None = None  # top-N names ≤ this % (informational)
    max_daily_loss_pct: float | None = None        # day P&L worse than -X → halt
    max_drawdown_pct: float | None = None          # equity vs peak worse than -X → halt
    max_daily_turnover_pct: float | None = None    # gross traded notional / equity cap


@dataclass
class RiskAssessment:
    halt: bool = False
    halt_reason: str = ""
    forced_approval: dict[str, str] = field(default_factory=dict)  # coid/ticker -> reason
    violations: list[str] = field(default_factory=list)


def assess(orders: list[OrderRequest], *, account: Account,
           positions: dict[str, Position], prices: dict[str, float],
           policy: RiskPolicy, day_pnl_pct: float | None = None,
           drawdown_pct: float | None = None,
           equity_basis: float | None = None) -> RiskAssessment:
    """Evaluate pre-trade risk. ``day_pnl_pct``/``drawdown_pct`` are negative for losses.

    ``equity_basis`` is the denominator for the %-of-capital limits: pass the portfolio's
    CONFIGURED capital so a $5k allocation isn't measured against a $100k broker account
    (which would make every concentration/size limit ~20x too loose). Falls back to
    ``account.equity`` when not provided.
    """
    a = RiskAssessment()
    equity = (equity_basis if equity_basis is not None else account.equity) or 0.0

    # ── portfolio-level circuit breakers → halt everything ──
    if policy.max_daily_loss_pct is not None and day_pnl_pct is not None \
            and day_pnl_pct <= -abs(policy.max_daily_loss_pct):
        a.halt, a.halt_reason = True, f"daily loss {day_pnl_pct:.1%} ≤ -{policy.max_daily_loss_pct:.1%}"
    if policy.max_drawdown_pct is not None and drawdown_pct is not None \
            and drawdown_pct <= -abs(policy.max_drawdown_pct):
        a.halt = True
        a.halt_reason = (a.halt_reason + "; " if a.halt_reason else "") + \
            f"drawdown {drawdown_pct:.1%} ≤ -{policy.max_drawdown_pct:.1%}"
    if a.halt:
        a.violations.append(a.halt_reason)
        return a

    # ── per-order position-size limit → force approval (buys only; exits never blocked) ──
    if policy.max_single_position_pct is not None and equity > 0:
        held_val = {t: p.qty * prices.get(t, p.current_price) for t, p in positions.items()}
        for o in orders:
            if o.side != "buy":
                continue
            px = prices.get(o.ticker, 0.0)
            post_val = held_val.get(o.ticker, 0.0) + o.qty * px
            pct = post_val / equity
            if pct > policy.max_single_position_pct:
                key = o.client_order_id or o.ticker
                a.forced_approval[key] = (
                    f"position would be {pct:.1%} > limit {policy.max_single_position_pct:.1%}")
                a.violations.append(f"{o.ticker}: {a.forced_approval[key]}")

    # ── turnover cap (informational/forced-approval on the marginal buys) ──
    if policy.max_daily_turnover_pct is not None and equity > 0:
        gross = sum(o.qty * prices.get(o.ticker, 0.0) for o in orders)
        if gross / equity > policy.max_daily_turnover_pct:
            a.violations.append(
                f"turnover {gross/equity:.1%} > cap {policy.max_daily_turnover_pct:.1%}")
    return a
