# trading.live — running multiple strategies as live portfolios

Status: **DESIGN** (scaffolding in this package is a starting point; the multi-portfolio +
web-UI shape below supersedes the single-release scaffolding and will be built out in phases).
Paper-first: nothing executes real orders until you deliberately enable it per portfolio.

This document is written from **your** point of view — what you set up once, what you do daily,
weekly, and per-rebalance to run and monitor several strategies at the same time. The workflow is
up front; the engineering contracts (clock, gates, integrity, ops) sit in the middle; deployment
and phases at the back.

> **Peer review applied (2026-06-19).** Sections §2, §6–§11, §15, §19–§21 incorporate the
> high/medium-priority findings from the four spec reviews in `peer-review/2026-06-19-live-spec/`
> (execution clock, release pinning, idempotency, order/fill handling, three-level kill,
> reconciliation, corporate actions, tradability denylist, risk policy, calendar/DST,
> notifications, migrations/backups). One review finding is **unresolved and gates the isolation
> model**: whether a retail Alpaca identity may hold more than one *live* account (§18, §23).

---

## 1. The idea, in one picture

You run several **portfolios** side by side. Each portfolio is:

> **one validated strategy (a `trading.lab` release) + its own broker account + its own capital
> + its own approval & risk policy + its own schedule.**

Portfolios are **independent and isolated** — separate broker accounts, balances, P&L, and kill
switch. One blowing up or being paused never touches another. You manage all of them from a single
**web control plane** (separate from the lab dashboard), reachable remotely behind auth.

```
                         ┌─────────────────────────────────────────┐
   you (browser, phone)  │   trading.live WEB UI  (monitor+control) │
                         └───────────────┬─────────────────────────┘
                                         │ approve / pause / kill / onboard
                 ┌───────────────────────┼───────────────────────┐
        Portfolio A (x03)         Portfolio B (other release)   Portfolio C …
        ├ broker account A        ├ broker account B            ├ account C
        ├ $X capital              ├ $Y capital                  ├ …
        ├ approval + risk policy  ├ approval + risk policy      ├ …
        └ schedule (monthly)      └ schedule (weekly)           └ …
                 └───────────────── all read the SAME ──────────┘
              trading.marketdata + trading.lab releases + shared denylist
```

**The one rule that never bends (parity):** a portfolio's live trades are produced by the *exact*
`Release.build_candidates` code validated in the lab, fed by the *exact* `trading.marketdata`
loader the backtest used. The live engine is a broker + scheduler + safety wrapper around
validated code — never a re-implementation. If live and backtest signals could diverge, the
validation is void.

---

## 2. Non-negotiable live invariants (the order gate)

A portfolio may submit an order **only if every one of these is true**. The engine checks them in
order before any broker call; the first failure blocks and raises an alert. This is the contract
the rest of the document elaborates.

1. **Env/mode allowed** — `live` only when `TRADING_ENV=prod`; `dev`/`testing` are paper-locked (§18).
2. **Portfolio active** — not paused, not kill-tripped (§10.1).
3. **Account identity matches** — the broker account the keys reach hashes to the portfolio's
   configured account identity, and the endpoint matches the mode (paper vs live) (§13, §17).
4. **Release pinned** — the imported release code hash matches the promoted lab manifest (§11).
5. **Marketdata snapshot fresh & recorded** — inputs hashed and stored for this run (§6, §12).
6. **Signal parity holds** — live ranking equals a same-day lab backtest ranking (§12).
7. **Reconciled** — broker positions/cash agree with the live ledger within tolerance (§10.2).
8. **Tradable** — the symbol passes the tradability gate and is **not on the buy denylist** (§8).
9. **Policy permits** — approval policy auto-allows it, or a valid unexpired approval exists (§7).
10. **Idempotent** — the deterministic `client_order_id` for this intent has not already been
    submitted, and we are inside the release's execution window (§6, §11).

> Exits are privileged: a **sell that reduces or closes risk is never blocked by the denylist or by
> a stale-data anomaly** — you must always be able to get out. It still respects the kill switch
> and reconciliation block (those stop *all* order traffic).

---

## 3. Core concepts (your mental model)

