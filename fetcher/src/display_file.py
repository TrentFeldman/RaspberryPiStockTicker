"""display.txt: the file the fetcher writes and the LED ticker reads.

It's the ONLY link between the two programs, so either can be restarted
without the other. One setting per line, plain text:

    # written by fetcher.py 2026-09-28T10:00:01
    updated 1790455209            epoch of the last successful quote refresh (drives STALE)
    mode market                   market | after | pre | weekend | overnight | sleep
    brightness 70                 1-100, applied live by the ticker
    status ok                     or: status error <short message for the panel>
    moon 0.43                     moon phase, 0 new .. 0.5 full (sleep screen)
    test Mon 10:00                only while test mode is on
    rotate 6                      seconds per stock turn (market hours)
    event close 1790625600        countdown target: today's close, or the next open
    offset 172800                 test mode only: pretend minus real seconds
    account 12345.67 98.76 0.80  value, change $, change % ("na" if unknown)
    quote NVDA 118.02 6.21 chg=6.90 lo=111.80 hi=118.30 big=1 turn=298409335
    weather Today 93/68F          one line per strip item (off hours only; text, in the strip after the quotes)

The ticker's side of this format is ticker/src/display_file.h; keep the two
in step. The file is replaced in one step (write_atomic), so the ticker never
reads half a file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .quotes import Quote
from .schedule import ACCOUNT_MODES


@dataclass
class DisplayState:
    """Everything the panel should show; rendered to text by render_display()."""
    mode: str = "weekend"
    brightness: int = 70
    status: str = "ok"               # "ok", or the most important problem (short)
    updated: float = 0.0             # epoch of last successful tastytrade quote refresh
    account: tuple[float, float | None, float | None] | None = None  # value, change $, change %
    quotes: list[Quote] = field(default_factory=list)
    overnight_session: bool = False  # 24/5 stocks are trading right now
    moon: float = 0.0                # moon phase, for the sleep screen
    test_label: str | None = None    # set while pretend/test mode is active ("Mon 10:00")
    rotate: float = 0.0              # seconds per stock turn (tells the ticker)
    event: tuple[str, float] | None = None  # ("open"|"close", epoch): the countdown target
    offset: float = 0.0              # pretend minus real seconds (test mode), for the ticker's clock
    big_move_pct: float = 0.0        # tag quotes moving at least this much (0 = off)
    weather: list[str] = field(default_factory=list)  # strip text items ("68F Sunny", ...)


def _price(v: float) -> str:
    """Cents for normal prices; 4 significant digits below $1 (0.2135,
    9.12e-06), where cents would show 0.00."""
    return f"{v:.2f}" if abs(v) >= 1 else f"{v:.4g}"


def render_display(st: DisplayState) -> str:
    """The display.txt text for this state (format: see the top of this file)."""
    lines = [
        f"# written by fetcher.py {datetime.now().isoformat(timespec='seconds')}",
        f"updated {int(st.updated)}",
        f"mode {st.mode}",
        f"brightness {st.brightness}",
        # Status must stay on one line: squash any newlines/runs of spaces.
        "status ok" if st.status == "ok" else f"status error {' '.join(st.status.split())[:60]}",
        f"moon {st.moon:.2f}",
    ]
    if st.test_label:
        lines.append(f"test {st.test_label}")
    if st.rotate:
        lines.append(f"rotate {st.rotate:g}")
    if st.event:
        lines.append(f"event {st.event[0]} {st.event[1]:.0f}")
    if st.offset:
        lines.append(f"offset {st.offset:.0f}")
    if st.account and st.mode in ACCOUNT_MODES:
        value, chg, pct = st.account
        fmt = lambda v: "na" if v is None else f"{v:.2f}"
        lines.append(f"account {value:.2f} {fmt(chg)} {fmt(pct)}")
    for q in st.quotes if st.mode != "sleep" else ():  # asleep: nothing to show
        extras = "".join(f" {k}={v:.2f}" for k, v in q.stats.items() if k != "halted")
        if q.stats.get("halted"):
            extras += " halted=1"  # only written when halted
        if st.big_move_pct and abs(q.pct) >= st.big_move_pct:
            extras += " big=1"
        if q.turn is not None:
            extras += f" turn={q.turn}"
        lines.append(f"quote {q.name} {_price(q.price)} {q.pct:.2f}{extras}")
    if st.mode in ACCOUNT_MODES:  # only the account screens have the strip
        lines += [f"weather {w}" for w in st.weather]
    return "\n".join(lines) + "\n"


def write_atomic(path: Path, text: str) -> None:
    """Write via a temp file + rename, so a reader never sees a half-written file.
    (A rename replaces the old file in one step.)"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)
