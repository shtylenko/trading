#!/usr/bin/env python3
"""
retrieve_excerpts.py

Retrieval tool for the Ross Cameron transcript corpus.
Pulls targeted, contextual excerpts using ripgrep (fast) + optional DB FTS.
Never loads full transcripts into the LLM. Designed for building deduplicated consolidated docs.

Usage examples:
  python -m library.ross_cameron.scripts.retrieve_excerpts \
      --queries "icebreaker" "first candle new high" "max loss" "5 pillars OR stock selection" \
      --out-dir library/ross_cameron/excerpts \
      --max-excerpts 12 \
      --min-views 20000

  python -m library.ross_cameron.scripts.retrieve_excerpts \
      --queries "VWAP trap" "walk away" "give back half" \
      --canonical-only
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / "ross_cameron" / "content"
INDEX_PATH = ROOT / "ross_cameron" / "transcript_index.json"
DB_PATH = ROOT / "ross_cameron" / "library.db"

BOILERPLATE_PATTERNS = [
    r"(?i)trading is risky\.? most beginner traders lose money",
    r"(?i)my results are not typical",
    r"(?i)remember as always, trading is risky",
    r"(?i)take it slow and practice in a simulator",
    r"(?i)thank you guys for tuning in",
    r"(?i)hit the thumbs up",
    r"(?i)subscribe if you.*like",
    r"^\s*Title:\s*.*$",
    r"^\s*Views:\s*\d+.*$",
    r"^\s*URL:\s*https?://.*$",
    r"^=+\s*$",
]

@dataclass
class Excerpt:
    file: str
    title: str
    url: str
    views: int
    size_kb: int
    query: str
    text: str
    context_before: str = ""
    context_after: str = ""

def load_index() -> List[Dict]:
    if not INDEX_PATH.exists():
        print(f"ERROR: Index not found at {INDEX_PATH}. Run index builder first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(INDEX_PATH.read_text())

def clean_text(text: str) -> str:
    """Remove common boilerplate and normalize whitespace."""
    for pat in BOILERPLATE_PATTERNS:
        text = re.sub(pat, "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tighten_excerpt(text: str, keywords: List[str], max_chars: int = 2200) -> str:
    """Try to keep only the most relevant paragraph(s) around the keywords."""
    lowered = text.lower()
    # Find first occurrence of any keyword
    positions = []
    for kw in keywords:
        for m in re.finditer(re.escape(kw.lower()), lowered):
            positions.append(m.start())
    if not positions:
        return text[:max_chars]
    center = sorted(positions)[0]
    # Expand around center
    start = max(0, center - 900)
    end = min(len(text), center + 1300)
    snippet = text[start:end]
    # Prefer to cut at sentence or paragraph boundaries
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars]
    # Try to start at a sentence
    first_period = snippet.find(". ")
    if 80 < first_period < 400:
        snippet = snippet[first_period+2:]
    return snippet.strip()

def run_rg_json_search(query: str, content_dir: Path, context: int = 3) -> List[Dict]:
    """Run ripgrep --json for reliable structured matches + context."""
    safe_q = query.strip()
    cmd = [
        "rg",
        "--json",
        "-i",
        "-B", str(context),
        "-A", str(context),
        "-e", safe_q,
        "--glob", "*.txt",
        str(content_dir),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode not in (0, 1):
            print(f"rg warning: {result.stderr.strip()}", file=sys.stderr)
        events = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events
    except FileNotFoundError:
        print("ERROR: ripgrep (rg) not found. Falling back to pure Python search.", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print("rg timed out.", file=sys.stderr)
        return []


def parse_rg_json(events: List[Dict], query: str, index: Dict[str, Dict]) -> List[Excerpt]:
    """Turn rg --json events into deduplicated Excerpt objects with surrounding context."""
    # Group events by path
    by_path: Dict[str, List[Dict]] = defaultdict(list)
    for ev in events:
        if ev.get("type") in ("match", "context"):
            p = ev.get("data", {}).get("path", {}).get("text")
            if p:
                by_path[p].append(ev)

    excerpts: List[Excerpt] = []
    for path, evs in by_path.items():
        fname = Path(path).name
        meta = index.get(fname, {})
        # Collect lines in order
        lines_with_ctx = []
        for ev in sorted(evs, key=lambda e: e.get("data", {}).get("line_number", 0)):
            txt = ev.get("data", {}).get("lines", {}).get("text", "")
            lines_with_ctx.append(txt.rstrip("\n"))

        if not lines_with_ctx:
            continue
        full = "\n".join(lines_with_ctx)
        cleaned = clean_text(full)
        if len(cleaned) < 50:
            continue

        ex = Excerpt(
            file=fname,
            title=meta.get("title", fname),
            url=meta.get("url", ""),
            views=meta.get("views", 0),
            size_kb=meta.get("size_kb", 0),
            query=query,
            text=cleaned,
        )
        excerpts.append(ex)
    return excerpts


def pure_python_search(query: str, content_dir: Path, index: Dict[str, Dict], context: int = 3) -> List[Excerpt]:
    """Reliable fallback: scan files in Python, collect context windows around matches."""
    excerpts: List[Excerpt] = []
    q_lower = query.lower()
    files = sorted(content_dir.glob("*.txt"))
    for f in files:
        try:
            text = f.read_text(errors="ignore")
        except Exception:
            continue
        if q_lower not in text.lower():
            continue
        lines = text.splitlines()
        matches = []
        for i, line in enumerate(lines):
            if q_lower in line.lower():
                matches.append(i)
        if not matches:
            continue
        for mi in matches[:3]:  # cap per file
            start = max(0, mi - context)
            end = min(len(lines), mi + context + 1)
            window = "\n".join(lines[start:end])
            cleaned = clean_text(window)
            if len(cleaned) < 50:
                continue
            meta = index.get(f.name, {})
            ex = Excerpt(
                file=f.name,
                title=meta.get("title", f.stem),
                url=meta.get("url", ""),
                views=meta.get("views", 0),
                size_kb=meta.get("size_kb", 0),
                query=query,
                text=cleaned,
            )
            excerpts.append(ex)
    return excerpts

def query_db_fts(db_path: Path, query: str, limit: int = 30) -> List[Dict]:
    """Optional: query the existing FTS for additional or alternative matches."""
    if not db_path.exists():
        return []
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        # transcripts_fts is a virtual table; use MATCH
        # We pull title + snippet. Content is in the FTS.
        sql = """
            SELECT 
                t.file_path,
                t.title,
                t.view_count,
                t.url,
                snippet(transcripts_fts, -1, '[[', ']]', ' … ', 20) as snip
            FROM transcripts_fts
            JOIN transcripts t ON t.id = transcripts_fts.rowid
            WHERE transcripts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        rows = conn.execute(sql, (query, limit)).fetchall()
        conn.close()
        results = []
        for r in rows:
            results.append({
                "file": Path(r[0]).name if r[0] else "",
                "title": r[1] or "",
                "views": r[2] or 0,
                "url": r[3] or "",
                "text": r[4] or "",
            })
        return results
    except Exception as e:
        print(f"DB FTS query failed (non-fatal): {e}", file=sys.stderr)
        return []

