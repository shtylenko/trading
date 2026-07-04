"""Engine orchestration.

P0 (`plan_portfolio`): env + kill-switch gate → pin the release → build the live
StrategyContext (parity) → snapshot-hash → pure planner → persist + log. No broker.

P1 (`rebalance_portfolio`): the full state machine on PAPER — reconcile broker vs
ledger → plan → diff held-vs-target → classify (auto/approval) → persist proposal +
park approvals → execute auto (idempotent) → reconcile. `execute_pending` runs orders
after you approve them. Broker is injected (FakeBroker in tests/dev, AlpacaBroker paper).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone

from trading.live import ledger, portfolio as portfolio_mod
from trading.live import executor as executor_mod
from trading.live.broker import Account, BrokerBase, OrderRequest
from trading.live.config import EnvConfig, LiveConfig, load_env_config
from trading.live.context_builder import build_live_context
from trading.live.denylist import Denylist, load_platform_denylist, merge
from trading.live.logging import EventLogger
from trading.live.manifest import ReleaseManifest, capture_manifest, verify_pinned
from trading.live.planner import TargetBook, build_target_book
from trading.live.policy import ApprovalPolicy, classify
from trading.live.reconcile import reconcile_positions
from trading.live.risk import RiskAssessment, RiskPolicy, assess as assess_risk
from trading.live.notifications import Notifier, Severity, default_notifier
from trading.lab.strategies import get_release_class


def _snapshot_hash(context, asof: date) -> str:
    """Deterministic hash of the marketdata inputs feeding the ranking (DESIGN §6)."""
    parts = [f"asof={asof.isoformat()}"]
    daily = getattr(context, "daily", None) or {}
    for t in sorted(daily):
        df = daily[t]
        try:
            parts.append(f"{t}:{len(df)}:{float(df['close'].iloc[-1]):.4f}")
        except Exception:
            parts.append(f"{t}:na")
    if getattr(context, "spy_daily", None) is not None and len(context.spy_daily):
        parts.append(f"SPY:{float(context.spy_daily['close'].iloc[-1]):.4f}")
    return "sha256:" + hashlib.sha256("|".join(parts).encode()).hexdigest()


def _load_universe(name: str, asof: date, log: EventLogger) -> list[str]:
    from trading.lab.data.universes import load_universe_tickers
    try:
        return list(load_universe_tickers(name, asof))
    except Exception as exc:
        log.emit("data.error", level="WARN", component="engine",
                 message=f"universe '{name}' unavailable", data={"error": str(exc)})
        return []


def plan_portfolio(release_id: str, *, asof: date | None = None,
                   universe_name: str = "liquid_pit", mode: str = "paper",
                   pinned: ReleaseManifest | None = None,
                   env: EnvConfig | None = None,
                   portfolio_id: str | None = None) -> TargetBook:
    """Build + persist today's target book for a release. Returns the TargetBook."""
    env = env or load_env_config()
    env.require_mode_allowed(mode)
    asof = asof or date.today()
    run_id = f"run_{release_id}_{asof.isoformat()}_{uuid.uuid4().hex[:8]}"
    log = EventLogger(env)
    ledger.init_db(env)

    release = get_release_class(release_id)()
    manifest = pinned or capture_manifest(release)
    log.emit("run.start", component="engine", release_id=release_id, run_id=run_id,
             mode=mode, portfolio_id=portfolio_id,
             data={"asof": asof.isoformat(), "code_hash": manifest.code_hash,
                   "universe": universe_name, "pinned": pinned is not None})

    # Invariant gates (DESIGN §2): kill switch + release pin. (Mode/env already checked.)
    if ledger.is_kill_switch_active(env=env):
        log.emit("killswitch.changed", level="WARN", component="engine", run_id=run_id,
                 message="kill switch active — no plan produced")
        ledger.record_run(run_id, release_id=release_id, asof=asof, mode=mode,
                          state="blocked", code_hash=manifest.code_hash,
                          portfolio_id=portfolio_id, env=env)
        raise SystemExit("⛔ kill switch active")
    verify_pinned(release, manifest)  # raises ReleasePinMismatch on drift

    # Build context (parity with the lab swing backtest).
    cfg = LiveConfig(release_id=release_id, mode=mode, universe_name=universe_name)
    universe = _load_universe(universe_name, asof, log)
    if not universe:
        ledger.record_run(run_id, release_id=release_id, asof=asof, mode=mode,
                          state="failed", code_hash=manifest.code_hash,
                          portfolio_id=portfolio_id, env=env)
        log.emit("run.end", level="WARN", component="engine", run_id=run_id,
                 message="no universe → empty plan")
        return TargetBook(release_id=release_id, asof=asof)

    context = build_live_context(release, asof, universe, cfg)
    snap = _snapshot_hash(context, asof)
    log.emit("marketdata.snapshot", component="engine", run_id=run_id,
             data={"snapshot_hash": snap, "universe": universe_name,
                   "ranked_context": len(context.daily)})
    log.emit("context.built", component="engine", run_id=run_id,
             data={"tickers": len(context.daily)})

    # Plan (pure) + denylist gate.
    pf_entries = ledger.active_denylist(portfolio_id, asof, env=env) if portfolio_id else []
    denylist: Denylist = merge(load_platform_denylist(), pf_entries)
    book = build_target_book(release, context, denylist, asof=asof)
    log.emit("ranking.done", component="engine", run_id=run_id,
             data={"ranked": book.ranked_count, "target": len(book.entries),
                   "blocked": len(book.blocked)})
    for b in book.blocked:
        log.emit("tradability.blocked", level="WARN", component="engine", run_id=run_id,
                 data={"ticker": b.ticker, "rank": b.rank, "reason": b.reason})

    ledger.record_run(
        run_id, release_id=release_id, asof=asof, mode=mode, state="proposal_created",
        code_hash=manifest.code_hash, snapshot_hash=snap, portfolio_id=portfolio_id, env=env,
        target_book=[asdict(e) for e in book.entries],
        blocked=[asdict(b) for b in book.blocked],
    )
    log.emit("run.end", component="engine", run_id=run_id,
             message="target book ready", data={"run_id": run_id})
    return book


