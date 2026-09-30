#!/bin/bash
# Install (or remove) the hub75 ticker as two systemd services that start on boot.
#
#   sudo deploy/install.sh              install / update and (re)start
#   sudo deploy/install.sh --uninstall  stop, disable and remove
#
# Safe to re-run after changing code or config.
set -euo pipefail

HUB=$(cd "$(dirname "$0")/.." && pwd)  # the project folder
RUN_AS=$(stat -c %U "$HUB")             # the fetcher runs as whoever owns it
UNITS=(hub75-fetcher.service hub75-ticker.service)

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo $0 $*" >&2
  exit 1
fi

if [ "${1:-}" = "--uninstall" ]; then
  systemctl disable --now "${UNITS[@]}" 2>/dev/null || true
  for u in "${UNITS[@]}"; do rm -f "/etc/systemd/system/$u"; done
  systemctl daemon-reload
  echo "Removed. The panel is no longer driven; run programs by hand if needed."
  exit 0
fi

echo "== Building (as $RUN_AS)"
sudo -u "$RUN_AS" make -C "$HUB" ticker/ticker calibrate white_screen

echo "== Checking the fetcher can reach tastytrade"
if ! sudo -u "$RUN_AS" python3 "$HUB/fetcher/fetcher.py" --check; then
  echo "fetcher --check failed; fix the FAIL lines above, then re-run this script." >&2
  exit 1
fi

echo "== Installing services"
for u in "${UNITS[@]}"; do
  sed -e "s|@HUB@|$HUB|g" -e "s|@USER@|$RUN_AS|g" "$HUB/deploy/$u" > "/etc/systemd/system/$u"
  chmod 644 "/etc/systemd/system/$u"
done
systemctl daemon-reload
systemctl enable "${UNITS[@]}"
systemctl restart "${UNITS[@]}"
sleep 5
systemctl --no-pager --lines=0 status "${UNITS[@]}" || true

echo
echo "Installed. Both services start on boot and restart if they crash."
echo "Check health any time with: $HUB/status.sh"
