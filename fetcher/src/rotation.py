"""What's on screen: which symbols get picked, and fetching just those.

Two ways of showing prices, depending on the mode:

  Market hours: ONE stock at a time, full screen, a new one every 6 s.
    Like racking the next round before it fires: ~2 s before each turn,
    pick one symbol at random and fetch only its quote, tagged with the
    turn it's for. So tastytrade gets one small request per turn, never a
    bulk download of the whole list.

        turn 10 on screen      turn 11 on screen
        |----------------------|----------------------|
                     ^ ~2 s before turn 11: pick + fetch its stock

  Off hours: the scrolling strip. A random handful (10) is picked and
    fetched in ONE request, then replaced every 1-2 minutes.

Picks come from pool(): every stock/ETF eligible right now (see picking.py).
"""

from __future__ import annotations

from dataclasses import replace

from .config import Config
from .picking import Deck, eligible, next_turn
from .quotes import Quote
from .stocks import StockData
from .web import ApiError

RACK_TRIES = 3  # picks per turn when a picked symbol turns out to have no usable quote


class Rotation:
    """Picks symbols (via a shuffled Deck) and keeps what's on screen."""

    def __init__(self, cfg: Config, stocks: StockData):
        self.cfg, self.stocks = cfg, stocks
        self.deck = Deck()
        self.playlist: list[Quote] = []     # market hours: picked quotes, each tagged with its turn
        self.strip: list[Quote] = []        # off hours: the strip's current random picks
        self.rack_tries: dict[int, int] = {}  # turn -> picks tried for it so far

    # -- choosing ---------------------------------------------------------

    def pool(self, mode: str, overnight_session: bool) -> list[str]:
        """Every stock/ETF that may be picked right now, in config order."""
        return [s for s in self.cfg.equities if self.stocks.usable(s)
                and eligible(s in self.stocks.overnight_ok, mode, overnight_session)]

    def quotes_for(self, picks: list[str]) -> list[Quote]:
        """Quotes for picked symbols, in pick order, fetched in one request.

        A pick with no usable quote is left out and marked bad. A big mover
        is dealt again within a few minutes.
        """
        got = self.stocks.fetch_quotes(picks) if picks else {}
        out = []
        for s in picks:
            q = got.get(s)
            if q is None:
                self.stocks.mark_bad(s)
                continue
            if abs(q.pct) >= self.cfg.big_move_pct:
                self.deck.boost(s)  # big mover: deal it again within a few minutes
            out.append(q)
        return out

    # -- off hours: the strip ---------------------------------------------

    def refresh_strip(self, mode: str, overnight_session: bool) -> None:
        """Off hours: a new random handful for the strip, fetched in one request."""
        picks = self.deck.draw(self.pool(mode, overnight_session), self.cfg.strip_size)
        quotes = self.quotes_for(picks)
        if picks and not quotes:
            raise ApiError(200, "no_quotes", f"no usable price for {', '.join(picks)}")
        self.strip = quotes

    # -- market hours: one stock per turn ---------------------------------

    def rack_turn(self, now: float) -> int | None:
        """The turn that needs a stock picked and fetched right now, if any.

        Normally the next turn, ~2 s before it starts. At start-up (or after
        a gap, e.g. the network was down) the CURRENT turn is filled straight
        away so the screen isn't left empty. Gives up on a turn after
        RACK_TRIES picks without a quote (the previous stock then simply
        stays up a turn longer).
        """
        rotate = self.cfg.rotate_sec
        cur = int(now // rotate)
        latest = max((q.turn for q in self.playlist), default=None)
        if latest is None or latest < cur - 1:
            target = cur
        else:
            target = next_turn(now, rotate, min(self.cfg.rack_lead, rotate - 1))
        if target is None or (latest is not None and latest >= target):
            return None  # nothing due yet, or already racked
        return target if self.rack_tries.get(target, 0) < RACK_TRIES else None

    def refresh_rack(self, turn: int) -> None:
        """Pick the stock for `turn` and fetch its quote into the playlist.

        Only used during market hours, where every symbol is eligible (so
        the pool is the "market" one).
        """
        self.rack_tries[turn] = self.rack_tries.get(turn, 0) + 1
        quotes = self.quotes_for(self.deck.draw(self.pool("market", False), 1))
        if quotes:  # else: the pick had no quote (now skipped); the next tick picks again
            self.playlist.append(replace(quotes[0], turn=turn))
        # Keep the current and upcoming turns, plus the one before as a fallback.
        self.playlist = [q for q in self.playlist if q.turn >= turn - 2]
        self.rack_tries = {t: n for t, n in self.rack_tries.items() if t >= turn - 2}

    # -- output -----------------------------------------------------------

    def on_screen(self, mode: str) -> list[Quote]:
        """The quotes for display.txt: the racked stocks in turn order during
        market hours, otherwise the strip."""
        return sorted(self.playlist, key=lambda q: q.turn) if mode == "market" else self.strip
