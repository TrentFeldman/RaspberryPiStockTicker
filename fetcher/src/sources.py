"""When each data source is due again, and backing off after errors.

The fetcher has several independent data sources ("sessions", "quotes",
"rack", "account", "instruments", "weather"). Each one gets a
Source that remembers when it may run next, so one failing source never
blocks or speeds up the others.

After a success: next run = now + its normal interval (config.toml [intervals]).
After a failure:
  * worth retrying soon (no network, 429, 5xx): exponential backoff with a
    little randomness, 5 s, 10 s, 20 s ... up to 5 minutes
  * won't fix itself (400, 404, ...): wait the normal interval, at least 60 s
"""

from __future__ import annotations

import logging
import random

from .logs import ErrorTracker
from .web import ApiError


class Source:
    """Schedule and error state of one data source."""

    BACKOFF_BASE, BACKOFF_CAP = 5.0, 300.0  # seconds: first retry delay, longest delay

    def __init__(self, name: str):
        self.name = name
        self.errors = ErrorTracker(name)
        self.next_due = 0.0    # epoch when it may run again (0 = right away)
        self.failures = 0      # failures in a row
        self.last_ok = 0.0     # epoch of the last success (0 = never)
        self.panel_error = ""  # short text for the LED panel while failing

    def due(self, now: float) -> bool:
        return now >= self.next_due

    def succeeded(self, now: float, interval: float) -> None:
        self.errors.ok(now)
        self.failures, self.last_ok = 0, now
        self.next_due = now + interval

    def failed(self, now: float, err: Exception, interval: float) -> None:
        self.failures += 1
        if isinstance(err, ApiError) and not err.retryable:
            delay = max(interval, 60.0)  # won't fix itself quickly; don't hammer
            level = logging.ERROR
        else:
            delay = min(self.BACKOFF_CAP, self.BACKOFF_BASE * 2 ** (self.failures - 1))
            delay *= random.uniform(0.8, 1.2)  # spread retries out a little
            level = logging.WARNING
        self.next_due = now + delay
        msg = err.short() if isinstance(err, ApiError) else f"{type(err).__name__}: {err}"
        self.panel_error = err.panel() if isinstance(err, ApiError) else type(err).__name__[:20]
        self.errors.error(msg, now, level)
