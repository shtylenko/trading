#!/usr/bin/env python3
"""YouTube research: PORTFOLIO CONSTRUCTION / REBALANCING (5 keywords, 20 videos each)."""

import sys, os, json, re, time
sys.path.insert(0, '/Users/shtylenko/Projects/ytmcp')
from ytapi import YouTubeAPI

BASE_DIR = "/Users/shtylenko/Hermes/projects/trading_strategy_finder/engine/strategy_lab/strategies/xsec_momentum/peer-feedback/2026-06-17-keyword-research"
SAVE_DIR = os.path.join(BASE_DIR, "transcripts", "portfolio_rebalancing")
os.makedirs(SAVE_DIR, exist_ok=True)

KEYWORDS = {
    "rebalancing_frequency": "momentum portfolio rebalancing frequency",
    "overlapping_portfolios_jegadeesh": "momentum overlapping portfolios Jegadeesh",
    "vol_scaling_barroso_santa_clara": "volatility scaling momentum risk-managed momentum Barroso Santa-Clara",
    "crash_risk_daniel_moskowitz": "momentum crash risk dynamic Daniel Moskowitz",
    "equal_vs_value_weight": "equal weight vs value weight momentum portfolio"
}

api = YouTubeAPI()

def sf(kw, vid, title):
    return f"{kw}_{vid}_{re.sub(r'[^a-zA-Z0-9_-]', '_', title)[:60]}.txt"

def tx(url, mr=3):
    for a, d in enumerate([3, 8, 15]):
        try:
            t = api.transcribe_video(url)
            if isinstance(t, dict) and 'raw_text' in t: return t['raw_text']
            if isinstance(t, dict) and t.get('error') == 'Retry':
                if a < mr - 1: time.sleep(d)
                else: return "[RETRY EXHAUSTED]"
            else: return f"[UNEXPECTED]"
        except Exception as e:
            if a < mr - 1: time.sleep(d)
            else: return f"[ERROR: {str(e)[:120]}]"
    return "[FAILED]"

results = {}
for kw_key, kw_query in KEYWORDS.items():
    print(f"\n{'='*60}\nSEARCHING: {kw_query}")
    try:
        r = api.search_videos(kw_query, max_results=20)
    except Exception as e:
        print(f"  FAILED: {e}")
        results[kw_query] = {"status": "FAIL", "videos": [], "ok": 0}
        continue
    videos = r.get("data", [])
    print(f"  Found {len(videos)}")
    ok_count, vlist = 0, []
    for idx, v in enumerate(videos[:20]):
        vid, title, channel, views = v.get("video_id",""), v.get("title",""), v.get("channel",""), v.get("view_count",0)
        if not vid: continue
        print(f"  [{idx+1}/20] {title[:70]} ({channel})")
        try: details = api.get_video_details(vid)
        except: continue
        ti = details.get("transcript")
        transcript = ""
        transcribed = False
        if ti and ti.get("transcript_url"):
            transcript = tx(ti["transcript_url"])
            if transcript and not transcript.startswith("["):
                transcribed = True; ok_count += 1
                print(f"    ✓ ({len(transcript)} chars)")
            else: print(f"    ✗")
        else: print(f"    - no url"); transcript = "[NO TRANSCRIPT]"
        with open(os.path.join(SAVE_DIR, sf(kw_key, vid, title)), 'w') as f:
            f.write(f"TITLE: {title}\nURL: https://youtube.com/watch?v={vid}\nCHANNEL: {channel}\nVIEWS: {views}\nKEYWORD: {kw_query}\n{'='*70}\n\n{transcript}")
        vlist.append({"vid": vid, "title": title, "channel": channel, "views": views, "ok": transcribed})
    results[kw_query] = {"ok": ok_count, "videos": vlist}
    print(f"  => {ok_count}/{len(vlist)} transcribed")
    time.sleep(0.5)

with open(os.path.join(SAVE_DIR, "_FINDINGS.md"), 'w') as f:
    f.write("# Portfolio Construction / Rebalancing — YouTube Research Findings\n\nGenerated: 2026-06-17\n\n")
    total_ok = sum(r["ok"] for r in results.values())
    f.write(f"Total transcribed: {total_ok}\n\n")
    for kw, info in results.items():
        f.write(f"## {kw}\n\n")
        if info.get("status") == "FAIL": f.write("FAILED\n\n"); continue
        f.write(f"Transcribed: {info['ok']}/{len(info['videos'])}\n\n")
        f.write("| # | Title | Channel | OK |\n|---|---|---|---|\n")
        for i, v in enumerate(info["videos"][:20], 1):
            f.write(f"| {i} | {v['title'][:60]} | {v['channel'][:25]} | {'✓' if v['ok'] else '✗'} |\n")
        f.write("\n")

print(f"\nDONE! Transcribed {total_ok} videos total")