# ── P1: full rebalance state machine (paper) ─────────────────────────────────

class RebalanceBlocked(RuntimeError):
    """Raised when an invariant blocks the rebalance (kill switch / reconcile mismatch)."""


def _ensure_identity(portfolio_id: str, broker: BrokerBase, *, env, log, notifier,
                     run_id: str, on_block=None) -> None:
    """Account-identity gate (invariant #3). If the portfolio is bound to an account,
    the broker reached must BE that account; if unbound, bind it on first connect.
    ``on_block`` (optional) records a blocked run before raising RebalanceBlocked."""
    from trading.live import portfolios as _pf
    from trading.live.secrets import IdentityMismatch, account_id_hash, verify_account_identity
    cfg = _pf.get(portfolio_id, env=env)
    if cfg is None:
        return
    acct = broker.get_account()
    if cfg.account_id_hash:
        try:
            verify_account_identity(acct.account_id, cfg.account_id_hash)
        except IdentityMismatch as exc:
            if on_block:
                on_block()
            log.emit("broker.error", level="ERROR", component="engine", run_id=run_id,
                     portfolio_id=portfolio_id, message="account identity mismatch",
                     error={"type": "IdentityMismatch", "detail": str(exc)})
            notifier.notify(Severity.CRITICAL, f"{portfolio_id}: account identity mismatch",
                            str(exc), portfolio_id=portfolio_id)
            raise RebalanceBlocked(str(exc))
    elif acct.account_id:
        _pf.bind_account(portfolio_id, account_id_hash(acct.account_id), env=env)


@dataclass
class RebalanceResult:
    run_id: str
    proposal_id: str
    target: list[str] = field(default_factory=list)
    auto_executed: list[str] = field(default_factory=list)
    pending_approval: list[dict] = field(default_factory=list)   # {approval_id, ticker, coid}
    exec_report: dict = field(default_factory=dict)


def _order_dict(o: OrderRequest, auto: bool, reason: str, coid: str) -> dict:
    return {"ticker": o.ticker, "side": o.side, "qty": o.qty, "style": o.style,
            "reason": o.reason, "coid": coid, "auto": auto, "decision_reason": reason}


