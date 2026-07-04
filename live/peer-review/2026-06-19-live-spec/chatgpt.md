## Overall verdict

This is a **good spec**. The core architecture is sane: independent portfolios, paper-first promotion, strict lab/live parity, per-portfolio broker isolation, kill switches, approval workflow, structured logs, and separate `dev` / `testing` / `prod` environments. The strongest part is the “never re-implement strategy logic” rule: live trades must come from the exact validated `Release.build_candidates` path and same marketdata loader. That is the right north star. 

The biggest improvement is this: **turn the spec from a workflow description into an executable operations contract.** Right now it explains what should happen, but several high-risk states are still implicit: partial fills, stale approvals, broker mismatch recovery, order timing, release immutability, schema migrations, and disaster recovery.

---

## Highest-priority improvements

### 1. Define the exact trading clock

This is the most important gap.

The spec says the engine runs “after the close settles,” but also compares realized fills to modeled close fills. That can become a serious parity trap. If your backtest assumes close fills, but the live system generates orders after the close, you cannot actually get that same close fill.

Add a dedicated section:

```md
## Execution clock

For each release, define:

- signal_date
- data_asof timestamp
- decision timestamp
- order submission window
- expected fill model
- live order type
- backtest fill assumption

Example:
- Signals are computed using data through close of D.
- Orders are generated after data validation on D.
- Orders are submitted as MOO/market/limit orders on D+1.
- Backtest must model D+1 open/close accordingly.
```

Do not leave this fuzzy. A tiny mismatch here can invalidate the whole parity claim.

---

### 2. Add explicit state machines

You should not implement this with booleans scattered across tables. Define state machines up front.

Add these:

**Portfolio state**

```text
draft → paper_active → paper_paused → live_pending → live_active → live_paused → retiring → retired
                         │                                  │
                         └──────── kill_tripped ◄───────────┘
```

**Rebalance run state**

```text
scheduled
→ context_building
→ candidates_built
→ proposal_created
→ awaiting_approval
→ executing_sells
→ executing_buys
→ reconciling
→ complete

failure states:
failed / expired / cancelled / superseded / blocked
```

**Order state**

```text
intent_recorded
→ submitted
→ accepted
→ partially_filled
→ filled

terminal alternatives:
rejected / cancelled / expired / unknown_broker_state
```

This matters because your current spec correctly says approvals can expire and runs should be idempotent, but it does not yet define exactly what happens if a user approves while the run expires, the broker partially fills, or the app restarts mid-submit. 

---

### 3. Strengthen idempotency beyond `(portfolio, date)`

The spec says a rebalance is keyed by `(portfolio, date)`. That is good but not enough. Use something closer to:

```text
portfolio_id
+ scheduled_rebalance_id
+ release_id
+ release_version_hash
+ marketdata_snapshot_id
+ run_attempt
```

Why: the same calendar date can be re-run with different marketdata, a patched release, a changed schedule, or a partial previous attempt. You want retries to be safe, but you also want changed inputs to be visible, not silently treated as the same run.

Add:

```md
Every rebalance run stores:
- release_id
- release git SHA / package version
- strategy params checksum
- marketdata snapshot hash
- universe snapshot hash
- calendar used
- broker account identity hash
```

---

### 4. Make releases immutable

`release_id = x03` is not enough. You need to guarantee that the code behind `x03` did not change.

Add a release manifest:

```json
{
  "release_id": "x03",
  "release_version": "x03.2026-06-18",
  "git_sha": "...",
  "strategy_class": "...",
  "params_hash": "...",
  "marketdata_schema_version": "...",
  "validation_report_hash": "...",
  "promoted_at": "...",
  "promoted_by": "..."
}
```

Then the live system should refuse to run if the imported release code does not match the manifest. Your current parity rule is correct, but it needs this enforcement layer. 

---

### 5. Separate “capital target” from broker truth

The spec says each portfolio has capital, balances, and dedicated broker accounts. That is right, but it should clarify what is authoritative. Broker equity/cash should be the source of truth for executable sizing; configured capital should be a risk target or cap.

Add:

```md
Capital model:
- broker_cash, broker_equity, buying_power: read-only from broker
- configured_capital_limit: max capital this portfolio may deploy
- cash_reserve_pct: cash buffer to avoid rejected buys
- target_gross_exposure_pct
- margin_allowed: false by default
- shorting_allowed: false
```

Also add rules for deposits/withdrawals. Otherwise, manual transfers can create confusing “drift” that looks like strategy P&L.

---

### 6. Be stricter about approval policy

The hybrid approval policy is a good idea, but it mixes different risk types. Sells, reductions, buys, increases, and brand-new names should not be treated the same.

Replace the current policy with a matrix:

| Order type                                  | Default                              |
| ------------------------------------------- | ------------------------------------ |
| Sell to reduce risk / exit matured position | Auto, unless anomaly                 |
| Buy brand-new position                      | Approval required at first           |
| Increase existing position                  | Auto only within tight notional band |
| Sell due to reconciliation repair           | Approval required                    |
| Flatten due to kill switch                  | Separate emergency action            |
| Any order during parity drift               | Block                                |
| Any order during broker/ledger mismatch     | Block                                |

