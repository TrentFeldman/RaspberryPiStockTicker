"""Tests for src/schedule.py: which screen mode applies at each time of day."""

import unittest
from datetime import datetime, timezone

from helpers import CFG, et, session
from src.schedule import compute_mode, moon_phase


class ScheduleTests(unittest.TestCase):
    mon = session(2026, 9, 28)

    def mode(self, now, today):
        return compute_mode(now, today, CFG)

    def test_market_hours(self):
        self.assertEqual(self.mode(et(2026, 9, 28, 9, 30), self.mon), "market")
        self.assertEqual(self.mode(et(2026, 9, 28, 15, 59), self.mon), "market")

    def test_after_hours(self):
        self.assertEqual(self.mode(et(2026, 9, 28, 16, 0), self.mon), "after")
        self.assertEqual(self.mode(et(2026, 9, 28, 19, 59), self.mon), "after")

    def test_premarket(self):
        self.assertEqual(self.mode(et(2026, 9, 28, 6, 30), self.mon), "pre")
        self.assertEqual(self.mode(et(2026, 9, 28, 9, 29), self.mon), "pre")

    def test_overnight_weekday(self):
        self.assertEqual(self.mode(et(2026, 9, 28, 20, 0), self.mon), "overnight")
        self.assertEqual(self.mode(et(2026, 9, 28, 22, 59), self.mon), "overnight")

    def test_sleep(self):
        self.assertEqual(self.mode(et(2026, 9, 28, 23, 0), self.mon), "sleep")
        self.assertEqual(self.mode(et(2026, 9, 28, 3, 0), self.mon), "sleep")
        self.assertEqual(self.mode(et(2026, 9, 28, 6, 29), self.mon), "sleep")
        self.assertEqual(self.mode(et(2026, 9, 26, 23, 30), None), "sleep")  # weekends too

    def test_weekend_day_and_night(self):
        self.assertEqual(self.mode(et(2026, 9, 26, 12), None), "weekend")
        self.assertEqual(self.mode(et(2026, 9, 26, 22), None), "overnight")

    def test_holiday_is_weekend(self):
        # A weekday with no session (e.g. Thanksgiving) behaves like a weekend.
        self.assertEqual(self.mode(et(2026, 11, 26, 11), None), "weekend")

    def test_early_close(self):
        early = session(2026, 11, 27, close_h=13, ext_h=17)
        self.assertEqual(self.mode(et(2026, 11, 27, 12, 59), early), "market")
        self.assertEqual(self.mode(et(2026, 11, 27, 13, 0), early), "after")
        self.assertEqual(self.mode(et(2026, 11, 27, 18), early), "after")  # past ext, before night
        self.assertEqual(self.mode(et(2026, 11, 27, 21), early), "overnight")


class MoonTests(unittest.TestCase):
    def test_known_phases(self):
        # New moon 2024-04-08 18:21 UTC (the eclipse); full moon 2024-04-23 23:49 UTC.
        new = moon_phase(datetime(2024, 4, 8, 18, 21, tzinfo=timezone.utc))
        full = moon_phase(datetime(2024, 4, 23, 23, 49, tzinfo=timezone.utc))
        self.assertLess(min(new, 1 - new), 0.03)
        self.assertAlmostEqual(full, 0.5, delta=0.03)


if __name__ == "__main__":
    unittest.main()
