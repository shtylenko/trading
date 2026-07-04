#!/usr/bin/env python3
"""Regenerate exit_holding _FINDINGS.md from saved transcripts."""

import os, re, glob

SAVE_DIR = "/Users/shtylenko/Hermes/projects/trading_strategy_finder/engine/strategy_lab/strategies/xsec_momentum/peer-feedback/2026-06-17-keyword-research/transcripts/exit_holding"

# Group transcripts by keyword
files = sorted(os.listdir(SAVE_DIR))
keyword_groups = {}
for f in files:
    if f == "_FINDINGS.md" or f.endswith(".py"):
        continue
    # Parse keyword from filename
    kw_match = re.match(r'^([a-z_]+?)_', f)
    if kw_match:
        kw = kw_match.group(1)
        keyword_groups.setdefault(kw, []).append(f)

with open(os.path.join(SAVE_DIR, "_FINDINGS.md"), 'w') as out:
    out.write("# Exit / Holding Period — YouTube Research Findings\n\n")
    out.write(f"Generated: 2026-06-17\n\n")
    
    total = sum(len(v) for v in keyword_groups.values())
    out.write(f"Total transcript files: {total}\n\n")
    
    for kw, flist in sorted(keyword_groups.items()):
        out.write(f"## {kw}\n\n")
        out.write(f"Files: {len(flist)}\n\n")
        out.write("| # | Filename | Size |\n|---|---|---|\n")
        for i, f in enumerate(sorted(flist)[:20], 1):
            fp = os.path.join(SAVE_DIR, f)
            sz = os.path.getsize(fp)
            out.write(f"| {i} | {f[:70]} | {sz:,}B |\n")
        out.write("\n")

print(f"Regenerated {os.path.join(SAVE_DIR, '_FINDINGS.md')} with {total} files")
