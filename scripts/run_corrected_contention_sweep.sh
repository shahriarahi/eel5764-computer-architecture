#!/bin/bash
# Run matched A-line controls and A/(16-A) partitioned treatments.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RESULT_ROOT="${RESULT_ROOT:-$ROOT/results/contention-corrected-20261001-v2}"
export RESULT_ROOT

cd "$ROOT"

# Preserve the proposal's original 16-line unpartitioned positive control.
bash scripts/run_contention_control.sh l1d4k UNPARTITIONED 16
python3 analysis/analyze_contention.py \
    --results "$RESULT_ROOT/UNPARTITIONED-A16" --statistic max-set

for monitor_ways in 1 2 3 4 5 6 7 8; do
    split="$monitor_ways-$((16 - monitor_ways))"
    bash scripts/run_contention_control.sh \
        l1d4k UNPARTITIONED "$monitor_ways"
    python3 analysis/analyze_contention.py \
        --results "$RESULT_ROOT/UNPARTITIONED-A$monitor_ways" \
        --statistic max-set
    python3 -c \
        'import json,sys; r=json.load(open(sys.argv[1])); sys.exit(0 if r["distinguishable"] and r["probe_mapping_validation"] == "PASS congruent" else 1)' \
        "$RESULT_ROOT/UNPARTITIONED-A$monitor_ways/analysis.json"

    bash scripts/run_contention_control.sh l1d4k "$split" "$monitor_ways"
    python3 analysis/analyze_contention.py \
        --results "$RESULT_ROOT/$split" --statistic max-set
done

python3 analysis/summarize_matched_contention.py --results-root "$RESULT_ROOT"
