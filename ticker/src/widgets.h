// widgets.h - small drawing building blocks shared by the screens.
//
//   DrawChange    a green up-arrow / red down-arrow plus text: "^ +1.65%"
//   DrawRangeRow  "DAY  335 ======o=== 343": where the price sits in a range
//
// Colours for changes: green up, red down, grey when (practically) flat.
#pragma once

#include <algorithm>
#include <cmath>
#include <string>

#include "colors.h"
#include "fonts.h"
#include "format.h"
#include "led.h"

// A change under 0.005% shows as flat (no arrow, grey): it would print as 0.00%.
inline bool IsFlat(double pct) { return std::fabs(pct) < 0.005; }

inline const Color &ChangeColor(double pct) {
  if (IsFlat(pct)) return kFlat;
  return pct > 0 ? kUp : kDown;
}

// Arrow size that suits a font: about half the height above the baseline, odd
// (so the tip is a single pixel in the middle).
inline int ArrowWidth(const Font &font) { return std::max(5, (font.baseline() / 2) * 2 + 1); }

// Solid triangle, `w` wide (odd), pointing up or down, bottom edge on `base_y`.
// Returns the width used.
inline int DrawArrow(Canvas *c, int x, int base_y, bool up, int w, const Color &col) {
  const int h = (w + 1) / 2;
  for (int i = 0; i < h; ++i) {
    const int half = up ? i : h - 1 - i;  // row i counts from the top
    const int y = base_y - h + 1 + i;
    for (int dx = -half; dx <= half; ++dx) c->SetPixel(x + w / 2 + dx, y, col.r, col.g, col.b);
  }
  return w;
}

// Width DrawChange() will use for this text (for right-aligning it).
inline int ChangeWidth(const Font &font, double pct, const std::string &text) {
  return (IsFlat(pct) ? 0 : ArrowWidth(font) + 2) + TextWidth(font, text);
}

// Draws the arrow (if the change isn't flat) plus text, coloured by the
// change; returns the width used.
inline int DrawChange(Canvas *c, const Font &font, int x, int baseline, double pct, const std::string &text) {
  const Color &col = ChangeColor(pct);
  int w = 0;
  if (!IsFlat(pct)) w += DrawArrow(c, x, baseline - 1, pct > 0, ArrowWidth(font), col) + 2;
  w += DrawText(c, font, x + w, baseline, col, text.c_str());
  return w;
}

// "LABEL lo [====o---] hi" on one row whose top is at `top`. The part of the
// bar up to the price is tinted with a third of `fill`; the marker (3 px
// tall) is `marker`. Returns false (drawing only the label and low end) if
// the bar would be too short to mean anything.
inline bool DrawRangeRow(Canvas *c, const Font &font, int top, const char *label, const Color &label_col,
                         double lo, double hi, double price, const Color &fill, const Color &marker) {
  const int W = c->width();
  const int base = top + font.baseline();
  const std::string los = Compact(lo), his = Compact(hi);
  int x = 2;
  x += DrawText(c, font, x, base, label_col, label) + 3;
  x += DrawText(c, font, x, base, kFlat, los.c_str()) + 3;
  const int hi_w = TextWidth(font, his);
  const int bar0 = x, bar1 = W - 2 - hi_w - 3;  // the bar fills the space between the numbers
  if (bar1 - bar0 < 12) return false;
  DrawText(c, font, W - 2 - hi_w, base, kFlat, his.c_str());

  const int y = top + (font.baseline() + 1) / 2;  // middle of the digits
  const double t = hi > lo ? std::min(1.0, std::max(0.0, (price - lo) / (hi - lo))) : 0.5;
  const int mx = bar0 + (int)std::lround(t * (bar1 - bar0));  // marker position
  DrawLine(c, bar0, y, bar1, y, kTrack);
  if (mx > bar0) DrawLine(c, bar0, y, mx - 1, y, Color(fill.r / 3, fill.g / 3, fill.b / 3));
  for (int dy = -1; dy <= 1; ++dy) DrawLine(c, mx, y + dy, std::min(mx + 1, bar1), y + dy, marker);
  return true;
}
