# llm_trader code review — 2026-07-16

Scope: `trading/llm_trader/` with emphasis on multi-strategy layout, `cup_handle`,
deterministic execution, batch harness, and agent reliability. Grounded in recent
pilots (BNY 0.1–0.3) and `testset_10` batch `20260716130652-BATCH-0668d1`.

---

## 1. What is strong (keep)

| Area | Why it matters |
|---|---|
| **Clean package split** `marketdata ← lab ← live` monorepo + `llm_trader` multi-strategy families | Clear dependency direction; skills under `strategies/<id>/skills/` |
| **Deterministic OHLC engine** (`execution.py`) | Agent emits intent only; fills/size/costs not LLM-authored — huge anti-cheat / reproducibility win |
| **One-tick gateway** (`step.IsolatedStreamGateway`) | Real no-look-ahead; better than “trust the prompt” |
| **Skill versioning + seal hashes** | Behavioral edits cannot silently rewrite history |
| **Promotion tooling** (`compare`, effective-R, RULE_TRACE, IMPROVING) | Warrior-grade experiment discipline; cup_handle can reuse it |
| **Multi-day continue harness** | Fixes hermes early-exit mid-ARM (observed on BNY 0.2/0.3) without changing skill math |
| **Viewer multi-day dates + JSON-safe metrics** | Recent fixes for real operator pain |

Recent `testset_10` (skill 0.3.0): **0 abandoned**, 7 continues, 5 trades all green on that slice, 5 stands — process infrastructure is largely working.

---

## 2. Architecture risks (agent / code failure modes)

### 2.1 Agent loop is still a “long chat with shell tools”

**Problem:** Multi-day streams are ~80 daily bars × (step + resolve + log) ≈ **200+ tool cycles**. Models self-stop with progress reports (BNY 0.2/0.3). Continues paper over that; they do not remove root cause.

**Risk:** Cost, latency, residual abandon after continue budget, non-deterministic manage quality.

**Directions (prefer simplification):**

1. **Plan-then-watch fast path (highest leverage)**  
   Lookback phase: allow **batch observe** or server-side “summary of bars 0..N” without 40 LLM turns, *or* auto-OBSERVE until checklist-ready with LLM only on arm/manage bars.  
   Keep full per-bar LLM only from arm → flat.

2. **Harness-owned loop for pure OBSERVE**  
   If last N decisions are OBSERVE + flat + unarmed, harness advances bars and only wakes the model on structure change / setup day / fill events.  
   Same no-look-ahead if advances go through the gateway.

3. **Hermes turn budget explicit**  
   Document/raise max turns; fail closed with `agent_abandoned` if exit while live (already partly done).

### 2.2 Dual execution paths + dual position engines

**Problem:** `PositionEngine` (legacy reported-fill) lives in `recorder.py` beside `ExecutionEngine`. Batch defaults still mention `reported_fill_v1`. Two validation graphs, two mental models for agents and reviewers.

**Risk:** Wrong path on skill mis-pin; test matrix explosion; subtle P&L differences when comparing history.

**Directions:**

- Mark reported-fill **read-only / archive**; refuse new skills without `deterministic_ohlc_v1`.
- Eventually delete or isolate legacy behind `llm_trader/legacy/`.
- Single public action vocabulary in one module (already partly true for deterministic).

### 2.3 God modules

| File | ~LOC | Issue |
|---|---|---|
| `batchsim.py` | ~2750 | prompt + sandbox + run + audit + compare + promote + diagnostics |
| `recorder.py` | ~2600 | init/log/finalize + engines + list/metrics + report |

**Risk:** Hard to review; accidental contract changes (prompt hash / harness hash) with drive-by edits; slow tests.

**Directions:** Split without behavior change:

```
batchsim/
  prompt.py, run.py, audit.py, compare.py, continue.py, cli.py
recorder/
  session.py, finalize.py, metrics.py, report.py
```

Keep public `python -m trading.llm_trader.batchsim` entrypoints stable.

### 2.4 Skill vs SPEC vs scanner mismatch (cup_handle)

| Source | Entry / gates |
|---|---|
| `SPEC.md` | Break of handle high + **green close** + **vol ≥ 1.3× 20d**; SMA200 required; handle 3–15 |
| Skill 0.3.0 | ARM at handle high; ENTER_CLOSE if already above; SMA200 **soft if null**; no hard vol×1.3 |
| Scanner (`patterns.py`) | Mechanical detect; feeds testsets |

**Evidence:** On `testset_10`, **ENTER_CLOSE dominated** (4–5 leaves) vs pure ARM path (PGY). Agents treat “plan ready mid-lookback after lip already broken” as market-on-close, not stop entry.

