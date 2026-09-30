"""Logging: where log lines go, and keeping secrets out of them.

Every fetcher file logs through ONE shared logger named "fetcher" (`log`
below), so all lines look the same and land in the same two places:

  * the systemd journal       journalctl -u hub75-fetcher
  * logs/fetcher.log  rotated at 1 MB, 5 old files kept

    2026-09-28 10:00:01 INFO    mode pre -> market
    2026-09-28 10:04:12 WARNING quotes: HTTP 503 unavailable: ...

Two safety features:

  SecretFilter   replaces every known secret (client secret, refresh token,
                 access token, account number) with *** before a line is
                 written anywhere. Secrets register themselves via add().
  ErrorTracker   keeps a failing source from flooding the log: the first
                 error is logged, identical repeats are counted and summed
                 up every 10 minutes, and the recovery is logged once.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
import time
from typing import TYPE_CHECKING

from .util import duration

if TYPE_CHECKING:  # only for type hints; avoids a circular import
    from .config import Config

log = logging.getLogger("fetcher")


class SecretFilter(logging.Filter):
    """Replaces any known secret with *** in every log line (and tracebacks)."""

    secrets: set[str] = set()  # shared by every handler

    @classmethod
    def add(cls, *values: str) -> None:
        """Register secrets to hide. Very short values are ignored: hiding
        "a" or "12" would mangle ordinary words and numbers."""
        cls.secrets.update(v for v in values if v and len(v) >= 8)

    @classmethod
    def redact(cls, text: str) -> str:
        for s in cls.secrets:
            text = text.replace(s, "***")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        # Format the message first (so secrets passed as %s arguments are
        # caught too), then store the cleaned text as the whole message.
        record.msg = self.redact(record.getMessage())
        record.args = ()
        if record.exc_info and not record.exc_text:
            record.exc_text = self.redact(logging.Formatter().formatException(record.exc_info))
        return True  # never drop a line, only clean it


def setup_logging(cfg: Config, verbose: bool, to_file: bool = True) -> None:
    """Send log lines to stderr (the journal) and, unless to_file is False,
    to the rotating log file. verbose=True adds DEBUG lines."""
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if to_file:
        cfg.log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(
            cfg.log_file, maxBytes=1_000_000, backupCount=5, encoding="utf-8"))
    for h in handlers:
        h.setFormatter(fmt)
        h.addFilter(SecretFilter())  # on every handler: nothing gets out unfiltered
        root.addHandler(h)


class ErrorTracker:
    """Per-source error bookkeeping that keeps the log readable.

    With a source failing every few seconds for an hour, the log shows:
        WARNING quotes: HTTP 503 down                         (first time)
        WARNING quotes: still failing: HTTP 503 down (120 times since 10:04)
        INFO    quotes: recovered after 700 failure(s) over 1h00m (...)
    instead of hundreds of identical lines.
    """

    def __init__(self, source: str, repeat_every: float = 600):
        self.source = source              # name shown in the log ("quotes", "account", ...)
        self.repeat_every = repeat_every  # seconds between "still failing" summaries
        self.message: str | None = None  # the current error (None = working)
        self.count = 0                    # failures in a row with that message
        self.since = 0.0                  # when this error first appeared
        self.last_logged = 0.0

    @property
    def failing(self) -> bool:
        return self.message is not None

    def error(self, message: str, now: float, level: int = logging.WARNING) -> None:
        """Record a failure at time `now` (epoch seconds)."""
        if message != self.message:  # a new kind of error: always log it
            self.message, self.count, self.since, self.last_logged = message, 1, now, now
            log.log(level, "%s: %s", self.source, message)
            return
        self.count += 1
        if now - self.last_logged >= self.repeat_every:
            self.last_logged = now
            log.log(level, "%s: still failing: %s (%d times since %s)", self.source, message,
                    self.count, time.strftime("%H:%M", time.localtime(self.since)))

    def ok(self, now: float) -> None:
        """Record a success; logs the recovery if the source was failing."""
        if self.message is not None:
            log.info("%s: recovered after %d failure(s) over %s (last error: %s)", self.source,
                     self.count, duration(now - self.since), self.message)
        self.message, self.count = None, 0