def rebalance_portfolio(portfolio_id: str, release, broker: BrokerBase, *, context,
                        asof: date, policy: ApprovalPolicy | None = None,
                        risk_policy: RiskPolicy | None = None,
                        notifier: Notifier | None = None,
                        day_pnl_pct: float | None = None, drawdown_pct: float | None = None,
                        pinned: ReleaseManifest | None = None,
                        env: EnvConfig | None = None,
                        universe_label: str = "(injected)") -> RebalanceResult:
    """Run one paper rebalance: reconcile → plan → diff → risk → classify → auto-execute.

    ``context`` is injected (caller builds it; keeps this testable). Broker truth is
    the pre-trade source for held positions; the ledger is reconciled against it first.
    """
    env = env or load_env_config()
    env.require_mode_allowed(broker.mode)
    policy = policy or ApprovalPolicy()
    risk_policy = risk_policy or RiskPolicy()
    notifier = notifier or default_notifier()
    asof = asof or date.today()
    run_id = f"reb_{release.release_id}_{asof.isoformat()}_{uuid.uuid4().hex[:8]}"
    proposal_id = f"prop_{run_id}"
    log = EventLogger(env)
    ledger.init_db(env)
    manifest = pinned or capture_manifest(release)

    log.emit("run.start", component="engine", release_id=release.release_id, run_id=run_id,
             mode=broker.mode, portfolio_id=portfolio_id,
             data={"asof": asof.isoformat(), "code_hash": manifest.code_hash})

    # invariants: kill switch (global OR this portfolio's) + release pin + identity
    if ledger.is_kill_switch_active(portfolio_id, env=env):
        ledger.record_run(run_id, release_id=release.release_id, asof=asof, mode=broker.mode,
                          state="blocked", portfolio_id=portfolio_id, env=env)
        log.emit("killswitch.changed", level="WARN", component="engine", run_id=run_id,
                 message="kill switch active")
        raise RebalanceBlocked("kill switch active")
    verify_pinned(release, manifest)

    # account identity (invariant #3) — bind on first connect, block on mismatch
    _ensure_identity(portfolio_id, broker, env=env, log=log, notifier=notifier, run_id=run_id,
                     on_block=lambda: ledger.record_run(
                         run_id, release_id=release.release_id, asof=asof, mode=broker.mode,
                         state="blocked", portfolio_id=portfolio_id, env=env))

    # reconcile broker vs ledger BEFORE acting (DESIGN §10.2)
    broker_positions = broker.get_positions()
    led_positions = ledger.get_positions(portfolio_id, env=env)
    rec = reconcile_positions(broker_positions, led_positions)
    if not rec.ok:
        ledger.record_run(run_id, release_id=release.release_id, asof=asof, mode=broker.mode,
                          state="blocked", portfolio_id=portfolio_id, env=env)
        log.emit("reconcile.mismatch", level="ERROR", component="engine", run_id=run_id,
                 portfolio_id=portfolio_id, data=rec.as_dict())
        notifier.notify(Severity.CRITICAL, f"{portfolio_id}: reconciliation mismatch",
                        str(rec.as_dict()), portfolio_id=portfolio_id)
        raise RebalanceBlocked(f"reconciliation mismatch: {rec.as_dict()}")
    log.emit("reconcile.ok", component="engine", run_id=run_id, portfolio_id=portfolio_id)

    # hold-timer authority is the LEDGER's entry_date — some broker position feeds
    # (e.g. Alpaca) don't carry one, which would make the time exit never fire. Merge
    # the ledger entry_date onto the broker-truth positions used for the held-vs-target diff.
    for tk, pos in broker_positions.items():
        if pos.entry_date is None and tk in led_positions:
            pos.entry_date = led_positions[tk].get("entry_date")

    # plan target book (parity) + denylist gate (platform YAML + per-portfolio DB entries)
    denylist: Denylist = merge(load_platform_denylist(),
                               ledger.active_denylist(portfolio_id, asof, env=env))
    book = build_target_book(release, context, denylist, asof=asof)
    snap = _snapshot_hash(context, asof)
    log.emit("ranking.done", component="engine", run_id=run_id, portfolio_id=portfolio_id,
             data={"ranked": book.ranked_count, "target": len(book.entries),
                   "blocked": len(book.blocked)})

    # diff held (broker truth) vs target → orders
    account = broker.get_account()
    from trading.live import portfolios as _pf
    pcfg = _pf.get(portfolio_id, env=env)
    cfg = LiveConfig(release_id=release.release_id, mode=broker.mode,
                     capital=(pcfg.capital if pcfg else 0.0),
                     fractional=(pcfg.fractional if pcfg else False))
    prices = {e.ticker: (e.close or 0.0) for e in book.entries}
    orders = portfolio_mod.reconcile(book.tickers, broker_positions, account,
                                     hold_days=int(getattr(release, "hold_days", 20)),
                                     asof=asof, config=cfg, prices=prices)
    # attach deterministic client_order_ids
    for o in orders:
        o.client_order_id = executor_mod.client_order_id(portfolio_id, o.ticker, o.side, asof)

    # %-of-capital limits (risk + approval bands) measure against the portfolio's
    # CONFIGURED capital, not the broker account equity — same basis as sizing, so a $5k
    # allocation on a $100k account doesn't render every limit ~20x too loose.
    equity_basis = (pcfg.capital if pcfg and pcfg.capital > 0 else account.equity)

    # ── pre-trade risk gate (DESIGN §7) ──
    risk = assess_risk(orders, account=account, positions=broker_positions, prices=prices,
                       policy=risk_policy, day_pnl_pct=day_pnl_pct, drawdown_pct=drawdown_pct,
                       equity_basis=equity_basis)
    if risk.halt:
        ledger.record_run(run_id, release_id=release.release_id, asof=asof, mode=broker.mode,
                          state="blocked", portfolio_id=portfolio_id, env=env)
        log.emit("circuit_breaker.tripped", level="ERROR", component="engine", run_id=run_id,
                 portfolio_id=portfolio_id, data={"reason": risk.halt_reason})
        notifier.notify(Severity.CRITICAL, f"{portfolio_id}: risk halt", risk.halt_reason,
                        portfolio_id=portfolio_id)
        raise RebalanceBlocked(f"risk halt: {risk.halt_reason}")
    for v in risk.violations:
        log.emit("risk.violation", level="WARN", component="engine", run_id=run_id,
                 portfolio_id=portfolio_id, data={"detail": v})

    # ── parity-drift gate (DESIGN §7 matrix: "any order during parity drift → block") ──
    # Active drift means the live strategy may no longer match what was validated, so we
    # halt the whole rebalance (no new orders, incl. exits) and require human attention —
    # not just downgrade buys. Manual intervention / kill is the escape hatch.
    if ledger.parity_drift_active(portfolio_id, env=env):
        ledger.record_run(run_id, release_id=release.release_id, asof=asof, mode=broker.mode,
                          state="blocked", code_hash=manifest.code_hash, snapshot_hash=snap,
                          portfolio_id=portfolio_id, env=env)
        log.emit("parity.drift", level="ERROR", component="engine", run_id=run_id,
                 portfolio_id=portfolio_id, message="active parity drift — rebalance blocked")
        notifier.notify(Severity.CRITICAL, f"{portfolio_id}: parity drift — blocked",
                        "2+ consecutive parity breaches; investigate before trading",
                        portfolio_id=portfolio_id)
        raise RebalanceBlocked("parity drift active")

    # classify auto vs needs-approval; risk breaches downgrade the affected orders to approval
    held = set(broker_positions)
    anomalies = {o.ticker for o in orders
                 if o.client_order_id in risk.forced_approval or o.ticker in risk.forced_approval}
    decisions = classify(orders, equity=equity_basis, held=held, policy=policy, prices=prices,
                         anomalies=anomalies)
    classified = [_order_dict(d.order, d.auto, d.reason, d.order.client_order_id) for d in decisions]
    ledger.create_proposal(proposal_id, run_id=run_id, portfolio_id=portfolio_id,
                           orders=classified, env=env)
    for d in decisions:
        log.emit("policy.classified", component="engine", run_id=run_id, portfolio_id=portfolio_id,
                 data={"ticker": d.order.ticker, "side": d.order.side,
                       "auto": d.auto, "reason": d.reason})

    # park needs-approval orders; collect auto orders
    pending: list[dict] = []
    expires_at = (datetime.now(timezone.utc) +
                  timedelta(minutes=policy.approval_ttl_minutes)).isoformat()
    auto_orders: list[OrderRequest] = []
    for d in decisions:
        if d.auto:
            auto_orders.append(d.order)
        else:
            aid = f"appr_{uuid.uuid4().hex[:10]}"
            ledger.create_approval(aid, proposal_id=proposal_id,
                                   client_order_id=d.order.client_order_id,
                                   ticker=d.order.ticker, expires_at=expires_at, env=env)
            pending.append({"approval_id": aid, "ticker": d.order.ticker,
                            "coid": d.order.client_order_id})
            log.emit("approval.requested", level="WARN", component="engine", run_id=run_id,
                     portfolio_id=portfolio_id, data={"approval_id": aid, "ticker": d.order.ticker})

    # execute auto orders now (idempotent)
    rep = executor_mod.execute(auto_orders, broker=broker, portfolio_id=portfolio_id,
                               run_id=run_id, asof=asof, env=env, log=log)
    ledger.set_proposal_state(proposal_id, "executing" if pending else "complete", env=env)
    ledger.record_run(run_id, release_id=release.release_id, asof=asof, mode=broker.mode,
                      state="awaiting_approval" if pending else "complete",
                      code_hash=manifest.code_hash, snapshot_hash=snap,
                      portfolio_id=portfolio_id, env=env,
                      target_book=[asdict(e) for e in book.entries],
                      blocked=[asdict(b) for b in book.blocked])
    log.emit("run.end", component="engine", run_id=run_id, portfolio_id=portfolio_id,
             data={"auto": rep.__dict__, "pending": len(pending)})
    if pending:
        notifier.notify(Severity.ACTION_REQUIRED, f"{portfolio_id}: {len(pending)} orders need approval",
                        ", ".join(p["ticker"] for p in pending[:10]), portfolio_id=portfolio_id)

    return RebalanceResult(
        run_id=run_id, proposal_id=proposal_id, target=book.tickers,
        auto_executed=[o.ticker for o in auto_orders],
        pending_approval=pending, exec_report=rep.__dict__)


