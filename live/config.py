"""Live-execution configuration — two orthogonal axes (DESIGN §18).

  - ENV  (`TRADING_ENV` = dev|testing|prod): WHERE we run → paths, ports, DB, logs.
  - MODE (paper|live, per portfolio): WHICH broker account a portfolio trades.

The hard link: **real money only in prod**. ``live`` mode is refused unless
``TRADING_ENV=prod`` — dev/testing are paper-locked here, before any order path.
Paper-first, dry-run-by-default everywhere.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

VALID_ENVS = ("dev", "testing", "prod")
VALID_MODES = ("paper", "live")

# Root for all live state (DB, logs). Override per env via TRADING_LIVE_STATE_DIR.
_PKG_DIR = Path(__file__).resolve().parent


def _env() -> str:
    env = os.getenv("TRADING_ENV", "dev").lower()
    if env not in VALID_ENVS:
        raise ValueError(f"TRADING_ENV={env!r} invalid; expected one of {VALID_ENVS}")
    return env


@dataclass(frozen=True)
class EnvConfig:
    """Resolved environment bundle. One selector (TRADING_ENV) drives everything."""

    env: str
    state_dir: Path          # live DB + kill-switch file live here
    log_dir: Path            # daily JSONL log directories (DESIGN §14)
    db_path: Path            # SQLite live ledger (P0/P1; Postgres before serious live)
    web_host: str
    web_port: int
    web_token: str = ""      # control-plane auth token (empty in dev; required to mutate)

    @property
    def live_allowed(self) -> bool:
        """Real-money (live mode) is permitted ONLY in prod."""
        return self.env == "prod"

    def require_mode_allowed(self, mode: str) -> None:
        """Raise if a portfolio mode is not allowed in this environment."""
        if mode not in VALID_MODES:
            raise ValueError(f"mode={mode!r} invalid; expected {VALID_MODES}")
        if mode == "live" and not self.live_allowed:
            raise PermissionError(
                f"live mode is forbidden in TRADING_ENV={self.env!r}; "
                "real money runs only in prod (DESIGN §18)"
            )


def load_env_config() -> EnvConfig:
    env = _env()
    state_dir = Path(os.getenv("TRADING_LIVE_STATE_DIR", str(_PKG_DIR / "_state" / env)))
    log_dir = Path(os.getenv("TRADING_LIVE_LOG_DIR", str(_PKG_DIR / "logs" / env)))
    # Per-env web port so testing + prod can coexist on one droplet (DESIGN §18).
    default_port = {"dev": 8800, "testing": 8810, "prod": 8820}[env]
    return EnvConfig(
        env=env,
        state_dir=state_dir,
        log_dir=log_dir,
        db_path=Path(os.getenv("TRADING_LIVE_DB", str(state_dir / "live.db"))),
        web_host=os.getenv("TRADING_LIVE_WEB_HOST", "127.0.0.1"),
        web_port=int(os.getenv("TRADING_LIVE_WEB_PORT", str(default_port))),
        web_token=os.getenv("TRADING_LIVE_WEB_TOKEN", ""),
    )


# ── Per-run / per-portfolio knobs (sizing, order style). Paper-first. ──
@dataclass(frozen=True)
class LiveConfig:
    """One immutable config per run. Defaults are conservative."""

    release_id: str
    dry_run: bool = True               # default: build the plan, submit nothing
    mode: str = "paper"                # paper unless deliberately set live (and env=prod)
    cash_reserve_pct: float = 0.02     # dry powder for fills/fees
    capital: float = 0.0               # portfolio's allocated capital; 0 → use broker equity
    max_names: int | None = None       # None → use release.top_n unchanged
    fractional: bool = False
    universe_name: str = "live_liquid"
    entry_order_style: str = "market_on_close"

    def __post_init__(self) -> None:
        if self.mode not in VALID_MODES:
            raise ValueError(f"mode={self.mode!r} invalid; expected {VALID_MODES}")
