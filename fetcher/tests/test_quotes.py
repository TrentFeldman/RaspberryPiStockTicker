"""Tests for src/quotes.py: turning tastytrade market data into panel quotes."""

import unittest

import helpers  # noqa: F401  (sets up the import path)
from src.quotes import display_name, parse_quote, quote_stats


class QuoteTests(unittest.TestCase):
    def test_parse_quote(self):
        price, pct = parse_quote({"last": "341.4603", "prev-close": "335.92"})
        self.assertAlmostEqual(price, 341.4603)
        self.assertAlmostEqual(pct, 1.6493, places=3)

    def test_parse_quote_fallbacks(self):
        self.assertEqual(parse_quote({"last": None, "mark": "10", "prev-close": "8"}), (10.0, 25.0))
        self.assertEqual(parse_quote({"last": "5", "prev-close": None}), (5.0, 0.0))
        self.assertIsNone(parse_quote({"last": None, "mark": None, "mid": None}))
        self.assertIsNone(parse_quote({"last": "NaN"}))

    def test_parse_quote_overnight_prefers_mid(self):
        item = {"last": "100", "mark": "102", "bid": "101.9", "ask": "102.1", "prev-close": "100"}
        self.assertEqual(parse_quote(item), (100.0, 0.0))
        self.assertEqual(parse_quote(item, prefer_mark=True), (102.0, 2.0))  # no mid: mark
        no_book = dict(item, bid=None, ask=None)
        self.assertEqual(parse_quote(no_book, prefer_mark=True)[0], 100.0)  # no bid/ask: last
        # The real overnight shape (2026-09-28 20:00): mark stuck at last, mid moves.
        night = {"last": "485.0", "mark": "485.0", "mid": "485.385", "bid": "485.0", "ask": "485.77",
                 "prev-close": "485.0"}
        self.assertEqual(parse_quote(night, prefer_mark=True)[0], 485.385)

    def test_quote_stats(self):
        item = {"open": "336.2", "day-low-price": "335.1", "day-high-price": "343", "year-low-price": "169.11",
                "year-high-price": "360.1", "prev-close": "335.92", "is-trading-halted": False}
        s = quote_stats(item, 341.46)
        self.assertEqual((s["lo"], s["hi"], s["ylo"], s["yhi"], s["open"]), (335.1, 343.0, 169.11, 360.1, 336.2))
        self.assertAlmostEqual(s["chg"], 5.54, places=2)
        self.assertEqual(s["halted"], 0.0)
        self.assertEqual(quote_stats({"is-trading-halted": True, "open": None}, 1)["halted"], 1.0)

    def test_display_name(self):
        self.assertEqual(display_name("BRK/B"), "BRK.B")
        self.assertEqual(display_name("AAPL"), "AAPL")


if __name__ == "__main__":
    unittest.main()
