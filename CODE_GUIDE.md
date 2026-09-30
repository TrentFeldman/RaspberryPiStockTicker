# Code guide: a tour of the ticker's code

This guide is for reading the code, not running it (the README covers that). Every file starts
with a comment that explains its job, so once you know which file to open, the file explains itself.

## The big picture: two programs and one text file

```
 tastytrade API ─┐                                         ┌─────────────────────────┐
 wttr.in ────────┴──> FETCHER (Python) ──> display.txt ──> │ TICKER (C++)            │ ──> LED panel
                      fetcher/                (plain text)  │ ticker/                 │
                      decides WHAT to show                  │ decides HOW it looks    │
                      runs as you, ~2 ticks/s               │ runs as root, ~60 fps   │
                                                            └─────────────────────────┘
```

- The **fetcher** does all the thinking: what time it is, which mode (market, after hours, sleep,
  …), which stock is up next, getting prices, handling errors. It writes its conclusions to
  `ticker/display.txt`.
- The **ticker** does all the drawing. It never talks to the internet. It re-reads `display.txt`
  whenever the file changes and draws it about 60 times a second.
- `display.txt` is the only link between them, so either can be restarted without the other. It's
  plain text you can `cat`. The format is documented in both `fetcher/src/display_file.py`
  (writing) and `ticker/src/display_file.h` (reading).

## Follow one price from the internet to the wall

Market hours, 10:00:04, one turn every 6 seconds:

| When | Where | What happens |
|---|---|---|
| 10:00:04.0 | `fetcher/src/app.py` `tick()` | Runs twice a second. Step 3 works out the mode: `market`. |
| | `fetcher/src/rotation.py` `rack_turn()` | The next turn starts at 10:00:06, 2 s away, so it's time to rack it. |
| | `fetcher/src/picking.py` `Deck.draw()` | Deals the next card from the shuffled deck, say `NVDA`. |
| | `fetcher/src/stocks.py` `fetch_quotes()` → `tastytrade.py` `get()` | One small request for NVDA's quote. |
| | `fetcher/src/quotes.py` `parse_quote()` | Price $118.02, +6.21 % today, plus day/52-week ranges. |
| | `fetcher/src/rotation.py` `quotes_for()` | +6.21 % is at least 5 %, a big mover, so NVDA goes back in the deck to come up again soon. |
| | `fetcher/src/display_file.py` `render_display()` | Writes the line `quote NVDA 118.02 6.21 ... big=1 turn=N` to `display.txt`. |
| 10:00:04.5 | `ticker/src/main.cpp` | Notices the file changed (checked once a second) and re-reads it (`display_file.h`). |
| 10:00:06.0 | `ticker/src/rotation.h` `FeaturedIndex()` | The clock says turn N has started, so NVDA's turn has come. |
| | `ticker/src/screen.h` `DrawScreen()` | Market mode with quotes, so it draws the full-screen stock view. |
| | `ticker/src/screen_stock.h` `DrawStockFull()` | Draws the gold frame, symbol, price, change, ranges and clock. |
| every 1/60 s | `ticker/src/main.cpp` | The frame goes to the panel (`SwapOnVSync`). |

Both programs work out "turn N" from the clock (`turn = epoch seconds / 6`), so they never have to
signal each other.

## Reading order

**Fetcher** (`fetcher/`, Python, standard library only):
1. `fetcher.py`: the front door; only reads the command line.
2. `src/app.py`: the main loop. Read `tick()` and its five steps; everything else hangs off it.
3. `src/schedule.py` and `src/picking.py`: the rules (which mode when; who may be picked when).
4. `src/rotation.py`: how the next stock or the strip gets picked and fetched.
5. The rest as needed; `src/__init__.py` lists every file with one line each.

