#!/bin/bash
# Network watchdog. Run every 2 minutes by hub75-netwatch.timer, as root.
#
# If the Pi can't resolve any host name for 10 minutes, it restarts tailscaled
# (it runs the Pi's DNS) and reconnects the Wi-Fi, then tries again every 10
# minutes for as long as it stays broken. When names work again it just notes
# how long the outage lasted. It never reboots the Pi.
#
# Why: one night the Pi's DNS died at 05:22 and nothing fixed it until
# someone replugged it at 08:08. This is that replug, minus the human.
#
# Events (not every check) go to logs/netwatch.log and the journal
# (journalctl -t hub75-netwatch). Settings can be overridden through the
# NETWATCH_* variables below; tests/netwatch_test.sh uses them.
set -u

HUB=$(cd "$(dirname "$0")/.." && pwd)
IFACE=${NETWATCH_IFACE:-wlan0}                              # the Wi-Fi interface to reconnect
HOSTS=${NETWATCH_HOSTS:-"api.tastyworks.com cloudflare.com"} # healthy if ANY of these resolves
AFTER=${NETWATCH_AFTER:-600}                                # seconds broken before repairing
STATE=${NETWATCH_STATE:-/run/hub75-netwatch}                # since = when it broke, tried = last repair
LOG=${NETWATCH_LOG:-$HUB/logs/netwatch.log}
DRY=${NETWATCH_DRY:-}                                       # set: log the repair but don't do it

say() { echo "$(date '+%F %T') $*" >> "$LOG"; logger -t hub75-netwatch "$*"; }

mkdir -p "$STATE"
now=$(date +%s)

# Healthy: any name resolves. Clear the state and note how long it was down.
for h in $HOSTS; do
  if timeout 8 getent hosts "$h" > /dev/null; then
    if [ -f "$STATE/since" ]; then say "names resolve again after $(( now - $(cat "$STATE/since") ))s"; fi
    rm -f "$STATE/since" "$STATE/tried"
    exit 0
  fi
done

# Broken. Remember when it started.
if [ ! -f "$STATE/since" ]; then
  echo "$now" > "$STATE/since"
  say "cannot resolve names; will try to repair after $(( AFTER / 60 )) min"
fi
since=$(cat "$STATE/since")
tried=$(cat "$STATE/tried" 2> /dev/null || echo 0)

# Broken long enough, and not repaired within the last AFTER seconds: repair.
if [ $(( now - since )) -ge "$AFTER" ] && [ $(( now - tried )) -ge "$AFTER" ]; then
  echo "$now" > "$STATE/tried"
  say "no names for $(( (now - since) / 60 )) min: restarting tailscaled, reconnecting $IFACE${DRY:+ (dry run)}"
  if [ -z "$DRY" ]; then
    if systemctl cat tailscaled > /dev/null 2>&1; then systemctl restart tailscaled || say "tailscaled restart failed"; fi
    nmcli device reconnect "$IFACE" || say "reconnect of $IFACE failed"
  fi
fi
