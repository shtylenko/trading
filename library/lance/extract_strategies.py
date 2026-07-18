#!/usr/bin/env python3
"""Extract strategy explanations from Lance Breitstein's transcripts and compile into a reference file."""
import os, json, re

TRANSCRIPTS_DIR = "/Users/shtylenko/Projects/trading/library/lance/transcripts"
VIDEOS_PATH = "/Users/shtylenko/Projects/trading/library/lance/lance_videos.json"
OUTPUT_PATH = "/Users/shtylenko/Projects/trading/library/lance/lance_strategies.md"

# Load video metadata
with open(VIDEOS_PATH) as f:
    videos = json.load(f)

video_by_id = {v["video_id"]: v for v in videos}

def read_transcript(video_id):
    """Read transcript file content."""
    path = os.path.join(TRANSCRIPTS_DIR, f"{video_id}.txt")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return ""

def get_video_url(video_id):
    return f"https://youtube.com/watch?v={video_id}"

def fmt_link(video_id):
    v = video_by_id.get(video_id, {})
    title = v.get("title", "Unknown")
    return f"[{title}]({get_video_url(video_id)})"

# ====== DEFINE ALL STRATEGIES LANCE TALKS ABOUT ======

strategies = [
    # Each entry: (strategy_name, [video_ids], extraction_keywords)
    
    ("No Man's Land Trading", 
     ["FMxPiKlZuvM", "40Ib2P4_1SE", "K-t2XreQuUM"],
     ["no man'", "no man", "nomansland"]),
    
    ("Right Side of the \"V\" Strategy",
     ["wtQIj6Apiq0"],
     ["right side of the v", "right side of the V"]),
    
    ("Scalping Trading Strategies (3 Strategies)",
     ["2DXQqwKSwJE"],
     ["scalping"]),
    
    ("Swing Trading Strategies (2 Strategies)",
     ["k-X0164r66U"],
     ["swing trade"]),
    
    ("Trend Trading",
     ["ZOHG-OnQuos"],
     ["trend"]),
    
    ("Anchored VWAP Edge",
     ["D2P-0xh6aEM"],
     ["anchored vwap", "anchored vwop"]),
    
    ("Bollinger Band Edge",
     ["ZZ-e9wxARSI"],
     ["bollinger", "bollinger"]),
    
    ("ORB (Opening Range Breakout) Trading",
     ["9Mr2dSi-EEc"],
     ["ORB", "opening range"]),
    
    ("Momentum Trading (Reacting to Ross Cameron)",
     ["sxjsqauWE9E"],
     ["momentum"]),
    
    ("Moving Average Trading (Reacting to Qullamaggie)",
     ["H01JbbEY7ac"],
     ["moving average", "qullamaggie"]),
    
    ("Trendline Trading (Reacting to Tori Trades)",
     ["62qSFeXa9z0"],
     ["trendline"]),
    
    ("IPO Trading Strategies (4 Strategies)",
     ["HAlYMtluzCk"],
     ["ipo"]),
    
    ("The Bobblehead Method",
     ["TexislSXpjs"],
     ["bobblehead"]),
    
    ("Playbook Trading & Building a Trading System",
     ["46PUq3WymmI", "_jWWfY_pesY"],
     ["playbook"]),
    
    ("Trade Sizing Strategy",
     ["ABzXM-9LonM"],
     ["sizing", "size"]),
    
    ("Risk Management Strategy",
     ["gb7nNveNBjg", "51l76HdSpV0"],
     ["risk management"]),
    
    ("Expected Value & Trade Selection",
     ["44D9z2YqgxE"],
     ["expected value", "expected"]),
    
    ("Fibonacci Trading",
     ["FHo1qxHRG98"],
     ["fibonacci"]),
    
    ("Multi-Timeframe Analysis",
     ["V-3owTiHmhw"],
     ["timeframe", "multi-timeframe", "multiple time"]),
    
    ("MACD Trading",
     ["q-jwEXbNSBs"],
     ["MACD"]),
    
    ("Options Selling Strategy (4 Golden Rules)",
     ["eWeGAYvjxh4", "IkM7vbbSVvU", "k6I04ciE1KE"],
     ["option"]),
    
    ("News Trading",
     ["eDdpTNB04ws"],
     ["news"]),
    
    ("Level 2 / Tape Reading",
     ["RKV1rncXSkg"],
     ["level 2", "tape"]),
    
    ("Prediction Market Trading Playbook",
     ["DtSLXf78gZo"],
     ["prediction market"]),
    
    ("In-Play Stock Selection",
     ["7FbTZZNljSo"],
     ["in-play", "inplay", "broken slot"]),
    
    ("Trade Review System (3-Step)",
     ["hC4g7qY6UcQ"],
     ["review", "reviewing"]),
    
    ("Trading Hotkeys",
     ["5iyme1n6dvs"],
     ["hotkey"]),
    
    ("Trading with Fundamentals vs Technicals",
     ["IA_THHFgHaw"],
     ["fundamental", "technicals disagree"]),
    
    ("2026 Trading Gameplan (Annual Process)",
     ["RgztJHUBRjE"],
     ["gameplan", "game plan"]),
    
    ("Constraint Analysis (4 Constraints)",
     ["3sug7e1AYk8"],
     ["constraint"]),
    
    ("The 3 Real Reasons Why 95% of Traders Fail",
     ["9BIaQ9FQ8r4"],
     ["95%", "fail"]),
    
    ("The Psychological Reality of Trading",
     ["UWoXBLAXHEY"],
     ["psychology", "psychological"]),
    
    ("Geopolitical Risk Premium Trading (Oil)",
     ["fz1ut4_GJB0"],
     ["geopolitical", "oil"]),
    
    ("Crypto / Memecoin Trading",
     ["ecfWIiTZ0V4"],
     ["crypto", "memecoin", "meme"]),
]

