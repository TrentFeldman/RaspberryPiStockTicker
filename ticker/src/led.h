// led.h - the LED library's drawing tools, under short names.
//
// The panel library (the S-PWM fork of rpi-rgb-led-matrix, ../matrix-pwm-test) gives us:
//
//   Canvas    something to draw on. SetPixel(x, y, r, g, b), width(), height(),
//             Clear(). The ticker draws each frame on an off-screen canvas,
//             then shows it all at once (see main.cpp).
//   Color     an (r, g, b) colour, each 0-255. The palette is in colors.h.
//   Font      a BDF bitmap font: height(), baseline() (pixels from the top of
//             a line to the bottom of letters like "A"), CharacterWidth(c).
//   DrawText(canvas, font, x, baseline_y, color, text) -> width in pixels
//   DrawLine(canvas, x0, y0, x1, y1, color)
//
// Coordinates: (0, 0) is the top-left LED; x grows to the right (0-127),
// y grows downwards (0-63). Pixels outside the panel are simply ignored.
#pragma once

#include "canvas.h"
#include "graphics.h"

using rgb_matrix::Canvas;
using rgb_matrix::Color;
using rgb_matrix::DrawLine;
using rgb_matrix::DrawText;
using rgb_matrix::Font;
