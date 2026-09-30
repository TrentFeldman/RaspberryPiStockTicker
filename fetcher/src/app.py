"""The fetcher's main loop: Fetcher.tick(), run about twice a second.

Each tick does the same five steps, in order:

  1. read the clock      real time, and the pretend time in test mode
  2. market calendar     refresh the tastytrade sessions (every 10 min)
  3. schedule            work out the mode, brightness, moon, countdown
  4. fetch what's due    weather, the daily symbol check, then either the next
                         stock (market hours) or the strip + account (off hours)
  5. publish             write display.txt if anything changed; heartbeat log

Most ticks do almost nothing: every data source has its own timer (see
sources.py) and only runs when due. What each source fetches:

    source       what                                   how often (config.toml)
    -----------  -------------------------------------  -----------------------
    sessions     market open/close times                 [intervals] sessions
    instruments  which symbols exist / trade 24/5        once a day
    rack         market hours: the next stock's quote    once per 6 s turn
    quotes       off hours: the strip's random picks     quotes_day / quotes_night
    account      account value (off hours only)          account / account_quiet
    weather      strip weather (wttr.in, not tastytrade) weather (30 min), strip modes only

Rules that keep it safe to run for weeks unattended:
  * one source failing never stops the others (each runs inside _run())
  * a login failure pauses ALL tastytrade calls for 30 min, because
    repeated failed logins get the IP blocked for ~8 hours
  * last good data stays on screen; the panel shows STALE when it's old
  * nothing is fetched while the panel sleeps, except the market calendar
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from . import VERSION
from .account import AccountData
from .config import Config
from .credentials import Credentials
from .display_file import DisplayState, render_display, write_atomic
from .logs import log
from .pretend import PretendClock
from .rotation import Rotation
from .schedule import ACCOUNT_MODES, QUIET_MODES, brightness_for, compute_mode, moon_phase
from .sessions import SessionInfo, market_event, overnight_active
from .sources import Source
from .stocks import StockData
from .tastytrade import TastyClient
from .util import duration
from .weather import WeatherData
from .web import ApiError, AuthError

SOURCE_NAMES = ("sessions", "quotes", "rack", "account", "instruments", "weather")

# The panel shows one problem at a time: the first failing source in this
# order (after AUTH, which always wins), with its label.
STATUS_LABELS = (("quotes", "QUOTES"), ("rack", "QUOTES"), ("sessions", "SESSIONS"),
                 ("account", "ACCOUNT"))


class Fetcher:
    """Owns every data source and writes display.txt."""

    def __init__(self, cfg: Config, creds: Credentials):
        self.cfg = cfg
        self.client = TastyClient(cfg, creds)
        self.stocks = StockData(cfg, self.client)
        self.weather = WeatherData(cfg)
        self.account = AccountData(cfg, self.client)
        self.rotation = Rotation(cfg, self.stocks)
        self.sources = {n: Source(n) for n in SOURCE_NAMES}
        self.state = DisplayState(brightness=cfg.brightness_day)

        # Market calendar (from tastytrade).
        self.session_info: SessionInfo | None = None  # real time (account day-change reference)
        self.session_eff: SessionInfo | None = None   # at the pretend time, while test mode is on

        # Test mode.
        self.pretend = PretendClock(cfg.pretend, cfg.pretend_max_minutes)
        self.pretending = False
        self.eff_now: datetime | None = None  # the schedule's time (pretend time in test mode)

        # Login-failure pause (see _run).
        self.auth_blocked_until = 0.0
        self.auth_error: str | None = None    # short text for the panel while paused

        self.last_heartbeat = 0.0
        self.last_written: str | None = None  # display.txt body last written (skip identical writes)
        self.write_enabled = True             # False for --once: never touch the live file
        self.stop = False                     # set by the signal handler: finish the tick, then exit

    # -- the main cycle ---------------------------------------------------

    def tick(self) -> None:
        """Run whatever is due, then rewrite the display file (if it changed)."""
        now, now_dt, eff_dt, pretending = self._read_clock()
        tasty_ok = now >= self.auth_blocked_until
        if tasty_ok:
            if self.auth_error:
                log.info("auth pause over; retrying tastytrade")
                self.auth_error = None
            self._run("sessions", self.refresh_sessions, self.cfg.intervals["sessions"], now)
        mode = self._update_schedule(now_dt, eff_dt, pretending)
        self._fetch_due(now, now_dt, mode, tasty_ok)
        self._publish(now, mode)

    def _read_clock(self) -> tuple[float, datetime, datetime, bool]:
        """Step 1. Returns (now epoch, real now, schedule now, pretending?).

        Real time is used for API data and the account reference; the
        schedule time (pretend time in test mode) for everything the panel
        shows about time: mode, brightness, countdown, clock.
        """
        now = time.time()
        now_dt = datetime.now(timezone.utc)
        eff_dt, pretending = self.pretend.now(now_dt)
        if pretending != self.pretending:
            self.sources["sessions"].next_due = 0  # fetch sessions for the new (pretend) date
            if not pretending:
                self.session_eff = None
        self.pretending, self.eff_now = pretending, eff_dt
        return now, now_dt, eff_dt, pretending

    def _update_schedule(self, now_dt: datetime, eff_dt: datetime, pretending: bool) -> str:
        """Step 3. Work out the mode and everything the panel shows about time.
        Returns the mode."""
        # Without session data (API down at start-up) this degrades to the
        # weekend/overnight schedule: account + weather.
        info = self.session_eff if pretending else self.session_info
        today = info.today(eff_dt, self.cfg.tz) if info else None
        mode = compute_mode(eff_dt, today, self.cfg)
        overnight = overnight_active(eff_dt, info, self.cfg.tz)
        st = self.state
        if mode != st.mode:
            log.info("mode %s -> %s%s", st.mode, mode, " (test mode)" if pretending else "")
            if mode in ACCOUNT_MODES:
                self.sources["account"].next_due = 0  # refresh right away
            self.sources["quotes"].next_due = 0       # new mode, new interval: start with fresh prices
        if overnight != st.overnight_session:
            log.info("overnight equity session %s", "started" if overnight else "ended")
            self.sources["quotes"].next_due = 0
        st.mode, st.overnight_session = mode, overnight
        self.stocks.prefer_mark = overnight
        st.brightness = brightness_for(mode, eff_dt, self.cfg)
        st.moon = moon_phase(eff_dt)
        st.test_label = eff_dt.astimezone(self.cfg.tz).strftime("%a %H:%M") if pretending else None
        # Clock + countdown: the ticker adds `offset` to its own clock, so both
        # follow the pretend time in test mode and tick between file writes.
        event = market_event(eff_dt, info)
        st.event = (event[0], event[1].timestamp()) if event else None
        st.offset = round(eff_dt.timestamp() - now_dt.timestamp()) if pretending else 0.0
        st.big_move_pct = self.cfg.big_move_pct
        return mode

    def _fetch_due(self, now: float, now_dt: datetime, mode: str, tasty_ok: bool) -> None:
        """Step 4. Run the data sources this mode needs (each only if due)."""
        iv = self.cfg.intervals
        if mode in ACCOUNT_MODES:  # only while the strip (and so the weather) is on screen
            self._run("weather", self.weather.refresh, iv["weather"], now, tasty=False)
        if not tasty_ok or self.stop:
            return
        self._run("instruments", self.stocks.refresh_instruments, iv["instruments"], now)
        if mode == "market":
            # One stock on screen at a time: pick it at random just before
            # its turn and fetch only that quote.
            turn = self.rotation.rack_turn(now)
            if turn is not None:
                self._run("rack", lambda: self.rotation.refresh_rack(turn), 0, now)
        elif mode != "sleep":  # nothing to show while asleep; sessions keep health checks going
            quiet = mode in QUIET_MODES
            overnight = self.state.overnight_session
            self._run("quotes", lambda: self.rotation.refresh_strip(mode, overnight),
                      iv["quotes_night"] if quiet else iv["quotes_day"], now)
            self._run("account", lambda: self.account.refresh(now_dt, self.session_info),
                      iv["account_quiet"] if quiet else iv["account"], now)

    def _publish(self, now: float, mode: str) -> None:
        """Step 5. Fill in the rest of the display state and write it out."""
        st = self.state
        st.rotate = self.cfg.rotate_sec
        st.updated = max(self.sources["quotes"].last_ok, self.sources["rack"].last_ok)
        st.quotes = self.rotation.on_screen(mode)
        st.account = self.account.value
        st.weather = self.weather.current(now)
        st.status = self.status_line()
        self.write_display()
        self.heartbeat(now)

    def _run(self, name: str, fn, interval: float, now: float, tasty: bool = True) -> None:
        """Run one data source's refresh if it's due, and record the outcome.

        Every error is caught here, so one broken source can't stop the loop
        or the other sources. `tasty` marks sources that log in to tastytrade.
        """
        src = self.sources[name]
        # Re-checked per call: an auth failure earlier in this same tick
        # must stop every later tastytrade call (each would be a login).
        if not src.due(now) or (tasty and time.time() < self.auth_blocked_until):
            return
        try:
            fn()
            src.succeeded(now, interval)
        except AuthError as e:
            backoff = self.cfg.intervals["auth_backoff"]
            self.auth_blocked_until = time.time() + backoff
            self.auth_error = e.panel()
            src.failed(now, e, interval)
            log.error("AUTH FAILED (%s). Pausing all tastytrade calls for %s. If this repeats: on "
                      "my.tastytrade.com > My Profile > API > OAuth Applications > Manage, create a "
                      "new grant and put the new refresh_token (and client_secret if regenerated) in %s",
                      e.short(), duration(backoff), self.cfg.credentials)
        except Exception as e:  # noqa: BLE001 - one source must never kill the loop
            if not isinstance(e, ApiError):
                log.exception("%s: unexpected error", name)  # a bug, not an API problem: log the traceback
            src.failed(now, e, interval)

    # -- individual refreshes that belong to no other part -----------------

    def refresh_sessions(self) -> None:
        """Fetch the market calendar (and, in test mode, the calendar at the
        pretend date, so test mode gets that date's real holidays/early closes)."""
        data = self.client.get("/market-time/equities/sessions/current")["data"]
        self.session_info = SessionInfo.from_api(data)
        log.debug("sessions: %s", [(s.open.isoformat(), s.close.isoformat()) for s in self.session_info.sessions])
        if self.pretending and self.eff_now is not None:
            # The sessions API can evaluate any instant.
            at = self.eff_now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            data = self.client.get("/market-time/equities/sessions/current", [("current-time", at)])["data"]
            self.session_eff = SessionInfo.from_api(data)

    # -- output -----------------------------------------------------------

    def write_display(self) -> None:
        """Write the display file only when its content changed (saves SD-card wear)."""
        text = render_display(self.state)
        body = text.split("\n", 1)[1]  # ignore the '# written by' timestamp line
        if not self.write_enabled or body == self.last_written:
            return
        try:
            write_atomic(self.cfg.display, text)
            self.last_written = body
        except OSError as e:
            log.error("cannot write display file %s: %s", self.cfg.display, e)

    def status_line(self) -> str:
        """The most important problem, short enough for the panel ("ok" if none)."""
        if self.auth_error:
            return "AUTH " + self.auth_error
        for name, label in STATUS_LABELS:
            src = self.sources[name]
            if src.errors.failing and src.failures:
                return f"{label} {src.panel_error}"
        return "ok"

    def heartbeat(self, now: float) -> None:
        """Every [intervals] heartbeat seconds, one INFO line summing up the
        fetcher's health (mode, how old the data is, errors)."""
        if now - self.last_heartbeat < self.cfg.intervals["heartbeat"]:
            return
        self.last_heartbeat = now
        age = lambda s: duration(now - s.last_ok) if s.last_ok else "never"
        tok = self.client.token_age()
        st = self.state
        log.info("heartbeat: mode=%s%s overnight=%s pool=%d/%d skipped=%d quotes age: strip %s, next-up %s "
                 "weather %s account=%s token_age=%s status=%s",
                 st.mode, f" (TEST {st.test_label})" if st.test_label else "",
                 "on" if st.overnight_session else "off",
                 len(self.rotation.pool(st.mode, st.overnight_session)),
                 len(self.cfg.equities),
                 len(self.stocks.bad), age(self.sources["quotes"]), age(self.sources["rack"]),
                 age(self.sources["weather"]),
                 "ok" if st.account else "n/a", duration(tok) if tok is not None else "none",
                 st.status)

    def run_forever(self) -> None:
        """What the service runs: tick until stopped (SIGTERM / Ctrl-C)."""
        log.info("fetcher %s starting; display file %s", VERSION, self.cfg.display)
        while not self.stop:
            try:
                self.tick()
            except Exception:  # noqa: BLE001
                log.exception("unexpected error in main loop; continuing in 30s")
                time.sleep(30)
                continue
            time.sleep(0.5)  # ticks are cheap; this just times the pre-turn fetch closely
        log.info("fetcher stopped")