def extract_strategy_text(transcript, keywords):
    """Find the most relevant section of the transcript for a given strategy."""
    lines = transcript.split('\n')
    # Find lines that mention the keyword
    relevant_sections = []
    current_section = []
    in_relevant = False
    
    for i, line in enumerate(lines):
        lower_line = line.lower()
        if any(kw.lower() in lower_line for kw in keywords):
            if not in_relevant:
                # Start of relevant section - include some context before
                current_section = lines[max(0, i-2):i]
                in_relevant = True
            current_section.append(line)
        else:
            if in_relevant:
                if len(current_section) > 5 and i > 0:
                    # End of section - add 5 more lines for closure
                    current_section.extend(lines[i:min(len(lines), i+5)])
                    relevant_sections.append('\n'.join(current_section))
                current_section = []
                in_relevant = False
    
    if in_relevant and current_section:
        relevant_sections.append('\n'.join(current_section))
    
    return relevant_sections

def clean_text(text):
    """Clean up transcript text for readability."""
    text = re.sub(r'\[music\]', '', text)
    text = re.sub(r'\[__\]', '', text)
    text = re.sub(r'\(\)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Build the strategies document
output = []
output.append("# Lance Breitstein (TheOneLanceB) — Trading Strategies Reference\n")
output.append(f"Compiled from {len(os.listdir(TRANSCRIPTS_DIR))} video transcripts of TheOneLanceB YouTube channel.\n")
output.append(f"Lance Breitstein is a former Trillium top trader with $100M+ verified profits, profiled in Jack Schwager's upcoming Market Wizards: The Next Generation. He mentors traders at SMB Capital and has trained dozens of 6-7 figure P&L traders.\n")
output.append("---\n")

for sname, vid_ids, keywords in strategies:
    output.append(f"\n## {sname}\n")
    
    video_links = []
    for vid in vid_ids:
        if vid in video_by_id:
            v = video_by_id[vid]
            video_links.append(fmt_link(vid))
    
    if video_links:
        output.append(f"**Videos:** {' | '.join(video_links)}\n")
    
    # Extract content from transcripts
    all_text_parts = []
    for vid in vid_ids:
        transcript = read_transcript(vid)
        if transcript:
            # Find the strategy explanation part
            sections = extract_strategy_text(transcript, keywords)
            if sections:
                # Take the most substantial section
                best = max(sections, key=len)
                cleaned = clean_text(best[:3000])  # Limit to ~3000 chars
                all_text_parts.append(cleaned)
            else:
                # Fallback: take first 2000 chars after title
                clean = clean_text(transcript[200:2000])
                all_text_parts.append(clean)
    
    if all_text_parts:
        combined = ' '.join(all_text_parts)
        # Trim to a reasonable size (about 1200-2000 chars)
        if len(combined) > 2000:
            # Try to break at sentence boundary
            trimmed = combined[:2000]
            last_period = trimmed.rfind('.')
            if last_period > 500:
                trimmed = trimmed[:last_period+1]
            combined = trimmed
        output.append(f"{combined}\n")
    else:
        output.append("*Transcript not available or strategy not found in transcript.*\n")
    
    output.append("---\n")

# Add a "concepts not strategies" section for key principles
output.append("\n## Key Trading Principles (Non-Strategy Concepts)\n\n")
principles = [
    ("In-Play Stock Selection", "7FbTZZNljSo", "Lance only trades stocks that are 'in-play' — stocks with high relative volume, a catalyst (news/earnings/sector move), and institutional interest. He compares this to finding broken slot machines at a casino where the player has the edge. Most stocks have no edge; in-play stocks are where professional traders concentrate their attention."),
    ("The 3 Real Reasons Why 95% of Traders Fail", "9BIaQ9FQ8r4", "1) No runway — they don't give themselves enough time to learn (expects 4-5 years minimum part-time). 2) Unrealistic expectations — they try to monetize before they're competent. 3) No structure/mentorship — they try to learn alone without a framework."),
    ("4 Constraints Limiting Your Trading", "3sug7e1AYk8", "The four constraints most beginners face: (1) Stock selection — they trade S&P 500 when they should trade in-play stocks. (2) No system to capture plays. (3) Don't know where to find plays with edge. (4) No effective daily routine or trading pod."),
    ("Expected Value (EV) Thinking", "44D9z2YqgxE", "Lance emphasizes optimizing for expected value, not percentage moves. Trading is probabilistic — every setup has an EV based on win rate × average win / average loss. Beginners should chase positive EV setups, not home runs."),
    ("The Playbook Concept", "46PUq3WymmI", "A trading playbook is a documented set of setups with specific entry/exit rules, risk parameters, and market conditions. Lance says building a playbook is the most important thing a developing trader can do — it codifies your edge into repeatable actions."),
    ("Multi-Timeframe Analysis", "V-3owTiHmhw", "Lance emphasizes aligning multiple timeframes: the daily chart for direction/trend, the intraday chart for entries. He credits Brian Shannon's book on this concept as foundational to his success."),
    ("Sleep & Trading Performance", "q-jwEXbNSBs", "Lance has a dedicated video on how sleep quality directly impacts trading profitability. He cites research on cognitive decline from sleep deprivation and its effects on decision-making, risk assessment, and discipline."),
    ("Trading Psychology from Dr. Jonathan Katz", "jkzZiOZCsZ0", "Key rules: (1) Prevent tilt proactively — once you're angry it's too late. (2) Emotional regulation is a skill that must be trained. (3) Identify personal triggers and remove them from your environment. (4) The best traders separate self-worth from P&L."),
    ("Stop Losses: Don't Guess", "mdCzn7n4ODc", "Lance argues against arbitrary stop losses. Instead, stops should be placed at levels that would invalidate the thesis for the trade — below support for longs, above resistance for shorts. A stop should mean 'my analysis was wrong', not 'I can't take the heat.'"),
    ("Why Your First Few Years of P&L Don't Matter", "EgFXjEpSy50", "Lance's key principle: early trading P&L is noise, not signal. The first few years should be about process-building, not profits. Skill compounds over time — focus on building a repeatable edge, not the dollar amount in your account."),
    ("Trading Drawdowns: Step-by-Step", "zLtBTyJvrO8", "Lance's process: (1) Stop trading immediately when drawdown hits threshold. (2) Review last 20 trades to find the pattern. (3) Reduce size by 50%. (4) Fix the specific issue before scaling back up. (5) Never try to trade your way out of a drawdown."),
    ("Do THIS After Every Winning Trade", "nNy5J8ByBVc", "Lance emphasizes reviewing winning trades just as carefully as losers. Winners can embed bad habits that happen to work out. The 3-step review: (1) Did I follow my rules? (2) Was I lucky or good? (3) What would I do differently?"),
]

for pname, pvid, pdesc in principles:
    output.append(f"\n### {pname}\n")
    v = video_by_id.get(pvid, {})
    output.append(f"**Video:** [{v.get('title', pname)}](https://youtube.com/watch?v={pvid})\n\n")
    output.append(f"{pdesc}\n")

# Write the file
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write('\n'.join(output))

print(f"Written to {OUTPUT_PATH}")
print(f"Total strategies documented: {len(strategies)}")
print(f"Total principles documented: {len(principles)}")
