"""trading.live CLI — P0 control-plane operations (paper, no broker).

    python3 -m trading.live.cli plan --release x03 [--universe liquid_pit] [--asof YYYY-MM-DD]
    python3 -m trading.live.cli kill --on | --off
    python3 -m trading.live.cli status

`plan` builds + persists today's target book from validated code and prints it (no
orders, no broker). `kill` trips/resets the kill switch. `status` shows env + state.
"""
from __future__ import annotations

import argparse
from datetime import date

from trading.live import ledger
from trading.live.config import LiveConfig, load_env_config
from trading.live.engine import plan_portfolio, rebalance_portfolio


def _cmd_plan(args) -> None:
    asof = date.fromisoformat(args.asof) if args.asof else None
    book = plan_portfolio(args.release, asof=asof, universe_name=args.universe, mode=args.mode)
    print(f"\n=== {book.release_id} target book | asof {book.asof} | "
          f"ranked={book.ranked_count} target={len(book.entries)} blocked={len(book.blocked)} ===")
    for e in book.entries:
        sc = f"{e.score:+.4f}" if e.score is not None else "   n/a"
        px = f"${e.close:.2f}" if e.close else ""
        print(f"  #{e.rank:<3} {e.ticker:<6} score={sc}  {px}")
    if book.blocked:
        print("\nBlocked (buy-denied):")
        for b in book.blocked:
            print(f"  #{b.rank:<3} {b.ticker:<6} — {b.reason}")
    if not book.entries:
        print("  (empty — see warnings above; needs a live universe + marketdata)")


def _make_broker(kind: str, mode: str, prices: dict):
    """Construct a broker. P1 default is the FakeBroker (no creds needed for paper-fake)."""
    if kind == "fake":
        from trading.live.broker import FakeBroker
        return FakeBroker(prices=prices, mode=mode)
    if kind == "alpaca":
        import os
        from trading.live.broker import AlpacaBroker
        key, sec = os.getenv("ALPACA_API_KEY_ID", ""), os.getenv("ALPACA_SECRET_KEY", "")
        if not key or not sec:
            raise SystemExit("alpaca broker needs ALPACA_API_KEY_ID + ALPACA_SECRET_KEY")
        return AlpacaBroker(api_key=key, secret_key=sec, mode=mode)
    raise SystemExit(f"unknown broker {kind!r}")


def _cmd_rebalance(args) -> None:
    from trading.live.config import load_env_config
    from trading.live.context_builder import build_live_context
    from trading.live.engine import _load_universe
    from trading.live.logging import EventLogger
    from trading.lab.strategies import get_release_class

    env = load_env_config()
    asof = date.fromisoformat(args.asof) if args.asof else date.today()
    release = get_release_class(args.release)()
    cfg = LiveConfig(release_id=args.release, mode=args.mode, universe_name=args.universe)
    universe = _load_universe(args.universe, asof, EventLogger(env))
    if not universe:
        raise SystemExit("no universe → cannot rebalance")
    context = build_live_context(release, asof, universe, cfg)
    # prices for the fake broker (so paper-fake fills): last close per target/held name
    prices = {t: float(df["close"].iloc[-1]) for t, df in context.daily.items() if len(df)}
    broker = _make_broker(args.broker, args.mode, prices)

    res = rebalance_portfolio(args.portfolio, release, broker, context=context, asof=asof, env=env)
    print(f"\n=== rebalance {args.portfolio} ({args.release}, {args.mode}/{args.broker}) "
          f"asof {asof} ===")
    print(f"run={res.run_id}")
    print(f"target={len(res.target)}  auto-executed={len(res.auto_executed)}  "
          f"pending-approval={len(res.pending_approval)}")
    print("exec:", res.exec_report)
    if res.pending_approval:
        print("\nPending approval (use the UI/ledger to approve):")
        for p in res.pending_approval[:20]:
            print(f"  {p['ticker']:<6} approval={p['approval_id']}")


def _cmd_approve(args) -> None:
    env = load_env_config()
    ledger.init_db(env)
    with ledger.connect(env) as conn:
        rows = conn.execute(
            "SELECT approval_id, ticker FROM approvals WHERE proposal_id=? AND status='pending'",
            [args.proposal]).fetchall()
    picked = [r for r in rows if args.all or r["ticker"] in set(args.ticker or [])]
    for r in picked:
        ledger.decide_approval(r["approval_id"], "approved", by="cli", env=env)
    print(f"approved {len(picked)} order(s) on {args.proposal}")


