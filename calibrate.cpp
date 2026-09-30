// calibrate.cpp - interactive panel calibration. Run in a terminal (ssh -t).
//
// Keys:
//   arrows      shift image 1 px          W A S D   shift image 8 px
//   0           reset shift               p         next test pattern
//   m / M       next / previous panel mode (restarts the panel)
//   c           cycle width  128/64/256   r         cycle height 64/32/128
//   + / -       brightness                Enter     save to panel.conf
//   q           quit
//
// Mode and size changes need a fresh matrix, so the program re-executes itself
// with its current state passed in --state=...

#include "panel.h"
#include "term.h"

#include <algorithm>
#include <csignal>
#include <cstring>
#include <unistd.h>

using namespace rgb_matrix;

static volatile bool g_stop = false;
static void on_signal(int) { g_stop = true; }

static int TextWidth(const Font &font, const char *text) {
  int w = 0;
  for (const char *p = text; *p; ++p) w += font.CharacterWidth(*p);
  return w;
}

static const char *kPatterns[] = {"frame + HELLO", "grid (x/y every 16 px)", "quadrants",
                                  "white"};
constexpr int kPatternCount = 4;

static void Rect(Canvas *c, int x0, int y0, int x1, int y1, const Color &col) {
  DrawLine(c, x0, y0, x1, y0, col);
  DrawLine(c, x0, y1, x1, y1, col);
  DrawLine(c, x0, y0, x0, y1, col);
  DrawLine(c, x1, y0, x1, y1, col);
}

static void DrawPattern(Canvas *c, int pattern, const Font &small, const Font &tiny,
                        const Font &big) {
  const int W = c->width(), H = c->height();
  const Color white(255, 255, 255);
  c->Clear();
  switch (pattern) {
    case 0: {
      Rect(c, 0, 0, W - 1, H - 1, white);
      const int top = 2 + small.baseline();
      const int bottom = H - 3 - (small.height() - small.baseline());
      DrawText(c, small, 2, top, Color(255, 0, 0), "TL");
      DrawText(c, small, W - 2 - TextWidth(small, "TR"), top, Color(0, 255, 0), "TR");
      DrawText(c, small, 2, bottom, Color(0, 0, 255), "BL");
      DrawText(c, small, W - 2 - TextWidth(small, "BR"), bottom, Color(255, 255, 0), "BR");
      DrawText(c, big, (W - TextWidth(big, "HELLO")) / 2, (H - big.height()) / 2 + big.baseline(),
               white, "HELLO");
      break;
    }
    case 1: {
      const Color cols[] = {Color(255, 0, 0), Color(0, 255, 0), Color(0, 80, 255),
                            Color(255, 255, 0)};
      for (int y = 0; y < H; y += 16) DrawLine(c, 0, y, W - 1, y, Color(60, 60, 60));
      for (int x = 0, i = 0; x < W; x += 16, ++i) {
        DrawLine(c, x, 0, x, H - 1, cols[i % 4]);
        DrawText(c, tiny, x + 2, 1 + tiny.baseline(), cols[i % 4], std::to_string(x).c_str());
      }
      for (int y = 16; y < H; y += 16)
        DrawText(c, tiny, 2, y + 1 + tiny.baseline(), Color(160, 160, 160),
                 std::to_string(y).c_str());
      DrawLine(c, W - 1, 0, W - 1, H - 1, white);  // last column
      DrawLine(c, 0, H - 1, W - 1, H - 1, white);  // last row
      break;
    }
    case 2:
      for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x) {
          const bool right = x >= W / 2, lower = y >= H / 2;
          if (!right && !lower) c->SetPixel(x, y, 120, 0, 0);
          else if (right && !lower) c->SetPixel(x, y, 0, 120, 0);
          else if (!right && lower) c->SetPixel(x, y, 0, 0, 160);
          else c->SetPixel(x, y, 120, 120, 0);
        }
      break;
    default:
      for (int y = 0; y < H; ++y)
        for (int x = 0; x < W; ++x) c->SetPixel(x, y, 255, 255, 255);
  }
}

struct State {
  PanelConfig cfg;
  int pattern = 0;
};

static std::string Encode(const State &s) {
  char buf[128];
  snprintf(buf, sizeof(buf), "--state=%d,%d,%d,%d,%d,%d,%d", s.cfg.mode, s.cfg.cols, s.cfg.rows,
           s.cfg.x_offset, s.cfg.y_offset, s.cfg.brightness, s.pattern);
  return buf;
}

static bool Decode(const char *arg, State *s) {
  if (strncmp(arg, "--state=", 8) != 0) return false;
  PanelConfig &c = s->cfg;
  return sscanf(arg + 8, "%d,%d,%d,%d,%d,%d,%d", &c.mode, &c.cols, &c.rows, &c.x_offset,
                &c.y_offset, &c.brightness, &s->pattern) == 7;
}

