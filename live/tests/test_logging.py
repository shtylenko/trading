import json
from datetime import datetime, timezone

from trading.live.logging import EventLogger


def _today_dir(env):
    return env.log_dir / datetime.now(timezone.utc).strftime("%Y-%m-%d")


def test_emit_writes_jsonl_with_schema(env):
    log = EventLogger(env)
    rec = log.emit("run.start", component="engine", release_id="x03", run_id="r1",
                   data={"asof": "2024-06-03"})
    assert rec["schema_version"] == "1.0" and rec["event_id"]
    line = (_today_dir(env) / "events.jsonl").read_text().strip()
    got = json.loads(line)
    assert got["event"] == "run.start" and got["run_id"] == "r1"
    assert got["correlation_id"] == "r1"          # defaults to run_id


def test_errors_subset_and_redaction(env):
    log = EventLogger(env)
    log.emit("broker.error", level="ERROR", data={"api_key": "SECRET123", "msg": "boom"})
    errs = (_today_dir(env) / "errors.jsonl").read_text().strip()
    got = json.loads(errs)
    assert got["level"] == "ERROR"
    assert got["data"]["api_key"] == "***"        # secret redacted
    assert got["data"]["msg"] == "boom"


def test_summary_and_manifest(env):
    log = EventLogger(env)
    log.emit("run.end", component="engine")
    log.write_summary({"runs": 1, "blocked": 0})
    d = _today_dir(env)
    assert json.loads((d / "summary.json").read_text())["runs"] == 1
    manifest = json.loads((d / "manifest.json").read_text())
    assert "events.jsonl" in manifest["files"] and "summary.json" in manifest["files"]
