// term.h - raw keyboard input for the interactive calibrate tool.
#pragma once

#include <poll.h>
#include <termios.h>
#include <unistd.h>

// Puts stdin into unbuffered, no-echo mode; restores it on destruction.
// Ctrl-C still sends SIGINT.
class RawTerminal {
 public:
  RawTerminal() {
    if (tcgetattr(STDIN_FILENO, &saved_) != 0) return;  // not a terminal (e.g. piped)
    struct termios t = saved_;
    t.c_lflag &= ~(ICANON | ECHO);
    t.c_cc[VMIN] = 0;
    t.c_cc[VTIME] = 0;
    active_ = tcsetattr(STDIN_FILENO, TCSANOW, &t) == 0;
  }
  ~RawTerminal() { Restore(); }
  void Restore() {
    if (active_) tcsetattr(STDIN_FILENO, TCSANOW, &saved_);
    active_ = false;
  }

 private:
  struct termios saved_ {};
  bool active_ = false;
};

enum Key { kKeyNone = 0, kKeyUp = 1000, kKeyDown, kKeyLeft, kKeyRight };

// Returns the next key (a character, or kKeyUp/kKeyDown/kKeyLeft/kKeyRight for arrows),
// or kKeyNone if nothing arrives within timeout_ms.
inline int ReadKey(int timeout_ms) {
  struct pollfd pfd = {STDIN_FILENO, POLLIN, 0};
  if (poll(&pfd, 1, timeout_ms) <= 0) return kKeyNone;
  char buf[8];
  const int len = read(STDIN_FILENO, buf, sizeof(buf));
  if (len <= 0) return kKeyNone;
  if (len >= 3 && buf[0] == 27 && buf[1] == '[') {
    switch (buf[2]) {
      case 'A': return kKeyUp;
      case 'B': return kKeyDown;
      case 'C': return kKeyRight;
      case 'D': return kKeyLeft;
    }
    return kKeyNone;
  }
  return static_cast<unsigned char>(buf[0]);
}
