# Defense sweep over the proposal's design — preregistration

Frozen 2026-10-18, before any `tdma-rsa` or `tdma-rsq` output exists. All
values are simulated (gem5). This step asks the accepted proposal's question
about the full defense: way partitioning, 4-cycle request TDMA, and per-domain
LLC response queues. It is judged by the proposal's own success criterion over
its full design.

## Cases (`run_sweep.py`; executable `66c30701…`, unchanged since `PREREGISTRATION.md`)

- **Defended treatment (`tdma-rsa`).** The AES victim, run for the three public
  seeds `0x5764A5E5`, `0x5764A5E6`, and `0x5764A5E7` at A=1…8: 24 runs.
- **Defended quiet victim (`tdma-rsq`).** The same 24 configurations with the
  quiet victim.
- **Arguments.** Each case reuses the baseline arguments from its frozen v3
  treatment's `cmd.txt` (`results/updated run/sweep-v3`). It also reuses that
  treatment's probe-path length, which is 138, or 137 for 8/8. The only
  additions are `--respq` and `--tdma-slot-cycles 4`, plus `--quiet-binary` for
  `tdma-rsq`.
- **Execution.** Up to 6 fresh processes run concurrently, each with a 600 s
  bound. After the first failure, no new case starts. A failed case is
  preserved, and roots are never reused.

## Per-case validity

- gem5 exits 0. A requestor-mapping or response-retry `fatal` counts as a
  failure.
- `system.llc.response_domain_prefixes` is `cpu0. cpu1.`.
- All TDMA violation counters are zero.
- For AES cases, the unchanged `analysis/analyze_contention.py --statistic
  max-set` also requires `PASS congruent` mapping, a `PASS disjoint` way
  allocation with 0 violations, a hit-only statistic, and more than zero
  encryptions.

## Primary outcome 1: the proposal's success criterion

The frozen decision code `analysis/summarize_sweep_v3.py` runs unchanged. Its
inputs are:

- **Controls.** The stored v3 unpartitioned controls
  (`sweep-v3/seed-*/UNPARTITIONED-A{w}`). They already pass the proposal's
  control-validity rule at all eight allocations.
- **Treatments.** The defended AES runs.
- **View root.** The summarizer reads one root, so `tdma-rsv` is built from
  **byte-identical copies** of each run's `analysis.json`, `run_meta.json`, and
  `probes.bin`. No original file is modified.

The decision rule is the one the proposal and the paper use:

- two co-primary statistics, max-set SNR and hit-only;
- Fisher combination across the three seeds;
- Holm correction across the 8 allocations × 2 statistics in each arm;
- the self-eviction gate;
- the stable collapse point.

**The defense satisfies the proposal's criterion** if every allocation is
judged `indistinguishable`, so that the stable collapse point is `1-15`.
Any other conclusion is reported as found.

## Primary outcome 2: byte-level noninterference

For all 24 configurations, compare the defended AES `probes.bin` with the
defended quiet `probes.bin` record by record. **PASS** requires 24 of 24
byte-identical. Otherwise, report the count of differing configurations and
the differing records and intervals for each one.

## Secondary outcomes (descriptive)

- The treatment hit-only effect per probed line, its 90% CI, and the fraction
  of control effect retained, compared with the way-only v3 treatment.
- Costs relative to the v3 controls, using the summarizer's own fields: monitor
  IPC, AES IPC, cycles per encryption, and LLC miss rates. In addition, AES
  encryptions relative to the v3 way-only treatment.

## Limits

The three public seeds change plaintexts but share one activity schedule and
one key. A PASS covers this design in gem5 and claims nothing beyond it.