| Concept | What it is |
|---|---|
| **Portfolio** | A live instance of one strategy. Has: a lab `release_id` (e.g. `x03`), a dedicated broker account, capital, an **approval policy**, a **risk policy**, a **schedule**, a **mode** (`paper`/`live`), and an operational **status** (`active`/`paused`/`retiring`/`retired`). |
| **Mode** (`paper`/`live`) | **Per portfolio, independent.** One portfolio can be live while another is paper. With Alpaca, paper and live are *separate accounts* (different endpoint + keys); mode is which account the keys point at (§4.1). |
| **Rebalance / run** | The strategy's periodic decision point (from the release; x03 = every 20 trading days). The engine ranks, diffs against holdings, and produces a **proposed order set**. Each run has a state machine (§6). |
| **Approval policy** | Per-portfolio rules classifying each order as auto vs needs-approval, by *risk direction* not just size (§7). |
| **Risk policy** | Per-portfolio pre-trade limits (concentration, exposure, daily-loss/drawdown) checked *before* approval classification (§7). |
| **Tradability gate / denylist** | A pre-trade filter; symbols that are halted, non-tradable, or on the **buy denylist** cannot be *bought* (sells still allowed) (§8). |
| **Pending approval** | A proposed order (subset) parked for you. **Expires** if you don't act — safer to skip than to fire stale orders (§7). |
| **Alert** | Something wanting attention: pending approval, reconciliation mismatch, broker error, risk/drawdown breach, parity drift, corporate-action mismatch (§14, §15). |
| **Kill switch** | Three levels (pause / kill / flatten), per portfolio and global; stored in DB **and** on disk (§10.1). |

---

## 4. What the web UI gives you

**Overview** — per portfolio: name, strategy, mode, equity, today's & cumulative P&L, # positions,
risk-utilization bars, next rebalance, status, health dot. A global banner (N approvals, M alerts)
and the **global kill switch**. A **dry-run parity** button that runs today's ranking with no
broker, to spot data issues before the close.

**Portfolio detail** — current positions with hold timers (days held / horizon) and unrealized
P&L; the **pending order set** when due, shown as *current book vs proposed book* with weight
deltas and a per-order **reason it needs approval** (new name / oversized / risk breach / anomaly),
plus **Approve / Approve-subset / Reject**; history (rebalances, fills with expected-vs-realized
quality); the **parity panel** (signal-match %, slippage bps vs backtest, tracking error).

**Control actions (behind auth)** — approve/reject; pause/kill/flatten a portfolio; reset a kill;
onboard/retire; edit capital, approval policy, risk policy, schedule, **and the denylist**; trip
the global kill. Every control action is written to the **audit log** with actor + timestamp.

---

## 5. Your workflows

### 5.0 Beginning — bring the platform up (once)
1. Stand up the control plane (paper) reachable remotely behind auth (§17). No portfolios yet.
2. Confirm data + lab wiring: the dry-run ("today's target book for x03", no broker) proves parity.
3. Drill the kill switch (global + per-portfolio; all three levels) before any money.

### 5.1 Onboard a portfolio (once per strategy)
1. **Pick a promoted release** — the UI offers only lab-`promoted` releases (today: x03) and pins
   its manifest hash (§11).
2. **Open & fund a dedicated broker account**; store its keys in the portfolio's secret slot (§17).
3. **Set capital, approval policy, risk policy, denylist scope** (start strict: `auto_max_pct=0`).
4. **Set the schedule** (release defaults; you pick the day/time, after the close settles, §19).
5. **Start in `paper` mode** (paper account). Run ≥1 full hold cycle; watch the parity panel.
6. **Promote to `live`** only after a clean paper cycle + parity < threshold + a kill-switch drill.
   Promotion attaches a *new, funded real account*'s keys (not a flag flip). On promotion the
   platform **auto-creates a shadow paper portfolio** mirroring the config — a permanent live-vs-
   paper parity feed at no extra effort.

### 5.2 Daily (a few minutes — most days nothing needs you)
1. Open Overview; scan health dots + global P&L.
2. Clear the alert queue: approve/reject pending orders; acknowledge alerts.
3. **Review yesterday's auto-executed orders** (light oversight of what the policy did unattended).
4. A reconciliation mismatch or corporate-action mismatch blocks that portfolio — confirm the fix.

### 5.3 Weekly (15–30 min)
1. Look ahead: which portfolios rebalance this week? Pre-read likely target books.
2. Health review: drawdown vs limit, risk utilization, cash, parity drift.
3. Capital review: independent accounts — decide top-ups/trims (manual transfers; the platform
   reports a **capital-drift alert** when broker cash deviates >X% from configured capital, which
   catches dividends or transfers you forgot).
