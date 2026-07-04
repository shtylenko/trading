from __future__ import annotations

from .models import SimulatedTrade


def compute_trade_metrics(trades: list[SimulatedTrade]) -> dict:
    filled = [t for t in trades if t.entry_time is not None and t.exit_reason != "NO_FILL"]
    wins = [t for t in filled if t.pnl_pct > 0]
    losses = [t for t in filled if t.pnl_pct <= 0]
    gross_win = sum(t.pnl_pct for t in wins)
    gross_loss = abs(sum(t.pnl_pct for t in losses))
    rs = [t.realized_r for t in filled if t.realized_r is not None]
    total_r = sum(rs)
    no_fill = len(trades) - len(filled)
    return {
        "trade_count": len(filled),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / len(filled) * 100.0) if filled else 0.0,
        "gross_win_pct": gross_win,
        "gross_loss_pct": gross_loss,
        "profit_factor": (gross_win / gross_loss) if gross_loss else (float("inf") if gross_win else 0.0),
        "total_pnl_pct": sum(t.pnl_pct for t in filled),
        "avg_pnl_pct": (sum(t.pnl_pct for t in filled) / len(filled)) if filled else 0.0,
        "best_trade_pct": max((t.pnl_pct for t in filled), default=0.0),
        "worst_trade_pct": min((t.pnl_pct for t in filled), default=0.0),
        # R-based (size-aware) aggregates — the decision-grade numbers.
        # total_pnl_pct sums unsized per-trade price moves and should NOT
        # be read as an account return.
        "total_realized_r": total_r,
        "avg_realized_r": (total_r / len(rs)) if rs else 0.0,
        "best_trade_r": max(rs, default=0.0),
        "worst_trade_r": min(rs, default=0.0),
        "account_return_pct_at_1pct_risk": total_r * 1.0,
        "no_fill_count": no_fill,
    }

