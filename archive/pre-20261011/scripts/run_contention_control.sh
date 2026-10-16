#!/bin/bash
# Run one predeclared contention configuration. A failed run is preserved
# beside its intended result; an existing successful result is never deleted
# or replaced.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GEM5="${GEM5:-$HOME/eel5764/gem5/build/RISCV/gem5.opt}"
MODE="${1:-baseline}"
SPLIT_NAME="${2:-UNPARTITIONED}"
MONITOR_WAYS="${3:-}"
WORKLOAD_SEED="${4:-1466213861}"
case "$SPLIT_NAME" in
    UNPARTITIONED) SPLIT_ARG=off ;;
    1-15|2-14|3-13|4-12|5-11|6-10|7-9|8-8) SPLIT_ARG="$SPLIT_NAME" ;;
    *)
        echo "error: split must be UNPARTITIONED or one of 1-15 through 8-8" >&2
        exit 1
        ;;
esac
if [ -z "$MONITOR_WAYS" ]; then
    if [ "$SPLIT_NAME" = UNPARTITIONED ]; then
        MONITOR_WAYS=16
    else
        MONITOR_WAYS="${SPLIT_NAME%%-*}"
    fi
fi
case "$MONITOR_WAYS" in
    ''|*[!0-9]*) echo "error: monitor ways must be an integer from 1 through 16" >&2; exit 1 ;;
esac
[ "$MONITOR_WAYS" -ge 1 ] && [ "$MONITOR_WAYS" -le 16 ] || {
    echo "error: monitor ways must be an integer from 1 through 16" >&2
    exit 1
}
if [ "$SPLIT_NAME" != UNPARTITIONED ]; then
    ALLOCATED_WAYS="${SPLIT_NAME%%-*}"
    [ "$MONITOR_WAYS" -eq "$ALLOCATED_WAYS" ] || {
        echo "error: monitor ways ($MONITOR_WAYS) must equal the monitor allocation ($ALLOCATED_WAYS)" >&2
        exit 1
    }
fi
case "$WORKLOAD_SEED" in
    ''|*[!0-9]*) echo "error: workload seed must be a positive decimal integer" >&2; exit 1 ;;
esac
[ "$WORKLOAD_SEED" -gt 0 ] || {
    echo "error: workload seed must be a positive decimal integer" >&2
    exit 1
}
case "$MODE" in
    baseline)
        RESULT_NAME=contention
        L1D_SIZE=16KiB
        WORKLOADS=(workloads/monitor workloads/victim)
        ;;
    l1d4k)
        RESULT_NAME=contention-l1d4k
        L1D_SIZE=4KiB
        WORKLOADS=(workloads/monitor_l1d4k workloads/victim_l1d4k)
        ;;
    *)
        echo "error: mode must be 'baseline' or 'l1d4k'" >&2
        exit 1
        ;;
esac
PARENT="${RESULT_ROOT:-$ROOT/results/$RESULT_NAME}"
if [ "$SPLIT_NAME" = UNPARTITIONED ] && [ -n "${RESULT_ROOT:-}" ]; then
    CASE_NAME="UNPARTITIONED-A$MONITOR_WAYS"
else
    CASE_NAME="$SPLIT_NAME"
fi
FINAL="$PARENT/$CASE_NAME"

cd "$ROOT"
[ -x "$GEM5" ] || { echo "error: gem5 binary not found: $GEM5" >&2; exit 1; }
for binary in "${WORKLOADS[@]}"; do
    [ -f "$binary" ] || {
        echo "error: missing $binary (run workloads/build.sh)" >&2
        exit 1
    }
done
[ ! -e "$FINAL" ] || {
    echo "error: refusing to replace existing $FINAL" >&2
    exit 1
}

mkdir -p "$PARENT"
STAGING="$(mktemp -d "$PARENT/.$CASE_NAME.tmp.XXXXXX")"
COMPLETE=0
preserve_failed_run() {
    if [ "$COMPLETE" -eq 0 ] && [ -d "$STAGING" ]; then
        FAILED="$PARENT/$CASE_NAME.failed.$(date +%Y%m%dT%H%M%S)"
        mv "$STAGING" "$FAILED"
        echo "preserved failed run at $FAILED" >&2
    fi
}
trap preserve_failed_run EXIT

COMMAND=("$GEM5" -r -e -d "$STAGING" configs/run_contention.py \
    --split "$SPLIT_ARG" \
    --l1d-size "$L1D_SIZE" \
    --monitor-ways "$MONITOR_WAYS" \
    --workload-seed "$WORKLOAD_SEED")
printf '%q ' "${COMMAND[@]}" > "$STAGING/cmd.txt"
echo >> "$STAGING/cmd.txt"
sha256sum "${WORKLOADS[@]}" > "$STAGING/workload_sha256.txt"

echo "== $CASE_NAME contention mode=$MODE l1d=$L1D_SIZE monitor_ways=$MONITOR_WAYS"
"${COMMAND[@]}"
for file in stats.txt run_meta.json config.ini config.json simout.txt simerr.txt; do
    [ -s "$STAGING/$file" ] || {
        echo "error: $STAGING/$file missing or empty" >&2
        exit 1
    }
done
grep -q '^victim aes_self_test=PASS ' "$STAGING/simout.txt" || {
    echo "error: victim AES self-test marker missing" >&2
    exit 1
}
grep -q '^monitor status=PASS records=16384$' "$STAGING/simout.txt" || {
    echo "error: monitor completion marker missing" >&2
    exit 1
}
grep -q "^OK contention split=$SPLIT_ARG " "$STAGING/simout.txt" || {
    echo "error: gem5 completion marker missing" >&2
    exit 1
}
PROBE_COUNT="$(grep -c '^probe,' "$STAGING/simout.txt")"
[ "$PROBE_COUNT" -eq 16384 ] || {
    echo "error: expected 16384 probe records, found $PROBE_COUNT" >&2
    exit 1
}
STATS_COUNT="$(grep -c '^---------- Begin Simulation Statistics ----------' \
    "$STAGING/stats.txt")"
[ "$STATS_COUNT" -eq 2 ] || {
    echo "error: expected measurement and automatic final stats blocks, found $STATS_COUNT" >&2
    exit 1
}

mv "$STAGING" "$FINAL"
COMPLETE=1
trap - EXIT
echo "OK control artifacts=$FINAL probe_records=$PROBE_COUNT stats_blocks=$STATS_COUNT"
