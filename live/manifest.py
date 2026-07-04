"""Release hash-pinning (DESIGN §2 invariant #4, §11).

A portfolio is bound to a specific *version* of a lab release, not just its
``release_id``. The engine computes a deterministic hash of the release's source
code and refuses to run if it differs from the pinned manifest — so a redeploy of
``trading.lab`` can never silently change live behaviour (parity guarantee).

P0 scope: compute the code hash + build/verify a manifest. The promoted-by /
validation-report fields are recorded when present; lab-lifecycle integration that
populates them lands with P2.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


def release_code_hash(release) -> str:
    """Deterministic SHA-256 over the release class's source + key class attrs.

    Uses the source of the release's module-level class plus the trading-relevant
    class attributes that define its behaviour. Two runs that executed different
    code (or different params) never share a hash.
    """
    cls = type(release)
    try:
        src = inspect.getsource(cls)
    except (OSError, TypeError):
        src = f"{cls.__module__}.{cls.__qualname__}"  # fallback: identity only
    attrs = {
        k: getattr(release, k, None)
        for k in (
            "release_id", "strategy_letter", "strategy_alias",
            "daily_lookback_days", "hold_days", "rebalance_cadence_days",
            "top_n", "use_close_stop", "requires_spy_daily",
            "min_price", "min_dollar_vol", "daily_adjustment",
        )
    }
    # Extra signature inputs a release may declare (e.g. a model pickle).
    try:
        extra = release.signature_inputs()
        attrs["_signature_inputs"] = [(label, hashlib.sha256(b).hexdigest()) for label, b in extra]
    except Exception:
        pass
    payload = src + "\n" + json.dumps(attrs, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReleaseManifest:
    release_id: str
    release_version: str          # e.g. "x03.2026-06-18"
    code_hash: str                # release_code_hash(...)
    strategy_class: str           # "trading.lab.strategies.xsec_momentum.x03.Release"
    captured_at: str              # ISO-8601 UTC
    git_sha: str | None = None
    validation_report_hash: str | None = None
    promoted_at: str | None = None
    promoted_by: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "ReleaseManifest":
        return cls(**json.loads(s))


def capture_manifest(release, *, version: str | None = None, git_sha: str | None = None,
                     promoted_by: str | None = None) -> ReleaseManifest:
    """Snapshot a release's identity + code hash (call at promote/onboard time)."""
    cls = type(release)
    now = datetime.now(timezone.utc).isoformat()
    return ReleaseManifest(
        release_id=release.release_id,
        release_version=version or f"{release.release_id}.{now[:10]}",
        code_hash=release_code_hash(release),
        strategy_class=f"{cls.__module__}.{cls.__qualname__}",
        captured_at=now,
        git_sha=git_sha,
        promoted_by=promoted_by,
    )


class ReleasePinMismatch(RuntimeError):
    """Raised when the imported release code no longer matches the pinned manifest."""


def verify_pinned(release, manifest: ReleaseManifest) -> None:
    """Refuse to proceed if the live code drifted from the pinned manifest."""
    if release.release_id != manifest.release_id:
        raise ReleasePinMismatch(
            f"release_id mismatch: imported {release.release_id!r} vs pinned {manifest.release_id!r}")
    current = release_code_hash(release)
    if current != manifest.code_hash:
        raise ReleasePinMismatch(
            f"{release.release_id} code hash drifted from pinned manifest "
            f"({manifest.release_version}): imported {current} != pinned {manifest.code_hash}. "
            "Re-validate + re-pin in the lab before running live (DESIGN §11).")