Your current policy says routine orders may auto-execute while new names, oversized orders, anomalies, reconciliation mismatches, kill switch, broker errors, and drawdown breakers block or require approval. That is directionally right; the next version should distinguish “risk-reducing” from “risk-increasing” actions. 

---

### 7. Define kill switch semantics precisely

Right now “kill switch stops trading” is not enough.

Add three levels:

```md
Pause:
- no new proposals
- no new orders
- existing open orders unchanged unless manually cancelled

Kill:
- no new proposals
- no new orders
- cancel all open orders for that portfolio
- keep reconciliation and monitoring running

Flatten:
- cancel open orders
- submit liquidation orders
- requires live re-auth + confirmation
- logs emergency action
```

Global kill should probably mean: **cancel open orders and block new orders across all portfolios**, but not automatically flatten unless you explicitly choose the stronger action.

---

### 8. Add reconciliation tolerance and repair workflow

The spec correctly blocks trading when broker and ledger disagree. Good. But now define the details.

Add:

```md
Reconciliation compares:
- symbol
- quantity
- side
- average entry price
- market value
- cash
- buying power
- open orders
- pending fills
- corporate actions

Allowed tolerances:
- share qty tolerance
- cash tolerance
- price tolerance
- fractional share rounding tolerance

Mismatch workflow:
1. classify mismatch
2. block trading
3. show broker state vs ledger state
4. allow manual resolution action
5. write audit event
6. require fresh reconcile.ok before next order
```

Also decide who owns hold timers. I would make **fills the authority** for hold timers, not the broker position snapshot.

---

### 9. Add order execution details

This needs its own section. Include:

```md
Order execution policy:
- order type: market / limit / MOO / MOC / LOC
- time-in-force
- fractional vs whole shares
- min notional
- cash buffer
- sell-before-buy sequencing
- handling partial fills
- handling unfilled orders
- retry rules
- broker outage behavior
- max slippage guard
- max spread guard
- halt / non-tradable symbol behavior
```

Especially important: never blindly retry submit calls unless idempotency with the broker is solid. A network timeout after submission can produce an “unknown” state. That state must block further action until reconciled.

---

### 10. Improve marketdata parity

“Same loader” is necessary but not sufficient. Live and lab can still diverge if the provider revises data, corporate actions are adjusted differently, or the live cache is warmed differently.

Add a `marketdata_snapshot` concept:

```md
Each run stores:
- provider
- data_asof
- calendar version
- universe membership
- adjustment policy
- row counts
- missing symbols
- stale symbols
- input hash
```

Your deployment section says prod/testing will warm their own live-scoped marketdata cache rather than ship the heavy research cache. That is reasonable, but it increases the need for per-run input snapshots and hashes. 

---

## Architecture recommendations

### DB choice

For P0/P1, SQLite is fine **only if** all writes go through one process or one API service with WAL mode and careful locking.

For live prod, I would lean toward **Postgres**, because you have:

* web app writes,
* scheduler/engine writes,
* approval writes,
* audit log writes,
* alerts,
* possible future notification workers.

DuckDB should not be the live ledger. It is great for analytics/research, not transactional live state.

Recommended spec decision:

```md
P0/P1: SQLite via repository abstraction.
Before live: Postgres unless single-writer architecture remains intentionally enforced.
Never use DuckDB as the live transactional ledger.
```

### Scheduler choice

Use **daily cron/invocation for P0/P1**, not a long-running scheduler. It is easier to reason about, easier to make idempotent, and easier to recover.

Later, add a long-running service only if you need intraday actions, websockets, or frequent health checks.

### UI stack

For v1, I would choose **FastAPI + HTMX/Jinja**, not React, unless you already want to invest in frontend complexity.

Reason: this is an internal control plane, not a consumer app. Your risk is backend correctness, not frontend sophistication. HTMX can give you approvals, live-ish refresh, tables, and forms with much less surface area.

A good compromise:

```md
P0/P1: FastAPI + Jinja/HTMX
P3+: React only if the UI becomes interaction-heavy
```

### Remote access

Prefer **Tailscale** for your personal trading-control surface. Cloudflare Access is also valid, but Tailscale is simpler for “only I need to access this from laptop/phone.” Your current spec’s instinct to avoid exposing a public port is exactly right. 

---

## Deployment and operations gaps

Add these before P0/P1 hardens:

### 1. Schema migrations

Add:

```md
All DB schema changes use versioned migrations.
App startup checks expected schema version.
Prod deploy refuses to start on unknown or failed migration state.
```

### 2. Backups and restore drills

You need backups for:

* live DB,
* audit log,
* JSONL logs,
* config,
* release manifests.

Add a restore test:

