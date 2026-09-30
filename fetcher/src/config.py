"""Settings: read fetcher/config.toml into one Config object.

Every other file gets its settings from the Config made here, never from
the TOML file directly. config.toml is deployed together with the code, so
every setting is required: a missing one stops the fetcher at start-up with
a clear message ("config ...: missing setting 'timezone'") rather than
failing later in some odd way.

Where each setting lives in config.toml:

    [paths]      credentials, display, log_file, pretend
    [api]        base_url, timeout_sec
    [symbols]    stocks, etfs
    [weather]    location, units
    [schedule]   timezone, premarket_start, night_start, night_end, sleep_start
    [rotation]   seconds, lead_sec, strip
    [intervals]  seconds between refreshes of each data source
    [display]    brightness_day/night/sleep, big_move_pct
    [pretend]    max_minutes
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from datetime import datetime
from datetime import time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

from .util import unique

# The [intervals] entries the code uses (seconds). All required.
INTERVALS = ("sessions", "instruments", "quotes_day", "quotes_night", "account", "account_quiet",
             "weather", "heartbeat", "auth_backoff")


@dataclass
class Config:
    """All settings, already converted to the right types (paths, times, numbers)."""

    # [paths]
    credentials: Path             # tastytrade.conf (secrets; see credentials.py)
    display: Path                 # display.txt, read by the LED ticker
    log_file: Path                # fetcher.log
    pretend: Path                 # pretend.json, written by pretend.sh (test mode)
    # [api]
    base_url: str                 # tastytrade API, e.g. https://api.tastyworks.com
    timeout: float                # seconds before an HTTP request gives up
    # [symbols]
    stocks: list[str]
    etfs: list[str]
    # [weather]
    weather_location: str         # city / ZIP / "lat,lon"; "" = wttr.in guesses from the IP address
    weather_units: str            # "F" or "C"
    # [schedule] (clock times in `tz`)
    tz: ZoneInfo
    premarket_start: dtime        # pre-market screen starts (trading days)
    night_start: dtime            # dimmer; "overnight" screen
    night_end: dtime              # back to normal brightness
    sleep_start: dtime            # night-sky screen from here until night_end
    # [rotation]
    rotate_sec: float             # each stock's turn on the full screen (market hours)
    rack_lead: float              # pick + fetch the next stock this many seconds before its turn
    strip_size: int               # off hours: random picks in the scrolling strip
    # [intervals]: data source name -> seconds between refreshes
    intervals: dict[str, float]
    # [display]
    brightness_day: int
    brightness_night: int
    brightness_sleep: int
    big_move_pct: float           # |change %| at or above this: highlighted, and shown more often
    # [pretend]
    pretend_max_minutes: float    # test mode switches itself off after this

    @property
    def equities(self) -> list[str]:
        """Stocks and ETFs together: everything tastytrade lists under /equities."""
        return self.stocks + self.etfs


def _parse_hhmm(value: str) -> dtime:
    """ "06:30" -> 06:30 (a clock time)."""
    return datetime.strptime(value, "%H:%M").time()


def load_config(path: Path) -> Config:
    """Read config.toml. Stops the program with a clear message if a setting
    is missing."""
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    # [paths] are relative to the project folder (the one holding fetcher/);
    # absolute paths and ~ work too.
    root = Path(path).resolve().parent.parent

    def where(p: str) -> Path:
        return root / os.path.expanduser(p)  # an absolute path replaces root

    try:
        p, api, sym, weather, sch, rot, iv, disp = (raw[k] for k in (
            "paths", "api", "symbols", "weather", "schedule", "rotation", "intervals", "display"))
        return Config(
            credentials=where(p["credentials"]),
            display=where(p["display"]),
            log_file=where(p["log_file"]),
            pretend=where(p["pretend"]),
            base_url=api["base_url"].rstrip("/"),
            timeout=float(api["timeout_sec"]),
            # Duplicates are dropped (a symbol listed twice isn't picked twice as
            # often), and an ETF also listed under stocks counts once, as a stock.
            stocks=unique(sym["stocks"]),
            etfs=unique(sym["etfs"], skip=sym["stocks"]),
            weather_location=str(weather["location"]).strip(),
            weather_units="C" if str(weather["units"]).upper() == "C" else "F",
            tz=ZoneInfo(sch["timezone"]),
            premarket_start=_parse_hhmm(sch["premarket_start"]),
            night_start=_parse_hhmm(sch["night_start"]),
            night_end=_parse_hhmm(sch["night_end"]),
            sleep_start=_parse_hhmm(sch["sleep_start"]),
            # The ticker takes the turn length from the display file; below
            # 5 s a turn is too short to read and the fetch rate climbs.
            rotate_sec=max(5.0, float(rot["seconds"])),
            rack_lead=float(rot["lead_sec"]),
            strip_size=max(1, int(rot["strip"])),
            intervals={k: float(iv[k]) for k in INTERVALS},
            brightness_day=int(disp["brightness_day"]),
            brightness_night=int(disp["brightness_night"]),
            brightness_sleep=int(disp["brightness_sleep"]),
            big_move_pct=float(disp["big_move_pct"]),
            pretend_max_minutes=float(raw["pretend"]["max_minutes"]),
        )
    except KeyError as e:
        raise SystemExit(f"config {path}: missing setting {e}") from None
