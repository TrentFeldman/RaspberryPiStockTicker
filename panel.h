// panel.h - shared setup for the 128x64 FM6565/TC7559 panel.
//
// Probing showed the FM6565 answers to the matrix-pwm-test fork's FM6373
// profile with shift-register row select (TC7559). All programs create the
// matrix through here so the known-good flags live in one place.
//
// Calibration (mode, size, x/y shift) is stored in panel.conf, written
// by the interactive `calibrate` tool. Programs draw through OffsetCanvas so a
// saved shift applies everywhere.
#pragma once

#include "canvas.h"
#include "graphics.h"
#include "led-matrix.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <vector>

#ifndef FONT_DIR
#define FONT_DIR "../matrix-pwm-test/fonts/"
#endif
// Register profile catalogs used by --led-spwm-register-config=N.
#ifndef SPWM_PROFILES
#define SPWM_PROFILES "../matrix-pwm-test/lib/spwm/registertest/data"
#endif

// Panel modes that lit up during probing, plus the other data layouts of the
// 64-scan variant. Each is a set of flags added on top of the base flags.
struct PanelMode {
  const char *name;
  std::vector<const char *> flags;
};

inline const std::vector<PanelMode> &PanelModes() {
  static const std::vector<PanelMode> modes = {
      {"fm6373 shiftreg (probe 1)", {"--led-panel-type=fm6373", "--led-spwm-row-addr-type=1"}},
      {"fm6373 scan64 layout1 (probe 2)",
       {"--led-panel-type=fm6373", "--led-spwm-row-addr-type=1", "--led-spwm-scan=64",
        "--led-spwm-data-layout=1", "--led-spwm-register-config=2"}},
      {"fm6373 scan64 layout2",
       {"--led-panel-type=fm6373", "--led-spwm-row-addr-type=1", "--led-spwm-scan=64",
        "--led-spwm-data-layout=2", "--led-spwm-register-config=2"}},
      {"fm6373 scan64 layout3",
       {"--led-panel-type=fm6373", "--led-spwm-row-addr-type=1", "--led-spwm-scan=64",
        "--led-spwm-data-layout=3", "--led-spwm-register-config=2"}},
      {"fm6373 scan64 layout4",
       {"--led-panel-type=fm6373", "--led-spwm-row-addr-type=1", "--led-spwm-scan=64",
        "--led-spwm-data-layout=4", "--led-spwm-register-config=2"}},
      {"fm6373 scan64 layout5",
       {"--led-panel-type=fm6373", "--led-spwm-row-addr-type=1", "--led-spwm-scan=64",
        "--led-spwm-data-layout=5", "--led-spwm-register-config=2"}},
      {"icnd1065l scan32 (probe 8)",
       {"--led-panel-type=icnd1065l", "--led-spwm-row-addr-type=2", "--led-spwm-scan=32",
        "--led-spwm-register-config=2"}},
  };
  return modes;
}

struct PanelConfig {
  int mode = 0;
  int cols = 128;
  int rows = 64;
  int x_offset = 0;
  int y_offset = 0;
  int brightness = 30;
};

// Fixed path (set by the Makefile) so it's the same file under sudo, where
// HOME would be /root.
#ifndef PANEL_CONF
#define PANEL_CONF "panel.conf"
#endif
inline std::string PanelConfigPath() { return PANEL_CONF; }

inline PanelConfig LoadPanelConfig() {
  PanelConfig c;
  std::ifstream in(PanelConfigPath());
  std::string key;
  int value;
  while (in >> key >> value) {
    if (key == "mode") c.mode = value;
    else if (key == "cols") c.cols = value;
    else if (key == "rows") c.rows = value;
    else if (key == "x_offset") c.x_offset = value;
    else if (key == "y_offset") c.y_offset = value;
    else if (key == "brightness") c.brightness = value;
  }
  if (c.mode < 0 || c.mode >= (int)PanelModes().size()) c.mode = 0;
  return c;
}

inline bool SavePanelConfig(const PanelConfig &c) {
  std::ofstream out(PanelConfigPath());
  out << "mode " << c.mode << "\ncols " << c.cols << "\nrows " << c.rows
      << "\nx_offset " << c.x_offset << "\ny_offset " << c.y_offset
      << "\nbrightness " << c.brightness << "\n";
  return bool(out);
}

