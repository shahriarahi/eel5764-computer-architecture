# Workloads

Small, freestanding RISC-V programs that run inside gem5 (SE mode) only.
They put controlled, reproducible pressure on the shared LLC for the capacity
study and the separate, defensive contention-control experiment. None of the
programs inspects another process's memory or performs key inference.

| Binary | Core | What it does |
|---|---|---|
| `randacc` | 0 | Uniform random loads over a 128 KiB working set (2048 lines of 64 B). The line index comes from a 64-bit LCG with fixed seed `12345`, so every run issues the identical address sequence. Its LLC hit rate grows with the LLC capacity it is allowed to use. |
| `stream` | 1 | One load per 64-byte line, sweeping a 1 MiB buffer (4x the LLC) over and over. Almost no reuse; it continuously inserts new blocks into the LLC. |
| `chase` | pilot only | Pointer chase over a fixed random cycle. Kept because the first pilot (see `results/pilot/`) used it; it was replaced by `randacc` because a fixed cyclic order under LRU gives an all-or-nothing hit rate. |
| `monitor` | 0, contention control | Takes a required depth argument from 1 through 16, primes and probes exactly that many lines in each of the 256 LLC sets, measures elapsed `rdcycle` values, and buffers the records until measurement is over. |
| `victim` | 1, contention control | Educational AES-128 using four conventional 1 KiB T-tables, a fixed public key, deterministic public plaintexts selected by a required public seed argument, and a fixed public active/idle schedule. |
| `monitor_l1d4k`, `victim_l1d4k` | redesigned contention control | The same sources and public inputs, compiled with two-million-cycle intervals so a full 256-set probe completes with the symmetric 4 KiB L1D profile. |

Both measured workloads loop forever. `configs/run.py` decides how long they
run: a 1 ms warm-up, a stats reset, then a 4 ms measurement window. Running
for a fixed window rather than to completion keeps both cores active for the
entire measured interval.

## Output format

Each program prints a single header line to stdout at start-up, which gem5
captures in `results/<split>/simout.txt`:

```
randacc ws_bytes=131072 lines=2048 seed=12345
stream buf_bytes=1048576 lines=16384
```

Capacity-study measurements come from gem5 statistics (`stats.txt`). The
contention experiment additionally obtains simulated cycle measurements from
`monitor`. Each monitor record is:

```
probe,<timestamp_cycles>,<interval>,<label>,<llc_set>,<latency_cycles>
```

The monitor is launched as `monitor <ways>`, and the victim is launched as
`victim <decimal-seed>`. A partitioned run requires the monitor depth to equal
its LLC allocation. Each corrected partitioned run is paired with an
unpartitioned control using the identical depth, victim seed, and binaries.

`label=1` means AES-active and `label=0` means AES-idle. The monitor emits one
record for every combination of 64 intervals and 256 LLC sets. Records remain
in memory during measurement and are written afterward, so output syscalls do
not enter the measured latency, IPC, or miss rate.

The shared schedule is in `contention_common.h`: measurement begins at CPU
cycle 2,000,000 (1 ms at 2 GHz). The original binaries use 1,000,000-cycle
intervals; the separately named 4 KiB-profile binaries use 2,000,000-cycle
intervals. The fixed non-alternating sequence contains 32 active and 32 idle
intervals. Both workloads derive the interval from absolute `rdcycle`; they
do not share memory.

## Reproducing the inputs

- `randacc`'s sequence is fully determined by `WS_BYTES` (default 128 KiB) and
  `SEED` (default 12345), both compile-time constants in `randacc.c`.
  Override them with `-DWS_BYTES=... -DSEED=...`.
- `stream` has no random input: it always sweeps its buffer in order.
- Every result directory records the SHA-256 of both binaries in
  `workload_sha256.txt`, so you can confirm that all configurations ran the
  same programs.
- The contention victim uses public AES-128 key
  `000102030405060708090a0b0c0d0e0f`. The corrected repeated study predeclares
  three public plaintext LCG seeds: `0x5764a5e5`, `0x5764a5e6`, and
  `0x5764a5e7`. The decimal form is passed on the victim command line and is
  recorded in both `run_meta.json` and `analysis.json`.
- The victim checks the public FIPS-197 known-answer vector at startup and
  prints `aes_self_test=PASS` before measurement.

## Building

Run inside WSL2 (Ubuntu 26.04, `riscv64-linux-gnu-gcc` 15.2):

```bash
sh workloads/build.sh
```

The flags are `-O2 -march=rv64gc -mabi=lp64d -static -nostdlib -ffreestanding
-fno-builtin -fno-tree-loop-distribute-patterns -Wl,--no-relax`. Why they are
unusual:

- **No libc.** Ubuntu 26.04's static glibc is built for RVA23 and uses vector
  fault-only-first loads (`vle8ff.v`). gem5 v25.1's `TimingSimpleCPU` panics
  on these instead of trimming `vl` when they touch unmapped memory. A tiny
  syscall wrapper in `common.h` handles `write` and `exit`.
- **`-march=rv64gc`.** No vector instructions anywhere in the binaries.
- **`--no-relax`.** Without the C runtime nothing initialises `gp`, so the
  linker must not turn accesses into `gp`-relative ones.
- **`rw_segment_anchor` in `common.h`.** gem5's ELF loader panics on an
  all-`.bss` data segment whose file offset lies past the end of the file, so
  each binary carries one initialised word.

## Safety boundary

These programs run only inside the gem5 simulator on the author's machine.
They are not intended for, or tested on, physical hardware. The monitor times
only its own buffer and compares those measurements with public activity
labels; it does not infer, rank, or guess key bytes. The conventional 4 KiB
T-table footprint is not artificially evicted. The original control uses a
16 KiB private L1D; the redesigned control uses symmetric 4 KiB private L1D
caches so ordinary capacity pressure exposes the table activity to the shared
LLC. Measured latency can also include contention in shared LLC queues, ports,
MSHRs, and interconnects, so it is not a pure eviction measurement.