```md
Monthly restore drill:
- restore latest backup into isolated environment
- verify portfolios, positions, approvals, run history
- reconcile restored state against broker read-only snapshot
```

### 3. Disk, clock, and process health

Add alerts for:

* disk > 80%,
* log write failure,
* DB write failure,
* system clock drift,
* marketdata freshness failure,
* broker auth failure,
* scheduler missed run,
* container restart loop.

Clock drift matters more than it seems in trading systems.

### 4. Secrets safety

Your spec already says real broker keys only exist in prod, not repo or laptop. Good. 

Add these checks:

```md
On startup, each portfolio verifies:
- broker endpoint matches mode
- broker account identity matches configured portfolio account hash
- live keys are unavailable outside prod
- paper keys are unavailable in live portfolio configs
```

This protects you from accidentally pointing portfolio A at portfolio B’s account.

---

## Logging improvements

The JSONL daily log design is good. Keep it. The daily `summary.json` is also a good idea because it gives your external agent a clean entry point. 

Add these fields to every event:

```json
{
  "schema_version": "1.0",
  "event_id": "...",
  "ts": "...",
  "level": "INFO",
  "event": "order.submitted",
  "component": "engine",
  "portfolio_id": "...",
  "run_id": "...",
  "correlation_id": "...",
  "causation_id": "...",
  "actor_type": "system|user",
  "actor_id": "...",
  "attempt": 1,
  "data": {}
}
```

Also add a rule:

```md
The DB is the state source of truth.
JSONL is the event/audit/analysis stream.
Critical events are emitted from committed DB state where possible.
```

That prevents log/state divergence.

---

## Add notification channels

The current workflow assumes you open the web UI daily. That is fine for monitoring, but bad for incidents.

Add:

```md
Notification channels:
- email for warning/approval
- SMS/push for live kill/broker/reconciliation failures
- optional Discord/Slack webhook for paper/testing
```

Severity model:

```text
INFO: no user action
WARN: user should review
ACTION_REQUIRED: approval/reconciliation needed
CRITICAL: live trading blocked, kill switch, broker unknown state
```

---

## Recommended additions to the phase plan

Your current phase plan is good, but I’d tighten it with acceptance criteria. 

### P0 acceptance criteria

```md
- Can load promoted release manifest.
- Can build target book from live marketdata.
- Records release hash and marketdata snapshot hash.
- Shows target book in UI.
- No broker credentials accepted yet.
- Kill switch state exists and is testable.
```

### P1 acceptance criteria

```md
- Fake broker passes full order lifecycle tests.
- Alpaca paper broker passes submit/fill/reconcile tests.
- Partial fill and rejected order are simulated.
- Approval expiry works.
- Re-running same rebalance cannot double-submit.
- Ledger survives process restart.
```

### P2 acceptance criteria

```md
- Lab/live signal parity check implemented.
- Slippage attribution implemented.
- Drift bands configurable.
- Any parity drift blocks new risk-increasing orders.
```

### P3 acceptance criteria

```md
- Multiple portfolios run simultaneously.
- Account identity verification prevents key/account mixups.
- Global kill cancels open orders and blocks new ones.
- Remote access is private-network protected.
- Audit log includes actor and action.
```

### P4 acceptance criteria

```md
- Live starts with tiny capital.
- Margin disabled.
- Max order notional enforced.
- Max daily loss / drawdown breaker enforced.
- Restore drill completed before scale-up.
```

---

## Open questions I would resolve now

My recommended answers:

| Question          | Recommendation                                                      |
| ----------------- | ------------------------------------------------------------------- |
| Web stack         | FastAPI + HTMX/Jinja for P0/P1; React only later                    |
| Remote auth       | Tailscale first                                                     |
| Broker            | Alpaca only for v1, but keep `BrokerAdapter` interface clean        |
| Approval defaults | Start with approve-all buys; auto-allow normal exits unless anomaly |
| Scheduler         | Daily cron/invocation first                                         |
| Live DB           | SQLite only for P0/P1 single-writer; Postgres before serious live   |
| Secrets           | Prod-only secret store; startup account identity verification       |
| Logging           | Keep JSONL + daily summary; add event IDs/schema version            |
| Marketdata cache  | Warm live cache, but hash every run’s input snapshot                |
| Deployment        | Add migrations, backups, restore drills, health alerts              |

---

## The one spec change I would make immediately

Add this near the top, right after the parity rule:

```md
## Non-negotiable live invariants

A portfolio may submit an order only if all are true:

1. TRADING_ENV/mode combination is allowed.
2. Portfolio is active and not kill-tripped.
3. Broker account identity matches the portfolio config.
4. Release manifest hash matches the promoted lab artifact.
5. Marketdata snapshot is fresh and recorded.
6. Signal parity check passes.
7. Broker positions reconcile with live ledger.
8. Approval policy permits the order or valid approval exists.
9. Idempotency key has not already submitted this order intent.
10. Order clock is inside the release-defined execution window.
```

That turns the document from “good design” into a safer implementation contract.
