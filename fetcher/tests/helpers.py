"""Shared bits for the unit tests (not a test file itself).

Run all tests from hub75/fetcher (no network needed):

    python3 -m unittest discover tests -v

Each test_<name>.py file tests src/<name>.py; test_app.py runs whole ticks
with the network replaced by fakes.
"""

import sys
from datetime import datetime
from pathlib import Path

FETCHER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FETCHER_DIR))  # so `import src...` works from the tests folder

from src.config import load_config  # noqa: E402
from src.sessions import Session, SessionInfo  # noqa: E402

CFG = load_config(FETCHER_DIR / "config.toml")  # the real config.toml
ET = CFG.tz  # America/New_York


def et(y, mo, d, h, mi=0):
    """A time in New York: et(2026, 9, 28, 9, 30) = Mon 28 Sep 2026, 9:30 am."""
    return datetime(y, mo, d, h, mi, tzinfo=ET)


def session(y, mo, d, close_h=16, ext_h=20):
    """A regular trading session on that day (9:30 open)."""
    return Session(et(y, mo, d, 9, 30), et(y, mo, d, close_h), et(y, mo, d, ext_h))


def week_info(*days):
    """SessionInfo with regular sessions on the given (y, m, d) days."""
    return SessionInfo([session(*d) for d in days])
