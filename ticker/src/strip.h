// strip.h - the scrolling strip at the bottom of the account screens.
//
//   | AAPL 341.46 ^1.6%    MSFT 512.10 v0.3%    68F Sunny    Today 93/68F  <- moving left
//
// Quotes first, then the weather items (from display.txt `weather` lines), each
// piece in its own colour: temperatures by how warm, the sky, UV, sun, moon.
//
// The fetcher replaces the strip's random picks every minute or two. The
// strip never jumps when that happens:
//   * same symbols, new prices  -> the new prices are used right away
//   * new symbols               -> they queue up right behind the current
//                                  set, which finishes scrolling first
//
// Scrolling is frame-locked: exactly 1 pixel every N screen refreshes (N set
// in main.cpp from --scroll-speed), so every step is held for the same time.
// Time-based steps judder whenever a frame lands late.
#pragma once

#include <cmath>
#include <string>
#include <vector>

#include "colors.h"
#include "display_file.h"
#include "fonts.h"
#include "format.h"
#include "led.h"
#include "widgets.h"

// One piece of a weather item: some text and its colour.
struct Piece {
  Color color;
  std::string text;
};

// Split a colour-tagged weather item into pieces:
//   "{label}Today {hot}93{label}/{mild}68F" -> grey "Today ", orange "93", grey "/", green "68F"
// Text before the first tag uses the default weather colour.
inline std::vector<Piece> ColorPieces(const std::string &s) {
  std::vector<Piece> out;
  Color color = kWeatherDefault;
  size_t i = 0;
  while (i < s.size()) {
    const size_t close = s[i] == '{' ? s.find('}', i) : std::string::npos;
    if (close != std::string::npos) {  // a tag: switch colour
      color = WeatherColor(s.substr(i + 1, close - i - 1));
      i = close + 1;
      continue;
    }
    size_t next = s.find('{', i + 1);  // text runs until the next tag
    if (next == std::string::npos) next = s.size();
    out.push_back({color, s.substr(i, next - i)});
    i = next;
  }
  return out;
}

// One pass of `quotes` starting at x; returns its total width. Items that
// are entirely off-screen are measured but not drawn. Big movers' symbols
// are gold.
inline int DrawStrip(Canvas *c, const Font &font, const std::vector<Quote> &quotes, int x, int baseline) {
  const int W = c->width();
  const int gap = 12;  // pixels between items
  int cx = x;
  for (const Quote &q : quotes) {
    if (q.text_only) {  // weather: coloured pieces of text
      const std::vector<Piece> pieces = ColorPieces(q.sym);
      int item_w = 0;
      for (const Piece &p : pieces) item_w += TextWidth(font, p.text);
      if (cx + item_w >= 0 && cx < W) {
        int ix = cx;
        for (const Piece &p : pieces) ix += DrawText(c, font, ix, baseline, p.color, p.text.c_str());
      }
      cx += item_w + gap;
      continue;
    }
    const std::string sym = q.sym + " ";
    const std::string price = FormatPrice(q.price) + " ";
    const std::string pct = Format("%.1f%%", std::fabs(q.change_pct));  // the arrow shows the sign
    const int item_w = TextWidth(font, sym) + TextWidth(font, price) + ChangeWidth(font, q.change_pct, pct);
    if (cx + item_w >= 0 && cx < W) {
      int ix = cx;
      ix += DrawText(c, font, ix, baseline, q.Get("big") > 0 ? kGold : kWhite, sym.c_str());
      ix += DrawText(c, font, ix, baseline, kFlat, price.c_str());
      DrawChange(c, font, ix, baseline, q.change_pct, pct);
    }
    cx += item_w + gap;
  }
  return cx - x;
}

// Same symbols in the same order (prices may differ)?
inline bool SameSymbols(const std::vector<Quote> &a, const std::vector<Quote> &b) {
  if (a.size() != b.size()) return false;
  for (size_t i = 0; i < a.size(); ++i)
    if (a[i].sym != b[i].sym) return false;
  return true;
}

// Scroll position and the set of quotes currently scrolling.
class StripScroller {
 public:
  // `width`: panel width (new sets start just off its right edge).
  // `frames_per_px`: move 1 pixel every this many frames (0 = still).
  StripScroller(int width, int frames_per_px) : width_(width), frames_per_px_(frames_per_px), x_(width) {}

  // Call once per frame, whether or not the strip is on screen.
  void Step() {
    if (frames_per_px_ > 0 && ++frame_no_ % frames_per_px_ == 0) x_ -= 1;
  }

  // Draw the strip at `baseline`. `latest` is what display.txt lists now;
  // it replaces the scrolling set as described at the top of this file.
  void Draw(Canvas *c, const Font &font, int baseline, const std::vector<Quote> &latest) {
    if (showing_.empty() && !latest.empty()) showing_ = latest, x_ = width_;  // start from the right edge
    else if (SameSymbols(showing_, latest)) showing_ = latest;               // just new prices
    if (showing_.empty()) return;
    const int strip_w = DrawStrip(c, font, showing_, x_, baseline);
    if (x_ + strip_w < width_ && !latest.empty())  // the end is on screen: the next pass follows it
      DrawStrip(c, font, latest, x_ + strip_w, baseline);
    if (x_ + strip_w <= 0) x_ += strip_w, showing_ = latest;  // this pass has gone: the next becomes current
  }

  // Forget the current set (the strip left the screen): the next Draw
  // starts afresh from the right edge.
  void Reset() { showing_.clear(); }

 private:
  int width_;
  int frames_per_px_;
  int x_;                       // left edge of the current pass (goes negative as it scrolls off)
  long frame_no_ = 0;
  std::vector<Quote> showing_;  // the set scrolling right now
};
