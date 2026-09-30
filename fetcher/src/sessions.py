"""Market calendar: when the stock market opens and closes.

The dates come from tastytrade (/market-time/equities/sessions/current), so
holidays and early closes (e.g. 1 pm the day after Thanksgiving) are
handled without a holiday list in this code. One API answer describes up
to three trading sessions: the previous, the current (if the market is
open today) and the next.

    Session     one trading day: open 9:30, close 16:00, extended close 20:00
    SessionInfo those (up to) three sessions, with lookups by day

Also here:
    market_event()      the next open/close, for the panel's countdown
    overnight_active()  is the 24/5 overnight stock session running?

Everything in this file is pure logic (no network), so it's easy to test.
All times are timezone-aware datetimes; the API gives them in UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from datetime import time as dtime
from zoneinfo import ZoneInfo

from .web import ApiError

# Overnight equity session (24/5 trading, e.g. Blue Ocean ATS): 20:00-04:00 ET,
# Sunday-Thursday nights, only when the next day is a trading day.
OVERNIGHT_START = dtime(20, 0)
OVERNIGHT_END = dtime(4, 0)


def parse_time(value: str) -> datetime:
    """Parse tastytrade timestamps. They come in two styles:

        "2026-09-25T13:30:00.000+00:00"   (ISO-8601)
        "2026-09-25 13:30:00+00"          (short offset, no "T")
    """
    v = value.strip().replace(" ", "T").replace("Z", "+00:00")
    t = v.find("T")
    sign = max(v.rfind("+"), v.rfind("-"))
    if t > 0 and sign > t and len(v) - sign == 3:
        v += ":00"  # '+00' -> '+00:00', which fromisoformat understands
    return datetime.fromisoformat(v)


@dataclass(frozen=True)
class Session:
    """One trading day's regular session."""
    open: datetime       # regular open (9:30 ET)
    close: datetime      # regular close (16:00 ET, or 13:00 on early-close days)
    close_ext: datetime  # end of after-hours trading (20:00 ET)


@dataclass
class SessionInfo:
    """What /market-time/equities/sessions/current returned: the current
    session (if the market trades today), the previous and the next one."""
    sessions: list[Session]  # sorted by open time

    @classmethod
    def from_api(cls, data: dict) -> "SessionInfo":
        """Build from the API's "data" object. Raises ApiError if it has no
        usable open/close times at all."""
        found = []
        for d in (data, data.get("previous-session"), data.get("next-session")):
            if d and d.get("open-at") and d.get("close-at"):
                close = parse_time(d["close-at"])
                ext = parse_time(d["close-at-ext"]) if d.get("close-at-ext") else close
                found.append(Session(parse_time(d["open-at"]), close, ext))
        if not found:
            raise ApiError(200, "bad_session", "session response had no open/close times")
        return cls(sorted(set(found), key=lambda s: s.open))  # set(): current may repeat previous/next

    def on(self, day: date, tz: ZoneInfo) -> Session | None:
        """The session opening on `day` (local date), if it's a trading day we know about."""
        for s in self.sessions:
            if s.open.astimezone(tz).date() == day:
                return s
        return None

    def today(self, now: datetime, tz: ZoneInfo) -> Session | None:
        """Today's session, or None on weekends, holidays or unknown days."""
        return self.on(now.astimezone(tz).date(), tz)

    def last_opened(self, now: datetime) -> Session | None:
        """The most recent session that has already opened (today's, once it
        opens; otherwise the previous trading day's)."""
        opened = [s for s in self.sessions if s.open <= now]
        return max(opened, key=lambda s: s.open) if opened else None


def market_event(now: datetime, info: SessionInfo | None) -> tuple[str, datetime] | None:
    """The next thing the market does, for the panel's countdown.

    ("close", today's close) during regular hours (early closes included);
    otherwise ("open", the next regular open). None without session data.

        Mon 11:00 -> ("close", Mon 16:00)     panel: "CLOSES 42m" (last hour)
        Mon 17:00 -> ("open",  Tue 9:30)      panel: "OPENS 16h"
        Sat 12:00 -> ("open",  Mon 9:30)      panel: "OPENS MON"
    """
    if info is None:
        return None
    for s in info.sessions:
        if s.open <= now < s.close:
            return "close", s.close
    upcoming = [s.open for s in info.sessions if s.open > now]
    return ("open", min(upcoming)) if upcoming else None


def overnight_active(now: datetime, info: SessionInfo | None, tz: ZoneInfo) -> bool:
    """True during an overnight equity session (24/5 stock trading).

    It runs 20:00-04:00 local and belongs to the NEXT trading day, so it's
    active only if a session opens on that day: Sunday-Thursday nights
    normally; not on Friday nights or on the eve of a holiday.
    """
    if info is None:
        return False
    local = now.astimezone(tz)
    if local.time() >= OVERNIGHT_START:
        leads_into = local.date() + timedelta(days=1)  # evening: tomorrow's session
    elif local.time() < OVERNIGHT_END:
        leads_into = local.date()                       # after midnight: today's session
    else:
        return False
    return info.on(leads_into, tz) is not None