4. Lab handoff: onboard/retire portfolios as the lab promotes/retires releases.

### 5.4 Per-rebalance (the real decision moment)
After the close settles the engine runs and parks a proposed order set: review the diff (sells =
matured exits; buys = new top names) and the per-order reasons; routine in-band orders may be
auto-marked; flagged ones wait. Approve (all/subset) or reject. Approved orders execute **sells
first, then buys**; rejected names simply don't move. Fills + parity update after.

> Cadence reality: an x03 portfolio has a real decision ~monthly. With several portfolios on
> different schedules, your week is mostly monitoring punctuated by occasional approvals.

### 5.5 Incidents
- One strategy misbehaving → pause or kill it; others keep running.
- Market-wide / freeze everything → global kill (block new orders; optional flatten behind confirm).
- Broker outage/auth failure → portfolio goes yellow, refuses to trade, alerts; never silently
  retries into a bad state.

---

## 6. The execution clock (parity's sharpest edge)

The backtest fills at a specific price; the live system must reproduce *that* price or the parity
claim is void. The engine runs **after** the close, so it cannot get the same-bar close fill the
backtest assumed unless the clock is defined explicitly. **Every release declares an execution
clock**, and its lab backtest must model the matching fill:

| Field | Meaning (x03 example) |
|---|---|
| `signal_date` (D) | bar whose close drives the ranking (close of D) |
| `data_asof` | timestamp of the marketdata snapshot used (settled close of D) |
| `decision_time` | when the engine ranks + proposes (after D close settles) |
| `submission_window` | when orders may be sent (e.g. D+1 open, MOO) |
| `live_order_type` | the live order (e.g. market-on-open / limit) |
| `backtest_fill_assumption` | **must match** the live fill (e.g. D+1 open) — enforced in the lab |

If a release's live clock and its backtest fill assumption disagree, the release is **not eligible
for live** until the lab re-validates on the correct fill. The per-run **marketdata snapshot**
(provider, `data_asof`, calendar version, universe membership, adjustment policy, row counts,
missing/stale symbols, input hash) is recorded so signal parity (§12) is reproducible and a daily
`parity.replay` can re-run `build_candidates` on the stored snapshot and diff vs what was proposed.

**Run state machine:** `scheduled → context_building → candidates_built → proposal_created →
awaiting_approval → executing_sells → executing_buys → reconciling → complete`; failure terminals:
`failed | expired | cancelled | superseded | blocked`.

---

## 7. Approval policy & per-portfolio risk policy

Two gates run per order: the **risk policy** first (hard limits), then the **approval policy**
(auto vs you). Both are per-portfolio, stored in the DB, editable in the UI without a deploy.

**Risk policy (pre-trade, hard).** Configurable knobs; a breach forces approval or blocks, and is
shown as the reason in the UI ("would be 14% of book, limit 12%"):
`max_single_position_pct`, `max_sector_exposure_pct`, `max_top_n_concentration_pct`,
`max_daily_loss_pct` / `max_drawdown_pct` (trip → auto-pause), `max_daily_turnover_pct`.

**Approval policy — by risk *direction*, not just size.** Risk-reducing actions are safe to
automate; risk-increasing actions earn scrutiny:

| Order kind | Default |
|---|---|
| Sell to exit a matured hold / reduce risk | **Auto**, unless anomaly |
| Buy a brand-new position | **Approval** (especially while young) |
| Increase an existing position | Auto only within a tight notional band |
| Sell forced by reconciliation repair | **Approval** |
| Flatten from kill switch | Separate emergency action (§10.1) |
| Any order during parity drift | **Block** |
| Any order during broker/ledger mismatch | **Block** |

Auto requires *all*: order within band (`auto_max_pct`, `auto_max_names`, `auto_max_daily_turnover`)
AND a **liquidity gate** (e.g. 20-day ADV ≥ 5× order notional) AND a **volatility gate** (e.g. no
auto if the name gapped > X% vs last close). New portfolios start fully manual (`auto_max_pct=0`);
relax after clean cycles. **Pending approvals expire** (default ~90 min after the open) — stale
fills kill edge.

---

## 8. Tradability gate & stock denylist