def _cmd_execute(args) -> None:
    from datetime import date as _date
    from trading.live.config import load_env_config
    from trading.live.context_builder import build_live_context
    from trading.live.engine import _load_universe, execute_pending
    from trading.live.logging import EventLogger
    from trading.lab.strategies import get_release_class

    env = load_env_config()
    asof = _date.fromisoformat(args.asof) if args.asof else _date.today()
    # price the fake broker from a fresh context (alpaca prices itself)
    prices = {}
    if args.broker == "fake":
        release = get_release_class(args.release)()
        cfg = LiveConfig(release_id=args.release, mode=args.mode, universe_name=args.universe)
        uni = _load_universe(args.universe, asof, EventLogger(env))
        ctx = build_live_context(release, asof, uni, cfg) if uni else None
        prices = {t: float(df["close"].iloc[-1]) for t, df in (ctx.daily.items() if ctx else [])}
    broker = _make_broker(args.broker, args.mode, prices)
    rep = execute_pending(args.proposal, broker, asof=asof, portfolio_id=args.portfolio, env=env)
    print("execute:", rep)


def _cmd_refresh(args) -> None:
    """Pull current prices + account NAV from the broker → persist for the web UI
    (position current-value column + equity chart). Read-only against the broker."""
    env = load_env_config()
    broker = _make_broker(args.broker, args.mode, prices={})
    from trading.live.engine import refresh_market_state
    rep = refresh_market_state(args.portfolio, broker, source="manual", env=env)
    print(f"refresh {args.portfolio} ({args.broker}/{args.mode}):", rep)


def _cmd_sync(args) -> None:
    """Poll the broker for fills on a portfolio's open orders and book them to the ledger.

    Stand-in for the streaming fill feed: run after `execute` (or any time orders may
    have filled) so the ledger matches the broker before the next rebalance reconciles.
    """
    env = load_env_config()
    broker = _make_broker(args.broker, args.mode, prices={})
    from trading.live.engine import sync_fills
    rep = sync_fills(args.portfolio, broker, env=env)
    print(f"sync {args.portfolio} ({args.broker}/{args.mode}):", rep)


def _cmd_parity(args) -> None:
    from datetime import date as _date
    from trading.live.config import load_env_config
    from trading.live.context_builder import build_live_context
    from trading.live.engine import _load_universe, parity_check
    from trading.live.logging import EventLogger
    from trading.lab.strategies import get_release_class

    env = load_env_config()
    asof = _date.fromisoformat(args.asof) if args.asof else _date.today()
    release = get_release_class(args.release)()
    cfg = LiveConfig(release_id=args.release, universe_name=args.universe)
    uni = _load_universe(args.universe, asof, EventLogger(env))
    if not uni:
        raise SystemExit("no universe → cannot replay parity")
    ctx = build_live_context(release, asof, uni, cfg)
    print("parity:", parity_check(args.portfolio, release, context=ctx, asof=asof, env=env))


def _cmd_corpactions(args) -> None:
    """Apply corporate actions from a JSON file: [{symbol, ca_type, ex_date, ratio?, cash_per_share?}]."""
    import json
    from trading.live.config import load_env_config
    from trading.live.corporate_actions import CorporateAction, apply_actions

    env = load_env_config()
    actions = [CorporateAction(**a) for a in json.loads(open(args.file).read())]
    rep = apply_actions(args.portfolio, actions, env=env)
    print(f"corporate actions on {args.portfolio}: applied={rep.applied} "
          f"flagged={rep.flagged} skipped={len(rep.skipped)}")


def _cmd_backfill(args) -> None:
    """Rebuild the daily performance series from equity_snapshots (single source, no gaps)."""
    from trading.live.engine import backfill_performance_from_snapshots
    env = load_env_config()
    ledger.init_db(env)
    rep = backfill_performance_from_snapshots(args.portfolio, env=env)
    if "error" in rep:
        print(f"backfill {args.portfolio}: ERROR — {rep['error']}")
    else:
        print(f"backfill {args.portfolio}: {rep['n_days']} trading days "
              f"({rep['first_day']} → {rep['last_day']}), total return {rep.get('port_total_pct', 'N/A'):+.2f}%")


def _cmd_kill(args) -> None:
    env = load_env_config()
    ledger.init_db(env)
    if args.on:
        ledger.set_kill_switch(True, actor="cli", env=env)
        print("⛔ kill switch TRIPPED (DB + disk). No plans/orders until reset.")
    elif args.off:
        ledger.set_kill_switch(False, actor="cli", env=env)
        print("✅ kill switch RESET.")
    else:
        print("kill switch:", "ACTIVE" if ledger.is_kill_switch_active(env=env) else "off")


