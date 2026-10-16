# Repeated Matched-Control AES Cache-Contention Study

> **Revision note (October 11, 2026).** No data, analysis, or number in this
> report was changed. Following an independent validation and a post-hoc
> analysis (`APPENDIX_POSTHOC_20261011.md`), these statements were qualified:
> §1 (the result is limited to the predeclared max-set statistic), §4
> (previously said the checks "establish that the result is not caused by
> monitor self-thrashing"), §5 (previously said the rule "was implemented and
> tested before the new measurements were collected"), §6 (a second
> individually significant treatment seed added), §8 (stable-allocation row),
> §9 (two threats added), and §10 (new evidence paths).

## 1. Research question and result

This gem5-only study asks how many ways of a shared 16-way LLC must be
assigned to each of two security domains before a local monitor on core 0 can
no longer distinguish public, labelled AES-active from AES-idle intervals on
core 1, and what performance cost that allocation imposes.

The corrected experiment primes and probes exactly `A` lines per set for an
`A/(16-A)` monitor/AES allocation. Each treatment has an unpartitioned control
using the same monitor depth, binary, public AES plaintext seed, and schedule.
Three predeclared plaintext seeds provide repeated workload inputs.

**Measured result under the predefined decision rule:** with the predeclared
maximum per-set SNR statistic, `1/15` is the first tested allocation and the
stable collapse point. All eight allocations were indistinguishable after
Fisher combination across the three seeds and Holm familywise correction
across the eight treatments. All 24 matched controls were individually
distinguishable.

This conclusion means only that the monitor did not distinguish the activity
labels **under this statistic**. It is not an equivalence proof. A post-hoc
analysis (`APPENDIX_POSTHOC_20261011.md`) found that the partitioned monitor
evicts 20–25% of its own probe lines, and that this label-independent noise
hides the signal. Once those self-evicted probes are removed, all 24
partitioned runs distinguish AES-active from AES-idle intervals (p=0.0001 each).
Way partitioning removed the eviction component of the channel. A
hit-latency timing component remained: 92% of the control effect at `1/15`
and 14–32% at `2/14` through `8/8`. Because these findings are post-hoc, they
qualify the result above rather than replace it.

## 2. Simulated platform

- gem5 v25.1.0.1, commit `c8222cc67a399bfc01e8658dd14b30d5bfd634f9`.
- RISC-V syscall-emulation mode; no physical hardware measurement.
- Two `TimingSimpleCPU` cores at 2 GHz.
- Private 16 KiB L1I and symmetric 4 KiB, four-way L1D caches.
- Shared 256 KiB, 16-way, 64-byte-line LLC with 256 sets and LRU replacement.
- Public AES-128 key and public deterministic plaintext seeds
  `0x5764A5E5`, `0x5764A5E6`, and `0x5764A5E7`.
- Per run, 32 active and 32 idle intervals of 2,000,000 cycles each.

The 4 KiB L1D is a deliberate stress configuration: the four AES T-tables
alone occupy 4 KiB. It exposes lookup activity to the LLC but limits
generalization to processors with larger private caches.

## 3. Repeated experimental design

For each public plaintext seed and each `A=1...8`, the study ran:

1. An unpartitioned control whose monitor walked `A` congruent lines per set.
2. The `A/(16-A)` partitioned treatment using the same binaries and inputs.

This produced 48 inferential gem5 processes: 24 matched controls and 24
partitioned treatments. Two additional A=16 unpartitioned positive-control
diagnostics brought the approved execution count to exactly 50. The diagnostics
are excluded from allocation inference and performance aggregation.

The serial sweep took 45.73 minutes. Every process used a fresh output
directory. Earlier result roots remain unchanged.

## 4. Validation gates

Each process had to provide a passing AES known-answer test, 16,384 probe
records, two statistics blocks, a constant virtual-to-physical LLC-set
rotation, and a seed matching its run metadata. Each partitioned treatment
also had to report zero valid blocks outside its assigned ways.

The completed dataset contains:

- 50 of 50 planned `analysis.json` files and no failed-run directories;
- 819,200 validated probe records and 100 statistics blocks;
- 50 of 50 `PASS congruent` physical-set mappings;
- 24 of 24 `PASS disjoint` treatments with zero isolation violations;
- 24 of 24 individually distinguishable matched controls; and
- one workload-binary hash set across all 50 processes.

These checks rule out an unverified virtual/physical set assumption and
overlapping cache-way masks. They do **not** rule out monitor self-eviction.
The monitor writes a 384 KiB record array during measurement, which allocates
96 new lines per interval. In a partitioned run those lines can only go into
the monitor's own `A` ways, where they evict its probe lines. As a result,
20–25% of partitioned probe walks include an LLC miss, against at most about
6% in the matched controls (Appendix A.3).

## 5. Statistical method

For each LLC set within one run:

```text
SNR = abs(mean(active) - mean(idle)) / pooled sample standard deviation
```

The run statistic is the maximum SNR over 256 sets. Each of 10,000 balanced
label permutations recomputes the maximum using analysis seed 5764. Its
empirical p-value is `(1 + count(null >= observed)) / 10001`.

