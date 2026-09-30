"""The daily schedule: which screen the panel shows right now, and how bright.

    mode       when                                          top of the panel     bottom
    ---------  --------------------------------------------  -------------------  ------------
    market     trading day, 9:30 until the close              one stock, full      (none)
                                                             screen with stats
    after      trading day, close until 20:00 / night_start   account value        random strip
    pre        trading day, premarket_start until 9:30        account value        random strip
    weekend    weekends and holidays, daytime                 account value        weather strip
    overnight  night_start until sleep_start, every day       account value        random strip
    sleep      sleep_start until night_end, every day         night sky (no data)

The times come from config.toml [schedule]; trading days, holidays and early
closes come from tastytrade (see sessions.py). ACCOUNT_MODES are the modes
that show the account value; QUIET_MODES are the ones where prices barely
move, so the fetcher asks for them less often.

Also here: brightness_for() and moon_phase() (for the night-sky screen).
Pure logic, no network.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from datetime import time as dtime
from zoneinfo import ZoneInfo

from .config import Config
from .sessions import Session

ACCOUNT_MODES = {"after", "pre", "weekend", "overnight"}  # account value on top, strip below
QUIET_MODES = {"weekend", "overnight"}  # little moves: poll the strip and account slowly


def _local(day: date, t: dtime, tz: ZoneInfo) -> datetime:
    """A local clock time on a given day, as a timezone-aware datetime."""
    return datetime.combine(day, t, tzinfo=tz)


def _in_window(t: dtime, start: dtime, end: dtime) -> bool:
    """start <= t < end on a 24-hour clock.

    Windows may cross midnight (23:00-06:30 contains 02:00); start == end is
    an empty window (used to switch sleep off).
    """
    if start == end:
        return False
    if start < end:
        return start <= t < end
    return t >= start or t < end


def is_night(now: datetime, cfg: Config) -> bool:
    """Between night_start and night_end (dimmer brightness)."""
    return _in_window(now.astimezone(cfg.tz).time(), cfg.night_start, cfg.night_end)


def is_sleep(now: datetime, cfg: Config) -> bool:
    """Between sleep_start and night_end (night-sky screen)."""
    return _in_window(now.astimezone(cfg.tz).time(), cfg.sleep_start, cfg.night_end)


def compute_mode(now: datetime, today: Session | None, cfg: Config) -> str:
    """What the panel should show at `now` (see the table at the top).

    `today` is today's trading session, or None on weekends and holidays
    (and when the session data couldn't be fetched: the panel then falls
    back to the weekend/overnight screens, which still work).
    """
    if today is not None:
        if today.open <= now < today.close:
            return "market"
        if today.close <= now < today.close_ext:
            return "after"
        pre_start = _local(now.astimezone(cfg.tz).date(), cfg.premarket_start, cfg.tz)
        if pre_start <= now < today.open:
            return "pre"
    if is_sleep(now, cfg):
        return "sleep"
    if is_night(now, cfg):
        return "overnight"
    return "after" if today is not None else "weekend"


def brightness_for(mode: str, now: datetime, cfg: Config) -> int:
    """Panel brightness (1-100): sleep, night or day level from config.toml."""
    if mode == "sleep":
        return cfg.brightness_sleep
    if is_night(now, cfg):
        return cfg.brightness_night
    return cfg.brightness_day


SYNODIC_MONTH = 29.530588853  # days from one new moon to the next (average)
KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)


def moon_phase(now: datetime) -> float:
    """Moon phase 0..1: 0 new, 0.25 first quarter, 0.5 full, 0.75 last quarter.

    Counts average lunar months from a known new moon: within about a day of
    the real phase, plenty for a picture of the moon.
    """
    days = (now - KNOWN_NEW_MOON).total_seconds() / 86400
    return (days / SYNODIC_MONTH) % 1.0
