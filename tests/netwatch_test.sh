#!/bin/bash
# Test deploy/netwatch.sh without root, without touching the network, using a
# throwaway state dir, log and a host name that can never resolve.
#
#   bash tests/netwatch_test.sh      prints PASS/FAIL lines; exit 0 if all pass
HUB=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
export NETWATCH_STATE=$tmp/state NETWATCH_LOG=$tmp/log NETWATCH_DRY=1 NETWATCH_HOSTS=nonexistent.invalid
run() { bash "$HUB/deploy/netwatch.sh"; }
fail=0
check() { if grep -q "$2" "$tmp/log"; then echo "PASS  $1"; else echo "FAIL  $1 (wanted: $2)"; fail=1; fi; }

run;                                      check "first failure is noted, no repair yet" "will try to repair"
grep -q "restarting" "$tmp/log" && { echo "FAIL  repaired too early"; fail=1; }
echo $(( $(date +%s) - 700 )) > "$tmp/state/since"
run;                                      check "repairs after 10 min broken" "restarting tailscaled.*(dry run)"
n1=$(grep -c restarting "$tmp/log"); run
[ "$(grep -c restarting "$tmp/log")" = "$n1" ] && echo "PASS  does not repair again straight away" || { echo "FAIL  repaired twice in a row"; fail=1; }
NETWATCH_HOSTS=localhost run;             check "recovery is logged" "resolve again"
[ -f "$tmp/state/since" ] && { echo "FAIL  state not cleared"; fail=1; } || echo "PASS  state cleared"
exit $fail
