"""Aggregate analytics over a set of proposed orders (web stats page).

Pure + testable: takes the enriched approval rows (see app._enrich_approvals) and a
capital figure, returns sector / capital / concentration / conviction / composition
aggregates. No marketdata — sector comes from the lab's sector_map.yaml (a lookup),
everything else from the proposal/book fields already on each row.
"""
from __future__ import annotations

import statistics
from functools import lru_cache
from pathlib import Path

# SPDR sector ETF → human label (matches sector_map.yaml's `etfs`).
SECTOR_NAMES = {
    "XLB": "Materials", "XLC": "Communication Svcs", "XLE": "Energy",
    "XLF": "Financials", "XLI": "Industrials", "XLK": "Technology",
    "XLP": "Consumer Staples", "XLRE": "Real Estate", "XLU": "Utilities",
    "XLV": "Health Care", "XLY": "Consumer Discretionary",
}

# stats.py is trading/live/web/ → parents[2] is the `trading` package root.
_SECTOR_MAP_PATH = (Path(__file__).resolve().parents[2]
                    / "lab" / "universes" / "sector_map.yaml")


@lru_cache(maxsize=1)
def load_sector_map(path: str | None = None) -> dict[str, str]:
    """ticker -> SPDR sector ETF (cached). Empty dict if the map is unavailable."""
    import yaml
    p = Path(path) if path else _SECTOR_MAP_PATH
    if not p.exists():
        return {}
    raw = yaml.safe_load(p.read_text()) or {}
    return {k.upper(): v for k, v in (raw.get("map") or {}).items()}


def _median(xs):
    return statistics.median(xs) if xs else None


def compute(rows: list[dict], *, capital: float = 0.0,
            sector_map: dict[str, str] | None = None) -> dict:
    """Aggregate one set of proposed orders (pending OR queue) into display stats."""
    sector_map = sector_map if sector_map is not None else load_sector_map()
    n = len(rows)
    if n == 0:
        return {"n": 0}

    buys = [r for r in rows if r.get("side") == "buy"]
    sells = [r for r in rows if r.get("side") == "sell"]
    buy_notional = sum(r.get("notional") or 0 for r in buys)
    sell_notional = sum(r.get("notional") or 0 for r in sells)

    # ── sector distribution (by buy notional + count; sells reduce exposure) ──
    sectors: dict[str, dict] = {}
    for r in rows:
        etf = sector_map.get((r.get("ticker") or "").upper(), "—")
        name = SECTOR_NAMES.get(etf, "Unmapped" if etf == "—" else etf)
        s = sectors.setdefault(name, {"sector": name, "count": 0, "notional": 0.0})
        s["count"] += 1
        if r.get("side") == "buy":
            s["notional"] += r.get("notional") or 0
    total_sec_notional = sum(s["notional"] for s in sectors.values()) or 0.0
    for s in sectors.values():
        s["pct"] = (s["notional"] / total_sec_notional * 100) if total_sec_notional else 0.0
    sector_rows = sorted(sectors.values(), key=lambda s: (-s["notional"], -s["count"]))

    # ── concentration over the BUY book (the exposure being added) ──
    buy_notionals = sorted((r.get("notional") or 0 for r in buys), reverse=True)
    tot = sum(buy_notionals) or 0.0
    shares = [bn / tot for bn in buy_notionals] if tot else []
    hhi = sum(sh * sh for sh in shares)
    concentration = {
        "top5_pct": (sum(buy_notionals[:5]) / tot * 100) if tot else None,
        "max_weight_pct": (buy_notionals[0] / tot * 100) if buy_notionals else None,
        "hhi": round(hhi, 3) if shares else None,
        "effective_n": round(1 / hhi, 1) if hhi else None,
    }

    # ── conviction (rank/score over all rows) ──
    scores = [r["score"] for r in rows if r.get("score") is not None]
    ranks = [r["rank"] for r in rows if r.get("rank") is not None]
    conviction = {
        "score_min": min(scores) if scores else None,
        "score_med": _median(scores),
        "score_max": max(scores) if scores else None,
        "rank_min": min(ranks) if ranks else None,
        "rank_max": max(ranks) if ranks else None,
    }

    # ── composition ──
    reasons: dict[str, int] = {}
    for r in rows:
        reasons[r.get("reason") or "—"] = reasons.get(r.get("reason") or "—", 0) + 1
    new_positions = sum(1 for r in buys if not r.get("held_qty"))
    adds = sum(1 for r in buys if r.get("held_qty"))

    return {
        "n": n,
        "capital": {
            "buy_notional": buy_notional, "sell_notional": sell_notional,
            "net_notional": buy_notional - sell_notional,
            "buy_pct_of_capital": (buy_notional / capital * 100) if capital else None,
            "n_buys": len(buys), "n_sells": len(sells),
        },
        "sectors": sector_rows,
        "concentration": concentration,
        "conviction": conviction,
        "composition": {"new_positions": new_positions, "adds": adds,
                        "reasons": sorted(reasons.items(), key=lambda kv: -kv[1])},
    }
