import os
import tempfile
import time
import unittest
from pathlib import Path

import db as session_db
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
        receiver.init_session_db(self.base / "test.db")

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


class SessionDbTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "session.db"
        session_db.set_db_path(self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_tickers_join_daily_session(self):
        result = session_db.upsert_screener_rows(
            [
                {
                    "ticker": "aapl",
                    "ticker_id": "1",
                    "name": "Apple",
                    "fields": {"close": 200},
                    "raw": {"symbol": "AAPL", "close": 200},
                },
                {
                    "ticker": "MSFT",
                    "ticker_id": "2",
                    "name": "Microsoft",
                    "fields": {},
                    "raw": {"symbol": "MSFT"},
                },
            ],
            source_url="https://example/screener",
            session_date="2026-07-14",
            captured_at="2026-07-14T10:00:00-04:00",
            screener_key="gap-n-go",
            screener_name="Gap'n'Go",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["session_date"], "2026-07-14")
        self.assertEqual(sorted(result["new_tickers"]), ["AAPL", "MSFT"])
        self.assertEqual(result["snapshots_written"], 2)
        self.assertEqual(result["screener_key"], "gap-n-go")

        sess = session_db.get_session("2026-07-14")
        self.assertIsNotNone(sess)
        self.assertEqual(sess["ticker_count"], 2)
        tickers = {t["ticker"] for t in sess["tickers"]}
        self.assertEqual(tickers, {"AAPL", "MSFT"})
        self.assertEqual(sess["tickers"][0]["screener_key"], "gap-n-go")

    def test_same_ticker_updates_not_duplicates(self):
        session_db.upsert_screener_rows(
            [{"ticker": "XYZ", "raw": {"v": 1}}],
            session_date="2026-07-14",
            captured_at="2026-07-14T10:00:00-04:00",
            throttle_sec=9999,
            screener_key="gap-n-go",
            screener_name="Gap'n'Go",
        )
        result = session_db.upsert_screener_rows(
            [{"ticker": "XYZ", "raw": {"v": 1}}],  # same hash
            session_date="2026-07-14",
            captured_at="2026-07-14T10:00:10-04:00",
            throttle_sec=9999,
            screener_key="gap-n-go",
            screener_name="Gap'n'Go",
        )
        self.assertEqual(result["new_tickers"], [])
        self.assertEqual(result["updated_tickers"], 1)
        # Same hash + within throttle → no new snapshot
        self.assertEqual(result["snapshots_written"], 0)

        sess = session_db.get_session("2026-07-14")
        self.assertEqual(sess["ticker_count"], 1)
        self.assertEqual(sess["tickers"][0]["last_seen_at"], "2026-07-14T10:00:10-04:00")

    def test_hash_change_writes_snapshot_even_within_throttle(self):
        session_db.upsert_screener_rows(
            [{"ticker": "ABC", "raw": {"price": 1}}],
            session_date="2026-07-14",
            captured_at="2026-07-14T10:00:00-04:00",
            throttle_sec=9999,
            screener_key="gap-n-go",
        )
        result = session_db.upsert_screener_rows(
            [{"ticker": "ABC", "raw": {"price": 2}}],
            session_date="2026-07-14",
            captured_at="2026-07-14T10:00:05-04:00",
            throttle_sec=9999,
            screener_key="gap-n-go",
        )
        self.assertEqual(result["new_tickers"], [])
        self.assertEqual(result["snapshots_written"], 1)

    def test_new_day_creates_new_session(self):
        session_db.upsert_screener_rows(
            [{"ticker": "AAA", "raw": {}}],
            session_date="2026-07-14",
            captured_at="2026-07-14T10:00:00-04:00",
            screener_key="gap-n-go",
        )
        session_db.upsert_screener_rows(
            [{"ticker": "BBB", "raw": {}}],
            session_date="2026-07-15",
            captured_at="2026-07-15T10:00:00-04:00",
            screener_key="gap-n-go",
        )
        sessions = session_db.list_sessions()
        dates = {s["session_date"] for s in sessions}
        self.assertEqual(dates, {"2026-07-14", "2026-07-15"})
        self.assertEqual(session_db.get_session("2026-07-14")["ticker_count"], 1)
        self.assertEqual(session_db.get_session("2026-07-15")["ticker_count"], 1)

    def test_invalid_rows_skipped(self):
        result = session_db.upsert_screener_rows(
            [
                {"ticker": "", "raw": {}},
                {"raw": {"no_ticker": True}},
                {"ticker": "OK", "raw": {}},
            ],
            session_date="2026-07-14",
            captured_at="2026-07-14T10:00:00-04:00",
            screener_key="gap-n-go",
        )
        self.assertEqual(result["new_tickers"], ["OK"])
        self.assertEqual(result["skipped_invalid"], 2)


class ScreenerConfigTest(unittest.TestCase):
    def test_public_config_includes_gap_n_go(self):
        import screener_config
        pub = screener_config.public_config()
        self.assertTrue(pub["ok"])
        self.assertTrue(pub["require_my_screeners"])
        keys = {s["key"] for s in pub["screeners"]}
        self.assertIn("gap-n-go", keys)
        g = next(s for s in pub["screeners"] if s["key"] == "gap-n-go")
        self.assertEqual(g["max_rows_per_push"], 50)
        self.assertEqual(g["max_session_tickers"], 50)

    def test_match_name_gap_n_go(self):
        import screener_config
        m = screener_config.match_screener_name("Gap'n'Go")
        self.assertIsNotNone(m)
        self.assertEqual(m["key"], "gap-n-go")
        m2 = screener_config.match_screener_name("gap n go")
        self.assertIsNotNone(m2)
        self.assertIsNone(screener_config.match_screener_name("Random Screener"))

    def test_max_rows_helpers(self):
        import screener_config
        self.assertEqual(screener_config.max_rows_per_push("gap-n-go"), 50)
        self.assertEqual(screener_config.max_session_tickers("gap-n-go"), 50)


class SessionLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        import session_log
        self.session_log = session_log
        session_log.set_base_dir(self.base / "sessions")
        # Point receiver log dir so handle paths stay independent
        self.old_sessions = getattr(receiver, "SESSIONS_LOG_DIR", None)
        receiver.SESSIONS_LOG_DIR = self.base / "sessions"
        session_log.set_base_dir(receiver.SESSIONS_LOG_DIR)
        receiver.init_session_db(self.base / "test.db")

    def tearDown(self):
        if self.old_sessions is not None:
            receiver.SESSIONS_LOG_DIR = self.old_sessions
        self.tmp.cleanup()

    def test_log_event_appends_ndjson(self):
        r1 = self.session_log.log_event(
            "session_start",
            session_date="2026-07-15",
            screener_key="gap-n-go",
        )
        r2 = self.session_log.log_event(
            "ticker_added",
            session_date="2026-07-15",
            ticker="AAPL",
        )
        self.assertEqual(r1["event"], "session_start")
        self.assertEqual(r2["ticker"], "AAPL")
        path = self.session_log.log_path("2026-07-15")
        self.assertTrue(path.is_file())
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        self.assertEqual(len(lines), 2)
        events = self.session_log.read_events("2026-07-15")
        self.assertEqual([e["event"] for e in events], ["session_start", "ticker_added"])
        only = self.session_log.read_events("2026-07-15", event="ticker_added")
        self.assertEqual(len(only), 1)
        self.assertEqual(only[0]["ticker"], "AAPL")

    def test_upsert_logs_session_start_and_ticker_added(self):
        # Isolate session_log used by receiver handlers via module import
        import session_log
        session_log.set_base_dir(self.base / "sessions")
        result = session_db.upsert_screener_rows(
            [
                {"ticker": "NVDA", "raw": {"close": 100}},
                {"ticker": "AMD", "raw": {"close": 50}},
            ],
            session_date="2026-07-15",
            captured_at="2026-07-15T09:30:00-04:00",
            screener_key="gap-n-go",
            screener_name="Gap'n'Go",
        )
        self.assertTrue(result.get("session_created"))
        self.assertEqual(sorted(result["new_tickers"]), ["AMD", "NVDA"])

        # Mirror what handle_screener does with the result
        if result.get("session_created"):
            session_log.log_event(
                "session_start",
                session_date=result["session_date"],
                session_id=result.get("session_id"),
                screener_key="gap-n-go",
            )
        for t in result["new_tickers"]:
            session_log.log_event(
                "ticker_added",
                session_date=result["session_date"],
                ticker=t,
                screener_key="gap-n-go",
            )
        events = session_log.read_events("2026-07-15")
        names = [e["event"] for e in events]
        self.assertIn("session_start", names)
        self.assertEqual(names.count("ticker_added"), 2)

    def test_known_events_documented(self):
        required = {
            "session_start",
            "session_end",
            "screener_open",
            "screener_close",
            "ticker_added",
            "screener_push",
            "push_rejected",
            "watchlist_added",
            "watchlist_error",
            "receiver_start",
            "receiver_stop",
        }
        self.assertTrue(required.issubset(self.session_log.EVENTS))


class WatchlistSyncTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "wl.db"
        import webull_watchlist as wl
        self.wl = wl
        wl.set_db_path(self.db_path)
        self.fake = wl.WebullWatchlistClient(data_client=None, dry_run=True)
        # Seed a fake existing empty list behaviour via dry_run create
        wl.set_client_factory(lambda: self.fake)

    def tearDown(self):
        self.wl.set_client_factory(None)
        self.tmp.cleanup()

    def test_sync_new_tickers_dry_run(self):
        result = self.wl.sync_new_tickers(
            ["AAPL", "NVDA"],
            session_date="2026-07-14",
            screener_key="gap-n-go",
            config={
                "enabled": True,
                "dry_run": True,
                "watchlist_name": "Today's Gap'n'Go",
                "screener_keys": ["gap-n-go"],
                "instrument_category": "US_STOCK",
                "reset_daily": True,
                "region_id": "us",
                "environment": "prod",
            },
            client=self.fake,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertEqual(sorted(result["added"]), ["AAPL", "NVDA"])
        # second call should skip already-synced
        result2 = self.wl.sync_new_tickers(
            ["AAPL", "MSFT"],
            session_date="2026-07-14",
            screener_key="gap-n-go",
            config={
                "enabled": True,
                "dry_run": True,
                "watchlist_name": "Today's Gap'n'Go",
                "screener_keys": ["gap-n-go"],
                "instrument_category": "US_STOCK",
                "reset_daily": True,
            },
            client=self.fake,
        )
        self.assertEqual(result2["added"], ["MSFT"])
        self.assertIn("AAPL", result2["skipped"])
        ops = [c[0] for c in self.fake._calls]
        self.assertIn("create_watchlist", ops)
        self.assertIn("add_watchlist_instruments", ops)

    def test_wrong_screener_key_skipped(self):
        result = self.wl.sync_new_tickers(
            ["ZZZ"],
            session_date="2026-07-14",
            screener_key="other-screener",
            config={
                "enabled": True,
                "dry_run": True,
                "watchlist_name": "Today's Gap'n'Go",
                "screener_keys": ["gap-n-go"],
            },
            client=self.fake,
        )
        self.assertEqual(result["added"], [])
        self.assertEqual(result["skipped"], ["ZZZ"])


if __name__ == "__main__":
    unittest.main()
