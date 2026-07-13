#!/usr/bin/env python3
"""
Phase 1: Search YouTube for swing/intraday trading strategy videos
from top influencers focused on long stock/ETF US strategies.
"""
import sys, json, re, os, time
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

OUTPUT_DIR = "/Users/shtylenko/Projects/trading/library/youtube-influencers"
api = YouTubeAPI()

# Strategic search queries targeting our 25 strategy categories
search_queries = [
    # Momentum Burst / Episodic Pivot
    "momentum burst strategy swing trading stocks",
    "episodic pivot breakout strategy stocks",
    "Kristjan Qullamaggie trading strategy",
    
    # Weekly Breakout / Consolidation
    "weekly chart breakout consolidation strategy stocks",
    "Financial Wisdom swing trading strategy weekly charts",
    
    # Pullback / EMA strategies
    "pullback to 21 EMA swing trading strategy stocks",
    "anchored VWAP pullback strategy stocks",
    "buy the first pullback after breakout stocks",
    
    # Pocket Pivot / VCP
    "Mark Minervini SEPA strategy pocket pivot",
    "VCP volatility contraction pattern swing trading",
    "pocket pivot volume accumulation strategy",
    
    # Bull Flag / Continuation
    "bull flag breakout swing trading strategy stocks",
    "flag pattern continuation stocks swing trade",
    
    # MACD strategies
    "MACD 3 10 16 pullback swing trading strategy",
    "Linda Raschke MACD swing trading strategy",
    
    # Trend following strategies
    "9 EMA 21 EMA trend following swing trading",
    "50 day moving average bounce strategy stocks",
    "20 day moving average support swing trade",
    
    # Gap and Go
    "gap and go momentum stocks strategy",
    "gap fill trading strategy stocks",
    
    # Support/Resistance
    "support resistance bounce swing trading strategy",
    "swing trading support resistance levels",
    
    # Range Breakout
    "range breakout with volume confirmation strategy",
    "consolidation breakout scanner stocks",
    
    # VWAP strategies
    "VWAP bounce strategy stocks swing trade",
    "VWAP trend following intraday stocks",
    
    # Cup and Handle
    "cup and handle breakout stocks strategy",
    "cup and handle pattern swing trading",
    
    # Inside Bar
    "inside bar breakout swing trading strategy",
    "inside bar continuation pattern stocks",
    
    # SMA Trend Structure
    "20 50 200 SMA trend structure swing trading",
    "moving average ribbon strategy stocks",
    
    # Fibonacci
    "Fibonacci retracement pullback entry stocks",
    "Fibonacci extension targets swing trading",
    
    # Bollinger Bands
    "Bollinger band squeeze breakout strategy",
    "Bollinger band walk strategy stocks",
    
    # Relative Strength
    "relative strength sector rotation strategy stocks",
    "relative strength ranking swing trading",
    
    # Institutional Accumulation
    "institutional accumulation volume analysis stocks",
    "accumulation distribution volume strategy stocks",
    
    # ETF Strategies
    "best swing trading ETFs strategy",
    "QQQ SPY swing trading strategy",
    
    # Specific Influencer Strategies
    "Rayner Teo price action swing trading strategy",
    "Chris Sain bull flag 100K strategy",
    "Larry Jones swing trading buy the dip",
    "Hamid Shojaee concentrated portfolio strategy",
    "Martin Luk pullback trading strategy",
    "Pradeep Bonde StockBee trading strategy",
    "Ricky Gutierrez swing trading setups",
    "Lance Ippolito swing trading strategy",
]

all_videos = {}
seen_ids = set()
batch = 0

for query in search_queries:
    try:
        r = api.search_videos(query, max_results=15)
        for v in r.get("data", []):
            vid = v.get("video_id", "")
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                channel = v.get("channel", "Unknown")
                title = v.get("title", "")
                views = v.get("view_count", 0)
                duration = v.get("duration", "")
                all_videos[vid] = {
                    "video_id": vid,
                    "title": title,
                    "channel": channel,
                    "views": views,
                    "duration": duration,
                    "url": v.get("url", ""),
                    "published": v.get("published_date", ""),
                    "query": query
                }
    except Exception as e:
        print(f"  Error searching '{query}': {e}")
    
    batch += 1
    if batch % 10 == 0:
        print(f"Processed {batch}/{len(search_queries)} queries, collected {len(all_videos)} unique videos", flush=True)
    time.sleep(0.3)

print(f"\n=== Total unique videos found: {len(all_videos)} ===", flush=True)

# Sort by views descending
sorted_vids = sorted(all_videos.values(), key=lambda x: x["views"], reverse=True)

# Save full results
with open(f"{OUTPUT_DIR}/all_videos_found.json", "w") as f:
    json.dump(sorted_vids, f, indent=2)

# Save top 200 for transcription
top_vids = sorted_vids[:200]
with open(f"{OUTPUT_DIR}/top_videos.json", "w") as f:
    json.dump(top_vids, f, indent=2)

print(f"\nTop 20 by views:", flush=True)
for i, v in enumerate(top_vids[:20]):
    print(f"  {i+1}. [{v['views']} views] {v['channel']}: {v['title'][:80]}", flush=True)
