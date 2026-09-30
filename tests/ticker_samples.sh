#!/bin/bash
HUB=$(cd "$(dirname "$0")/.." && pwd)  # the project folder
# Smoke test: run the ticker briefly against every sample display file and a
# missing file; each run must exit cleanly on SIGINT (exit status 0).
cd "$HUB"
fail=0
for s in ticker/samples/*.txt; do
  timeout --preserve-status -s INT 3 ./ticker/ticker --display="$s" --stale-after=0 >/dev/null 2>&1
  rc=$?
  echo "$(basename "$s"): exit $rc"
  [ $rc -eq 0 ] || fail=1
done
out=$(timeout --preserve-status -s INT 3 ./ticker/ticker --display=/nonexistent.txt 2>&1)
rc=$?
echo "missing file: exit $rc; $(echo "$out" | grep -m1 "can't read")"
[ $rc -eq 0 ] || fail=1
exit $fail
