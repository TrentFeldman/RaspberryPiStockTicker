// screen.h - which screen to draw right now.
//
//   display.txt unreadable ............................ NO DATA + the reason
//   mode sleep ........................................ night sky (night_sky.h)
//   no quotes and no account yet ...................... NO DATA + health / "fetcher starting?"
//   market hours (not an account mode) with quotes ... one stock, full screen (screen_stock.h)
//   otherwise (pre, after, overnight, weekend) ........ account on top (screen_account.h),
//                                                        a divider, the scrolling strip (strip.h)
#pragma once

#include <string>
#include <vector>

#include "colors.h"
#include "display_file.h"
#include "fonts.h"
#include "health.h"
#include "led.h"
#include "night_sky.h"
#include "screen_account.h"
#include "screen_stock.h"
#include "strip.h"

// What the frame loop works out before drawing each frame.
struct FrameInfo {
  bool loaded = false;     // display.txt was read OK
  std::string load_error;  // why not, if it wasn't
  std::string health;      // "" or a problem to show (HealthText)
  size_t featured = 0;     // which quote's turn it is (FeaturedIndex)
  bool alt_phase = false;  // flips every 3 s: alternating texts
  double secs = 0;         // seconds since the ticker started: drives the animations
};

// Things that move across frames and remember where they were.
struct Animation {
  StripScroller strip;
  ShootingStar shooting_star;
};

// Draw one frame on an already cleared canvas.
inline void DrawScreen(Canvas *c, const Fonts &f, const Layout &layout, const Display &d, const FrameInfo &fr,
                       Animation *anim) {
  bool strip_shown = false;
  if (!fr.loaded) {
    DrawNoData(c, f, fr.load_error);
  } else if (d.mode == "sleep") {
    DrawNightSky(c, d, fr.secs, &anim->shooting_star);
  } else if (d.quotes.empty() && !d.has_account) {
    DrawNoData(c, f, fr.health.empty() ? "no quotes yet (fetcher starting?)" : fr.health);
  } else if (!IsAccountMode(d.mode) && !d.quotes.empty()) {
    // Market hours: the rotating stock gets the whole panel; no strip.
    DrawStockFull(c, f, d.quotes[fr.featured], fr.health, d, fr.alt_phase);
  } else {
    strip_shown = true;
    // Account on top (until the account value arrives: just any problem text).
    if (IsAccountMode(d.mode) && d.has_account)
      DrawAccount(c, f, d, fr.health, fr.alt_phase);
    else
      DrawText(c, *f.small, 2, 1 + f.small->baseline(), kAlert, fr.health.c_str());
    DrawLine(c, 0, layout.divider_y, c->width() - 1, layout.divider_y, kDim);
    std::vector<Quote> items = d.quotes;  // the strip: quotes, then the weather as plain text
    for (const std::string &w : d.weather) {
      Quote t{w, 0, 0, {}};
      t.text_only = true;
      items.push_back(t);
    }
    anim->strip.Draw(c, *f.strip, layout.strip_base, items);
  }
  if (!strip_shown) anim->strip.Reset();  // don't resume an old strip after market hours
}
