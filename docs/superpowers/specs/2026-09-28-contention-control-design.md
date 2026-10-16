# Simulated Cache-Contention Control Design

## Scope

Add the missing unpartitioned-control portion of the original defensive study.
Core 0 measures only its own cache lines. Core 1 runs a deliberately
leakage-prone educational AES-128 implementation with four conventional 1 KiB
T-tables. All execution remains inside gem5 RISC-V SE mode. The experiment
classifies only public AES-active versus AES-idle intervals; it performs no
key inference or secret-dependent classification.

This first implementation stops after analyzing `UNPARTITIONED`. It does not
run the eight partitioned cases or change the existing isolation-and-cost
results.

## Scientific constraint

The AES tables remain at their conventional total size of 4 KiB, with no
artificial L1 eviction. They therefore fit in the configured 16 KiB private
L1D. Since the classic-cache model does not back-invalidate private L1 lines
when the mostly-inclusive LLC evicts a line, the unpartitioned control may
show no recurring LLC contention after warm-up. A non-detection is a valid
stopping result, not grounds for silently changing the workload.

## Components

### Portable AES component

`workloads/aes_ttable.[ch]` implements AES-128 encryption with four 256-entry
32-bit T-tables, each aligned to 64 bytes. It exposes table initialization,
AES-128 key expansion, and single-block encryption. A portable known-answer
test uses the public FIPS-197 key/plaintext/ciphertext example.

### Victim workload

`workloads/victim.c` initializes the tables, verifies the known-answer vector,
expands the fixed public key, and generates plaintexts from a documented fixed
seed. It uses the shared public interval schedule: during an active interval
it repeatedly encrypts; during an idle interval it executes a register-only
wait loop. It exits only after the measurement and logging grace period.

### Monitor workload

`workloads/monitor.c` owns a 256 KiB, 64-byte-aligned buffer arranged as 16
lines for each of 256 LLC sets. Within each interval it primes all sets, waits
until the probe phase, then follows a dependent 16-line chain for each set and
measures elapsed cycles with RISC-V `rdcycle`. It records data in memory during
measurement and emits it afterward in one buffered write.

Each record is CSV:

```text
probe,<timestamp_cycles>,<interval>,<label>,<llc_set>,<latency_cycles>
```

### Shared schedule

`workloads/contention_common.h` defines a one-millisecond warm-up
(`2,000,000` CPU cycles at 2 GHz), 64 one-million-cycle measurement
intervals, and a fixed balanced schedule containing 32 active and 32 idle
labels in non-alternating order. Both programs derive the current interval
from the absolute `rdcycle` value, so the separate SE address spaces need no
shared memory.

### gem5 configuration and runner

`configs/run_contention.py` reproduces the existing two-core hierarchy and
requestor-to-partition mapping, but runs `monitor` on core 0 and `victim` on
core 1. It resets statistics after the warm-up, simulates exactly the 64
measurement intervals, and explicitly dumps the first, measurement-only
statistics block. It then allows buffered log output to finish; gem5 writes a
second automatic block at final exit, which includes serialization and is
preserved but excluded from performance metrics. It records phase exit causes
and timing constants in `run_meta.json`.

`scripts/run_contention_control.sh` builds no software and runs only the
unpartitioned case into `results/contention/UNPARTITIONED`. It refuses to
replace an existing result directory. It records the command and workload
hashes and fails if expected output, the AES self-test, or the gem5 completion
marker is absent.

## Data reduction and decision rule

`analysis/analyze_contention.py` accepts exactly one record for every
interval/set pair: 64 intervals times 256 sets, with timestamps inside the
declared interval and labels matching the public schedule. It applies no
post-hoc filtering. The 256 set latencies in an interval are averaged to form
one interval sample, yielding 32 active and 32 idle samples.

For active samples `a` and idle samples `i`, observed SNR is

```text
abs(mean(a) - mean(i)) / pooled_sample_standard_deviation
```

where the pooled variance is

```text
((n_a - 1) * var(a) + (n_i - 1) * var(i)) / (n_a + n_i - 2).
```

The null calculation shuffles the 64 interval labels 10,000 times with Python
PRNG seed `5764`, preserving the 32/32 counts. The 95th percentile is the
nearest-rank value at sorted index 9,499. The corrected empirical p-value is
`(1 + count(null_snr >= observed_snr)) / 10,001`.

The unpartitioned control passes only when observed SNR is strictly greater
than the null 95th percentile and the empirical p-value is below 0.05. A zero
pooled standard deviation makes SNR undefined and is reported as an analysis
error rather than replaced. Missing, duplicated, late, mislabeled, or
non-numeric samples also fail explicitly.

The analysis writes `results/contention/UNPARTITIONED/analysis.json` with the
observed SNR, null threshold, p-value, group counts, group means, exact
formula, seed, permutation count, and PASS/FAIL decision. A FAIL prevents any
partition sweep.

## Performance metrics

The first stats block covers only the 64 measurement intervals; gem5's second,
automatic final block includes logging and is not used. Per-core IPC is read
from `system.cpu0.ipc` and `system.cpu1.ipc` in the first block. Per-core LLC miss rate is
the sum of `system.llc.demandMisses::cpuN.inst` and `.data` divided by the
corresponding demand-access sum. A present `system.llc.demandAccesses::total`
is required; omitted zero-valued vector entries count as zero, while zero
total accesses for a core produce a reported NaN rather than an invented
rate.

## Verification

Tests precede implementation. Python unit tests cover SNR arithmetic, fixed
shuffle reproducibility, malformed/duplicate log rejection, label validation,
and zero-variance handling. Portable C tests cover the AES known-answer vector
and the balanced activity schedule. The RISC-V build is checked for undefined
symbols, vector instructions, and `gp`-relative references. The final control
run must produce a complete monitor log, a passing AES self-test, the expected
measurement and automatic-final stats blocks, and a traceable analysis result; whether the scientific decision is
PASS or FAIL is not predetermined.