static void PrintStatus(const State &s) {
  printf("\r\033[K[%d/%zu] %s | %dx%d | shift x=%d y=%d | bright %d%% | %s",
         s.cfg.mode + 1, PanelModes().size(), PanelModes()[s.cfg.mode].name, s.cfg.cols,
         s.cfg.rows, s.cfg.x_offset, s.cfg.y_offset, s.cfg.brightness, kPatterns[s.pattern]);
  fflush(stdout);
}

static int Next(const int *list, int n, int v) {
  for (int i = 0; i < n; ++i)
    if (list[i] == v) return list[(i + 1) % n];
  return list[0];
}

int main(int argc, char **argv) {
  State st;
  st.cfg = LoadPanelConfig();
  const bool restarted = argc > 1 && Decode(argv[1], &st);
  if (st.cfg.mode < 0 || st.cfg.mode >= (int)PanelModes().size()) st.cfg.mode = 0;

  int n = 1;  // don't pass our own args to the library
  char **v = argv;
  RGBMatrix *matrix = CreatePanel(&n, &v, st.cfg);
  if (matrix == nullptr) return 1;

  Font small, tiny, big;
  if (!LoadFont(&small, "5x8") || !LoadFont(&tiny, "tom-thumb") || !LoadFont(&big, "9x18B")) {
    delete matrix;
    return 1;
  }

  signal(SIGINT, on_signal);
  signal(SIGTERM, on_signal);
  RawTerminal term;

  if (!restarted) {
    printf("\nPanel calibration\n"
           "  arrows: shift 1px   WASD: shift 8px   0: reset shift   p: pattern\n"
           "  m/M: panel mode     c: width   r: height   +/-: brightness\n"
           "  Enter: save         q: quit\n\n");
  }

  FrameCanvas *frame = matrix->CreateFrameCanvas();
  bool dirty = true;
  bool restart = false;

  while (!g_stop && !restart) {
    if (dirty) {
      OffsetCanvas oc(frame, st.cfg.x_offset, st.cfg.y_offset);
      DrawPattern(&oc, st.pattern, small, tiny, big);
      frame = matrix->SwapOnVSync(frame);
      PrintStatus(st);
      dirty = false;
    }

    const int key = ReadKey(200);
    if (key == kKeyNone) continue;

    int &x = st.cfg.x_offset, &y = st.cfg.y_offset;
    static const int kCols[] = {128, 64, 256}, kRows[] = {64, 32, 128};
    const int modes = PanelModes().size();
    switch (key) {
      case kKeyUp: y -= 1; break;
      case kKeyDown: y += 1; break;
      case kKeyRight: x += 1; break;
      case kKeyLeft: x -= 1; break;
      case 'w': case 'W': y -= 8; break;
      case 's': case 'S': y += 8; break;
      case 'a': case 'A': x -= 8; break;
      case 'd': case 'D': x += 8; break;
      case '0': x = y = 0; break;
      case 'p': case 'P': st.pattern = (st.pattern + 1) % kPatternCount; break;
      case '+': case '=':
        st.cfg.brightness = std::min(100, st.cfg.brightness + 10);
        matrix->SetBrightness(st.cfg.brightness);
        break;
      case '-': case '_':
        st.cfg.brightness = std::max(10, st.cfg.brightness - 10);
        matrix->SetBrightness(st.cfg.brightness);
        break;
      case 'm': st.cfg.mode = (st.cfg.mode + 1) % modes; restart = true; break;
      case 'M': st.cfg.mode = (st.cfg.mode + modes - 1) % modes; restart = true; break;
      case 'c': case 'C': st.cfg.cols = Next(kCols, 3, st.cfg.cols); restart = true; break;
      case 'r': case 'R': st.cfg.rows = Next(kRows, 3, st.cfg.rows); restart = true; break;
      case '\n': case '\r':
        printf(SavePanelConfig(st.cfg) ? "\r\033[KSaved to %s\n" : "\r\033[KCould not write %s\n",
               PanelConfigPath().c_str());
        break;
      case 'q': case 'Q': g_stop = true; break;
    }
    // Keep the shift within one panel width/height.
    if (st.cfg.cols) x = ((x % st.cfg.cols) + st.cfg.cols) % st.cfg.cols;
    if (st.cfg.rows) y = ((y % st.cfg.rows) + st.cfg.rows) % st.cfg.rows;
    dirty = true;
  }

  matrix->Clear();
  delete matrix;
  term.Restore();

  if (restart) {
    printf("\r\033[KSwitching to: %s ...", PanelModes()[st.cfg.mode].name);
    fflush(stdout);
    std::string state = Encode(st);
    char *args[] = {argv[0], &state[0], nullptr};
    execv("/proc/self/exe", args);
    perror("execv");
    return 1;
  }
  printf("\n");
  return 0;
}