For each allocation, Fisher's method combines the three per-seed p-values.
Holm adjustment then controls the familywise error rate across the eight
allocation tests at alpha 0.05. The eight matched-control p-value families are
corrected separately. An allocation is interpretable only if all three
individual controls are distinguishable and its combined control result passes
Holm correction.

A stable collapse point is the first allocation whose treatment is not
significant after correction and for which every larger tested monitor
allocation is also not significant. This rule is stated here as it was
designed for the repeated study. The project has no version history, and
`analysis/summarize_repeated_contention.py` was last modified at 23:20:55,
about one minute after the final gem5 process ended (23:19:49). The file
record therefore cannot confirm that the implemented rule was unchanged after
the data were collected.

## 6. Security results

SNR values below are simulated means and sample standard deviations across the
three public plaintext seeds.

| Split | Control SNR mean +/- SD | Partitioned SNR mean +/- SD | Fisher p | Holm p | Corrected result |
|---|---:|---:|---:|---:|---|
| 1/15 | 0.753951 +/- 0.009952 | 0.599548 +/- 0.059948 | 0.256154 | 1.000000 | indistinguishable |
| 2/14 | 0.887231 +/- 0.078722 | 0.579414 +/- 0.119100 | 0.457840 | 1.000000 | indistinguishable |
| 3/13 | 1.040909 +/- 0.086041 | 0.650087 +/- 0.094867 | 0.281171 | 1.000000 | indistinguishable |
| 4/12 | 1.189073 +/- 0.027197 | 0.768531 +/- 0.082069 | 0.021146 | 0.148019 | indistinguishable |
| 5/11 | 1.267922 +/- 0.024469 | 0.760470 +/- 0.072512 | 0.041401 | 0.248409 | indistinguishable |
| 6/10 | 1.381426 +/- 0.048459 | 0.768402 +/- 0.005300 | 0.049165 | 0.248409 | indistinguishable |
| 7/9 | 1.570399 +/- 0.032549 | 0.796324 +/- 0.206010 | 0.007693 | 0.061546 | indistinguishable |
| 8/8 | 1.724397 +/- 0.130042 | 0.613490 +/- 0.074456 | 0.684138 | 1.000000 | indistinguishable |

![Repeated SNR and corrected p-values](results/contention-repeated-20261001/repeated_snr.png)

The corrected `7/9` result is closest to the decision boundary
(`Holm p=0.061546`). One of its three individual seed runs was significant
(seed `0x5764A5E7`, p=0.0017). The `4/12` treatment also had one individually
significant seed (`0x5764A5E5`, p=0.0202). Both are preserved in
`per_seed_matched.csv`. The across-seed, across-allocation rule nevertheless
classifies both allocations as indistinguishable. This sensitivity is a threat
to validity, not grounds to change the predeclared rule after seeing the data.

Appendix A.5 repeats this comparison with a post-hoc hit-only statistic. Under
that statistic every treatment is distinguishable (Holm p = 3.3e-9 at all
eight allocations).

## 7. Performance cost

Positive IPC cost means lower treatment IPC. Positive cycles-per-encryption
cost means more cycles and therefore lower AES throughput. Miss-rate changes
are treatment minus matched control in percentage points.

| Split | Monitor IPC cost | AES IPC cost | Monitor LLC miss change | AES LLC miss change | AES cycles/encryption cost |
|---|---:|---:|---:|---:|---:|
| 1/15 | 0.7867% | -0.0016% | +19.362274 pp | -0.000000047 pp | -0.0098% |
| 2/14 | 1.3995% | -0.0036% | +18.687424 pp | -0.000000058 pp | -0.0112% |
| 3/13 | 2.0283% | -0.0043% | +18.486016 pp | -0.000000109 pp | -0.0195% |
| 4/12 | 2.7542% | -0.0052% | +18.771406 pp | -0.000000156 pp | -0.0279% |
| 5/11 | 3.4152% | -0.0072% | +18.677765 pp | -0.000000173 pp | -0.0307% |
| 6/10 | 4.0675% | -0.0096% | +18.568832 pp | -0.000000166 pp | -0.0293% |
| 7/9 | 4.7389% | -0.0124% | +18.489692 pp | -0.000135605 pp | -0.0293% |
| 8/8 | 5.4186% | -0.0144% | +18.497756 pp | -0.000135613 pp | -0.0293% |

At the first sufficient tested allocation, `1/15`, the monitor's mean IPC cost
is `0.7867%` and its LLC miss rate increases by `19.362274` percentage points.
The AES core shows a `0.0016%` IPC increase, an LLC miss-rate decrease of
`0.000000047` percentage points, and a `0.0098%` reduction in cycles per
encryption. These AES differences are extremely small and are reported as
simulated descriptive values, not as evidence that partitioning improves AES
performance.

IPC remains secondary because both programs use `rdcycle` busy-wait loops.
AES cycles per completed encryption is the clearer useful-work metric.

## 8. Proposal-to-result claim matrix

