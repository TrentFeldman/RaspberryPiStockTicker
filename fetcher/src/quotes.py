"""Quotes: one price on the panel, and how a tastytrade market-data item becomes one.

A Quote is what ends up as one `quote ...` line in display.txt:

    quote AAPL 341.46 1.65 chg=5.54 prev=335.92 open=336.20 lo=335.10 hi=343.00 ...
          name price  %    stats (optional extras for the full-screen view)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .util import num

# Extra stats for the full-screen stock view: display-file key -> tastytrade field.
STAT_FIELDS = {"open": "open", "lo": "day-low-price", "hi": "day-high-price",
               "ylo": "year-low-price", "yhi": "year-high-price"}


@dataclass
class Quote:
    """One symbol's price, ready for the panel."""
    name: str                   # what the panel shows: "AAPL", "BRK.B"
    price: float
    pct: float                  # change today in %
    stats: dict[str, float] = field(default_factory=dict)  # optional extras (see quote_stats)
    turn: int | None = None     # market hours: the full-screen turn this quote was picked for


def display_name(symbol: str) -> str:
    """tastytrade symbol -> panel name: BRK/B -> BRK.B (a space would split
    the display-file line, so spaces go too)."""
    return symbol.replace("/", ".").replace(" ", "")


def parse_quote(item: dict, prefer_mark: bool = False) -> tuple[float, float] | None:
    """(price, change %) from a /market-data/by-type item, or None if unusable.

    Normally uses the last trade price, falling back to mark or mid. The
    change is against the previous close.

    prefer_mark is for the overnight session, where `last` only reflects the
    regular session (and `mark` matched `last` in every overnight snapshot
    logged, e.g. 2026-09-28 20:00: last = mark = 485.00, mid = 485.385): the
    bid/ask midpoint comes first there, but only when both a bid and an ask
    are actually quoted.
    """
    order = ("mid", "mark", "last") if prefer_mark else ("last", "mark", "mid")
    if prefer_mark and not ((num(item.get("bid")) or 0) > 0 and (num(item.get("ask")) or 0) > 0):
        order = ("last", "mark", "mid")  # no two-sided market: the midpoint means nothing
    price = next((p for p in (num(item.get(k)) for k in order) if p), None)
    if price is None:
        return None
    prev = num(item.get("prev-close"))
    pct = (price - prev) / prev * 100 if prev else 0.0
    return price, pct


def quote_stats(item: dict, price: float) -> dict[str, float]:
    """The extras for the full-screen stock view (only the ones present):

        open, lo/hi (today's range), ylo/yhi (52-week range)
        chg     $ change vs the previous close     prev   the previous close
        halted  1.0 if trading is halted, else 0.0
    """
    stats = {k: v for k, f in STAT_FIELDS.items() if (v := num(item.get(f))) is not None and v > 0}
    prev = num(item.get("prev-close"))
    if prev:
        stats["chg"] = price - prev
        stats["prev"] = prev
    stats["halted"] = 1.0 if item.get("is-trading-halted") is True else 0.0
    return stats
