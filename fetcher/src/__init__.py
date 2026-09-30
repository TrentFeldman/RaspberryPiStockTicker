"""The fetcher's source code, one job per file.

`fetcher.py` (one folder up) is only the front door: it reads the command
line and starts `app.Fetcher`. Everything else lives here. Read the files
roughly in this order, simplest first:

  Basics (no stock knowledge)
    util.py           tiny helpers: safe number parsing, "1h05m" durations
    logs.py           where log lines go; hides secrets; collapses repeated errors
    config.py         reads config.toml into a Config object
    credentials.py    the ONLY file that reads tastytrade.conf (the secrets)
    web.py            every HTTP request goes through http_json(); API errors

  Pure logic (no network: easy to test)
    sessions.py       market calendar: when the market opens/closes, 24/5 nights
    schedule.py       which screen mode it is right now (market, after, sleep, ...)
    pretend.py        test mode: pretend it's another time (pretend.sh)
    quotes.py         the Quote record and how a tastytrade price becomes one
    picking.py        random picks: who may be picked when, the shuffled deck
    display_file.py   writes display.txt, the file the LED ticker reads

  Data sources (talk to the internet)
    tastytrade.py     logged-in tastytrade client (token refresh, batching)
    sources.py        when each source is due again; backoff after errors
    stocks.py         which symbols exist, their quotes
    weather.py        weather for the strip (wttr.in)
    account.py        account value and its day change

  Putting it together
    rotation.py       what's on screen: the next stock (market hours) or the strip
    app.py            the main loop: Fetcher.tick() runs about twice a second
    check.py          `fetcher.py --check`: try every call once, print a report

See ../../CODE_GUIDE.md for a guided tour.
"""

VERSION = "1.0"
