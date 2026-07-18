#!/usr/bin/env python3
"""Phase 3: Batch transcribe all 132 videos from TheOneLanceB."""
import sys, json, os, time, re
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

OUTPUT_DIR = "/Users/shtylenko/Projects/trading/library/lance"
TRANSCRIPTS_DIR = os.path.join(OUTPUT_DIR, "transcripts")
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

api = YouTubeAPI()

# Load video list
videos_path = os.path.join(OUTPUT_DIR, "lance_videos.json")
with open(videos_path) as f:
    videos = json.load(f)

# Filter to those with transcript URLs
to_transcribe = [v for v in videos if v.get("transcript_url")]
print(f"Total to transcribe: {len(to_transcribe)}")

# Load progress
progress_path = os.path.join(OUTPUT_DIR, "transcribe_progress.json")
if os.path.exists(progress_path):
    with open(progress_path) as f:
        progress = json.load(f)
    done_ids = set(progress.get("done", []))
    print(f"Resuming: {len(done_ids)} already done")
else:
    progress = {"done": [], "failed": [], "empty": []}
    done_ids = set()

ok_count = len(done_ids)
fail_count = 0
empty_count = 0

for i, v in enumerate(to_transcribe):
    vid = v["video_id"]
    
    # Skip if already done
    if vid in done_ids:
        continue
    
    transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{vid}.txt")
    if os.path.exists(transcript_path) and os.path.getsize(transcript_path) > 100:
        done_ids.add(vid)
        ok_count += 1
        progress["done"] = list(done_ids)
        continue
    
    title = v.get("title", "Unknown")
    transcript_url = v.get("transcript_url")
    
    if not transcript_url:
        continue
    
    # Transcribe with retries for 403 Retry errors
    text = None
    for attempt in range(5):
        try:
            result = api.transcribe_video(transcript_url, use_cache=True)
            if "raw_text" in result and result["raw_text"]:
                text = result["raw_text"]
                break
            elif "error" in result and "Retry" in result.get("error", ""):
                delays = [3, 8, 15, 25]
                wait = delays[min(attempt, len(delays)-1)]
                print(f"  Retry {attempt+1}/5 for {vid} ({title[:50]}): waiting {wait}s")
                time.sleep(wait)
            else:
                break
        except Exception as e:
            time.sleep(5)
    
    if text:
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(f"Title: {title}\n")
            f.write(f"URL: https://youtube.com/watch?v={vid}\n")
            f.write(f"{'='*70}\n\n")
            f.write(text)
        done_ids.add(vid)
        ok_count += 1
        
        if (ok_count - len(done_ids | set(progress.get("done", [])))) % 10 == 0:
            progress["done"] = list(done_ids)
            with open(progress_path, "w") as f:
                json.dump(progress, f)
    else:
        fail_count += 1
        progress["failed"].append(vid)
        print(f"  FAIL: {vid} ({title[:50]})")
    
    # Status update
    total_done = len(done_ids)
    if total_done % 10 == 0:
        print(f"  Progress: {total_done}/{len(to_transcribe)} transcribed ({ok_count} OK, {fail_count} fail)")
        progress["done"] = list(done_ids)
        with open(progress_path, "w") as f:
            json.dump(progress, f)
    
    time.sleep(1.5)  # Rate limiting

# Final save
progress["done"] = list(done_ids)
with open(progress_path, "w") as f:
    json.dump(progress, f)

print(f"\nTranscripts complete: {ok_count} OK, {fail_count} failed")
print(f"Files saved to: {TRANSCRIPTS_DIR}")