Before any **buy** is proposed, each candidate passes a **tradability gate**. A symbol is buy-
eligible only if it is currently tradable at the broker **and not on the denylist**. This never
blocks a **sell** — you must always be able to exit a position you already hold.

**The denylist** is an explicit list of symbols you never want *bought*, regardless of what a
strategy ranks. Two layers, merged at gate time:
- **Platform denylist** — a version-controlled file `trading/live/denylist.yml` (baseline; changes
  are auditable through git). Applies to **all** portfolios.
- **Per-portfolio denylist** — DB-stored, editable in the UI for quick/emergency additions, scoped
  to one portfolio.

Each entry carries: `symbol`, `reason`, `scope` (platform | portfolio_id), optional `expires`
(auto-removes after a date), and `added_by`/`added_at` (audit). Matching is by symbol; corporate-
action renames are normalized through `trading.marketdata`.

**The gate also auto-blocks buys (not just the manual list):**
- **Halted / LULD** — symbol in an exchange volatility halt at decision/submission time; never
  retry a market order into a halt (catastrophic reopen slippage).
- **Non-tradable / delisted / unknown** at the broker.
- Optional category rules a portfolio can switch on: leveraged/inverse ETFs, sub-`min_price`,
  below a liquidity floor, or inside an earnings blackout.

A blocked candidate is dropped from the buy set and logged as `tradability.blocked` with the
reason; if it materially changes the target book, the rebalance is flagged for your approval rather
than silently shrinking. The denylist is surfaced and editable in the UI (§4).

---

## 9. Order execution & fills

- **Order types per release clock** (§6): market / limit / MOO / MOC, with explicit time-in-force.
  The wrapper does not invent a type a release wasn't validated with; any override is audited.
- **Whole vs fractional shares**, `min_notional`, and a `cash_reserve_pct` buffer to avoid rejected
  buys. Sequencing: **sells before buys** to free buying power.
- **Partial fills** tracked via the broker's **WebSocket/SSE trade-update stream**, not REST
  polling. To modify an order, **cancel-and-replace** (cancel, await confirmation, recompute the
  unfilled remainder, submit fresh) — never blind-`replace` (broker replace semantics evaluate
  against the *original* qty and corrupt the ledger).
- **Unknown state after a timeout** (network drop post-submit) → the portfolio **blocks further
  action until reconciled**; we never blindly resubmit. Safe resume is guaranteed by the
  deterministic `client_order_id` (§11) — the broker rejects a duplicate.
- **Rate limits**: exponential backoff honoring `Retry-After` on HTTP 429; batch marketdata via
  bulk endpoints rather than per-symbol calls.
- **Costs**: persist realized commission + slippage per fill for net P&L and parity attribution.
- **Connection health**: the fill stream expects heartbeats; a missed heartbeat tears down and
  reconnects (cross-country links drop silently).

---

## 10. Integrity mechanics

### 10.1 Kill switch — three levels, broker-enforced
- **Pause** — scheduler stops creating proposals; no new orders; existing open orders left as-is.
- **Kill** — no new proposals/orders **and** call broker `cancel_all_orders` for that account;
  reconciliation + monitoring keep running.
- **Flatten** — cancel opens **and** submit liquidation orders; requires live re-auth + an extra
  confirmation; logs an emergency action.

Kill state is stored in **both the DB and a file on disk** that the engine reads before every
submit, so it survives a DB outage. **Global kill** = cancel opens + block new orders across all
portfolios (it does not auto-flatten unless you choose the stronger action). Drilled monthly.

### 10.2 Reconciliation — before every run, and after every fill
Compare broker vs ledger on: symbol, qty, side, avg entry price, market value, cash, buying power,
open orders, pending fills. **Tolerances** are explicit (share qty, cash to the cent, price,
fractional rounding). On mismatch: classify → **block trading** → show broker-state vs ledger-state
→ allow a manual resolution action → write an audit event → require a fresh `reconcile.ok` before
the next order. **Hold timers are owned by fills** (first-fill timestamp), never by the proposal
date or a position snapshot. Reconciliation events log `expected` vs `actual` in `data`.