def execute_pending(proposal_id: str, broker: BrokerBase, *, asof: date,
                    portfolio_id: str, env: EnvConfig | None = None) -> dict:
    """Execute the APPROVED (non-expired) orders of a proposal. Idempotent.

    Expires stale approvals first, then submits only those marked 'approved'.
    """
    env = env or load_env_config()
    log = EventLogger(env)
    notifier = default_notifier()

    with ledger.connect(env) as conn:
        row = conn.execute(
            "SELECT orders, run_id, portfolio_id FROM order_proposals WHERE proposal_id=?",
            [proposal_id]).fetchone()
    if not row:
        return {"submitted": 0, "note": "proposal not found"}

    # ── isolation: the proposal MUST belong to the caller's portfolio ──
    # otherwise fills would be booked under the wrong portfolio/broker (DESIGN §2 #3).
    if row["portfolio_id"] != portfolio_id:
        raise RebalanceBlocked(
            f"proposal {proposal_id} belongs to {row['portfolio_id']!r}, not {portfolio_id!r}")

    # ── same pre-trade gates as a rebalance: mode, kill, account identity ──
    env.require_mode_allowed(broker.mode)
    if ledger.is_kill_switch_active(portfolio_id, env=env):
        raise RebalanceBlocked("kill switch active")
    _ensure_identity(portfolio_id, broker, env=env, log=log, notifier=notifier, run_id=row["run_id"])

    ledger.expire_stale_approvals(env=env)
    approved = ledger.approved_client_order_ids(proposal_id, env=env)
    if not approved:
        return {"submitted": 0, "note": "no approved orders"}

    run_id = row["run_id"]
    orders = [OrderRequest(ticker=o["ticker"], side=o["side"], qty=o["qty"], style=o["style"],
                           reason=o["reason"], client_order_id=o["coid"])
              for o in json.loads(row["orders"]) if o["coid"] in approved]

    rep = executor_mod.execute(orders, broker=broker, portfolio_id=portfolio_id,
                               run_id=run_id, asof=asof, env=env, log=log)
    ledger.set_proposal_state(proposal_id, "complete", env=env)
    out = rep.__dict__
    # Market orders (esp. fractional) often fill AFTER the submit response returns; poll
    # once now so fast fills are booked immediately. A standalone `sync` catches the rest.
    out["sync"] = sync_fills(portfolio_id, broker, env=env)
    # snapshot NAV + current prices so the detail chart/value columns get a point per trade
    try:
        out["refresh"] = refresh_market_state(portfolio_id, broker, source="execute", env=env)
    except Exception as exc:                          # never fail an execution on a snapshot
        log.emit("equity.snapshot_failed", level="WARN", component="engine",
                 portfolio_id=portfolio_id, error={"type": type(exc).__name__, "detail": str(exc)})
    return out


