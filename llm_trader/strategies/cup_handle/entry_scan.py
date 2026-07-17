"""As-of (single-date) cup-and-handle entry scan.

Given a calendar date ``D`` and a ticker universe, list the cup-and-handle
buy-stop plans that a *causal* scan would publish at ``D``'s close — the
``prebreak_arm`` plans whose handle completes on ``D`` and whose buy-stop goes
live on a later session (``D+1 … D+arm_expiry_bars``).

This is the forward / daily-operations counterpart to the historical
:func:`run_scan`.  It is deliberately:

  * **Parity-preserving** — it reuses :func:`detect_ticker` /
    ``detect_from_frame``, the *same* detector the backtest and the discovery
    scan use.  There is no second copy of the cup geometry, so a live arm list
    matches what the backtest would have attributed to that day.
  * **Point-in-time** — it pins ``cfg.end = D`` so no bar dated after ``D`` is
    ever fetched or inspected (the detector only ever looks backward).  That
    single invariant is what makes the scan free of look-ahead.
  * **Read-only** — it never touches the ``EntryStore`` DB or
    ``entries.last_scan.json``.  It prints a table and, optionally, writes a
    dated JSON artifact.

The emitted rows are exactly what a deterministic arm executor needs to place
a buy-stop — trigger, stop, dual targets, ATR, and the arm-expiry / max-gap
guardrails — with no LLM in the loop.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, Sequence

from trading.llm_trader.fsutils import atomic_write_json
from trading.llm_trader.models import Entry

from .config import CupHandleConfig
from .patterns import detect_ticker, fetch_market_regime

log = logging.getLogger("llm_trader.cup_handle.entry_scan")

STRATEGY_ID = "cup_handle"

# The current listing universe (``universe.fetch_symbols``) reflects symbols
# trading *today*, so using it for an older ``D`` is survivorship-biased — it
# silently drops names that were delisted between ``D`` and now.  For anything
# but a near-current date the caller must supply a point-in-time universe.
LIVE_UNIVERSE_MAX_AGE_DAYS = 7


@dataclass
class AsofScanResult:
    """Outcome of one as-of scan (pure data; no side effects)."""

    day: date
    arms: list[Entry]
    symbols_requested: int
    symbols_scanned: list[str]
    symbols_failed: list[str]

    def to_dict(self) -> dict:
        return {
            "as_of": self.day.isoformat(),
            "strategy": STRATEGY_ID,
            "symbols_requested": self.symbols_requested,
            "symbols_scanned": len(self.symbols_scanned),
            "symbols_failed": self.symbols_failed,
            "arms": [_arm_row(a) for a in self.arms],
        }


def _arm_row(e: Entry) -> dict:
    """Flatten one arm into the fields an executor / report cares about."""
    f = e.features
    return {
        "ticker": e.ticker,
        "as_of": e.day.isoformat(),
        "trigger": f.get("entry_trigger", e.entry_px),
        "stop": f.get("stop_px"),
        "target1": f.get("target1_px"),
        "target2": f.get("target2_px"),
        "atr": f.get("atr"),
        "cup_depth_pct": f.get("cup_depth_pct"),
        "arm_expiry_bars": f.get("arm_expiry_bars"),
        "max_entry_gap_atr": f.get("max_entry_gap_atr"),
        "bar_close": e.bar_close,
        "reason": e.reason,
    }


def scan_asof(
    day: date,
    symbols: Sequence[str],
    cfg: CupHandleConfig,
    *,
    strategy_id: str = STRATEGY_ID,
    market_ok_dates: Optional[set] = None,
) -> AsofScanResult:
    """Return the cup-and-handle arms published at ``day``'s close.

    ``cfg`` is *cloned* with ``start = end = day`` (the caller's config is left
    untouched), which pins the detector's fetch window and per-bar emit filter
    to ``day``; no bar dated after ``day`` is fetched or inspected.

    Fails closed the same way :func:`run_scan` does: if the fraction of symbols
    that error out exceeds ``cfg.max_scan_failure_rate`` a ``RuntimeError`` is
    raised rather than returning a silently short arm list.
    """
    scan_cfg = replace(cfg, start=day, end=day)
    scan_cfg.validate()

    ordered = list(dict.fromkeys(s.strip().upper() for s in symbols if s and s.strip()))
    if not ordered:
        raise ValueError("scan_asof requires at least one symbol")

    # Fetch the SPY regime once (if enabled) rather than per symbol.
    if scan_cfg.require_spy_above_sma50 and market_ok_dates is None:
        market_ok_dates = fetch_market_regime(scan_cfg)

    arms: list[Entry] = []
    scanned: list[str] = []
    failed: list[str] = []
    for sym in ordered:
        try:
            found = detect_ticker(
                sym, scan_cfg, strategy_id=strategy_id, market_ok_dates=market_ok_dates
            )
        except Exception:
            log.exception("as-of scan failed for %s", sym)
            failed.append(sym)
            continue
        scanned.append(sym)
        arms.extend(found)

    failure_rate = len(failed) / len(ordered)
    if failure_rate > scan_cfg.max_scan_failure_rate:
        raise RuntimeError(
            f"as-of scan failed closed: {len(failed)}/{len(ordered)} symbols "
            f"({failure_rate:.2%}) failed, exceeding max_scan_failure_rate="
            f"{scan_cfg.max_scan_failure_rate:.2%}"
        )

    arms.sort(key=lambda e: e.ticker)
    return AsofScanResult(
        day=day,
        arms=arms,
        symbols_requested=len(ordered),
        symbols_scanned=scanned,
        symbols_failed=failed,
    )


# --------------------------------------------------------------------------- #
# Universe resolution
# --------------------------------------------------------------------------- #
def _load_universe_file(path: Path) -> list[str]:
    """Parse a universe file: JSON array/object, or newline/comma text.

    ``#`` starts a comment (whole-line or trailing).
    """
    path = Path(path)
    if not path.exists():
        raise ValueError(f"universe file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text[0] in "[{":
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("symbols", [])
        return [str(s).strip() for s in data if str(s).strip()]
    out: list[str] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        out.extend(tok for tok in line.replace(",", " ").split() if tok)
    return out


def resolve_universe(
    day: date,
    *,
    symbols: Optional[Sequence[str]],
    universe_file: Optional[str],
    exchanges: Sequence[str],
    today: Optional[date] = None,
) -> list[str]:
    """Resolve the ticker universe, refusing survivorship-biased fallbacks.

    Precedence: explicit ``symbols`` → ``universe_file`` → the live listing
    universe.  The live fallback is only permitted for a near-current ``day``;
    for an older date the caller must pass a point-in-time universe or the scan
    would snoop on which names survived to today.
    """
    if symbols:
        return list(symbols)
    if universe_file:
        return _load_universe_file(Path(universe_file))
    today = today or date.today()
    if day < today - timedelta(days=LIVE_UNIVERSE_MAX_AGE_DAYS):
        raise ValueError(
            f"refusing to use the current (survivorship-biased) listing universe "
            f"for the historical date {day.isoformat()}; pass --symbols or "
            f"--universe-file with the point-in-time constituents as of that date"
        )
    from trading.llm_trader.universe import fetch_symbols

    return list(fetch_symbols(tuple(exchanges)))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def _print_table(result: AsofScanResult, stream=sys.stdout) -> None:
    rows = [_arm_row(a) for a in result.arms]
    print(
        f"cup_handle arms as of {result.day.isoformat()} — "
        f"{len(rows)} plan(s) from {result.symbols_requested} symbol(s)",
        file=stream,
    )
    if result.symbols_failed:
        print(f"  failed: {', '.join(result.symbols_failed)}", file=stream)
    if not rows:
        print("  (no plans)", file=stream)
        return
    cols = [
        "ticker", "trigger", "stop", "target1", "target2",
        "atr", "cup_depth_pct", "arm_expiry_bars",
    ]
    widths = {c: max([len(c)] + [len(_fmt(r[c])) for r in rows]) for c in cols}
    print("  " + "  ".join(c.rjust(widths[c]) for c in cols), file=stream)
    for r in rows:
        print("  " + "  ".join(_fmt(r[c]).rjust(widths[c]) for c in cols), file=stream)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cup_handle.entry_scan",
        description=(
            "List cup-and-handle buy-stop plans armed as of a given date "
            "(causal, read-only; reuses the backtest detector)."
        ),
    )
    p.add_argument(
        "--date",
        required=True,
        help="As-of date YYYY-MM-DD (plans are published at this session's close).",
    )
    g = p.add_argument_group("universe (explicit sources are required for historical dates)")
    g.add_argument("--symbols", nargs="+", help="Explicit tickers (point-in-time universe).")
    g.add_argument(
        "--universe-file",
        help="File of tickers: JSON array/object or newline/comma text ('#' comments).",
    )
    p.add_argument(
        "--config",
        help="CupHandleConfig YAML (thresholds only; --date overrides start/end).",
    )
    p.add_argument(
        "--max-symbols", type=int, help="Scan only the first N symbols (pipeline test)."
    )
    p.add_argument(
        "--max-scan-failure-rate",
        type=float,
        help=(
            "Tolerate up to this fraction of symbols failing to fetch before the scan "
            "fails closed (default 0.0). Raise it (e.g. 0.02) for large universes where "
            "a few names may not resolve on a given date."
        ),
    )
    p.add_argument("--json", help="Also write the structured result to this path.")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = _build_parser().parse_args(argv)
    try:
        day = date.fromisoformat(args.date)
    except ValueError:
        print(f"error: --date must be YYYY-MM-DD, got {args.date!r}", file=sys.stderr)
        return 2

    cfg = CupHandleConfig.from_yaml(args.config) if args.config else CupHandleConfig()
    if args.max_scan_failure_rate is not None:
        cfg.max_scan_failure_rate = args.max_scan_failure_rate
    try:
        universe = resolve_universe(
            day,
            symbols=args.symbols,
            universe_file=args.universe_file,
            exchanges=cfg.exchanges,
        )
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.max_symbols is not None:
        universe = universe[: args.max_symbols]
    if not universe:
        print("error: resolved universe is empty", file=sys.stderr)
        return 2

    result = scan_asof(day, universe, cfg)
    _print_table(result)
    if args.json:
        atomic_write_json(Path(args.json), result.to_dict())
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