### 10.3 Corporate actions
Splits, dividends, mergers, delistings, spin-offs break positions, P&L, hold timers, and parity if
unhandled (this bit the lab before — the x03 split-adjustment correction). A **nightly corporate-
actions job** reconciles broker positions against `trading.marketdata` split/dividend events:
splits adjust shares/price in positions + history; cash dividends credit cash (or reinvest per
portfolio setting); delistings/mergers flag for approval or close per rule. **Live and backtest
must use identical adjustment methodology** (this is part of parity, §12). A mismatch raises
`reconcile.corp_action_mismatch` and blocks trading until resolved.

---

## 11. Release immutability & idempotency

**Pinning.** Every portfolio stores `release_id` + `release_git_sha` + `params_hash` (+
`release_image_digest` in containerized deploys). A promoted release ships a **manifest**
(`release_id`, `release_version`, `git_sha`, `strategy_class`, `params_hash`,
`marketdata_schema_version`, `validation_report_hash`, `promoted_at`, `promoted_by`). The engine
**refuses to run if the imported code hash ≠ the pinned manifest** — a redeploy of `trading.lab`
can never silently change live behavior. The triple is stamped on every `run.start` event.

**Idempotency.** The rebalance key is not just `(portfolio, date)` but
`(portfolio_id, scheduled_rebalance_id, release_id, release_version_hash, marketdata_snapshot_id,
run_attempt)` — so a retry is safe, but *changed inputs are visible, not silently merged*. Each
order uses a deterministic **`client_order_id`** = hash of (portfolio, symbol, side, rebalance
date); the broker's matching engine rejects duplicates, so a crash-resume cannot double-submit.

---

## 12. Parity & the edge audit

For each live portfolio the platform continuously answers *is this still the strategy I validated?*
and shows three numbers, alerting if any breaches for **2 consecutive rebalances**:
- **Signal parity** — live ranking on D equals a same-day lab backtest ranking on D (same release,
  same marketdata snapshot, §6). Mismatch blocks trading.
- **Fill slippage (bps vs backtest)** — realized fills vs the backtest's modeled fill under the
  release clock (§6). Persistent negative slippage means execution is eating the edge.
- **Tracking error** — realized equity curve vs the modeled curve over the window.

The daily `parity.replay` (§6) catches *data-loader* drift, not just code drift.

---

## 13. Safety model (summary)

Everything above rolls up to: **paper-first per portfolio**; **only-promoted, hash-pinned releases**
(§11); **real money only in prod** (§18); the **10-invariant order gate** (§2); **isolation by
construction** (separate accounts); **reconcile-before-act** with hold timers owned by fills (§10.2);
**three-level, disk-backed kill** (§10.1); **idempotent, deterministic order IDs** (§11);
**startup identity checks** (broker endpoint matches mode, account-identity hash matches config,
live keys unavailable outside prod, paper keys rejected in a live config — prevents pointing
portfolio A at account B); and a **secrets abstraction** (`secrets.py`) so credentials are never
read ad hoc from env in broker code. Remote control is an attack surface — auth + private network
(§17), every control action in the audit log.

---

## 14. Logging & daily observability (for external analysis)

Every operational action is a **structured JSONL event** in **daily-rotated files**, so you can
point your own AI agent at a day's logs to analyze operational health and propose fixes. The agent
is **out of scope — you run it**; the platform just emits clean logs. Scope is **operational
health** (execution, infra, data, broker, reconciliation, latency) — *not* alpha/decay judgments.
**The DB is the state source of truth; JSONL is the event/audit/analysis stream**; critical events
are emitted from committed DB state to avoid log/state divergence.

