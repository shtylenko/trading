#!/usr/bin/env python3
"""Build a rule-based point-in-time universe from Alpaca data.

Rule (per quarterly snapshot date): common US equities listed on NYSE /
NASDAQ / AMEX / ARCA / BATS where, over the 20 trading days strictly before
the snapshot date, the last close >= --min-price and the median daily dollar
volume >= --min-adv, with at least --min-active-days bars present.

Known limitation (documented, not hidden): the asset list comes from
Alpaca's *current* active assets, so tickers delisted before today are
missing from historical snapshots — residual survivorship bias that flatters
2022–2023 results. Treat early-year results as upper bounds.

Usage:
    python3 -m trading.lab.scripts.build_universe \\
        --start 2022-01-01 --end 2026-06-30 --out liquid_pit
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.marketdata.providers.alpaca_provider import _load_creds

UNIVERSES_DIR = Path(__file__).resolve().parents[1] / "universes"
CACHE_PATH = UNIVERSES_DIR / "_daily_screen_cache.parquet"

ALLOWED_EXCHANGES = {"NYSE", "NASDAQ", "AMEX", "ARCA", "BATS"}
SYMBOL_RE = re.compile(r"^[A-Z]{1,5}$")
# ETF/ETN issuers and non-common-stock instruments. Deliberately narrow:
# "TRUST"/"FUND" alone would also drop REITs and holdings companies.
NAME_EXCLUDE_RE = re.compile(
    r"\bETF\b|\bETN\b|ISHARES|VANGUARD|\bSPDR\b|PROSHARES|DIREXION|"
    r"WISDOMTREE|GLOBAL X|FIRST TRUST|INVESCO (?:.*\b(?:ETF|FUND|PORTFOLIO)\b)?|"
    r"\bWARRANT|\bRIGHTS?\b|\bUNITS?\b|PREFERRED|DEPOSITARY",
    re.IGNORECASE,
)


def quarterly_snapshot_dates(start: date, end: date) -> list[date]:
    dates = []
    d = date(start.year, ((start.month - 1) // 3) * 3 + 1, 1)
    while d <= end:
        if d >= start:
            dates.append(d)
        month = d.month + 3
        d = date(d.year + (month - 1) // 12, (month - 1) % 12 + 1, 1)
    return dates


def list_candidate_symbols() -> list[str]:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import AssetClass, AssetStatus
    from alpaca.trading.requests import GetAssetsRequest

    key, sec = _load_creds()
    tc = TradingClient(key, sec, paper=True)
    assets = tc.get_all_assets(
        GetAssetsRequest(asset_class=AssetClass.US_EQUITY, status=AssetStatus.ACTIVE)
    )
    out = []
    for a in assets:
        exch = getattr(a.exchange, "value", str(a.exchange))
        if exch not in ALLOWED_EXCHANGES:
            continue
        if not a.tradable:
            continue
        if not SYMBOL_RE.match(a.symbol or ""):
            continue
        if NAME_EXCLUDE_RE.search(a.name or ""):
            continue
        if a.symbol == "SPY":
            continue
        out.append(a.symbol)
    return sorted(set(out))


def fetch_daily_history(
    symbols: list[str], start: date, end: date, chunk_size: int = 500
) -> pd.DataFrame:
    """Daily close/volume for all symbols, cached to parquet across runs."""
    if CACHE_PATH.exists():
        cached = pd.read_parquet(CACHE_PATH)
        have = set(cached["symbol"].unique())
        lo, hi = cached["date"].min(), cached["date"].max()
        if set(symbols) <= have and lo <= pd.Timestamp(start) and hi >= pd.Timestamp(
            end
        ) - pd.Timedelta(days=7):
            print(f"Using cached daily screen data ({len(cached):,} rows)")
            return cached

    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    key, sec = _load_creds()
    client = StockHistoricalDataClient(key, sec)
    # the subscription rejects SIP queries that include the most recent
    # window, so never ask past yesterday
    end = min(end, date.today() - timedelta(days=1))
    frames: list[pd.DataFrame] = []
    for i in range(0, len(symbols), chunk_size):
        chunk = symbols[i : i + chunk_size]
        req = StockBarsRequest(
            symbol_or_symbols=chunk,
            timeframe=TimeFrame.Day,
            start=datetime(start.year, start.month, start.day),
            end=datetime(end.year, end.month, end.day, 23, 59),
            adjustment="raw",
            feed="sip",
        )
        bars = client.get_stock_bars(req)
        df = bars.df
        if df is None or df.empty:
            continue
        df = df.reset_index()[["symbol", "timestamp", "close", "volume"]]
        df["date"] = pd.to_datetime(df["timestamp"]).dt.tz_convert(
            "America/New_York"
        ).dt.normalize().dt.tz_localize(None)
        frames.append(df[["symbol", "date", "close", "volume"]])
        print(
            f"  fetched daily bars {i + len(chunk)}/{len(symbols)} symbols "
            f"({sum(len(f) for f in frames):,} rows)"
        )
    out = pd.concat(frames, ignore_index=True)
    UNIVERSES_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(CACHE_PATH, index=False)
    return out


def screen_snapshot(
    daily: pd.DataFrame,
    snap: date,
    min_price: float,
    min_adv: float,
    min_active_days: int,
    window: int = 20,
) -> list[str]:
    snap_ts = pd.Timestamp(snap)
    recent = daily[daily["date"] < snap_ts]
    # last `window` trading days before the snapshot, per the market calendar
    days = recent["date"].drop_duplicates().nlargest(window)
    if len(days) < min_active_days:
        return []
    win = recent[recent["date"].isin(days)]
    g = win.groupby("symbol")
    stats = pd.DataFrame(
        {
            "n_days": g.size(),
            "last_close": g.apply(lambda x: x.loc[x["date"].idxmax(), "close"]),
            "median_dollar_vol": g.apply(
                lambda x: (x["close"] * x["volume"]).median()
            ),
        }
    )
    ok = stats[
        (stats["n_days"] >= min_active_days)
        & (stats["last_close"] >= min_price)
        & (stats["median_dollar_vol"] >= min_adv)
    ]
    return sorted(ok.index.tolist())


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a PIT universe YAML")
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2026-06-30")
    parser.add_argument("--min-price", type=float, default=5.0)
    parser.add_argument("--min-adv", type=float, default=25_000_000.0)
    parser.add_argument("--min-active-days", type=int, default=15)
    parser.add_argument("--out", default="liquid_pit", help="Universe name (YAML stem)")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()
    snaps = quarterly_snapshot_dates(start, end)
    print(f"Snapshots: {snaps[0]} .. {snaps[-1]} ({len(snaps)} quarterly)")

    symbols = list_candidate_symbols()
    print(f"Candidate symbols after exchange/name screen: {len(symbols)}")

    daily = fetch_daily_history(symbols, start - timedelta(days=45), end)

    lines = [
        f"name: {args.out}",
        "description: >-",
        "  Rule-based point-in-time universe: NYSE/NASDAQ/AMEX/ARCA/BATS common",
        f"  stocks with prev-close >= ${args.min_price:g} and 20d median dollar volume",
        f"  >= ${args.min_adv:,.0f}, quarterly snapshots. Built from Alpaca's current",
        "  active asset list, so pre-2024 snapshots miss since-delisted names",
        "  (survivorship bias; treat early years as upper bounds).",
        "policy: point_in_time",
        "snapshots:",
    ]
    for snap in snaps:
        tickers = screen_snapshot(
            daily, snap, args.min_price, args.min_adv, args.min_active_days
        )
        print(f"  {snap}: {len(tickers)} tickers")
        lines.append(f'  - effective_date: "{snap.isoformat()}"')
        lines.append("    tickers:")
        # quote: bare ON/NO/YES etc. parse as YAML 1.1 booleans
        lines.extend(f'      - "{t}"' for t in tickers)

    out_path = UNIVERSES_DIR / f"{args.out}.yaml"
    out_path.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