**Risk:**

- Skill edge ≠ scanner edge → backtest on scanner names does not measure SPEC edge.
- ENTER_CLOSE on already-extended bars may worsen R (late entry, same stop formula from trigger).
- Soft SMA200 admits weaker trends.

**Directions:**

1. **One source of truth:** SPEC formulas copy into skill front-matter or skill generates from SPEC; RULE_TRACE cites SPEC rows.
2. **Prefer ARM-only** for cup_handle v0.4: forbid ENTER_CLOSE except setup-day exception with vol filter; or require green close + rvol≥1.3 for ENTER_CLOSE.
3. **Expose scanner plan levels in meta** (handle_high, stop, cup_depth) optionally under skill flag — reduces reduce LLM measurement error; keep LLM for “stand vs arm” judgment only. (Tradeoff: less “discovery”; more reliability.)

### 2.5 Prompt bloat and duplicated rules

Skill (~12KB) is inlined fully into every hermes prompt; batchsim wraps more stop/continue rules. Agent sees:

- skill shell/init steps (batch already did init/start)
- redundant “do not read _sealed” (sandbox already blocks)

**Risk:** Instruction conflict; attention on wrong sections; longer context → more mid-run abort.

**Directions:**

- **Batch skill slim:** strip “how to init” when `batchsim` runs; inject “runtime contract only” section.
- Split skill into `skill_runtime.md` (agent) vs `skill_operator.md` (human CLI).
- Cap batch prompt: single stop table, no thrice-repeated “don’t abandon.”

### 2.6 Simulations tree pollution

`simulations/` holds 20k+ artifacts **and** ad-hoc agent helper scripts (`log_bar*.py`, `_batch_runner.py`).  
**Risk:** Agents invent local helpers; audit surface grows; disk/noise.

**Directions:** `.gitignore` already heavy — also **sandbox deny-write** except decisions.jsonl; quarantine helper scripts out of sim dirs; periodic archive.

### 2.7 Metrics / viewer footguns (mostly fixed)

- `profit_factor_r = Infinity` broke JSON (fixed 2026-07-16).
- Keep `json.dumps(..., allow_nan=False)` on all API paths (SSE events too if any float metrics).

---

## 3. Profitability levers (cup_handle first)

Ordered by expected impact × ease given current system.

### P1 — Align entry quality with SPEC (skill 0.4.x)

- Require **breakout volume** and/or **green close** before treating break as valid (especially ENTER_CLOSE).
- Hard-fail handle length outside 3–15 (SPEC) — not soft prose.
- Optional: cancel arm if handle expands >40% of cup depth after arm (SPEC handle depth).

**Hypothesis:** fewer late/extended ENTER_CLOSE; higher stand rate; better R on traded.

### P2 — Stop and scale mechanics

- Skill T1/T2 from **entry_trigger + f×depth** is fine; after fill, **R-based** scales sometimes diverge from fill gap — document “use absolute targets from plan; ignore fill gap for T1.”
- Trail rules after T1 (SET_STOP to BE) are underspecified → LLM variance. Objectify: after T1 fill → BE; after T2 → trail under prior bar low / SMA20.
- BNY-class losses: stop is 1.5×ATR under trigger but **gap entries** widen risk per share vs plan — engine sizes on stop distance from fill; verify open_risk ≤ budget after gap (should already); consider **wider plan stop** or **skip if open gap > 0.5×ATR**.

### P3 — Scanner / set construction

- `testset_10` win-rate is not a promote gate (n=5 trades).
- Build **dev vs holdout** for cup_handle (same as warrior IMPROVING).
- Score scanner candidates by **historical breakout continuation** features offline (no LLM) to raise base rate before paying for agents.

### P4 — Reduce dead lookback cost without changing edge

- Auto-forward lookback → spend model budget on **arm decision + manage**, not bar 0…20 narration.
- Same expected edge, lower variance from fatigue/abort.

### P5 — Risk budget / profile

- Swing $500 risk is fine for research; for live comparison hold constant across A/B.
- Consider **max heat** across concurrent names if live path is added later (out of scope for sim).

---

## 4. Reliability levers (infra)

### R1 — Continue harness (done; harden)

- Log `continues_used` on session.json (not only batch log).
- After continue budget: status `agent_abandoned` + resume — already close.
- Optional: **auto-OBSERVE continue** without LLM when only pending arm and no structure change (cheap).

### R2 — Contract tests for agent-facing surfaces

Golden tests for:

- multi-day prompt contains arm-early + no BATCHSIM_SID while armed
- finalize stamps dates on multi-day actions
- JSON metrics never contain non-finite floats
- continue detector on live arm

