// fonts.h - the four text sizes and where things sit vertically.
//
// The ticker uses four font "roles", chosen in fonts.conf (format
// and how to change them: panel.h, FontChoice):
//
//   big    symbol, price, account value          (default 9x18B)
//   mid    change lines                          (default 7x13B)
//   small  labels, clock, ranges, health text    (default 5x8)
//   strip  the scrolling strip                   (default 7x13)
//
// Nothing is laid out at fixed pixel positions: rows are placed from the
// font heights, so a different font choice still fits.
#pragma once

#include <algorithm>
#include <cstdio>
#include <map>
#include <memory>
#include <string>

#include "led.h"
#include "panel.h"

// Width of `text` in pixels.
inline int TextWidth(const Font &font, const std::string &text) {
  int w = 0;
  for (char c : text) w += font.CharacterWidth(c);
  return w;
}

// Loaded fonts, kept for the life of the program (a Font can't be copied, so
// they live here and the screens use pointers to them).
class FontCache {
 public:
  // The font at `path`, or nullptr (with a message) if it can't be loaded.
  const Font *Get(const std::string &path) {
    auto it = fonts_.find(path);
    if (it != fonts_.end()) return it->second.get();
    auto f = std::make_unique<Font>();
    if (!f->LoadFont(path.c_str())) {
      fprintf(stderr, "Couldn't load font %s\n", path.c_str());
      return nullptr;
    }
    return (fonts_[path] = std::move(f)).get();
  }

 private:
  std::map<std::string, std::unique_ptr<Font>> fonts_;
};

// The font for each role.
struct Fonts {
  const Font *big = nullptr;    // symbol, price, account value
  const Font *mid = nullptr;    // change lines
  const Font *small = nullptr;  // index, labels, health
  const Font *strip = nullptr;  // scrolling strip
};

// Load the fonts named in `choice`. A font that fails to load falls back to
// the default for that role, so a bad fonts.conf never blanks the panel.
// False only if even a default can't be loaded.
inline bool ResolveFonts(const FontChoice &choice, FontCache *cache, Fonts *out) {
  const FontChoice defaults;
  const std::string *want[] = {&choice.big, &choice.mid, &choice.small, &choice.strip};
  const std::string *fallback[] = {&defaults.big, &defaults.mid, &defaults.small, &defaults.strip};
  const Font **slot[] = {&out->big, &out->mid, &out->small, &out->strip};
  for (int i = 0; i < 4; ++i) {
    const Font *f = cache->Get(*want[i]);
    if (!f) f = cache->Get(*fallback[i]);
    if (!f) return false;
    *slot[i] = f;
  }
  return true;
}

// Where the account screens split: the top section above a dim divider line,
// the scrolling strip below it.
//
//   +------------------------------+
//   | top section                  |
//   |------------------------------| <- divider_y
//   | AAPL 341.46 ^1.6%  MSFT ...  | <- strip text sits on strip_base
//   +------------------------------+
struct Layout {
  int divider_y;   // y of the dim line between the top section and the strip
  int strip_base;  // baseline of the scrolling strip

  static Layout For(const Fonts &f, int height) {
    Layout l;
    l.divider_y = std::max(20, height - f.strip->height() - 2);
    l.strip_base = l.divider_y + 2 + f.strip->baseline();
    return l;
  }
};
