**Overall Assessment**: This is an **excellent, production-minded spec**. It correctly prioritizes the hardest parts of running live strategies—**parity/fidelity to validated logic**, **isolation**, **paper-first discipline**, **human oversight via hybrid approval**, **reconciliation**, and **observability**—while keeping scope tight ("what it does NOT do"). The mental model, workflows, safety model, and phased rollout (P0–P4) are clear and operator-centric. The parity rule ("exact `Release.build_candidates` + exact `trading.marketdata`") is the right north star.

It already mitigates the classic failure modes (drift, silent execution mismatch, fat-finger, one bad strategy taking down everything). With modest additions it becomes even more robust for multi-strategy personal use.

---

### Strengths (what’s already strong)

- **Safety by construction**: Paper-first per portfolio, dedicated accounts, reconcile-before-act, two-level kill switches, only-promoted-releases gate, `TRADING_ENV` guard.
- **Parity as a first-class citizen** (§6) — this is rare and correct.
- **Hybrid approval policy** — pragmatic balance between automation and oversight.
- **Structured daily JSONL logging + `summary.json`** designed for an external agent — forward-thinking and low-friction.
- **Clear dependency direction** and "wrapper, not re-implementation" philosophy.
- **Phased, realistic rollout** with dry-run parity proof before money touches anything.
- Good ASCII diagram and explicit "what it does NOT do" section.

---

### Recommended Improvements

I’ve grouped them by impact and grouped high-priority items first. Many are additive (new sections or small extensions) rather than rewrites.

#### 1. Risk Management (High Priority — Pre- & Post-Trade Controls)

**Gap**: Approval policy + drawdown circuit breaker exist, but explicit **portfolio-level risk policy** and concentration/exposure checks are missing. Regulatory/best-practice literature (FCA, FIA) emphasizes calibrated pre-trade controls and independent risk checks.

**Recommendations**:
- Add a new **"Risk Policy (per portfolio)"** concept/table entry alongside Approval Policy.
- Configurable knobs (editable in UI):
  - `max_single_position_pct` (e.g. 8–12%)
  - `max_sector_exposure_pct`
  - `max_top_n_concentration_pct` (e.g. top 5 names ≤ 40%)
  - `max_daily_loss_pct` / `max_drawdown_pct` (triggers auto-pause or forces approval)
  - `volatility_target` or `max_beta_to_spy` (optional, if you add a simple risk model later)
- These checks run **before** policy classification and **always** require approval (or block) if breached. Surface them prominently in the pending-order UI ("Why this needs approval: position would be 14% of book").
- Add a **Risk dashboard** tile in portfolio detail + overview (current exposures vs limits, heatmaps).
- In §7 Safety, explicitly call out "pre-trade risk checks + post-trade reconciliation + circuit breakers".

This turns the platform into a proper risk-aware wrapper.

#### 2. Corporate Actions, Dividends & Adjustments (High Priority — Accuracy & Parity)

**Gap**: Not mentioned. Splits, dividends, mergers, delistings, and spin-offs will break position tracking, P&L, hold timers, and parity if unhandled.

**Add**:
- New lightweight module or integration in `marketdata` / `ledger.py` (or a `corporate_actions.py`).
- Automatic handling for:
  - Splits → adjust shares/price in positions + history.
  - Cash dividends → credit cash (or auto-reinvest per portfolio setting).
  - Delistings/mergers → flag for approval or auto-sell/close per rules.
- **Parity extension**: Live and backtest must use identical adjustment methodology (adjusted vs unadjusted prices, as-of dates). Document this in the parity panel.
- In ledger: add `corporate_action_events` table or events in the JSONL stream.
- Onboarding checklist: confirm the release + marketdata pipeline handles the names in the universe (or gracefully skips unknowns).

This is table-stakes for any equity swing/hold strategy like x03.

#### 3. Notifications & Remote Usability (High — You won’t stare at the UI all day)

**Gap**: Workflows assume you open the Overview daily. For phone/remote use, **push notifications** are essential for pending approvals and critical alerts.

**Add**:
- Configurable notification channels per portfolio / alert severity: Email, Telegram, ntfy.sh / Pushover, SMS (Twilio), or simple webhook.
- Pending approval → rich notification with summary + deep link to approve/reject.
- Critical (kill switch, reconciliation mismatch, large slippage, DD breach, broker auth failure) → immediate + escalation.
- New component: `notifications.py` (background task or Celery-like).
- In UI settings: per-portfolio notification rules + "quiet hours".

#### 4. Scheduler & Market Calendar (Medium-High — Reliability)

**Gap**: "after the close settles" and "trading days" need explicit handling for holidays, early closes, and data settlement windows.

**Recommendations**:
- Use `pandas_market_calendars` (or `exchange_calendars`) for NYSE/NASDAQ schedule.
- Add a small `calendar.py` or integrate into `scheduler.py`.
- Configurable rebalance offset (e.g., "first trading day of cycle + 30–60 min after close" to allow settlement).
- Explicit handling of non-trading days and early-close shortened sessions.
- Idempotency already good; make the market date part of the key.

#### 5. UI / Visualization & Approval Experience (Medium)

- **Pending orders UI**: Side-by-side "current book vs proposed book" with % weight changes, hold timers, and highlighted reasons. Visual allocation (pie or treemap) before/after.
- **Parity panel**: Interactive equity curve (live vs backtest), slippage distribution, per-rebalance attribution table.
- **Risk + health**: Sparkline of recent P&L, current risk utilization bars, open alerts count.
- **Mobile**: Responsive + PWA-friendly (or at least good phone layout). Add "Approve from notification" deep links.
- Optional power-user: "What-if" mode — temporarily adjust sizes and see projected risk/impact before approving.

