"""
Load and serve named-screener configuration.

Only configured, enabled screeners may contribute tickers to daily sessions.
The extension arms when the user has My Screeners open AND has selected a
matching named screener (e.g. Gap'n'Go).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).parent / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "screeners.json"

_DEFAULT = {
    "require_my_screeners": True,
    "screeners": [
        {
            "key": "gap-n-go",
            "name": "Gap'n'Go",
            "name_match": ["gap'n'go", "gap n go", "gapngo", "gap-n-go"],
            "enabled": True,
            "webull_screener_id": None,
            "max_rows_per_push": 50,
            "max_session_tickers": 50,
        }
    ],
}

DEFAULT_MAX_ROWS_PER_PUSH = 50
DEFAULT_MAX_SESSION_TICKERS = 50


def _normalize_match(s: str) -> str:
    """Lowercase + strip punctuation for fuzzy name compare."""
    s = (s or "").lower().strip()
    s = s.replace("'", "").replace("'", "").replace("'", "")
    s = re.sub(r"[\s\-_]+", "", s)
    return s


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        return json.loads(json.dumps(_DEFAULT))
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return json.loads(json.dumps(_DEFAULT))
        if "screeners" not in data or not isinstance(data["screeners"], list):
            data["screeners"] = _DEFAULT["screeners"]
        if "require_my_screeners" not in data:
            data["require_my_screeners"] = True
        return data
    except Exception:
        return json.loads(json.dumps(_DEFAULT))


def enabled_screeners(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = config if config is not None else load_config()
    out = []
    for s in cfg.get("screeners") or []:
        if not isinstance(s, dict):
            continue
        if not s.get("enabled", True):
            continue
        if not s.get("key") or not s.get("name"):
            continue
        out.append(s)
    return out


def screener_by_key(key: str, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not key:
        return None
    for s in enabled_screeners(config):
        if s.get("key") == key:
            return s
    return None


def max_rows_per_push(key: str, config: dict[str, Any] | None = None) -> int:
    s = screener_by_key(key, config)
    if not s:
        return DEFAULT_MAX_ROWS_PER_PUSH
    try:
        return int(s.get("max_rows_per_push") or DEFAULT_MAX_ROWS_PER_PUSH)
    except (TypeError, ValueError):
        return DEFAULT_MAX_ROWS_PER_PUSH


def max_session_tickers(key: str, config: dict[str, Any] | None = None) -> int:
    s = screener_by_key(key, config)
    if not s:
        return DEFAULT_MAX_SESSION_TICKERS
    try:
        return int(s.get("max_session_tickers") or DEFAULT_MAX_SESSION_TICKERS)
    except (TypeError, ValueError):
        return DEFAULT_MAX_SESSION_TICKERS


def public_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Payload for GET /config/screeners (extension + tools)."""
    cfg = config if config is not None else load_config()
    screeners = []
    for s in enabled_screeners(cfg):
        matches = list(s.get("name_match") or [])
        # Always include canonical name as a match
        if s["name"] not in matches:
            matches = [s["name"], *matches]
        screeners.append({
            "key": s["key"],
            "name": s["name"],
            "name_match": matches,
            "name_match_normalized": [_normalize_match(m) for m in matches],
            "webull_screener_id": s.get("webull_screener_id"),
            "max_rows_per_push": max_rows_per_push(s["key"], cfg),
            "max_session_tickers": max_session_tickers(s["key"], cfg),
            "enabled": True,
        })
    return {
        "ok": True,
        "require_my_screeners": bool(cfg.get("require_my_screeners", True)),
        "screeners": screeners,
    }


def match_screener_name(visible_name: str, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Return configured screener if visible_name matches an enabled entry."""
    norm = _normalize_match(visible_name)
    if not norm:
        return None
    for s in enabled_screeners(config):
        candidates = [s["name"], *(s.get("name_match") or [])]
        for c in candidates:
            if _normalize_match(c) == norm:
                return {
                    "key": s["key"],
                    "name": s["name"],
                    "webull_screener_id": s.get("webull_screener_id"),
                }
            # substring either way for small variants
            cn = _normalize_match(c)
            if cn and (cn in norm or norm in cn) and min(len(cn), len(norm)) >= 5:
                return {
                    "key": s["key"],
                    "name": s["name"],
                    "webull_screener_id": s.get("webull_screener_id"),
                }
    return None


def match_screener_id(webull_id: str | None, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not webull_id:
        return None
    wid = str(webull_id).strip()
    for s in enabled_screeners(config):
        bound = s.get("webull_screener_id")
        if bound is not None and str(bound) == wid:
            return {
                "key": s["key"],
                "name": s["name"],
                "webull_screener_id": bound,
            }
    return None
