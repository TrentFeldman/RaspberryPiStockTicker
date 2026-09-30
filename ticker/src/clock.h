// clock.h - the wall clock and the market countdown.
//
//   ClockText   "9:18"          12-hour time, no seconds
//   EventText   "OPENS 1h12m"   time until the next open, or "CLOSES 42m"
//   CornerClock "TEST 9:18"     the clock as drawn in a screen corner (yellow in test mode)
//
// In test mode (pretend.sh) the fetcher writes `offset` = pretend minus real
// seconds; EffNow() adds it, so the clock and countdown follow the pretend
// time and keep ticking between file writes.
#pragma once

#include <algorithm>
#include <cstdio>
#include <ctime>
#include <string>

#include "colors.h"
#include "display_file.h"

// The panel's "now": real time plus the test-mode offset (0 normally).
inline time_t EffNow(const Display &d) { return time(nullptr) + static_cast<time_t>(d.offset); }

// "9:18": 12-hour local time (the Pi runs on America/New_York).
inline std::string ClockText(time_t t) {
  struct tm tm;
  localtime_r(&t, &tm);
  char buf[8];
  snprintf(buf, sizeof(buf), "%d:%02d", tm.tm_hour % 12 == 0 ? 12 : tm.tm_hour % 12, tm.tm_min);
  return buf;
}

// "OPENS 42m" / "OPENS 1h12m" / "OPENS 17h" / "OPENS MON" / "CLOSES 42m".
// Empty when unknown or already passed (e.g. the fetcher is down), so it
// never shows nonsense.
inline std::string EventText(const Display &d, time_t now) {
  if (d.event_at <= now || d.event_kind.empty()) return "";
  const long long s = d.event_at - now;  // seconds to go
  std::string when;
  if (s < 3600) {
    when = std::to_string(std::max(1LL, s / 60)) + "m";
  } else if (s < 10 * 3600) {
    char buf[16];
    snprintf(buf, sizeof(buf), "%lldh%02lldm", s / 3600, s % 3600 / 60);
    when = buf;
  } else if (s < 24 * 3600) {
    when = std::to_string(s / 3600) + "h";
  } else {  // a day or more away: the weekday is more useful than "63h"
    const time_t t = static_cast<time_t>(d.event_at);
    struct tm tm;
    localtime_r(&t, &tm);
    static const char *kDays[] = {"SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"};
    when = kDays[tm.tm_wday];
  }
  return (d.event_kind == "close" ? "CLOSES " : "OPENS ") + when;
}

// The clock for a screen corner, and its colour (*col): grey normally,
// yellow "TEST 9:18" in test mode.
inline std::string CornerClock(const Display &d, time_t now, Color *col) {
  *col = d.test_label.empty() ? kFlat : kTestBadge;
  return (d.test_label.empty() ? "" : "TEST ") + ClockText(now);
}
