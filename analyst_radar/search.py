"""
YouTube search + transcript fetch for analyst interviews (spec §5.4).

ALL YouTube I/O goes through the existing ytmcp wrapper
(/Users/shtylenko/Projects/ytmcp, ``ytapi.YouTubeAPI``). No yt-dlp. Requires
RAPIDAPI_KEY in the environment.

This is mechanical plumbing only (spec §5): search, dedup by youtube_id, fetch
transcripts, store interviews. No content analysis — deciding whether a video
truly *is* the analyst's market interview is LLM/skill work, not done here.
"""
import os
import sys
from typing import Optional

# ytmcp lives under a different root than the `trading` monorepo, so it is not
# on the import path. Add it explicitly. Override with YTMCP_DIR if relocated.
YTMCP_DIR = os.environ.get("YTMCP_DIR", "/Users/shtylenko/Projects/ytmcp")
if YTMCP_DIR not in sys.path:
    sys.path.insert(0, YTMCP_DIR)

from ytapi import YouTubeAPI  # noqa: E402  (path shim must run first)

from .db import get_db, _now

# Default per-analyst search scope (spec §5.4).
DEFAULT_MAX_RESULTS = 40
DEFAULT_UPLOAD_DATE = "week"


def _api() -> YouTubeAPI:
    """Construct the ytapi client (reads RAPIDAPI_KEY from env)."""
    return YouTubeAPI()


def search_analyst_interviews(
    analyst_name: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    upload_date: str = DEFAULT_UPLOAD_DATE,
    api: Optional[YouTubeAPI] = None,
) -> list[dict]:
    """Search YouTube for recent interviews featuring the analyst.

    Returns a list of candidate dicts:
        {youtube_url, youtube_id, title, channel_name, published_date}
    The query is mechanical; relevance filtering is the LLM's job downstream.
    """
    api = api or _api()
    query = f'"{analyst_name}" stock market forecast'
    resp = api.search_videos(query, max_results=max_results, upload_date=upload_date)
    if "error" in resp:
        raise RuntimeError(f"ytapi search failed for {analyst_name!r}: {resp['error']}")

    out = []
    for v in resp.get("data", []):
        vid = v.get("video_id")
        if not vid:
            continue
        out.append({
            "youtube_url": v.get("url") or f"https://www.youtube.com/watch?v={vid}",
            "youtube_id": vid,
            "title": v.get("title", ""),
            "channel_name": v.get("channel", ""),
            # Prefer the YYYYMMDD field; fall back to the human "x days ago" text.
            "published_date": v.get("published_date_YYYYMMDD") or v.get("published_date", ""),
        })
    return out


def fetch_transcript(youtube_id: str, api: Optional[YouTubeAPI] = None) -> Optional[str]:
    """Fetch transcript text for a video id, or None if unavailable (spec §5.3).

    ytapi caches transcripts on disk, so back-fills are cheap. A missing
    transcript is the common case, not an error to raise on.
    """
    api = api or _api()
    result = api.get_transcript(youtube_id)
    if "error" in result:
        return None
    text = (result.get("raw_text") or "").strip()
    return text or None


