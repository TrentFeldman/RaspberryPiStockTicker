// night_sky.h - the sleep screen: a calm night sky instead of numbers.
//
//   48 faint stars that twinkle slowly (a new pattern each day, the same all night)
//   the moon at tonight's real phase (from the fetcher's `moon` line), with craters
//   a shooting star every 3-8 minutes (the first one 20 s after start)
//   two single dim pixels in the bottom corners as status markers (colors.h):
//     bottom-left red     the fetcher reports a problem
//     bottom-right yellow test mode is on
//
// Everything is kept dim and warm so the room stays dark.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <ctime>

#include "colors.h"
#include "display_file.h"
#include "led.h"

inline constexpr double kPi = 3.14159265358979323846;

// Deterministic pseudo-random numbers: the same input always gives the same
// output, so the "random" sky stays put all night.
inline uint32_t Hash(uint32_t x) {
  x ^= x >> 16; x *= 0x7feb352d; x ^= x >> 15; x *= 0x846ca68b; x ^= x >> 16;
  return x;
}

// A shooting star in flight (or the wait for the next one).
struct ShootingStar {
  double start = -1;  // seconds (steady clock); < 0 = none active
  double next = 20;   // when the next one starts
  double x0 = 0, y0 = 0, dx = 0, dy = 0;  // start position and speed (px/s), set when one starts
};

// Warm white at level v (0-255) that stays neutral when dim. Very low values
// round to "off" one colour at a time (blue first, then green), so a fading
// warm pixel turned red before going dark: twinkling stars flared red. Below
// v=24 all three channels are equal and switch on/off together; the warm tint
// (g_ratio/b_ratio of red at full warmth) fades in between v=24 and v=84.
inline void SetWarm(Canvas *c, int x, int y, int v, double g_ratio, double b_ratio) {
  v = std::min(255, std::max(0, v));
  const double w = std::min(1.0, std::max(0.0, (v - 24) / 60.0));  // 0 = neutral .. 1 = fully warm
  c->SetPixel(x, y, v, (uint8_t)std::lround(v * (1 - w * (1 - g_ratio))),
              (uint8_t)std::lround(v * (1 - w * (1 - b_ratio))));
}

// Twinkling stars at time t (seconds), seeded by today's date. Stars that
// would overlap the moon (centre mx,my, radius r) are skipped.
inline void DrawStars(Canvas *c, double t, int mx, int my, int r) {
  const int W = c->width(), H = c->height();
  const time_t now = time(nullptr);
  struct tm lt;
  localtime_r(&now, &lt);
  const uint32_t seed = Hash(lt.tm_year * 400 + lt.tm_yday);  // a new sky each day
  for (int i = 0; i < 48; ++i) {
    const uint32_t h = Hash(seed + i * 7919);  // this star's own random bits
    const int x = h % W, y = (h >> 8) % (H - 4);
    if ((x - mx) * (x - mx) + (y - my) * (y - my) <= (r + 3) * (r + 3)) continue;  // keep clear of the moon
    const double period = 3.0 + (h >> 16) % 600 / 100.0;   // twinkle every 3-9 s
    const double phase = (h >> 4) % 628 / 100.0;           // so they don't all pulse together
    const double base = 0.35 + ((h >> 20) % 65) / 100.0;  // brightness 0.35-1.0
    const double tw = base * (0.55 + 0.45 * std::sin(2 * kPi * t / period + phase));
    const int v = (int)std::lround(150 * tw);
    SetWarm(c, x, y, v, 0.85, 0.65);
    if (i % 16 == 0) {  // a few brighter stars with a faint cross
      const int s = v / 3;
      SetWarm(c, x - 1, y, s, 0.85, 0.65);
      SetWarm(c, x + 1, y, s, 0.85, 0.65);
      SetWarm(c, x, y - 1, s, 0.85, 0.65);
      SetWarm(c, x, y + 1, s, 0.85, 0.65);
    }
  }
}

