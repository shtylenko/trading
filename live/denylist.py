"""Buy denylist + tradability gate (pure, testable).

The denylist gates **buys only** — selling/exiting a held position is always allowed
(DESIGN.md §8). Two layers are merged: the version-controlled platform baseline
(`denylist.yml`) and per-portfolio entries from the live DB (passed in by the caller;
this module stays I/O-free apart from reading the baseline YAML).

Wired into the planner before any buy is proposed; a blocked candidate is dropped and
an event is logged (`tradability.blocked`). Category rules (leveraged/inverse, price /
liquidity floors) are evaluated by the caller using `trading.marketdata` features and
passed via `TradabilityInputs` — kept here only as declarative config.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

_BASELINE_PATH = Path(__file__).resolve().parent / "denylist.yml"


@dataclass(frozen=True)
class DenylistEntry:
    symbol: str
    reason: str
    scope: str = "platform"          # "platform" | a portfolio_id
    expires: date | None = None
    added_by: str | None = None

    def active_on(self, asof: date) -> bool:
        return self.expires is None or asof < self.expires


@dataclass
class Denylist:
    """Merged platform + per-portfolio denylist, plus category rules."""

    entries: list[DenylistEntry] = field(default_factory=list)
    categories: dict = field(default_factory=dict)

    def blocked_reason(self, symbol: str, asof: date) -> str | None:
        """Return the block reason for a BUY of ``symbol``, or None if buy-eligible.

        Only the explicit symbol list is checked here; category/numeric rules are
        applied by the caller (it has the marketdata features). Never call this to
        gate a SELL — exits are always allowed.
        """
        sym = symbol.upper()
        for e in self.entries:
            if e.symbol.upper() == sym and e.active_on(asof):
                return e.reason
        return None


def load_platform_denylist(path: Path | str | None = None) -> Denylist:
    """Load the version-controlled baseline (`denylist.yml`). I/O lives here only."""
    import yaml  # local import: keep module import-light

    p = Path(path or _BASELINE_PATH)
    raw = yaml.safe_load(p.read_text()) if p.exists() else {}
    raw = raw or {}
    entries = [
        DenylistEntry(
            symbol=item["symbol"],
            reason=item.get("reason", "platform denylist"),
            scope="platform",
            expires=_parse_date(item.get("expires")),
            added_by=item.get("added_by"),
        )
        for item in (raw.get("symbols") or [])
    ]
    return Denylist(entries=entries, categories=raw.get("categories") or {})


def merge(platform: Denylist, portfolio_entries: list[DenylistEntry]) -> Denylist:
    """Merge the platform baseline with per-portfolio (DB-sourced) entries."""
    return Denylist(entries=[*platform.entries, *portfolio_entries],
                    categories=platform.categories)


def _parse_date(v) -> date | None:
    if not v:
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v))


@dataclass(frozen=True)
class TradabilityInputs:
    """Per-symbol facts the caller supplies (from broker + trading.marketdata)."""

    tradable: bool            # broker says the symbol is currently tradable
    halted: bool              # exchange volatility (LULD) / trading halt
    price: float | None = None
    dollar_vol_20d: float | None = None
    is_leveraged_inverse: bool = False
    is_otc: bool = False


def buy_blocked_reason(symbol: str, asof: date, denylist: Denylist,
                       t: TradabilityInputs) -> str | None:
    """Full buy-side tradability gate: explicit denylist + auto + category rules.

    Returns the first block reason, or None if the symbol may be bought. Sells must
    NOT be routed through here.
    """
    # 1) hard tradability (broker / exchange)
    if not t.tradable:
        return "non-tradable at broker"
    if t.halted:
        return "halted (LULD/trading halt) — never buy into a halt"
    # 2) explicit symbol denylist (platform + portfolio)
    reason = denylist.blocked_reason(symbol, asof)
    if reason:
        return f"denylist: {reason}"
    # 3) category rules
    cats = denylist.categories or {}
    if cats.get("block_leveraged_inverse") and t.is_leveraged_inverse:
        return "category: leveraged/inverse ETF"
    if cats.get("block_otc_pinksheet") and t.is_otc:
        return "category: OTC/pink-sheet"
    min_price = cats.get("min_price")
    if min_price is not None and t.price is not None and t.price < float(min_price):
        return f"category: price ${t.price:.2f} < min ${float(min_price):.2f}"
    min_dv = cats.get("min_dollar_vol")
    if min_dv is not None and t.dollar_vol_20d is not None and t.dollar_vol_20d < float(min_dv):
        return f"category: 20d $vol below floor ${float(min_dv):,.0f}"
    return None
