This is a strong spec — you’ve already made the hard calls right: one strategy = one broker account, parity as a non-negotiable, paper-first per portfolio, and a control plane that’s separate from the lab. The shape will work.

Here are the improvements I’d make before you lock P0, mostly to close reliability and security gaps that bite later when you have 3+ portfolios live.

## What’s already solid
- **Isolation by account** not by code flag. That’s the only way to survive a bug.
- **Hybrid approval** per portfolio with a default-deny start. Good learning curve.
- **JSONL event log** as the source of truth for your external agent — that makes the system debuggable without you babysitting it.
- **Two-axis env vs mode** — dev/testing/prod separate from paper/live. That prevents the classic "oops I pointed prod at paper keys".

## Critical gaps to fix

### 1. Parity needs to be provable, not just stated
You say "exact Release.build_candidates" but the spec doesn't lock the code. Add three fields to every portfolio record:
- `release_id` (e.g. x03)
- `release_git_sha`
- `release_image_digest`

The engine refuses to run if the loaded module's hash doesn't match. Store the same triple in every `run.start` event. Without this, a redeploy of trading.lab can silently change live behavior and void your backtest.

Also add a daily `parity.replay` job: take yesterday's marketdata snapshot, re-run build_candidates in a clean container, diff vs what was actually proposed. Log mismatch as `parity.drift`. This catches data-loader drift, not just code drift.

### 2. Approval policy needs more real-world knobs
Your current auto vs approval is size + new-name. Add:
- **liquidity gate**: auto only if 20-day ADV > 5x order notional
- **volatility gate**: if VIX > 30 or stock gap > 8% vs close, force approval
- **turnover gate**: auto_max_pct of portfolio *and* auto_max_daily_turnover (e.g. 15%)
- **time decay**: pending approvals expire in 90 minutes after market open, not "configurable" — stale fills kill edge

Make policy a small DSL in the DB, not hardcoded, so you can tune per portfolio without a deploy.

### 3. Kill switch must be two-stage and broker-enforced
Right now it's a flag. Add:
- **Soft kill**: scheduler stops creating proposals (your current)
- **Hard kill**: API calls `cancel_all_orders` + optional `close_all_positions` per broker account, with a second confirmation in UI
- Store kill state in both DB *and* a file on disk that engine checks before submit — survives DB outage

Drill this monthly, not just at onboarding.

### 4. Reconciliation is under-specified
You check ledger vs broker. Also check:
- **Corporate actions**: nightly job compares broker positions vs marketdata splits/dividends. Mismatch → `reconcile.corp_action_mismatch` and block trading
- **Cash**: broker cash vs ledger cash after every fill, tolerance $0.01
- **Hold timers**: derive from first fill timestamp, not from proposal date

Log reconciliation as a first-class event with `expected` and `actual` in the `data` field — your agent needs that to diagnose.

### 5. Live DB: don't start with SQLite
With scheduler + web + engine writing concurrently, you'll hit locking on day 2 of multi-portfolio. Start P1 with Postgres (even a single-container). It gives you row-level locks, proper audit_log append-only table, and easy point-in-time restore. DuckDB is great for lab, wrong for live OLTP.

## Recommended changes by section

**§4.1 Onboarding**
- When you promote to live, auto-create a shadow paper portfolio that mirrors the live config. Keep it running forever — that's your continuous parity feed without extra work.
- Require a checklist in UI before live flip: paper cycle complete, parity < 5bps slippage, kill drill logged, capital confirmed.

**§6 Parity panel**
- Show three numbers, not just a curve: signal match %, fill slippage bps vs backtest, and tracking error (annualized). Alert if any breaches for 2 consecutive rebalances.

**§8 Logging**
- Add `schema_version: "1.0"`, `event_id` (ulid), `trace_id` to every event. Makes replay trivial.
- Keep `events.jsonl` for 90 days hot, gzip to cold storage for 2 years. Add a `metrics.prom` sidecar that exposes counters for Prometheus — your phone dashboard shouldn't tail JSONL.
- Redact more aggressively: strip full order IDs, account numbers, symbols are fine.

**§10 Architecture**
- Split `engine.py` into `planner` (pure, no I/O) and `executor` (broker calls). Lets you unit-test the planner against logged events.
- Add `secrets.py` abstraction now — don't read env directly in broker.py. You'll thank yourself when moving to a vault.

**§11 Environments**
- Good choice on Docker Compose. Add one more rule: prod compose file has `restart: unless-stopped` and mounts secrets read-only. Testing and prod must use different Docker networks — prevents accidental cross-talk.

## Answers to your open questions in §15

- **Web stack**: FastAPI + React. You need live WebSocket tiles and approval buttons that feel instant — HTMX will fight you by P2. Use FastAPI for backend, React with TanStack Query for state.
- **Remote auth**: Tailscale, not Cloudflare Access. Trading control plane should have zero public ingress. Tailscale gives you phone access, device posture, and you can kill a device instantly. Put Caddy in front for TLS inside the tailnet.
- **Broker**: Start with Alpaca Broker API sub-accounts, not separate logins. One master key, each portfolio is a sub-account with isolated buying power. Much cleaner secret management and you can programmatically fund/close.
- **Approval defaults**: Start `auto_max_pct=0`, `auto_max_names=0`, expiry 90 min. After 2 clean cycles, move to 3% / 2 names.
- **Scheduler**: Long-running service with APScheduler, not cron. You need in-memory idempotency keys and graceful shutdown during a rebalance.
- **Live DB**: Postgres 16, one schema per env.
- **Secrets**: Use Doppler or 1Password Connect from P1. Per-portfolio secrets as `ALPACA_LIVE_<portfolio_id>`. Never .env files on the host.
- **Logging retention**: JSONL daily, gzip after 7 days, delete after 730 days. Keep summary.json forever.
- **Host**: One Hetzner/DO box for testing+prod is fine if you use separate Docker projects and volumes. Warm marketdata cache by replaying last 500 trading days on first boot — don't seed from dev.

## Two small workflow tweaks
1. Daily workflow: add a 30-second "dry-run parity check" button on Overview that runs today's ranking without broker — lets you spot data issues before the close.
2. Weekly: add a "capital drift" alert when actual broker cash deviates >2% from target capital in config — catches dividends or manual transfers you forgot.

If you lock the parity hash, switch to Postgres early, and make kill switch broker-enforced, the rest of the spec will scale cleanly to 5-10 portfolios. Want me to turn this into a revised DESIGN.md with the schema changes and a concrete `policy` table definition?