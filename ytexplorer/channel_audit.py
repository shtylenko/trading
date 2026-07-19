"""Conservative, explainable channel-topic audit.

This is intentionally a triage classifier.  It decides whether a channel is a
useful recurring *discovery source*, never whether the channel or its trading
claims are credible.
"""
from __future__ import annotations

from typing import Any


TRADING_TERMS = {
    "trading", "trader", "trade", "market", "stock", "stocks", "equity", "equities",
    "options", "futures", "forex", "crypto", "bitcoin", "technical analysis", "price action",
    "vwap", "breakout", "momentum", "swing", "investing", "portfolio", "chart",
}
STRATEGY_TERMS = {
    "entry", "exit", "stop", "risk", "setup", "strategy", "indicator", "position sizing",
    "backtest", "breakout", "pullback", "support", "resistance", "vwap", "rvol", "volume",
}


def audit_samples(videos: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a content mix based only on supplied titles/descriptions/transcripts."""
    if not videos:
        return {"sample_size": 0, "trading_ratio": 0.0, "strategy_ratio": 0.0, "matches": []}
    matches: list[dict[str, Any]] = []
    trading_count = strategy_count = 0
    for video in videos:
        text = " ".join(str(video.get(k) or "") for k in ("title", "description", "transcript_text")).lower()
        trading = sorted(term for term in TRADING_TERMS if term in text)
        strategy = sorted(term for term in STRATEGY_TERMS if term in text)
        trading_count += bool(trading)
        strategy_count += bool(strategy)
        matches.append({"video_id": video.get("video_id"), "trading_terms": trading, "strategy_terms": strategy})
    n = len(videos)
    return {
        "sample_size": n,
        "trading_ratio": trading_count / n,
        "strategy_ratio": strategy_count / n,
        "matches": matches,
    }


def recommend_status(audit: dict[str, Any], *, min_sample: int = 12, min_trading_ratio: float = 0.70,
                     min_strategy_ratio: float = 0.40) -> tuple[str, str]:
    """Recommend a source state.  Candidate is safe whenever evidence is thin."""
    n = int(audit["sample_size"])
    trading = float(audit["trading_ratio"])
    strategy = float(audit["strategy_ratio"])
    if n < min_sample:
        return "candidate", f"needs {min_sample - n} more sampled videos before automatic promotion"
    if trading >= min_trading_ratio and strategy >= min_strategy_ratio:
        return "approved", f"content audit passed: {trading:.0%} trading, {strategy:.0%} strategy/process"
    if trading < 0.25:
        return "rejected", f"content audit failed: only {trading:.0%} trading content"
    return "candidate", f"mixed content: {trading:.0%} trading, {strategy:.0%} strategy/process"