#### 6. Execution, Partial Fills & Costs (Medium)

- Clarify order type policy (market-on-close vs limit? strategy-driven or wrapper override with audit?).
- Partial fills: explicit policy (wait until next cycle? cancel remainder? force market? configurable per portfolio).
- Persist **realized** commission + slippage per fill for accurate net P&L and parity attribution.
- In history: show "expected vs realized" fill quality.

#### 7. Architecture, Tech Choices & §15 Open Questions (Actionable Recommendations)

**My recommended answers** (incorporate into §15 or a new "Tech Decisions" subsection):

| Question                  | Recommendation                                                                 | Rationale |
|---------------------------|----------------------------------------------------------------------------------|---------|
| **Web stack**            | FastAPI (backend) + **HTMX + Jinja2 + Tailwind/Alpine.js** for v1. Full React only if dashboards get very rich. | Lightweight, fast iteration, no heavy frontend toolchain. |
| **Remote auth**          | **Tailscale** first (easiest for personal use, phone-friendly, ACLs). Cloudflare Access as alternative. | Zero-trust, minimal attack surface, no port exposure. |
| **Broker**               | Start with **Alpaca** (excellent API, commission-free, separate paper/live accounts, good 2026 recognition for algos). Use adapter pattern. Add IBKR later for options/futures/global or robustness. | Alpaca matches current scope perfectly; complaints on data are manageable with your parity/reconcile layer. |
| **Approval defaults**    | New portfolios: `auto_max_pct=0`. Stable: 3–5% / 2–3 names. Expiry: "until next market open + 2h" or fixed 6–8h. | Conservative start, then relax with track record. |
| **Scheduler form**       | Long-running service (`apscheduler` or similar) preferred over pure cron for dynamic schedules + WebSocket push potential. | More robust; cron still fine for P0. |
| **Live DB**              | **SQLite** (via SQLAlchemy/Tortoise) for P0–P3. Easy backup, zero ops. Migrate to Postgres if needed later. Add Alembic migrations from day one. DuckDB excellent for read/analytics layer on exports. | Perfect simplicity for single-operator scope. |
| **Secrets**              | Dev: `.env` (gitignored). Docker: mounted secrets or env from host. Host-side: **Doppler / Infisical** (open-source) or 1Password CLI / `pass`. Never in repo. Prod keys only on prod host. | Defense in depth + easy rotation. |
| **Logging**              | Your JSONL + daily dir + `summary.json` is excellent. Implement from P1. Retention: 30–90 days raw events, 1–2 years summaries. Optional daily agent cron that emails/Telegram-reports. | Already best-in-class for your use case. |
| **Remote host + cache**  | US East (low latency to Alpaca). Hetzner / OVH / Linode strong value. Warm cache on first deploy with retry/backoff script. | Practical & cost-effective. |
| **Registry**             | GHCR (free private repos). | Simple and integrated with your GitHub Actions flow. |

**New files to list in §10**:
- `risk.py` (policy checks)
- `corporate_actions.py`
- `calendar.py`
- `notifications.py`

**Suggested improved architecture diagram** (visual enhancement for §1 and §10):



*(Note: The generated visual above is illustrative. For the actual DESIGN.md I recommend including clean **Mermaid** source instead — it renders perfectly in GitHub, Obsidian, etc. I can provide the exact Mermaid if you want.)*

#### 8. Additional Sections Worth Adding

- **Corporate Actions Handling** (new)
- **Notifications & Alerting Channels** (new)
- **Performance Reporting & Exports** (tax-ready trade logs, attribution, CSV/PDF, Schedule D / 8949 friendly)
- **Disaster Recovery & Backups** (daily DB snapshots + log archival, tested restore procedure)
- **Platform KPIs & Observability** (reconciliation success rate, approval latency, slippage vs modeled, uptime, etc.)
- **Glossary** (Release, Portfolio, Run, Proposal, Intent, Fill, Parity, etc.)

#### 9. Minor Polish & Clarifications

- §2: Add "Risk Policy" to the Portfolio row in the table.
- §4.2 Daily: Add "Review any auto-executed orders from the prior day (light oversight)."
- §5 & new Risk Policy: Clarify precedence (Risk checks always gate before or alongside approval policy).
- §7: Add "Release code pinning / hash verification on import" and "Data pipeline validation on startup".
- §8 Logging: Add events for `risk.violation`, `corporate_action.applied`, `notification.sent`.
- §13 Phases: Fold risk policy + notifications into P2 or early P3.

---

### Prioritized Implementation Order (for your phases)

1. **P0/P1 core** — Keep as planned + add basic risk checks skeleton + market calendar.
2. **P2** — Parity panels + hybrid policy + **risk policy** + corporate actions handling.
3. **P3** — Full multi-portfolio UI + **notifications** + remote auth hardening.
4. **Ongoing** — DR/backups, tax exports, deeper attribution.

---

**Conclusion**: This spec is already at a high bar — better than many institutional starter designs in its safety focus. The additions above (especially risk policy, corporate actions, notifications, and calendar) close the remaining practical gaps for reliable multi-strategy personal trading without bloating scope.

Would you like me to:
- Draft the new sections in full markdown ready to drop into DESIGN.md?
- Provide the clean Mermaid diagram source?
- Sketch `risk.py` or `policy.py` interfaces / skeletons?
- Help turn any part into code (e.g., the scheduler with pandas_market_calendars, or a notification service)?

Just say the word and we’ll iterate. This platform has the potential to be genuinely trustworthy for running several strategies side-by-side.