#!/usr/bin/env python3
"""
Phase 2: Filter videos by relevant channels and transcribe them.
Focus on US stock/ETF long-only strategies. No crypto/futures/options.
"""
import sys, json, re, os, time
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

OUTPUT_DIR = "/Users/shtylenko/Projects/trading/library/youtube-influencers"
TRANSCRIPT_DIR = f"{OUTPUT_DIR}/transcripts"
api = YouTubeAPI()

# Target channels for long US stock/ETF strategies
TARGET_CHANNELS = [
    "Rayner Teo", "Financial Wisdom", "Lance Ippolito", "Chris Sain", "Larry Jones",
    "Matt Giannino", "Ricky Gutierrez", "ClayTrader", "Humbled Trader", "SMB Capital",
    "Ross Cameron", "Warrior Trading", "TraderNick", "Stock Moe", "ZipTrader",
    "Bulls on Wall Street", "GDT Stock Trading", "Gaurav", "Mind Math Money",
    "Wysetrade", "TradingLab", "The Trading Geek", "Simplify Trading",
    "Investors Underground", "Chat With Traders", "Simpler Trading",
    "TopDog Trading", "Hamid Shojaee", "Savvy Trader", "Stockwonk",
    "Pradeep Bonde", "StockBee", "Words of Rizdom", "TraderTom",
    "The Contrarian Trader", "The Trade Risk", "SwingTrading with Cycles",
    "Trade Empowered", "PensionCraft", "Brian Feroldi", "Joseph Carlson",
    "Graham Stephan", "Andrei Jikh", "Martyn Lucas",
    "Brandon J", "Sven Carlin",
]

# Load top videos
with open(f"{OUTPUT_DIR}/top_videos.json") as f:
    top_videos = json.load(f)

# Filter to target channels
filtered = []
for v in top_videos:
    channel = v.get("channel", "")
    for tc in TARGET_CHANNELS:
        if tc.lower() in channel.lower():
            filtered.append(v)
            break

# Also add some high-view videos from relevant channels that contain strategy keywords
strategy_keywords = ["strategy", "swing trade", "breakout", "pullback", "momentum", 
                     "moving average", "MACD", "support and resistance", "VWAP",
                     "bull flag", "cup and handle", "trend", "EMA", "VCP", 
                     "pocket pivot", "Fibonacci", "gaps", "volume", "consolidation"]
for v in top_videos:
    title = v.get("title", "").lower()
    if v["video_id"] not in {f["video_id"] for f in filtered}:
        if any(kw in title for kw in strategy_keywords):
            filtered.append(v)
    if len(filtered) >= 300:
        break

print(f"Filtered to {len(filtered)} videos for transcription", flush=True)

# Save filtered list
with open(f"{OUTPUT_DIR}/filtered_videos.json", "w") as f:
    json.dump(filtered, f, indent=2)

# Print top 30 for reference
for i, v in enumerate(filtered[:30]):
    print(f"  {i+1}. [{v['views']}] {v['channel'][:30]}: {v['title'][:60]}", flush=True)

# Phase 2: Transcribe! Prioritize by views
# Process top 150 videos (or as many as we can)
transcribed = 0
errors = 0
no_transcript = 0
max_to_transcribe = 150
retry_backoffs = [3, 8, 15]

for idx, v in enumerate(filtered[:max_to_transcribe]):
    vid = v["video_id"]
    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', v["title"])[:60]
    outpath = f"{TRANSCRIPT_DIR}/{vid}_{safe_title}.txt"
    
    # Skip if already transcribed
    if os.path.exists(outpath):
        continue
    
    # Get video details + transcript URL
    details = api.get_video_details(vid)
    if "error" in details:
        errors += 1
        continue
    
    transcript = details.get("transcript")
    if not transcript or not transcript.get("transcript_url"):
        no_transcript += 1
        continue
    
    # Transcribe with retry for 403
    transcript_url = transcript["transcript_url"]
    text = None
    for attempt, delay in enumerate(retry_backoffs):
        result = api.transcribe_video(transcript_url, use_cache=True)
        if "error" not in result and "raw_text" in result and result["raw_text"]:
            text = result["raw_text"]
            break
        elif result.get("error") == "Retry" or "Retry" in str(result):
            time.sleep(delay)
        else:
            break
    
    if text:
        with open(outpath, "w") as f:
            f.write(f"Title: {v['title']}\n")
            f.write(f"Channel: {v['channel']}\n")
            f.write(f"URL: {v['url']}\n")
            f.write(f"Views: {v['views']}\n")
            f.write(f"Duration: {v['duration']}\n")
            f.write(f"{'='*70}\n\n{text}")
        transcribed += 1
    else:
        errors += 1
    
    if (idx + 1) % 20 == 0:
        print(f"Progress: {idx+1}/{min(len(filtered), max_to_transcribe)} | OK:{transcribed} Fail:{errors} NoSub:{no_transcript}", flush=True)
    time.sleep(0.5)

print(f"\n=== Transcription Complete ===", flush=True)
print(f"  Transcribed: {transcribed}", flush=True)
print(f"  Failed: {errors}", flush=True)
print(f"  No transcript: {no_transcript}", flush=True)
print(f"  Total attempted: {min(len(filtered), max_to_transcribe)}", flush=True)