### R3 — Timeout / cost

- Multi-day default timeout 900s × (1+continues) can cascade.
- Per-continue shorter timeout once past arm; or raise initial timeout only for multi_day.

### R4 — Delete or fence legacy

- Refuse `reported_fill_v1` for new cup_handle/warrior major versions.
- Single finalize path in tests for multi-day.

---

## 5. Simplification map (make agents fail less)

| Idea | Agent risk removed | Edge risk |
|---|---|---|
| Auto-OBSERVE lookback | Mid-stream abort, token burn | Low if LLM still decides arm |
| Scanner levels in meta | Wrong handle_high / stop math | Medium — less “pure LLM plan” |
| ARM-only entry | Late ENTER_CLOSE | Medium — may miss some breaks |
| Slim batch skill text | Conflicting init instructions | Low |
| Split batchsim/recorder | Dev regressions | Low if pure refactor |
| Kill reported-fill path | Wrong execution model | Low for new work |
| Objectify trail after T1 | Random manage | Low–medium (testable) |

**Recommended sequence:**

1. Slim batch prompt + auto-OBSERVE lookback (reliability, cost).  
2. Skill 0.4 SPEC alignment (profitability hypothesis).  
3. Paired compare on `testset_30` vs 0.3.0.  
4. Module split of batchsim/recorder (maintainability).  
5. Legacy path freeze.

---

## 6. Concrete improvement backlog

### Immediate (days)

| ID | Item | Type |
|---|---|---|
| A1 | Skill 0.4: volume/green-close gate for ENTER_CLOSE; harden handle length | skill / profit |
| A2 | Batch prompt: strip init/CLI; one stop contract; multi-day only | reliability |
| A3 | Stamp `continues_used` + reason on session.json | observability |
| A4 | Auto-advance OBSERVE for multi-day lookback until checklist or setup−k | agent reliability |
| A5 | SSE/json already fixed — audit all dumps for `allow_nan=False` | reliability |

### Near-term (1–2 weeks)

| ID | Item | Type |
|---|---|---|
| B1 | `testset_30` + holdout exclude vs dev; promote gate on 0.4 | process |
| B2 | Objectify post-T1 trail in skill + RULE_TRACE | skill / profit |
| B3 | Split `batchsim.py` into package (no behavior change) | code risk |
| B4 | Optional meta.plan_levels from scanner for deterministic stop/target | reliability |
| B5 | Refuse new skills without deterministic_ohlc_v1 | code risk |

### Later

| ID | Item | Type |
|---|---|---|
| C1 | Offline breakout quality ranker for scan | profit base rate |
| C2 | Delete PositionEngine / reported-fill after archive | simplify |
| C3 | Live path shared Release with lab (if product goal) | product |
| C4 | Warrior 4.0.0 control batches (existing BACKLOG V4) | warrior |

---

## 7. What not to do

- **Don’t** add more prose checklists without mechanical predicates — warrior history shows soft manage ladders can REJECT on paired ΔR.
- **Don’t** promote cup_handle on n=10 or single BNY re-pilots.
- **Don’t** re-introduce agent-supplied fill prices.
- **Don’t** expand skill with shell tutorials for batch mode.

---

## 9. Implemented 2026-07-16 (follow-up)

| Item | Status |
|---|---|
| Slim multi-day batch prompt (runtime contract; strip init/shell/finalize) | **Done** (`_skill_text_for_batch_agent`, shorter `_prompt`) |
| Auto-OBSERVE deep lookback (default last 20 bars before setup for LLM) | **Done** (`_auto_observe_multi_day_lookback` in `_preseal`) |
| Skill **0.4.0** SPEC breakout quality + hard handle 3–15 | **Done** (base pointer) |
| Continue harness + agent_abandoned | Prior |
| JSON-safe profit factor | Prior |

Next: paired `testset_10` or `testset_30` run of **0.4.0** vs **0.3.0**.

---

## 8. Summary judgment

**Infrastructure:** B+ after multi-day date fixes, continue harness, JSON metrics fix. Main residual risk is **LLM turn length**, not fill cheating.

**Edge research:** Early. cup_handle 0.3.0 process works; **SPEC/skill/entry-mode alignment** and **scanner base rate** are the real profitability work. testset_10 is encouraging but not a gate.

**Code health:** Two megamodules + dual engines are the largest long-term footguns. Prefer **simplify agent surface** (fewer decisions per session) over more hermes continues forever.

---

*Reviewer: Grok (in-repo session, 2026-07-16). Evidence: BNY pilots, testset_10 batch, codebase inspection of batchsim/recorder/execution/step/skills.*
