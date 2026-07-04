"""Broker adapters — the ONLY modules that talk to a broker (DESIGN §9, §17).

`BrokerBase` is the contract the executor/engine use; everything else stays testable
against `FakeBroker`. `AlpacaBroker` is the real paper/live adapter (guarded import;
not exercised without creds). One broker instance per portfolio account.

Order lifecycle states mirror DESIGN §6:
    accepted → partially_filled → filled
    terminal alternatives: rejected | canceled | unknown
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone


# ── value types ──────────────────────────────────────────────────────────────
@dataclass
class Position:
    ticker: str
    qty: float
    avg_entry_price: float
    current_price: float
    entry_date: str | None = None      # broker- or ledger-sourced; see DESIGN §10.2


@dataclass
class Account:
    equity: float
    buying_power: float
    cash: float = 0.0
    account_id: str = ""               # identity check (DESIGN §2 invariant #3)
    last_equity: float = 0.0           # prior trading-day close (Alpaca's "today %" basis)


@dataclass
class OrderRequest:
    ticker: str
    side: str                          # "buy" | "sell"
    qty: float
    style: str = "market"             # "market" | "market_on_close" | ...
    reason: str = ""
    client_order_id: str | None = None  # deterministic idempotency key (DESIGN §11)


@dataclass
class BrokerOrder:
    client_order_id: str
    ticker: str
    side: str
    qty: float
    status: str                        # accepted|partially_filled|filled|rejected|canceled|unknown
    filled_qty: float = 0.0
    filled_avg_price: float | None = None
    broker_order_id: str | None = None
    reason: str = ""                   # rejection / note
    submitted_at: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.status in ("filled", "rejected", "canceled")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── contract ─────────────────────────────────────────────────────────────────
class BrokerBase:
    """All broker access goes through this. Implementations: FakeBroker, AlpacaBroker."""

    mode: str = "paper"

    def get_account(self) -> Account: raise NotImplementedError
    def get_positions(self) -> dict[str, Position]: raise NotImplementedError
    def submit_order(self, order: OrderRequest) -> BrokerOrder: raise NotImplementedError
    def get_order(self, client_order_id: str) -> BrokerOrder | None: raise NotImplementedError
    def cancel_all_orders(self) -> int: raise NotImplementedError

    def get_equity_history(self, *, period: str = "30D", timeframe: str = "1H"
                           ) -> list[tuple[int, float]]:
        """Broker-computed NAV time series as (unix_seconds, equity). Default: none."""
        return []

    def get_portfolio_perf(self, *, period: str = "1M") -> dict:
        """Daily NAV series + cost basis for return calc:
        {"base_value": float|None, "daily": [(unix_seconds, equity), ...]}."""
        return {"base_value": None, "daily": []}

    def get_latest_price(self, symbol: str) -> float | None:
        """Latest live trade price for a symbol (for intraday 'today' benchmark). None if n/a."""
        return None


# ── fake (deterministic, for tests + dev) ────────────────────────────────────
class FakeBroker(BrokerBase):
    """In-memory broker with a deterministic, controllable fill model.

    - Fills at ``prices[ticker]`` (or no price → stays accepted/unfilled).
    - ``reject`` set → those tickers are rejected. ``partial`` map → fills only that
      fraction (status partially_filled). Otherwise fills fully on submit.
    Positions update on fill so reconciliation/round-trips are testable.
    """

    def __init__(self, *, equity: float = 100_000.0, prices: dict[str, float] | None = None,
                 positions: dict[str, Position] | None = None, mode: str = "paper",
                 reject: set[str] | None = None, partial: dict[str, float] | None = None,
                 account_id: str = "FAKE-ACCT",
                 equity_history: list[tuple[int, float]] | None = None,
                 perf: dict | None = None, last_equity: float | None = None):
        self._equity = equity
        self._last_equity = equity if last_equity is None else last_equity
        self._cash = equity
        self._prices = dict(prices or {})
        self._positions: dict[str, Position] = dict(positions or {})
        self.mode = mode
        self._reject = set(reject or set())
        self._partial = dict(partial or {})
        self._orders: dict[str, BrokerOrder] = {}
        self._account_id = account_id
        self._equity_history = list(equity_history or [])
        self._perf = perf or {"base_value": None, "daily": []}
        self._lock = threading.Lock()

    def get_equity_history(self, *, period: str = "30D", timeframe: str = "1H"
                           ) -> list[tuple[int, float]]:
        return list(self._equity_history)

    def get_portfolio_perf(self, *, period: str = "1M") -> dict:
        return dict(self._perf)

    def get_account(self) -> Account:
        return Account(equity=self._equity, buying_power=self._cash, cash=self._cash,
                       account_id=self._account_id, last_equity=self._last_equity)

    def get_latest_price(self, symbol: str) -> float | None:
        return self._prices.get(symbol)

    def get_positions(self) -> dict[str, Position]:
        return {t: Position(p.ticker, p.qty, p.avg_entry_price, p.current_price, p.entry_date)
                for t, p in self._positions.items() if p.qty != 0}

    def submit_order(self, order: OrderRequest) -> BrokerOrder:
        coid = order.client_order_id or f"{order.ticker}:{order.side}:{order.qty}"
        with self._lock:
            if coid in self._orders:                       # idempotent: broker dedups
                return self._orders[coid]
            bo = BrokerOrder(coid, order.ticker, order.side, order.qty, "accepted",
                             broker_order_id=f"fake-{len(self._orders)+1}", submitted_at=_now())
            if order.ticker in self._reject:
                bo.status, bo.reason = "rejected", "fake reject"
            else:
                px = self._prices.get(order.ticker)
                frac = self._partial.get(order.ticker, 1.0)
                fill_qty = order.qty * frac
                if px is not None and fill_qty > 0:
                    bo.filled_qty = fill_qty
                    bo.filled_avg_price = px
                    bo.status = "filled" if frac >= 1.0 else "partially_filled"
                    self._apply_fill(order.side, order.ticker, fill_qty, px)
            self._orders[coid] = bo
            return bo

    def get_order(self, client_order_id: str) -> BrokerOrder | None:
        return self._orders.get(client_order_id)

    def cancel_all_orders(self) -> int:
        with self._lock:
            n = 0
            for bo in self._orders.values():
                if bo.status in ("accepted", "partially_filled"):
                    bo.status = "canceled"
                    n += 1
            return n

    def _apply_fill(self, side: str, ticker: str, qty: float, px: float) -> None:
        pos = self._positions.get(ticker)
        signed = qty if side == "buy" else -qty
        self._cash -= signed * px
        if pos is None:
            if side == "buy":
                self._positions[ticker] = Position(ticker, qty, px, px, _now()[:10])
        else:
            new_qty = pos.qty + signed
            if new_qty <= 0:
                self._positions.pop(ticker, None)
            else:
                if side == "buy":  # weighted avg on adds
                    pos.avg_entry_price = (pos.avg_entry_price * pos.qty + px * qty) / new_qty
                pos.qty = new_qty
                pos.current_price = px


# ── alpaca (real; guarded — not exercised without creds) ─────────────────────
class AlpacaBroker(BrokerBase):
    """Alpaca paper/live adapter. Endpoint+keys come from secrets; mode picks the URL.

    Implements the same contract over alpaca-py. Submission uses the deterministic
    ``client_order_id`` so a retry/crash-resume can never double-submit (DESIGN §11).
    Real fills should be tracked via the trade-updates stream (DESIGN §9); this P1
    adapter polls ``get_order`` for the lifecycle and is upgraded to streaming in P2.
    """

    def __init__(self, *, api_key: str, secret_key: str, mode: str = "paper"):
        from alpaca.trading.client import TradingClient
        self.mode = mode
        self._key, self._sec = api_key, secret_key
        self._data = None
        self._client = TradingClient(api_key, secret_key, paper=(mode != "live"))

    def get_account(self) -> Account:
        a = self._client.get_account()
        le = float(a.last_equity) if getattr(a, "last_equity", None) else 0.0
        return Account(equity=float(a.equity), buying_power=float(a.buying_power),
                       cash=float(a.cash), account_id=str(a.account_number), last_equity=le)

    def get_latest_price(self, symbol: str) -> float | None:
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockLatestTradeRequest
            if self._data is None:
                self._data = StockHistoricalDataClient(self._key, self._sec)
            t = self._data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
            return float(t[symbol].price)
        except Exception:
            return None

    def get_positions(self) -> dict[str, Position]:
        out: dict[str, Position] = {}
        for p in self._client.get_all_positions():
            out[p.symbol] = Position(p.symbol, float(p.qty), float(p.avg_entry_price),
                                     float(p.current_price or p.avg_entry_price))
        return out

    def submit_order(self, order: OrderRequest) -> BrokerOrder:
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        req = MarketOrderRequest(
            symbol=order.ticker, qty=order.qty,
            side=OrderSide.BUY if order.side == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            client_order_id=order.client_order_id,
        )
        o = self._client.submit_order(req)
        return self._to_broker_order(o, order.client_order_id)

    def get_order(self, client_order_id: str) -> BrokerOrder | None:
        try:
            o = self._client.get_order_by_client_id(client_order_id)
        except Exception:
            return None
        return self._to_broker_order(o, client_order_id)

    def cancel_all_orders(self) -> int:
        resp = self._client.cancel_orders()
        return len(resp or [])

    def get_equity_history(self, *, period: str = "30D", timeframe: str = "1H"
                           ) -> list[tuple[int, float]]:
        """Alpaca account portfolio history → (unix_seconds, equity). Hourly by default.

        Valid under the one-account-per-portfolio invariant (account NAV == portfolio NAV).
        ``intraday_reporting='market_hours'`` so the curve has no flat overnight gaps.
        """
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        req = GetPortfolioHistoryRequest(period=period, timeframe=timeframe,
                                         intraday_reporting="market_hours")
        h = self._client.get_portfolio_history(req)
        out: list[tuple[int, float]] = []
        for ts, eq in zip(h.timestamp or [], h.equity or []):
            if eq is not None and float(eq) > 0:
                out.append((int(ts), float(eq)))
        return out

    def get_portfolio_perf(self, *, period: str = "1M") -> dict:
        """Daily NAV series + base_value (cost basis) from Alpaca portfolio history.
        Daily timeframe → close-to-close returns and total-since-inception."""
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        h = self._client.get_portfolio_history(
            GetPortfolioHistoryRequest(period=period, timeframe="1D"))
        daily = [(int(t), float(e)) for t, e in zip(h.timestamp or [], h.equity or [])
                 if e is not None and float(e) > 0]
        bv = float(h.base_value) if getattr(h, "base_value", None) else None
        return {"base_value": bv, "daily": daily}

    @staticmethod
    def _enum_val(x) -> str:
        """alpaca-py enums stringify as 'OrderStatus.FILLED'; we want the value 'filled'."""
        return str(getattr(x, "value", x)).lower()

    @staticmethod
    def _to_broker_order(o, coid: str) -> BrokerOrder:
        filled = float(getattr(o, "filled_qty", 0) or 0)
        raw = AlpacaBroker._enum_val(getattr(o, "status", "unknown"))
        status = {"new": "accepted", "accepted": "accepted", "pending_new": "accepted",
                  "accepted_for_bidding": "accepted", "partially_filled": "partially_filled",
                  "filled": "filled", "rejected": "rejected",
                  "canceled": "canceled", "cancelled": "canceled", "expired": "canceled"}.get(raw, "unknown")
        avg = getattr(o, "filled_avg_price", None)
        return BrokerOrder(
            client_order_id=coid, ticker=o.symbol, side=AlpacaBroker._enum_val(o.side),
            qty=float(o.qty), status=status, filled_qty=filled,
            filled_avg_price=float(avg) if avg else None,
            broker_order_id=str(o.id), submitted_at=str(getattr(o, "submitted_at", "")),
        )