// The moon, centre (mx,my), radius r, at `phase` (0 new, .25 first quarter =
// right half lit, .5 full, .75 last quarter). The unlit part is a faint disc
// so the round shape stays readable.
inline void DrawMoon(Canvas *c, double phase, int mx, int my, int r) {
  const double k = std::cos(2 * kPi * phase);  // where the light/dark edge crosses each row
  const bool waxing = phase < 0.5;             // lit from the right while waxing
  static const int craters[][3] = {{-3, -2, 2}, {2, 3, 2}, {3, -4, 1}};  // dx, dy, radius
  for (int dy = -r; dy <= r; ++dy) {
    const double half = std::sqrt(std::max(0, r * r - dy * dy)) + 0.5;  // half-width of this row
    for (int dx = -r; dx <= r; ++dx) {
      if (std::fabs(dx) > half) continue;
      const bool lit = waxing ? dx > k * half : dx < -k * half;
      if (!lit) {
        SetWarm(c, mx + dx, my + dy, 12, 0.8, 0.6);  // faint, neutral
        continue;
      }
      double shade = 1.0;
      for (const auto &cr : craters)
        if ((dx - cr[0]) * (dx - cr[0]) + (dy - cr[1]) * (dy - cr[1]) <= cr[2] * cr[2]) shade = 0.72;
      c->SetPixel(mx + dx, my + dy, (uint8_t)(kMoonLit.r * shade), (uint8_t)(kMoonLit.g * shade),
                  (uint8_t)(kMoonLit.b * shade));
    }
  }
}

// A short diagonal streak with a fading tail, lasting 0.7 s. Starts a new one
// when it's time.
inline void DrawShootingStar(Canvas *c, double t, ShootingStar *shoot) {
  const int W = c->width();
  if (shoot->start < 0 && t >= shoot->next) {
    const uint32_t h = Hash((uint32_t)(t * 1000));
    shoot->start = t;
    shoot->x0 = 10 + h % (W - 50);
    shoot->y0 = 2 + (h >> 8) % 12;
    shoot->dx = 60 + (h >> 16) % 40;   // px per second
    shoot->dy = 25 + (h >> 24) % 20;
    shoot->next = t + 180 + (h >> 4) % 300;  // every 3-8 min
  }
  if (shoot->start < 0) return;
  const double age = t - shoot->start, life = 0.7;
  if (age > life) {
    shoot->start = -1;
    return;
  }
  const double fade = 1.0 - age / life;
  for (int i = 0; i < 8; ++i) {  // head first, then 7 tail pixels, each dimmer
    const double back = i * 0.018;
    const int x = (int)std::lround(shoot->x0 + shoot->dx * (age - back));
    const int y = (int)std::lround(shoot->y0 + shoot->dy * (age - back));
    SetWarm(c, x, y, (int)std::lround(200 * fade * (1.0 - i / 8.0)), 0.90, 0.75);
  }
}

// Unobtrusive health/test markers: one dim pixel each, bottom corners.
inline void DrawSleepMarkers(Canvas *c, const Display &d) {
  const int W = c->width(), H = c->height();
  if (d.status != "ok") c->SetPixel(0, H - 1, kSleepError.r, kSleepError.g, kSleepError.b);
  if (!d.test_label.empty()) c->SetPixel(W - 1, H - 1, kSleepTest.r, kSleepTest.g, kSleepTest.b);
}

// The whole sleep screen at time t (seconds since start).
inline void DrawNightSky(Canvas *c, const Display &d, double t, ShootingStar *shoot) {
  const int mx = c->width() - 22, my = 15, r = 9;  // moon centre and radius
  DrawStars(c, t, mx, my, r);
  DrawMoon(c, d.moon, mx, my, r);
  DrawShootingStar(c, t, shoot);
  DrawSleepMarkers(c, d);
}
