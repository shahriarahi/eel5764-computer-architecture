# 4 KiB L1D Contention-Control Redesign

## Status of the first control

The original 16 KiB-L1D unpartitioned control is retained as a failed pilot at
`results/contention/UNPARTITIONED`. It produced only six victim LLC demand
accesses and did not beat the predeclared interval-mean null test. Its data and
`analysis.json` must not be overwritten or reclassified.

## Predeclared changes

The redesigned control changes exactly two methodological choices before new
data are observed:

1. Both cores receive symmetric 4 KiB, four-way private L1D caches in the
   dedicated contention configuration. The completed isolation/cost study
   remains at 16 KiB. The AES victim remains a conventional four-table
   implementation with four 1 KiB tables and no explicit eviction sweep.
2. The activity statistic is the largest per-set SNR among all nonconstant LLC
   set time series. Every shuffled-label replicate recomputes all eligible
   per-set SNRs and retains its own maximum, so the null distribution accounts
   for searching across 256 sets.

Everything else is frozen: RISC-V SE mode, two `TimingSimpleCPU` cores, public
AES inputs, 64 balanced intervals, all 16,384 probe records,
10,000 label shuffles, seed 5764, pooled-sample-standard-deviation SNR, and
alpha 0.05.

## Execution-feasibility amendment

The first 4 KiB attempt was preserved before analysis because the monitor
reported `probe_deadline` at interval 4: its 500,000-cycle probe window was too
short after the smaller L1D moved more of the monitor's own accesses to the
LLC. The redesigned profile therefore uses two-million-cycle intervals and a
one-million-cycle probe offset. This changes only the time budget per labelled
interval; it retains all 256 sets, 16 ways per set, 64 labels, and the analysis
defined above. Separately named workload binaries preserve exact reproduction
of the original one-million-cycle control.

## Decision rule

The redesigned unpartitioned control passes only when observed maximum per-set
SNR is strictly above the 95th percentile of shuffled maximum SNR and the
corrected empirical p-value is below 0.05. A passing result permits later
partitioned evaluation using this frozen method. A failed result stops the
sweep; no further cache-size or workload tuning is allowed within this method.

## Output isolation

The new run writes only to `results/contention-l1d4k/UNPARTITIONED`. The runner
refuses to replace a completed result and preserves failed attempts under
timestamped names.
