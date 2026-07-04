#!/usr/bin/env python3
"""YouTube research: CORE / ACADEMIC category (5 keywords, 20 videos each).
Searches YouTube, transcribes, saves transcripts. Designed to be fault-tolerant."""

import sys
import os
import json
import re
import time
import http.client
from urllib.parse import urlencode

sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

BASE_DIR = "/Users/shtylenko/Hermes/projects/trading_strategy_finder/engine/strategy_lab/strategies/xsec_momentum/peer-feedback/2026-06-17-keyword-research"
SAVE_DIR = os.path.join(BASE_DIR, "transcripts", "core_academic")
os.makedirs(SAVE_DIR, exist_ok=True)

KEYWORDS = {
    "cross_sectional_momentum_strategy": "cross-sectional momentum strategy",
    "jegadeesh_titman_12_1": "Jegadeesh Titman momentum 12-1",
    "relative_strength_momentum": "relative strength momentum stocks",
    "momentum_factor_umd": "momentum factor investing UMD factor",
    "residual_momentum": "residual momentum"
}

api = YouTubeAPI()

def slugify(text):
    return re.sub(r'[^a-z0-9_]+', '_', text.lower())[:40]

def safe_filename(keyword, vid, title):
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:60]
    return f"{keyword}_{vid}_{safe}.txt"

def transcribe_with_retry(transcript_url, max_retries=3):
    """Transcribe with exponential backoff for 403/Retry errors."""
    delays = [3, 8, 15]
    for attempt in range(max_retries):
        try:
            text = api.transcribe_video(transcript_url)
            if isinstance(text, dict) and 'raw_text' in text:
                return text['raw_text']
            elif isinstance(text, dict) and text.get('error') == 'Retry':
                if attempt < max_retries - 1:
                    time.sleep(delays[attempt])
                    continue
                return f"[TRANSCRIPT UNAVAILABLE after {max_retries} retries: {text.get('error')}]"
            else:
                return f"[TRANSCRIPT UNEXPECTED FORMAT: {str(text)[:200]}]"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delays[attempt])
                continue
            return f"[TRANSCRIPT ERROR: {str(e)[:200]}]"
    return "[TRANSCRIPT FAILED]"

results_summary = {}

