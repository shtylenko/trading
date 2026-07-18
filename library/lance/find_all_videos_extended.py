#!/usr/bin/env python3
"""Phase 1 extended: Exhaustive search for ALL TheOneLanceB videos."""
import sys, json, re, os, time
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

OUTPUT_DIR = "/Users/shtylenko/Projects/trading/library/lance"
api = YouTubeAPI()

# Load existing
existing_path = os.path.join(OUTPUT_DIR, "lance_videos.json")
if os.path.exists(existing_path):
    with open(existing_path) as f:
        existing = json.load(f)
    seen_ids = {v["video_id"] for v in existing}
    print(f"Loaded {len(existing)} existing videos, {len(seen_ids)} IDs")
else:
    existing = []
    seen_ids = set()

all_videos = {v["video_id"]: v for v in existing}

# Expanded query list - beam search approach
queries = [
    "TheOneLanceB",  # catch-all
    "Lance Breitstein",
    "TheOneLanceB trading",
    "TheOneLanceB strategy",
    "TheOneLanceB stocks",
    "TheOneLanceB day trading",
    "TheOneLanceB forex",
    "TheOneLanceB psychology",
    "Lance Breitstein trading",
    "Lance Breitstein strategy",
    "Lance Breitstein stocks",
    "day trading routine lance",
    "trading psychology lance",
    "no man's land trading lance",
    "right side of the V trading lance",
    "trading constraints beginning",
    "trading playbook",
    "market wizards lance breitstein",
    "trillium trading lance",
    "trading career lance",
    "small account trading",
    "trading gameplan",
    "trading charts setup",
    "how to start day trading lance",
    "trading pod",
    "stock selection lance",
    "trend trading lance",
    "trade review lance",
    "trading mistakes lance",
    "growing account trading",
    "trading mindset lance",
    "trading rules",
    "pro trader tips",
    "trading journal lance",
    "risk management lance",
    "trading edge",
    "scalping strategies lance",
    "momentum trading lance",
    "swing trading lance",
    "breakout trading lance",
    "trading system lance",
    "trading routine lance",
    "trading discipline",
    "quit your job trading",
    "trading full time",
    "trader education",
    "SMB Capital lance",
    "price action lance",
    "trading indicators lance",
    "theonelanceb shorts",
    "theonelanceb quick",
    "theonelanceb tips",
    "theonelanceb mistakes",
    "theonelanceb scalping",
    "theonelanceb VWAP",
    "theonelanceb momentum",
    "theonelanceb trend",
    "theonelanceb breakouts",
    "theonelanceb support",
    "theonelanceb risk",
    "theonelanceb losses",
    "theonelanceb profits",
    "theonelanceb trading plan",
    "theonelanceb technical analysis",
    "theonelanceb price action",
    "theonelanceb indicators",
    "theonelanceb rsi",
    "theonelanceb moving average",
    "theonelanceb MACD",
    "theonelanceb trading setup",
    "theonelanceb watchlist",
    "theonelanceb premarket",
    "theonelanceb reversal",
    "theonelanceb continuation",
    "breitstein trading",
    "theonelanceb wall street",
    "theonelanceb market wizards",
    "theonelanceb jack schwager",
    "theonelanceb smb capital",
    "theonelanceb trillium",
    "theonelanceb options",
    "theonelanceb futures",
    "theonelanceb spy",
    "theonelanceb qqq",
    "theonelanceb bitcoin",
    "theonelanceb nvda",
    "theonelanceb tsla",
    "theonelanceb apple",
    "theonelanceb amzn",
    "theonelanceb googl",
    "theonelanceb interview",
    "theonelanceb podcast",
    "theonelanceb reacts",
    "theonelanceb qa",
    "theonelanceb live",
    "theonelanceb stream",
    "theonelanceb course",
    "theonelanceb million",
    "lance breitstein reacts",
    "lance breitstein review",
    "lance breitstein interview",
    "lance breitstein podcast",
    "theonelanceb short squeeze",
    "theonelanceb volatility",
    "theonelanceb liquidity",
    "theonelanceb market making",
    "theonelanceb position sizing",
    "theonelanceb win rate",
    "theonelanceb drawdown",
    "theonelanceb backtesting",
    "theonelanceb trading plan",
    "theonelanceb trading rules",
    "theonelanceb morning routine",
    "theonelanceb daily routine",
    "theonelanceb end of day",
    "theonelanceb market open",
    "theonelanceb volume analysis",
    "theonelanceb tape reading",
    "theonelanceb level 2",
    "theonelanceb time and sales",
    "theonelanceb order flow",
    "theonelanceb pattern day trading",
    "theonelanceb PDT rule",
    "theonelanceb prop firm",
    "theonelanceb funded account",
    "theonelanceb trading challenge",
    "theonelanceb small account challenge",
]

for i, q in enumerate(queries):
    try:
        r = api.search_videos(q, max_results=50)
        for v in r.get("data", []):
            vid = v.get("video_id", "")
            channel = v.get("channel", "")
            if vid and "TheOneLanceB" in (channel or "") and vid not in seen_ids:
                seen_ids.add(vid)
                all_videos[vid] = v
        new_count = len(seen_ids)
        if (i+1) % 10 == 0:
            print(f"  Q {i+1}/{len(queries)} -> {new_count} unique so far")
        time.sleep(0.25)
    except Exception as e:
        if (i+1) % 10 == 0:
            print(f"  Q {i+1}/{len(queries)} error: {e}")
        time.sleep(0.5)

print(f"\nTotal unique videos after exhaustive search: {len(all_videos)}")

# Sort by view_count
sorted_vids = sorted(all_videos.values(), key=lambda v: v.get("view_count", 0), reverse=True)

# Save
output = []
for v in sorted_vids:
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
print(f"\nTotal count: {len(output)}")
print(f"\nTop 20 by views:")
for i, v in enumerate(output[:20]):
    print(f"  {i+1:>2}. [{v['view_count']:>8,}] {v['title'][:70]} ({v['video_id']})")
print(f"\nBottom 5:")
for v in output[-5:]:
    print(f"     [{v['view_count']:>8,}] {v['title'][:70]} ({v['video_id']})")
