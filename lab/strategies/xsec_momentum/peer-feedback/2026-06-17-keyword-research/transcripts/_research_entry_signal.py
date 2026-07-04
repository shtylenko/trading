#!/usr/bin/env python3
"""YouTube research: ENTRY / SIGNAL CONSTRUCTION (5 keywords, 20 videos each)."""

import sys, os, json, re, time
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

BASE_DIR = "/Users/shtylenko/Hermes/projects/trading_strategy_finder/engine/strategy_lab/strategies/xsec_momentum/peer-feedback/2026-06-17-keyword-research"
SAVE_DIR = os.path.join(BASE_DIR, "transcripts", "entry_signal")
os.makedirs(SAVE_DIR, exist_ok=True)

KEYWORDS = {
    "momentum_lookback_optimization": "momentum lookback period optimization",
    "momentum_skip_month_12_1": "momentum gap skip-month 12-1",
    "52w_high_george_hwang": "52-week high momentum strategy George Hwang",
    "path_dependent_momentum": "momentum path-dependent momentum smoothness",
    "idiosyncratic_ff3_residual": "idiosyncratic momentum FF3 residual"
}

api = YouTubeAPI()

def safe_filename(kw, vid, title):
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:60]
    return f"{kw}_{vid}_{safe}.txt"

def transcribe_with_retry(url, max_retries=3):
    delays = [3, 8, 15]
    for attempt in range(max_retries):
        try:
            text = api.transcribe_video(url)
            if isinstance(text, dict) and 'raw_text' in text:
                return text['raw_text']
            elif isinstance(text, dict) and text.get('error') == 'Retry':
                if attempt < max_retries - 1:
                    time.sleep(delays[attempt])
                    continue
                return f"[RETRY EXHAUSTED]"
            else:
                return f"[UNEXPECTED: {str(text)[:200]}]"
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(delays[attempt])
                continue
            return f"[ERROR: {str(e)[:200]}]"
    return "[FAILED]"

results = {}

for kw_key, kw_query in KEYWORDS.items():
    print(f"\n{'='*60}")
    print(f"SEARCHING: {kw_query}")
    
    try:
        r = api.search_videos(kw_query, max_results=20)
    except Exception as e:
        print(f"  FAILED: {e}")
        results[kw_query] = {"status": "FAIL", "videos": [], "ok": 0}
        continue
    
    videos = r.get("data", [])
    print(f"  Found {len(videos)} videos")
    ok_count = 0
    vlist = []
    
    for idx, v in enumerate(videos[:20]):
        vid = v.get("video_id", "")
        title = v.get("title", "Unknown")
        channel = v.get("channel", "Unknown")
        views = v.get("view_count", 0)
        if not vid:
            continue
        
        print(f"  [{idx+1}/20] {title[:70]} ({channel})")
        fname = safe_filename(kw_key, vid, title)
        fpath = os.path.join(SAVE_DIR, fname)
        
        try:
            details = api.get_video_details(vid)
        except:
            print(f"    NO DETAILS")
            continue
        
        ti = details.get("transcript")
        transcript = ""
        transcribed = False
        if ti and ti.get("transcript_url"):
            transcript = transcribe_with_retry(ti["transcript_url"])
            if transcript and not transcript.startswith("["):
                transcribed = True
                ok_count += 1
                print(f"    ✓ ({len(transcript)} chars)")
            else:
                print(f"    ✗ no transcript")
        else:
            print(f"    - no transcript url")
            transcript = "[NO TRANSCRIPT]"
        
        with open(fpath, 'w') as f:
            f.write(f"TITLE: {title}\nURL: https://youtube.com/watch?v={vid}\nCHANNEL: {channel}\nVIEWS: {views}\nKEYWORD: {kw_query}\n{'='*70}\n\n{transcript}")
        
        vlist.append({"vid": vid, "title": title, "channel": channel, "views": views, "ok": transcribed})
    
    results[kw_query] = {"status": "OK", "videos": vlist, "ok": ok_count}
    print(f"  => {ok_count}/{len(vlist)} transcribed")
    time.sleep(0.5)

# Write findings
with open(os.path.join(SAVE_DIR, "_FINDINGS.md"), 'w') as f:
    f.write("# Entry / Signal Construction — YouTube Research Findings\n\n")
    f.write("Generated: 2026-06-17\n\n")
    total_ok = sum(r["ok"] for r in results.values() if r["status"] == "OK")
    f.write(f"Total transcribed: {total_ok}\n\n")
    
    for kw, info in results.items():
        f.write(f"## {kw}\n\n")
        if info["status"] != "OK":
            f.write(f"Status: {info['status']}\n\n"); continue
        f.write(f"Transcribed: {info['ok']}/{len(info['videos'])}\n\n")
        f.write("| # | Title | Channel | Views | OK |\n|---|---|---|---|---|\n")
        for i, v in enumerate(info["videos"][:20], 1):
            f.write(f"| {i} | {v['title'][:60]} | {v['channel'][:30]} | {v['views']} | {'✓' if v['ok'] else '✗'} |\n")
        f.write("\n")

print(f"\nDONE! Transcribed {total_ok} videos total")
