#!/bin/bash
# Pre-build check for the gem5 tracing extension (Phase B, step 0).
#
# Runs `g++ -fsyntax-only` on requestor_partition_manager.cc against the real
# gem5 v25.1.0.1 headers.  It is NOT a gem5 build: nothing is linked or run,
# and the gem5 tree is only read.  Two compiles:
#   CONTROL  the frozen ../../gem5_ext with its real generated headers --
#            proves the flags and include paths are sound;
#   PATCHED  this directory's gem5_ext copy, with hand-made stand-ins for the
#            two generated headers that depend on the new parameters
#            (params/RequestorPartitionManager.hh gains victim_* fields and
#            debug/VictimTable.hh is added).  The stand-ins are derived from
#            the real generated files by text substitution.
#
#   usage: gem5_syntax_check.sh            (GEM5_TREE defaults to ~/eel5764/gem5)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
GEM5=${GEM5_TREE:-$HOME/eel5764/gem5}
BUILD=$GEM5/build/RISCV
[ -d "$BUILD/params" ] || { echo "no built gem5 tree at $GEM5 (set GEM5_TREE)" >&2; exit 2; }

# The repository path contains spaces; compile through a space-free symlink.
LINK=$(mktemp -u /tmp/aesleak-src.XXXXXX)
WORK=$(mktemp -d /tmp/aesleak-syn.XXXXXX)
trap 'rm -rf "$WORK" "$LINK"' EXIT
ln -s "$REPO" "$LINK"

EXT=$(dirname "$(dirname "$(find "$GEM5/ext" -name magic_enum.hh | head -1)")")
mkdir -p "$WORK/params" "$WORK/debug"
python3 - "$BUILD/params/RequestorPartitionManager.hh" \
          "$WORK/params/RequestorPartitionManager.hh" <<'PY'
import sys
text = open(sys.argv[1]).read()
needle = "    std::string tags_path;\n"
assert needle in text, "generated params header has an unexpected layout"
text = text.replace(needle, needle +
    "    std::string victim_requestor_name;\n"
    "    Addr victim_vaddr_base;\n"
    "    Addr victim_vaddr_size;\n"
    "    unsigned victim_set_count;\n")
open(sys.argv[2], "w").write(text)
PY
sed 's/RequestorPartition/VictimTable/g;
     s/Requestor-to-partition mapping decisions/LLC fills of the traced victim table range/' \
    "$BUILD/debug/RequestorPartition.hh" > "$WORK/debug/VictimTable.hh"

FLAGS="-std=c++20 -fsyntax-only -Wall -Wno-unused-parameter -DTRACING_ON=1 -DUSE_RISCV_ISA"
INC="-I $BUILD -I $GEM5/src -I $EXT -I $GEM5/ext/pybind11/include"

# Diagnostics from gem5's own headers (-Wsign-compare) are expected; only
# errors, or any diagnostic located in the extension itself, fail the check.
check() {
    label=$1; log=$2; status=$3
    errors=$(grep -c 'error' "$log")
    own=$(grep -cE '/gem5_ext/requestor_partition_manager\.(cc|hh):[0-9]+:[0-9]+: (warning|error)' "$log")
    echo "$label: g++ exit=$status  error lines=$errors  diagnostics in extension=$own"
    [ "$status" -eq 0 ] && [ "$errors" -eq 0 ] && [ "$own" -eq 0 ]
}

g++ $FLAGS -I "$LINK" $INC "$LINK/gem5_ext/requestor_partition_manager.cc" \
    > "$WORK/control.log" 2>&1
check "CONTROL (frozen original, real generated headers)" "$WORK/control.log" $? || fail=1

g++ $FLAGS -I "$WORK" -I "$LINK/experiments/aes-leakage" $INC \
    "$LINK/experiments/aes-leakage/gem5_ext/requestor_partition_manager.cc" \
    > "$WORK/patched.log" 2>&1
check "PATCHED (experiment copy, stand-in generated headers)" "$WORK/patched.log" $? || fail=1

if [ "${fail:-0}" -ne 0 ]; then
    grep -E 'error' "$WORK/patched.log" "$WORK/control.log" | head -10
    echo "syntax check FAIL"
    exit 1
fi
echo "syntax check PASS"
