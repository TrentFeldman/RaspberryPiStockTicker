"""`fetcher.py --check`: try every call once and print a pass/fail report.

    PASS  credentials file        /home/pi/hub75/ticker/tastytrade.conf (mode 600)
    PASS  oauth token             access token issued
    PASS  account                 ****34
    PASS  sessions                mode now: market, overnight session off
    PASS  symbols + 24/5          335/335 found, 218 trade overnight
    PASS  quotes (every symbol)   335/335 symbols
    PASS  balance + day change    value ok, change ok
    PASS  weather                 Ulaanbaatar: {mild}68F {sun}Sunny | {label}Humidity {value}52% | ...
    PASS  display file writable   /home/pi/hub75/ticker

    9 passed, 0 failed

Safe to run while the service is running: it never writes display.txt
(only a throwaway display.check next to it), and it logs in exactly once.
If the login fails, the steps that need it are skipped, not retried.
"""

from __future__ import annotations

import stat
from datetime import datetime, timezone

from .app import Fetcher
from .config import Config
from .credentials import Credentials, load_credentials
from .display_file import write_atomic
from .schedule import compute_mode
from .sessions import overnight_active
from .weather import WeatherData
from .web import ApiError


def run_check(cfg: Config) -> int:
    """Run every check, print the report, return the exit code (0 = all passed)."""
    results: list[tuple[bool, str, str]] = []  # (passed?, step name, detail)

    def step(name: str, fn) -> bool:
        """Run one check; a returned string is shown as the detail."""
        try:
            detail = fn()
            results.append((True, name, detail or ""))
            return True
        except SystemExit as e:  # load_credentials stops with a readable message
            results.append((False, name, str(e)))
        except Exception as e:  # noqa: BLE001
            results.append((False, name, e.short() if isinstance(e, ApiError) else f"{type(e).__name__}: {e}"))
        return False

    def weather() -> str:  # wttr.in, no login: the place it picked and what the strip will show
        w = WeatherData(cfg)
        w.refresh()
        return f"{w.area}: {' | '.join(w.items)}"

    creds: list[Credentials] = []
    step("credentials file", lambda: creds.append(load_credentials(cfg.credentials)) or
         f"{cfg.credentials} (mode {stat.S_IMODE(cfg.credentials.stat().st_mode):o})")
    if creds:
        _check_tastytrade(Fetcher(cfg, creds[0]), cfg, step)
    step("weather", weather)
    check_file = cfg.display.with_name("display.check")
    step("display file writable", lambda: write_atomic(check_file, "ok\n") or check_file.unlink()
         or str(cfg.display.parent))

    width = max(len(n) for _, n, _ in results)
    for ok, name, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<{width}}  {detail}")
    failed = sum(not ok for ok, _, _ in results)
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


def _check_tastytrade(f: Fetcher, cfg: Config, step) -> None:
    """Log in once; only if that works, try every tastytrade call."""
    c = f.client
    if not step("oauth token", lambda: c.refresh_token() or "access token issued"):
        return
    step("account", lambda: f"****{c.account()[-2:]}")
    now = datetime.now(timezone.utc)

    def sessions() -> str:
        f.refresh_sessions()
        mode = compute_mode(now, f.session_info.today(now, cfg.tz), cfg)
        overnight = "on" if overnight_active(now, f.session_info, cfg.tz) else "off"
        return f"mode now: {mode}, overnight session {overnight}"

    def symbols() -> str:
        f.stocks.refresh_instruments()
        known = f.stocks.known
        text = f"{len(known)}/{len(cfg.equities)} found, {len(f.stocks.overnight_ok)} trade overnight"
        if len(known) < len(cfg.equities):
            text += f"; NOT FOUND: {' '.join(s for s in cfg.equities if s not in known)}"
        return text

    def balance() -> str:
        f.account.refresh(datetime.now(timezone.utc), f.session_info)
        return "value ok, change ok" if f.account.value[1] is not None else "value ok, change unavailable"

    step("sessions", sessions)
    step("symbols + 24/5", symbols)
    step("quotes (every symbol)", f.stocks.check_all)
    step("balance + day change", balance)