**Ticker** (`ticker/src/`, C++; `main.cpp` includes all the headers, built as one program):
1. `main.cpp`: start-up and the frame loop.
2. `screen.h`: which screen to draw right now.
3. `screen_stock.h`, `screen_account.h`, `strip.h`, `night_sky.h`: the screens themselves.
4. Building blocks: `widgets.h` (arrows, range bars), `format.h` (number text), `clock.h`,
   `fonts.h`, `colors.h`, `led.h` (the LED library's drawing names).

## File map

### `fetcher/src/`
| File | Job |
|---|---|
| `util.py` | tiny helpers: safe number parsing, "1h05m" |
| `logs.py` | log setup; hides secrets; collapses repeated errors |
| `config.py` | reads `config.toml` into one `Config` |
| `credentials.py` | the **only** file that reads `tastytrade.conf` (secrets) |
| `web.py` | every HTTP request (`http_json`), and `ApiError` |
| `tastytrade.py` | logged-in tastytrade client: token refresh, 100-symbol batches |
| `sessions.py` | market calendar: open/close times, the countdown target, 24/5 nights |
| `schedule.py` | which mode it is; brightness; moon phase |
| `pretend.py` | test mode (`pretend.sh`) |
| `quotes.py` | the `Quote` record; tastytrade price → quote |
| `picking.py` | who may be picked when; the shuffled `Deck`; turn numbers |
| `display_file.py` | writes `display.txt` |
| `sources.py` | when each data source runs next; backoff after errors |
| `stocks.py` | which symbols exist / trade 24/5; stock quotes |
| `weather.py` | weather for the strip (wttr.in) |
| `account.py` | account value and day change |
| `rotation.py` | what's on screen: next stock (market hours) or the strip |
| `app.py` | the main loop (`Fetcher.tick`) |
| `check.py` | `fetcher.py --check` report |

### `ticker/src/`
| File | Job |
|---|---|
| `main.cpp` | start-up, options, the frame loop |
| `display_file.h` | the `Quote`/`Display` records; reading `display.txt` |
| `screen.h` | which screen to draw |
| `screen_stock.h` | market hours: one stock, full screen |
| `screen_account.h` | the account value (outside market hours) |
| `strip.h` | the scrolling strip |
| `night_sky.h` | the sleep screen |
| `health.h` | STALE / error text, the NO DATA screen |
| `widgets.h` | arrows, change text, range bars |
| `format.h` | number formatting (commas, prices, range labels) |
| `clock.h` | clock and OPENS/CLOSES countdown |
| `rotation.h` | whose turn it is |
| `fonts.h` | the four font roles, and where the strip sits |
| `colors.h` | every colour |
| `led.h` | short names for the LED library's drawing tools |

Shared by all the C++ programs: `panel.h` (panel setup, calibration, font choice). `term.h` is
keyboard input for `calibrate`.

## "I want to change…"

| Change | Where |
|---|---|
| Which stocks can appear | `fetcher/config.toml` `[symbols]` (restart the fetcher) |
| Times of day (pre-market start, night, sleep) | `config.toml` `[schedule]` |
| Brightness | `config.toml` `[display]` |
| How long each stock stays up; strip size | `config.toml` `[rotation]` |
| How often each source is asked | `config.toml` `[intervals]` |
| What counts as a "big mover" | `config.toml` `[display] big_move_pct` |
| Who may be picked in which mode | `fetcher/src/picking.py` `eligible()` |
| What the mode is at a given time | `fetcher/src/schedule.py` `compute_mode()` |
| A new stat on the stock screen | fetcher `quotes.py` `STAT_FIELDS`, then ticker `screen_stock.h` |
| Colours | `ticker/src/colors.h` |
| Fonts | `fonts.conf` (deploy, then restart the ticker; format in `panel.h`) |
| The layout of a screen | `ticker/src/screen_stock.h` / `screen_account.h` (a picture at the top of each) |
| Strip speed | `ticker --scroll-speed=` (pixels per second, default 30) |
| Weather place or units | `config.toml` `[weather]`; what it says and which colour name each piece gets: `fetcher/src/weather.py` |
| Weather colours | `ticker/src/colors.h` `WeatherColor` |
| Night sky | `ticker/src/night_sky.h` |
| STALE timing | `ticker --stale-after=` (seconds, default 300) |
| What's on the panel when something breaks | fetcher `app.py` `status_line()`, ticker `health.h` |

After changing code: copy it to the Pi, run `make` and the unit tests (README "Push to the Pi").
The running services keep the old version until they're restarted
(`sudo systemctl restart hub75-fetcher hub75-ticker`).

## Rules the code sticks to

- **Secrets stay secret.** Only `credentials.py` reads `tastytrade.conf`. Every secret is registered
  with the log filter (`logs.py SecretFilter`), which replaces it with `***` in any log line.
- **Never hammer a login.** Any login failure pauses *all* tastytrade calls for 30 minutes
  (`app.py _run`). tastytrade blocks an IP for about 8 hours after repeated failed logins.
- **Be light on tastytrade.** Market hours: one tiny request per 6 s turn. Off hours: one request
  a minute or two. Bulk requests go in batches of 100 symbols.
- **One failure never stops the rest.** Each data source runs on its own timer inside a
  catch-everything wrapper (`app.py _run`, `sources.py`). The last good data stays up; if it gets
  old, the panel says `STALE`.
- **The panel never shows half a file.** `display.txt` is written to a temp file and renamed into
  place (`display_file.py write_atomic`).
- **Test mode can't get stuck.** A pretend time switches itself off (`pretend.py`).

## Tests

| What | Command (on the Pi) | Covers |
|---|---|---|
| Unit tests | `cd fetcher && python3 -m unittest discover tests -v` | one `tests/test_<name>.py` per `src/<name>.py`; no network needed |
| Ticker samples | `bash tests/ticker_samples.sh` (stop `hub75-ticker` first) | every `ticker/samples/*.txt` starts and exits cleanly |
| Real APIs | `python3 fetcher/fetcher.py --check` | each API call once, pass/fail report |
| Dry run | `cd fetcher && python3 fetcher.py --once` | one full tick, printed instead of written |
| Other times of day | `bash tests/pretend_modes.sh` | `--once` at six pretend times |
| Look at a screen | `sudo ./ticker/ticker --display=ticker/samples/market.txt --stale-after=0` | the real panel, sample data |
