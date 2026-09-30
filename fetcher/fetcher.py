#!/usr/bin/env python3
"""hub75 ticker data fetcher.

Pulls quotes and the account value from tastytrade (plus the weather from
wttr.in), picks symbols at random from config.toml, decides what the LED
panel should show for the time of day, and writes ticker/display.txt
for the C++ ticker to draw.

This file is only the front door: it reads the command line and starts the
right thing. The code itself lives in src/ (see src/__init__.py for a map,
and ../CODE_GUIDE.md for a guided tour).

Usage:
  fetcher.py              run forever (what the hub75-fetcher service does)
  fetcher.py --check      test every API call once and print a pass/fail report
  fetcher.py --once       fetch everything once and print the display file
                          (doesn't touch the live display.txt)
  fetcher.py --verbose    debug logging
  fetcher.py --config PATH

Standard library only (Python 3.11+).
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

from src.app import Fetcher
from src.check import run_check
from src.config import load_config
from src.credentials import load_credentials
from src.display_file import render_display
from src.logs import log, setup_logging

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config.toml"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ap.add_argument("--check", action="store_true", help="test every API call once and exit")
    ap.add_argument("--once", action="store_true", help="fetch once and print the display file")
    ap.add_argument("--verbose", action="store_true", help="debug logging")
    args = ap.parse_args()

    cfg = load_config(args.config)
    # --check and --once are run by hand: log to the terminal only, not the log file.
    setup_logging(cfg, args.verbose, to_file=not (args.check or args.once))
    if args.check:
        return run_check(cfg)

    fetcher = Fetcher(cfg, load_credentials(cfg.credentials))
    if args.once:
        fetcher.write_enabled = False  # don't touch the live file
        fetcher.tick()
        print(render_display(fetcher.state), end="")
        return 0 if fetcher.state.status == "ok" else 1

    def on_signal(signum, _frame):
        """systemctl stop / Ctrl-C: finish the current tick, then exit cleanly."""
        log.info("received %s, stopping", signal.Signals(signum).name)
        fetcher.stop = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    fetcher.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
