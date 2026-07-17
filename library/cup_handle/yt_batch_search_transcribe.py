#!/usr/bin/env python3
"""Search YouTube broadly, rank candidates by views, batch-transcribe as many as possible."""
import sys, os, json, time
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

api = YouTubeAPI()
LIB = "/Users/shtylenko/Projects/trading/library/cup_handle"

# Additional search queries to cast a wider net
extra_queries = [
    "cup and handle trading strategy stock market",
    "William O'Neil cup handle breakout",
    "cup handle pattern stocks backtest performance",
    "swing trading cup handle base breakout",
    "cup and handle scanner screener",
    "best cup handle setups 2024 2025 2026",
    "cup handle pattern entry stop target rules",
    "how to trade cup handle pattern stocks",
    "cup with handle trading strategy backtested",
    "cup handle pattern win rate statistics",
    "rounded bottom cup handle trading",
    "technical analysis cup pattern",
    "cup handle fail fake breakout avoid",
    "stage 2 uptrend cup base breakout",
    "institutional accumulation cup pattern",
    "cup handle pattern python detection",
    "trader cup handle daily chart swing",
    "cup handle example stock analysis",
    "O'Neil base types cup flat double bottom",
    "cup handle relative strength volume breakout",
]

print("=== STEP 1: Search for candidates ===")
all_vids = {}
for q in extra_queries:
    try:
        r = api.search_videos(q, max_results=10)
        for v in r.get("data", []):
            vid = v.get("video_id", "")
            title = v.get("title", "")
            views = v.get("view_count", 0) or 0
            chan = v.get("channel_title", "")
            if vid and vid not in all_vids and views > 500:
                all_vids[vid] = {"vid": vid, "title": title, "views": views, "channel": chan}
            elif vid and vid not in all_vids:
                all_vids[vid] = {"vid": vid, "title": title, "views": views, "channel": chan}
    except:
        pass
    time.sleep(0.3)

# Also search the original queries for more results
original_queries = [
    "cup and handle pattern strategy backtest",
    "cup and handle swing trading rules",
    "O'Neil cup and handle pattern explained",
    "VCP pattern Minervini backtest results",
    "cup and handle breakout entry strategy",
]
for q in original_queries:
    try:
        r = api.search_videos(q, max_results=10)
        for v in r.get("data", []):
            vid = v.get("video_id", "")
            title = v.get("title", "")
            views = v.get("view_count", 0) or 0
            chan = v.get("channel_title", "")
            if vid and vid not in all_vids and views > 500:
                all_vids[vid] = {"vid": vid, "title": title, "views": views, "channel": chan}
            elif vid and vid not in all_vids:
                all_vids[vid] = {"vid": vid, "title": title, "views": views, "channel": chan}
    except:
        pass
    time.sleep(0.3)

# Sort by views descending
sorted_vids = sorted(all_vids.values(), key=lambda x: -x["views"])
print(f"Found {len(sorted_vids)} unique candidate videos")

# Save candidate list
cand_path = os.path.join(LIB, "03_yt_candidates.json")
with open(cand_path, 'w') as f:
    json.dump(sorted_vids, f, indent=2)
print(f"Candidates saved to {cand_path}")

# Skip already-transcribed videos
existing = set()
for fname in os.listdir(LIB):
    if fname.startswith("yt_") and fname.endswith(".txt"):
        vid = fname[3:-4]
        existing.add(vid)
print(f"Already transcribed: {len(existing)} videos")

# Transcribe as many as possible
print("\n=== STEP 2: Batch transcribe ===")
transcribed = []
errors = []
failed_no_transcript = []
skip_count = 0

for i, v in enumerate(sorted_vids):
    vid = v["vid"]
    title = v["title"]
    views = v["views"]
    chan = v["channel"]

    if vid in existing:
        skip_count += 1
        continue

    outpath = os.path.join(LIB, f"yt_{vid}.txt")
    if os.path.exists(outpath) and os.path.getsize(outpath) > 100:
        skip_count += 1
        continue

    print(f"[{i+1}/{len(sorted_vids)}] {vid} ({views} views) - {title[:60]}")
    try:
        details = api.get_video_details(vid)
        video = details.get('video_details', {})
        transcript_info = details.get('transcript')

        meta = f"Title: {title}\nChannel: {chan}\nViews: {views}\nURL: https://youtube.com/watch?v={vid}\n\n"

        if transcript_info and transcript_info.get('transcript_url'):
            text = api.transcribe_video(transcript_info['transcript_url'])
            if isinstance(text, dict) and 'raw_text' in text:
                content = text['raw_text']
                with open(outpath, 'w') as f:
                    f.write(meta + content)
                transcribed.append({"vid": vid, "title": title, "views": views, "channel": chan, "chars": len(content)})
                print(f"  ✓ {len(content)} chars")
            else:
                failed_no_transcript.append(vid)
                # write metadata anyway
                with open(outpath, 'w') as f:
                    f.write(meta + f"[TRANSCRIPT NOT AVAILABLE]\n{text}")
                print(f"  ✗ ytapi failed: {str(text)[:100]}")
        else:
            # Try youtube-transcript-api as fallback
            try:
                from youtube_transcript_api import YouTubeTranscriptApi
                tr = YouTubeTranscriptApi().fetch(vid)
                text = " ".join(s.text for s in tr)
                if len(text) > 50:
                    with open(outpath, 'w') as f:
                        f.write(meta + text)
                    transcribed.append({"vid": vid, "title": title, "views": views, "channel": chan, "chars": len(text)})
                    print(f"  ✓ (fallback) {len(text)} chars")
                else:
                    failed_no_transcript.append(vid)
                    print(f"  ✗ fallback too short")
            except Exception as e2:
                failed_no_transcript.append(vid)
                with open(outpath, 'w') as f:
                    f.write(meta + f"[TRANSCRIPT NOT AVAILABLE]\n{str(e2)}")
                print(f"  ✗ no transcript: {str(e2)[:80]}")
    except Exception as e:
        errors.append({"vid": vid, "error": str(e)})
        print(f"  ✗ ERROR: {str(e)[:100]}")

    # Rate limit: sleep 1s every 5 videos
    if (i + 1) % 5 == 0:
        time.sleep(2)
    else:
        time.sleep(0.5)

# Summary
print(f"\n=== SUMMARY ===")
print(f"Candidates found: {len(sorted_vids)}")
print(f"Newly transcribed: {len(transcribed)}")
print(f"Skipped (already done): {skip_count}")
print(f"No transcript: {len(failed_no_transcript)}")
print(f"Errors: {len(errors)}")
print(f"Total transcribed files: {len([f for f in os.listdir(LIB) if f.startswith('yt_') and f.endswith('.txt')])}")

# Write summary JSON
summary = {
    "total_candidates": len(sorted_vids),
    "newly_transcribed": transcribed,
    "failed_no_transcript": failed_no_transcript[:50],
    "errors": errors[:20],
    "total_transcript_files": len([f for f in os.listdir(LIB) if f.startswith('yt_') and f.endswith('.txt')]),
}
summary_path = os.path.join(LIB, "03_yt_transcript_summary.json")
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2, default=str)
print(f"Summary saved to {summary_path}")