for kw_key, kw_query in KEYWORDS.items():
    print(f"\n{'='*60}")
    print(f"SEARCHING: {kw_query}")
    
    try:
        r = api.search_videos(kw_query, max_results=20)
    except Exception as e:
        print(f"  SEARCH FAILED: {e}")
        results_summary[kw_query] = {"status": "SEARCH_FAILED", "videos": [], "transcribed": 0}
        continue
    
    videos = r.get("data", [])
    if not videos:
        print(f"  NO RESULTS")
        results_summary[kw_query] = {"status": "NO_RESULTS", "videos": [], "transcribed": 0}
        continue
    
    print(f"  Found {len(videos)} videos")
    transcribed_count = 0
    video_details = []
    
    for idx, v in enumerate(videos[:20]):
        vid = v.get("video_id", "")
        title = v.get("title", "Unknown")
        channel = v.get("channel", "Unknown")
        views = v.get("view_count", 0)
        published = v.get("published_date", "")
        
        if not vid:
            continue
        
        print(f"\n  [{idx+1}/20] {title[:70]} ({channel})")
        fname = safe_filename(kw_key, vid, title)
        fpath = os.path.join(SAVE_DIR, fname)
        
        # Get details (need this for transcript URL)
        try:
            details = api.get_video_details(vid)
        except Exception as e:
            print(f"    DETAILS FAILED: {e}")
            continue
        
        video = details.get("video_details", {})
        ti = details.get("transcript")
        
        transcript_text = ""
        if ti and ti.get("transcript_url"):
            transcript_text = transcribe_with_retry(ti["transcript_url"])
            if transcript_text and not transcript_text.startswith("[TRANSCRIPT"):
                transcribed_count += 1
                print(f"    ✓ TRANSCRIBED ({len(transcript_text)} chars)")
            else:
                print(f"    ✗ {transcript_text[:80]}")
        else:
            # Try to search by ID directly for transcript
            try:
                # Sometimes the details response has transcript info differently
                fallback_details = api.get_video_details(vid)
                ti2 = fallback_details.get("transcript")
                if ti2 and ti2.get("transcript_url"):
                    transcript_text = transcribe_with_retry(ti2["transcript_url"])
                    if transcript_text and not transcript_text.startswith("[TRANSCRIPT"):
                        transcribed_count += 1
                        print(f"    ✓ TRANSCRIBED (fallback, {len(transcript_text)} chars)")
                    else:
                        print(f"    ✗ {transcript_text[:80]}")
                else:
                    print(f"    - NO TRANSCRIPT URL")
                    transcript_text = "[NO TRANSCRIPT AVAILABLE]"
            except Exception as e:
                print(f"    - NO TRANSCRIPT: {str(e)[:60]}")
                transcript_text = "[NO TRANSCRIPT AVAILABLE]"
        
        # Save the transcript
        with open(fpath, 'w') as f:
            f.write(f"TITLE: {title}\n")
            f.write(f"URL: https://youtube.com/watch?v={vid}\n")
            f.write(f"CHANNEL: {channel}\n")
            f.write(f"VIEWS: {views}\n")
            f.write(f"PUBLISHED: {published}\n")
            f.write(f"KEYWORD: {kw_query}\n")
            f.write(f"={'='*70}\n\n")
            f.write(transcript_text)
        
        video_details.append({
            "vid": vid,
            "title": title,
            "channel": channel,
            "views": views,
            "published": published,
            "transcribed": bool(transcript_text and not transcript_text.startswith("[TRANSCRIPT") and transcript_text != "[NO TRANSCRIPT AVAILABLE]"),
            "chars": len(transcript_text)
        })
    
    results_summary[kw_query] = {
        "status": "OK",
        "total_found": len(videos),
        "transcribed": transcribed_count,
        "videos": video_details
    }
    print(f"\n  ---> {transcribed_count}/{len(videos[:20])} transcribed for '{kw_query}'")
    time.sleep(1)

# Write findings summary
findings_path = os.path.join(SAVE_DIR, "_FINDINGS.md")
with open(findings_path, 'w') as f:
    f.write("# Core / Academic — YouTube Research Findings\n\n")
    f.write(f"Generated: 2026-06-17\n\n")
    f.write("## Summary\n\n")
    f.write(f"Researched 5 keywords, targeting 20 videos each.\n\n")
    
    total_transcribed = sum(r["transcribed"] for r in results_summary.values() if r["status"] == "OK")
    f.write(f"Total videos transcribed: {total_transcribed}\n\n")
    
    for kw_query, info in results_summary.items():
        f.write(f"## {kw_query}\n\n")
        if info["status"] != "OK":
            f.write(f"Status: {info['status']}\n\n")
            continue
        
        f.write(f"Videos found: {info['total_found']}, Transcribed: {info['transcribed']}\n\n")
        
        f.write("| # | Title | Channel | Views | Transcribed |\n")
        f.write("|---|---|---|---|---|\n")
        for i, v in enumerate(info["videos"][:20], 1):
            transcribed_mark = "✓" if v["transcribed"] else "✗"
            f.write(f"| {i} | {v['title'][:60]} | {v['channel'][:30]} | {v['views']} | {transcribed_mark} |\n")
        f.write("\n")
    
    f.write("## Cross-Sectional Momentum — Key Ideas Extracted\n\n")
    f.write("Ideas from these videos that could improve the xsec_momentum strategy:\n\n")
    f.write("### P0 (High priority — test next)\n\n")
    f.write("(To be filled after reading transcript content)\n\n")
    f.write("### P1 (Medium priority)\n\n")
    f.write("(To be filled after reading transcript content)\n\n")
    f.write("### P2 (Low priority / gated)\n\n")
    f.write("(To be filled after reading transcript content)\n\n")

print(f"\n{'='*60}")
print(f"DONE! Transcribed {total_transcribed} videos total")
print(f"Findings saved to: {findings_path}")
print(f"{'='*60}")
