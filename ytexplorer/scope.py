"""Explicit research-scope policy for long-only equity idea discovery."""
from __future__ import annotations

import re
from typing import Any


# These are deliberately focused-topic patterns rather than a generic ``short``
# substring, which would wrongly reject innocuous phrases such as "short-term".
_OUT_OF_SCOPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bfutures?\b", re.IGNORECASE), "futures"),
    (re.compile(r"\boptions?\b", re.IGNORECASE), "options"),
    (re.compile(r"\bshort(?:ing|\s+sell(?:ing)?|\s+(?:position|trade|strategy)s?)\b", re.IGNORECASE), "shorting"),
    (re.compile(r"\blong\s*(?:/|&|and|vs\.?)[\s-]*short\b", re.IGNORECASE), "long-short"),
    (re.compile(r"\bbearish\b", re.IGNORECASE), "bearish-trading"),
)


def long_only_scope(video: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return whether title, description, and channel fit the long-only mandate."""
    text = f"{video.get('title', '')}\n{video.get('description', '')}\n{video.get('channel', '')}\n{video.get('channel_title', '')}"
    reasons = [label for pattern, label in _OUT_OF_SCOPE_PATTERNS if pattern.search(text)]
    return not reasons, reasons
