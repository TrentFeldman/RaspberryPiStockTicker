// white_screen.cpp - fill the panel with one colour.
//
// Uses the saved calibration (panel.conf) via panel.h.
//
// Run: ./white_screen [r g b] [--led-... overrides]
// e.g. ./white_screen                  white
//      ./white_screen 255 0 0          red
//      ./white_screen --led-brightness=30

#include "panel.h"

#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <unistd.h>

using rgb_matrix::RGBMatrix;

static volatile bool g_stop = false;
static void on_signal(int) { g_stop = true; }

int main(int argc, char **argv) {
  int n = argc;
  char **v = argv;
  RGBMatrix *matrix = CreatePanel(&n, &v);
  if (matrix == nullptr) return 1;

  // Whatever the library didn't consume is our optional "r g b".
  int r = 255, g = 255, b = 255;
  if (n >= 4) { r = atoi(v[1]); g = atoi(v[2]); b = atoi(v[3]); }

  signal(SIGINT, on_signal);
  signal(SIGTERM, on_signal);

  matrix->Fill(r, g, b);
  printf("Showing %d,%d,%d. Ctrl-C to stop.\n", r, g, b);
  while (!g_stop) sleep(1);

  matrix->Clear();
  delete matrix;
  return 0;
}