def compute_performance(current_equity, last_equity, base_value, daily_equity, spy_closes,
                        spy_now=None, spy_prior=None) -> dict:
    """Pure portfolio-vs-SPY return calc (percent), framed as LIVE-current vs references so
    it matches the broker app's "today". Inputs:
      current_equity : latest live account NAV
      last_equity    : prior trading-day close (broker's today-% basis)
      base_value     : portfolio cost basis (Alpaca base_value)
      daily_equity   : [(unix_ts, equity), ...] ascending COMPLETED daily NAV closes
      spy_closes     : [(date, close), ...] ascending COMPLETED daily SPY closes (excl. today)
      spy_now        : live SPY price (defaults to last completed close)
      spy_prior      : SPY prior completed close (defaults to spy_closes[-1])
    Today = current vs prior close (matches the broker app). 30d = current vs ~30 sessions
    back. Total = current vs inception (base_value / SPY inception close).
    """
    from datetime import datetime, timezone
    out = {"port_total_pct": None, "port_daily_pct": None, "port_30d_pct": None,
           "spy_total_pct": None, "spy_daily_pct": None, "spy_30d_pct": None}

    # ── portfolio: live equity vs references ──
    if base_value and current_equity is not None:
        out["port_total_pct"] = (current_equity / base_value - 1) * 100
    if last_equity and current_equity is not None:
        out["port_daily_pct"] = (current_equity / last_equity - 1) * 100   # == broker's today
    if current_equity is not None and daily_equity:
        anchor = daily_equity[-30][1] if len(daily_equity) >= 30 else daily_equity[0][1]
        if anchor:
            out["port_30d_pct"] = (current_equity / anchor - 1) * 100

    # ── SPY: same windows, live price vs references ──
    sn = spy_now if spy_now is not None else (spy_closes[-1][1] if spy_closes else None)
    if sn is not None and spy_closes:
        prior = spy_prior if spy_prior is not None else spy_closes[-1][1]
        if prior:
            out["spy_daily_pct"] = (sn / prior - 1) * 100
        anchor = spy_closes[-30][1] if len(spy_closes) >= 30 else spy_closes[0][1]
        if anchor:
            out["spy_30d_pct"] = (sn / anchor - 1) * 100
        incep_close = spy_closes[0][1]
        if daily_equity:                          # align SPY inception to the portfolio's
            incep = datetime.fromtimestamp(daily_equity[0][0], tz=timezone.utc).date()
            incep_close = next((c for d, c in spy_closes if d >= incep), incep_close)
        if incep_close:
            out["spy_total_pct"] = (sn / incep_close - 1) * 100
    return out


def _spy_daily_closes(start, end):
    """Ascending [(date, close)] for SPY over [start, end] via the marketdata loader."""
    import pandas as pd
    from trading.lab.data.market_data import fetch_daily_range
    spy = fetch_daily_range("SPY", start, end, force=False, adjustment="split")
    if spy is None or spy.empty:
        return []
    idx = pd.DatetimeIndex(spy.index).normalize()
    return [(idx[i].date(), float(spy["close"].iloc[i])) for i in range(len(spy))]


def _session_align_daily(daily_equity, spy_closes):
    """Remap Alpaca daily-NAV bar timestamps to their TRUE session date.

    Alpaca stamps each daily portfolio-history bar at 00:00 UTC of the day AFTER the session
    it closes (verified: the bar dated 6/24 holds 6/23's close == last_equity). Left as-is,
    every by-day row is labeled one day late. Remap each bar to the latest SPY trading day
    strictly before the bar's UTC date (SPY = the market calendar, handles holidays/weekends).
    """
    import bisect
    from datetime import datetime, timezone, time
    spy_dates = sorted(d for d, _ in spy_closes)
    out = []
    for ts, eq in daily_equity:
        bar_date = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        j = bisect.bisect_left(spy_dates, bar_date) - 1
        session = spy_dates[j] if (spy_dates and j >= 0) else bar_date
        sess_ts = int(datetime.combine(session, time(), tzinfo=timezone.utc).timestamp())
        out.append((sess_ts, eq))
    return out


