#!/bin/bash
# Test mode: make the ticker pretend it's another time, to preview the schedule.
#
#   ./pretend.sh "mon 10:00"          market hours (full-screen stock stats)
#   ./pretend.sh "mon 17:00"          after hours (account + everything)
#   ./pretend.sh "mon 21:00"          overnight: account + 24h stocks + weather, dimmed
#   ./pretend.sh "fri 21:00"          overnight, no stock session: weather only
#   ./pretend.sh "sat 12:00"          weekend: account + weather
#   ./pretend.sh "mon 23:30"          sleep (night sky)
#   ./pretend.sh "2026-12-25 11:00"   any date/time `date -d` understands
#   ./pretend.sh off                  back to real time
#   ./pretend.sh                      show the current state
#
# Optional second argument: minutes before it switches itself off (default 30,
# capped at [pretend] max_minutes in fetcher/config.toml). Pretend time keeps
# flowing from the moment you set it. Prices and the account stay real; only
# the schedule (what's shown, brightness) follows the pretend clock.
# The panel shows a small TEST badge while this is on. No restart needed.
set -euo pipefail
HUB=$(cd "$(dirname "$0")" && pwd)
FILE=$HUB/pretend.json

if [ $# -eq 0 ]; then
  if [ -f "$FILE" ]; then
    echo "pretend file: $(cat "$FILE")"
    grep -h 'TEST MODE\|test mode' "$HUB/logs/fetcher.log" 2>/dev/null | tail -n 2
  else
    echo "real time (no pretend file)"
  fi
  exit 0
fi

if [ "$1" = off ]; then
  rm -f "$FILE"
  echo "back to real time (takes effect within a second)"
  exit 0
fi

target=$(TZ=America/New_York date -d "$1" --iso-8601=seconds) || {
  echo "couldn't understand the time '$1' (try: \"mon 10:00\" or \"2026-09-28 20:30\")" >&2
  exit 1
}
minutes=${2:-30}
printf '{"target": "%s", "set_at": %s, "expires_min": %s}\n' "$target" "$(date +%s)" "$minutes" > "$FILE.tmp"
mv "$FILE.tmp" "$FILE"
echo "pretending it is $(TZ=America/New_York date -d "$target" '+%a %Y-%m-%d %H:%M %Z') for ${minutes} min"
echo "(back to real time automatically, or: $0 off)"
