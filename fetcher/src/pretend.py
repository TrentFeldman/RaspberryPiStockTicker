"""Test mode: pretend it's another time, so any screen can be checked any time.

    ./pretend.sh 'mon 10:00'    pretend it's Monday 10:00 (for 30 min)
    ./pretend.sh off            back to real time

pretend.sh writes pretend.json:
    {"target": "2026-09-28T10:00:00-04:00", "set_at": 1790500000, "expires_min": 30}

While it's on, the SCHEDULE (mode, brightness, countdown, clock) follows the
pretend time, and the pretend time keeps flowing: 5 minutes after setting
"mon 10:00" it's "mon 10:05". Prices and the account are always real.

Safety: the pretend time switches itself off after expires_min (capped by
config.toml [pretend] max_minutes), so the wall display can never get stuck
on a fake time. A missing, invalid or expired file means real time.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .logs import log
from .sessions import parse_time
from .util import duration


class PretendClock:
    """Reads pretend.json (only when it changes) and answers "what time is it?"."""

    def __init__(self, path: Path, max_minutes: float):
        self.path, self.max_minutes = path, max_minutes
        self._mtime: float | None = None    # file's modification time when last read
        self._target: datetime | None = None  # the pretend time at set_at (None = off)
        self._set_at = 0.0                  # real epoch when pretend.sh ran
        self._expires = 0.0                 # seconds after set_at when it switches off
        self._expired_logged = False

    def _load(self) -> None:
        """Re-read the file if it changed (cheap: just a stat() otherwise)."""
        try:
            mtime = self.path.stat().st_mtime
        except OSError:  # no file: real time
            if self._target is not None:
                log.info("test mode off (pretend file removed)")
            self._mtime, self._target = None, None
            return
        if mtime == self._mtime:
            return
        self._mtime, self._target, self._expired_logged = mtime, None, False
        try:
            data = json.loads(self.path.read_text())
            target = parse_time(data["target"])
            if target.tzinfo is None:
                raise ValueError("target has no timezone")
            self._target, self._set_at = target, float(data["set_at"])
            self._expires = min(float(data.get("expires_min", self.max_minutes)), self.max_minutes) * 60
            log.info("TEST MODE: pretending it is %s (for %s)", target.isoformat(timespec="minutes"),
                     duration(self._expires))
        except (OSError, ValueError, KeyError, TypeError) as e:
            log.warning("ignoring invalid pretend file %s: %s", self.path, e)

    def now(self, real: datetime) -> tuple[datetime, bool]:
        """(effective time, pretending?). The effective time is the real time
        unless test mode is on."""
        self._load()
        if self._target is None:
            return real, False
        elapsed = real.timestamp() - self._set_at
        if elapsed > self._expires or elapsed < -60:  # expired, or set_at is in the future (clock jump)
            if not self._expired_logged:
                log.info("test mode expired; back to real time")
                self._expired_logged = True
            return real, False
        return self._target + timedelta(seconds=max(0.0, elapsed)), True