def compute_daily_breakdown(daily_equity, spy_closes) -> list[dict]:
    """Per-trading-day portfolio vs SPY returns, newest first. Iterates the portfolio's
    own daily NAV series (which starts at inception), so it never shows days older than
    the portfolio. Each row is close-to-close over the same interval for both legs.
      [{date, port_pct, spy_pct, excess}]  (excess/spy null if SPY for that day is missing)
    """
    from datetime import datetime, timezone
    # SPY's own close-to-close daily return, keyed by date — computed over SPY's OWN
    # consecutive sessions so a market holiday (e.g. Juneteenth) or a gap in the portfolio
    # series never blanks the comparison. (The portfolio's first measured row may span a
    # gap; SPY still shows that session's real move, which is the useful number.)
    spy_ret = {}
    for i in range(1, len(spy_closes)):
        d, c = spy_closes[i]
        pc = spy_closes[i - 1][1]
        if pc:
            spy_ret[d] = (c / pc - 1) * 100
    rows = []
    for i in range(1, len(daily_equity)):
        eq_prev = daily_equity[i - 1][1]
        ts_cur, eq_cur = daily_equity[i]
        if not eq_prev:
            continue
        d_cur = datetime.fromtimestamp(ts_cur, tz=timezone.utc).date()
        port = (eq_cur / eq_prev - 1) * 100
        spy = spy_ret.get(d_cur)
        rows.append({"date": d_cur.isoformat(), "port_pct": port, "spy_pct": spy,
                     "excess": (port - spy) if spy is not None else None})
    rows.reverse()                                  # newest first
    return rows


def backfill_performance_from_snapshots(portfolio_id: str, env: EnvConfig | None = None) -> dict:
    """Rebuild the portfolio daily performance series from equity_snapshots (single source).

    Reads ALL equity_snapshots for the portfolio, buckets them by trading day, takes the
    last snapshot per day as that day's NAV, then computes close-to-close daily returns
    alongside SPY close-to-close returns from the cached marketdata. Writes a single new
    ``performance_snapshots`` row with the complete ``daily_json``.

    This is the "backfill" that fixes missing days in the By-trading-day table without
    mixing broker-pull data (get_portfolio_perf) with cached data — it uses equity_snapshots
    exclusively for the portfolio leg, which is the same Alpaca broker source, just at
    whatever timestamps refreshes happened. The SPY leg uses the marketdata daily bar cache.

    Returns a dict with ``rows_written``, ``n_days``, ``first_day``, ``last_day``.
    """
    from datetime import time as _time
    env = env or load_env_config()
    ledger.init_db(env)

    # 1. Read all equity snapshots, sort by ts
    series = ledger.equity_series(portfolio_id, limit=10000, env=env)
    if not series:
        return {"error": "no equity snapshots for this portfolio"}

    # 2. Bucket by UTC date — take the LAST equity value per day
    daily_equity: dict[str, float] = {}
    for r in series:
        day = r["ts"][:10]
        daily_equity[day] = r["equity"]  # last wins (series is oldest→newest)

    daily_list = sorted(daily_equity.items())  # [(iso_date, equity), ...]

    # Read portfolio config for capital (used for base_value + pre-funding trim)
    from trading.live import portfolios as _portfolios
    p_cfg = _portfolios.get(portfolio_id, env=env)
    capital = getattr(p_cfg, "capital", 0)

    first_day = daily_list[0][0]
    last_day = daily_list[-1][0]

    # 3. Trim pre-funding days — if the NAV is unrealistically low compared to the
    #    portfolio's capital, those are snapshots taken before fills settled.
    capital = getattr(p_cfg, "capital", 0)
    if capital > 0:
        daily_list = [(d, e) for d, e in daily_list if e >= capital * 0.5]
        if len(daily_list) < 2:
            return {"error": "too few valid post-funding equity snapshots"}
        first_day = daily_list[0][0]
        last_day = daily_list[-1][0]

    # 4. Convert to [(unix_ts, equity)] for compute_daily_breakdown
    #    Use 20:00 UTC (4pm ET / market close) as the canonical day-stamp
    from datetime import timezone as _tz
    close_hour_utc = 20  # 4pm ET in summer = 20:00 UTC
    daily_equity_ts = []
    for iso_d, eq in daily_list:
        y, m, d_ = int(iso_d[:4]), int(iso_d[5:7]), int(iso_d[8:10])
        dt = datetime(y, m, d_, close_hour_utc, 0, 0, tzinfo=_tz.utc)
        daily_equity_ts.append((int(dt.timestamp()), eq))

    # 4. Get SPY daily closes from marketdata cache
    spy_start = datetime.fromisoformat(first_day).date()
    spy_end = datetime.fromisoformat(last_day).date()
    spy_closes = _spy_daily_closes(spy_start, spy_end)

    # 5. Compute daily breakdown (reuses existing function, returns newest-first)
    breakdown = compute_daily_breakdown(daily_equity_ts, spy_closes)

    # 6. Use the portfolio's configured capital as base_value (the first equity snapshot
    #    may be from before fills were booked, giving a distorted total return)
    base_value = capital or daily_list[0][1]

    nav_last = daily_list[-1][1]
    port_total_pct = (nav_last / base_value - 1) * 100 if base_value else None
    pot_daily_pct = breakdown[0]["port_pct"] if breakdown else None

    spy_first = spy_closes[0][1] if spy_closes else None
    spy_last = spy_closes[-1][1] if spy_closes else None
    spy_total_pct = (spy_last / spy_first - 1) * 100 if (spy_first and spy_last) else None

    # 5d / 30d — approximate from available days
    port_30d_pct = None
    spy_30d_pct = None
    if len(daily_list) >= 2:
        d30 = min(len(daily_list) - 1, 21)  # ~30 trading days
        nav_30d_back = daily_list[-1 - d30][1]
        if nav_30d_back:
            port_30d_pct = (nav_last / nav_30d_back - 1) * 100
            # SPY 30d: match to calendar day
            date_30d_back = daily_list[-1 - d30][0]
            spy_match = [(d, c) for d, c in spy_closes if d.isoformat() == date_30d_back]
            if spy_match:
                spy_30d_pct = (spy_last / spy_match[0][1] - 1) * 100 if spy_match[0][1] else None

    # 7. Persist — same shape as the existing performance snapshot
    ledger.record_performance(
        portfolio_id,
        base_value=base_value,
        port_total_pct=port_total_pct,
        port_daily_pct=pot_daily_pct,
        port_30d_pct=port_30d_pct,
        spy_total_pct=spy_total_pct,
        spy_daily_pct=spy_30d_pct,  # approximate; web shows N/A for today if no live-pull
        spy_30d_pct=spy_30d_pct,
        daily_json=json.dumps(breakdown),
        env=env,
    )
    ledger.audit("performance.backfill", actor="system",
                 detail=f"{portfolio_id} {len(breakdown)} days {first_day}→{last_day}", env=env)

    return {
        "ok": True,
        "portfolio_id": portfolio_id,
        "n_days": len(breakdown),
        "first_day": first_day,
        "last_day": last_day,
        "port_total_pct": port_total_pct,
    }


