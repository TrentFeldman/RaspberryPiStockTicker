# hub75 LED stock ticker

A 128×64 HUB75 RGB LED panel on a Raspberry Pi 4. During market hours it shows live stock and ETF
quotes, one full screen at a time. Outside them it shows your tastytrade account value, with a
scrolling strip of overnight-tradable stocks and the weather. At night it shows a night sky.

Two programs share one text file:

- **fetcher** (Python 3.11+, stdlib only) polls the tastytrade API and wttr.in, and writes `ticker/display.txt`.
- **ticker** (C++) reads that file and draws it on the panel at about 60 fps.

Either one can be restarted without the other. [CODE_GUIDE.md](CODE_GUIDE.md) is a guided tour of the code.

## Hardware

- **Panel:** P2.5 128×64, 1/32 scan. Column driver FM6565 (S-PWM), row driver TC7559 (shift-register
  row select, not A–E address lines). Mainline hzeller/rpi-rgb-led-matrix, Adafruit and most
  tutorials show **nothing** on this panel.
- **Driver library:** the S-PWM fork of rpi-rgb-led-matrix (see hzeller/rpi-rgb-led-matrix #1866),
  using the FM6373 profile:
  `--led-panel-type=fm6373 --led-spwm-row-addr-type=1 --led-spwm-scan=64 --led-spwm-data-layout=1 --led-spwm-register-config=2`
  (calibrate mode 2).
- **Adapter:** Seengreat RGB Matrix Adapter, regular pinout. It also powers the Pi.
- **Power:** a 5 V 4 A supply, shared by the Pi and the panel. That's enough for mostly-dark
  content, but not for full white at high brightness.
- **Cabling:** the ribbon goes into the panel's **input** socket (the arrows point away from it).
  S-PWM panels don't always flash at power-up, so no flash doesn't mean it isn't working.

## Modes

The mode is picked from the clock (America/New_York). Session times come from tastytrade's
market-sessions API, so holidays and early closes are handled automatically.

| Mode | When | Screen |
|---|---|---|
| `market` | regular session | one random stock full screen, 6 s each: price, change, day and 52-week ranges, open/gap |
| `pre` / `after` | 06:30 → open, close → 20:00 | account value, plus a strip of 24h stocks and weather |
| `weekend` | weekends and holidays, 06:30–20:00 | account value, plus a weather strip |
| `overnight` | 20:00–23:00 | account value, plus a weather strip (and 24h stocks while an overnight session runs); dimmed |
| `sleep` | 23:00–06:30 | night sky: twinkling stars, the moon at its real phase, shooting stars |

- **Random picks:** stocks are dealt from a shuffled deck, so none repeats until all have been shown.
- **Big movers:** a stock that moved ≥ `big_move_pct` gets a gold frame and one extra turn.
- **Overnight prices:** 24h stocks use the bid/ask midpoint, because `last` and `mark` stay frozen overnight.
- **Weather:** colour-coded, from wttr.in (no API key). It's fetched only while the strip is on
  screen, at most every 30 min.
- **Health:** problems show on the panel in red: `! NO NETWORK 12m`, `STALE 12m`, `! AUTH`, `! QUOTES …`, `NO DATA`.

## Setup

1. Raspberry Pi OS 64-bit, timezone America/New_York. Install the tools:
   `sudo apt install git g++ make python3`.
2. Clone and build the S-PWM fork to `~/matrix-pwm-test`.
3. Put this repo next to it, e.g. `~/hub75` beside `~/matrix-pwm-test` (see below). All paths are
   relative to the repo; a library elsewhere needs `make RGB_DIR=/path/to/it`.
4. Run `make`, then `sudo ./calibrate`. Keys: `m` mode, arrows shift, `p` pattern, Enter saves
   `panel.conf`.
5. Create a tastytrade OAuth app with **only the `read` scope** (my.tastytrade.com → API → OAuth
   Applications), then create a grant.
6. Write `ticker/tastytrade.conf` with `chmod 600`:
   ```
   client_secret=…
   refresh_token=…
   ```
7. `python3 fetcher/fetcher.py --check` checks the credentials, the API, the symbols and the weather.
8. `sudo deploy/install.sh` builds, checks, and installs and starts the `hub75-fetcher` and
   `hub75-ticker` services and the network watchdog timer. Use `--uninstall` to remove them.
9. Optional: keep system logs across reboots, so an outage can be diagnosed after a restart:
   `sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald`.

### Push to the Pi and build

Clone on the Pi (`git clone … ~/hub75`, then `git pull` to update), or push from another machine:

```bash
rsync -av --exclude-from=.gitignore ./ pi@raspberrypi:hub75/
ssh pi@raspberrypi 'cd hub75 && make && cd fetcher && python3 -m unittest discover tests'
ssh -t pi@raspberrypi 'sudo systemctl restart hub75-fetcher hub75-ticker'
```

From Windows, convert line endings to LF first (`git config core.autocrlf input`), or the scripts
won't run.

## Configuration

Everything is in `fetcher/config.toml`, and every key is required:

- symbols, by sector;
- schedule times;
- brightness per mode;
- polling intervals;
- rotation speed;
- weather location and units.

Restart `hub75-fetcher` after editing it.

Fonts are BDF files, set per role (big, mid, small, strip) in `fonts.conf`. The layout adapts to the
font sizes. The bundled fonts are in `fonts/`, with their licences.

## API usage

- **Market hours:** one small quote request per 6 s turn, for the next stock only.
- **Off hours:** one request per strip refresh (every 1–2 min), plus the account value (every 2–10 min).
- **Sleep:** only the market calendar.
- **Errors:** they back off exponentially (up to 5 min). An auth failure pauses all tastytrade calls
  for 30 min, because repeated failed logins get your IP blocked for about 8 h.
- **Logs:** secrets are redacted from all log output.

## Operation

| Task | Command |
|---|---|
| Health overview | `./status.sh` |
| Log | `logs/fetcher.log` (rotating), or `journalctl -u hub75-fetcher`; network repairs: `logs/netwatch.log` |
| Test the API connection | `python3 fetcher/fetcher.py --check` |
| Dry run (prints the display file) | `python3 fetcher/fetcher.py --once` |
| Preview another time of day | `./pretend.sh "mon 10:00"` … `./pretend.sh off` (turns itself off after 30 min) |
| Draw a sample without live data | stop `hub75-ticker`, then `sudo ticker/ticker --display=ticker/samples/after.txt --stale-after=0` |
| Unit tests | `cd fetcher && python3 -m unittest discover tests` |
| Ticker smoke test | `bash tests/ticker_samples.sh` (stop `hub75-ticker` first) |
| Network watchdog test | `bash tests/netwatch_test.sh` (no root, no network) |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Panel dark, services running | Panel settings changed: re-run `calibrate`. |
| Scrambled or doubled image | Re-run `calibrate`. |
| `! NO NETWORK 12m` | The Pi can't resolve names or connect: Wi-Fi, router or DNS. After 10 min the network watchdog (`deploy/netwatch.sh`, a systemd timer set up by `install.sh`) restarts tailscaled (if installed) and reconnects Wi-Fi via NetworkManager, repeating every 10 min. It never reboots. What it did is in `logs/netwatch.log`. |
| `STALE` | No fresh quotes for 5 min, but the network is fine: the fetcher stopped or tastytrade is failing. Check `logs/fetcher.log`. |
| `! AUTH` | The grant was deleted or the secret regenerated: create a new grant. Don't restart in a loop; each start is a login attempt. |
| Every tastytrade request times out | The IP is blocked after failed logins (~8 h). Wait it out. |
| `! QUOTES HTTP 403` | REST quotes need a funded account. |
| Wrong mode | Check the Pi's timezone and NTP (`timedatectl`). |
| Flicker, random resets | Run `vcgencmd get_throttled`. `0x50005` means under-voltage: use a better supply or lower the brightness. |

**Flicker:** the Pi clocks the S-PWM chips from a busy-looping thread, so reserve CPUs 2–3 for it.
- Append `isolcpus=domain,managed_irq,2,3 nohz_full=2,3 rcu_nocbs=2,3 irqaffinity=0,1` to
  `/boot/firmware/cmdline.txt`.
- The ticker service is pinned to CPU 2, and the library's refresh thread runs on CPU 3.
- If it still flickers, try `idle=poll`, then a real-time kernel.

## Disclaimer

This is a hobby project and not affiliated with tastytrade. It only reads data, and never places orders.
