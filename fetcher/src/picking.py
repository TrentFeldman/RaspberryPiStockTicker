"""Random picks: which symbols may be shown when, and dealing them out fairly.

Three small pieces:

  eligible()   the rules for who may be picked in each mode (below)
  Deck         shuffles the eligible symbols and deals them one by one, so
               everything is shown once before anything repeats
  next_turn()  the wall-clock "turn" numbering shared with the ticker

Who may be picked (market hours pick from everything; off hours only from
what is actually trading):

    mode        stocks/ETFs
    ---------   ---------------------------------------------------------
    market      all
    pre, after  only those that trade 24/5
    overnight   24/5 ones, while the overnight session runs (Sun-Thu nights)
    weekend     none (the strip shows just the weather)
    sleep       nothing is shown
"""

from __future__ import annotations

import random


def eligible(overnight_ok: bool, mode: str, overnight_session: bool) -> bool:
    """Whether a stock may be picked right now (see the table above).

    overnight_ok       the stock is permitted in the 24/5 overnight session
    overnight_session  the overnight session is running right now
    """
    if mode == "market":
        return True
    if mode in ("pre", "after"):
        return overnight_ok
    if mode == "overnight":
        return overnight_ok and overnight_session
    return False  # weekend / holiday / sleep


class Deck:
    """Random picks without repeats: shuffle the pool, deal it out, reshuffle.

    Every eligible symbol is shown once before anything repeats (with ~350
    symbols at 6 s a turn, a full deck lasts ~35 minutes). Like a real deck,
    cards are dealt from the end of the list.
    """

    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()  # tests pass a seeded one for repeatable results
        self.cards: list[str] = []         # still to be dealt (the next one is cards[-1])
        self.last: str | None = None       # the card dealt most recently
        self.boosted: set[str] = set()     # dealt an extra time this deck (big movers)

    def boost(self, card: str, within: int = 30) -> None:
        """Deal `card` once more, soon: somewhere in the next `within` draws.

        For big movers. Once per card per deck, so a big mover comes up about
        twice per deck instead of looping.
        """
        if card in self.boosted or card in self.cards:  # already boosted, or still to come anyway
            return
        self.boosted.add(card)
        n = min(within, len(self.cards))
        # Cards are dealt from the end: inserting at len-k makes it draw number k+1.
        self.cards.insert(len(self.cards) - (self.rng.randint(0, n - 1) if n else 0), card)

    def draw(self, pool: list[str], n: int = 1) -> list[str]:
        """Up to n different symbols from `pool`.

        The pool may change between calls (mode changes, a symbol turns out
        bad): cards no longer in it are dropped, and new ones join at the
        next reshuffle.
        """
        members = set(pool)
        self.cards = [c for c in self.cards if c in members]  # the pool shrank: drop the rest
        out: list[str] = []
        while len(out) < min(n, len(members)):
            if not self.cards:  # deck used up: reshuffle the whole pool
                self.cards = list(dict.fromkeys(pool))
                self.rng.shuffle(self.cards)
                self.boosted.clear()
                if len(self.cards) > 1 and self.cards[-1] == self.last:  # no back-to-back repeat
                    self.cards[0], self.cards[-1] = self.cards[-1], self.cards[0]
            card = self.cards.pop()
            if card not in out:
                out.append(card)
                self.last = card
        return out


def next_turn(now: float, rotate: float, lead: float) -> int | None:
    """The next stock turn's number, if it starts within `lead` seconds.

    Turns follow the wall clock: turn = epoch // rotate. The ticker computes
    the same number, so both agree which stock is up without talking to each
    other. With rotate=6 and lead=2:

        now=60.0  -> None   (turn 10 just started; turn 11 is 6 s away)
        now=64.0  -> 11     (turn 11 starts at 66.0: 2 s away, rack it now)
    """
    turn = int(now // rotate) + 1
    return turn if turn * rotate - now <= lead else None
