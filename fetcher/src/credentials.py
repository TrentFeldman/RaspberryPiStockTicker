"""The tastytrade login secrets. The ONLY file that reads tastytrade.conf.

tastytrade.conf lives only on the Pi (ticker/tastytrade.conf), is
never committed or copied, and must be readable by its owner only
(chmod 600). It holds two lines:

    client_secret=...    from my.tastytrade.com > API > OAuth Applications
    refresh_token=...    from the same page ("create grant")

As soon as the values are read they're registered with logs.SecretFilter,
so even an accidental log line or error message shows *** instead.
"""

from __future__ import annotations

import stat
from dataclasses import dataclass
from pathlib import Path

from .logs import SecretFilter, log


@dataclass
class Credentials:
    client_secret: str
    refresh_token: str

    def __repr__(self) -> str:  # never print the values, even when debugging
        return "Credentials(***)"


def load_credentials(path: Path) -> Credentials:
    """Read key=value lines. Stops the program with a clear message if the
    file or a value is missing. Values are never logged or printed."""
    if not path.exists():
        raise SystemExit(f"credentials file not found: {path} "
                         "(create it with client_secret=... and refresh_token=...)")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:  # any permission for "group" or "others"
        log.warning("credentials file %s is readable by other users (mode %o); run: chmod 600 %s",
                    path, mode, path)
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    missing = [k for k in ("client_secret", "refresh_token") if not values.get(k)]
    if missing:
        raise SystemExit(f"credentials file {path} is missing: {', '.join(missing)}")
    creds = Credentials(values["client_secret"], values["refresh_token"])
    SecretFilter.add(creds.client_secret, creds.refresh_token)
    return creds
