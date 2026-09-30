"""Tests for src/display_file.py: the exact text the LED ticker reads."""

import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (sets up the import path)
from src.display_file import DisplayState, render_display, write_atomic
from src.quotes import Quote


class DisplayTests(unittest.TestCase):
    def state(self, mode):
        return DisplayState(mode=mode, brightness=70, updated=100, account=(1000.0, 10.0, 1.0),
                            quotes=[Quote("AAPL", 1.5, 2.0), Quote("SPY", 9.0, -1.0)])

    def test_market_has_all_quotes_no_account(self):
        text = render_display(self.state("market"))
        self.assertIn("quote AAPL 1.50 2.00", text)
        self.assertIn("quote SPY 9.00 -1.00", text)
        self.assertNotIn("account", text)

    def test_off_hours_quotes_with_account(self):
        text = render_display(self.state("after"))
        self.assertIn("quote AAPL", text)
        self.assertIn("account 1000.00 10.00 1.00", text)

    def test_turn_tag_and_tiny_prices(self):
        st = self.state("market")
        st.quotes = [Quote("AAPL", 1.5, 2.0, turn=123), Quote("TINY", 0.00000912, 3.0),
                     Quote("CHEAP", 0.21346, -1.0)]
        text = render_display(st)
        self.assertIn("quote AAPL 1.50 2.00 turn=123", text)
        self.assertIn("quote TINY 9.12e-06 3.00", text)  # not 0.00
        self.assertIn("quote CHEAP 0.2135 -1.00", text)

    def test_sleep_has_no_quotes_or_account(self):
        st = self.state("sleep")
        st.moon = 0.4321
        text = render_display(st)
        self.assertNotIn("quote", text)
        self.assertNotIn("account", text)
        self.assertIn("moon 0.43", text)

    def test_stats_and_test_label(self):
        st = self.state("market")
        st.quotes[0].stats = {"chg": 5.54, "lo": 335.1, "halted": 1.0}
        st.test_label = "Mon 10:00"
        text = render_display(st)
        self.assertIn("quote AAPL 1.50 2.00 chg=5.54 lo=335.10 halted=1", text)
        self.assertIn("test Mon 10:00", text)

    def test_unknown_change_and_error_status(self):
        st = self.state("pre")
        st.account = (1000.0, None, None)
        st.status = "AUTH  HTTP 401\ninvalid_grant: nope"
        text = render_display(st)
        self.assertIn("account 1000.00 na na", text)
        self.assertIn("status error AUTH HTTP 401 invalid_grant: nope", text)  # one line

    def test_write_atomic(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "display.txt"
            write_atomic(p, "a\n")
            write_atomic(p, "b\n")
            self.assertEqual(p.read_text(), "b\n")
            self.assertEqual([x.name for x in Path(d).iterdir()], ["display.txt"])

    def test_event_and_offset_lines(self):
        st = DisplayState(mode="after", event=("open", 1790595000.0))
        text = render_display(st)
        self.assertIn("event open 1790595000\n", text)
        self.assertNotIn("offset", text)           # real time: no offset line
        st.offset = 172800.0
        self.assertIn("offset 172800\n", render_display(st))

    def test_big_movers_tagged_at_threshold(self):
        st = DisplayState(mode="market", big_move_pct=5.0,
                          quotes=[Quote("UP", 1.0, 5.0), Quote("DOWN", 1.0, -5.2),
                                  Quote("MEH", 1.0, 4.9)])
        text = render_display(st)
        self.assertIn("quote UP 1.00 5.00 big=1", text)
        self.assertIn("quote DOWN 1.00 -5.20 big=1", text)
        self.assertIn("quote MEH 1.00 4.90\n", text)
        st.big_move_pct = 0.0                           # 0 = off
        self.assertNotIn("big=1", render_display(st))

    def test_display_tells_ticker_the_turn_length(self):
        st = DisplayState(mode="market", rotate=6.0)
        self.assertIn("rotate 6\n", render_display(st))


if __name__ == "__main__":
    unittest.main()
