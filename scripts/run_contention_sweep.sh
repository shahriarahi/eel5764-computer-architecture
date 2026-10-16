#!/bin/bash
# Run the frozen 4 KiB monitor/AES method as a fresh gem5 process per split.
# Existing completed results are never replaced.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ALL=(UNPARTITIONED 1-15 2-14 3-13 4-12 5-11 6-10 7-9 8-8)
if [ "$#" -eq 0 ]; then
    SPLITS=("${ALL[@]}")
else
    SPLITS=("$@")
fi

declare -A SEEN=()
for split in "${SPLITS[@]}"; do
    case "$split" in
        UNPARTITIONED|1-15|2-14|3-13|4-12|5-11|6-10|7-9|8-8) ;;
        *) echo "error: invalid split: $split" >&2; exit 1 ;;
    esac
    [ -z "${SEEN[$split]:-}" ] || {
        echo "error: duplicate split: $split" >&2
        exit 1
    }
    SEEN[$split]=1
done

cd "$ROOT"
for split in "${SPLITS[@]}"; do
    bash scripts/run_contention_control.sh l1d4k "$split"
    python3 analysis/analyze_contention.py \
        --results "results/contention-l1d4k/$split" --statistic max-set
done
