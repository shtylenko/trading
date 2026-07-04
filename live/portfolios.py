"""Portfolio registry (DESIGN §3, §5.1) — onboard / list / get / retire.

A portfolio binds one promoted lab release to one broker account + capital + policies +
schedule + mode. The DB ``portfolios`` table is the source of truth; this module is the
typed API over it. Onboarding pins the release manifest (so live can verify the code
hasn't drifted) and records the broker secret handle + expected account-identity hash.

Multi-portfolio isolation is by construction: each portfolio carries its own secret
handle and account-identity hash, so two portfolios never share creds or an account.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from trading.live import ledger
from trading.live.config import EnvConfig, load_env_config
from trading.live.manifest import ReleaseManifest, capture_manifest
from trading.lab.strategies import get_release_class

VALID_STATUS = ("active", "paused", "retiring", "retired")


@dataclass
class PortfolioConfig:
    portfolio_id: str
    release_id: str
    mode: str = "paper"
    status: str = "active"
    universe: str = "liquid_pit"
    capital: float = 0.0
    fractional: bool = False
    secret_handle: str | None = None
    account_id_hash: str | None = None
    manifest: dict | None = None
    approval_policy: dict = field(default_factory=dict)
    risk_policy: dict = field(default_factory=dict)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def onboard(portfolio_id: str, release_id: str, *, mode: str = "paper",
            universe: str = "liquid_pit", capital: float = 0.0, fractional: bool = False,
            secret_handle: str | None = None, account_id_hash: str | None = None,
            approval_policy: dict | None = None, risk_policy: dict | None = None,
            actor: str = "user", env: EnvConfig | None = None) -> PortfolioConfig:
    """Register a new portfolio. Refuses live mode outside prod; pins the release manifest.

    Only a promoted release should be onboarded; lab-lifecycle enforcement is wired in
    P2's follow-up. Here we at least pin the imported release's code hash so drift is
    detectable at run time.
    """
    env = env or load_env_config()
    env.require_mode_allowed(mode)
    if mode not in ("paper", "live"):
        raise ValueError(f"bad mode {mode!r}")
    ledger.init_db(env)
    if get(portfolio_id, env=env) is not None:
        raise ValueError(f"portfolio {portfolio_id!r} already exists")

    release = get_release_class(release_id)()       # raises if unknown release
    manifest: ReleaseManifest = capture_manifest(release)
    cfg = PortfolioConfig(
        portfolio_id=portfolio_id, release_id=release_id, mode=mode, status="active",
        universe=universe, capital=capital, fractional=fractional, secret_handle=secret_handle,
        account_id_hash=account_id_hash, manifest=json.loads(manifest.to_json()),
        approval_policy=approval_policy or {}, risk_policy=risk_policy or {})

    with ledger.connect(env) as conn:
        conn.execute(
            "INSERT INTO portfolios (portfolio_id, release_id, mode, status, code_hash, universe, "
            "capital, fractional, secret_handle, account_id_hash, manifest, approval_policy, "
            "risk_policy, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [portfolio_id, release_id, mode, "active", manifest.code_hash, universe, capital,
             int(fractional), secret_handle, account_id_hash, manifest.to_json(),
             json.dumps(cfg.approval_policy), json.dumps(cfg.risk_policy), _now()])
    ledger.audit("portfolio.onboard", actor=actor,
                 detail=f"{portfolio_id} release={release_id} mode={mode}", env=env)
    return cfg


def _row_to_cfg(r) -> PortfolioConfig:
    return PortfolioConfig(
        portfolio_id=r["portfolio_id"], release_id=r["release_id"], mode=r["mode"],
        status=r["status"], universe=r["universe"] or "liquid_pit", capital=r["capital"] or 0.0,
        fractional=bool(r["fractional"]) if "fractional" in r.keys() else False,
        secret_handle=r["secret_handle"], account_id_hash=r["account_id_hash"],
        manifest=json.loads(r["manifest"]) if r["manifest"] else None,
        approval_policy=json.loads(r["approval_policy"]) if r["approval_policy"] else {},
        risk_policy=json.loads(r["risk_policy"]) if r["risk_policy"] else {})


def get(portfolio_id: str, env: EnvConfig | None = None) -> PortfolioConfig | None:
    env = env or load_env_config()
    ledger.init_db(env)
    with ledger.connect(env) as conn:
        r = conn.execute("SELECT * FROM portfolios WHERE portfolio_id=?", [portfolio_id]).fetchone()
        return _row_to_cfg(r) if r else None


def list_portfolios(env: EnvConfig | None = None, *, include_retired: bool = False
                    ) -> list[PortfolioConfig]:
    env = env or load_env_config()
    ledger.init_db(env)
    with ledger.connect(env) as conn:
        q = "SELECT * FROM portfolios"
        if not include_retired:
            q += " WHERE status != 'retired'"
        return [_row_to_cfg(r) for r in conn.execute(q + " ORDER BY portfolio_id").fetchall()]


def set_status(portfolio_id: str, status: str, *, actor: str = "user",
               env: EnvConfig | None = None) -> None:
    if status not in VALID_STATUS:
        raise ValueError(f"bad status {status!r}")
    env = env or load_env_config()
    with ledger.connect(env) as conn:
        cur = conn.execute("UPDATE portfolios SET status=? WHERE portfolio_id=?",
                           [status, portfolio_id])
        if cur.rowcount == 0:
            raise ValueError(f"no portfolio {portfolio_id!r}")
    ledger.audit("portfolio.status", actor=actor, detail=f"{portfolio_id} -> {status}", env=env)


def bind_account(portfolio_id: str, account_id_hash: str, *, actor: str = "system",
                 env: EnvConfig | None = None) -> None:
    """Bind the broker account identity on first connect (DESIGN §13)."""
    env = env or load_env_config()
    with ledger.connect(env) as conn:
        conn.execute("UPDATE portfolios SET account_id_hash=? WHERE portfolio_id=?",
                     [account_id_hash, portfolio_id])
    ledger.audit("portfolio.bind_account", actor=actor,
                 detail=f"{portfolio_id} {account_id_hash}", env=env)