// Base flags + the config's mode/size/brightness + any --led-* flags from the
// command line (last one wins). Leftover arguments are returned in argc/argv.
inline rgb_matrix::RGBMatrix *CreatePanel(int *argc, char ***argv, const PanelConfig &c) {
  static std::vector<std::string> owned;
  static std::vector<char *> args;
  owned = {
      "--led-gpio-mapping=regular",
      "--led-slowdown-gpio=5",
      "--led-no-hardware-pulse",
      // Under sudo the library would otherwise switch to user "daemon", which
      // can't read fonts or write panel.conf in the (private) home directory.
      "--led-no-drop-privs",
      "--led-limit-refresh=60",
      "--led-cols=" + std::to_string(c.cols),
      "--led-rows=" + std::to_string(c.rows),
      "--led-brightness=" + std::to_string(c.brightness),
  };
  for (const char *f : PanelModes()[c.mode].flags) owned.push_back(f);

  args = {(*argv)[0]};
  for (std::string &s : owned) args.push_back(&s[0]);
  for (int i = 1; i < *argc; ++i) args.push_back((*argv)[i]);
  *argc = args.size();
  *argv = args.data();
  setenv("SPWM_PROFILE_DIR", SPWM_PROFILES, 0);  // don't override a user setting
  return rgb_matrix::RGBMatrix::CreateFromFlags(argc, argv);
}

inline rgb_matrix::RGBMatrix *CreatePanel(int *argc, char ***argv) {
  return CreatePanel(argc, argv, LoadPanelConfig());
}

inline bool LoadFont(rgb_matrix::Font *font, const char *name) {
  std::string path = std::string(FONT_DIR) + name + ".bdf";
  if (!font->LoadFont(path.c_str())) {
    fprintf(stderr, "Couldn't load font %s\n", path.c_str());
    return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Ticker fonts: which BDF file each text role uses, from fonts.conf.
// To change one, edit it and restart the ticker. One line per role; relative
// paths are relative to fonts.conf itself:
//
//   big fonts/Jersey10-Regular-19.bdf
//   mid ../matrix-pwm-test/fonts/7x13.bdf
//   small fonts/Tamzen6x12r.bdf
//   strip fonts/Tamzen7x14b.bdf
//
// fonts/ has the three custom fonts in use; the library's classic X11 fonts
// are in matrix-pwm-test/fonts/. A missing role, or a font that won't load,
// falls back to the default below.

#ifndef FONTS_CONF
#define FONTS_CONF "fonts.conf"
#endif

struct FontChoice {
  std::string big = std::string(FONT_DIR) + "9x18B.bdf";   // symbol, price, account value
  std::string mid = std::string(FONT_DIR) + "7x13B.bdf";   // change lines
  std::string small = std::string(FONT_DIR) + "5x8.bdf";   // labels, clock, health
  std::string strip = std::string(FONT_DIR) + "7x13.bdf";  // scrolling strip

  std::string *Role(int i) { return i == 0 ? &big : i == 1 ? &mid : i == 2 ? &small : &strip; }
};

inline const char *const kFontRoles[] = {"big", "mid", "small", "strip"};

inline FontChoice LoadFontChoice() {
  FontChoice c;
  const std::string conf = FONTS_CONF;
  const std::string dir = conf.substr(0, conf.find_last_of('/') + 1);  // "" if no '/'
  std::ifstream in(conf);
  std::string role, path;
  while (in >> role >> path) {
    if (path[0] != '/') path = dir + path;  // relative paths are relative to fonts.conf
    for (int i = 0; i < 4; ++i)
      if (role == kFontRoles[i]) *c.Role(i) = path;
  }
  return c;
}

// Draws onto another canvas with the whole image shifted by (dx, dy),
// wrapping around the edges.
class OffsetCanvas : public rgb_matrix::Canvas {
 public:
  OffsetCanvas(rgb_matrix::Canvas *target, int dx, int dy) : t_(target), dx_(dx), dy_(dy) {}
  void set_target(rgb_matrix::Canvas *target) { t_ = target; }

  int width() const override { return t_->width(); }
  int height() const override { return t_->height(); }
  void SetPixel(int x, int y, uint8_t r, uint8_t g, uint8_t b) override {
    if (x < 0 || y < 0 || x >= width() || y >= height()) return;
    const int w = width(), h = height();
    t_->SetPixel(((x + dx_) % w + w) % w, ((y + dy_) % h + h) % h, r, g, b);
  }
  void Clear() override { t_->Clear(); }
  void Fill(uint8_t r, uint8_t g, uint8_t b) override { t_->Fill(r, g, b); }

 private:
  rgb_matrix::Canvas *t_;
  int dx_, dy_;
};
