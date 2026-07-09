"""Reveal and log remaining bars for a flat position (no re-entry)."""
import json
import subprocess
import sys
import os

SDIR = "/Users/shtylenko/Projects/trading/llm_trader/simulations/20260709102528-IBG-b2812f"
MONOROOT = "/Users/shtylenko/Projects"

def run(cmd, capture=True):
    result = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True, cwd=MONOROOT,
        env={**os.environ, "PYTHONPATH": MONOROOT}
    )
    return result.stdout, result.stderr, result.returncode

# Source env
subprocess.run("set -a && . trading/.env && set +a", shell=True, cwd=MONOROOT, capture_output=True)

for _ in range(400):  # safety limit
    out, err, code = run(f'python3 -m trading.llm_trader.step next --session "{SDIR}"')
    if code != 0:
        print(f"ERROR: {err}")
        break
    
    # Check for STATUS end
    if "STATUS end" in out or "ended=true" in out:
        print(f"SESSION ENDED: {out.strip()}")
        break
    
    # Parse the tick
    lines = out.strip().split('\n')
    tick_line = None
    for line in lines:
        if line.startswith('{"type": "tick"'):
            tick_line = json.loads(line)
            break
    
    if tick_line is None:
        print(f"PARSE ERROR - no tick: {out[:200]}")
        break
    
    i = tick_line['i']
    t = tick_line['time']
    
    # Log OBSERVE
    record = {
        "i": i,
        "time": t,
        "thought": f"Post-cutoff observation bar {i} at {t}, flat. No re-entry.",
        "action": "OBSERVE",
        "fill_px": None,
        "shares_delta": None,
        "stop": None,
        "note": "Flat - post-cutoff"
    }
    record_json = json.dumps(record, ensure_ascii=False)
    
    log_out, log_err, log_code = run(
        f'set -a && . trading/.env && set +a && python3 -m trading.llm_trader.recorder log --session "{SDIR}" --record \'{record_json}\''
    )
    if log_code != 0:
        print(f"LOG ERROR at i={i}: {log_err}")
    
    if (i + 1) % 20 == 0:
        print(f"Revealed {i+1} bars, last @ {t}")

print("ALL DONE")
