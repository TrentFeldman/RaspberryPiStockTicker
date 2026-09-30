#!/bin/bash
# Log the Pi's supply status once a second while the whole panel shows white
# (the heaviest load). Stop the ticker first: only one program can drive the panel.
#   sudo systemctl stop hub75-ticker && bash powercheck.sh; sudo systemctl start hub75-ticker
echo "before: $(vcgencmd get_throttled)"
timeout -s INT 10 "$(dirname "$0")/white_screen" >/dev/null &
for i in $(seq 1 10); do
  sleep 1
  echo "t=${i}s $(vcgencmd get_throttled) core=$(vcgencmd measure_volts core | cut -d= -f2)"
done
wait
echo "--- kernel log:"
dmesg 2>/dev/null | grep -i -E 'voltage|throttl' | tail -5 || echo "(dmesg needs sudo)"