def dedup_excerpts(excerpts: List[Excerpt], similarity_thresh: float = 0.82) -> List[Excerpt]:
    """Very lightweight near-dup removal using normalized token overlap."""
    def norm(s: str) -> set:
        s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
        return set(s.split())

    kept = []
    seen_norms = []
    for ex in sorted(excerpts, key=lambda e: -e.views):  # prefer high-view sources
        n = norm(ex.text)
        if not n:
            continue
        is_dup = False
        for sn in seen_norms:
            inter = len(n & sn)
            union = len(n | sn)
            if union > 0 and (inter / union) >= similarity_thresh:
                is_dup = True
                break
        if not is_dup:
            kept.append(ex)
            seen_norms.append(n)
    return kept

def filter_by_index(excerpts: List[Excerpt], index: List[Dict], min_views: int = 0, canonical_only: bool = False) -> List[Excerpt]:
    idx_by_file = {e["file"]: e for e in index}
    filtered = []
    for ex in excerpts:
        meta = idx_by_file.get(ex.file, {})
        if min_views and meta.get("views", 0) < min_views:
            continue
        if canonical_only:
            title_l = meta.get("title", "").lower()
            if not any(k in title_l for k in ("guide", "ultimate", "full training", "how to", "step by step", "master this")):
                continue
        filtered.append(ex)
    return filtered

