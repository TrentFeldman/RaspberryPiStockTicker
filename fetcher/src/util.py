"""Tiny helpers used all over the fetcher.

Nothing here knows about stocks or APIs. These are small, safe conversions
that several other files need, kept in one place so they behave the same
everywhere.
"""

from __future__ import annotations


def num(value) -> float | None:
    """Turn an API value into a float, or None if it isn't a usable number.

    APIs send numbers as strings ("341.46"), as null, or as junk ("NaN").

        num("341.46") -> 341.46      num(None) -> None
        num("NaN")    -> None        num("abc") -> None
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # NaN is the only value that isn't equal to itself


def duration(seconds: float) -> str:
    """A length of time for log lines: "45s", "12m", "1h05m"."""
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:  # under 1.5 hours: minutes read better
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def unique(items, skip=()) -> list[str]:
    """Items in their original order, without duplicates or anything in `skip`.

        unique(["A", "B", "A", "C"], skip=["C"]) -> ["A", "B"]
    """
    return list(dict.fromkeys(s for s in items if s not in skip))
