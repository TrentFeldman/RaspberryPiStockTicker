"""Tests for src/sessions.py: the market calendar, the countdown target and 24/5 nights."""

import unittest
from datetime import datetime, timezone

from helpers import ET, et, session, week_info
from src.sessions import Session, SessionInfo, market_event, overnight_active, parse_time

# Real API shape, captured on Saturday 2026-09-26 (no current session).
SAT_API = {
    "instrument-collection": "Equity", "state": "Closed",
    "next-session": {"close-at": "2026-09-28T20:00:00.000+00:00", "close-at-ext": "2026-09-29T00:00:00.000+00:00",
                     "open-at": "2026-09-28T13:30:00.000+00:00", "session-date": "2026-09-28",
                     "start-at": "2026-09-28T12:15:00.000+00:00"},
    "previous-session": {"close-at": "2026-09-25T20:00:00.000+00:00", "close-at-ext": "2026-09-26T00:00:00.000+00:00",
                         "open-at": "2026-09-25T13:30:00.000+00:00", "session-date": "2026-09-25",
                         "start-at": "2026-09-25T12:15:00.000+00:00"},
}


class SessionInfoTests(unittest.TestCase):
    def test_session_info_from_api(self):
        info = SessionInfo.from_api(SAT_API)
        now = et(2026, 9, 26, 12)
        self.assertIsNone(info.today(now, ET))
        self.assertEqual(info.last_opened(now).open, et(2026, 9, 25, 9, 30))
        self.assertEqual(info.today(et(2026, 9, 28, 8), ET).open, et(2026, 9, 28, 9, 30))
        self.assertEqual(info.sessions[0].close_ext, et(2026, 9, 25, 20))

    def test_dst_boundary(self):
        # Market times are absolute (UTC) from the API; the ET date must still match.
        info = SessionInfo([Session(datetime(2026, 11, 2, 14, 30, tzinfo=timezone.utc),
                                    datetime(2026, 11, 2, 21, tzinfo=timezone.utc),
                                    datetime(2026, 11, 3, 1, tzinfo=timezone.utc))])
        self.assertIsNotNone(info.today(et(2026, 11, 2, 7), ET))

    def test_parse_time_formats(self):
        a = parse_time("2026-09-25 13:30:00+00")
        b = parse_time("2026-09-25T13:30:00.000+00:00")
        c = parse_time("2026-09-25T13:30:00Z")
        self.assertEqual(a, b)
        self.assertEqual(b, c)


class OvernightTests(unittest.TestCase):
    # Mon 28 Sep .. Fri 2 Oct 2026 trading; Sat/Sun off.
    info = week_info((2026, 9, 25), (2026, 9, 28), (2026, 9, 29), (2026, 10, 2))

    def active(self, *when):
        return overnight_active(et(*when), self.info, ET)

    def test_sunday_and_weeknights(self):
        self.assertTrue(self.active(2026, 9, 27, 20, 0))    # Sunday night -> Monday
        self.assertTrue(self.active(2026, 9, 28, 3, 59))    # early Monday
        self.assertTrue(self.active(2026, 9, 28, 21, 0))    # Monday night -> Tuesday

    def test_not_during_day_or_premarket(self):
        self.assertFalse(self.active(2026, 9, 28, 4, 0))
        self.assertFalse(self.active(2026, 9, 28, 12, 0))
        self.assertFalse(self.active(2026, 9, 28, 19, 59))

    def test_friday_night_and_holiday_eve(self):
        self.assertFalse(self.active(2026, 9, 25, 21, 0))   # Friday -> Saturday
        self.assertFalse(self.active(2026, 9, 26, 21, 0))   # Saturday
        # Tue 29 Sep has a session but Wed 30 Sep isn't in the list (holiday):
        self.assertFalse(self.active(2026, 9, 29, 21, 0))

    def test_no_session_data(self):
        self.assertFalse(overnight_active(et(2026, 9, 28, 21), None, ET))


class MarketEventTests(unittest.TestCase):
    """The countdown target: today's close while open, else the next open."""
    fri, mon, tue = session(2026, 9, 25), session(2026, 9, 28), session(2026, 9, 29)

    def event(self, now, *sessions):
        return market_event(now, SessionInfo(list(sessions)))

    def test_premarket_counts_to_open(self):
        self.assertEqual(self.event(et(2026, 9, 28, 8), self.fri, self.mon), ("open", et(2026, 9, 28, 9, 30)))

    def test_open_counts_to_close(self):
        self.assertEqual(self.event(et(2026, 9, 28, 11), self.fri, self.mon, self.tue),
                         ("close", et(2026, 9, 28, 16)))

    def test_early_close(self):
        half = session(2026, 11, 27, close_h=13)  # day after Thanksgiving
        self.assertEqual(self.event(et(2026, 11, 27, 12), half), ("close", et(2026, 11, 27, 13)))

    def test_after_hours_counts_to_tomorrow(self):
        self.assertEqual(self.event(et(2026, 9, 28, 17), self.fri, self.mon, self.tue),
                         ("open", et(2026, 9, 29, 9, 30)))

    def test_weekend_and_holiday(self):
        self.assertEqual(self.event(et(2026, 9, 26, 12), self.fri, self.mon), ("open", et(2026, 9, 28, 9, 30)))
        self.assertEqual(self.event(et(2026, 9, 26, 12), self.fri, self.tue),  # Monday holiday
                         ("open", et(2026, 9, 29, 9, 30)))

    def test_no_data(self):
        self.assertIsNone(market_event(et(2026, 9, 26, 12), None))
        self.assertIsNone(self.event(et(2026, 9, 26, 12), self.fri))  # nothing upcoming known


if __name__ == "__main__":
    unittest.main()
