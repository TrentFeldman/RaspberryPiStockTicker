"""Weather for the scrolling strip, from wttr.in (free, no key, no login).

wttr.in is the "curl wttr.in" terminal weather service; ?format=j1 gives the
same forecast as JSON. To be kind to it, the weather is only fetched while
the strip is on screen (pre-market, after hours, evenings, weekends), at most
every 30 minutes (config.toml [intervals] weather): never during market
hours or at night.

The strip shows these items after the quotes:

    now        68F Sunny   Feels 70F   Humidity 52%   Wind 2mph N   UV 7
    today      Today 93/68F rain 30%
    next hours Noon 87F   3pm 93F   6pm 88F rain 30%   9pm 76F
    tomorrow   Tomorrow 92/71F rain 40%
    sky        Sunrise 7:30   Sunset 7:25   Moon 93% Waning Gibbous

Some items only appear when they say something: "Feels" when it differs from
the temperature, UV when above 0, rain when the chance is 20% or more.
"Next hours" are the next four of wttr.in's 3-hourly steps.

Colour: every piece of text is tagged with a colour NAME for the ticker,
e.g. "{hot}93F {sun}Sunny". This file decides what each piece is (a hot
temperature, sunny sky, a high UV index); the ticker's colors.h decides
what colour that is (WeatherColor). The names:

    label, value                     grey labels, white plain values
    freeze cold cool mild warm hot scorch
                                     temperatures by band (TEMP_BANDS, in F)
    sun cloud fog rain storm snow    the sky (from wttr.in's description)
    uv-low uv-mod uv-high uv-vhigh uv-ext
                                     the UV index (the standard WHO bands)
    sunrise sunset moon

Location: config.toml [weather] location; empty = wttr.in guesses from this
connection's IP address. The place it picked is logged ("weather for ...").

Weather is a nice-to-have: if wttr.in is down, the last good weather stays
for up to 3 hours, then the strip simply leaves it out. It never shows an
error on the panel (the log has it).
"""

from __future__ import annotations

import time
import urllib.parse
from datetime import datetime

from . import web
from .config import Config
from .logs import log
from .web import ApiError

WTTR_URL = "https://wttr.in/"
STALE_AFTER = 3 * 3600  # seconds: older weather is dropped rather than shown as current
RAIN_SHOWN_FROM = 20    # % chance of rain worth mentioning
NEXT_HOURS = 4          # how many upcoming 3-hour steps to show

# Colour bands: (highest value in the band, colour name). Above the last: the fallback.
TEMP_BANDS = ((32, "freeze"), (49, "cold"), (64, "cool"), (74, "mild"), (84, "warm"), (94, "hot"))  # F
UV_BANDS = ((2, "uv-low"), (5, "uv-mod"), (7, "uv-high"), (10, "uv-vhigh"))  # WHO UV index bands
# Sky colour from words in wttr.in's description, first match wins
# ("Patchy light rain with thunder" is a storm, not just rain).
SKY_WORDS = (("storm", ("thunder",)),
             ("snow", ("snow", "sleet", "blizzard", "ice", "freezing")),
             ("rain", ("rain", "drizzle", "shower")),
             ("fog", ("fog", "mist", "haze")),
             ("cloud", ("cloud", "overcast")),
             ("sun", ("sun", "clear")))


def _c(name: str, text: str) -> str:
    """Tag `text` with a colour name for the ticker: _c("hot", "93F") -> "{hot}93F"."""
    return "{" + name + "}" + text


def _band(value: float, bands, above: str) -> str:
    """The colour name of the band `value` falls in (`above` past the last one)."""
    return next((name for top, name in bands if value <= top), above)


def _sky(desc: str) -> str:
    """Colour name for a sky description: "Partly cloudy" -> "cloud"."""
    d = desc.lower()
    return next((name for name, words in SKY_WORDS if any(w in d for w in words)), "value")


def _clean(text: str) -> str:
    """Text from wttr.in made safe for the panel: plain ASCII (the fonts have
    nothing else), no braces (they mark colours), single spaces."""
    return " ".join(text.encode("ascii", "ignore").decode().replace("{", "").replace("}", "").split())


def _temp(rec: dict, prefix: str, u: str, unit: bool = True) -> str:
    """A temperature in the chosen units, coloured by how warm it is (the band
    always comes from the Fahrenheit value). `prefix` is wttr.in's field name
    without its unit letter: "temp_" -> temp_F / temp_C."""
    return _c(_band(float(rec[prefix + "F"]), TEMP_BANDS, "scorch"), rec[prefix + u] + (u if unit else ""))


