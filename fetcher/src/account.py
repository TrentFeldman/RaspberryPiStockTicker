"""The account screen's numbers: current value and its day change.

  value       net liquidating value from /accounts/{acct}/balances
              (refreshed every 2 min, every 10 min on quiet nights/weekends)
  day change  value minus the value at the regular close BEFORE the latest
              trading session, so after 4 pm and all weekend it reads as
              "how the latest trading day went"

The reference value (the "before" number) comes from the net-liq history.
It's looked up once per trading session and remembered; if the lookup
fails, the panel shows the value without a change and it's retried in
10 minutes.

The account number and balance are never written to the log.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from .config import Config
from .logs import log
from .sessions import SessionInfo, parse_time
from .tastytrade import TastyClient
from .util import num
from .web import ApiError, AuthError


class AccountData:
    """Latest account value and day change."""

    def __init__(self, cfg: Config, client: TastyClient):
        self.cfg, self.client = cfg, client
        # (value, change $, change %); the change parts are None when unknown.
        self.value: tuple[float, float | None, float | None] | None = None
        self.ref_cache: dict[datetime, float] = {}  # last-opened session's open -> reference net-liq
        self.ref_retry_after = 0.0                  # epoch before which a failed lookup isn't retried

    def refresh(self, now: datetime, sessions: SessionInfo | None) -> None:
        """Fetch the current value and work out the day change.

        `now` is the REAL time (not test mode) and `sessions` the real market
        calendar: the change is always measured against real trading days.
        """
        acct = self.client.account()
        bal = self.client.get(f"/accounts/{acct}/balances")["data"]
        value = num(bal.get("net-liquidating-value"))
        if value is None:
            raise ApiError(200, "bad_balance", "balance response had no net-liquidating-value")
        ref = self.reference_value(now, sessions)
        if ref:
            self.value = (value, value - ref, (value - ref) / ref * 100)
        else:
            self.value = (value, None, None)

    def reference_value(self, now: datetime, sessions: SessionInfo | None) -> float | None:
        """Net-liq at the regular close before the latest trading session.

        Cached per session; None if it can't be determined (retried in 10 min).
        An AuthError is passed on (the app must pause logins); other errors
        just mean "no day change for now".
        """
        last = sessions.last_opened(now) if sessions else None
        if last is None:
            return None
        if last.open in self.ref_cache:
            return self.ref_cache[last.open]
        if time.time() < self.ref_retry_after:
            return None
        self.ref_retry_after = time.time() + 600  # on failure, retry in 10 min
        try:
            # Ask the calendar what the session BEFORE `last` was: evaluate
            # "current session" one minute after `last` opened.
            probe = (last.open + timedelta(minutes=1)).astimezone(timezone.utc)
            data = self.client.get("/market-time/equities/sessions/current",
                                   [("current-time", probe.strftime("%Y-%m-%dT%H:%M:%SZ"))])["data"]
            prev = data.get("previous-session") or {}
            ref_time = parse_time(prev["close-at"])
            ref = None
            for back in ("1w", "1m"):  # a week of history is usually enough; a month covers long holidays
                points = self.client.get(f"/accounts/{self.client.account()}/net-liq/history",
                                         [("time-back", back)])["data"]
                points = points.get("items", []) if isinstance(points, dict) else points
                before = [p for p in points if p.get("time") and parse_time(p["time"]) <= ref_time]
                if before:
                    ref = num(max(before, key=lambda p: parse_time(p["time"])).get("close"))
                    break
            if ref:
                self.ref_cache = {last.open: ref}  # only the latest session is ever needed
                log.info("account day-change reference: net-liq at %s close",
                         ref_time.astimezone(self.cfg.tz).strftime("%a %m-%d %H:%M"))
            else:
                log.warning("no net-liq history before %s; day change unavailable", ref_time)
            return ref
        except AuthError:
            raise
        except (ApiError, KeyError, ValueError) as e:
            log.warning("account day-change reference unavailable (retry in 10m): %s", e)
            return None
