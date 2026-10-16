#!/bin/sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="$ROOT/tmp/contention-build-test"
CC=riscv64-linux-gnu-gcc
CFLAGS="-O2 -march=rv64gc -mabi=lp64d -static -nostdlib -ffreestanding \
-fno-builtin -fno-tree-loop-distribute-patterns -Wall -Wextra -Werror \
-Wl,--no-relax"

mkdir -p "$OUT"
$CC $CFLAGS -o "$OUT/victim" \
    "$ROOT/workloads/victim.c" "$ROOT/workloads/aes_ttable.c"
$CC $CFLAGS -o "$OUT/monitor" "$ROOT/workloads/monitor.c"

for binary in victim monitor; do
    readelf -h "$OUT/$binary" | grep -q 'Machine:.*RISC-V'
    test "$(riscv64-linux-gnu-nm -u "$OUT/$binary" | wc -l)" -eq 0
    test "$(riscv64-linux-gnu-objdump -d "$OUT/$binary" | \
        grep -cE '\sv[a-z]+[0-9]*\.[vx]|vsetvl' || true)" -eq 0
    test "$(riscv64-linux-gnu-objdump -d "$OUT/$binary" | \
        grep -c '(gp)' || true)" -eq 0
done

echo "contention workload build PASS"
