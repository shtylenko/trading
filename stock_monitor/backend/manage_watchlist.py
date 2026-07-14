#!/usr/bin/env python3
"""
Manage the Webull "Today's Gap'n'Go" watchlist via OpenAPI.

Uses the same watchlist operations documented for Webull Cloud MCP:
  https://developer.webull.com/apis/docs/AI-friendly-Resources/mcp/

  get_watchlists              → list watchlists
  create_watchlist            → create if missing
  get_watchlist_instruments   → list symbols on a watchlist
  add_watchlist_instruments   → add tickers
  remove_watchlist_instruments→ remove tickers

This is a plain Python script (no LLM/MCP session). It calls the official
Webull OpenAPI Python SDK with app key/secret.

Credentials (backend/.env or environment):
  WEBULL_APP_KEY
  WEBULL_APP_SECRET
  WEBULL_ENVIRONMENT=prod|uat
  WEBULL_REGION_ID=us

Examples:
  # One-time browser OAuth login (Cloud MCP — paper/live account)
  python3 manage_watchlist.py login

  # List all Webull watchlists
  python3 manage_watchlist.py list

  # Show symbols currently on Today's Gap'n'Go
  python3 manage_watchlist.py show

  # Reconcile with today's local session DB:
  #   - add tickers that are in the session but not on the watchlist
  #   - remove tickers that are on the watchlist but no longer in the session
  python3 manage_watchlist.py sync --remove-stale

  # Manual add / remove
  python3 manage_watchlist.py add AAPL NVDA
  python3 manage_watchlist.py remove AAPL

  # Dry-run (no Webull writes)
  python3 manage_watchlist.py sync --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow `python3 manage_watchlist.py` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent))

import db as session_db
import webull_watchlist as wl


def _cfg(args: argparse.Namespace) -> dict:
    cfg = wl.load_config()
    if args.name:
        cfg["watchlist_name"] = args.name
    if args.dry_run:
        cfg["dry_run"] = True
    return cfg


# Reuse one client instance per process so dry-run state (created lists / symbols) persists
_CLIENT = None


def _client(cfg: dict):
    global _CLIENT
    dry = bool(cfg.get("dry_run"))
    if _CLIENT is not None and getattr(_CLIENT, "dry_run", False) == dry:
        return _CLIENT
    if dry:
        _CLIENT = wl.WebullWatchlistClient(data_client=None, dry_run=True)
        return _CLIENT
    # Prefer MCP OAuth (retail paper/live account) unless config says openapi_sdk
    cfg = dict(cfg)
    _CLIENT = wl.make_client(cfg)
    return _CLIENT


def _category(cfg: dict) -> str:
    return str(cfg.get("instrument_category") or "US_STOCK")


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_login(args: argparse.Namespace) -> int:
    """Browser OAuth login for Webull Cloud MCP (api.webull.com/mcp)."""
    import webull_mcp
    try:
        webull_mcp.login_interactive(open_browser=not args.no_browser)
    except webull_mcp.McpError as e:
        print(str(e), file=sys.stderr)
        return 1
    # Smoke-test: initialize + list tools path
    try:
        init = webull_mcp.initialize_session()
        print("MCP initialize OK:", json.dumps(init, default=str)[:200])
    except Exception as e:
        print(f"Note: MCP initialize after login: {e}")
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    import webull_mcp
    webull_mcp.clear_tokens()
    print("Cleared Cloud MCP tokens.")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """get_watchlists"""
    wl.load_dotenv()
    cfg = _cfg(args)
    try:
        client = _client(cfg)
        lists = client.get_watchlists()
    except Exception as e:
        print(str(e), file=sys.stderr)
        print("\nIf using MCP OAuth, run:  python manage_watchlist.py login", file=sys.stderr)
        return 1
    if getattr(client, "dry_run", False) and not lists:
        print("(dry-run — no live watchlists)")
        return 0
    if not lists:
        print("No watchlists returned (empty account or parse failed).")
        return 0
    print(f"{'ID':<40}  {'NAME'}")
    print("-" * 60)
    for w in lists:
        wid = str(w.get("watchlist_id") or w.get("id") or "?")
        name = w.get("name") or "?"
        marker = "  <-- target" if name == cfg.get("watchlist_name") else ""
        print(f"{wid:<40}  {name}{marker}")
    print(f"\n{len(lists)} watchlist(s)")
    print(f"auth_mode={cfg.get('auth_mode')}")
    return 0


def _resolve_watchlist(
    client: wl.WebullWatchlistClient,
    cfg: dict,
    *,
    create: bool = True,
) -> tuple[str, str]:
    """Return (watchlist_id, name). Optionally create if missing."""
    name = str(cfg.get("watchlist_name") or "Today's Gap'n'Go")
    lists = client.get_watchlists()
    for w in lists:
        if str(w.get("name") or "") == name:
            wid = w.get("watchlist_id") or w.get("id")
            if wid:
                return str(wid), name
    if not create:
        raise SystemExit(f"Watchlist {name!r} not found. Create it with: ensure")
    wid = client.create_watchlist(name)
    if not wid:
        raise SystemExit(f"create_watchlist failed for {name!r}")
    print(f"Created watchlist {name!r} → {wid}")
    return str(wid), name


def cmd_ensure(args: argparse.Namespace) -> int:
    """create_watchlist if missing"""
    wl.load_dotenv()
    cfg = _cfg(args)
    client = _client(cfg)
    wid, name = _resolve_watchlist(client, cfg, create=True)
    print(f"Watchlist ready: {name!r} id={wid}" + (" (dry-run)" if client.dry_run else ""))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """get_watchlist_instruments"""
    wl.load_dotenv()
    cfg = _cfg(args)
    client = _client(cfg)
    create = bool(args.create) or client.dry_run
    wid, name = _resolve_watchlist(client, cfg, create=create)
    instruments = client.get_instruments(wid)
    symbols = sorted(
        {(i.get("symbol") or "").upper() for i in instruments if i.get("symbol")}
    )
    print(f"Watchlist: {name!r}  id={wid}" + ("  [dry-run]" if client.dry_run else ""))
    if not symbols:
        print("(empty)")
    else:
        for s in symbols:
            print(f"  {s}")
        print(f"\n{len(symbols)} symbol(s)")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """add_watchlist_instruments"""
    wl.load_dotenv()
    cfg = _cfg(args)
    client = _client(cfg)
    symbols = sorted({s.upper().strip() for s in args.symbols if s.strip()})
    if not symbols:
        print("No symbols given.", file=sys.stderr)
        return 2
    wid, name = _resolve_watchlist(client, cfg, create=True)
    cat = _category(cfg)
    # Skip already present
    existing = {
        (i.get("symbol") or "").upper()
        for i in client.get_instruments(wid)
        if i.get("symbol")
    }
    to_add = [s for s in symbols if s not in existing]
    skipped = [s for s in symbols if s in existing]
    if skipped:
        print(f"Already on list (skip): {', '.join(skipped)}")
    if not to_add:
        print("Nothing to add.")
        return 0
    instruments = [{"symbol": s, "category": cat} for s in to_add]
    client.add_instruments(wid, instruments)
    mode = "DRY-RUN " if client.dry_run else ""
    print(f"{mode}Added to {name!r}: {', '.join(to_add)}")
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    """remove_watchlist_instruments"""
    wl.load_dotenv()
    cfg = _cfg(args)
    client = _client(cfg)
    symbols = sorted({s.upper().strip() for s in args.symbols if s.strip()})
    if not symbols:
        print("No symbols given.", file=sys.stderr)
        return 2
    # create=True only for dry-run memory continuity; live API still needs the list to exist
    wid, name = _resolve_watchlist(client, cfg, create=client.dry_run)
    cat = _category(cfg)
    existing = {
        (i.get("symbol") or "").upper()
        for i in client.get_instruments(wid)
        if i.get("symbol")
    }
    to_remove = [s for s in symbols if s in existing]
    missing = [s for s in symbols if s not in existing]
    if missing:
        print(f"Not on list (skip): {', '.join(missing)}")
    if not to_remove:
        print("Nothing to remove.")
        return 0
    instruments = [{"symbol": s, "category": cat} for s in to_remove]
    client.remove_instruments(wid, instruments)
    mode = "DRY-RUN " if client.dry_run else ""
    print(f"{mode}Removed from {name!r}: {', '.join(to_remove)}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """
    Reconcile Webull watchlist with local daily session tickers:
      - ADD symbols present in session but not on watchlist
      - REMOVE symbols on watchlist but not in today's session (if --remove-stale)
    """
    wl.load_dotenv()
    cfg = _cfg(args)
    client = _client(cfg)

    # Local session DB
    db_path = Path(args.db) if args.db else Path(__file__).parent / "data" / "stock_monitor.db"
    if not db_path.is_file():
        print(f"Session DB not found: {db_path}", file=sys.stderr)
        print("Run the receiver and collect Gap'n'Go tickers first.", file=sys.stderr)
        return 1
    session_db.set_db_path(db_path)
    wl.set_db_path(db_path)

    date = args.date or session_db.session_date_today()
    sess = session_db.get_session(date, include_tickers=True)
    session_tickers = sorted(
        {
            (t.get("ticker") or "").upper()
            for t in (sess or {}).get("tickers") or []
            if t.get("ticker")
        }
    )
    if not session_tickers and not args.allow_empty:
        print(f"No tickers in local session for {date}.")
        print("Use --allow-empty to clear the watchlist anyway (with --remove-stale).")
        return 0

    wid, name = _resolve_watchlist(client, cfg, create=True)
    cat = _category(cfg)
    current = {
        (i.get("symbol") or "").upper()
        for i in client.get_instruments(wid)
        if i.get("symbol")
    }

    to_add = sorted(set(session_tickers) - current)
    to_remove = sorted(current - set(session_tickers)) if args.remove_stale else []

    print(f"Session date : {date}")
    print(f"Watchlist    : {name!r}  id={wid}" + ("  [dry-run]" if client.dry_run else ""))
    print(f"Session size : {len(session_tickers)}")
    print(f"Watchlist sz : {len(current)}")
    print(f"To add       : {to_add or '—'}")
    print(f"To remove    : {to_remove or '—'}" + ("" if args.remove_stale else "  (pass --remove-stale to enable)"))

    if args.dry_run or client.dry_run:
        # Still record intended ops via client dry_run paths if we call them
        pass

    if to_add:
        instruments = [{"symbol": s, "category": cat} for s in to_add]
        client.add_instruments(wid, instruments)
        for s in to_add:
            wl._record_sync(
                date, s,
                status="dry_run" if client.dry_run else "synced",
                watchlist_id=wid,
                watchlist_name=name,
            )
        print(f"{'DRY-RUN ' if client.dry_run else ''}Added {len(to_add)}: {', '.join(to_add)}")

    if to_remove:
        instruments = [{"symbol": s, "category": cat} for s in to_remove]
        client.remove_instruments(wid, instruments)
        print(f"{'DRY-RUN ' if client.dry_run else ''}Removed {len(to_remove)}: {', '.join(to_remove)}")

    if not to_add and not to_remove:
        print("Already in sync.")

    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--name",
        default=None,
        help="Watchlist name (default: config / Today's Gap'n'Go)",
    )
    common.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write to Webull (log intended ops only)",
    )
    common.add_argument(
        "--db",
        default=None,
        help="Path to stock_monitor.db (default: backend/data/stock_monitor.db)",
    )

    p = argparse.ArgumentParser(
        description="Manage Webull watchlist (MCP-equivalent OpenAPI ops)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
        parents=[common],
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    p_login = sub.add_parser(
        "login",
        parents=[common],
        help="Browser OAuth login to Webull Cloud MCP (required once)",
    )
    p_login.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open browser; print URL only",
    )
    p_login.set_defaults(func=cmd_login)

    p_logout = sub.add_parser(
        "logout",
        parents=[common],
        help="Clear saved Cloud MCP OAuth tokens",
    )
    p_logout.set_defaults(func=cmd_logout)

    p_list = sub.add_parser(
        "list",
        parents=[common],
        help="get_watchlists — list all watchlists",
    )
    p_list.set_defaults(func=cmd_list)

    p_ens = sub.add_parser(
        "ensure",
        parents=[common],
        help="create_watchlist if missing",
    )
    p_ens.set_defaults(func=cmd_ensure)

    p_show = sub.add_parser(
        "show",
        parents=[common],
        help="get_watchlist_instruments — show symbols",
    )
    p_show.add_argument(
        "--create",
        action="store_true",
        help="Create the watchlist if it does not exist",
    )
    p_show.set_defaults(func=cmd_show)

    p_add = sub.add_parser(
        "add",
        parents=[common],
        help="add_watchlist_instruments",
    )
    p_add.add_argument("symbols", nargs="+", help="Ticker symbols")
    p_add.set_defaults(func=cmd_add)

    p_rm = sub.add_parser(
        "remove",
        parents=[common],
        help="remove_watchlist_instruments",
    )
    p_rm.add_argument("symbols", nargs="+", help="Ticker symbols")
    p_rm.set_defaults(func=cmd_remove)

    p_sync = sub.add_parser(
        "sync",
        parents=[common],
        help="Add session tickers not on list; optionally remove stale ones",
    )
    p_sync.add_argument(
        "--date",
        default=None,
        help="Session date YYYY-MM-DD (default: today America/New_York)",
    )
    p_sync.add_argument(
        "--remove-stale",
        action="store_true",
        help="Remove watchlist symbols that are not in the local session",
    )
    p_sync.add_argument(
        "--allow-empty",
        action="store_true",
        help="Allow sync when local session has zero tickers",
    )
    p_sync.set_defaults(func=cmd_sync)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
