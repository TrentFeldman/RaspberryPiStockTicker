// screen_stock.h - market hours: one stock on the whole panel, with its stats.
//
//   +----------------------------------+
//   | AAPL                     $341.46 |  symbol + price          DrawSymbolAndPrice
//   |              ^ +5.54  +1.65%     |  change today            DrawChangeLine
//   | DAY  335 =====o== 343            |  today's range           DrawStockRanges
//   | 52W  169 ==========o== 360       |  52-week range
//   | OPEN 336.20  GAP +0.4%     10:32 |  open/gap + clock        DrawStockBottomLine
//   +----------------------------------+
//
// Extras:
//   big mover (big=1)      gold frame around the panel + "BIG MOVE" left of the change
//   near the 52-week high  the 52W row turns gold ("52W HI"); near the low, blue ("52W LO")
//   last hour of trading   the clock alternates with amber "CLOSES 42m"
//   halted                 "HALTED" in red on the bottom line
//   a problem              red health text replaces the bottom line's left side
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

// A 1-pixel gold border around the whole panel (big movers).
inline void DrawBigMoveFrame(Canvas *c) {
  const int W = c->width(), H = c->height();
  DrawLine(c, 0, 0, W - 1, 0, kGold);
  DrawLine(c, 0, H - 1, W - 1, H - 1, kGold);
  DrawLine(c, 0, 0, 0, H - 1, kGold);
  DrawLine(c, W - 1, 0, W - 1, H - 1, kGold);
}

// Top row: the symbol on the left, the price right-aligned. A long price
// drops to the mid font rather than collide.
inline void DrawSymbolAndPrice(Canvas *c, const Fonts &f, const Quote &q) {
  const int W = c->width();
  const int sym_base = 1 + f.big->baseline();
  const int sym_w = DrawText(c, *f.big, 2, sym_base, kWhite, q.sym.c_str());
  const std::string price = "$" + FormatPrice(q.price);
  const Font *pf = f.big;
  if (2 + sym_w + 6 + TextWidth(*f.big, price) > W - 2) pf = f.mid;
  DrawText(c, *pf, W - 2 - TextWidth(*pf, price), sym_base, kWhite, price.c_str());
}

// Second row (top at `top`): "+5.54  +1.65%" with an arrow, right-aligned
// (just the % if there's no room or no $ change). Big movers also get a gold
// "BIG MOVE" (or "BIG") at the left, if it fits.
inline void DrawChangeLine(Canvas *c, const Fonts &f, const Quote &q, int top, bool big) {
  const int W = c->width();
  const std::string pct = Format("%+.2f%%", q.change_pct);
  std::string change = pct;
  if (q.Has("chg")) {
    const double chg = q.Get("chg");
    const std::string abs_chg = (chg < 0 ? "-" : "+") + WithCommas(std::fabs(chg), std::fabs(chg) >= 1000 ? 0 : 2);
    if (ChangeWidth(*f.mid, q.change_pct, abs_chg + "  " + pct) <= W - 4) change = abs_chg + "  " + pct;
  }
  const int change_w = ChangeWidth(*f.mid, q.change_pct, change);
  DrawChange(c, *f.mid, W - 2 - change_w, top + f.mid->baseline(), q.change_pct, change);
  if (!big) return;
  for (const char *badge : {"BIG MOVE", "BIG"}) {  // the longest one that fits
    if (2 + TextWidth(*f.small, badge) + 4 <= W - 2 - change_w) {
      DrawText(c, *f.small, 2, top + f.mid->baseline(), kGold, badge);
      break;
    }
  }
}

