// display_file.h - reading display.txt, the fetcher's instructions for the panel.
//
// The fetcher (fetcher/src/display_file.py) writes the file; this is the
// reading side. It's plain text, one setting per line; lines starting with #
// are comments. Example (market hours):
//
//   updated 1790455209           epoch of the last successful quote refresh (drives STALE)
//   mode market                  market | after | pre | weekend | overnight | sleep
//   brightness 70                1-100, applied live
//   status ok                    or: status error <short message>
//   moon 0.43                    moon phase 0 new .. 0.5 full .. 1 (sleep screen)
//   test Mon 10:00               only while test mode is on
//   rotate 6                     seconds per stock turn
//   event close 1790625600       countdown target: today's close, or the next open
//   offset 172800                test mode: pretend minus real seconds (the clock follows it)
//   account 12345.67 98.76 0.80 value, change $, change % ("na" if unknown)
//   quote NVDA 118.02 6.21 chg=6.90 lo=111.80 hi=118.30 big=1 turn=298409335
//         name price  change%  then optional key=value stats:
//           chg prev open lo hi ylo yhi halted
//           big=1   a big mover (gold frame)      turn=N  shown during turn N
//   weather {label}Today {hot}93{label}/{mild}68F
//                                one line per weather item for the strip (off hours);
//                                {name} switches colour (names: colors.h WeatherColor)
//
// Unknown lines and keys are ignored, so the fetcher can add things without
// breaking an older ticker. DisplayWatcher re-reads the file whenever it
// changes.
#pragma once

#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <sys/stat.h>
#include <vector>

// One `quote` line.
struct Quote {
  std::string sym;    // "AAPL", "BRK.B"
  double price;
  double change_pct;  // today's change in %
  // Optional stats for the full-screen view (see the list above).
  std::map<std::string, double> stats;
  long long turn = -1;  // market hours: the turn this stock was picked for (-1 = none)
  bool text_only = false;  // strip only: not a price, just `sym` as (colour-tagged) text: the weather

  bool Has(const char *k) const { return stats.count(k) > 0; }
  // The stat's value, or 0 if it's missing.
  double Get(const char *k) const { auto it = stats.find(k); return it == stats.end() ? 0 : it->second; }
};

// Everything parsed from display.txt.
struct Display {
  long updated = 0;
  std::string mode = "market";
  int brightness = 0;  // 0 = not specified
  std::string status = "ok";
  bool has_account = false;
  double account = 0;
  bool account_change_known = false;
  double account_change = 0, account_pct = 0;
  std::vector<Quote> quotes;
  double moon = 0;         // moon phase 0..1 (sleep screen)
  std::string test_label;  // non-empty while the fetcher's test mode is on
  double rotate = 0;       // seconds per stock turn (0 = none given: 5)
  std::string event_kind;  // "open" or "close": the countdown's target...
  long long event_at = 0;  // ...and its epoch (0 = unknown)
  long long offset = 0;    // test mode: pretend minus real seconds (the clock follows it)
  std::vector<std::string> weather;  // strip text items ("{mild}68F {sun}Sunny", ...), after the quotes
};

// Modes that show the account value on top and the scrolling strip below.
inline bool IsAccountMode(const std::string &mode) {
  return mode == "after" || mode == "pre" || mode == "weekend" || mode == "overnight";
}

// "12.5" -> 12.5. False for "na", junk, or infinity/NaN.
inline bool ParseNumber(const std::string &s, double *out) {
  if (s == "na") return false;
  char *end = nullptr;
  *out = strtod(s.c_str(), &end);
  return end && *end == '\0' && std::isfinite(*out);
}

