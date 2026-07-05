#!/usr/bin/env python3
"""
build_canon.py

Produces a highly deduplicated "Trading Canon" reference from:
- The existing all_content_structured.md (narrative base)
- Retrieved excerpts in excerpts/*.md

Goal: one clean, authoritative, low-duplication document with
canonical statements + best verbatim + practical checklists.

Run after retrieve_excerpts.py.
"""

from pathlib import Path
import re
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
EXCERPTS = ROOT / "ross_cameron" / "excerpts"
STRUCTURED = ROOT / "ross_cameron" / "all_content_structured.md"
OUT = ROOT / "ross_cameron" / "ROSS_CAMERON_TRADING_CANON.md"

def load_text(p: Path) -> str:
    return p.read_text(errors="ignore") if p.exists() else ""

def extract_section(structured: str, header: str) -> str:
    """Pull a whole ## section from the structured doc."""
    pattern = rf"(## {re.escape(header)}.*?)(?=\n## |\Z)"
    m = re.search(pattern, structured, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""

def best_quote(excerpt_text: str, anchors: list[str]) -> str:
    """Return a short high-signal quote around anchors."""
    for a in anchors:
        if a.lower() in excerpt_text.lower():
            # crude: take ~400 chars around first hit
            idx = excerpt_text.lower().find(a.lower())
            start = max(0, idx - 180)
            end = min(len(excerpt_text), idx + 280)
            q = excerpt_text[start:end].strip()
            q = re.sub(r"\s+", " ", q)
            if len(q) > 60:
                return q[:450] + ("..." if len(q) > 450 else "")
    return ""

def main():
    structured = load_text(STRUCTURED)

    canon = []
    canon.append("# Ross Cameron — Trading Canon (Deduplicated Reference)")
    canon.append(f"\nGenerated: {datetime.now().isoformat(timespec='minutes')}")
    canon.append("Source: 428 transcripts + structured synthesis. Focused on canonical statements to minimize duplication.\n")

    # ========== STOCK SELECTION ==========
    canon.append("\n## 1. Stock Selection — The 5 Pillars (Canonical)")

    canon.append("""
**Canonical Rule (consistent across all major trainings):**
Trade only stocks that meet **all five** of the following on the current day:

1. **Price**: $2 – $20 (sweet spot $5–$10 for most accounts; small accounts may go as low as ~$1.50–$6).
2. **Percentage Gain Today**: Up at least 10% (many sources prefer >25% or leading gainer status).
3. **Relative Volume**: ≥ 5× average (minimum 2×; 5×+ is strongly preferred).
4. **Catalyst / News**: Breaking news or strong catalyst (FDA, earnings surprise, contract, etc.). Sector themes are secondary and riskier.
5. **Float**: < 20M shares in hot markets; < 10M (ideally < 5M) in cold markets. Lower is dramatically better.

If a stock fails any pillar, skip it. "If it's not obvious, there is no A-quality setup."
""")

    # Pull best quotes
    pillars_txt = load_text(EXCERPTS / "pillars.md") + load_text(EXCERPTS / "price_between.md") + load_text(EXCERPTS / "relative_volume.md")
    q1 = best_quote(pillars_txt, ["five pillars", "price", "2 and 20"])
    if q1:
        canon.append(f'\n> {q1}\n')

    canon.append("""
**Practical Scanner Checklist**
- Leading % gainers with high rel vol
- News headline in last 24–48h (or strong pre-market momentum)
- Low float confirmation (use Level 2 / float data)
- Avoid: >20–50M float, no catalyst, <2× rel vol, >$20–$50 (unless exceptional hot market)
""")

    # ========== RISK & SIZING ==========
    canon.append("\n## 2. Risk Management & Position Sizing")

    canon.append("""
**Icebreaker Rule (core innovation for consistency)**
- Start every day at **~25% of normal size** (your "icebreaker" trade).
- Only scale to full size **after** you have booked a meaningful profit milestone (commonly ~$1,000 on main account; scaled down for small accounts).
- If the day stays cold and you never hit the milestone → stay small all day.
- Result: small losses on bad days, full participation on good days. This mechanic supported long green streaks.

**Max Loss / Daily Risk**
- Hard daily max loss (commonly cited in $5k–$7.5k range on main account; scale to account size).
- "30-cent rule" is a common per-share risk reference on many setups (adjust by volatility and account).

**Walk-Away Rules (repeated across recaps and trainings)**
- Give back > ~half of your daily profit → strongly consider stopping.
- 3 sizable losses in a row → step away.
- No quality setup for a long time → walk away.
- Hit daily green goal → protect it; do not "keep going."

**Position Size Formula**
Shares = (Max $ risk you are willing to take on the trade) / (Risk per share to your stop)
""")

    ice = load_text(EXCERPTS / "icebreaker.md")
    q_ice = best_quote(ice, ["icebreaker", "quarter", "25%"])
    if q_ice:
        canon.append(f'\n> {q_ice}\n')

    # ========== ENTRIES ==========
    canon.append("\n## 3. Core Entry Patterns")

    canon.append("""
**Primary Pattern: First Candle New High / ACD-style Break**
- Stock in clear uptrend or strong momentum (higher highs/higher lows or powerful catalyst move).
- Pullback or consolidation (micro pullback or flat top).
- Entry: Buy the **first candle that makes a new high** after the pullback (often on 5-min chart). Enter on the break, do not wait for close.
- Stop: Below the low of the pullback/consolidation candle or a fixed $ risk (e.g. 30 cents).
- Confirmation: High relative volume + positive/expanding MACD helpful but keep indicators minimal.

**Micro Pullback**
- Especially useful in fast parabolic moves where classic deeper pullbacks never occur.
- Buy small dips in a strong runner that still respects the uptrend.
- Requires the stock to still meet the 5 pillars.

**Other High-Probability Entries**
- Red-to-Green moves into/after halts.
- VWAP reclaim after a washout ("sub-VWAP trap" — one of the favorites).
- Break of pre-market high or opening range in a leading gainer.
""")

    mp = load_text(EXCERPTS / "micro_pullback.md")
    q_mp = best_quote(mp, ["micro pullback"])
    if q_mp:
        canon.append(f'\n> {q_mp}\n')

    # ========== VWAP ==========
    canon.append("\n## 4. VWAP Setups (Key Variants)")

    canon.append("""
- **VWAP Support Bounce**: Strong stock pulls back to VWAP and curls up → buy the reclaim/support bounce.
- **Sub-VWAP Trap (favorite)**: Stock extends hard, washes out below VWAP (stops run), then reclaims VWAP with volume. High-probability long.
- VWAP as resistance (used for shorts, less common in his long-biased style).
""")

    # ========== MARKET REGIMES ==========
    canon.append("\n## 5. Market Regimes (Hot vs Cold)")

    canon.append("""
**Hot Market Playbook**
- Be aggressive once icebreaker succeeds.
- Multiple stocks can work; focus on the clearest, highest rel vol leaders.
- Size up more readily.

**Cold Market Playbook**
- Stay smaller, more selective.
- Wait for the very best (often news-driven) setups.
- Easier to walk away early.
- Protect the cushion built in prior hot periods.

He repeatedly emphasizes: "Be aggressive when the market is hot, foot off the gas when it's cooler."
""")

    # ========== DISCIPLINE & PSYCH ==========
    canon.append("\n## 6. Discipline & Psychology (Non-Negotiable)")

    canon.append("""
- Pre-trade daily checklist (sleep, emotional state, recent performance, prior day strength, scanners, FOMO level).
- Track your own metrics religiously (best price range, time of day, win rate by setup, etc.).
- "When in doubt, there is no doubt" — if it's not obvious, do not force it.
- Successful red day = loss within your rules + you stayed disciplined.
- Never average down on losers. Add only to winners (scaling in thirds is common).
""")

    # Footer
    canon.append("""
---

**Notes on this Canon**
- Extracted to minimize duplication while preserving the clearest statements and concrete numbers.
- Many concepts are taught with near-identical wording across "Ultimate Guide", "Full Training", and challenge series.
- Always verify against current market regime and your own account size/risk tolerance.
- Practice in simulator until the rules are automatic.
- Results are never typical. Risk management is the edge.

Sources: High-view training videos + systematic retrieval across 428 transcripts.
""")

    OUT.write_text("\n".join(canon))
    print(f"Wrote {OUT}")

if __name__ == "__main__":
    main()
