#!/bin/bash
# V09 -- (a) the overlap schedule builds with -D overrides only (no source
# change) and its manifest is accepted by the adapter's own loader;
# (b) the analysis accepts a run directory with the overlap schedule;
# (c) syntax of the commands used in EXECUTION_PLAN.md, without running gem5.
# Writes only under postdoc-review/verify/_tmp.  Run inside WSL.
set -u
export PYTHONDONTWRITEBYTECODE=1
ROOT="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
EXP="$ROOT/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage"
TMP="$ROOT/postdoc-review/verify/_tmp"
rm -rf "$TMP/ovl-n20" "$TMP/synth-ovl"; mkdir -p "$TMP"

echo "== (a) overlap build: EXTRA_DEFS='-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL' sh build.sh 20 <tmp>"
EXTRA_DEFS="-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL" sh "$EXP/build.sh" 20 "$TMP/ovl-n20" >"$TMP/ovl-build.log" 2>&1
echo "   build.sh exit status: $?"
ls "$TMP/ovl-n20" | tr '\n' ' '; echo
python3 -B - "$EXP" "$TMP/ovl-n20" <<'EOF'
import json, sys
from pathlib import Path
exp, out = Path(sys.argv[1]), Path(sys.argv[2])
m = json.loads((out / "build_manifest.json").read_text())
print("   manifest defines:", m["defines"])
print("   manifest schedule:", {k: m["schedule"][k] for k in
      ("OFF_PRIME", "OFF_ENC", "OFF_ENC_END", "OFF_PROBE", "W")})
assert m["schedule"]["OFF_PROBE"] == 520192 < m["schedule"]["OFF_ENC"]
sys.path.insert(0, str(exp))
import importlib.util
spec = importlib.util.spec_from_file_location("rl", str(exp / "run_leakage.py"))
rl = importlib.util.module_from_spec(spec); spec.loader.exec_module(rl)
man = rl.load_manifest(out)
print("   run_leakage.load_manifest accepts the overlap build: n_win", man["n_win"])
ref = json.loads((exp / "build" / "n20" / "build_manifest.json").read_text())
same = [b for b in m["binaries"] if m["binaries"][b]["sha256"] == ref["binaries"][b]["sha256"]]
print("   binaries identical to build/n20 (unaffected by the offsets):", same)
print("   binaries that differ:", sorted(set(m["binaries"]) - set(same)))
EOF
echo "   without -DLEAK_ALLOW_OVERLAP the same offsets must be refused by the header's static assert:"
EXTRA_DEFS="-DLEAK_OFF_PROBE=520192UL" sh "$EXP/build.sh" 20 "$TMP/ovl-bad" >"$TMP/ovl-bad.log" 2>&1
echo "   build.sh exit status: $? ($(grep -c 'encryption must finish before the probe starts' "$TMP/ovl-bad.log") static-assert messages)"
rm -rf "$TMP/ovl-bad"

echo "== (b) the analysis reads a run directory with the overlap schedule (synthetic)"
python3 -B - "$EXP" "$TMP/synth-ovl" <<'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "analysis"))
import aes_leak_analysis as A
A.synth_run(sys.argv[2], n=300, rounds1=False, schedule={"OFF_PROBE": 520192})
res = A.analyze_run_dir(sys.argv[2])
print("   run checks all passed:", res["run_checks"]["all_passed"],
      "| trace fills in AES phase:", res["ground_truth"]["fills_in_aes_phase"],
      "| outside:", res["ground_truth"]["fills_outside_aes_phase"])
EOF

echo "== (c) command syntax (no gem5)"
cd "$EXP"
python3 -B run_leakage.py --help >/dev/null 2>&1; echo "   run_leakage.py --help exit $?"
python3 -B analysis/aes_leak_analysis.py analyze --help >/dev/null 2>&1; echo "   aes_leak_analysis.py analyze --help exit $?"
python3 -B analysis/aes_leak_analysis.py synth --help >/dev/null 2>&1; echo "   aes_leak_analysis.py synth --help exit $?"
python3 -B analysis/power_synth.py --help >/dev/null 2>&1; echo "   power_synth.py --help exit $?"
sh -n build.sh; echo "   sh -n build.sh exit $?"
bash -n gem5_syntax_check.sh; echo "   bash -n gem5_syntax_check.sh exit $?"
for g in gem5-leak gem5-respq; do
  test -x ~/eel5764/$g/build/RISCV/gem5.opt; echo "   ~/eel5764/$g/build/RISCV/gem5.opt exists and is executable: exit $? (the binary is NOT executed here)"
done
python3 -B preserve.py --help >/dev/null 2>&1; echo "   preserve.py --help exit $? (capture/verify need Windows git; see the plan)"
