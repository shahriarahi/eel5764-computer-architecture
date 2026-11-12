#!/bin/sh
# Build the freestanding RISC-V workloads of the AES leakage experiment
# (run inside WSL2 Ubuntu-26.04, like workloads/build.sh).
#
#   usage: build.sh [N_WIN] [OUT_DIR]
#     N_WIN    windows per run, 1..65535 (default 2000)
#     OUT_DIR  default: experiments/aes-leakage/build/n<N_WIN>
#   env:   EXTRA_DEFS  extra -D flags, e.g. "-DLEAK_FAKE_CLOCK" (qemu tests
#                      only: such a build is refused by run_leakage.py)
#          CC          cross compiler (default riscv64-linux-gnu-gcc)
#
# Flags are those of workloads/build.sh (checked by tests/test_build.py):
#   -nostdlib -ffreestanding : no glibc (its RVV routines crash gem5's
#                              TimingSimpleCPU, see workloads/common.h)
#   -march=rv64gc            : no vector instructions at all
#   -Wl,--no-relax           : no gp-relative accesses
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
N_WIN=${1:-2000}
OUT=${2:-$HERE/build/n$N_WIN}
CC=${CC:-riscv64-linux-gnu-gcc}
EXTRA_DEFS=${EXTRA_DEFS:-}
CFLAGS="-O2 -march=rv64gc -mabi=lp64d -static -nostdlib -ffreestanding \
-fno-builtin -fno-tree-loop-distribute-patterns -Wall -Wextra -Wl,--no-relax"

case "$N_WIN" in
    ''|*[!0-9]*) echo "build.sh: N_WIN must be an integer" >&2; exit 2 ;;
esac
mkdir -p "$OUT"
cd "$HERE"
set -x
# victim_leak_<r1|full>_<scrub|noscrub>: round-1-only or full AES; with or
# without the 8 KiB private-cache walk before each encryption.
$CC $CFLAGS -DN_WIN="$N_WIN" $EXTRA_DEFS -DLEAK_ROUNDS1=1 -DLEAK_SCRUB=1 \
    -o "$OUT/victim_leak_r1_scrub" victim_leak.c aes_leak_ext.c
$CC $CFLAGS -DN_WIN="$N_WIN" $EXTRA_DEFS -DLEAK_ROUNDS1=1 -DLEAK_SCRUB=0 \
    -o "$OUT/victim_leak_r1_noscrub" victim_leak.c aes_leak_ext.c
$CC $CFLAGS -DN_WIN="$N_WIN" $EXTRA_DEFS -DLEAK_ROUNDS1=0 -DLEAK_SCRUB=1 \
    -o "$OUT/victim_leak_full_scrub" victim_leak.c aes_leak_ext.c
$CC $CFLAGS -DN_WIN="$N_WIN" $EXTRA_DEFS -DLEAK_ROUNDS1=0 -DLEAK_SCRUB=0 \
    -o "$OUT/victim_leak_full_noscrub" victim_leak.c aes_leak_ext.c
# TVLA fixed-vs-random: full AES with scrub, even windows use the fixed
# plaintext.
$CC $CFLAGS -DN_WIN="$N_WIN" $EXTRA_DEFS -DLEAK_ROUNDS1=0 -DLEAK_SCRUB=1 \
    -DLEAK_TVLA=1 -o "$OUT/victim_leak_tvla" victim_leak.c aes_leak_ext.c
$CC $CFLAGS -DN_WIN="$N_WIN" $EXTRA_DEFS -o "$OUT/monitor_leak" monitor_leak.c
set +x
python3 "$HERE/write_manifest.py" --out-dir "$OUT" --n-win "$N_WIN" \
    --cc "$CC" -- $EXTRA_DEFS
