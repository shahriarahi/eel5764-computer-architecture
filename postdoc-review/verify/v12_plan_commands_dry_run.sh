#!/bin/bash
# V12 -- every build and run command of EXECUTION_PLAN.md, checked WITHOUT
# running gem5: the builds are really made (in the mirror), every run_arm.sh
# invocation is executed with DRY_RUN=1 (pre-flight checks + printed command),
# and each printed adapter command line is validated by the baseline config's
# own validators.  Needs the mirror made by v10_reference_code_tests.sh.
set -u
export PYTHONDONTWRITEBYTECODE=1
ROOT="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
MIR="$ROOT/postdoc-review/verify/_tmp/mirror"
E="$MIR/experiments/aes-leakage"
[ -f "$E/run_arm.sh" ] || { echo "run v10_reference_code_tests.sh first"; exit 1; }
cp "$ROOT/postdoc-review/reference/run_arm.sh" "$E/"
cd "$E"

echo "== builds named in the plan (made in the mirror only)"
sh build.sh 500 >/dev/null 2>&1; echo "   sh build.sh 500 -> exit $? ($(ls build/n500 | wc -l) files)"
EXTRA_DEFS="-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL" sh build.sh 200 "$E/build/ovl-n200" >/dev/null 2>&1; echo "   overlap build N=200 -> exit $?"
EXTRA_DEFS="-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL" sh build.sh 2000 "$E/build/ovl-n2000" >/dev/null 2>&1; echo "   overlap build N=2000 -> exit $?"
python3 -B - <<'EOF'
import json
for d in ("n500", "ovl-n200", "ovl-n2000"):
    m = json.load(open("build/%s/build_manifest.json" % d))
    print("   build/%-10s n_win %-5d OFF_PROBE %d defines %s" % (
        d, m["n_win"], m["schedule"]["OFF_PROBE"], m["defines"]))
ref = json.load(open("build/n2000/build_manifest.json"))
ovl = json.load(open("build/ovl-n2000/build_manifest.json"))
same = sorted(b for b in ref["binaries"] if ref["binaries"][b]["sha256"] == ovl["binaries"][b]["sha256"])
print("   ovl-n2000 binaries identical to n2000:", same)
EOF

echo "== dry run of every planned run (DRY_RUN=1: nothing is executed)"
N=0; BAD=0
dry() {
  N=$((N + 1))
  if DRY_RUN=1 bash run_arm.sh "$@" > "$MIR/dry.out" 2>&1; then
    grep -v '^DRY RUN' "$MIR/dry.out" | grep -- '--split' | sed 's/^ */   /' | sed "s#$HOME#~#g" | sed "s# --debug-flags=VictimTable --debug-file=victim_table.trace##; s#experiments/aes-leakage/##g" | cut -c1-220
    grep -- '--split' "$MIR/dry.out" >> "$MIR/dry.all"
  else
    BAD=$((BAD + 1)); echo "   PRE-FLIGHT FAILED for: $*"; sed 's/^/     /' "$MIR/dry.out"
  fi
}
: > "$MIR/dry.all"
S1=1466213861; S2=1466213862; S3=1466213863
# Block E1: window (state) schedule
dry e1-p2a-s1-n2000 full-scrub   n2000 off 16 $S1
dry e1-p2b-s1-n2000 full-noscrub n2000 off 16 $S1
for s in 1 2; do eval seed=\$S$s
  dry e1-c8-s$s-n500 full-scrub n500 off 8 $seed
  dry e1-c1-s$s-n500 full-scrub n500 off 1 $seed
done
for s in 1 2 3; do eval seed=\$S$s
  dry e1-w8-s$s-n500 full-scrub n500 8-8 8 $seed
  dry e1-w1-s$s-n500 full-scrub n500 1-15 1 $seed
done
# Block E2: overlap schedule, no interconnect defense
dry e2-pilot-c8-s1-n200 r1-scrub ovl-n200 off 8 $S1
for s in 1 2; do eval seed=\$S$s
  dry e2-oc8-s$s-n2000 r1-scrub ovl-n2000 off 8 $seed
  dry e2-oc1-s$s-n2000 r1-scrub ovl-n2000 off 1 $seed
  dry e2-ow8-s$s-n2000 r1-scrub ovl-n2000 8-8 8 $seed
  dry e2-ow1-s$s-n2000 r1-scrub ovl-n2000 1-15 1 $seed
  dry e2-fw8-s$s-n2000 full-scrub ovl-n2000 8-8 8 $seed
  dry e2-fw1-s$s-n2000 full-scrub ovl-n2000 1-15 1 $seed
done
# Block E3: defense binary
dry p0d-r1-scrub-n20 r1-scrub n20 off 16 $S1 guard
for s in 1 2; do eval seed=\$S$s
  dry e3-od8-s$s-n2000 r1-scrub ovl-n2000 8-8 8 $seed defense
  dry e3-od1-s$s-n2000 r1-scrub ovl-n2000 1-15 1 $seed defense
done
echo "   planned runs: $N, pre-flight failures: $BAD"

echo "== pre-flight refusals (each must exit 3 and run nothing)"
DRY_RUN=1 bash run_arm.sh p1-r1-scrub-n2000 r1-scrub n2000 off 16 $S1 >/dev/null 2>&1; echo "   existing run directory name -> exit $?"
DRY_RUN=1 bash run_arm.sh x-bad-split full-scrub n500 8-7 8 $S1 >/dev/null 2>&1; echo "   split 8-7 -> exit $?"
DRY_RUN=1 bash run_arm.sh x-bad-ways full-scrub n500 8-8 4 $S1 >/dev/null 2>&1; echo "   split 8-8 with 4 monitor ways -> exit $?"
DRY_RUN=1 bash run_arm.sh x-bad-seed full-scrub n500 8-8 8 12345 >/dev/null 2>&1; echo "   unknown seed -> exit $?"
DRY_RUN=1 bash run_arm.sh x-no-build full-scrub n999 8-8 8 $S1 >/dev/null 2>&1; echo "   missing build -> exit $?"

echo "== every printed command line is accepted by the baseline config's validators and names an existing variant and build"
python3 -B - "$MIR" <<'EOF'
import importlib.util, re, sys
from pathlib import Path
mir = Path(sys.argv[1]); exp = mir / "experiments" / "aes-leakage"
sys.path.insert(0, str(exp))
spec = importlib.util.spec_from_file_location("rl", str(exp / "run_leakage.py"))
rl = importlib.util.module_from_spec(spec); spec.loader.exec_module(rl)
baseline = rl.load_baseline(mir)
ok = 0
lengths = {}
for line in (mir / "dry.all").read_text().splitlines():
    variant = re.search(r"--victim-variant (\S+)", line).group(1)
    split = re.search(r"--split (\S+)", line).group(1)
    ways = int(re.search(r"--monitor-ways (\d+)", line).group(1))
    build = re.search(r"--build-dir (\S+)", line).group(1)
    name = re.search(r"-d experiments/aes-leakage/runs/(\S+)", line).group(1)
    assert variant in rl.VARIANTS, line
    baseline.validate_monitor_ways(baseline.parse_split(split), ways)
    rl.load_manifest(mir / build)
    assert "-r -e" in line and "--debug-flags=VictimTable" in line
    lengths.setdefault(re.sub(r"-s[123]-", "-sX-", name), set()).add(len(name))
    ok += 1
assert all(len(v) == 1 for v in lengths.values()), lengths
print("   %d command lines validated; the run names of each seed group have equal length (needed for the differential test)" % ok)
EOF
rm -f "$MIR/dry.out"
