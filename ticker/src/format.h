// format.h - turning numbers into short text for a 128-pixel-wide panel.
//
//   FormatPrice(10512.3)   "10,512"       (whole dollars from 10,000 up)
//   FormatPrice(341.456)   "341.46"
//   FormatPrice(0.000912)  "0.0009120"    (4 significant digits below $1)
//   WithCommas(1234567.8, 2)  "1,234,567.80"
//   Compact(335.1)         "335"          (range labels)
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>

// printf-style formatting of one number: Format("%+.2f%%", 1.5) -> "+1.50%".
inline std::string Format(const char *fmt, double v) {
  char buf[32];
  snprintf(buf, sizeof(buf), fmt, v);
  return buf;
}

// 1234567.891 -> "1,234,567.89"; decimals = 0 drops the cents.
inline std::string WithCommas(double v, int decimals) {
  char buf[48];
  snprintf(buf, sizeof(buf), "%.*f", decimals, std::fabs(v));
  std::string s = buf;
  size_t dot = s.find('.');
  int end = dot == std::string::npos ? s.size() : dot;
  for (int i = end - 3; i > 0; i -= 3) s.insert(i, ",");  // a comma every 3 digits, from the right
  return (v < 0 ? "-" : "") + s;
}

// Prices: cents below 10,000, whole numbers above (10,512), and four
// significant digits below $1 (0.2134, 0.000009120).
inline std::string FormatPrice(double p) {
  const double a = std::fabs(p);
  if (a > 0 && a < 1) return WithCommas(p, std::min(12, 3 - (int)std::floor(std::log10(a))));
  return WithCommas(p, a >= 10000 ? 0 : 2);
}

// Short numbers for range labels: 10,512 / 343 / 98.12.
inline std::string Compact(double v) {
  if (std::fabs(v) >= 1000) return WithCommas(v, 0);
  if (std::fabs(v) >= 100) return Format("%.0f", v);
  return Format("%.2f", v);
}
