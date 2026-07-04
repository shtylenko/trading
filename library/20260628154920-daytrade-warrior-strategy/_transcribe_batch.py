import sys, json, re, os, time
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

OUT_DIR = "/Users/shtylenko/Hermes/deep_research/20260628154920-daytrade-warrior-strategy"
os.makedirs(f"{OUT_DIR}/transcripts", exist_ok=True)
api = YouTubeAPI()

with open(f"{OUT_DIR}/_last100_videos.json") as f:
    videos = json.load(f)

# Phase 1: Resolve actual titles. 
print("="*60)
print("PHASE 1: Resolving titles for all 100 videos")
print("="*60)

title_map = {}
for i, v in enumerate(videos):
    vid = v["video_id"]
    details = api.get_video_details(vid)
    vd = details.get('video_details', {})
    title = vd.get('title', 'UNKNOWN')
    title_map[vid] = title
    videos[i]["resolved_title"] = title
    videos[i]["view_count"] = vd.get('view_count', v.get('view_count', 0))
    videos[i]["channel_title"] = vd.get('channel_title', '')
    transcript_info = details.get('transcript')
    videos[i]["has_transcript_url"] = 1 if (transcript_info and transcript_info.get('transcript_url')) else 0
    videos[i]["transcript_url"] = transcript_info.get('transcript_url', '') if transcript_info else ''
    if (i+1) % 10 == 0:
        print(f"  [{i+1}/100] Resolved {len(title_map)} titles...")
    time.sleep(0.3)

# Save resolved titles
with open(f"{OUT_DIR}/_resolved_videos.json", "w") as f:
    json.dump(videos, f, indent=2, default=str)

print(f"\nTitles resolved. Videos with transcript URLs: {sum(1 for v in videos if v.get('has_transcript_url'))}/{len(videos)}")
print()

# Phase 2: Transcribe all videos
print("="*60)
print("PHASE 2: Batch transcription")
print("="*60)

results = []
for i, v in enumerate(videos):
    vid = v["video_id"]
    title = v.get("resolved_title", v.get("title", "UNKNOWN"))
    transcript_url = v.get("transcript_url", "")
    
    print(f"[{i+1}/100] {vid} - {title[:70]}")
    
    if not transcript_url:
        print(f"  SKIP: No transcript URL")
        results.append({"vid": vid, "title": title, "status": "NO_URL"})
        continue
    
    # First attempt
    text = api.transcribe_video(transcript_url)
    
    # Retry with exponential backoff for 403/'Retry' errors
    attempt = 0
    max_attempts = 3
    while isinstance(text, dict) and (text.get('code') == 403 or str(text.get('error', '')).lower() == 'retry') and attempt < max_attempts:
        attempt += 1
        delay = [3, 8, 15][attempt - 1] if attempt <= 3 else 15
        print(f"  Retry {attempt}/{max_attempts} in {delay}s (error: {text})...")
        time.sleep(delay)
        text = api.transcribe_video(transcript_url)
    
    if isinstance(text, dict) and 'raw_text' in text:
        content = text['raw_text']
        if len(content) > 100:
            safe = re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:60]
            fpath = f"{OUT_DIR}/transcripts/transcript_{vid}_{safe}.txt"
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(f"Title: {title}\n")
                f.write(f"Channel: {v.get('channel_title', '')}\n")
                f.write(f"Views: {v.get('view_count', '')}\n")
                f.write(f"URL: https://youtube.com/watch?v={vid}\n")
                f.write("="*70 + "\n\n")
                f.write(content)
            results.append({"vid": vid, "title": title, "status": "OK", "chars": len(content)})
            print(f"  OK: {len(content)} chars")
        else:
            results.append({"vid": vid, "title": title, "status": "TOO_SHORT", "chars": len(content)})
            print(f"  TOO_SHORT: {len(content)} chars")
    else:
        results.append({"vid": vid, "title": title, "status": "FAIL", "error": str(text)})
        print(f"  FAIL: {text}")
    
    # Save partial progress
    with open(f"{OUT_DIR}/_transcribe_progress.json", "w") as f:
        json.dump({
            "completed": i+1, 
            "total": len(videos), 
            "ok": len([r for r in results if r['status'] == 'OK']),
            "fail": len([r for r in results if r['status'] != 'OK']),
            "results": results
        }, f, indent=2)
    
    time.sleep(0.5)

# Final summary
ok = [r for r in results if r['status'] == 'OK']
fail = [r for r in results if r['status'] != 'OK']
print()
print("="*60)
print("FINAL SUMMARY")
print("="*60)
print(f"  Total: {len(results)}")
print(f"  OK: {len(ok)} ({sum(r.get('chars',0) for r in ok)} chars)")
print(f"  Failed: {len(fail)}")
for r in fail:
    print(f"    {r['vid']}: {r['status']} - {r.get('error', '')}")

with open(f"{OUT_DIR}/_transcribe_summary.json", "w") as f:
    json.dump({"results": results}, f, indent=2)