// Reads the whole file into *out. Returns false (with a reason in *error) only
// if the file can't be read at all; a malformed line is skipped, so a
// partially odd file still shows something.
inline bool LoadDisplay(const std::string &path, Display *out, std::string *error) {
  std::ifstream in(path);
  if (!in) {
    *error = std::string("can't read ") + path + ": " + strerror(errno);
    return false;
  }
  Display d;
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') continue;
    std::istringstream ss(line);
    std::string key;
    ss >> key;
    if (key == "updated") {
      ss >> d.updated;
    } else if (key == "mode") {
      ss >> d.mode;
    } else if (key == "brightness") {
      ss >> d.brightness;
    } else if (key == "status") {
      std::string kind;
      ss >> kind;
      if (kind == "ok") {
        d.status = "ok";
      } else {  // "status error <message>": keep the message
        std::getline(ss, d.status);
        d.status.erase(0, d.status.find_first_not_of(' '));
        if (d.status.empty()) d.status = "error";
      }
    } else if (key == "account") {
      std::string v, c, p;
      ss >> v >> c >> p;
      if (ParseNumber(v, &d.account)) {
        d.has_account = true;
        d.account_change_known = ParseNumber(c, &d.account_change) && ParseNumber(p, &d.account_pct);
      }
    } else if (key == "quote") {
      Quote q;
      std::string price, pct, extra;
      ss >> q.sym >> price >> pct;
      if (q.sym.empty() || !ParseNumber(price, &q.price) || !ParseNumber(pct, &q.change_pct)) continue;
      while (ss >> extra) {  // key=value stats; unknown keys are kept but unused
        const size_t eq = extra.find('=');
        double v;
        if (eq == std::string::npos) continue;
        if (extra.compare(0, eq, "turn") == 0) q.turn = strtoll(extra.c_str() + eq + 1, nullptr, 10);
        else if (ParseNumber(extra.substr(eq + 1), &v)) q.stats[extra.substr(0, eq)] = v;
      }
      d.quotes.push_back(q);
    } else if (key == "weather") {
      std::string w;
      std::getline(ss, w);
      w.erase(0, w.find_first_not_of(' '));
      if (!w.empty()) d.weather.push_back(w);
    } else if (key == "moon") {
      ss >> d.moon;
    } else if (key == "rotate") {
      ss >> d.rotate;
    } else if (key == "event") {
      ss >> d.event_kind >> d.event_at;
    } else if (key == "offset") {
      ss >> d.offset;
    } else if (key == "test") {
      std::getline(ss, d.test_label);
      d.test_label.erase(0, d.test_label.find_first_not_of(' '));
    }
  }
  *out = d;
  return true;
}

// The file's modification time in nanoseconds (0 if it doesn't exist).
// Nanoseconds, not seconds: the fetcher can rewrite the file twice within one
// second (a just-fetched quote right after another update), and both must
// be noticed.
inline long long FileMtime(const std::string &path) {
  struct stat st;
  if (stat(path.c_str(), &st) != 0) return 0;
  return st.st_mtim.tv_sec * 1000000000LL + st.st_mtim.tv_nsec;
}

// Keeps a Display up to date with the file: re-reads it when it changes.
// If the file becomes unreadable, loaded() turns false (the panel shows
// NO DATA with the reason) until it can be read again.
class DisplayWatcher {
 public:
  explicit DisplayWatcher(const std::string &path) : path_(path) {}

  // The first read, at start-up. Failing isn't fatal: we keep checking.
  void Start(Display *d) {
    mtime_ = FileMtime(path_);
    loaded_ = LoadDisplay(path_, d, &error_);
    if (!loaded_) fprintf(stderr, "%s; will keep checking.\n", error_.c_str());
  }

  // Re-read the file if it changed since the last good read (or has been
  // unreadable). On a failed read *d keeps its previous content.
  void Poll(Display *d) {
    const long long m = FileMtime(path_);
    if (m == mtime_ && loaded_) return;
    Display fresh;
    if (LoadDisplay(path_, &fresh, &error_)) {
      if (!loaded_) fprintf(stderr, "display file readable again\n");
      *d = fresh;
      loaded_ = true;
      mtime_ = m;
    } else if (loaded_) {  // report it once, not every second
      fprintf(stderr, "%s\n", error_.c_str());
      loaded_ = false;
    }
  }

  bool loaded() const { return loaded_; }
  const std::string &error() const { return error_; }  // why it couldn't be read

 private:
  std::string path_;
  long long mtime_ = 0;  // FileMtime at the last good read
  bool loaded_ = false;
  std::string error_;
};
