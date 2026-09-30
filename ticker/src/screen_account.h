// screen_account.h - the top section outside market hours: the account.
//
//   +----------------------------------+
//   | ACCOUNT                     9:18 |  label row (alternates with "OPENS 1h12m")
//   |           $12,345.67             |  account value, centred
//   |        ^ +$98.76 +0.80%         |  change since the last trading day's start
//   |----------------------------------|  (the scrolling strip is below: strip.h)
//
// Shown pre-market, after hours, overnight and on weekends. A problem
// replaces the label with red health text.
#pragma once

#include <cmath>
#include <ctime>
#include <string>

#include "clock.h"
#include "colors.h"
#include "display_file.h"
#include "fonts.h"
#include "format.h"
#include "led.h"
#include "widgets.h"

// Label row: health text, or "ACCOUNT" alternating every 3 s with the
// countdown ("OPENS 1h12m"); the clock on the right if there's room.
inline void DrawAccountLabelRow(Canvas *c, const Fonts &f, const Display &d, const std::string &health,
                                bool alt_phase) {
  const int W = c->width();
  const int label_base = 1 + f.small->baseline();
  const time_t now = EffNow(d);
  int left_w;
  if (!health.empty()) {
    left_w = DrawText(c, *f.small, 2, label_base, kAlert, health.c_str());
  } else {
    const std::string event = EventText(d, now);
    const bool show_event = alt_phase && !event.empty();
    left_w = DrawText(c, *f.small, 2, label_base, show_event ? kFlat : kLabel,
                      show_event ? event.c_str() : "ACCOUNT");
  }
  Color clock_col;
  std::string clock = CornerClock(d, now, &clock_col);
  if (2 + left_w + 4 + TextWidth(*f.small, clock) > W - 2) clock = ClockText(now);  // drop "TEST "
  if (2 + left_w + 4 + TextWidth(*f.small, clock) <= W - 2)
    DrawText(c, *f.small, W - 2 - TextWidth(*f.small, clock), label_base, clock_col, clock.c_str());
}

// The value, centred below the label row. Drops the cents, then shrinks to
// the mid font, if it doesn't fit. Returns the y just below it.
inline int DrawAccountValue(Canvas *c, const Fonts &f, const Display &d) {
  const int W = c->width();
  std::string value = "$" + WithCommas(d.account, 2);
  const Font *vf = f.big;
  if (TextWidth(*vf, value) > W - 4) value = "$" + WithCommas(d.account, 0);
  if (TextWidth(*vf, value) > W - 4) vf = f.mid;
  const int value_top = 1 + f.small->height() + 2;
  DrawText(c, *vf, (W - TextWidth(*vf, value)) / 2, value_top + vf->baseline(), kWhite, value.c_str());
  return value_top + vf->height();
}

// "+$98.76 +0.80%" centred below `top` (just the % if the $ part doesn't
// fit). Nothing if the fetcher couldn't work out the change.
inline void DrawAccountChange(Canvas *c, const Fonts &f, const Display &d, int top) {
  if (!d.account_change_known) return;
  const int W = c->width();
  const double chg = d.account_change;
  const std::string pct = Format("%+.2f%%", d.account_pct);
  std::string text = (chg < 0 ? "-$" : "+$") + WithCommas(std::fabs(chg), std::fabs(chg) >= 1000 ? 0 : 2) + " " + pct;
  if (ChangeWidth(*f.mid, d.account_pct, text) > W - 4) text = pct;
  const int change_base = top + 2 + f.mid->baseline();
  DrawChange(c, *f.mid, (W - ChangeWidth(*f.mid, d.account_pct, text)) / 2, change_base, d.account_pct, text);
}

// The whole account top section (see the picture at the top).
inline void DrawAccount(Canvas *c, const Fonts &f, const Display &d, const std::string &health, bool alt_phase) {
  DrawAccountLabelRow(c, f, d, health, alt_phase);
  const int below_value = DrawAccountValue(c, f, d);
  DrawAccountChange(c, f, d, below_value);
}