**Every event carries:** `schema_version`, `event_id` (ulid), `ts` (ISO-8601 UTC), `level`,
`event` (typed), `component`, `portfolio_id`, `mode`, `release_id`, `run_id`,
`correlation_id`/`causation_id` (reconstruct a run's lifecycle), `actor_type` (`system`|`user`) +
`actor_id`, `attempt`, `message`, `data`, and `latency_ms`/`error` where relevant. **Secrets,
API keys, and account numbers are redacted** (symbols are fine).

**Daily files** — one directory per UTC day:
```
trading/live/logs/2026-06-18/
  events.jsonl   ← full operational event stream (agent source of truth)
  errors.jsonl   ← WARN/ERROR subset (fast triage)
  summary.json   ← end-of-day rollup: counts by event/level, per-portfolio run outcomes, fills,
                   total slippage vs modeled, reconciliation/parity status, rate-limit backoffs,
                   avg API latency, open alerts
  manifest.json  ← schema version + file list
```
Retention: hot `events.jsonl` ~90 days, gzip to cold ~2 years, **keep `summary.json` indefinitely**.
`logs/` is gitignored.

**Taxonomy** (additions in **bold**): scheduler (`scheduler.tick`, `portfolio.due|skipped`,
**`scheduler.missed_run`**); data (`data.fetch|stale|error`, **`marketdata.snapshot`**); run
(`run.start|end`, `context.built`, `ranking.done`); decisions (`proposal.created`,
`policy.classified`, **`risk.violation`**, `approval.requested|granted|rejected|expired`); gate
(**`tradability.blocked`**); execution (`order.intent|submitted|filled|rejected|error`,
**`order.partial_fill`**, **`order.unknown_state`**); integrity (`reconcile.ok|mismatch`,
**`reconcile.corp_action_mismatch`**, **`corporate_action.applied`**, `parity.ok|drift`,
**`parity.replay`**); risk/ops (`circuit_breaker.tripped`, `killswitch.changed`, `broker.error|retry`,
**`notification.sent`**, `alert.raised`).

---

## 15. Notifications & alerting

You won't watch the UI all day, so the platform pushes. Per-portfolio / per-severity channels
(email, Telegram/ntfy/Pushover, optional webhook), with **quiet hours**:
- `INFO` — no action (log only).
- `WARN` — review when convenient.
- `ACTION_REQUIRED` — pending approval / reconciliation; rich notification + deep link to approve.
- `CRITICAL` — live kill, broker auth failure, reconciliation/corp-action mismatch, large slippage,
  drawdown breach — immediate + escalation.

---

## 16. What the platform does NOT do (on purpose)

- It does **not** invent exits/stops a strategy wasn't validated with (x03 is a pure time-exit,
  equal-weight book — no surprise trailing stops).
- It does **not** sweep cash between portfolio accounts automatically (you do; it only reports).
- It does **not** internally cross/net trades between portfolios (a peer review proposed this — it
  is **rejected**: an internal A→B transfer is not what any backtest did, so it breaks both
  isolation and parity). Cross-portfolio **wash-sale awareness** is provided only as an *alert /
  tax-lot report*, never as auto-netting.
- It does **not** run un-promoted / experimental releases — that's the lab's job.
- It does **not** re-implement strategy logic — it imports it.

---

## 17. Architecture

```
trading/live/
  config.py          ← TRADING_ENV bundle (dev/testing/prod) — see §18
  secrets.py         ← secret resolution abstraction (no ad-hoc env reads in broker code) — NEW
  portfolios/        ← declarative per-portfolio defaults; source of truth is the DB
  denylist.yml       ← platform buy-denylist (version-controlled baseline) — see §8 — NEW
  denylist.py        ← denylist + tradability-gate loader/checker (pure) — NEW
  broker.py          ← broker adapter, per-portfolio account; submit + WebSocket/SSE fills
  context_builder.py ← builds the live StrategyContext (parity with lab swing backtest)
  planner.py         ← PURE: context → rank → reconcile-diff → risk/policy/tradability classify
                       → proposed order set. No I/O (unit-testable against logged events) — NEW
  executor.py        ← broker I/O: submit (client_order_id), track fills, cancel-and-replace — NEW
  policy.py          ← approval classifier (risk-direction matrix) — NEW
  risk.py            ← per-portfolio pre-trade risk-limit checks — NEW
  calendar.py        ← NYSE/NASDAQ trading calendar + DST-correct scheduling — NEW
  corporate_actions.py ← nightly split/div/delist reconcile + adjustment — NEW
  notifications.py   ← push channels + severity routing + quiet hours — NEW
  scheduler.py       ← which portfolios are due (calendar-aware); triggers runs — NEW
  engine.py          ← orchestrates a run: planner → approval/auto → executor → ledger — NEW
  ledger.py          ← live state DB (separate from lab): see data model below
  logging.py         ← structured JSONL emitter + daily rotation (§14) — NEW
  logs/              ← daily log directories (gitignored; consumed by your agent)
  web/               ← control plane (separate app from lab): api/ (FastAPI) + ui/
  DESIGN.md          ← this file
```

**Dependency direction unchanged:** `marketdata ← lab ← live`. `live` imports validated releases
from `trading.lab` and reads `trading.marketdata`; nothing flows back. **Engine split:** `planner`
is pure (testable), `executor` does all broker I/O.

