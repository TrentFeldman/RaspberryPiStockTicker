"""Stocks and ETFs from tastytrade: which exist, which trade 24/5, and their quotes.

StockData keeps three lists about the symbols in config.toml:

  known         symbols tastytrade recognises (checked once a day, so a typo
                or a delisted symbol is never picked)
  overnight_ok  symbols allowed in the 24/5 overnight session (same check)
  bad           symbols that were picked but came back with no usable price;
                skipped until the next daily check

and fetches quotes for any list of symbols (100 per request). It doesn't
decide WHAT to fetch; rotation.py does that.
"""

from __future__ import annotations

from .config import Config
from .logs import log
from .quotes import Quote, display_name, parse_quote, quote_stats
from .tastytrade import TastyClient
from .web import ApiError


class StockData:
    """tastytrade stock/ETF symbol checks and quotes."""

    def __init__(self, cfg: Config, client: TastyClient):
        self.cfg, self.client = cfg, client
        self.known: set[str] | None = None  # stocks/ETFs tastytrade recognises (None = not checked yet)
        self.overnight_ok: set[str] = set()  # symbols permitted in the overnight session
        self.bad: set[str] = set()           # picked but had no usable quote; skipped until the daily check
        self.prefer_mark = False             # set by the app every tick: overnight session running,
                                             # so prices come from the bid/ask midpoint

    def usable(self, symbol: str) -> bool:
        """May this stock/ETF be picked? Not marked bad, and (once the daily
        check has run) known to tastytrade."""
        return symbol not in self.bad and (self.known is None or symbol in self.known)

    def mark_bad(self, symbol: str) -> None:
        """A picked symbol had no usable quote: skip it until the daily check,
        so it can't keep wasting turns."""
        if symbol not in self.bad:
            self.bad.add(symbol)
            log.warning("no usable quote for %s; skipping it until the daily symbol check", symbol)

    def refresh_instruments(self) -> None:
        """Daily symbol check: which configured stocks exist, and which trade 24/5.
        Also gives every symbol marked bad a fresh chance."""
        items = self.client.get_items("/instruments/equities", [("symbol[]", s) for s in self.cfg.equities])
        found = {i["symbol"] for i in items}
        ok = {i["symbol"] for i in items if i.get("overnight-trading-permitted") is True}
        unknown = [s for s in self.cfg.equities if s not in found]
        if found != self.known and unknown:  # log only when the answer changes
            log.warning("not found at tastytrade, never picked (typo, renamed or delisted?): %s", " ".join(unknown))
        if ok != self.overnight_ok:
            log.info("overnight (24/5) eligible: %d of %d; not eligible: %s", len(ok), len(found),
                     " ".join(s for s in self.cfg.equities if s in found and s not in ok) or "none")
        if self.bad:
            log.info("daily re-check: picking again %s", " ".join(sorted(self.bad)))
            self.bad.clear()
        self.known, self.overnight_ok = found, ok

    def fetch_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Quotes for tastytrade symbols, keyed by symbol.

        Symbols without a usable price are simply left out (logged at debug
        level); the caller decides what that means.
        """
        items = self.client.get_items("/market-data/by-type", [("equity[]", s) for s in symbols])
        got: dict[str, Quote] = {}
        for item in items:
            sym = item.get("symbol", "")
            parsed = parse_quote(item, prefer_mark=self.prefer_mark)
            if parsed is None:
                log.debug("no usable price for %s", sym)
                continue
            got[sym] = Quote(display_name(sym), *parsed, stats=quote_stats(item, parsed[0]))
        return got

    def check_all(self) -> str:
        """--check only: quote every configured symbol (100 per request) and
        report the ones without a usable price."""
        wanted = self.cfg.equities
        quotes = self.fetch_quotes(wanted)
        if not quotes:
            raise ApiError(200, "no_quotes", "quote response contained no usable prices")
        missing = [s for s in wanted if s not in quotes]
        return f"{len(quotes)}/{len(wanted)} symbols" + (f"; no quote: {' '.join(missing)}" if missing else "")
