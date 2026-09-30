// main.cpp - the ticker: draws display.txt on the 128x64 LED panel, ~60 times a second.
//
// Start here. What happens:
//   1. set up the panel (panel.h: calibration from panel.conf), read options, load fonts
//   2. read display.txt (written by the fetcher; format in display_file.h)
//   3. loop until stopped (Ctrl-C / systemctl stop):
//        once a second  re-read display.txt if it changed; apply its brightness
//        every frame    work out whose turn it is and whether anything's wrong,
//                       draw the right screen (screen.h), show it
//
// The ticker never talks to the internet: the fetcher does that. If the
// fetcher stops, the last data stays up and turns into a red STALE warning.
//
// Usage: ./ticker [--display=FILE] [--scroll-speed=30]
//                 [--stale-after=300 (seconds, 0 = off)] [--led-... overrides]
//
// Runs as root (service hub75-ticker) for real-time priority: smooth scrolling.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include <unistd.h>

#include "display_file.h"
#include "fonts.h"
#include "health.h"
#include "panel.h"
#include "rotation.h"
#include "screen.h"

using Clock = std::chrono::steady_clock;

// The panel refreshes at most 60 times a second (--led-limit-refresh in
// panel.h); measured on this Pi it's ~55. Either way 30 px/s rounds to
// "1 pixel every 2 frames".
// ponytail: assumes 45-75 Hz; if the refresh rate ever leaves that range, measure it and scale.
constexpr double kRefreshHz = 60;

static volatile bool g_stop = false;
static void on_signal(int) { g_stop = true; }

// Command-line options (after the panel library has taken its --led-... flags).
struct Options {
  std::string display_path;  // default: display.txt next to the program
  double scroll_speed = 30;  // strip speed, pixels per second (0 = still)
  int stale_after = 300;     // seconds without fresh quotes before STALE (0 = never)
};

// Fills *opt; false (with a message) on an unknown option.
static bool ParseOptions(int argc, char **argv, Options *opt) {
  const std::string self = argv[0];
  const size_t slash = self.rfind('/');
  opt->display_path = (slash == std::string::npos ? "." : self.substr(0, slash)) + "/display.txt";
  for (int i = 1; i < argc; ++i) {
    const char *a = argv[i];
    if (!strncmp(a, "--display=", 10)) opt->display_path = a + 10;
    else if (!strncmp(a, "--scroll-speed=", 15)) opt->scroll_speed = atof(a + 15);
    else if (!strncmp(a, "--stale-after=", 14)) opt->stale_after = atoi(a + 14);
    else { fprintf(stderr, "Unknown option %s\n", a); return false; }
  }
  return true;
}

int main(int argc, char **argv) {
  // 1. Panel, options, fonts.
  const PanelConfig panel = LoadPanelConfig();
  rgb_matrix::RGBMatrix *matrix = CreatePanel(&argc, &argv, panel);
  if (matrix == nullptr) return 1;
  Options opt;
  if (!ParseOptions(argc, argv, &opt)) {
    delete matrix;
    return 1;
  }
  FontCache cache;
  Fonts f;
  if (!ResolveFonts(LoadFontChoice(), &cache, &f)) {
    fprintf(stderr, "No usable fonts (check %s)\n", FONTS_CONF);
    delete matrix;
    return 1;
  }

  // 2. The data to show.
  Display display;
  DisplayWatcher watcher(opt.display_path);
  watcher.Start(&display);
  int brightness = panel.brightness;

  signal(SIGINT, on_signal);
  signal(SIGTERM, on_signal);
  printf("Ticker running from %s. Ctrl-C to stop.\n", opt.display_path.c_str());
  fflush(stdout);

  // Drawing happens on an off-screen frame; SwapOnVSync shows it at the
  // panel's next refresh. OffsetCanvas applies the calibrated x/y shift.
  const int W = matrix->width(), H = matrix->height();
  const Layout layout = Layout::For(f, H);
  rgb_matrix::FrameCanvas *frame = matrix->CreateFrameCanvas();
  OffsetCanvas shifted(frame, panel.x_offset, panel.y_offset);
  Canvas *canvas = &shifted;
  const auto start = Clock::now();
  auto last_check = start;
  const int frames_per_px = opt.scroll_speed > 0 ? std::max(1, (int)std::lround(kRefreshHz / opt.scroll_speed)) : 0;
  Animation anim{StripScroller(W, frames_per_px), ShootingStar()};

  // 3. The frame loop.
  while (!g_stop) {
    const auto now = Clock::now();
    if (now - last_check >= std::chrono::seconds(1)) {
      last_check = now;
      watcher.Poll(&display);
      if (display.brightness > 0 && display.brightness != brightness) {
        brightness = display.brightness;
        matrix->SetBrightness(brightness);
      }
    }

    FrameInfo fr;
    fr.loaded = watcher.loaded();
    fr.load_error = watcher.error();
    fr.featured = FeaturedIndex(display.quotes, display.rotate > 0 ? display.rotate : 5);  // samples: no rotate line
    anim.strip.Step();
    fr.secs = std::chrono::duration<double>(now - start).count();
    fr.alt_phase = static_cast<long>(fr.secs / 3) % 2 == 0;  // alternate every 3 s
    fr.health = HealthText(display, fr.loaded, time(nullptr), opt.stale_after, fr.alt_phase);

    canvas->Clear();
    DrawScreen(canvas, f, layout, display, fr, &anim);

    // SwapOnVSync blocks until the panel's next refresh, which paces this loop.
    frame = matrix->SwapOnVSync(frame);
    shifted.set_target(frame);
    if (Clock::now() - now < std::chrono::milliseconds(4)) usleep(12000);  // no vsync pacing (limit-refresh off)
  }

  matrix->Clear();
  delete matrix;
  return 0;
}
