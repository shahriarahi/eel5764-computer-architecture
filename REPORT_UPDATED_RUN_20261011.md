# Updated Run: Record-Free Repeated AES Cache-Contention Study

October 11, 2026. This report covers the corrected rerun ("updated run") and
compares it with the October 1 study. The October 1 report, result files and
code paths are preserved unchanged (§9).

> **Final result: the full v3 sweep (D3, §12).** All 50 processes were
> rerun with the corrected v3 monitor.
>
> - All 24 pairs pass the self-eviction gate.
> - **All eight allocations, 1/15 through 8/8, are distinguishable** under
>   both statistics.
> - There is no stable collapse point and no equivalence point.
> - The partitioned monitor keeps 100% of its control's hit-timing signal
>   at 1/15, and 70–85% at 2/14 through 8/8.
>
> Sections 1–11 are the supporting record of the earlier v2 sweep and the
> D2 rerun. Their retained-signal figures (91–100%) were partly affected by
> the v2 monitor's hot-variable conflict and are superseded by §12.

## 1. Answer from the v2 sweep (superseded by §12)

*The final answer is in §12: all eight allocations are distinguishable. This
section is kept as the record of the v2 sweep.*

**In this simulated system, LLC way partitioning did not stop the monitor from
detecting AES activity at any allocation that could be evaluated.**

- **1/15 through 6/10:** distinguishable after correction. All six passed the
  self-eviction gate, and all had valid controls under at least one statistic.
- **7/9 and 8/8:** uninterpretable. A smaller, residual monitor self-eviction
  failed the predeclared gate.
- **Stable collapse point:** none. **Equivalence point:** none. Every 90%
  confidence interval lies far outside ±0.02 cycles per line.
- **Size of the remaining signal:** at 1/15 to 6/10 the partitioned monitor
  keeps **91–100%** of its matched control's hit-timing signal.
- **Interpretation:** way partitioning separates cache *storage*. The signal
  this monitor detects is a latency shift on LLC *hits*, which is consistent
  with contention on shared ports, crossbar or queues. That path is not
  partitioned.

