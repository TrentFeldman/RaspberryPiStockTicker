// rotation.h - whose turn is it on the full screen?
//
// Market hours show one stock at a time, a new one every `rotate` seconds.
// Turns follow the wall clock:
//
//   turn = floor(epoch seconds / rotate)       e.g. rotate 6: a new turn at :00, :06, :12 ...
//
// The fetcher uses the same formula (fetcher/src/picking.py next_turn): about
// 2 s before each turn it picks a stock and writes it with turn=N. Neither
// program has to tell the other when a turn starts; both read the clock.
#pragma once

#include <algorithm>
#include <chrono>
#include <cmath>
#include <vector>

#include "display_file.h"

// The turn number right now.
inline long long TurnNow(double rotate_sec) {
  const double now = std::chrono::duration<double>(std::chrono::system_clock::now().time_since_epoch()).count();
  return static_cast<long long>(std::floor(now / std::max(1.0, rotate_sec)));
}

// Which quote to feature. Market hours: the latest one whose turn has come
// (if a fetch failed, the previous stock simply stays up longer; if none has
// come yet, the earliest). Untagged lists (sample files) step through
// in order, one per turn.
inline size_t FeaturedIndex(const std::vector<Quote> &quotes, double rotate_sec) {
  if (quotes.empty()) return 0;
  const long long turn = TurnNow(rotate_sec);
  long long best_turn = -1;
  size_t best = 0, earliest = 0;
  bool tagged = false;
  for (size_t i = 0; i < quotes.size(); ++i) {
    if (quotes[i].turn < 0) continue;
    if (!tagged || quotes[i].turn < quotes[earliest].turn) earliest = i;
    tagged = true;
    if (quotes[i].turn <= turn && quotes[i].turn > best_turn) best_turn = quotes[i].turn, best = i;
  }
  if (!tagged) return static_cast<size_t>(turn % (long long)quotes.size());
  return best_turn >= 0 ? best : earliest;
}
