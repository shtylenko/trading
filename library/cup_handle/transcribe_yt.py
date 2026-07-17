#!/usr/bin/env python3
"""Transcribe top cup-and-handle YouTube videos."""
import sys, os, json
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

api = YouTubeAPI()

# Videos with good view counts and relevant content
videos = [
    ("u38ldCw0CSo", "EXPERT Cup And Handle Chart Pattern Trading Strategy (For Pros Only)", 174288),
    ("2_DGdanpDWI", "WILLIAM O'NEIL - HOW TO MAKE MONEY IN STOCKS - Cup and Handle Chart Pattern", 170672),
    ("9gX--m5Bo30", "I Studied the Top 100 Stocks... The Results Shocked Me (VCP Pattern)", 23247),
    ("I8Usc5lza_Y", "Profitable Trading Strategy: Master the Volatility Contraction Pattern (VCP)", 84135),
    ("Tm0dkf8_giA", "+50% in 20 Days - How to Trade Breakouts with The Volatility Contraction Pattern", 103678),
    ("M7BaWuE3S1g", "Cup and Handle Pattern: Day Trading Strategy for Beginners", 48672),
    ("MvUHkmOzmaw", "Automatically Detect Cup and Handle Patterns: New Feature", 36734),
    ("LdBgc3A_bbs", "Cup With Handle Pattern - Common Mistake", 61525),
    ("IaOnSrnIrLI", "The Pattern Behind the Market's Biggest Winners", 9764),
    ("9HHfYUbQQQA", "Chart Patterns: Cup With Handle", 33877),
    ("z38jCt_h080", "ADVANCED Cup and Handle Chart Pattern Trading Strategy (For Pros Only)", 19273),
    ("0tife_Hcoeg", "Profitable Cup and Handle Trading Strategy", 1052),
    ("TCMYEdNIFMQ", "Channel about cup-handle screener", 0),
    ("KVGDJ5TPBjk", "How to Use Cup & Handle Indicator Trading Strategy in TradingView", 8589),
    ("pFfUOL6tf6Y", "Best Cup and Handle Chart Pattern Strategy for Swing Trading", 753),
    ("oWheof70O9g", "I made a Market Simulation to see if Patterns are Real", 1014470),
    ("X31hyMhB-3s", "3 Must-Know Algorithms for Automating Chart Pattern Trading in Python", 82700),
]

results = []
for vid, title, views in videos:
    print(f"\n=== {vid} ({views} views) ===")
    print(f"Title: {title}")
    try:
        details = api.get_video_details(vid)
        video = details.get('video_details', {})
        channel = video.get('channel_title', '')
        print(f"Channel: {channel}")

        transcript_info = details.get('transcript')
        if transcript_info and transcript_info.get('transcript_url'):
            text = api.transcribe_video(transcript_info['transcript_url'])
            if isinstance(text, dict) and 'raw_text' in text:
                content = text['raw_text']
                print(f"Transcribed: {len(content)} chars")
                results.append({
                    "video_id": vid,
                    "title": title,
                    "channel": channel,
                    "views": views,
                    "transcript": content[:5000],
                })
                # Save full transcript
                outpath = f"/Users/shtylenko/Projects/trading/library/cup_handle/yt_{vid}.txt"
                with open(outpath, 'w') as f:
                    f.write(f"Title: {title}\nChannel: {channel}\nViews: {views}\nURL: https://youtube.com/watch?v={vid}\n\n{content}")
                print(f"Saved to {outpath}")
            else:
                print(f"ytapi failed: {text}")
        else:
            print("No transcript URL available")
    except Exception as e:
        print(f"ERROR: {e}")

# Write summary
summary_path = "/Users/shtylenko/Projects/trading/library/cup_handle/03_youtube_metadata.json"
with open(summary_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\n\nSummary saved to {summary_path}: {len(results)} transcriptions")