def format_excerpt(ex: Excerpt) -> str:
    header = f"**{ex.title}** ({ex.views:,} views)\n{ex.url}\n`{ex.file}`"
    body = ex.text
    return f"{header}\n\n{body}\n"

def main():
    parser = argparse.ArgumentParser(description="Targeted excerpt retriever for Ross Cameron transcripts (no full-file reads).")
    parser.add_argument("--queries", nargs="+", required=True, help="Search phrases (supports simple OR inside a phrase)")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "ross_cameron" / "excerpts")
    parser.add_argument("--max-excerpts", type=int, default=10, help="Max excerpts kept per query after filtering/dedup")
    parser.add_argument("--context", type=int, default=4, help="Lines of context before/after for rg")
    parser.add_argument("--min-views", type=int, default=10000, help="Ignore sources below this view count")
    parser.add_argument("--canonical-only", action="store_true", help="Only keep 'guide / ultimate / full training' style sources")
    parser.add_argument("--use-db", action="store_true", help="Also query library.db FTS (supplements rg)")
    parser.add_argument("--combine", action="store_true", help="Write one combined file instead of per-query")
    args = parser.parse_args()

    index_list = load_index()
    index_by_file = {e["file"]: e for e in index_list}

    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_collected: Dict[str, List[Excerpt]] = defaultdict(list)

    for q in args.queries:
        print(f"[retrieve] Searching for: {q}", file=sys.stderr)

        excerpts: List[Excerpt] = []

        # 1. Preferred: ripgrep --json (structured)
        events = run_rg_json_search(q, CONTENT_DIR, context=args.context)
        if events:
            excerpts = parse_rg_json(events, q, index_by_file)
        else:
            # 2. Pure Python fallback (reliable)
            excerpts = pure_python_search(q, CONTENT_DIR, index_by_file, context=args.context)

        # Optional DB FTS supplement (if --use-db)
        if args.use_db:
            for h in query_db_fts(DB_PATH, q):
                meta = index_by_file.get(h.get("file", ""), {})
                ex = Excerpt(
                    file=h.get("file", ""),
                    title=h.get("title") or meta.get("title", ""),
                    url=h.get("url") or meta.get("url", ""),
                    views=h.get("views") or meta.get("views", 0),
                    size_kb=meta.get("size_kb", 0),
                    query=q,
                    text=clean_text(h.get("text", "")),
                )
                excerpts.append(ex)

        # Filter + rank + dedup (high-view + canonical preference)
        excerpts = filter_by_index(excerpts, index_list, min_views=args.min_views, canonical_only=args.canonical_only)
        excerpts = dedup_excerpts(excerpts)

        # Tighten for signal density (smaller LLM-friendly chunks)
        kws = [q] + q.split()
        for ex in excerpts:
            ex.text = tighten_excerpt(ex.text, kws, max_chars=1800)

        excerpts = sorted(excerpts, key=lambda e: -e.views)[: args.max_excerpts]

        all_collected[q] = excerpts
        print(f"  -> kept {len(excerpts)} excerpts", file=sys.stderr)

        if not args.combine:
            out_path = args.out_dir / f"{_safe_filename(q)}.md"
            content = f"# Excerpts: {q}\n\n"
            content += f"Query: `{q}` | min_views={args.min_views} | canonical_only={args.canonical_only}\n\n"
            for ex in excerpts:
                content += format_excerpt(ex) + "\n---\n\n"
            out_path.write_text(content)
            print(f"  wrote {out_path}", file=sys.stderr)

    if args.combine:
        out_path = args.out_dir / "combined_retrieved.md"
        content = "# Ross Cameron Corpus — Retrieved Excerpts (deduplicated)\n\n"
        for q, exs in all_collected.items():
            content += f"## {q}\n\n"
            for ex in exs:
                content += format_excerpt(ex) + "\n---\n\n"
        out_path.write_text(content)
        print(f"wrote combined {out_path}", file=sys.stderr)

    print("Done.", file=sys.stderr)

def _safe_filename(s: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "_", s.lower()).strip("_")[:80]

if __name__ == "__main__":
    main()