def prepend_live_today(breakdown, *, equity, last_equity, spy_now, spy_prior, date_iso):
    """Prepend the in-progress current session to the completed-day breakdown so the table's
    newest row matches the summary "Today" (equity/last_equity). Skips when flat (weekend /
    no movement) or when today is already a completed row. Tagged live=True for the UI."""
    if not (equity and last_equity) or abs(equity - last_equity) <= 1e-9:
        return breakdown
    if breakdown and breakdown[0].get("date") == date_iso:
        return breakdown
    port = (equity / last_equity - 1) * 100
    spy = (spy_now / spy_prior - 1) * 100 if (spy_now and spy_prior) else None
    row = {"date": date_iso, "port_pct": port, "spy_pct": spy,
           "excess": (port - spy) if spy is not None else None, "live": True}
    return [row] + list(breakdown)


def refresh_market_state(portfolio_id: str, broker: BrokerBase, *, source: str = "manual",
                         env: EnvConfig | None = None) -> dict:
    """Pull current prices + account NAV from the broker and persist them for the UI.

    Two writes: (1) stamp each held position with its current market price (current-value
    column), (2) append an equity snapshot (the detail-page chart). Read-only against the
    broker. Returns a summary. Assumes one broker account per portfolio (identity #3), so
    account.equity IS this portfolio's NAV.
    """
    env = env or load_env_config()
    ledger.init_db(env)                                # ensure schema/migrations are applied
    log = EventLogger(env)
    bpos = broker.get_positions()
    prices = {t: p.current_price for t, p in bpos.items() if p.current_price}
    n = ledger.update_position_prices(portfolio_id, prices, env=env)
    acct = broker.get_account()
    pos_val = sum(p.qty * p.current_price for p in bpos.values() if p.current_price)
    ledger.record_equity_snapshot(portfolio_id, equity=acct.equity, cash=acct.cash,
                                  positions_value=pos_val, source=source, env=env)

    # backfill the hourly NAV curve from the broker (authoritative; idempotent on ts).
    # One click reconstructs the whole chart at hourly resolution — no cron needed.
    from datetime import datetime, timezone
    hist_n = 0
    try:
        # 1H resolution; Alpaca caps hourly history at a 30-day window
        for ts, eq in broker.get_equity_history(period="30D", timeframe="1H"):
            iso = datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
            ledger.record_equity_snapshot(portfolio_id, equity=eq, source="history",
                                          ts=iso, env=env)
            hist_n += 1
    except Exception as exc:                           # history is best-effort enrichment
        log.emit("equity.history_failed", level="WARN", component="engine",
                 portfolio_id=portfolio_id, error={"type": type(exc).__name__, "detail": str(exc)})

    # portfolio-vs-SPY performance (daily close-to-close + total since inception)
    perf = None
    try:
        from datetime import timedelta
        pp = broker.get_portfolio_perf(period="3M")   # ≥30 trading sessions for the 30-day col
        daily_eq = pp.get("daily") or []
        if daily_eq:
            incep = datetime.fromtimestamp(daily_eq[0][0], tz=timezone.utc).date()
        else:
            incep = (datetime.now(timezone.utc) - timedelta(days=30)).date()
        # fetch SPY back to whichever is earlier: inception, or ~50 calendar days (≥30
        # trading sessions) so the 30-day column is valid even for a young portfolio
        now_d = datetime.now(timezone.utc).date()
        spy_start = min(incep - timedelta(days=7), now_d - timedelta(days=50))
        spy_all = _spy_daily_closes(spy_start, now_d)
        # completed SPY sessions = exclude today's partial bar; live price = latest trade
        spy_completed = [(d, c) for d, c in spy_all if d < now_d]
        spy_now = broker.get_latest_price("SPY")
        spy_prior = spy_completed[-1][1] if spy_completed else None
        # Alpaca daily bars are labeled one day late — remap to true session dates first
        daily_eq = _session_align_daily(daily_eq, spy_all)
        perf = compute_performance(acct.equity, getattr(acct, "last_equity", 0.0) or None,
                                   pp.get("base_value"), daily_eq, spy_completed,
                                   spy_now=spy_now, spy_prior=spy_prior)
        breakdown = compute_daily_breakdown(daily_eq, spy_all)
        breakdown = prepend_live_today(
            breakdown, equity=acct.equity, last_equity=getattr(acct, "last_equity", 0.0) or None,
            spy_now=spy_now, spy_prior=spy_prior, date_iso=now_d.isoformat())
        ledger.record_performance(portfolio_id, base_value=pp.get("base_value"),
                                  daily_json=json.dumps(breakdown), env=env, **perf)
    except Exception as exc:                           # performance is best-effort enrichment
        log.emit("performance.failed", level="WARN", component="engine",
                 portfolio_id=portfolio_id, error={"type": type(exc).__name__, "detail": str(exc)})

    log.emit("equity.snapshot", component="engine", portfolio_id=portfolio_id,
             data={"equity": acct.equity, "positions_value": pos_val,
                   "prices_updated": n, "history_points": hist_n, "source": source})
    return {"prices_updated": n, "equity": acct.equity, "cash": acct.cash,
            "positions_value": pos_val, "positions": len(bpos), "history_points": hist_n,
            "performance": perf}


