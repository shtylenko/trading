"""FastAPI control plane (P3 — multi-portfolio monitor + control).

    python3 -m trading.live.web.app          # serves on env web_host:web_port

Overview of all portfolios, per-portfolio detail (positions / latest book / pending
approvals with approve+reject), onboarding, and per-portfolio + global kill switches.

Security (DESIGN §17): bind to the Tailscale/loopback interface only — never a public
port. Mutating actions require the ``X-Live-Token`` header (or ``token`` form field) to
match ``TRADING_LIVE_WEB_TOKEN`` when set; in dev (no token) they're open on loopback.
Every control action is written to the audit log with the actor.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Header, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from trading.live import ledger, portfolios
from trading.live.config import load_env_config
from trading.live.denylist import load_platform_denylist

_WEB_DIR = Path(__file__).resolve().parent
_TEMPLATES = Jinja2Templates(directory=str(_WEB_DIR / "templates"))
app = FastAPI(title="trading.live control plane", docs_url=None, redoc_url=None)
# vendored JS assets (TradingView Lightweight Charts) — served locally, no CDN/Tailscale egress
app.mount("/static", StaticFiles(directory=str(_WEB_DIR / "static")), name="static")


def _check_auth(token: Optional[str]) -> None:
    """Gate mutating actions. A token is REQUIRED in prod (refuse if unconfigured), and
    when configured (any env) it must match. Dev/testing on loopback may run open."""
    env = load_env_config()
    if env.env == "prod" and not env.web_token:
        raise HTTPException(status_code=503,
                            detail="control token not configured (set TRADING_LIVE_WEB_TOKEN in prod)")
    if env.web_token and token != env.web_token:
        raise HTTPException(status_code=401, detail="bad or missing control token")


def _portfolio_view(env, p) -> dict:
    pos = ledger.get_positions(p.portfolio_id, env=env)
    kill = ledger.is_kill_switch_active(p.portfolio_id, env=env)
    return {"cfg": p, "positions": pos, "n_positions": len(pos), "kill": kill}


# ── read views ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    env = load_env_config()
    ledger.init_db(env)
    pfs = [_portfolio_view(env, p) for p in portfolios.list_portfolios(env=env)]
    return _TEMPLATES.TemplateResponse(request, "overview.html", {
        "env": env,
        # global kill = DB global flag OR disk-file fail-safe (is_kill_switch_active
        # checks both); independent of how many portfolios exist.
        "global_kill": ledger.is_kill_switch_active(env=env),
        "portfolios": pfs,
        "denylist": load_platform_denylist().entries,
        "audit": ledger.recent_audit(10, env=env),
    })


@app.get("/portfolio/{portfolio_id}", response_class=HTMLResponse)
def monitor(request: Request, portfolio_id: str):
    """Monitor tab (default): equity chart + holdings + holdings insights. What you HOLD."""
    from trading.live.web import stats as stats_mod
    env = load_env_config()
    p = portfolios.get(portfolio_id, env=env)
    if p is None:
        raise HTTPException(404, "no such portfolio")
    ctx = _summary_ctx(env, portfolio_id)
    last = ledger.latest_run(env=env, portfolio_id=portfolio_id)
    book = json.loads(last["target_book"]) if last and last["target_book"] else []
    book_by_ticker = {e["ticker"]: e for e in book}
    chart = _equity_chart_points(ctx["series"])
    cap = getattr(p, "capital", 0) or 0
    holdings_stats = stats_mod.compute(_holdings_stats_rows(ctx["pos_view"], book_by_ticker),
                                       capital=cap)
    perf = ledger.latest_performance(portfolio_id, env=env)
    return _TEMPLATES.TemplateResponse(request, "monitor.html", {
        "env": env, "p": p, "active_tab": "monitor",
        "summary": ctx["summary"], "pending_count": ctx["pending_count"], "kill": ctx["kill"],
        "positions": ctx["pos_view"], "pos_totals": ctx["totals"],
        "holdings_stats": holdings_stats, "perf": perf,
        "perf_daily": json.loads(perf["daily_json"]) if perf and perf.get("daily_json") else [],
        "equity_json": json.dumps(chart), "equity_n": len(chart)})


@app.get("/portfolio/{portfolio_id}/manage", response_class=HTMLResponse)
def manage(request: Request, portfolio_id: str):
    """Manage tab: pending approvals + execution queue + rebalance insights + strategy target."""
    from trading.live.web import stats as stats_mod
    env = load_env_config()
    p = portfolios.get(portfolio_id, env=env)
    if p is None:
        raise HTTPException(404, "no such portfolio")
    ctx = _summary_ctx(env, portfolio_id)
    last = ledger.latest_run(env=env, portfolio_id=portfolio_id)
    book = json.loads(last["target_book"]) if last and last["target_book"] else []
    book_by_ticker = {e["ticker"]: e for e in book}
    positions = ctx["positions"]
    pending = _enrich_approvals(env, portfolio_id, "pending", book_by_ticker, positions, p)
    approved = _enrich_approvals(env, portfolio_id, "approved", book_by_ticker, positions, p,
                                 with_exec_state=True)
    cap = getattr(p, "capital", 0) or 0
    return _TEMPLATES.TemplateResponse(request, "manage.html", {
        "env": env, "p": p, "active_tab": "manage",
        "summary": ctx["summary"], "pending_count": ctx["pending_count"], "kill": ctx["kill"],
        "book": book, "pending": pending, "approved": approved,
        "pending_stats": stats_mod.compute(pending, capital=cap),
        "queue_stats": stats_mod.compute(approved, capital=cap),
        "n_pending": len(pending), "n_queue": len(approved)})


@app.get("/portfolio/{portfolio_id}/stats")
def stats_redirect(portfolio_id: str):
    """Back-compat: the stats page folded into the Manage tab."""
    return RedirectResponse(f"/portfolio/{portfolio_id}/manage", status_code=308)


def _pending_count(env, portfolio_id) -> int:
    with ledger.connect(env) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM approvals a JOIN order_proposals p "
            "ON a.proposal_id=p.proposal_id WHERE p.portfolio_id=? AND a.status='pending'",
            [portfolio_id]).fetchone()
        return int(row["c"]) if row else 0


def _summary_ctx(env, portfolio_id: str) -> dict:
    """Shared header context for both tabs: NAV/cash/value/unrealized + pending badge + kill.
    Also returns positions + equity series so the Monitor tab can reuse them."""
    positions = ledger.get_positions(portfolio_id, env=env)
    pos_view, totals = _positions_view(positions)
    series = ledger.equity_series(portfolio_id, env=env)
    nav = series[-1]["equity"] if series else totals["value"]
    cash = series[-1]["cash"] if series else None
    # last refresh = most recent snapshot ts (the 'now' point a refresh writes is the max);
    # ISO-UTC, converted to the viewer's local time in the browser.
    as_of = series[-1]["ts"] if series else None
    summary = {"nav": nav, "cash": cash, "value": totals["value"],
               "upnl": totals["upnl"], "upnl_pct": totals["upnl_pct"], "as_of": as_of}
    return {"positions": positions, "pos_view": pos_view, "totals": totals, "series": series,
            "summary": summary, "pending_count": _pending_count(env, portfolio_id),
            "kill": ledger.is_kill_switch_active(portfolio_id, env=env)}


def _holdings_stats_rows(pos_view: list[dict], book_by_ticker: dict) -> list[dict]:
    """Shape held positions into stats.compute rows (by current market value), joining the
    strategy score/rank from the latest target book where the held name still appears."""
    rows = []
    for r in pos_view:
        be = book_by_ticker.get(r["ticker"], {})
        rows.append({"ticker": r["ticker"], "side": "buy", "qty": r["qty"],
                     "price": r["last_price"], "notional": r["value"] or 0,
                     "rank": be.get("rank"), "score": be.get("score"),
                     "reason": "held", "held_qty": r["qty"]})
    return rows


def _equity_chart_points(series: list[dict]) -> list[dict]:
    """Build a REGULAR hourly NAV series for the chart.

    Lightweight Charts spaces points by index (ordinal axis), not by real elapsed time, so
    an irregular mix — Alpaca's uniform hourly broker history + ad-hoc per-refresh snapshots
    at arbitrary minutes — renders with wrong gaps (points minutes apart look the same width
    as points hours apart). Use the broker's regular hourly 'history' points; floor each to
    the hour so the grid is exactly uniform (index spacing == time spacing). Fall back to
    bucketing whatever exists if no history has been backfilled yet. Ascending, unique.
    """
    hist = [r for r in series if r.get("source") == "history"]
    src = hist if hist else series
    buckets: dict[int, float] = {}
    for r in src:
        u = _iso_to_unix(r["ts"])
        if u is None:
            continue
        buckets[u - (u % 3600)] = r["equity"]      # floor to the hour, last value wins
    return [{"time": h, "value": v} for h, v in sorted(buckets.items())]


def _iso_to_unix(ts: str):
    from datetime import datetime
    try:
        return int(datetime.fromisoformat(ts).timestamp())
    except (ValueError, TypeError):
        return None


def _positions_view(positions: dict) -> tuple[list[dict], dict]:
    """Add current value + unrealized P&L per position (from the last refreshed price),
    plus portfolio totals. Value/P&L are None when no price has been pulled yet."""
    rows, tot_val, tot_cost, priced = [], 0.0, 0.0, False
    for t, pos in sorted(positions.items()):
        qty = pos.get("qty") or 0.0
        avg = pos.get("avg_entry_price") or 0.0
        last = pos.get("last_price")
        value = (qty * last) if last else None
        cost = qty * avg
        upnl = (value - cost) if value is not None else None
        upnl_pct = (upnl / cost * 100) if (upnl is not None and cost) else None
        if value is not None:
            tot_val += value; tot_cost += cost; priced = True
        rows.append({"ticker": t, "qty": qty, "avg_entry_price": avg, "entry_date": pos.get("entry_date"),
                     "last_price": last, "last_price_at": pos.get("last_price_at"),
                     "value": value, "upnl": upnl, "upnl_pct": upnl_pct})
    totals = {"value": tot_val if priced else None,
              "upnl": (tot_val - tot_cost) if priced else None,
              "upnl_pct": ((tot_val - tot_cost) / tot_cost * 100) if (priced and tot_cost) else None}
    return rows, totals


def _enrich_approvals(env, portfolio_id, status, book_by_ticker, positions, cfg,
                      with_exec_state: bool = False) -> list[dict]:
    """Join each approval (of the given status) to its proposed order + book entry so the
    table can show decision context: side, qty, price, notional, weight, rank, score, why.
    When ``with_exec_state``, also report whether the order has been executed yet
    (queued → submitted/filled/rejected), read from the order_intents spine."""
    out: list[dict] = []
    with ledger.connect(env) as conn:
        rows = conn.execute(
            "SELECT a.approval_id, a.ticker, a.client_order_id, a.proposal_id FROM approvals a "
            "JOIN order_proposals p ON a.proposal_id=p.proposal_id "
            "WHERE p.portfolio_id=? AND a.status=? ORDER BY a.ticker",
            [portfolio_id, status]).fetchall()
        orders_by_proposal: dict[str, dict] = {}
        for r in rows:
            pid = r["proposal_id"]
            if pid not in orders_by_proposal:
                prow = conn.execute("SELECT orders FROM order_proposals WHERE proposal_id=?",
                                    [pid]).fetchone()
                orders_by_proposal[pid] = (
                    {o["coid"]: o for o in json.loads(prow["orders"])} if prow else {})
            o = orders_by_proposal[pid].get(r["client_order_id"], {})
            be = book_by_ticker.get(r["ticker"], {})
            price = be.get("close")
            qty = o.get("qty") or 0
            notional = (qty or 0) * (price or 0)
            capital = getattr(cfg, "capital", 0) or 0
            held = positions.get(r["ticker"])
            row = {
                "approval_id": r["approval_id"],
                "ticker": r["ticker"],
                "side": o.get("side", "?"),
                "qty": qty,
                "price": price,
                "notional": notional,
                "weight_pct": (notional / capital * 100) if capital else None,
                "rank": be.get("rank"),
                "score": be.get("score"),
                "reason": o.get("decision_reason") or o.get("reason") or "",
                "held_qty": held["qty"] if held else 0,
            }
            if with_exec_state:
                irow = conn.execute(
                    "SELECT status FROM order_intents WHERE client_order_id=?",
                    [r["client_order_id"]]).fetchone()
                row["exec_state"] = ("queued" if (irow is None or irow["status"] == "intent")
                                     else irow["status"])
            out.append(row)
    # default order: by target-book rank ascending (None ranks last)
    out.sort(key=lambda r: (r["rank"] is None, r["rank"] if r["rank"] is not None else 0))
    return out


@app.get("/healthz")
def healthz():
    env = load_env_config()
    return {"ok": True, "env": env.env, "portfolios": len(portfolios.list_portfolios(env=env)),
            "global_kill": ledger.is_kill_switch_active(env=env)}


# ── control actions (auth-gated, audited) ────────────────────────────────────
@app.post("/kill")
def toggle_kill(active: str = Form(...), portfolio_id: str = Form(""),
                token: str = Form(""), x_live_token: Optional[str] = Header(None)):
    _check_auth(token or x_live_token)
    env = load_env_config()
    ledger.set_kill_switch(active == "on", portfolio_id=portfolio_id or None,
                           actor="web", env=env)
    return RedirectResponse("/", status_code=303)


@app.post("/onboard")
def onboard(portfolio_id: str = Form(...), release_id: str = Form(...),
            universe: str = Form("liquid_pit"), capital: float = Form(0.0),
            mode: str = Form("paper"), fractional: bool = Form(False),
            token: str = Form(""), x_live_token: Optional[str] = Header(None)):
    _check_auth(token or x_live_token)
    env = load_env_config()
    portfolios.onboard(portfolio_id, release_id, universe=universe, capital=capital,
                       mode=mode, fractional=fractional, actor="web", env=env)
    return RedirectResponse("/", status_code=303)


def _broker_for(p):
    """Build the broker for a portfolio's refresh. Creds come from the environment, or
    fall back to the gitignored ``_state/<env>/alpaca.env`` so the long-running web
    process works without the operator exporting them into its shell."""
    import os
    from trading.live.secrets import ensure_broker_env
    env = load_env_config()
    mode = getattr(p, "mode", "paper")
    if not ensure_broker_env(env.state_dir):
        raise HTTPException(503, "broker creds not configured — set ALPACA_API_KEY_ID/SECRET "
                                 f"in the environment or in {env.state_dir / 'alpaca.env'}")
    from trading.live.broker import AlpacaBroker
    return AlpacaBroker(api_key=os.environ["ALPACA_API_KEY_ID"],
                        secret_key=os.environ["ALPACA_SECRET_KEY"], mode=mode)


@app.post("/refresh")
def refresh(portfolio_id: str = Form(...), token: str = Form(""),
            x_live_token: Optional[str] = Header(None)):
    """Pull current prices + NAV from the broker → update position values + equity chart."""
    _check_auth(token or x_live_token)
    env = load_env_config()
    p = portfolios.get(portfolio_id, env=env)
    if p is None:
        raise HTTPException(404, "no such portfolio")
    from trading.live.engine import refresh_market_state, backfill_performance_from_snapshots
    broker = _broker_for(p)
    rep = refresh_market_state(portfolio_id, broker, source="web", env=env)
    # backfill the daily performance series from equity_snapshots (single source, no gaps)
    try:
        backfill_performance_from_snapshots(portfolio_id, env=env)
    except Exception:
        pass  # backfill is best-effort enrichment
    ledger.audit("portfolio.refresh", actor="web",
                 detail=f"{portfolio_id} equity={rep['equity']} prices={rep['prices_updated']}", env=env)
    return RedirectResponse(f"/portfolio/{portfolio_id}", status_code=303)


@app.post("/approve")
def approve(approval_id: str = Form(...), decision: str = Form(...), portfolio_id: str = Form(""),
            token: str = Form(""), x_live_token: Optional[str] = Header(None)):
    _check_auth(token or x_live_token)
    env = load_env_config()
    status = "approved" if decision == "approve" else "rejected"
    ledger.decide_approval(approval_id, status, by="web", env=env)
    ledger.audit("approval.decide", actor="web", detail=f"{approval_id} -> {status}", env=env)
    # approvals live on the Manage tab — return there, not Monitor
    return RedirectResponse(f"/portfolio/{portfolio_id}/manage" if portfolio_id else "/",
                            status_code=303)


def main() -> None:
    import uvicorn
    env = load_env_config()
    # web_host binds to loopback/Tailscale interface only (DESIGN §17) — never 0.0.0.0 in prod.
    # In dev, auto-reload on code edits (import-string form required for reload).
    if env.env == "dev":
        uvicorn.run("trading.live.web.app:app", host=env.web_host, port=env.web_port, reload=True)
    else:
        uvicorn.run(app, host=env.web_host, port=env.web_port)


if __name__ == "__main__":
    main()
