"""Append-only capture of contemporaneous Warrior scanner inputs.

Historical Warrior rows use a current float snapshot and are intentionally
non-promotable.  A forward-shadow cohort starts here: each candidate records
the scanner inputs and the exact float retrieval payload at scan time, before
any later replay or outcome analysis is possible.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ...fsutils import file_lock


SCHEMA_VERSION = 1


class ForwardShadowLedger:
    """Durable JSONL ledger for a frozen forward-shadow scanner cohort."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()

    def record_candidate(
        self,
        *,
        scan_id: str,
        candidate: Any,
        float_snapshot: Mapping[str, Any],
        float_gate_passed: bool,
        config: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Append one scanner candidate with immutable input provenance.

        ``captured_at`` is intentionally local wall-clock evidence, while the
        candidate date is the market date.  The record hash makes accidental
        mutation or duplicate input snapshots visible during cohort assembly.
        """
        record = {
            "schema_version": SCHEMA_VERSION,
            "kind": "warrior_forward_shadow_candidate",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "scan_id": scan_id,
            "ticker": candidate.ticker,
            "market_date": candidate.day.isoformat(),
            "scanner_inputs": {
                "open_px": candidate.open_px,
                "prior_close": candidate.prior_close,
                "gap_pct": candidate.gap_pct,
                "prior_day_volume_ratio": candidate.prior_day_volume_ratio,
                "prior_day_volume_baseline": candidate.avg_vol,
                "prior_day_volume": candidate.day_volume,
                "float_max": config.get("float_max"),
                "rvol_lookback": config.get("rvol_lookback"),
            },
            "float_provenance": dict(float_snapshot),
            "float_gate_passed": bool(float_gate_passed),
            "research_tier": "forward_shadow_pending_outcomes",
        }
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        record["record_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        with file_lock(lock_path):
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        return record