**Recommended stack (decisions in §23):** **FastAPI** backend; **HTMX/Jinja for v1** (React later
only if the UI gets interaction-heavy); **Tailscale** for remote access (E2E WireGuard, zero open
ports — a reverse proxy like Cloudflare Access terminates TLS at its edge and can see plaintext,
worse for a trading-control plane). Bind the web server to the Tailscale interface only.

**Live DB — not DuckDB.** DuckDB is the lab's analytics ledger, wrong for live OLTP (concurrent
web + scheduler + engine + fill-stream writers). **SQLite (WAL + `busy_timeout`, single-writer via
a serialized task queue) is acceptable for P0/P1; migrate to Postgres before serious live.** Heavy
parity aggregations run off a replica/export, never as long reads against the live DB (WAL
checkpoint starvation). Tables: `portfolios`, `release_manifests`, `rebalance_runs`,
`order_proposals`, `approvals`, `order_intents`, `fills`, `positions` (hold-day authority from
fills), `denylist`, `corporate_action_events`, `alerts`, `audit_log` (append-only),
`flags` (kill switches). Secrets referenced by handle, stored outside the DB (§13).

---

## 18. Environments & deployment

**Two orthogonal axes — never conflate:** `TRADING_ENV` (`dev`|`testing`|`prod` — *where* it runs)
vs per-portfolio **mode** (`paper`|`live` — *which account*). The hard link:

> **Real money only in prod.** A `live` portfolio is refused unless `TRADING_ENV=prod`; `dev` and
> `testing` are code-locked to paper, checked in the engine before any order path.

| Env | Host | Purpose | Allowed modes |
|---|---|---|---|
| `dev` | this laptop | development, fast iteration | **paper only** |
| `testing` | remote host | pre-prod validation on real infra (real schedules, paper trading) | **paper only** |
| `prod` | remote host | the real thing | paper + **live** |

`testing` and `prod` coexist on **one DigitalOcean Ubuntu droplet**, **fully isolated**: separate
Docker projects, **separate Docker networks** (no cross-talk), volumes, DB, logs, ports, secrets,
kill switches. (Choose a NYC/East-coast region for proximity to the exchanges/broker; size for the
live-scoped marketdata cache + Postgres, not the lab's heavy artifacts.)

**Packaging — Docker compose per env.** Same images on laptop and host. Prod compose uses
`restart: unless-stopped` and mounts secrets **read-only**.

**What deploys:** the *code* of `trading.marketdata` + `trading.lab` (for Release classes), **not**
the 12.8 GB research DuckDB nor the 28 GB bar cache. Each env warms its own live-scoped marketdata
cache (~420d for x03) from providers — never seeded from dev.

**Deploy flow — GitHub Actions CI/CD:** testing auto-deploys on merge to `main` (build → `pytest
trading/lab/tests` → push image → host pulls/recreates **testing**); prod deploys on a **release
tag** behind a **manual approval** (recreates **prod**; redeploy the prior tag to roll back). Image
registry: **GHCR**. **Promotion = code only** — portfolios/secrets/balances/live-DBs are per-env,
never copied. Real broker keys live only in the **prod** secret store (Doppler/1Password/host
keychain) — never in the repo or on the laptop. A deploy never auto-resets a tripped kill switch,
and **refuses to start on an unknown/failed DB migration** (§20).

---

## 19. Scheduling & market calendar

The scheduler wakes each trading day after the close settles, asks each portfolio "due per your
schedule?", and runs the engine for due ones (x03 ≈ monthly, so most days are just a health +
reconcile pass). **Calendar correctness is mandatory:** use a real NYSE/NASDAQ calendar
(`pandas_market_calendars`/`exchange_calendars`) for holidays and early closes, and schedule
triggers in **`America/New_York` via `zoneinfo`** while everything else (OS, containers, DB, logs)
runs in **UTC** — a hardcoded UTC cron fires an hour off after a DST flip. The market date is part
of the idempotency key (§11). P0/P1 may use a daily cron invocation; a long-running APScheduler
service comes later (graceful shutdown mid-rebalance, in-memory idempotency).

---

## 20. Operations: migrations, backups, health

- **Schema migrations** — versioned (Alembic); app startup checks the expected version; a deploy
  **refuses to start** on an unknown/failed migration.
