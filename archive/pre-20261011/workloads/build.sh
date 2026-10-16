#!/bin/sh
# Build the freestanding RISC-V workloads (run inside WSL2 Ubuntu-26.04).
#   -nostdlib -ffreestanding : no glibc (its RVV routines crash gem5's
#                              TimingSimpleCPU, see common.h)
#   -march=rv64gc            : no vector instructions at all
#   -Wl,--no-relax           : no gp-relative accesses (nothing sets gp
#                              without the C runtime's startup code)
set -eu
cd "$(dirname "$0")"
CC=riscv64-linux-gnu-gcc
CFLAGS="-O2 -march=rv64gc -mabi=lp64d -static -nostdlib -ffreestanding \
-fno-builtin -fno-tree-loop-distribute-patterns -Wall -Wextra -Wl,--no-relax"
set -x
$CC $CFLAGS -o chase chase.c
$CC $CFLAGS -o randacc randacc.c
$CC $CFLAGS -o stream stream.c
$CC $CFLAGS -o victim victim.c aes_ttable.c
$CC $CFLAGS -o monitor monitor.c
$CC $CFLAGS -DCONTENTION_EPOCH_CYCLES=2000000UL \
    -o victim_l1d4k victim.c aes_ttable.c
$CC $CFLAGS -DCONTENTION_EPOCH_CYCLES=2000000UL \
    -o monitor_l1d4k monitor.c
