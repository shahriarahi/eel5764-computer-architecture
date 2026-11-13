#!/bin/bash
# V10 -- the reference implementations in postdoc-review/reference/ pass their
# tests, the two source fixes apply, and the experiment's own 139 tests still
# pass with everything present.  The experiment directory is NOT modified:
# everything is copied into a mirror under postdoc-review/verify/_tmp/mirror
# and tested there.  Run inside WSL.
set -u
export PYTHONDONTWRITEBYTECODE=1
ROOT="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
WT="$ROOT/.codex-tmp/aes-leakage-worktree"
REF="$ROOT/postdoc-review/reference"
MIR="$ROOT/postdoc-review/verify/_tmp/mirror"
rm -rf "$MIR"; mkdir -p "$MIR/experiments/aes-leakage/runs"
cp -r "$WT/configs" "$WT/workloads" "$WT/gem5_ext" "$MIR/"
cd "$WT/experiments/aes-leakage"
for item in *; do
  case "$item" in runs|__pycache__) ;; *) cp -r "$item" "$MIR/experiments/aes-leakage/";; esac
done
for r in p0b-r1-scrub-n20 p0c-r1-scrub-n20 p1-r1-scrub-n2000; do
  cp -r "runs/$r" "$MIR/experiments/aes-leakage/runs/"
done
E="$MIR/experiments/aes-leakage"
find "$E" -name __pycache__ -type d -prune -exec rm -rf {} +

echo "== step order of EXECUTION_PLAN.md phase 1: tests first (they must FAIL before the fixes)"
cp "$REF/tests/test_fixes.py" "$E/tests/"
cd "$E"
python3 -B -m unittest tests.test_fixes 2>&1 | tail -3
echo "== apply_fixes.py (twice: the second run must report 'already applied')"
python3 -B "$REF/apply_fixes.py" "$E"; echo "   exit $?"
python3 -B "$REF/apply_fixes.py" "$E"; echo "   exit $?"
python3 -B -m unittest tests.test_fixes 2>&1 | tail -3

echo "== new modules and their tests"
cp "$REF/analysis/leak_followup.py" "$E/analysis/"
cp "$REF/run_leakage_defense.py" "$REF/run_arm.sh" "$E/"
cp "$REF/tests/test_leak_followup.py" "$REF/tests/test_run_leakage_defense.py" "$E/tests/"
python3 -B -m unittest tests.test_leak_followup tests.test_run_leakage_defense 2>&1 | tail -3
echo "== whole suite in the mirror (139 existing + 33 new; 2 tests that need the stored paper results are skipped in a mirror)"
python3 -B -m unittest discover -s tests -t . 2>&1 | tail -3

echo "== the tools on the real stored runs (read-only)"
R="$WT/experiments/aes-leakage/runs"
python3 -B analysis/leak_followup.py diff --a "$R/p0b-r1-scrub-n20" --b "$R/p0c-r1-scrub-n20" --allow-same-seed | tail -14
python3 -B analysis/leak_followup.py effect --run-dir "$R/p1-r1-scrub-n2000" --nperm 10000 | tail -22
python3 -B analysis/leak_followup.py count --run-dir "$R/p1-r1-scrub-n2000" --nperm 1000 | tail -22