// Bottom row (top at `top`). Left: health text if there's a problem, else
// HALTED, else "OPEN 336.20  GAP +0.4%".
// Right: the clock, alternating with amber "CLOSES 42m" in the last hour.
inline void DrawStockBottomLine(Canvas *c, const Fonts &f, const Quote &q, const std::string &health,
                                const Display &d, bool alt_phase, int top) {
  const int W = c->width();
  const int base = top + f.small->baseline();
  const time_t now = EffNow(d);
  Color right_col;
  std::string right = CornerClock(d, now, &right_col);
  if (d.event_kind == "close" && d.event_at - now <= 3600 && alt_phase && !EventText(d, now).empty())
    right = EventText(d, now), right_col = kAmber;
  const int room = W - 2 - TextWidth(*f.small, right) - 4 - 2;  // width available left of it
  if (!health.empty()) {
    DrawText(c, *f.small, 2, base, kAlert, health.c_str());
    if (TextWidth(*f.small, health) > room) right.clear();  // the problem matters more than the clock
  } else if (q.Get("halted") > 0) {
    DrawText(c, *f.small, 2, base, kAlert, "HALTED");
  } else if (q.Has("open")) {
    std::string line = "OPEN " + Compact(q.Get("open"));
    if (q.Has("prev") && q.Get("prev") > 0) {  // gap: how far the open was from yesterday's close
      const double gap = (q.Get("open") - q.Get("prev")) / q.Get("prev") * 100;
      const std::string with_gap = line + Format("  GAP %+.1f%%", gap);
      if (TextWidth(*f.small, with_gap) <= room) line = with_gap;
    }
    DrawText(c, *f.small, 2, base, kLabel, line.c_str());
  }
  if (!right.empty()) DrawText(c, *f.small, W - 2 - TextWidth(*f.small, right), base, right_col, right.c_str());
}

// The range rows, spread evenly between the change line (`free_top`) and the
// bottom line (`bottom_top`): today's range, then the 52-week range. With
// room for only one row, just today's range.
inline void DrawStockRanges(Canvas *c, const Fonts &f, const Quote &q, int free_top, int bottom_top) {
  const int sh = f.small->height();
  const bool day = q.Has("lo") && q.Has("hi");
  const bool year = q.Has("ylo") && q.Has("yhi");
  const int rows = (day ? 1 : 0) + (year ? 1 : 0);
  if (rows == 0) return;
  const int space = bottom_top - free_top;
  if (space < rows * sh) {
    if (space >= sh && day)  // room for one row only: the day range
      DrawRangeRow(c, *f.small, free_top + (space - sh) / 2, "DAY", kLabel, q.Get("lo"), q.Get("hi"), q.price,
                   ChangeColor(q.change_pct), kWhite);
    return;
  }
  const int gap = (space - rows * sh) / (rows + 1);
  int top = free_top + gap;
  if (day) {
    DrawRangeRow(c, *f.small, top, "DAY", kLabel, q.Get("lo"), q.Get("hi"), q.price, ChangeColor(q.change_pct),
                 kWhite);
    top += sh + gap;
  }
  if (year) {
    const double ylo = q.Get("ylo"), yhi = q.Get("yhi");
    const bool near_high = q.price >= yhi * 0.99, near_low = q.price <= ylo * 1.01;  // within 1%
    const Color &mark = near_high ? kGold : near_low ? kCool : kWhite;
    DrawRangeRow(c, *f.small, top, near_high ? "52W HI" : near_low ? "52W LO" : "52W",
                 near_high ? kGold : near_low ? kCool : kLabel, ylo, yhi, q.price, mark, mark);
  }
}

// The whole market-hours screen for quote `q` (see the picture at the top).
// `health` is "" or a problem to show; `alt_phase` flips every 3 s.
inline void DrawStockFull(Canvas *c, const Fonts &f, const Quote &q, const std::string &health,
                          const Display &d, bool alt_phase) {
  const bool big = q.Get("big") > 0;
  if (big) DrawBigMoveFrame(c);
  DrawSymbolAndPrice(c, f, q);
  const int change_top = 1 + f.big->height() + 1;
  DrawChangeLine(c, f, q, change_top, big);
  const int bottom_top = c->height() - f.small->height();
  DrawStockBottomLine(c, f, q, health, d, alt_phase, bottom_top);
  DrawStockRanges(c, f, q, change_top + f.mid->height() + 1, bottom_top);
}
