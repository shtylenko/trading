"""Narrow adapter around the separate ``ytmcp`` project."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from .store import PACKAGE_DIR


def _load_api():
    root = Path(os.getenv("YTMCP_DIR", PACKAGE_DIR.parent.parent / "ytmcp"))
    if not (root / "ytapi.py").exists():
        raise RuntimeError(f"ytmcp not found at {root}; set YTMCP_DIR to its directory")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from ytapi import YouTubeAPI  # type: ignore
    cache_dir = Path(os.getenv("YTEXPLORER_CACHE_DIR", PACKAGE_DIR / "data" / "transcript_cache"))
    return YouTubeAPI(cache_dir=str(cache_dir))


def search(query: str, *, max_results: int = 20, upload_date: str | None = None) -> list[dict[str, Any]]:
    response = _load_api().search_videos(query, max_results=max_results, upload_date=upload_date)
    if "error" in response:
        raise RuntimeError(response["error"])
    return list(response.get("data", []))


def channel_videos(channel_id: str, *, sort_by: str = "newest") -> list[dict[str, Any]]:
    response = _load_api().list_channel_videos(channel_id, sort_by=sort_by)
    if "error" in response:
        raise RuntimeError(response["error"])
    return list(response.get("videos", []))


def transcript(video_id: str) -> dict[str, Any]:
    return _load_api().get_transcript(video_id)
