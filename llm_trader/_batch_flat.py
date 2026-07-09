#!/usr/bin/env python3
"""Batch reveal and log remaining bars for flat position."""
import json
import subprocess
import os
import sys

SDIR = "/Users/shtylenko/Projects/trading/llm_trader/simulations/20260709102528-IBG-b2812f"
MONOROOT = "/Users/shtylenko/Projects"

# Get the venv python path
# The interpreter running this script is already in the right env

def run(cmd):
    p = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=MONOROOT,
        env={**os.environ, "PYTHONPATH": MONOROOT}
    )
    return p.stdout, p.stderr, p.returncode

# First source env in a way that persists
rc = subprocess.run(
    'bash -c "set -a && source trading/.env && set +a && env"',
    shell=True, capture_output=True, text=True, cwd=MONOROOT
)
# Parse and export env vars we need
for line in rc.stdout.splitlines():
    if '=' in line and not line.startswith('_'):
        k, v = line.split('=', 1)
        os.environ[k] = v

for loop_i in range(500):
    stdout, stderr, code = run(f'python3 -m trading.llm_trader.step next --session "{SDIR}"')
    if code != 0:
        print(f"STEP ERROR: {stderr}", file=sys.stderr)
        break
    
    if "STATUS end" in stdout or "ended=true" in stdout:
        print(f"=== SESSION ENDED at loop {loop_i} ===")
        print(stdout)
        break
    
    # Parse tick
    for line in stdout.splitlines():
        if line.strip().startswith('{"type": "tick"'):
            try:
                tick = json.loads(line)
            except json.JSONDecodeError:
                continue
            break
    else:
        print(f"NO TICK FOUND in: {stdout[:200]}", file=sys.stderr)
        break
    
    ti = tick['i']
    tt = tick['time']
    
    record = json.dumps({
        "i": ti,
        "time": tt,
        "thought": "Post-cutoff flat, no re-entry.",
        "action": "OBSERVE",
        "fill_px": None,
        "shares_delta": None,
        "stop": None,
        "note": "Flat"
    }, ensure_ascii=False)
    
    log_stdout, log_stderr, log_code = run(
        f'python3 -m trading.llm_trader.recorder log --session "{SDIR}" --record \'{record}\''
    )
    if log_code != 0:
        print(f"LOG ERROR at i={ti}: {log_stderr}", file=sys.stderr)
    
    if (ti + 1) % 100 == 0:
        print(f"Bar {ti+1} @ {tt}")

print("BATCH COMPLETE")
