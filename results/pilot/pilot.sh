#!/bin/bash
# Pilot: chase working-set size x {off, 2-14, 8-8, 14-2}; full-length window.
set -eu
P="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
G=~/eel5764/gem5/build/RISCV/gem5.opt
OUT=~/eel5764/pilot
CFLAGS="-O2 -march=rv64gc -mabi=lp64d -static -nostdlib -ffreestanding \
-fno-builtin -fno-tree-loop-distribute-patterns -Wall -Wextra -Wl,--no-relax"
rm -rf "$OUT"; mkdir -p "$OUT/bin"
for ws in 96 160 192 224; do
  riscv64-linux-gnu-gcc $CFLAGS -DWS_BYTES="($ws*1024)" \
    -o "$OUT/bin/chase_$ws" "$P/workloads/chase.c"
done
cd "$P"
printf "%-5s %-6s %9s %9s %9s %9s %6s %6s %5s\n" WS split ipc0 ipc1 llcmr0 llcmr1 unmap confl secs
for ws in 96 160 192 224; do
  for split in off 2-14 8-8 14-2; do
    d="$OUT/ws${ws}_$split"
    s=$(date +%s.%N)
    $G -q -d "$d" configs/run.py --split "$split" \
      --workloads "$OUT/bin/chase_$ws,workloads/stream" > "$d.log" 2>&1 \
      || { echo "FAILED ws=$ws split=$split (see $d.log)"; exit 1; }
    e=$(date +%s.%N)
    S="$d/stats.txt"
    v() { awk -v k="$1" '$1==k{print $2}' "$S"; }
    printf "%-5s %-6s %9s %9s %9s %9s %6s %6s %5.1f\n" "$ws" "$split" \
      "$(v system.cpu0.ipc)" "$(v system.cpu1.ipc)" \
      "$(v system.llc.demandMissRate::cpu0.data)" \
      "$(v system.llc.demandMissRate::cpu1.data)" \
      "$(v system.llc.partitioning_manager.unmappedLookups)" \
      "$(v system.llc.partitioning_manager.addrPartitionConflicts)" \
      "$(awk -v a="$s" -v b="$e" 'BEGIN{print b-a}')"
  done
done