| Proposal commitment | Completion status | Traceable evidence |
|---|---|---|
| gem5 v25.1.0.1, RISC-V SE, two timing cores, private L1 caches, and shared 16-way LLC | Validated | Per-run `config.ini`, `config.json`, and `run_meta.json` |
| Three public deterministic plaintext seeds | Validated | `run_plan.json` and per-run `workload_seed` in `analysis.json` |
| A-line monitor matched to each `A/(16-A)` allocation | Validated for `A=1...8` and all three seeds | 24 matched rows in `per_seed_matched.csv` |
| Fresh unpartitioned control and partitioned treatment for every seed/allocation pair | Validated: 24 controls and 24 treatments | 48 inferential entries in `run_plan.json` and 48 validated analyses |
| Two A=16 positive-control diagnostics excluded from inference | Validated | Two diagnostic entries in `run_plan.json`; excluded by the repeated summarizer |
| Exactly 50 fresh gem5 processes | Validated | 50 planned entries and 50 `analysis.json` files; no failed-run directories |
| Public AES key, deterministic labels, and AES correctness check | Validated | 50 `aes_self_test=PASS` records in `simout.txt` |
| Maximum per-set SNR with 10,000 shuffled-label permutations using analysis seed 5764 | Validated | Per-run `analysis.json` fields `statistic`, `permutations`, and `seed` |
| Fisher combination across the three workload seeds | Completed | `repeated_summary.json` field `combination` and `summary_repeated.csv` |
| Holm familywise correction across eight allocations, separately for controls and treatments | Completed | `repeated_summary.json` field `multiple_testing`; corrected p-values in `summary_repeated.csv` |
| Every allocation requires three individually significant matched controls and a corrected combined control | Validated: all 24 individual controls passed; all eight combined controls passed | `per_seed_matched.csv` and `control_valid` in `summary_repeated.csv` |
| Physical LLC-set congruence | Validated for all 50 processes | `probe_mapping_validation=PASS congruent`; zero mapping mismatches |
| Disjoint LLC ways | Validated for all 24 partitioned treatments | `isolation_validation=PASS disjoint`; zero isolation violations |
| Stable minimum tested allocation | Completed with qualification: `1/15` under the predeclared max-set rule; a post-hoc hit-only statistic distinguishes all eight allocations | `stable_collapse_point` in `repeated_summary.json`; Appendix A.5 and `results/posthoc-20261011/` |
| Per-core IPC and LLC miss-rate costs | Completed | Three-seed matched changes in `summary_repeated.csv` |
| AES useful-work cost | Completed using total encryptions and cycles per completed encryption | Per-run `aes_encryptions` and `aes_cycles_per_encryption` in `analysis.json` |

## 9. Threats to validity

- gem5 timing is not silicon timing; no physical hardware was measured.
- The 4 KiB L1D is a stress configuration and the T-tables nearly fill it.
- Three consecutive public seeds exercise different plaintext sequences but
  remain a small deterministic sample, not a population of real executions.
- Fisher combination treats the three seed-specific tests as independent
  evidence. Shared simulator structure may make that approximation optimistic.
- Failure to reject after Holm correction is not a formal equivalence test.
  It means the monitor did not distinguish the labels at this experiment's
  sample size and decision rule.
- `7/9` is close to alpha after correction and one seed was individually
  significant, so additional seeds could change the stable-collapse result.
- MSHRs, queues, ports, interconnects, coherence metadata, memory controllers,
  and DRAM remain shared and are not isolated by the LLC way masks. The
  post-hoc analysis is consistent with a measurable timing channel along this
  path. At A=1 to 3 the control probes almost never miss, yet active intervals
  are 0.25–0.35 cycles per line slower, and that hit-timing difference
  survives partitioning (Appendix A.6).
- In partitioned runs the monitor evicts its own probe lines through its
  record buffer. This raises measurement noise and lowers statistical power
  in the treatment arm only, which biases the predeclared test toward
  "indistinguishable" (Appendix A.3).
- IPC includes deliberate busy-wait instructions.

## 10. Evidence paths

- `results/contention-repeated-20261001/run_plan.json`
- `results/contention-repeated-20261001/per_seed_matched.csv`
- `results/contention-repeated-20261001/summary_repeated.csv`
- `results/contention-repeated-20261001/repeated_summary.json`
- `results/contention-repeated-20261001/seed-*/<case>/analysis.json`
- `results/contention-repeated-20261001/seed-*/<case>/stats.txt`
- `results/contention-repeated-20261001/seed-*/<case>/simout.txt`
- `results/contention-repeated-20261001/repeated_snr.pdf`
- `results/contention-repeated-20261001/repeated_snr.png`
- `APPENDIX_POSTHOC_20261011.md` (post-hoc validation and analysis)
- `analysis/posthoc_hit_only_20261011.py` and `results/posthoc-20261011/`

The invalid fixed-16-line pilot, stopped instrumentation attempt, and corrected
single-seed sweep remain preserved under their original result roots. They are
historical evidence and are not included in this repeated-study conclusion.
