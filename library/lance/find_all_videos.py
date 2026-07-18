#!/usr/bin/env python3
"""Phase 1: Find 200+ videos from TheOneLanceB channel using many search queries."""

import sys, json, re, os, time
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

OUTPUT_DIR = "/Users/shtylenko/Projects/trading/library/lance"

api = YouTubeAPI()

# Broad queries that will hit Lance's content across different topics
queries = [
    # Direct channel references
    "TheOneLanceB trading",
    "TheOneLanceB strategy",
    "TheOneLanceB stocks",
    "TheOneLanceB day trading",
    "TheOneLanceB forex",
    "TheOneLanceB psychology",
    "Lance Breitstein trading",
    "Lance Breitstein strategy",
    "Lance Breitstein stocks",
    # Topical queries that his videos cover
    "day trading routine lance",
    "trading psychology lance",
    "no man's land trading",
    "right side of the V trading",
    "trading constraints beginner",
    "trading playbook lance",
    "market wizards lance breitstein",
    "trillium trading lance",
    "trading career lance",
    "small account trading lance",
    "trading 2026 lance",
    "trading gameplan lance",
    "trading charts setup lance",
    "how to start trading lance",
    "trading pod lance",
    "stock selection lance",
    "trend trading lance",
    "trading with trend lance",
    "trade review lance",
    "trading mistakes lance",
    "trading losses lance",
    "growing account lance",
    "trading mindset lance",
    "professional trader lance",
    "trading rules lance",
    "pro trader tips lance",
    "trading journal lance",
    "risk management lance",
    "trading edge lance",
    "scalping lance",
    "momentum trading lance",
    "swing trading lance",
    "breakout trading lance",
    "trading system lance",
    "trading routine lance",
    "trading discipline lance",
    "trading profits lance",
    "quit your job trading lance",
    "trading full time lance",
    "trader education lance",
    "SMB Capital lance",
    "market analysis lance",
    "price action lance",
    "trading indicators lance",
]

seen_ids = set()
all_videos = []

for q in queries:
    try:
        r = api.search_videos(q, max_results=50)
        for v in r.get("data", []):
            vid = v.get("video_id", "")
            channel = v.get("channel", "")
            if vid and vid not in seen_ids and "TheOneLanceB" in channel:
                seen_ids.add(vid)
                all_videos.append(v)
        print(f"  Query '{q[:40]}...' -> {len([v for v in r.get('data', []) if 'TheOneLanceB' in (v.get('channel',''))])} new, total unique: {len(all_videos)}")
        time.sleep(0.3)
    except Exception as e:
        print(f"  Query '{q[:40]}...' FAILED: {e}")

# Sort by view_count descending (most popular first)
all_videos.sort(key=lambda v: v.get("view_count", 0), reverse=True)

print(f"\nTotal unique videos found: {len(all_videos)}")

# Save video list
output = []
for v in all_videos:
    output.append({
        "video_id": v.get("video_id"),
        "title": v.get("title"),
        "view_count": v.get("view_count", 0),
        "published_date": v.get("published_date", ""),
        "url": v.get("url", ""),
        "duration": v.get("duration", ""),
    })

with open(os.path.join(OUTPUT_DIR, "lance_videos.json"), "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Saved {len(output)} videos to lance_videos.json")
print(f"\nTop 10 by views:")
for i, v in enumerate(output[:10]):
    print(f"  {i+1}. [{v['view_count']:>8,}] {v['title']} ({v['video_id']})")