- **Backups & restore drills** — back up the live DB, audit log, JSONL logs, config, and release
  manifests. **Monthly restore drill**: restore into an isolated env, verify portfolios/positions/
  approvals/history, reconcile the restored state against a read-only broker snapshot.
- **Health alerts** — disk > 80%, log/DB write failure, **system clock drift**, marketdata
  freshness failure, broker auth failure, **scheduler missed run**, container restart loop.

---

## 21. Phases & acceptance criteria

- **P0 — control-plane skeleton (paper, no broker).** *Done when:* loads a promoted release
  manifest; builds the target book from live marketdata; records release-hash + marketdata-snapshot
  hash; shows the book + denylist in the UI; no broker creds accepted; kill-switch state exists and
  is testable.
- **P1 — one live-capable portfolio (paper).** *Done when:* a fake broker passes the full order
  lifecycle (incl. partial-fill + rejected); Alpaca **paper** passes submit/fill/reconcile;
  approval expiry works; re-running a rebalance cannot double-submit; the ledger survives a process
  restart; structured JSONL logging (§14) from day one.
- **P2 — parity audit + policies.** *Done when:* signal parity + slippage attribution implemented;
  drift bands configurable and block risk-increasing orders; risk policy + approval matrix +
  tradability/denylist enforced; corporate-actions job running; notifications wired.
- **P3 — multi-portfolio + remote UI hardening.** *Done when:* N portfolios run simultaneously;
  startup account-identity verification prevents key/account mixups; global kill cancels opens +
  blocks new; remote access is private-network-only; audit log records actor + action; kill drill
  passes.
- **P4 — small live → scale.** *Done when:* live starts with tiny capital; margin disabled; max
  order notional + daily-loss/drawdown breakers enforced; a restore drill is completed before
  scale-up.

---

## 22. How the current scaffolding maps

The existing stubs (`broker.py`, `context_builder.py`, `portfolio.py`, `ledger.py`, `config.py`,
`runner.py`) are the P0/P1 nucleus. `runner.py` splits into **`planner.py`** (pure) +
**`executor.py`** (I/O), orchestrated by **`engine.py`** and invoked per portfolio by
**`scheduler.py`**; `broker.py` becomes per-account with a fill stream; `ledger.py` grows the
multi-portfolio + manifests + approvals + denylist + corporate-actions + audit tables. New:
`secrets.py`, `policy.py`, `risk.py`, `calendar.py`, `corporate_actions.py`, `notifications.py`,
`logging.py`, `denylist.py` + `denylist.yml`, and the `web/` app. Parity (`context_builder` +
imported releases) and the target-book reconciler carry over unchanged in spirit.

---

## 23. Decisions & open questions

**Decided (from the peer reviews):**
- Remote auth → **Tailscale**. Live DB → **not DuckDB; SQLite (WAL) for P0/P1, Postgres before
  serious live**. Web → **FastAPI + HTMX/Jinja v1**. Scheduler → **cron P0/P1, APScheduler later**.
  Approval defaults → **`auto_max_pct=0`, ~90 min expiry**. Logging → **JSONL + daily `summary.json`,
  enriched schema (§14)**. Registry → **GHCR**. Host → **one DigitalOcean Ubuntu droplet** (NYC
  region) running the `testing` + `prod` Docker stacks, Tailscale-only ingress (§18).

**Still open:**
- **Broker account model (gates the isolation claim).** A review asserts a retail Alpaca *identity*
  may hold only **one live account** (KYC/AML); true multi-account is Broker-API/institutional. If
  so, "separate live account per portfolio" needs one of: (a) **virtual sub-ledger** on one live
  account (lose hard isolation), (b) **Alpaca Broker API** sub-accounts (institutional onboarding),
  (c) **IBKR linked accounts / LLC prop-group** (physical isolation, heavier). **Verify the live-
  account policy, then decide.** Paper is unaffected, so P0/P1 proceed regardless.
- **First-run marketdata cache warming** on the droplet (cold-fetch from providers vs. a seeded
  snapshot). Host is decided: **DigitalOcean Ubuntu droplet** (§18).
- **Secret store** backend (Doppler / 1Password / host keychain), prod keys isolated to prod.
- **Notification channel(s)** to wire first (email vs Telegram/ntfy).
- **Denylist seed** — which symbols/categories you want on the platform baseline (§8); ships empty.
