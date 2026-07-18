#!/usr/bin/env python3
"""Merge API-found and browser-found video IDs, then get details + transcripts."""
import sys, json, re, os, time
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

OUTPUT_DIR = "/Users/shtylenko/Projects/trading/library/lance"
api = YouTubeAPI()

# Load API-found videos
api_path = os.path.join(OUTPUT_DIR, "lance_videos.json")
with open(api_path) as f:
    api_videos = json.load(f)

# Browser-found IDs
browser_ids = [
    "62qSFeXa9z0","27cXk34t1gI","sxjsqauWE9E","H01JbbEY7ac","D2P-0xh6aEM","gb7nNveNBjg","_jWWfY_pesY","IwH5KOmkzZk","dYTifFG2SQY","2DXQqwKSwJE","87iSNJsb05U","ZOHG-OnQuos","tIB72PAeZLU","2MV6KYt8aKc","IkM7vbbSVvU","ZZ-e9wxARSI","k-X0164r66U","KeGZ7SoAc_k","38I-7tyBW2Y","bkwY7mBnu4Y","CXVNoBvjDpA","ztHVl9xNTS8","wtQIj6Apiq0","JlkOv61DgiE","SUrlJ8xzTg4","k_tdZk5XFBE","R5ZT8ozRLhw","vKy6Q9hwon4","PdLgzRipSD8","o7DfwJTC_Ow","WgRQWJq54OY","KxciCiwoqb8","4MCX8v1Vh88","bKvEfCGJS4g","spUZ7eO3LsE","t271JDePfYk","9w2jDlj6nmM","F-ZktuFvk0E","FglEMWycX9Q","eDdpTNB04ws","QmPUp9ISuDw","RBPs7Ld_Vms","fCp6CRu6E5Y","fpwQd__kGSQ","scb8zkhV8fU","FHo1qxHRG98","3vZYjW6aa6o","nNy5J8ByBVc","k6I04ciE1KE","i8NgzZgc5L4","eaK6yi-d8No","zLtBTyJvrO8","5wxNwS-FtZQ","3GnU70gQWus","iWwuAHGEtvQ","-ZV_EpqmUDQ","V-3owTiHmhw","RKV1rncXSkg","2EBJxiRwGGk","hC4g7qY6UcQ","5VeNsfIkfc0","QoQQvgeoZKE","9Mr2dSi-EEc","RgztJHUBRjE","7FbTZZNljSo","9BIaQ9FQ8r4","QP5HohzDGww","mdCzn7n4ODc","hBKjhqCes-I","VwMkhCzcpjU","EgFXjEpSy50","jkzZiOZCsZ0","_OhwIJdSyfI","hSnu9-cpdeY","eWeGAYvjxh4","U9UZ2U6bozQ","AVoMjAebyB4","dGjqaXTeiTU","9WqaZ_4Cld0","u1sabe0nlyo","ecfWIiTZ0V4","ppBeFX_YXvo","ABzXM-9LonM","KvH7MtRzGb4","q-jwEXbNSBs","f_q4gVowr_k","TexislSXpjs","TzLtTTcDp9M","2IhvsSaeJ64","-x1nbxasFcE","L5C4vO-SH5w","HAlYMtluzCk","9EEUa618xQw","TNcg7Ol7AKM","EUrA84h9K-Q","pvH7D8AGILA","iSaM1EVSfQQ","e8QlnXoiFGU","IA_THHFgHaw","VbR6AwBNmhI","7mT848jyG-w","5qIM0B1-lnM","yXgNylCE4u0","UWoXBLAXHEY","_L5FUIAI6oE","1jrcIjoC1s0","vGqaqTUxMG4","5R96Bmohltk","fz1ut4_GJB0","7867ICeHG7Y","Vv-4YtLg2sA","U5B1Hx0DSuo","a6yHjEsaMq8","5iyme1n6dvs","mjfONTBf6M0","L9wDpozjCtY","DtSLXf78gZo","ot1fjFGcsrc","cQLWD0NDseQ","nlsR9cpXy3E","XOLulRRnekU","K-t2XreQuUM","3sug7e1AYk8","ZJzpy-iiQR4","97cClZqDOwA","jMb5NzbHkvA","iOKYz1Jo4ZY","-vzpA1P2aBk","mcU13nJfyK4","2ep7sUKCfAI"
]

