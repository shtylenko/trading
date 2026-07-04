"""Parity audit — is this still the strategy I validated? (DESIGN §12).

Three signals; pure compare functions + a replay orchestrator:
  - **signal parity** — recompute ``build_candidates`` on a snapshot and compare the
    ranked book to what was actually proposed (catches code/data-loader drift).
  - **fill slippage** — realized fill price vs the modeled price under the release
    clock (the recorded target-book close), in bps.
  - **drift** — a result breaches when signal-match < band or |slippage| > band; the
    engine treats drift as active only after ``consecutive`` breaches (ledger), and
    then blocks risk-increasing orders.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DriftBands:
    min_signal_match_pct: float = 0.90    # < this → signal drift
    max_slippage_bps: float = 50.0        # |slippage| over this → fill drift


@dataclass
class ParityResult:
    signal_match_pct: float | None = None
    slippage_bps: float | None = None
    drift: bool = False
    detail: dict = field(default_factory=dict)


def signal_match(recorded_tickers: list[str], recomputed_tickers: list[str]) -> float:
    """Fraction of the recorded book reproduced by a recompute (order-insensitive)."""
    rec = list(recorded_tickers)
    if not rec:
        return 1.0 if not recomputed_tickers else 0.0
    overlap = len(set(rec) & set(recomputed_tickers))
    return overlap / len(rec)


def slippage_bps(fills: list[dict], expected_prices: dict[str, float]) -> float | None:
    """Quantity-weighted slippage vs expected, in bps. Positive = worse than modeled.

    ``fills``: [{ticker, side, qty, price}]. Buy paying more, or sell getting less,
    than expected is positive (cost). Names with no expected price are skipped.
    """
    num = den = 0.0
    for f in fills:
        exp = expected_prices.get(f["ticker"])
        if not exp or exp <= 0:
            continue
        sign = 1.0 if f["side"] == "buy" else -1.0
        bps = sign * (f["price"] - exp) / exp * 1e4
        w = abs(f["qty"]) * exp
        num += bps * w
        den += w
    return (num / den) if den > 0 else None


def evaluate(recorded_tickers: list[str], recomputed_tickers: list[str],
             fills: list[dict], expected_prices: dict[str, float],
             bands: DriftBands | None = None) -> ParityResult:
    bands = bands or DriftBands()
    sm = signal_match(recorded_tickers, recomputed_tickers)
    sl = slippage_bps(fills, expected_prices)
    drift = (sm < bands.min_signal_match_pct) or (sl is not None and abs(sl) > bands.max_slippage_bps)
    return ParityResult(signal_match_pct=sm, slippage_bps=sl, drift=drift,
                        detail={"min_signal_match": bands.min_signal_match_pct,
                                "max_slippage_bps": bands.max_slippage_bps,
                                "missing": sorted(set(recorded_tickers) - set(recomputed_tickers))})
