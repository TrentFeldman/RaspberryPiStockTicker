"""Tests for src/weather.py: wttr.in JSON becomes short strip items, tagged with colours."""

import unittest
from datetime import datetime

from helpers import ET
from src.display_file import DisplayState, render_display
from src.weather import TEMP_BANDS, UV_BANDS, _band, _sky, parse_weather


def hourly(*rows):
    return [{"time": t, "tempF": f, "tempC": c, "chanceofrain": r} for t, f, c, r in rows]


SKY = [{"sunrise": "07:30 AM", "sunset": "07:25 PM", "moon_illumination": "93", "moon_phase": "Waning Gibbous"}]

# wttr.in ?format=j1 shape (trimmed).
J1 = {
    "current_condition": [{"temp_F": "68", "temp_C": "20", "FeelsLikeF": "70", "FeelsLikeC": "21",
                           "humidity": "52", "windspeedMiles": "2", "windspeedKmph": "3", "winddir16Point": "N",
                           "uvIndex": "0", "weatherDesc": [{"value": "Sunny "}]}],
    "nearest_area": [{"areaName": [{"value": "Ulaanbaatar"}]}],
    "weather": [
        {"maxtempF": "93", "mintempF": "68", "maxtempC": "34", "mintempC": "20", "astronomy": SKY,
         "hourly": hourly(("900", "72", "22", "2"), ("1200", "87", "31", "1"), ("1500", "93", "34", "0"),
                          ("1800", "88", "31", "30"), ("2100", "76", "24", "7"))},
        {"maxtempF": "92", "mintempF": "71", "maxtempC": "33", "mintempC": "22", "astronomy": SKY,
         "hourly": hourly(("0", "73", "23", "40"), ("300", "71", "22", "10"))},
    ],
}


class WeatherTests(unittest.TestCase):
    def test_items(self):
        items, area = parse_weather(J1, "F", datetime(2026, 9, 29, 10, 0, tzinfo=ET))
        self.assertEqual(items, [
            "{mild}68F {sun}Sunny", "{label}Feels {mild}70F", "{label}Humidity {value}52%",
            "{label}Wind {value}2mph N",                                            # UV 0: left out
            "{label}Today {hot}93{label}/{mild}68F {rain}rain 30%",
            "{label}Noon {hot}87F", "{label}3pm {hot}93F", "{label}6pm {hot}88F {rain}rain 30%",
            "{label}9pm {warm}76F",                                                 # the next 4 steps
            "{label}Tomorrow {hot}92{label}/{mild}71F {rain}rain 40%",
            "{label}Sunrise {sunrise}7:30", "{label}Sunset {sunset}7:25",
            "{label}Moon {moon}93% Waning Gibbous"])
        self.assertEqual(area, "Ulaanbaatar")

    def test_late_evening_hours_run_into_tomorrow(self):
        items, _ = parse_weather(J1, "F", datetime(2026, 9, 29, 22, 0, tzinfo=ET))
        self.assertIn("{label}12am {mild}73F {rain}rain 40%", items)
        self.assertNotIn("{label}9pm {warm}76F", items)

    def test_celsius(self):
        items, _ = parse_weather(J1, "C", datetime(2026, 9, 29, 10, 0, tzinfo=ET))
        self.assertEqual(items[:4], ["{mild}20C {sun}Sunny", "{label}Feels {mild}21C", "{label}Humidity {value}52%",
                                     "{label}Wind {value}3km/h N"])  # colour bands still come from F

    def test_colour_bands(self):
        self.assertEqual([_band(t, TEMP_BANDS, "scorch") for t in (32, 33, 64, 65, 94, 95)],
                         ["freeze", "cold", "cool", "mild", "hot", "scorch"])
        self.assertEqual([_band(u, UV_BANDS, "uv-ext") for u in (2, 3, 8, 11)], ["uv-low", "uv-mod", "uv-vhigh", "uv-ext"])
        self.assertEqual([_sky(d) for d in ("Patchy light rain with thunder", "Light freezing rain", "Partly cloudy",
                                            "Mist", "Clear", "Tornado")],
                         ["storm", "snow", "cloud", "fog", "sun", "value"])

    def test_bad_reply_raises(self):
        with self.assertRaises(KeyError):
            parse_weather({"error": "Unknown location"}, "F", datetime(2026, 9, 29, 10, 0, tzinfo=ET))

    def test_display_lines_only_with_the_strip(self):
        st = DisplayState(mode="weekend", weather=["{mild}68F {sun}Sunny", "{label}Humidity {value}52%"])
        self.assertIn("weather {mild}68F {sun}Sunny\nweather {label}Humidity {value}52%\n", render_display(st))
        st.mode = "market"  # full-screen stock view: no strip, no weather
        self.assertNotIn("weather", render_display(st))


if __name__ == "__main__":
    unittest.main()
