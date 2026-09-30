// colors.h - every colour the ticker uses, in one place.
//
// Values are (red, green, blue), 0-255 each. The panel's overall brightness
// (display.txt "brightness") scales everything, so these are relative levels.
// Very dim colours (below ~25) round off one channel at a time on this
// panel; see SetWarm() in night_sky.h for what that did to the stars.
#pragma once

#include <map>
#include <string>

#include "led.h"

// Text and numbers.
inline const Color kWhite(255, 255, 255);    // symbols, prices, the account value
inline const Color kFlat(140, 140, 140);     // no change; secondary numbers (ranges, clock)
inline const Color kLabel(90, 90, 90);       // labels: ACCOUNT, DAY, 52W, OPEN
inline const Color kDim(40, 40, 40);         // the divider line above the strip

// Price moves.
inline const Color kUp(0, 200, 0);           // up today (green)
inline const Color kDown(220, 0, 0);         // down today (red)

// Highlights.
inline const Color kGold(230, 170, 0);       // big movers, near the 52-week high
inline const Color kCool(0, 150, 220);       // near the 52-week low
inline const Color kTrack(35, 35, 35);       // the empty part of a range bar
inline const Color kAmber(255, 120, 0);      // "CLOSES 42m" in the market's last hour
inline const Color kTestBadge(200, 200, 0);  // the clock while test mode (pretend.sh) is on

// Problems: STALE, "! AUTH ...", HALTED, NO DATA.
inline const Color kAlert(255, 40, 0);

// Night sky (sleep screen). Stars and the shooting star are drawn with
// SetWarm() in night_sky.h instead of fixed colours, so they fade cleanly.
inline const Color kMoonLit(210, 175, 120);  // the lit part of the moon (craters are 72% of this)
inline const Color kSleepError(60, 0, 0);    // one dim pixel, bottom-left: the fetcher reports a problem
inline const Color kSleepTest(50, 50, 0);    // one dim pixel, bottom-right: test mode is on

// Weather in the strip. The fetcher tags each piece of weather text with a
// colour name ("{hot}93F {sun}Sunny"; which name when: fetcher/src/weather.py).
// This is what each name looks like; an unknown name gets kWeatherDefault.
inline const Color kWeatherDefault(0, 150, 220);
inline Color WeatherColor(const std::string &name) {
  static const std::map<std::string, Color> kPalette = {
      {"label", kFlat},                // Today, Humidity, Wind, 3pm, ...
      {"value", kWhite},               // plain numbers: 52%, 2mph N
      // Temperatures, coldest to hottest (bands in weather.py TEMP_BANDS).
      {"freeze", Color(160, 205, 255)},  // 32F and below: icy
      {"cold", Color(60, 150, 255)},     // 33-49F
      {"cool", Color(0, 200, 190)},      // 50-64F
      {"mild", Color(110, 220, 70)},     // 65-74F
      {"warm", Color(245, 205, 30)},     // 75-84F
      {"hot", Color(255, 130, 0)},       // 85-94F
      {"scorch", Color(255, 45, 25)},    // 95F and up
      // The sky.
      {"sun", Color(255, 200, 0)},       // Sunny, Clear
      {"cloud", Color(175, 180, 200)},   // Cloudy, Overcast, Partly cloudy
      {"fog", Color(120, 120, 135)},     // Fog, Mist
      {"rain", Color(70, 140, 255)},     // rain, drizzle, showers (and "rain 40%")
      {"storm", Color(190, 90, 255)},    // thunder
      {"snow", Color(230, 240, 255)},    // snow, sleet, ice
      // UV index, the standard WHO colours.
      {"uv-low", Color(80, 200, 80)},    // 0-2
      {"uv-mod", Color(240, 220, 0)},    // 3-5
      {"uv-high", Color(255, 140, 0)},   // 6-7
      {"uv-vhigh", Color(240, 40, 40)},  // 8-10
      {"uv-ext", Color(190, 80, 255)},   // 11+
      // Sun and moon.
      {"sunrise", Color(255, 190, 60)},
      {"sunset", Color(255, 105, 65)},
      {"moon", Color(215, 205, 170)},
  };
  const auto it = kPalette.find(name);
  return it == kPalette.end() ? kWeatherDefault : it->second;
}
