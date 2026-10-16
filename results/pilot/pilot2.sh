#!/bin/bash
# Pilot 2: randacc working-set size x {off, 1-15, 4-12, 8-8}; full window.
# Pre-declared rule: pick the smallest WS where cpu0 IPC differs by >=10%
# between off and 8-8 AND between 1-15 and 8-8 (relative to 8-8).
set -eu
P="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
G=~/eel5764/gem5/build/RISCV/gem5.opt
OUT=~/eel5764/pilot2
CFLAGS="-O2 -march=rv64gc -mabi=lp64d -static -nostdlib -ffreestanding \
-fno-builtin -fno-tree-loop-distribute-patterns -Wall -Wextra -Wl,--no-relax"
rm -rf "$OUT"; mkdir -p "$OUT/bin"
sh "$P/workloads/build.sh" > "$OUT/build.log" 2>&1
for ws in 96 128 192; do
  riscv64-linux-gnu-gcc $CFLAGS -DWS_BYTES="($ws*1024)" \
    -o "$OUT/bin/randacc_$ws" "$P/workloads/randacc.c"
done
cd "$P"
printf "%-4s %-5s %9s %9s %9s %9s %5s %5s\n" WS split ipc0 ipc1 mr0 mr1 unmap confl
for ws in 96 128 192; do
  for split in off 1-15 4-12 8-8; do
    d="$OUT/ws${ws}_$split"
    $G -q -d "$d" configs/run.py --split "$split" \
      --workloads "$OUT/bin/randacc_$ws,workloads/stream" > "$d.log" 2>&1 \
      || { echo "FAILED ws=$ws split=$split (see $d.log)"; exit 1; }
    S="$d/stats.txt"
    v() { awk -v k="$1" '$1==k{print $2; f=1} END{if(!f) print 0}' "$S"; }
    mr() { awk -v m="$(v system.llc.demandMisses::$1)" \
               -v a="$(v system.llc.demandAccesses::$1)" \
               'BEGIN{ if (a>0) printf "%.4f", m/a; else print "n/a" }'; }
    printf "%-4s %-5s %9s %9s %9s %9s %5s %5s\n" "$ws" "$split" \
      "$(v system.cpu0.ipc)" "$(v system.cpu1.ipc)" \
      "$(mr cpu0.data)" "$(mr cpu1.data)" \
      "$(v system.llc.partitioning_manager.unmappedLookups)" \
      "$(v system.llc.partitioning_manager.addrPartitionConflicts)"
  done
done