def sync_fills(portfolio_id: str, broker: BrokerBase, *, env: EnvConfig | None = None) -> dict:
    """Poll non-terminal order intents against the broker and book any NEW fills.

    P1 stand-in for the trade-updates stream (DESIGN §9): the broker is polled with the
    deterministic client_order_id, and only the DELTA between the broker's cumulative
    filled_qty and what the ledger already booked is recorded — so repeated syncs are
    idempotent and partial→full fills are handled. The positions ledger (hold-day
    authority) updates via record_fill; entry_date is set on the first booked fill.
    """
    env = env or load_env_config()
    log = EventLogger(env)
    rep = {"checked": 0, "new_fills": 0, "filled": 0, "rejected": 0, "still_open": 0}
    for it in ledger.open_intents(portfolio_id, env=env):
        coid = it["client_order_id"]
        bo = broker.get_order(coid)
        if bo is None:
            continue
        rep["checked"] += 1
        booked = ledger.filled_qty_recorded(coid, env=env)
        delta = float(bo.filled_qty or 0.0) - booked
        if delta > 1e-9 and bo.filled_avg_price:
            ledger.record_fill(coid, portfolio_id=portfolio_id, ticker=it["ticker"],
                               side=it["side"], qty=delta, price=bo.filled_avg_price, env=env)
            rep["new_fills"] += 1
            log.emit("order.fill_synced", component="engine", portfolio_id=portfolio_id,
                     data={"ticker": it["ticker"], "coid": coid, "delta_qty": delta,
                           "price": bo.filled_avg_price, "status": bo.status})
        ledger.update_intent(coid, status=bo.status, broker_order_id=bo.broker_order_id,
                             filled_qty=bo.filled_qty, filled_avg_price=bo.filled_avg_price, env=env)
        if bo.status == "filled":
            rep["filled"] += 1
        elif bo.status == "rejected":
            rep["rejected"] += 1
        else:
            rep["still_open"] += 1
    return rep


def parity_check(portfolio_id: str, release, *, context, asof: date,
                 env: EnvConfig | None = None, bands=None) -> dict:
    """Replay parity for the latest run of a portfolio + record it (DESIGN §12).

    Recomputes the target book on the given context, compares to the recorded book
    (signal match), measures fill slippage vs recorded closes, flags drift, persists.
    """
    from trading.live.parity import DriftBands, evaluate
    env = env or load_env_config()
    log = EventLogger(env)
    last = ledger.latest_run(env=env, portfolio_id=portfolio_id)
    if not last:
        return {"note": "no run to check"}
    recorded = [e["ticker"] for e in json.loads(last["target_book"] or "[]")]
    expected_px = {e["ticker"]: e.get("close") for e in json.loads(last["target_book"] or "[]")}

    denylist = merge(load_platform_denylist(), ledger.active_denylist(portfolio_id, asof, env=env))
    book = build_target_book(release, context, denylist, asof=asof)
    recomputed = book.tickers

    with ledger.connect(env) as conn:
        fills = [dict(r) for r in conn.execute(
            "SELECT ticker, side, qty, price FROM fills WHERE portfolio_id=?", [portfolio_id])]

    res = evaluate(recorded, recomputed, fills, expected_px, bands or DriftBands())
    ledger.record_parity(last["run_id"], portfolio_id,
                         signal_match_pct=res.signal_match_pct, slippage_bps=res.slippage_bps,
                         drift=res.drift, detail=res.detail, env=env)
    log.emit("parity.replay", level="WARN" if res.drift else "INFO", component="parity",
             portfolio_id=portfolio_id,
             data={"signal_match_pct": res.signal_match_pct, "slippage_bps": res.slippage_bps,
                   "drift": res.drift})
    return {"signal_match_pct": res.signal_match_pct, "slippage_bps": res.slippage_bps,
            "drift": res.drift, "drift_active": ledger.parity_drift_active(portfolio_id, env=env)}
