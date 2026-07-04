#!/usr/bin/env python3
"""Generate the stratified screening testset.

Samples N trading days from each half-year bucket between --start and
--end with a fixed seed, so the sample is pre-registered and identical
for every strategy screened against it. Sessions are independent for
day-trading strategies (no overnight state), so a stratified day sample
is an unbiased estimate of full-period performance at ~12% of the cost.

Usage:
    python3 -m trading.lab.scripts.build_screen_testset \\
        --start 2022-01-01 --end 2026-06-05 --days-per-bucket 12 --seed 7
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading.marketdata.calendar import trading_days_in_range

TESTSETS_DIR = Path(__file__).resolve().parents[1] / "testsets"


def half_year_buckets(start: date, end: date) -> list[tuple[str, date, date]]:
    buckets = []
    year = start.year
    while True:
        for label, b0, b1 in (
            (f"{year}_h1", date(year, 1, 1), date(year, 6, 30)),
            (f"{year}_h2", date(year, 7, 1), date(year, 12, 31)),
        ):
            if b1 < start or b0 > end:
                continue
            buckets.append((label, max(b0, start), min(b1, end)))
        year += 1
        if date(year, 1, 1) > end:
            return buckets


def main() -> None:
    p = argparse.ArgumentParser(description="Generate the screening testset")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2026-06-05")
    p.add_argument("--days-per-bucket", type=int, default=12)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--name", default="screen_2022_2026_sampled")
    p.add_argument("--universe", default="liquid_pit")
    p.add_argument("--candidate-limit", type=int, default=25)
    args = p.parse_args()

    rng = np.random.default_rng(args.seed)
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    lines = [
        f"name: {args.name}",
        "description: >-",
        f"  Stratified screening sample: {args.days_per_bucket} trading days per",
        f"  half-year bucket {args.start}..{args.end}, seed {args.seed}. Coarse",
        "  kill-filter for strategy variants; survivors graduate to the full",
        "  eval_*_broad gauntlet. Kill: sum R < 0 or pooled sign-flip p > 0.5.",
        f"universe: {args.universe}",
        "universe_policy: point_in_time",
        f"candidate_limit: {args.candidate_limit}",
        "date_ranges:",
    ]
    total = 0
    for label, b0, b1 in half_year_buckets(start, end):
        days = trading_days_in_range(b0, b1)
        take = min(args.days_per_bucket, len(days))
        sample = sorted(rng.choice(len(days), size=take, replace=False))
        for i in sample:
            d = days[i]
            lines.append(f'  - start: "{d.isoformat()}"')
            lines.append(f'    end: "{d.isoformat()}"')
            lines.append(f"    label: {label}")
            lines.append("    role: screen")
            total += 1

    out = TESTSETS_DIR / f"{args.name}.yaml"
    out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out} ({total} days)")


if __name__ == "__main__":
    main()