**This reverses the October 1 conclusion** ("1/15 is the stable collapse
point"). The reversal is caused by one measurement artifact, described next.

## 2. What changed from the previous run

The previous monitor wrote a 384 KiB record array while measuring. In a
partitioned run those writes could only land in the monitor's own ways, where
they evicted 20–25% of its probe lines. That self-generated noise hid the
signal (`APPENDIX_POSTHOC_20261011.md`).

| | Previous run (Oct 1) | Updated run (Oct 11) |
|---|---|---|
| Monitor binary | `monitor_l1d4k` (`d25a119b…`) | `monitor_v2_l1d4k` (`1edbb2d3…`), same source built with `-DMONITOR_PROBE_SINK_FILE` |
| Record handling | 16,384 × 24 B array (96 new LLC lines per interval) | Record stored in the just-loaded probe line; one `writev` per interval, using functional reads |
| Probe output | `probe,` lines in `simout.txt` | `probes.bin` (16 B per record) |
| Statistics | Max-set SNR | Max-set SNR + hit-only interval mean (co-primary) |
| Multiple testing | Holm over 8 allocations | Holm over 16 tests (8 allocations × 2 statistics) |
| New gate | — | Self-eviction: treatment and control all-hit fractions within 1 percentage point |
| Effect size | — | Cycles per probed line, 90% bootstrap CI, equivalence margin ±0.02 |
| Results root | `results/contention-repeated-20261001/` | `results/updated run/sweep/` |

Unchanged: gem5 v25.1.0.1, RISC-V SE mode, two `TimingSimpleCPU` cores at
2 GHz, 16 KiB L1I, 4 KiB 4-way L1D, a 256 KiB 16-way LRU LLC, the AES victim
binary (`5ef763fa…`), public key, seeds `0x5764A5E5`–`E7`, the label schedule,
48 matched processes plus 2 A=16 diagnostics, and 10,000 permutations with
seed 5764.

## 3. Preregistration and deviations

All rules, thresholds and file hashes were fixed in
`PREREGISTRATION_V2_20261011.md` before any v2 data existed. That document
also recorded the expected outcome ("at least `1/15` is distinguishable").
One deviation, D1, occurred during the smoke test:

- **What happened:** the monitor's final stdout line interleaved with the
  victim's, which failed the runner's text check.
- **Fix:** the monitor now waits one interval after measurement ends before
  printing.
- **Not changed:** no measurement, analysis code or rule.

The failed process is preserved. A 2-process smoke test passed the gate
before the full sweep started.

## 4. Validation gates (v2 sweep)

| Check | Result |
|---|---|
| Processes completed / failed-run directories | 50 / 0 (46.8 min) |
| `probes.bin` complete (262,144 B) | 50 / 50 |
| AES known-answer test | 50 / 50 PASS |
| Physical LLC-set mapping | 50 / 50 `PASS congruent` |
| Way isolation, partitioned treatments | 24 / 24 `PASS disjoint`, 0 violations |
| Statistics blocks | 100 (2 per process) |
| Workload hash sets | 1 |
| **Self-eviction gate** | **18 / 24 pairs PASS**: every pair at 1/15–6/10; 0 of 3 at 7/9 and at 8/8 |

## 5. Security results (v2 sweep; superseded by §12)

Holm values of `6.6e-9` are the smallest possible with 10,000 permutations,
three seeds and 16 tests. Effects are active minus idle, in cycles per probed
line, averaged over seeds.

| Split | All-hit walks, control / treatment | Max-set control valid | Treatment Holm p, max-set | Treatment Holm p, hit-only | Control effect | Treatment effect [90% CI] | Retained | Conclusion |
|---|---|---|---:|---:|---:|---|---:|---|
| 1/15 | 99.99% / 99.98% | no | 0.030 | 6.6e-9 | +0.086 | +0.086 [+0.078, +0.093] | 100% | distinguishable |
| 2/14 | 99.99% / 99.98% | yes | 8.6e-8 | 6.6e-9 | +0.283 | +0.267 [+0.259, +0.274] | 94% | distinguishable |
| 3/13 | 99.99% / 99.98% | yes | 1.6e-7 | 6.6e-9 | +0.288 | +0.287 [+0.280, +0.295] | 100% | distinguishable |
| 4/12 | 99.60% / 99.14% | yes | 2.1e-8 | 6.6e-9 | +0.310 | +0.283 [+0.277, +0.289] | 91% | distinguishable |
| 5/11 | 99.60% / 99.07% | yes | 6.6e-9 | 6.6e-9 | +0.309 | +0.290 [+0.284, +0.295] | 94% | distinguishable |
| 6/10 | 99.57% / 98.92% | yes | 6.6e-9 | 6.6e-9 | +0.309 | +0.283 [+0.278, +0.289] | 92% | distinguishable |
| 7/9 | 99.55% / 97.74% | yes | 6.6e-9 | 6.6e-9 | +0.316 | +0.243 [+0.239, +0.247] | 77% | uninterpretable (gate) |
| 8/8 | 99.49% / 97.16% | yes | 6.6e-9 | 6.6e-9 | +0.321 | +0.222 [+0.217, +0.226] | 69% | uninterpretable (gate) |

![Updated-run effect sizes and corrected p-values](results/updated%20run/sweep/repeated_v2.png)

- **1/15.** The max-set control is valid in only 1 of 3 seeds, so max-set
  cannot be used at this allocation. The hit-only control is valid
  (Holm p = 6.6e-9), and the treatment is distinguishable under it. Once the
  rare misses are removed, the treatment's hit latencies match the
  control's: identical effect, identical SNR.
- **7/9 and 8/8.** Treatment probes miss about 2 percentage points more often
  than control probes, so by the predeclared rule these allocations cannot be
  classified. Descriptively the treatment signal is still strongly present
  (p at the permutation floor), and its lower retained share (69–77%) fits
  the same masking mechanism as in v1, in a weaker form. The remaining source
  of self-eviction was not identified. Candidates are the monitor's stack and
  page-table walks for its 4A probe pages.
- **Diagnostics.** The two A=16 unpartitioned runs, excluded from inference,
  give a max-set SNR of 46–50 (p = 1e-4), confirming a strong eviction signal
  when the monitor fills every way.

## 6. Performance cost (v2 sweep)

These are treatment-minus-control means over three seeds. Positive values
are costs.

| Split | Monitor IPC cost | Monitor LLC miss change | AES IPC cost | AES cycles/encryption cost |
|---|---:|---:|---:|---:|
| 1/15 | 0.009% | +0.26 pp | 0.000% | 0.000% |
| 2/14 | −0.003% | +0.26 pp | −0.000% | −0.004% |
| 3/13 | −0.002% | +0.26 pp | −0.001% | −0.007% |
| 4/12 | 0.023% | +0.64 pp | −0.001% | −0.013% |
| 5/11 | 0.043% | +0.64 pp | −0.003% | −0.008% |
| 6/10 | 0.029% | +0.58 pp | −0.004% | −0.010% |
| 7/9 | 0.015% | +0.53 pp | −0.005% | −0.007% |
| 8/8 | 0.002% | +0.50 pp | −0.005% | −0.010% |

Way partitioning costs these two workloads essentially nothing: under 0.05%
in every metric. This is a simulated, descriptive result for two small
workloads that fit easily in their allocations.

## 7. Comparison: previous run vs updated run

Source: `results/updated run/comparison/comparison_v1_v2.csv`, generated by
`analysis/compare_v1_v2.py`. The v1 hit-only values are post-hoc (Appendix);
the v2 values are preregistered.

![Previous vs updated run](results/updated%20run/comparison/comparison_v1_v2.png)

### 7.1 Self-eviction: removed (A ≤ 6) or much reduced (A = 7, 8)

| Split | Treatment all-hit walks, v1 → v2 | Monitor LLC miss change, v1 → v2 |
|---|---|---|
| 1/15 | 80.1% → 99.98% | +19.36 pp → +0.26 pp |
| 2/14 | 80.8% → 99.98% | +18.69 pp → +0.26 pp |
| 3/13 | 80.2% → 99.98% | +18.49 pp → +0.26 pp |
| 4/12 | 75.6% → 99.14% | +18.77 pp → +0.64 pp |
| 5/11 | 75.6% → 99.07% | +18.68 pp → +0.64 pp |
| 6/10 | 75.6% → 98.92% | +18.57 pp → +0.58 pp |
| 7/9 | 75.6% → 97.74% | +18.49 pp → +0.53 pp |
| 8/8 | 75.6% → 97.16% | +18.50 pp → +0.50 pp |

### 7.2 Security conclusion: reversed

| Split | v1 treatment Holm p (max-set) | v2 treatment Holm p (max-set / hit-only) | v1 conclusion | v2 conclusion |
|---|---:|---|---|---|
| 1/15 | 1.00 | 0.030 / 6.6e-9 | indistinguishable | **distinguishable** |
| 2/14 | 1.00 | 8.6e-8 / 6.6e-9 | indistinguishable | **distinguishable** |
| 3/13 | 1.00 | 1.6e-7 / 6.6e-9 | indistinguishable | **distinguishable** |
| 4/12 | 0.148 | 2.1e-8 / 6.6e-9 | indistinguishable | **distinguishable** |
| 5/11 | 0.248 | 6.6e-9 / 6.6e-9 | indistinguishable | **distinguishable** |
| 6/10 | 0.248 | 6.6e-9 / 6.6e-9 | indistinguishable | **distinguishable** |
| 7/9 | 0.062 | 6.6e-9 / 6.6e-9 | indistinguishable | uninterpretable |
| 8/8 | 1.00 | 6.6e-9 / 6.6e-9 | indistinguishable | uninterpretable |
| **Stable collapse point** | | | **1/15** | **none** |

The predeclared max-set statistic alone, which found nothing in v1, now
detects every treatment from 2/14 up. The v1 "collapse" was produced by the
artifact.

### 7.3 Hit-timing signal: the October 11 appendix overstated attenuation

| Split | Control effect, v1 → v2 | Treatment effect, v1 (post-hoc) → v2 | Share retained, v1 → v2 |
|---|---|---|---|
| 1/15 | +0.245 → +0.086 | +0.225 → +0.086 | 92% → 100% |
| 2/14 | +0.292 → +0.283 | +0.092 → +0.267 | 32% → 94% |
| 3/13 | +0.346 → +0.288 | +0.098 → +0.287 | 28% → 100% |
| 4/12 | +0.365 → +0.310 | +0.052 → +0.283 | 14% → 91% |
| 5/11 | +0.363 → +0.309 | +0.077 → +0.290 | 21% → 94% |
| 6/10 | +0.368 → +0.309 | +0.071 → +0.283 | 19% → 92% |
| 7/9 | +0.382 → +0.316 | +0.062 → +0.243 | 16% → 77% |
| 8/8 | +0.380 → +0.321 | +0.059 → +0.222 | 16% → 69% |

Appendix A.6 concluded that partitioning shrinks the timing signal to 14–32%
of the control at A ≥ 2. **The updated run does not support that.** The
record stream affected even the hit-only v1 estimates. With it removed,
partitioning leaves 91–100% of the signal at 1/15–6/10. The appendix's main
point, that a hit-timing channel survives partitioning, is confirmed and
strengthened.

The record stream also *inflated* the v1 control signal, most clearly at
A=1 (+0.245 → +0.086). That is why the max-set control at 1/15 was valid in
v1 but is not in v2.

### 7.4 Performance cost: the v1 cost was mostly the artifact

| Split | Monitor IPC cost, v1 → v2 | AES cycles/encryption cost, v1 → v2 |
|---|---|---|
| 1/15 | 0.787% → 0.009% | −0.010% → 0.000% |
| 4/12 | 2.754% → 0.023% | −0.028% → −0.013% |
| 8/8 | 5.419% → 0.002% | −0.029% → −0.010% |

The v1 monitor IPC cost (0.79–5.42%, rising with A) and its +18–19 pp miss
increase came from the monitor evicting its own probe lines, not from way
partitioning.

## 8. Threats to validity (v2 sweep; final list in §12.4)

*The first two bullets were resolved later. 7/9 and 8/8 were evaluated in §11
and §12, and the residual source was identified as the `probe_way_count` line
(§11.1).*

- **7/9 and 8/8 were not evaluated.** A residual self-eviction source,
  1.8–2.3 percentage points, remains unidentified. At A=4–6 treatment
  self-eviction is 0.5–0.7 points, within the gate, but it may still slightly
  reduce the measured signal.
- **The preregistration came after the post-hoc analysis,** written the same
  day by the same analyst. It fixed the code, rules and hashes before any v2
  data existed, but the hit-only statistic was chosen because of the post-hoc
  result. The max-set result needs no such caveat: it reaches the same
  conclusion for 2/14–6/10.
- **The mechanism is inferred, not instrumented.** No port, crossbar or MSHR
  statistic was examined.
- **The 1% gate and the ±0.02 cycles-per-line margin** were judgment calls,
  fixed before the data.
- **Fisher combination** assumes the three seed-level tests are independent.
  Most p-values sit at the permutation floor, so this does not change any
  conclusion.
- **Platform limits** (unchanged from v1): gem5 timing, not silicon; a 4 KiB
  L1D stress configuration; three deterministic public seeds; IPC includes
  busy-wait loops.

## 9. Previous run preserved

- **Results:** the 1,022 files under the October 1 result roots match
  `archive/pre-20261011/results_manifest.sha256` (re-checked after this
  sweep).
- **Code:** every new behaviour is opt-in, so the old code paths are still
  the default. A rerun of one October 1 case with current code reproduced it
  byte for byte.
- **Archive:** exact copies of the pre-edit sources are in
  `archive/pre-20261011/` (see its README).
- **Old documents:** `REPORT_REPEATED_20261001.md` is unchanged in substance
  and carries a revision note. This report supersedes its conclusion.

## 10. Evidence and reproduction

- `PREREGISTRATION_V2_20261011.md`: rules, hashes, deviation D1
- `results/updated run/smoke/`: smoke test, including the preserved failed
  attempt
- `results/updated run/sweep/`: 50 runs, `summary_v2.csv`, `summary_v2.json`,
  `per_seed_matched_v2.csv`, `repeated_v2.{png,pdf}`
- `results/updated run/comparison/`: `comparison_v1_v2.csv`,
  `comparison_v1_v2.{png,pdf}`
- `results/updated run/sweep_log.txt`: full sweep log

Run from the project root in WSL:

```bash
python3 scripts/run_repeated_contention_sweep_v2.py --plan full --results-root "results/updated run/sweep-repro"
```

```bash
python3 analysis/compare_v1_v2.py --out "results/updated run/comparison-repro"
```

## 11. Rerun of 7/9 and 8/8 (deviation D2)

### 11.1 Why the gate failed

Full investigation: `results/updated run/investigation-set191/README.md`.
There were two causes.

1. **Most of the gap was the signal itself.** The gate's 20-cycle "slow walk"
   proxy counted 20–100-cycle delays that happen only while AES is active.
   In 8/8 treatments these occurred in 41 of every 1,000 active-interval
   walks and in none of the idle-interval walks.
2. **One genuine self-evicted set.** An LLC trace showed that exactly one
   non-probe line ever occupied the monitor's ways. It holds the global
   `probe_way_count` (and `sink_fd`). The monitor read that variable on
   every set walk. From A=4 upward, the 4-way L1D kept evicting it, and
   each LLC refetch let it hold one monitor way in logical set 191.

### 11.2 What changed (D2, logged in the preregistration before the rerun)

- **Monitor v3** (`0722e049…`): the measurement loop keeps the way count
  and probe fd in registers. Its disassembly contains only probe-chain loads
  and probe-slot stores. The v1 and v2 binaries rebuild unchanged.
- **Gate:** a walk counts as a miss only when it is more than 100 cycles
  above the run's 1st-percentile walk. The tolerance is still 1 point. The
  original gate is reported next to it.
- **Rerun:** 12 fresh processes (7/9 and 8/8 × 3 seeds × 2 arms) in
  `results/updated run/rerun-7-9-8-8/`. All passed validation: 12/12
  mapping, 6/6 disjoint, 12/12 AES, 12/12 complete `probes.bin`, one hash
  set.

### 11.3 Results

| Split | Monitor | Gate D2 / original | Miss walks, control / treatment | Treatment Holm p (max-set / hit-only) | Control → treatment effect | 90% CI | Retained | Conclusion |
|---|---|---|---|---|---|---|---:|---|
| 1/15 | v2 | 3/3 / 3/3 | 0.006% / 0.006% | 0.030 / 6.6e-9 | +0.086 → +0.086 | [+0.078, +0.093] | 100% | distinguishable |
| 2/14 | v2 | 3/3 / 3/3 | 0.006% / 0.018% | 8.6e-8 / 6.6e-9 | +0.283 → +0.267 | [+0.259, +0.274] | 94% | distinguishable |
| 3/13 | v2 | 3/3 / 3/3 | 0.006% / 0.018% | 1.6e-7 / 6.6e-9 | +0.288 → +0.287 | [+0.280, +0.295] | 100% | distinguishable |
| 4/12 | v2 | 3/3 / 3/3 | 0.006% / 0.409% | 2.1e-8 / 6.6e-9 | +0.310 → +0.283 | [+0.277, +0.289] | 91% | distinguishable |
| 5/11 | v2 | 3/3 / 3/3 | 0.006% / 0.409% | 6.6e-9 / 6.6e-9 | +0.309 → +0.290 | [+0.284, +0.295] | 94% | distinguishable |
| 6/10 | v2 | 3/3 / 3/3 | 0.006% / 0.409% | 6.6e-9 / 6.6e-9 | +0.309 → +0.283 | [+0.278, +0.289] | 92% | distinguishable |
| **7/9** | **v3** | **3/3 / 3/3** | 0.006% / 0.018% | 6.6e-9 / 6.6e-9 | +0.392 → +0.284 | [+0.279, +0.290] | **73%** | **distinguishable** |
| **8/8** | **v3** | **3/3 / 3/3** | 0.006% / 0.018% | 6.6e-9 / 6.6e-9 | +0.401 → +0.279 | [+0.275, +0.284] | **70%** | **distinguishable** |

Combined across all eight allocations, there is **no stable collapse point
and no equivalence point**.

What the rerun shows:

- **The v3 fix brought the treatment's real miss rate down to the
  control's level** (0.018% vs 0.006%). With v3, 7/9 and 8/8 pass even the
  original 20-cycle gate (treatment all-hit walks 99.4–99.7%, against
  97.2–97.7% with v2).
- **Signal retained:**
  - At 7/9 and 8/8, partitioning keeps about **70%** of the control's
    hit-timing signal. That is the largest reduction seen at any allocation,
    but the effect is still far outside the ±0.02 equivalence margin.
  - The v3 controls show a larger effect (+0.39 to +0.40) than the v2
    controls did (+0.32). The v2 global-variable refetches also added noise
    in the control arm.
- **Cost:** monitor IPC cost is 0.026–0.030% and AES cycles per encryption
  change by −0.006 to −0.008%, both still negligible.

### 11.4 Remaining caveat

1/15–6/10 were measured with the v2 monitor. From 4/12 to 6/10 it carries
the set-191 conflict (0.41% of treatment walks, inside the gate), which may
slightly change those allocations' retained-signal estimates. A full v3
rerun of all 48 matched processes plus 2 diagnostics (about 47 min) would
give one consistent monitor across every allocation. The conclusion cannot
change in the "secure" direction: every allocation is already
distinguishable with p at the permutation floor.

### 11.5 Evidence

- `PREREGISTRATION_V2_20261011.md`, deviation D2
- `results/updated run/investigation-set191/`: trace evidence and scripts
- `results/updated run/rerun-7-9-8-8/`: 12 runs, `summary_combined.csv`,
  `summary_combined.json`, `per_seed_combined.csv`
- `results/updated run/rerun_log.txt`

Reproduce from the project root in WSL:

```bash
python3 scripts/run_rerun_v3.py --results-root "results/updated run/rerun-repro"
```

## 12. Final result: full v3 sweep (deviation D3)

All 50 processes (48 matched and 2 diagnostics) were rerun with the v3
monitor into `results/updated run/sweep-v3/` (October 12, 01:02–01:47).
The plan and hashes were logged as D3 before the run.

**Validation:** 50/50 processes and 0 failed directories; 819,200 probe
records; 50/50 AES PASS and mapping PASS; 24/24 disjoint; one hash set; all
50 runs used v3. **Self-eviction gate: 24/24 pairs pass** under both the D2
and the original gate. Probe walks with an LLC miss: 0.006–0.018% in
treatments, 0.006% in controls.

| Split | Treatment all-hit walks | Control → treatment effect (cycles per line) | 90% CI | Retained | Treatment Holm p (max-set / hit-only) | Conclusion |
|---|---:|---|---|---:|---|---|
| 1/15 | 99.98% | 0.347 → 0.346 | [0.335, 0.358] | 100% | 1.2e-5 / 6.6e-9 | distinguishable |
| 2/14 | 99.98% | 0.292 → 0.224 | [0.216, 0.232] | 77% | 3.7e-7 / 6.6e-9 | distinguishable |
| 3/13 | 99.98% | 0.338 → 0.287 | [0.279, 0.296] | 85% | 6.4e-8 / 6.6e-9 | distinguishable |
| 4/12 | 99.95% | 0.362 → 0.254 | [0.248, 0.260] | 70% | 6.6e-9 / 6.6e-9 | distinguishable |
| 5/11 | 99.87% | 0.383 → 0.302 | [0.297, 0.308] | 79% | 6.6e-9 / 6.6e-9 | distinguishable |
| 6/10 | 99.80% | 0.391 → 0.294 | [0.288, 0.299] | 75% | 6.6e-9 / 6.6e-9 | distinguishable |
| 7/9 | 99.62% | 0.392 → 0.284 | [0.278, 0.290] | 72% | 6.6e-9 / 6.6e-9 | distinguishable |
| 8/8 | 99.41% | 0.401 → 0.279 | [0.275, 0.284] | 70% | 6.6e-9 / 6.6e-9 | distinguishable |

There is **no stable collapse point and no equivalence point.** The max-set
control is now valid at all eight allocations, so the original predeclared
statistic alone also detects every treatment.

**Cost:** monitor IPC changes by at most 0.029%, and AES cycles per
encryption by at most 0.008%. The monitor's LLC miss rate rises by 0.26
percentage points. That rise is not ongoing self-eviction; it is a one-time
refill at the start of measurement:

- Treatment monitors take exactly 86 × A data misses, identical in every
  seed. Controls take none.
- Both arms make 32,768 × A data accesses, so the delta is
  86 / 32,768 = 0.26% at every A.
- Every timed walk with a miss falls in interval 0, the first walk after the
  stats reset. That is 3 walks per treatment run and 1 per control run.
- Interval 0 is idle-labelled, and the hit-only statistic excludes these
  walks.

Figure: `results/updated run/sweep-v3/repeated_v3.png`.

### 12.1 What changed from the v2 sweep

| | v2 sweep (§5) | v3 sweep (final) |
|---|---|---|
| Control effect at 1/15 | +0.086 | +0.347 |
| Retained signal, 2/14–6/10 | 91–100% | 70–85% |
| Max-set control valid at 1/15 | no | yes |
| Conclusions | 1/15–6/10 distinguishable; 7/9, 8/8 uninterpretable | all eight distinguishable |

The v2 monitor read the global `probe_way_count` on every set walk, which
added timing noise in **both** arms. At A=1 that suppressed most of the
signal (+0.086 vs +0.347). At A ≥ 4 the resulting set-191 conflict added
treatment-only noise, which made the v2 retained fractions look higher than
they are. The overall answer is unchanged, and the v3 numbers are more
precise. Partitioning does not reduce the hit-timing signal at 1/15 and
leaves 70–85% of it at larger allocations.

### 12.2 Reproducibility note

The v3 rerun (§11) and the v3 sweep wrote to output paths of different
lengths. All six control probe files are byte-identical between them. Five
of the six treatment files differ slightly, although every summary
statistic matches to three decimals. The monitor's argument and stack
layout depend on the output path, and under partitioning that still nudges
timing slightly. To reproduce a v3 run byte for byte, keep the same output
path length.

### 12.3 Updated Word reports

These are new files; the originals are unchanged.

- `Group18_EEL5764_Final_Project_Report_Updated.docx` (3 pages)
- `Group18_EEL5764_Final_Project_Report_Expanded_Updated.docx` (5 pages)

Both are generated by `scripts/build_updated_reports.py` from the original
DOCX templates and the v3 data. Every number is read from the result files,
and the script asserts the outcome pattern before writing. Both pass the
OOXML schema validator and were checked visually after rendering in Word.

**Regenerated October 14, 2026.** The builder's prose was corrected in three
places:

- The control effect "ranges from +0.292 to +0.401", replacing "rises from …
  to …".
- The +0.26 pp miss rise is described as a one-time refill at the start of
  measurement.
- The threats section adds the shared-schedule and gate-sensitivity caveats.

Each new statement is computed from the results and asserted by the builder.
The regenerated files open in Word without repair prompts and keep 3 and 5
pages, with clean page breaks on visual inspection. The OOXML schema
validator was not re-run on them. The October 12 versions are kept in
`archive/pre-20261014/`.

```bash
python3 scripts/run_repeated_contention_sweep_v3.py --results-root "results/updated run/sweep-v3-repro"
```

### 12.4 Threats to validity (final)

- **The mechanism is inferred, not instrumented.** The signal is attributed
  to shared LLC ports, crossbar or queues, but no port, crossbar or MSHR
  statistic was examined.
- **The analysis choices followed the data.** The hit-only statistic was
  chosen after the post-hoc analysis, and the D2 gate after the v2 sweep. Both
  were fixed before the v3 data existed. The predeclared max-set statistic
  alone reaches the same conclusion at all eight allocations.
- **The D2 gate is weak.** Its tolerance is 1 percentage point, while the
  observed treatment-minus-control miss-walk differences are at most 0.012
  points. The v2 set-191 conflict (0.40 points) would also have passed it. The
  stronger evidence that v3 has no self-eviction is direct:
  - no LLC set is slow in every interval, in any v3 run;
  - timed misses occur only in interval 0;
  - there are 3 miss walks out of 16,384 in treatments, against 1 in controls.
- **The seeds are not independent replicates.** All three seeds use the same
  activity schedule and the same permutation sequence
  (`random.Random(5764)`). Only the AES plaintexts differ, and the simulator
  is deterministic. Fisher combination assumes independent seed-level tests,
  but the conclusion does not depend on it. Each of the 24 treatment runs is
  significant on its own at p = 1/10,001 under the hit-only statistic, and a
  Bonferroni correction over all 24 still gives p ≤ 0.0024.
- **The effect depends on the monitor build.** The 1/15 control effect is
  +0.086 with v2 and +0.347 with v3, so the retained-signal percentages apply
  only to this monitor.
- **The control effect is not monotone in A.** It ranges from +0.29 (A=2) to
  +0.40 (A=8).
- **Isolation is checked by snapshot.** It is a tag-occupancy check at each
  stats dump (`preDumpStats`), not continuous monitoring.
- **Platform limits.** gem5 timing, not silicon; a 4 KiB L1D stress
  configuration; `TimingSimpleCPU`; three public seeds; IPC includes
  busy-wait loops.

### 12.5 Independent validation (October 14, 2026)

`VALIDATION_20261014.md` re-derived every stage from raw artifacts.

- **Pipeline re-run on copies:** byte-identical outputs for:
  - the October 1 study;
  - the post-hoc analysis;
  - the smoke test;
  - the v2 sweep;
  - the D2 rerun;
  - the comparison;
  - the v3 sweep;
  - both DOCX reports.
- **Independent reimplementation** (no project imports, a different RNG): the
  same conclusions, gates and effects. Bootstrap CIs agree to within 0.0011.
- **Fresh gem5 re-simulation** of seed `0x5764A5E5` 8/8 (control and
  treatment) at the same output-path length: `probes.bin` and `stats.txt`
  are bit-identical (`results/updated run/repro-v3/`).

No conclusion changed. §12.4 and the "+0.26 pp" explanation above come from
that validation.

## 13. Mechanism: the shared crossbar request layer (October 14)

§12 left the mechanism inferred. A preregistered follow-up
(`PREREGISTRATION_MECHANISM_20261014.md`) tested one specific candidate: the
**request layer of the shared L1-to-LLC crossbar**, `system.l2bus.reqLayer0`.

Every LLC request from both cores passes through this one layer. The
crossbar's response layers are one per core, so they are not shared. LLC
blocking was ruled out beforehand: `blockedCycles` is 0 in every v3 arm.

### 13.1 Design

The study has four crossbar settings. For each setting there are 3 seeds,
A ∈ {1, 8}, and a matched control plus a treatment, giving **48 fresh
processes**. All use the v3 monitor, and every run dumps statistics once
per labelled interval.

| Setting | Crossbar change | Request / writeback occupancy |
|---|---|---|
| default (`std`) | none: 32 B wide, 1 GHz, header 1 cycle | 1 ns / 3 ns |
| wider (`wid`) | 128 B wide | 1 ns / 2 ns |
| 2 GHz (`clk`) | crossbar on the CPU clock | 0.5 ns / 1.5 ns |
| near-ideal (`ide`) | 512 B, header 0, 2 GHz | ≤ 0.5 ns / 0.5 ns |

The statistics, CI and margin are the v3 study's, unchanged.

**Validation:**

- The guard run shows the code change has no effect at default settings:
  `guard-mx/` is bit-identical to `sweep-v3`.
- 48/48 runs pass. Isolation is disjoint in all 64 per-interval snapshots of
  every treatment.
- The 12 default runs reproduce `sweep-v3`'s `probes.bin` byte for byte, so
  per-interval stats dumps did not perturb the measurement.
- Re-running the analysis gives byte-identical output.

### 13.2 Results

Effect is active − idle hit latency in cycles per probed line, averaged over
three seeds; 90% bootstrap CIs are in brackets. Utilization is the mean
`reqLayer0` busy fraction.

| Setting | Utilization (1/15) | 1/15 control | 1/15 partitioned | Utilization (8/8) | 8/8 control | 8/8 partitioned |
|---|---:|---:|---:|---:|---:|---:|
| default | 5.5% | +0.347 | +0.346 [0.335, 0.357] | 6.9% | +0.401 | +0.279 [0.275, 0.284] |
| wider | 4.4% | +0.211 | +0.211 [0.202, 0.219] | 5.6% | +0.375 | +0.245 [0.241, 0.249] |
| 2 GHz | 2.4% | +0.045 | +0.045 [0.042, 0.048] | 3.0% | +0.129 | +0.114 [0.112, 0.116] |
| near-ideal | 0.6% | +0.000 | **+0.000** [0.000, 0.000] | 0.7% | +0.033 | **+0.033** [0.032, 0.034] |

**Preregistered predictions:**

- **P1 PASS.** Request-layer occupancy is higher in AES-active intervals in
  all four default cells: about +1.05e8 ticks per interval, which is about
  +10.5 points of utilization, with Fisher p = 4.1e-10 each. The correlation
  between per-interval occupancy and the monitor's hit-walk mean is
  r = 0.966–0.996.
- **P2 PASS.** The partitioned effect falls monotonically with utilization
  (Spearman ρ = 1.0 at A = 1 and A = 8).
- **P3 FAIL.** The near-ideal crossbar removes the 1/15 effect completely:
  +0.0001 cycles per line, hit-only p = 1.0 in every run, equivalent to
  zero. At 8/8 it leaves +0.033 [0.032, 0.034], an 88% reduction that is
  outside the ±0.02 margin.

**Outcome: `partial`.**

**What the raw latencies show** (seed e5, 1/15):

- **Default crossbar:** all 8,188 idle hit walks take exactly 33 cycles.
  9.4% of active walks are delayed by +2, +4 or +6 CPU cycles, which is 1–3
  cycles of the 1 GHz crossbar.
- **Near-ideal crossbar:** the delays become a symmetric ±1-cycle jitter
  (45 walks each way), so the mean shift is zero.

Figure: `results/updated run/mech-figures/fig_mechanism_paper.png`, made by
`analysis/plot_mechanism_figures.py` from the preregistered summary.

### 13.3 Interpretation

- **The crossbar request layer carries the leak.** It carries all of it at
  1/15 and 88% of it at 8/8.
- **Partitioning does not change that channel.** Control and treatment fall
  together as the crossbar gets faster. At the near-ideal setting they are
  identical (+0.033 at 8/8 in both arms).
- **The 8/8 residual is attributed to the LLC's own request path, by
  elimination.** It still comes in +2-cycle steps, which is one cycle of the
  LLC's 1 GHz clock; the LLC stays on the system clock in every setting.
  This attribution was preregistered as the meaning of a `partial` outcome.
  It is not a separate test.
- **What a defense needs.** Way partitioning must be paired with a
  partitioned or time-multiplexed interconnect (bandwidth partitioning, or
  per-domain arbitration of the shared request layer) before this channel
  closes. This configuration did not test such a mitigation.

### 13.4 Limits

- Changing the crossbar changes the simulated platform, and the
  near-ideal crossbar is not a realistic design. It is a diagnostic.
- The residual's attribution to the LLC request path is by elimination;
  gem5's classic cache exposes no per-port queueing statistic.
- The 2-cycle quantization was observed descriptively and was not
  preregistered.
- The three seeds share one schedule (§12.4). Every run is individually
  significant, or individually null at near-ideal 1/15.

Reproduce from the project root in WSL (about 40 minutes):

```bash
python3 scripts/run_mechanism.py
python3 analysis/summarize_mechanism.py
python3 analysis/plot_mechanism_figures.py
```
