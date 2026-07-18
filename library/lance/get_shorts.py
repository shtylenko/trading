#!/usr/bin/env python3
"""Extract ALL shorts from TheOneLanceB channel, save metadata + transcribe."""
import sys, json, os, time, http.client
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')

from ytapi import YouTubeAPI

OUTPUT_DIR = "/Users/shtylenko/Projects/trading/library/lance"
TRANSCRIPTS_DIR = os.path.join(OUTPUT_DIR, "transcripts")
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

api = YouTubeAPI()
cid = 'UCzksXiC-Ju-DTIZmMiaOVfQ'

# Load existing data
videos_path = os.path.join(OUTPUT_DIR, "lance_videos.json")
with open(videos_path) as f:
    existing = json.load(f)
existing_ids = {v['video_id'] for v in existing if isinstance(v, dict) and 'video_id' in v}
print(f"Existing videos: {len(existing_ids)}")

# Paginate through all shorts
print("Fetching all shorts...")
all_shorts = []
token = None

while True:
    headers = {'x-rapidapi-key': api.api_key, 'x-rapidapi-host': api.host}
    path = f'/channel/shorts?id={cid}'
    if token:
        path += f'&token={token}'
    
    conn = http.client.HTTPSConnection(api.host, timeout=20)
    conn.request('GET', path, headers=headers)
    res = conn.getresponse()
    raw_data = json.loads(res.read().decode('utf-8'))
    
    for item in raw_data.get('data', []):
        if item.get('type') == 'shorts':
            all_shorts.append(item)
    
    cont = raw_data.get('continuation')
    if not cont:
        break
    token = cont
    time.sleep(0.5)

print(f"Found {len(all_shorts)} shorts total")

# Get details + transcript URLs for all shorts in batches
shorts_with_transcripts = []
shorts_without = []

for i, s in enumerate(all_shorts):
    vid = s.get('videoId', '')
    if not vid:
        continue
    
    # Check if already in our set
    if vid in existing_ids:
        continue
    
    try:
        details = api.get_video_details(vid)
        if 'video_details' in details:
            vd = details['video_details']
            transcript_info = details.get('transcript')
            transcript_url = transcript_info.get('transcript_url') if transcript_info else None
            
            entry = {
                'video_id': vid,
                'title': vd.get('title', s.get('title', '')),
                'view_count': vd.get('view_count', 0),
                'published_date': vd.get('published_date', ''),
                'duration': vd.get('duration', ''),
                'url': f"https://youtube.com/watch?v={vid}",
                'is_short': True,
                'details': {
                    'channel_title': vd.get('channel_title', ''),
                    'has_transcript': vd.get('has_transcript', False),
                },
                'transcript_url': transcript_url,
            }
            
            if transcript_url:
                shorts_with_transcripts.append(entry)
            else:
                shorts_without.append(entry)
        else:
            # Still add even without details
            entry = {
                'video_id': vid,
                'title': s.get('title', ''),
                'view_count': 0,
                'url': f"https://youtube.com/watch?v={vid}",
                'is_short': True,
            }
            shorts_without.append(entry)
    except Exception as e:
        print(f"  Error getting details for {vid}: {e}")
    
    if (i+1) % 50 == 0:
        print(f"  Details: {i+1}/{len(all_shorts)} - {len(shorts_with_transcripts)} with transcripts")

print(f"\nShorts with transcripts: {len(shorts_with_transcripts)}")
print(f"Shorts without transcripts: {len(shorts_without)}")

# Save shorts metadata separately
metadata_path = os.path.join(OUTPUT_DIR, "lance_shorts.json")
with open(metadata_path, "w", encoding="utf-8") as f:
    json.dump({
        "channel_id": cid,
        "channel_name": "TheOneLanceB",
        "total_shorts": len(all_shorts),
        "with_transcripts": len(shorts_with_transcripts),
        "shorts": shorts_with_transcripts + shorts_without,
    }, f, indent=2, ensure_ascii=False)
print(f"Saved shorts metadata to {metadata_path}")

# Also update main videos JSON to include shorts
existing_entries = [v for v in existing if isinstance(v, dict) and 'video_id' in v]
existing_entries.extend(shorts_with_transcripts)
existing_entries.extend(shorts_without)

# Update channel metadata at top
meta_entry = {'_meta': {
    'channel_id': cid,
    'channel_name': 'TheOneLanceB',
    'channel_url': 'https://www.youtube.com/channel/' + cid,
    'total_api_video_count': len(existing_entries),
    'regular_videos': 130,
    'shorts': len(all_shorts),
}}
existing_entries.insert(0, meta_entry)

with open(videos_path, "w", encoding="utf-8") as f:
    json.dump(existing_entries, f, indent=2, ensure_ascii=False)
print(f"Updated main JSON with {len(existing_entries)-1} total entries")

# Now transcribe all shorts
print(f"\nTranscribing {len(shorts_with_transcripts)} shorts...")
progress_path = os.path.join(OUTPUT_DIR, "shorts_transcribe_progress.json")
done_ids = set()
if os.path.exists(progress_path):
    with open(progress_path) as f:
        prog = json.load(f)
    done_ids = set(prog.get("done", []))

ok = len(done_ids)
for i, s in enumerate(shorts_with_transcripts):
    vid = s['video_id']
    if vid in done_ids:
        continue
    
    transcript_path = os.path.join(TRANSCRIPTS_DIR, f"{vid}.txt")
    if os.path.exists(transcript_path) and os.path.getsize(transcript_path) > 50:
        done_ids.add(vid)
        ok += 1
        continue
    
    url = s.get('transcript_url')
    if not url:
        continue
    
    for attempt in range(3):
        try:
            result = api.transcribe_video(url, use_cache=True)
            if 'raw_text' in result and result['raw_text']:
                text = result['raw_text']
                title = s.get('title', 'Shorts')
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(f"Title: {title}\n")
                    f.write(f"URL: https://youtube.com/watch?v={vid}\n")
                    f.write(f"{'='*70}\n\n")
                    f.write(text)
                done_ids.add(vid)
                ok += 1
                break
            elif 'Retry' in str(result.get('error', '')):
                time.sleep([2, 5, 10][attempt])
        except Exception as e:
            time.sleep(2)
    
    if (i+1) % 50 == 0:
        print(f"  Transcribed: {ok}/{len(shorts_with_transcripts)}")

# Save progress
with open(progress_path, "w") as f:
    json.dump({"done": list(done_ids)}, f)

print(f"\nDone! Total shorts transcribed: {ok}/{len(shorts_with_transcripts)}")
