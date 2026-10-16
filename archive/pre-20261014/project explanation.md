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
control using the same monitor depth, binaries, AES seed, and schedule. This
matched control proves that the monitor could detect AES activity before the
way masks were enabled.

The final study uses three public plaintext seeds and eight allocations. That
creates 24 controls and 24 partitioned treatments. Two extra A=16 controls are
diagnostics only, bringing the approved total to exactly 50 fresh gem5
processes.

## How detectability is measured

For each LLC set, the signal-to-noise ratio is:

```text
SNR = |mean active latency - mean idle latency|
      / pooled sample standard deviation
```

The run statistic is the maximum SNR across the 256 sets. The analysis shuffles
the activity labels 10,000 times and recomputes that maximum, so searching many
sets does not create an uncorrected false positive.

For each allocation, Fisher's method combines the three public-seed p-values.
A Holm correction then controls familywise error across the eight allocations
at alpha 0.05. All three matched controls must also distinguish activity for an
allocation to be interpretable.

## What happened

All 24 matched controls distinguished AES-active from AES-idle intervals. The
partitioned results below are means across the three public seeds; the p-value
is the final Holm-adjusted value.

| Allocation | Matched-control SNR | Partitioned SNR | Holm p | Result |
|---|---:|---:|---:|---|
| 1/15 | 0.754 | 0.600 | 1.000 | Not distinguishable |
| 2/14 | 0.887 | 0.579 | 1.000 | Not distinguishable |
| 3/13 | 1.041 | 0.650 | 1.000 | Not distinguishable |
| 4/12 | 1.189 | 0.769 | 0.148 | Not distinguishable |
| 5/11 | 1.268 | 0.760 | 0.248 | Not distinguishable |
| 6/10 | 1.381 | 0.768 | 0.248 | Not distinguishable |
| 7/9 | 1.570 | 0.796 | 0.062 | Not distinguishable |
| 8/8 | 1.724 | 0.613 | 1.000 | Not distinguishable |

Under the predefined rule, `1/15` is the first tested stable collapse point:
it and every larger tested monitor allocation were not significant after
correction. This means the monitor did not demonstrate label distinguishability
under this test. It is not proof that active and idle behavior are identical.
The `7/9` result was close to the threshold, so more repetitions could change
the conclusion.

## How we know partitioning worked

The conclusion does not rely only on reduced SNR. Minimal gem5 instrumentation
checks which partition owns each valid LLC block. All 24 partitioned treatments
had disjoint way occupancy with zero violations.

All 50 processes also passed a virtual-to-physical LLC-set congruence check.
Therefore, the monitor did not rely on an unverified virtual-set assumption.

## What the protection cost

At the first tested stable collapse point, `1/15`, relative to its matched
unpartitioned controls:

- Monitor IPC fell by an average of `0.7867%`.
- Monitor LLC miss rate increased by `19.362274` percentage points.
- AES IPC increased by an average of `0.0016%`.
- AES LLC miss rate decreased by about `0.000000047` percentage points.
- AES cycles per completed encryption decreased by `0.0098%`.

The AES changes are extremely small and should be treated as descriptive
simulation variation, not evidence that partitioning improves AES. IPC is also
secondary because both programs deliberately busy-wait; cycles per completed
encryption is the clearer AES useful-work measure.

## What the result does not prove

Way partitioning isolates LLC data ways, but both cores still share LLC ports,
queues, MSHRs, interconnects, memory controllers, and DRAM. Failure to reject a
null hypothesis is also not a formal equivalence test.

The defensible conclusion is:

> Under the predefined three-seed test in this simulated configuration, the
> corrected monitor no longer distinguished the activity labels beginning at
> the tested `1/15` split, with valid matched controls and enforced way masks.

For exact measurements, reproducibility commands, and limitations, see
`RUNBOOK.md` and `REPORT_REPEATED_20261001.md`.
