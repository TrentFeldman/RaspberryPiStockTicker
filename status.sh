#!/bin/bash
# One-screen health report for the hub75 ticker. Usage: ./status.sh [log lines]
# The account value is masked; see ticker/display.txt for the real one.
HUB=$(cd "$(dirname "$0")" && pwd)
N=${1:-15}

echo "== Services"
for u in hub75-fetcher hub75-ticker; do
  printf '  %-14s %s (since %s)\n' "$u" "$(systemctl is-active $u)" \
    "$(systemctl show -p ActiveEnterTimestamp --value $u | cut -d' ' -f2-3)"
done

echo "== Display file"
f=$HUB/ticker/display.txt
if [ -f "$f" ]; then
  updated=$(awk '$1=="updated"{print $2}' "$f")
  age=$(( $(date +%s) - ${updated:-0} ))
  echo "  last data: $(date -d @"${updated:-0}" '+%a %H:%M:%S') (${age}s ago)"
  grep -E '^(mode|brightness|status)' "$f" | sed 's/^/  /'
  grep -q '^test' "$f" && echo "  TEST MODE: pretending it's $(awk '$1=="test"{$1="";print}' "$f") (turn off: $HUB/pretend.sh off)"
  echo "  quotes: $(grep -c '^quote' "$f")$(grep -q '^account' "$f" && echo ', account: shown')"
else
  echo "  missing: $f"
fi

echo "== Power"
t=$(vcgencmd get_throttled | cut -d= -f2)
case $t in
  0x0) echo "  ok ($t)";;
  *) echo "  $t  (bit0/0x1=under-voltage now, 0x10000=under-voltage since boot)";;
esac

echo "== Last $N fetcher log lines ($HUB/logs/fetcher.log)"
tail -n "$N" $HUB/logs/fetcher.log 2>/dev/null | sed 's/^/  /'

echo "== Ticker errors (journal, last 24h)"
journalctl -u hub75-ticker --since -24h --no-pager -p warning -q 2>/dev/null | tail -n 5 | sed 's/^/  /'