def store_interview(conn, candidate: dict, transcript: Optional[str]) -> bool:
    """Insert a new interview; dedup on youtube_id (spec §5.1).

    Returns True if a new row was inserted, False if the video was already known.
    Idempotent: re-running never duplicates (INSERT OR IGNORE on UNIQUE youtube_id).
    """
    now = _now()
    cur = conn.execute(
        """INSERT OR IGNORE INTO interviews
               (youtube_url, youtube_id, title, channel_name, published_date,
                transcript_text, fetched_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            candidate["youtube_url"],
            candidate["youtube_id"],
            candidate["title"],
            candidate["channel_name"],
            candidate["published_date"],
            transcript,
            now if transcript is not None else None,
            now,
        ),
    )
    conn.commit()
    return cur.rowcount > 0


def backfill_transcript(conn, youtube_id: str, api: Optional[YouTubeAPI] = None) -> bool:
    """Try to fill a previously-missing transcript for a stored interview.

    Returns True if a transcript was fetched and written, False otherwise.
    """
    transcript = fetch_transcript(youtube_id, api=api)
    if transcript is None:
        return False
    conn.execute(
        "UPDATE interviews SET transcript_text = ?, fetched_at = ? WHERE youtube_id = ?",
        (transcript, _now(), youtube_id),
    )
    conn.commit()
    return True


def scan_channel_feed(
    conn,
    channel_name: str,
    channel_id: str,
    max_results: int = 40,
    api: Optional[YouTubeAPI] = None,
) -> int:
    """List recent videos from a tracked YouTube channel and store any featuring tracked analysts.

    TWO MODES:
    1. Tracked analyst match → store interview immediately.
    2. Unrecognised guest on a financial media channel → queue as candidate,
       store interview so it's ready when approved.

    Returns the number of new interviews stored.
    """
    api = api or _api()
    result = api.list_channel_videos(channel_id, sort_by="newest")
    videos = result.get("videos", [])
    if not videos:
        return 0

    # Load tracked + candidate names to avoid dupes
    tracked = set(r[0].lower() for r in conn.execute("SELECT name FROM analysts WHERE is_active=1").fetchall())
    candidate_names = set(r[0].lower() for r in conn.execute("SELECT name FROM analyst_candidates WHERE status='pending'").fetchall())

    # Build (first, last, full_name) for title matching
    analyst_matchers = []
    for name in tracked:
        parts = name.strip().split()
        if len(parts) >= 2:
            analyst_matchers.append((parts[0].lower(), parts[-1].lower(), name))

    # Known financial media channels — only these get candidate queuing
    financial_channels = {
        "cnbc television", "bloomberg television", "bloomberg podcasts",
        "bloomberg originals", "fox business", "fox business clips",
        "yahoo finance", "schwab network", "charles schwab",
        "kitco news", "the compound", "david lin", "real vision",
        "wealthion", "investor's business daily", "steve eisman",
        "odds on open", "verified investing", "investor center",
        "the motley fool", "zacks investment research", "marketwatch",
        "schiffgold", "the stock market show",
    }

    is_financial = channel_name.lower() in financial_channels

    candidate_names_to_check = []
    new_count = 0

    for v in videos[:max_results]:
        title = v.get("title", "")
        title_lower = title.lower()
        published = v.get("published_date", "")
        youtube_id = v.get("video_id", "")
        if not youtube_id:
            continue

        # Skip non-finance content early (gaming, sports, etc) — only if NOT a known financial channel
        if not is_financial:
            skip_kw = ["drama", "movie", "anime", "k-pop", "bts", "weverse",
                       "gaming", "vod", "sport", "football", "basketball",
                       "audiobook", "comedy", "school board", "city council",
                       "commission", "planning", "public forum"]
            if any(kw in title_lower for kw in skip_kw):
                continue

        # Skip very long titles (likely full-show recordings, not clips)
        if len(title) > 120:
            continue

        # Check if already in DB
        existing = conn.execute(
            "SELECT id FROM interviews WHERE youtube_id = ?", (youtube_id,)
        ).fetchone()
        if existing:
            continue

        # Try to match a tracked analyst
        matched_analyst = None
        for first, last, full_name in analyst_matchers:
            if first in title_lower and last in title_lower:
                matched_analyst = full_name
                break

        # For financial channels, also try to extract guest name for candidate queuing
        candidate_name = None
        if is_financial and not matched_analyst:
            candidate_name = _extract_guest_name(title)
            if candidate_name and candidate_name.lower() in tracked | candidate_names:
                candidate_name = None  # already known

        # Only fetch transcript if there's something to do with this video
        if not matched_analyst and not candidate_name:
            continue

        transcript = fetch_transcript(youtube_id, api=api)
        candidate = {
            "youtube_url": v.get("url", f"https://www.youtube.com/watch?v={youtube_id}"),
            "youtube_id": youtube_id,
            "title": title,
            "channel_name": channel_name,
            "published_date": published,
        }

        if matched_analyst:
            # Mode 1: tracked analyst found → store immediately
            if store_interview(conn, candidate, transcript):
                new_count += 1
                print(f"  + [{youtube_id[:8]}] {matched_analyst} → {title[:60]}")
        elif candidate_name and transcript:
            # Mode 2: financial media channel, not tracked → queue as candidate
            from .db import store_candidate
            store_candidate(conn, name=candidate_name, firm=f"(from {channel_name})",
                            role="Market Analyst / Strategist",
                            bio=f"Discovered via {channel_name} video: {title}",
                            source_youtube_url=candidate["youtube_url"],
                            source_interview_title=title)
            print(f"  ? [{youtube_id[:8]}] CANDIDATE {candidate_name} → {title[:60]}")
            candidate_names.add(candidate_name.lower())
            if store_interview(conn, candidate, transcript):
                new_count += 1

    # Update last_scanned_at
    conn.execute(
        "UPDATE channels SET last_scanned_at = ? WHERE youtube_channel_id = ?",
        (_now(), channel_id),
    )
    conn.commit()
    return new_count


def _extract_guest_name(title: str) -> Optional[str]:
    """Try to extract a credible market analyst name from a financial media video title.

    Returns the full name (e.g. 'Meghan Shue') or None if no clear match.
    """
    import re

    # Patterns to try, in priority order
    patterns = [
        # "Org's Name says/predicts/warns/expects/sees..." — most reliable
        r"'s\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+(?:says|predicts|warns|expects|sees|forecasts)",
        # "Name: topic" — only if name has a recognizable first+last name structure
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)):\s",
    ]

    # Skip-first-word list: show segments, topics, currencies, sports, etc.
    skip_first = {
        "Squawk", "Bloomberg", "Special", "Options", "Tech", "Week",
        "Morning", "Evening", "Breaking", "Watch", "Today", "Daily",
        "Weekly", "Monthly", "Latest", "Update", "Markets", "Stocks",
        "Yen", "Dollar", "Euro", "Pound", "Gold", "Silver", "Oil", "Bond",
        "Asia", "Europe", "US", "China", "Japan", "India", "Global",
        "Pro", "Dr", "Prof", "Sir", "Lady", "Lord", "Bitcoin", "Crypto",
        "Ethereum", "Tesla", "Nvidia", "Apple", "Amazon", "Meta", "Google",
        "Defense", "Energy", "Health", "Tech", "Finance", "Media",
        "Full", "This", "What", "How", "Why", "The", "Top", "Best", "Now",
        "Here", "Next", "New", "Big", "Great", "Must", "Will", "Can",
    }

    for pat in patterns:
        m = re.search(pat, title)
        if m:
            name = m.group(1).strip()
            parts = name.split()
            if len(parts) < 2:
                continue
            if parts[0] in skip_first:
                continue
            # Skip sports figures via content keywords
            sports_kw = ["wimbledon", "nfl", "nba", "tennis", "soccer", "football",
                        "basketball", "baseball", "hockey", "golf", "boxing",
                        "pga", "mlb", "nhl", "ufc", "racing", "olympic",
                        "tour de france", "athlete", "player", "coach"]
            title_lower = title.lower()
            if any(kw in title_lower for kw in sports_kw):
                # Only allow sports content if it ALSO has finance keywords
                finance_kw = ["stock", "market", "invest", "economy", "fed",
                             "rate", "inflation", "ipo", "etf", "portfolio"]
                if not any(kw in title_lower for kw in finance_kw):
                    return None

            # Skip non-finance professionals
            non_finance_roles = ["writer", "author", "actor", "actress", "director",
                                "producer", "musician", "artist", "chef", "trainer",
                                "coach", "broadcaster", "podcaster"]
            role_match = [r for r in non_finance_roles if r in title_lower]
            if role_match:
                # Only skip if role is the primary descriptor (not both finance and non-finance)
                if not any(kw in title_lower for kw in ["stock", "market", "invest", "economy"]):
                    return None

            return name

    return None
