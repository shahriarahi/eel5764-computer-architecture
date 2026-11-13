#!/bin/bash
# run_batch.sh -- run the gem5 runs listed in a batch file, a few in parallel.
# Simulator only.  Run inside WSL2 Ubuntu-26.04 from experiments/aes-leakage.
#
#   usage: run_batch.sh BATCHFILE [JOBS]
#     BATCHFILE  one run per line: the arguments of run_arm.sh
#                (NAME VARIANT BUILD SPLIT WAYS SEED [MODE]); '#' starts a comment
#     JOBS       runs in parallel (default 4; gem5 is single-threaded and one
#                run needs about 0.7 GiB)
#   env: DRY_RUN=1 runs only the pre-flight checks and prints every command.
#
# Every run is pre-flight checked BEFORE anything starts; one failing check
# aborts the whole batch with nothing run.  Per run it writes
# runs/NAME.launch.log; the summary is runs/<batch>.batch.log.
# Exit status: 0 if every run exited 0 with `monitor status=PASS` and without an
# `error=` line; 1 otherwise; 3 if the pre-flight failed.
set -u
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then sed -n '2,17p' "$0"; exit 3; fi
HERE=$(cd "$(dirname "$0")" && pwd)
FILE=$1; JOBS=${2:-4}
[ -f "$FILE" ] || { echo "run_batch.sh: no such batch file: $FILE" >&2; exit 3; }
BATCH=$(basename "$FILE" .txt)
SUMMARY="$HERE/runs/$BATCH.batch.log"
mapfile -t LINES < <(grep -v '^[[:space:]]*#' "$FILE" | grep -v '^[[:space:]]*$')
[ "${#LINES[@]}" -ge 1 ] || { echo "run_batch.sh: $FILE lists no run" >&2; exit 3; }

echo "pre-flight: ${#LINES[@]} run(s) from $FILE"
for line in "${LINES[@]}"; do
    # shellcheck disable=SC2086
    if ! DRY_RUN=1 bash "$HERE/run_arm.sh" $line; then
        echo "run_batch.sh: pre-flight FAILED for: $line (nothing was run)" >&2
        exit 3
    fi
done
NAMES=$(for line in "${LINES[@]}"; do echo "${line%% *}"; done | sort | uniq -d)
[ -z "$NAMES" ] || { echo "run_batch.sh: duplicate run name(s): $NAMES" >&2; exit 3; }
if [ "${DRY_RUN:-0}" = 1 ]; then echo "DRY RUN: pre-flight passed, nothing was run"; exit 0; fi
[ -e "$SUMMARY" ] && { echo "run_batch.sh: $SUMMARY exists; this batch already ran" >&2; exit 3; }

STARTED=$(date '+%F %T')
echo "batch $BATCH started $STARTED, $JOBS in parallel"
# Each parallel job writes only its OWN launch log.  The summary is assembled
# afterwards by this one process: parallel appends to a single file lose lines
# on the Windows-mounted file system.
one() {
    local line=$1 name=${1%% *} start end status
    start=$(date +%s)
    # shellcheck disable=SC2086
    bash "$HERE/run_arm.sh" $line > "$HERE/runs/$name.launch.log" 2>&1
    status=$?
    end=$(date +%s)
    echo "run_batch: $name gem5_exit=$status seconds=$((end - start))" >> "$HERE/runs/$name.launch.log"
}
for line in "${LINES[@]}"; do
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do wait -n; done
    one "$line" &
done
wait
{
    echo "batch $BATCH started $STARTED, $JOBS in parallel"
    for line in "${LINES[@]}"; do
        name=${line%% *}
        sim="$HERE/runs/$name/simout.txt"
        last=$(grep '^run_batch: ' "$HERE/runs/$name.launch.log" 2>/dev/null | tail -1)
        verdict=OK
        case "$last" in *" gem5_exit=0 "*) ;; *) verdict=FAIL ;; esac
        grep -q '^monitor status=PASS' "$sim" 2>/dev/null || verdict=FAIL
        grep -q -E '^(victim|monitor) error=' "$sim" 2>/dev/null && verdict=FAIL
        echo "${last#run_batch: } $verdict $(grep -E -m1 '^(victim|monitor) error=' "$sim" 2>/dev/null)"
    done
    echo "batch $BATCH finished $(date '+%F %T')"
} > "$SUMMARY"
cat "$SUMMARY"
if grep -q ' FAIL' "$SUMMARY"; then echo "BATCH RESULT: FAIL"; exit 1; fi
echo "BATCH RESULT: PASS"