# Merge: browser IDs win if they exist, API IDs fill in
seen = set()
merged = []
browser_set = set(browser_ids)
api_by_id = {v["video_id"]: v for v in api_videos}

# First add all browser IDs (with API data if available)
for vid in browser_ids:
    if vid in api_by_id:
        merged.append(api_by_id[vid])
    else:
        merged.append({"video_id": vid, "title": "", "view_count": 0, "url": f"https://youtube.com/watch?v={vid}"})
    seen.add(vid)

# Then add API videos not in browser list
for v in api_videos:
    if v["video_id"] not in seen:
        merged.append(v)
        seen.add(v["video_id"])

print(f"Merged {len(merged)} unique videos (browser: {len(browser_ids)}, API: {len(api_videos)}, new from API: {len(merged)-len(browser_ids)})")

# Sort by view_count
merged.sort(key=lambda v: v.get("view_count", 0), reverse=True)

with open(api_path, "w", encoding="utf-8") as f:
    json.dump(merged, f, indent=2, ensure_ascii=False)

print(f"Saved {len(merged)} to lance_videos.json")
print(f"\nNow getting video details + transcript URLs for all...")

# Phase 2: Get video details and transcript URLs for each
details_dir = os.path.join(OUTPUT_DIR, "details")
os.makedirs(details_dir, exist_ok=True)

success_count = 0
no_transcript = 0
error_count = 0

for i, v in enumerate(merged):
    vid = v["video_id"]
    details_path = os.path.join(details_dir, f"{vid}.json")
    
    # Skip if already fetched
    if os.path.exists(details_path):
        with open(details_path) as f:
            d = json.load(f)
        if "video_details" in d:
            success_count += 1
            continue
    
    try:
        details = api.get_video_details(vid)
        if "video_details" in details:
            v["title"] = details["video_details"].get("title", v.get("title", ""))
            v["details"] = {
                "channel_title": details["video_details"].get("channel_title", ""),
                "view_count": details["video_details"].get("view_count", 0),
                "published_date": details["video_details"].get("published_date", ""),
                "duration": details["video_details"].get("duration", ""),
                "has_transcript": details["video_details"].get("has_transcript", False),
            }
            transcript = details.get("transcript")
            if transcript and transcript.get("transcript_url"):
                v["transcript_url"] = transcript["transcript_url"]
                v["language_code"] = transcript.get("language_code", "en")
                success_count += 1
            else:
                v["transcript_url"] = None
                no_transcript += 1
            
            with open(details_path, "w", encoding="utf-8") as f:
                json.dump(details, f, indent=2, ensure_ascii=False)
        else:
            error_count += 1
            print(f"  ERROR {vid}: {details.get('error', 'unknown')}")
    except Exception as e:
        error_count += 1
        print(f"  EXCEPTION {vid}: {e}")
    
    if (i+1) % 20 == 0:
        print(f"  Details: {i+1}/{len(merged)} - OK:{success_count} NoTrans:{no_transcript} Err:{error_count}")
    time.sleep(0.3)

print(f"\nDetails summary: {success_count} OK, {no_transcript} no transcript, {error_count} errors")

# Save updated video list
with open(api_path, "w", encoding="utf-8") as f:
    json.dump(merged, f, indent=2, ensure_ascii=False)

print(f"Updated video list saved")

# Print videos with transcript URLs available
available = [v for v in merged if v.get("transcript_url")]
print(f"\nVideos with available transcripts: {len(available)}/{len(merged)}")
print("Top 10 by views:")
for v in available[:10]:
    print(f"  [{v.get('view_count',0):>8,}] {v.get('title','')[:70]}")
