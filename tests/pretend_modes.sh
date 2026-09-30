#!/bin/bash
HUB=$(cd "$(dirname "$0")/.." && pwd)  # the project folder
# Dry-run the fetcher (--once: prints, never writes display.txt) at several
# pretend times and summarise what the panel would get. Real API data.
# Note: while this runs, a running fetcher service also sees the pretend file.
cd "$HUB"/fetcher
for t in "mon 10:00" "mon 17:00" "mon 21:00" "fri 21:00" "sat 12:00" "mon 23:30"; do
  $HUB/pretend.sh "$t" 5 >/dev/null
  out=$(python3 fetcher.py --once 2>/dev/null)
  printf '%-10s %s | quotes: %s\n' "$t" \
    "$(echo "$out" | grep -E '^(mode|brightness|test)' | tr '\n' ' ')" \
    "$(echo "$out" | awk '$1=="quote"{printf "%s ", $2}')"
done
$HUB/pretend.sh off >/dev/null
echo "(pretend off)"
