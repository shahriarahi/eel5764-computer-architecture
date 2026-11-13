#!/bin/bash
# run_arm.sh -- launch ONE gem5 leakage run with fixed, checked arguments.
# Simulator only.  Run inside WSL2 Ubuntu-26.04.
#
#   usage: run_arm.sh NAME VARIANT BUILD SPLIT WAYS SEED [MODE]
#     NAME     new run directory under experiments/aes-leakage/runs/ (must not exist)
#     VARIANT  r1-scrub | full-scrub | full-noscrub | tvla
#     BUILD    directory under experiments/aes-leakage/build/ (n20, n500, n2000, ovl-n2000, ...)
#     SPLIT    off | A-B with A+B = 16 (monitor ways - AES ways)
#     WAYS     monitor depth (16 when SPLIT is off and the monitor fills the LLC;
#              for a partitioned run it must equal A)
#     SEED     1466213861 | 1466213862 | 1466213863 (the three public seeds)
#     MODE     plain    (default) gem5-leak + run_leakage.py: no interconnect defense
#              guard    gem5-leak-def + run_leakage.py: defense binary, defense OFF
#              defense  gem5-leak-def + run_leakage_defense.py --tdma-slot-cycles 4 --respq
#   env: DRY_RUN=1 prints the command and the checks, and runs nothing.
#
# Exit status: gem5's, or 3 if a pre-flight check fails (nothing is run then).
set -u
if [ "$#" -lt 6 ] || [ "$#" -gt 7 ]; then
    sed -n '2,17p' "$0"; exit 3
fi
NAME=$1; VARIANT=$2; BUILD=$3; SPLIT=$4; WAYS=$5; SEED=$6; MODE=${7:-plain}
HERE=$(cd "$(dirname "$0")" && pwd)
WT=$(cd "$HERE/../.." && pwd)
RUN="experiments/aes-leakage/runs/$NAME"
BUILD_DIR="experiments/aes-leakage/build/$BUILD"

fail() { echo "run_arm.sh: $*" >&2; exit 3; }

case "$MODE" in
    plain)   GEM5="$HOME/eel5764/gem5-leak/build/RISCV/gem5.opt"
             CONFIG="experiments/aes-leakage/run_leakage.py"; EXTRA="" ;;
    guard)   GEM5="$HOME/eel5764/gem5-leak-def/build/RISCV/gem5.opt"
             CONFIG="experiments/aes-leakage/run_leakage.py"; EXTRA="" ;;
    defense) GEM5="$HOME/eel5764/gem5-leak-def/build/RISCV/gem5.opt"
             CONFIG="experiments/aes-leakage/run_leakage_defense.py"
             EXTRA="--tdma-slot-cycles 4 --respq" ;;
    *) fail "MODE must be plain, guard or defense (got $MODE)" ;;
esac
case "$VARIANT" in r1-scrub|full-scrub|full-noscrub|tvla) ;; *) fail "unknown VARIANT $VARIANT" ;; esac
case "$SEED" in 1466213861|1466213862|1466213863) ;; *) fail "SEED must be one of the three public seeds" ;; esac
case "$NAME" in *[!a-z0-9-]*|'') fail "NAME may contain only a-z, 0-9 and -" ;; esac
case "$WAYS" in ''|*[!0-9]*) fail "WAYS must be an integer" ;; esac
if [ "$SPLIT" = off ]; then
    [ "$WAYS" -ge 1 ] && [ "$WAYS" -le 16 ] || fail "WAYS must be 1..16"
else
    A=${SPLIT%-*}; B=${SPLIT#*-}
    case "$A$B" in ''|*[!0-9]*) fail "SPLIT must be off or A-B" ;; esac
    [ $((A + B)) -eq 16 ] || fail "SPLIT $SPLIT does not sum to 16"
    [ "$WAYS" -eq "$A" ] || fail "for a partitioned run WAYS ($WAYS) must equal the monitor's share ($A)"
fi
[ -e "$WT/$RUN" ] && fail "$RUN already exists; a run directory name is never reused"
[ -f "$WT/$BUILD_DIR/build_manifest.json" ] || fail "$BUILD_DIR/build_manifest.json is missing (run build.sh)"
[ -f "$WT/$CONFIG" ] || fail "$CONFIG is missing"

CMD=("$GEM5" -r -e --debug-flags=VictimTable --debug-file=victim_table.trace
     -d "$RUN" "$CONFIG")
# shellcheck disable=SC2206
CMD+=($EXTRA)
CMD+=(--victim-variant "$VARIANT" --build-dir "$BUILD_DIR" --split "$SPLIT"
      --monitor-ways "$WAYS" --workload-seed "$SEED")

if [ "${DRY_RUN:-0}" = 1 ]; then
    echo "DRY RUN ($MODE), from $WT:"
    printf '  '; printf '%q ' "${CMD[@]}"; echo
    [ -x "$GEM5" ] && echo "  gem5 binary: present" || echo "  gem5 binary: NOT PRESENT YET ($GEM5)"
    exit 0
fi
[ -x "$GEM5" ] || fail "gem5 binary not found: $GEM5"

cd "$WT" || fail "cannot cd to $WT"
START=$(date +%s)
"${CMD[@]}"
STATUS=$?
END=$(date +%s)
echo "run_arm: $NAME gem5_exit=$STATUS seconds=$((END - START))"
if [ -f "$RUN/simout.txt" ]; then
    grep -E '^(victim|monitor) (error|status|aes_self_test|pt_checksum)' "$RUN/simout.txt" | sed "s/^/run_arm: $NAME /"
fi
exit $STATUS
