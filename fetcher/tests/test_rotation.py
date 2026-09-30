"""Tests for src/rotation.py: one stock picked just before its turn (market hours),
a random handful in one request (off hours). tastytrade is replaced by a fake."""

import dataclasses
import unittest

from helpers import CFG
from src.app import Fetcher
from src.credentials import Credentials


class RackTests(unittest.TestCase):
    """Market hours: pick one stock at random just before its turn; fetch only that."""

    def setUp(self):
        cfg = dataclasses.replace(CFG, stocks=["AAPL", "MSFT", "BAD"], etfs=["SPY"],
                                  # fake_get returns +11.1% for everything; keep that from counting as a big move
                                  big_move_pct=50.0)
        self.fetcher = Fetcher(cfg, Credentials("s", "t"))
        self.rot = self.fetcher.rotation
        self.requests = []

        def fake_get(path, params=None):
            self.requests.append([s for _, s in params])
            return {"data": {"items": [{"symbol": s, "last": 10.0, "prev-close": 9.0}
                                       for _, s in params if s != "BAD"]}}

        self.fetcher.client.get = fake_get

    def deal(self, *cards):  # stack the deck: next picks are these, in order
        self.rot.deck.cards = list(reversed(cards))

    def test_fills_now_at_start_then_one_ahead_per_turn(self):
        rot = self.rot
        self.assertEqual(rot.rack_turn(61.0), 10)     # nothing yet: fill the current turn now
        self.deal("MSFT", "AAPL")
        rot.refresh_rack(10)
        self.assertIsNone(rot.rack_turn(62.0))        # mid-turn: nothing due
        self.assertEqual(rot.rack_turn(64.5), 11)     # 1.5 s before turn 11
        rot.refresh_rack(11)
        self.assertIsNone(rot.rack_turn(65.0))        # racked already
        self.assertEqual(self.requests, [["MSFT"], ["AAPL"]])  # one symbol per request
        self.assertEqual([(q.name, q.turn) for q in rot.playlist], [("MSFT", 10), ("AAPL", 11)])

    def test_bad_symbol_skipped_and_repicked(self):
        rot = self.rot
        self.deal("AAPL", "BAD", "SPY")
        rot.refresh_rack(10)
        with self.assertLogs("fetcher", level="WARNING") as cm:
            rot.refresh_rack(11)                      # picks BAD: no quote
        self.assertIn("no usable quote for BAD", cm.output[0])
        self.assertEqual([q.turn for q in rot.playlist], [10])
        self.assertNotIn("BAD", rot.pool("market", False))
        self.assertEqual(rot.rack_turn(64.5), 11)     # try again on the next tick
        rot.refresh_rack(11)
        self.assertEqual(rot.playlist[-1].name, "SPY")

    def test_pools(self):
        stocks, rot = self.fetcher.stocks, self.rot
        stocks.known, stocks.overnight_ok = {"AAPL", "MSFT", "SPY"}, {"AAPL", "SPY"}
        self.assertEqual(rot.pool("market", False), ["AAPL", "MSFT", "SPY"])  # BAD: unknown
        self.assertEqual(rot.pool("after", False), ["AAPL", "SPY"])            # 24/5 only
        self.assertEqual(rot.pool("weekend", False), [])

    def test_strip_is_one_request(self):
        self.fetcher.stocks.overnight_ok = {"AAPL", "MSFT", "SPY"}
        self.rot.refresh_strip("after", False)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(sorted(q.name for q in self.rot.strip), ["AAPL", "MSFT", "SPY"])

    def test_bulk_requests_are_batched_by_100(self):
        self.fetcher.client.get_items("/market-data/by-type", [("equity[]", f"S{i}") for i in range(250)])
        self.assertEqual([len(r) for r in self.requests], [100, 100, 50])


if __name__ == "__main__":
    unittest.main()
