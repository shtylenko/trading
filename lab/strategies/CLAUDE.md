# strategies/

Strategy families, each a directory; immutable release modules inside. Letters are owned per family (see root `CLAUDE.md`).

```text
strategies/
  base.py                    # StrategyRelease ABC — the release contract
  __init__.py                # release registry
  stocks_in_play_orb/        # letter o  (o01, o02, o03, ...)
  post_gap_opening_drive/    # letter d  (d01..d04)
  dominance_flip_reversal/   # letter f  (f01, ...)
  sma_mean_reversion/
  liquidation_cascade_reversal/
```

## Anatomy of a family directory

| File | Purpose |
|---|---|
| `dNN.py` | one **immutable** release. Opens with a full header docstring; subclasses `StrategyRelease`. |
| `variants.py` | parametrized base for a batch of one-lever variants (e.g. d02–d04), pre-registered and frozen together before running. |
| `backlog.md` | running research log: screen verdicts, kill/survive tables, what was tried and why it failed. Read this first before proposing new work on a family. |
| `feedback/` | dated review notes, e.g. `feedback/2026-06-13-d01-d04/`. |
| `spec.md` | (some families) the family-level design spec. |

> **Research scripts & data don't go here.** A one-off triage/test script for this family goes
> in `lab/experiments/<bucket>/` (e.g. `experiments/multiday/`), its capture data in
> `experiments/_data/` (gitignored), and its preregistration/findings in
> `validation/research_log/`. The family dir holds the durable record — `backlog.md` verdict
> rows that cite those artifacts. See **`../CLAUDE.md` → "Anti-bloat conventions"** (enforced by
> `tests/test_repo_hygiene.py`). The point: log the *evidence*, treat the *script* as disposable.

## The release contract (`base.py`)

Every release subclasses `StrategyRelease` and sets class attributes + implements 3 methods:

```python
class StrategyRelease(ABC):
    release_id: str            # "d01"
    strategy_letter: str       # "d"
    strategy_alias: str        # "post_gap_opening_drive"
    strategy_name: str
    description: str
    # non-default data requirements (runner hydrates these into StrategyContext):
    requires_extended_1m: bool = False
    requires_rth_1m: bool = False
    requires_spy_daily: bool = False
    historical_5m_lookback_days: int = 0
    entry_style: str = "breakout_stop"   # or "pullback_limit"

    def build_candidates(self, context) -> list[Candidate]: ...
    def build_signal(self, context, candidate) -> Signal | None: ...
    def exit_cutoff(self, context) -> datetime: ...
```

The runner **always** loads current-day RTH 5-minute bars + daily context. Release logic must **not** call providers directly — declare data requirements via the class attributes above and the runner hydrates `StrategyContext` before `build_candidates`.

## Adding a release

1. Pick the next number in the family (never edit a shipped release — they are immutable).
2. Write the header docstring: identity, thesis, data requirements, entry rules, exit/risk rules, known limitations, next intended releases. Map each new variant to a documented limitation of the prior release.
3. Pre-register one-lever variants together (in `variants.py`) **before** running, so the screen funnel is honest.
4. Register it (`__init__.py` registry) and verify with `--list`.
5. Run through the screen funnel (see root `CLAUDE.md`), record the verdict in `backlog.md`.
