# Beginner-Friendly Project Explanation

At a high level, this project asks:

> Can dividing a shared cache into private sections prevent one program from
> noticing another program's activity?

Everything happens inside the gem5 simulator. Nothing is measured on physical
hardware, and the project does not attempt to recover an AES key.

## The basic idea

Imagine the last-level cache, or LLC, as a bookshelf shared by two people:

- Core 0 runs a cache-contention monitor.
- Core 1 runs an educational AES encryption workload.
- The bookshelf has 16 compartments, called cache ways.

Without protection, both cores use all 16 ways. With way partitioning, the
ways are divided between them: `1/15` gives one way to the monitor and 15 to
AES, while `8/8` divides the cache equally. The experiment asks whether the
monitor can still distinguish when AES is active after this division.

## What the AES workload does

Core 1 runs AES-128 using four 1 KiB lookup tables, called T-tables. Table
lookups create cache activity that is intentionally easy to study.

The key, plaintexts, and labels are all public research inputs. The final
study uses one fixed public key, three deterministic public plaintext seeds,
32 AES-active intervals, and 32 AES-idle intervals. It measures activity only;
it never guesses or recovers key bytes.

## What the monitor does

Core 0 runs a Prime+Probe-style monitor. For each LLC set, it:

1. Accesses its own lines to place them in the cache (prime).
2. Waits while AES is active or idle.
3. Re-accesses those lines (probe).
4. Records the elapsed simulated CPU cycles.

Each process records 64 intervals for each of 256 LLC sets, or 16,384 probe
records. The monitor accesses only its own memory.

## Why the early experiments were not sufficient

The first system used a 16 KiB private L1 data cache. The four AES tables total
only 4 KiB, so most accesses stayed in L1 and the shared LLC saw too little AES
activity. That negative control could not support the partitioning study.

A later pilot used a 4 KiB L1D and exposed a strong AES signal, but its monitor
always walked 16 lines per set. When assigned fewer than 16 ways, its own lines
evicted one another. The resulting constant miss latency could falsely look
like successful isolation. That pilot is preserved but excluded from the final
conclusion.

## The corrected experiment

When testing an `A/(16-A)` split, the corrected monitor walks exactly `A`
lines per set. Every partitioned treatment is paired with an unpartitioned
control that has the same monitor depth, binaries, AES seed and schedule.
This matched control proves that the monitor could detect AES activity before
the way masks were enabled.

The study uses three public plaintext seeds and eight allocations. That gives
24 controls and 24 partitioned treatments. Two extra A=16 controls are
diagnostics only, for a total of 50 fresh gem5 processes.

## The mistake we found, and how we fixed it

Our first version of this study (October 1) concluded that `1/15` already
made AES activity undetectable. **That conclusion was wrong, and we have
withdrawn it.**

The cause was the monitor itself. It saved its 16,384 measurements into a
large 384 KiB array while it was measuring. In a partitioned run, every
cache line the monitor touches must fit into its own few ways. So the
array's writes kept pushing the monitor's own probe lines out of the cache.

About 20–25% of probe walks then contained a slow cache miss of roughly 120
cycles. That had nothing to do with AES; it happened only in partitioned
runs. Those big random delays drowned out a much smaller AES signal, so it
*looked* like partitioning worked.

We fixed the monitor in two steps:

1. **v2:** each measurement is stored inside the probe line the monitor just
   loaded. After each interval, the simulator reads the measurements out
   without touching the cache.
2. **v3:** two global variables (the way count and the output file handle)
   are kept in CPU registers during measurement. One of them was still
   getting evicted and refetched, which was enough to steal one monitor way
   in one cache set.

We also added a **self-eviction gate**. In each matched pair, the treatment
may not miss noticeably more often than its control; otherwise the
allocation counts as "uninterpretable". The rules were written down
(preregistered) before the final data was collected.

## How detectability is measured

The study uses two statistics.

**Max-set SNR.** For each LLC set, the signal-to-noise ratio is:

```text
SNR = |mean active latency - mean idle latency|
      / pooled sample standard deviation
```

