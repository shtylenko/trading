"""Advisory clustering for the existing evidence-backed research queue.

This step is intentionally separate from extraction: it may group or flag
candidates, but it cannot create an experiment or alter candidate state.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from typing import Any


SYNTHESIS_VERSION = "candidate-family-v1"
FAMILIES = {
    "swing_breakout_volume",
    "vwap_intraday",
    "opening_range_intraday",
    "ema_ma_trend",
    "momentum_continuation",
    "pullback_reversion",
    "liquidity_smc",
    "indicator_composite",
    "event_news",
    "quant_model",
    "risk_exit",
    "other",
}
RECOMMENDATIONS = {"retain", "merge", "needs-detail", "reject-scope"}


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_synthesis_prompt(candidates: list[dict[str, Any]]) -> str:
    records = [
        {
            "candidate_id": item["candidate_id"],
            "title": item["title"][:180],
            "summary": item["summary"][:500],
            "trigger": (item.get("trigger_rule") or "")[:300],
            "invalidation": (item.get("invalidation_rule") or "")[:300],
            "status": item["status"],
        }
        for item in candidates
    ]
    return f"""You are organizing a long-only equity research queue. These are already source-backed
hypotheses, not trade recommendations. Do not invent rules or assess profitability.

For each candidate assign exactly one family:
{", ".join(sorted(FAMILIES))}

Then give an advisory recommendation:
- retain: distinct, plausible research family member;
- merge: materially overlaps another supplied candidate; say which candidate ID in rationale;
- needs-detail: key entry/exit/invalidation information is missing;
- reject-scope: focused on options, futures, shorting, or long/short strategies.

Return JSON only:
{{"decisions":[{{"candidate_id":"...","family":"...","recommendation":"...","rationale":"brief evidence-grounded reason"}}]}}
Return one decision for every supplied ID. Do not change candidate status.

Candidates:
{json.dumps(records, ensure_ascii=False)}"""


def parse_synthesis_response(
    raw: str,
    expected_ids: set[str],
    *,
    allow_partial: bool = False,
) -> dict[str, dict[str, str]] | tuple[dict[str, dict[str, str]], list[str]]:
    try:
        cleaned = raw.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            cleaned = fenced.group(1)
        start = cleaned.find("{")
        if start < 0:
            raise json.JSONDecodeError("No JSON object found", cleaned, 0)
        value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"candidate synthesizer returned invalid JSON: {exc.msg}") from exc
    decisions = value.get("decisions") if isinstance(value, dict) else None
    if not isinstance(decisions, list):
        raise ValueError("candidate synthesizer result needs a decisions list")
    parsed: dict[str, dict[str, str]] = {}
    diagnostics: list[str] = []
    for position, item in enumerate(decisions, start=1):
        if not isinstance(item, dict):
            diagnostics.append(f"decision {position}: not an object")
            continue
        candidate_id = item.get("candidate_id")
        family = item.get("family")
        recommendation = item.get("recommendation")
        rationale = item.get("rationale")
        if candidate_id not in expected_ids:
            diagnostics.append(f"decision {position}: unknown candidate_id")
        elif candidate_id in parsed:
            diagnostics.append(f"decision {position}: duplicate candidate_id {candidate_id}")
        elif family not in FAMILIES or recommendation not in RECOMMENDATIONS:
            diagnostics.append(f"decision {position}: invalid family or recommendation")
        elif not isinstance(rationale, str) or not rationale.strip():
            diagnostics.append(f"decision {position}: missing rationale")
        else:
            parsed[candidate_id] = {
                "family": family,
                "recommendation": recommendation,
                "rationale": rationale.strip()[:600],
            }
    missing = expected_ids - set(parsed)
    if missing:
        diagnostics.append(f"missing decisions for {len(missing)} candidate(s)")
    if not allow_partial and diagnostics:
        raise ValueError("candidate synthesizer did not decide every supplied candidate")
    if allow_partial:
        if not parsed:
            raise ValueError("candidate synthesizer returned no usable decisions")
        return parsed, diagnostics
    return parsed


class CandidateSynthesizer:
    def __init__(self, store, *, runner=subprocess.run):
        self.store = store
        self.runner = runner

    def synthesize(
        self,
        candidates: list[dict[str, Any]],
        *,
        model: str | None = None,
        timeout: int = 90,
    ) -> tuple[dict[str, dict[str, str]], list[str]]:
        if not candidates:
            return {}, []
        prompt = build_synthesis_prompt(candidates)
        command = ["hermes", "-z", prompt, "--safe-mode"]
        if model:
            command.extend(["-m", model])
        proc = self.runner(command, text=True, capture_output=True, timeout=timeout, check=False)
        if proc.returncode:
            raise RuntimeError((proc.stderr or proc.stdout or "candidate synthesizer failed")[:1000])
        decisions, diagnostics = parse_synthesis_response(
            proc.stdout or "", {item["candidate_id"] for item in candidates}, allow_partial=True,
        )
        self.store.record_candidate_syntheses(
            decisions,
            model=model,
            prompt_hash=_digest(prompt),
            synthesis_version=SYNTHESIS_VERSION,
        )
        return decisions, diagnostics
