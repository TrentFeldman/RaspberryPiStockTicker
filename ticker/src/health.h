// health.h - making problems visible on the wall.
//
//   HealthText  the red text shown in place of a label when something's wrong:
//                 "NO DATA YET"   the fetcher hasn't had a good quote refresh yet
//                 "STALE 12m"     no good quote refresh for over --stale-after (5 min)
//                 "! NO NETWORK 12m"   the Pi can't reach the internet (DNS or
//                                 connection trouble). Once the data is stale
//                                 it replaces "STALE", because it's the cause.
//                 "! AUTH 400 invalid_grant"   the fetcher's status (alternates
//                                 with the normal label every 3 s)
//   DrawNoData  the whole-screen "NO DATA" message (display.txt unreadable,
//               or nothing to show yet)
//
// The sleep screen shows no text at all; a problem there is one dim red pixel
// in the bottom-left corner (night_sky.h).
#pragma once

#include <algorithm>
#include <ctime>
#include <string>

#include "colors.h"
#include "display_file.h"
#include "fonts.h"
#include "led.h"

// Health text for the panel, or "" when all is well. `alternate_phase` flips
// every 3 s: status errors show only in one phase, so the normal label stays
// readable too.
inline std::string HealthText(const Display &d, bool loaded, time_t now, int stale_after, bool alternate_phase) {
  if (!loaded || d.mode == "sleep") return "";  // sleep: no data is expected; no text at night
  if (stale_after > 0) {
    if (d.updated <= 0) return "NO DATA YET";
    const long age = now - d.updated;
    if (age > stale_after) {
      if (d.status.rfind("NO NETWORK", 0) == 0) return "! " + d.status.substr(0, 23);  // the cause, not just "STALE"
      return age < 5400 ? "STALE " + std::to_string(age / 60) + "m"
                        : "STALE " + std::to_string(age / 3600) + "h";
    }
  }
  if (d.status != "ok" && alternate_phase) return "! " + d.status.substr(0, 23);
  return "";
}

// Full-screen message when there is nothing sensible to show: "NO DATA" in
// big red letters, then the reason, wrapped to the panel width.
inline void DrawNoData(Canvas *c, const Fonts &f, const std::string &reason) {
  DrawText(c, *f.big, 2, 2 + f.big->baseline(), kAlert, "NO DATA");
  const int char_w = std::max(1, f.small->CharacterWidth('m'));
  const size_t per_line = (c->width() - 4) / char_w;
  int y = 4 + f.big->height() + f.small->baseline();
  for (size_t i = 0; i < reason.size() && y < c->height(); i += per_line, y += f.small->height() + 1)
    DrawText(c, *f.small, 2, y, kFlat, reason.substr(i, per_line).c_str());
}