The run statistic is the largest SNR across the 256 sets. The analysis
shuffles the activity labels 10,000 times and recomputes that maximum, so
searching many sets does not create a false positive.

**Hit-only mean.** For each interval, this averages only the probe walks that
were cache hits, then tests whether AES-active intervals are slower than
idle ones. The effect is reported in cycles per probed line.

For each allocation, Fisher's method combines the three seeds. A Holm
correction then controls false positives across all 16 tests (8 allocations
× 2 statistics), at alpha 0.05.

## What happened

With the corrected (v3) monitor:

- every matched pair passed the self-eviction gate (24/24);
- every control detected AES activity;
- **every partitioned treatment still detected AES activity.**

In the table below, effects are how much slower each probed line is during
AES-active intervals, averaged over the three seeds. "Retained" is the
partitioned effect as a share of its control's effect.

| Allocation | Control effect (cycles/line) | Partitioned effect | Retained | Holm p (hit-only) | Result |
|---|---:|---:|---:|---:|---|
| 1/15 | 0.347 | 0.346 | 100% | 6.6e-9 | Distinguishable |
| 2/14 | 0.292 | 0.224 | 77% | 6.6e-9 | Distinguishable |
| 3/13 | 0.338 | 0.287 | 85% | 6.6e-9 | Distinguishable |
| 4/12 | 0.362 | 0.254 | 70% | 6.6e-9 | Distinguishable |
| 5/11 | 0.383 | 0.302 | 79% | 6.6e-9 | Distinguishable |
| 6/10 | 0.391 | 0.294 | 75% | 6.6e-9 | Distinguishable |
| 7/9 | 0.392 | 0.284 | 72% | 6.6e-9 | Distinguishable |
| 8/8 | 0.401 | 0.279 | 70% | 6.6e-9 | Distinguishable |

The original max-set statistic alone reaches the same answer at all eight
allocations. `6.6e-9` is the smallest p-value this test can produce, so
these allocations are not borderline.

There is **no collapse point**: no allocation makes AES activity
undetectable. There is also no allocation where the signal is statistically
equivalent to zero.

## Why partitioning did not stop it

Partitioning did remove one channel. AES can no longer evict the monitor's
lines, and the monitor's probes almost never miss.

What remains is a tiny delay on cache **hits**, a few tenths of a cycle per
line. Way partitioning divides cache *storage*, but both cores still share
the LLC's ports, crossbar, request queues and miss-handling registers. When
AES is busy, the monitor's hits wait slightly longer. This explanation is
inferred from the timing data; we did not measure those structures directly.

## How we know partitioning was enforced

Minimal gem5 instrumentation checks which partition owns each valid LLC
block. All 24 partitioned treatments had disjoint way occupancy with zero
violations. All 50 processes also passed a virtual-to-physical LLC-set
check, so the monitor really probed the sets it believed it was probing.

## What the protection cost

Almost nothing, because both workloads fit easily in their allocations.

- **Monitor IPC** changed by at most 0.029%.
- **AES cycles per completed encryption** changed by at most 0.008%. AES
  cycles per encryption is the clearer useful-work measure, because both
  programs busy-wait, which inflates IPC.
- **Monitor LLC miss rate** rose by 0.26 percentage points in every
  partitioned run. That is a one-time refill of the monitor's lines at the
  start of measurement, not ongoing interference.

## What the result does not prove

- These are simulated results for one monitor, one workload, one cache
  configuration (a deliberately small 4 KiB L1D) and three seeds.
- The three seeds share the same activity schedule, so they are repeated
  inputs rather than independent experiments. Each partitioned run is
  significant on its own, though, so the conclusion does not depend on
  combining them.
- The shared-resource explanation is inferred, not instrumented.

The defensible conclusion is:

> In this simulated configuration, LLC way partitioning removed
> eviction-based contention at negligible cost, but the corrected monitor
> still distinguished AES activity at every tested allocation from `1/15` to
> `8/8`, through a hit-timing channel in shared LLC resources.

For the exact measurements, see `REPORT_UPDATED_RUN_20261011.md` §12. For
the independent check of every step, see `VALIDATION_20261014.md`. For the
current state of the project, see `HANDOFF.md`.
