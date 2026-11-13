#!/bin/bash
# V07 -- host capacity for parallel gem5 runs, and the experiment's test suite.
# Read-only.  Run inside WSL:  bash v07_host_and_tests.sh
set -u
ROOT="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
EXP="$ROOT/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage"

echo "== host"
echo "   cores: $(nproc)"
free -m | awk 'NR==2 {printf "   memory: total %d MiB, available %d MiB\n", $2, $7}'
echo "== memory of one gem5 run (P1, stats.txt hostMemory; gem5 reports KiB)"
grep -m1 '^hostMemory' "$EXP/runs/p1-r1-scrub-n2000/stats.txt" | awk '{printf "   hostMemory %d KiB = %.2f GiB per run\n", $2, $2/1048576}'
grep -m1 '^hostSeconds' "$EXP/runs/p1-r1-scrub-n2000/stats.txt" | awk '{printf "   hostSeconds %s for the measurement block of N = 2000\n", $2}'
AVAIL=$(free -m | awk 'NR==2 {print $7}')
echo "   => 4 parallel runs need about $(awk -v k=$(grep -m1 '^hostMemory' "$EXP/runs/p1-r1-scrub-n2000/stats.txt" | awk '{print $2}') 'BEGIN {printf "%.1f", 4*k/1048576}') GiB of $(awk -v a=$AVAIL 'BEGIN {printf "%.1f", a/1024}') GiB available; gem5 is single-threaded, so 4 of $(nproc) cores"
echo "   (the paper's defense sweep ran 6 jobs in parallel on this host: experiments/respq-defense-20261018/run_sweep.py, --jobs default 6)"

echo "== test suite (python3 -B -m unittest discover -s tests -t .)"
cd "$EXP" && python3 -B -m unittest discover -s tests -t . 2>&1 | tail -4
