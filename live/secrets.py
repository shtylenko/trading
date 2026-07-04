"""Secret resolution + broker-account identity verification (DESIGN §13, §17).

Per-portfolio broker keys are referenced by a **handle**, never stored in the DB or
logs. The handle resolves to env vars (dev/CI) or a host secret store (prod). Keep all
credential access here so broker code never reads env ad hoc.

Identity verification implements invariant #3 (DESIGN §2): the broker account the keys
actually reach must hash to the portfolio's configured ``account_id_hash``, and the
endpoint must match the mode — so you can never point portfolio A at account B, or a
paper config at a live account.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerCreds:
    api_key: str
    secret_key: str
    mode: str            # paper | live


class SecretError(RuntimeError):
    pass


def account_id_hash(account_id: str) -> str:
    """Stable, non-reversible fingerprint of a broker account number (safe to store/log)."""
    return "acct:" + hashlib.sha256(account_id.encode()).hexdigest()[:24]


def load_env_file(path) -> dict[str, str]:
    """Parse a shell-style env file (``export KEY="val"`` / ``KEY=val``) into a dict.

    Dev convenience so a long-running web process can pick up broker creds from the
    gitignored ``_state/<env>/alpaca.env`` without the operator having to export them
    into the server's shell. Missing file → empty dict. Quotes/comments handled.
    """
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return {}
    out: dict[str, str] = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def ensure_broker_env(state_dir, *, keys=("ALPACA_API_KEY_ID", "ALPACA_SECRET_KEY")) -> bool:
    """If broker creds aren't already in the environment, load them from
    ``<state_dir>/alpaca.env``. Returns True if all ``keys`` are present afterward."""
    import os
    if all(os.getenv(k) for k in keys):
        return True
    filevals = load_env_file(state_dir / "alpaca.env")
    for k in keys:
        if not os.getenv(k) and filevals.get(k):
            os.environ[k] = filevals[k]
    return all(os.getenv(k) for k in keys)


def resolve_creds(handle: str, mode: str) -> BrokerCreds:
    """Resolve a portfolio's broker creds from its handle.

    Convention: env vars ``<HANDLE>_KEY`` / ``<HANDLE>_SECRET`` (handle upper-cased,
    non-alnum → ``_``). Prod swaps this for a real secret store without touching callers.
    """
    h = "".join(c if c.isalnum() else "_" for c in handle.upper())
    key = os.getenv(f"{h}_KEY", "")
    sec = os.getenv(f"{h}_SECRET", "")
    if not key or not sec:
        raise SecretError(f"no creds for handle {handle!r} (expected env {h}_KEY/{h}_SECRET)")
    return BrokerCreds(api_key=key, secret_key=sec, mode=mode)


class IdentityMismatch(RuntimeError):
    """Raised when a broker account doesn't match the portfolio's configured identity."""


def verify_account_identity(broker_account_id: str, expected_hash: str | None) -> None:
    """Confirm the live broker account is the one this portfolio was onboarded with.

    If ``expected_hash`` is None (not yet bound — e.g. first paper run), this is a no-op;
    the caller binds it on first successful connect. Once bound, a mismatch hard-fails.
    """
    if expected_hash is None:
        return
    actual = account_id_hash(broker_account_id)
    if actual != expected_hash:
        raise IdentityMismatch(
            f"broker account {actual} != portfolio-configured {expected_hash} — "
            "refusing to trade the wrong account (DESIGN §2 invariant #3)")
