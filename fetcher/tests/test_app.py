"""Tests for src/app.py: whole ticks with the network replaced by a fake.

Regression guard: an auth failure must cause exactly one login attempt, then
a pause. tastytrade blocks an IP for ~8 hours after repeated failed logins.
"""

import unittest

from helpers import CFG, et, week_info
from src import web
from src.app import Fetcher
from src.credentials import Credentials
from test_weather import J1


class AuthBackoffTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.real_http_json = web.http_json

        def fake_http_json(method, url, **kw):
            self.calls.append(url)
            if url.endswith("/oauth/token"):
                raise web.ApiError(400, "invalid_grant", "Client secret mismatch")
            if "wttr.in" in url:
                return J1
            return {}

        web.http_json = fake_http_json  # every request in src/ goes through web.http_json
        self.fetcher = Fetcher(CFG, Credentials("wrong-secret-xyz", "refresh-token-xyz"))
        self.fetcher.write_enabled = False
        # Fixed daytime schedule clock: at night (sleep mode) the fetcher rightly
        # skips the weather, which would make this test depend on when it runs.
        self.fetcher.pretend.now = lambda real: (et(2026, 9, 26, 12), False)

    def tearDown(self):
        web.http_json = self.real_http_json

    def logins(self):
        return sum(u.endswith("/oauth/token") for u in self.calls)

    def test_one_login_per_backoff_window(self):
        with self.assertLogs("fetcher", level="WARNING"):
            self.fetcher.tick()
            self.assertEqual(self.logins(), 1)
            for _ in range(5):  # later ticks inside the 30 min pause: no more logins
                for s in self.fetcher.sources.values():
                    s.next_due = 0
                self.fetcher.tick()
        self.assertEqual(self.logins(), 1)
        self.assertEqual(self.fetcher.state.status, "AUTH 400 invalid_grant")
        self.assertLessEqual(len(self.fetcher.state.status), 23)  # fits the panel
        self.assertTrue(self.fetcher.weather.items)  # non-tastytrade source still works

    def test_retries_after_pause(self):
        with self.assertLogs("fetcher", level="WARNING"):
            self.fetcher.tick()
            self.fetcher.auth_blocked_until = 0  # pretend 30 min passed
            for s in self.fetcher.sources.values():
                s.next_due = 0
            self.fetcher.tick()
        self.assertEqual(self.logins(), 2)

    def test_no_weather_during_market_hours(self):
        # Be nice to wttr.in: the weather is only fetched while the strip shows it.
        self.fetcher.pretend.now = lambda real: (et(2026, 9, 28, 11), False)  # Monday 11:00
        self.fetcher.session_info = week_info((2026, 9, 28))
        with self.assertLogs("fetcher", level="WARNING"):
            self.fetcher.tick()
        self.assertEqual(self.fetcher.state.mode, "market")
        self.assertFalse(any("wttr.in" in u for u in self.calls))


if __name__ == "__main__":
    unittest.main()
