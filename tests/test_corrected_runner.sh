#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

output="$(RESULT_ROOT=results/unused GEM5=/not/a/gem5 \
    bash scripts/run_contention_control.sh l1d4k 4-12 16 2>&1 || true)"
printf '%s\n' "$output" | grep -q \
    'monitor ways (16) must equal the monitor allocation (4)'

echo "corrected runner validation PASS"
