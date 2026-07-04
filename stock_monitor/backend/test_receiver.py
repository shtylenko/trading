import os
import tempfile
import time
import unittest
from pathlib import Path

import receiver


class ReceiverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.old_state = {
            "DATA_DIR": receiver.DATA_DIR,
            "DEBUG_DIR": receiver.DEBUG_DIR,
            "NDJSON_PATH": receiver.NDJSON_PATH,
            "MAX_DEBUG_FILES": receiver.MAX_DEBUG_FILES,
        }
        receiver.DATA_DIR = self.base
        receiver.DEBUG_DIR = self.base / "debug"
        receiver.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        receiver.NDJSON_PATH = self.base / "candles.ndjson"
        receiver.MAX_DEBUG_FILES = 3

    def tearDown(self):
        receiver.DATA_DIR = self.old_state["DATA_DIR"]
        receiver.DEBUG_DIR = self.old_state["DEBUG_DIR"]
        receiver.NDJSON_PATH = self.old_state["NDJSON_PATH"]
        receiver.MAX_DEBUG_FILES = self.old_state["MAX_DEBUG_FILES"]
        self.tmp.cleanup()

    def test_validate_candles_normalizes_seconds_and_rejects_bad_rows(self):
        valid, rejected = receiver.validate_candles([
            {"t": 1783019220, "o": "10", "h": "11", "l": "9", "c": "10.5", "v": "100"},
            {"t": "bad", "o": 10, "h": 11, "l": 9, "c": 10.5},
        ])

        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["t"], 1783019220000)
        self.assertEqual(len(rejected), 1)

    def test_update_per_symbol_json_dedupes_ndjson_appends(self):
        candles, _ = receiver.validate_candles([
            {"t": 1783019220000, "o": 10, "h": 11, "l": 9, "c": 10.5, "v": 100},
        ])

        first_total, first_appended = receiver.update_per_symbol_json(
            "AAPL/US", "5", candles, tab_id="tab/a", received_at="t1"
        )
        second_total, second_appended = receiver.update_per_symbol_json(
            "AAPL/US", "5m", candles, tab_id="tab/b", received_at="t2"
        )

        self.assertEqual((first_total, first_appended), (1, 1))
        self.assertEqual((second_total, second_appended), (1, 0))
        self.assertEqual(receiver.NDJSON_PATH.read_text(encoding="utf-8").count("\n"), 1)
        self.assertTrue((self.base / "AAPL_US_5m.json").exists())

    def test_corrupt_json_is_preserved_before_rewrite(self):
        corrupt = self.base / "BAD_1m.json"
        corrupt.write_text("{not json", encoding="utf-8")
        candles, _ = receiver.validate_candles([
            {"t": 1783019220000, "o": 10, "h": 11, "l": 9, "c": 10.5, "v": 100},
        ])

        receiver.update_per_symbol_json("BAD", "1m", candles, tab_id="tab", received_at="t")

        self.assertTrue(list(self.base.glob("BAD_1m.json.corrupt-*")))

    def test_prune_debug_files_keeps_newest_files(self):
        for i in range(6):
            path = receiver.DEBUG_DIR / f"debug-{i}.json"
            path.write_text("{}", encoding="utf-8")
            old = time.time() - (10 - i)
            os.utime(path, (old, old))

        receiver.prune_debug_files()

        remaining = sorted(path.name for path in receiver.DEBUG_DIR.glob("*.json"))
        self.assertEqual(remaining, ["debug-3.json", "debug-4.json", "debug-5.json"])


if __name__ == "__main__":
    unittest.main()