def _cmd_status(args) -> None:
    env = load_env_config()
    ledger.init_db(env)
    print(f"env={env.env}  live_allowed={env.live_allowed}  db={env.db_path}")
    print(f"web={env.web_host}:{env.web_port}  logs={env.log_dir}")
    print("kill switch:", "ACTIVE" if ledger.is_kill_switch_active(env=env) else "off")
    last = ledger.latest_run(env)
    if last:
        print(f"last run: {last['run_id']} state={last['state']} asof={last['asof']}")
    else:
        print("last run: (none yet)")


def main() -> None:
    p = argparse.ArgumentParser(prog="trading.live", description="Live control plane (P0)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("plan", help="build + persist today's target book (no broker)")
    pp.add_argument("--release", "-r", required=True, help="e.g. x03")
    pp.add_argument("--universe", default="liquid_pit", help="universe snapshot name")
    pp.add_argument("--asof", help="YYYY-MM-DD settled trading day (default: today)")
    pp.add_argument("--mode", default="paper", choices=("paper", "live"))
    pp.set_defaults(func=_cmd_plan)

    pr = sub.add_parser("rebalance", help="run a full paper rebalance (proposal→auto/approval)")
    pr.add_argument("--release", "-r", required=True, help="e.g. x03")
    pr.add_argument("--portfolio", "-p", default="x03-pf1", help="portfolio id")
    pr.add_argument("--universe", default="liquid_pit")
    pr.add_argument("--asof", help="YYYY-MM-DD (default: today)")
    pr.add_argument("--mode", default="paper", choices=("paper", "live"))
    pr.add_argument("--broker", default="fake", choices=("fake", "alpaca"),
                    help="fake (default, no creds) or alpaca paper")
    pr.set_defaults(func=_cmd_rebalance)

    pa = sub.add_parser("approve", help="approve pending orders of a proposal")
    pa.add_argument("--proposal", required=True)
    pa.add_argument("--ticker", nargs="*", help="ticker(s) to approve")
    pa.add_argument("--all", action="store_true", help="approve all pending")
    pa.set_defaults(func=_cmd_approve)

    pe = sub.add_parser("execute", help="execute approved (non-expired) orders of a proposal")
    pe.add_argument("--proposal", required=True)
    pe.add_argument("--release", "-r", required=True)
    pe.add_argument("--portfolio", "-p", default="x03-pf1")
    pe.add_argument("--universe", default="liquid_pit")
    pe.add_argument("--asof")
    pe.add_argument("--mode", default="paper", choices=("paper", "live"))
    pe.add_argument("--broker", default="fake", choices=("fake", "alpaca"))
    pe.set_defaults(func=_cmd_execute)

    psy = sub.add_parser("sync", help="poll broker for fills on open orders → book to ledger")
    psy.add_argument("--portfolio", "-p", default="x03-pf1")
    psy.add_argument("--mode", default="paper", choices=("paper", "live"))
    psy.add_argument("--broker", default="alpaca", choices=("fake", "alpaca"))
    psy.set_defaults(func=_cmd_sync)

    prf = sub.add_parser("refresh", help="pull current prices + NAV → equity chart + position values")
    prf.add_argument("--portfolio", "-p", default="x03-pf1")
    prf.add_argument("--mode", default="paper", choices=("paper", "live"))
    prf.add_argument("--broker", default="alpaca", choices=("fake", "alpaca"))
    prf.set_defaults(func=_cmd_refresh)

    pp2 = sub.add_parser("parity", help="replay parity for a portfolio's latest run")
    pp2.add_argument("--release", "-r", required=True)
    pp2.add_argument("--portfolio", "-p", default="x03-pf1")
    pp2.add_argument("--universe", default="liquid_pit")
    pp2.add_argument("--asof")
    pp2.set_defaults(func=_cmd_parity)

    pc = sub.add_parser("corpactions", help="apply corporate actions from a JSON file")
    pc.add_argument("--portfolio", "-p", default="x03-pf1")
    pc.add_argument("--file", required=True, help="JSON list of corporate actions")
    pc.set_defaults(func=_cmd_corpactions)

    pk = sub.add_parser("kill", help="trip/reset the kill switch")
    g = pk.add_mutually_exclusive_group()
    g.add_argument("--on", action="store_true", help="trip the kill switch")
    g.add_argument("--off", action="store_true", help="reset the kill switch")
    pk.set_defaults(func=_cmd_kill)

    pbf = sub.add_parser("backfill", help="rebuild daily performance series from equity snapshots (no broker needed)")
    pbf.add_argument("--portfolio", "-p", default="x03-pf1")
    pbf.set_defaults(func=_cmd_backfill)

    ps = sub.add_parser("status", help="show env + kill switch + last run")
    ps.set_defaults(func=_cmd_status)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
