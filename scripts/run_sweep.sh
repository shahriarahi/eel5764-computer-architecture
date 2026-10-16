#!/bin/bash
# Run LLC split configurations, each as a fresh gem5 process, into
# results/<split>/. Run inside WSL2 from anywhere:
#   bash scripts/run_sweep.sh                 # all nine configurations
#   bash scripts/run_sweep.sh UNPARTITIONED 8-8
# Every run uses the same binaries (workloads/randacc, workloads/stream),
# which have fixed seeds, so inputs are identical across configurations.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GEM5="${GEM5:-$HOME/eel5764/gem5/build/RISCV/gem5.opt}"
ALL=(UNPARTITIONED 1-15 2-14 3-13 4-12 5-11 6-10 7-9 8-8)
SPLITS=("${@:-${ALL[@]}}")

cd "$ROOT"
[ -x "$GEM5" ] || { echo "error: gem5 binary not found: $GEM5" >&2; exit 1; }
for b in workloads/randacc workloads/stream; do
  [ -f "$b" ] || { echo "error: missing $b (run workloads/build.sh)" >&2; exit 1; }
done

for name in "${SPLITS[@]}"; do
  case "$name" in
    UNPARTITIONED) arg=off ;;
    *) arg="$name" ;;
  esac
  out="results/$name"
  rm -rf "$out"
  mkdir -p "$out"
  cmd=("$GEM5" -r -e -d "$out" configs/run.py --split "$arg")
  printf '%q ' "${cmd[@]}" > "$out/cmd.txt"; echo >> "$out/cmd.txt"
  sha256sum workloads/randacc workloads/stream > "$out/workload_sha256.txt"
  echo "== $name"
  if ! "${cmd[@]}"; then
    echo "error: gem5 failed for $name; see $out/simerr.txt" >&2
    tail -5 "$out/simerr.txt" >&2 || true
    exit 1
  fi
  for f in stats.txt run_meta.json config.ini simout.txt; do
    [ -s "$out/$f" ] || { echo "error: $out/$f missing or empty" >&2; exit 1; }
  done
  grep -q "^OK split=" "$out/simout.txt" \
    || { echo "error: $out/simout.txt lacks the OK line" >&2; exit 1; }
  grep -m1 "^OK split=" "$out/simout.txt"
done