def _rain(chance: int) -> str:
    """ " {rain}rain 40%", or "" when the chance is too small to mention."""
    return " " + _c("rain", f"rain {chance}%") if chance >= RAIN_SHOWN_FROM else ""


def _day(label: str, day: dict, u: str) -> str:
    """ "Today 93/68F rain 30%": high/low, each coloured by its own band, plus
    the day's highest hourly rain chance."""
    rain = max(int(h["chanceofrain"]) for h in day["hourly"])
    return (_c("label", label + " ") + _temp(day, "maxtemp", u, unit=False) + _c("label", "/")
            + _temp(day, "mintemp", u) + _rain(rain))


def _hour_label(hhmm: int) -> str:
    """wttr.in hourly time (0, 300, ... 2100) -> "12am", "3am", "Noon", "3pm"."""
    h = hhmm // 100
    return "Noon" if h == 12 else f"{h % 12 or 12}{'am' if h < 12 else 'pm'}"


def _clock(t: str) -> str:
    """ "07:30 AM" -> "7:30" (sunrise is morning, sunset evening: no AM/PM needed)."""
    return t.split()[0].lstrip("0")


def parse_weather(data: dict, units: str, now: datetime) -> tuple[list[str], str]:
    """wttr.in j1 JSON -> (strip items with colour tags, place name). `now` is
    the local time (picks the upcoming hours). Raises KeyError/IndexError/
    ValueError/TypeError if the reply isn't shaped as expected."""
    metric = units == "C"
    u = "C" if metric else "F"
    cur = data["current_condition"][0]
    today, tomorrow = data["weather"][0], data["weather"][1]

    # Now.
    desc = _clean(cur["weatherDesc"][0]["value"])
    items = [_temp(cur, "temp_", u) + " " + _c(_sky(desc), desc)]
    if cur["FeelsLike" + u] != cur["temp_" + u]:
        items.append(_c("label", "Feels ") + _temp(cur, "FeelsLike", u))
    items.append(_c("label", "Humidity ") + _c("value", cur["humidity"] + "%"))
    wind = int(cur["windspeedKmph" if metric else "windspeedMiles"])
    speed = f"{wind}{'km/h' if metric else 'mph'} {_clean(cur['winddir16Point'])}" if wind else "calm"
    items.append(_c("label", "Wind ") + _c("value", speed))
    uv = int(cur["uvIndex"])
    if uv > 0:
        items.append(_c("label", "UV ") + _c(_band(uv, UV_BANDS, "uv-ext"), str(uv)))

    # Today, the next few hours (running into tomorrow late in the day), tomorrow.
    items.append(_day("Today", today, u))
    hhmm = now.hour * 100 + now.minute
    upcoming = [h for h in today["hourly"] if int(h["time"]) > hhmm] + tomorrow["hourly"]
    items += [_c("label", _hour_label(int(h["time"])) + " ") + _temp(h, "temp", u) + _rain(int(h["chanceofrain"]))
              for h in upcoming[:NEXT_HOURS]]
    items.append(_day("Tomorrow", tomorrow, u))

    # Sun and moon.
    sky = today["astronomy"][0]
    items += [_c("label", "Sunrise ") + _c("sunrise", _clock(sky["sunrise"])),
              _c("label", "Sunset ") + _c("sunset", _clock(sky["sunset"])),
              _c("label", "Moon ") + _c("moon", f"{sky['moon_illumination']}% {_clean(sky['moon_phase'])}")]

    area = (data.get("nearest_area") or [{}])[0].get("areaName", [{}])[0].get("value", "?")
    return items, _clean(area)


class WeatherData:
    """The latest weather items for the strip."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.items: list[str] = []
        self.at = 0.0    # epoch of the last good refresh
        self.area = ""   # place wttr.in reported (logged when it changes)

    def refresh(self) -> None:
        url = WTTR_URL + urllib.parse.quote(self.cfg.weather_location) + "?format=j1"
        data = web.http_json("GET", url, timeout=self.cfg.timeout)
        try:
            items, area = parse_weather(data, self.cfg.weather_units, datetime.now(self.cfg.tz))
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as e:
            raise ApiError(200, "bad_weather", f"unexpected wttr.in reply ({type(e).__name__}: {e})") from None
        if area != self.area:
            log.info("weather for %s", area)
            self.area = area
        self.items, self.at = items, time.time()

    def current(self, now: float) -> list[str]:
        """The items to show now: [] if there's none yet or it's over 3 hours old."""
        return self.items if now - self.at < STALE_AFTER else []
