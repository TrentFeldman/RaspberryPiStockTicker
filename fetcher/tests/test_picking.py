"""Tests for src/picking.py: who may be picked when, the shuffled deck, turn numbers."""

import random
import unittest

import helpers  # noqa: F401  (sets up the import path)
from src.picking import Deck, eligible, next_turn


class EligibilityTests(unittest.TestCase):
    def test_rules(self):
        e = eligible  # (trades 24/5, mode, overnight session running)
        self.assertTrue(e(False, "market", False))    # market hours: any stock
        self.assertTrue(e(True, "after", False))      # after hours: 24/5 stocks...
        self.assertFalse(e(False, "after", False))    # ...only
        self.assertTrue(e(True, "pre", False))
        self.assertTrue(e(True, "overnight", True))
        self.assertFalse(e(True, "overnight", False))  # Friday night / holiday eve
        self.assertFalse(e(True, "weekend", False))   # weekends: the strip is just the weather
        self.assertFalse(e(True, "sleep", False))


class DeckTests(unittest.TestCase):
    pool = list("ABCDEFGH")

    def test_every_symbol_once_before_repeats(self):
        d = Deck(random.Random(1))
        first = [d.draw(self.pool)[0] for _ in range(8)]
        second = [d.draw(self.pool)[0] for _ in range(8)]
        self.assertEqual(sorted(first), self.pool)
        self.assertEqual(sorted(second), self.pool)
        self.assertNotEqual(first, self.pool)          # shuffled, not list order
        self.assertNotEqual(first[-1], second[0])      # no back-to-back repeat across decks

    def test_pool_changes(self):
        d = Deck(random.Random(2))
        d.draw(self.pool)
        self.assertTrue(set(d.draw(["A", "B"], 5)) <= {"A", "B"})  # shrunk: never outside it
        self.assertEqual(sorted(d.draw(list("ABC"), 3)), ["A", "B", "C"])  # n distinct
        self.assertEqual(d.draw([], 3), [])

    def test_boost_deals_again_soon_once_per_deck(self):
        d = Deck(random.Random(3))
        pool = [f"S{i}" for i in range(100)]
        first = d.draw(pool)[0]
        d.boost(first, within=30)
        d.boost(first, within=30)                        # second boost this deck: ignored
        nxt = [d.draw(pool)[0] for _ in range(30)]
        self.assertEqual(nxt.count(first), 1)            # dealt again within 30 draws
        rest = [d.draw(pool)[0] for _ in range(70)]      # the rest of this deck (99 + 1 boosted)
        self.assertNotIn(first, rest)                    # not a third time
        d.draw(pool)                                     # deck exhausted -> reshuffle clears boosts
        self.assertEqual(d.boosted, set())


class TurnTests(unittest.TestCase):
    def test_next_turn(self):
        self.assertIsNone(next_turn(60.0, 6, 2))   # turn 10 just started
        self.assertIsNone(next_turn(63.9, 6, 2))
        self.assertEqual(next_turn(64.0, 6, 2), 11)
        self.assertEqual(next_turn(65.9, 6, 2), 11)


if __name__ == "__main__":
    unittest.main()
