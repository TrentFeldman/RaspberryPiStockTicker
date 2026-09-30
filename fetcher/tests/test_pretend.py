"""Tests for src/pretend.py: test mode flows, expires, and ignores bad files."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from helpers import et
from src.pretend import PretendClock


class PretendTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "pretend.json"
        self.clock = PretendClock(self.path, max_minutes=60)
        self.real = datetime(2026, 9, 26, 17, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.dir.cleanup()

    def write(self, target, set_at, expires=60):
        self.path.write_text(json.dumps({"target": target, "set_at": set_at, "expires_min": expires}))

    def test_no_file_is_real_time(self):
        self.assertEqual(self.clock.now(self.real), (self.real, False))

    def test_pretend_time_flows(self):
        with self.assertLogs("fetcher", level="INFO"):
            self.write("2026-09-28T10:00:00-04:00", self.real.timestamp())
            eff, on = self.clock.now(self.real + timedelta(minutes=5))
        self.assertTrue(on)
        self.assertEqual(eff, et(2026, 9, 28, 10, 5))

    def test_expires(self):
        with self.assertLogs("fetcher", level="INFO") as cm:
            self.write("2026-09-28T10:00:00-04:00", self.real.timestamp(), expires=10)
            eff, on = self.clock.now(self.real + timedelta(minutes=11))
        self.assertFalse(on)
        self.assertIn("expired", cm.output[-1])

    def test_capped_by_config(self):
        with self.assertLogs("fetcher", level="INFO"):
            self.write("2026-09-28T10:00:00-04:00", self.real.timestamp(), expires=600)
            _, on = self.clock.now(self.real + timedelta(minutes=61))
        self.assertFalse(on)

    def test_invalid_file_ignored(self):
        self.path.write_text("not json")
        with self.assertLogs("fetcher", level="WARNING"):
            self.assertEqual(self.clock.now(self.real), (self.real, False))


if __name__ == "__main__":
    unittest.main()
