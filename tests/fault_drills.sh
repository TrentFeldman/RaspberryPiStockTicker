#!/bin/bash
HUB=$(cd "$(dirname "$0")/.." && pwd)  # the project folder
# Fault drills for the fetcher, using throwaway config/credentials/log/display
# in a temp dir (the live files are never touched).
#
#   bash tests/fault_drills.sh network   unreachable API: expect backoff + collapsed errors + STALE-able status
#   bash tests/fault_drills.sh auth      wrong client_secret: expect exactly ONE login attempt, then a 30 min pause
#
# The auth drill makes one failed login to tastytrade (well below the IP-block threshold).
set -u
drill=${1:?usage: fault_drills.sh network|auth}
secs=${2:-75}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
src=$HUB/fetcher/config.toml

sed -e "s|^credentials = .*|credentials = \"$tmp/creds.conf\"|" \
    -e "s|^display = .*|display = \"$tmp/display.txt\"|" \
    -e "s|^log_file = .*|log_file = \"$tmp/fetcher.log\"|" "$src" > "$tmp/config.toml"

case $drill in
  network)
    cp $HUB/ticker/tastytrade.conf "$tmp/creds.conf"
    sed -i 's|^base_url = .*|base_url = "https://api.invalid"|' "$tmp/config.toml"
    ;;
  auth)
    # Real refresh token, deliberately wrong secret.
    { grep '^refresh_token=' $HUB/ticker/tastytrade.conf; echo "client_secret=deliberately-wrong-for-drill"; } > "$tmp/creds.conf"
    ;;
esac
chmod 600 "$tmp/creds.conf"

echo "== running fetcher for ${secs}s with the $drill fault"
timeout -s TERM "$secs" python3 $HUB/fetcher/fetcher.py --config "$tmp/config.toml" 2>/dev/null
echo "== log"
cat "$tmp/fetcher.log"
echo "== display status line"
grep -E '^(status|updated|mode)' "$tmp/display.txt"
echo "== oauth attempts logged: $(grep -c 'AUTH FAILED' "$tmp/fetcher.log")"
echo "== secret scan (expect 0): $(grep -c 'deliberately-wrong-for-drill' "$tmp/fetcher.log")"
