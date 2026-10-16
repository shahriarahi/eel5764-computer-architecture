# Appendix: Post-Hoc Analysis of the Repeated Matched-Control Study

Companion to `REPORT_REPEATED_20261001.md`. Analysis date: October 11, 2026.

## A.1 Status and scope

This appendix is **post-hoc and exploratory**. It was designed after the
repeated study's results were seen. It does **not** replace the predeclared
max-set decision rule or change any reported number. No gem5 process was run.
The appendix re-reads the raw probe records of the 48 inferential runs in
`results/contention-repeated-20261001/`. That root, its analyses, and the main
report are unchanged.

The question is narrow. When the predeclared statistic stops distinguishing
AES-active from AES-idle intervals in the partitioned treatments, is that
because the signal was removed, or because something else hid it?

## A.2 Independent reproduction of the reported results

Before the new analysis, every result in the main report was recomputed from
the raw `simout.txt` and `stats.txt` files, independently of the project's
analysis code.

| Check | Outcome |
|---|---|
| 50 runs; 16,384 probe records each (819,200 total); 2 statistics blocks each (100 total) | Reproduced |
| One workload-hash set; `aes_self_test=PASS` and the matching plaintext seed in every run | Reproduced |
| 50 `PASS congruent` mappings; 24 `PASS disjoint` treatments with zero violations and correct way masks | Reproduced |
| Observed max-set SNR, best set, and eligible-set count, all 50 runs | Match within 1e-9 |
| 10,000-permutation empirical p-values (seed 5764), all 50 runs | Exact match |
| Fisher-combined and Holm-adjusted p-values for all 8 controls and 8 treatments | Exact match |
| Section 7 performance values | Match `summary_repeated.csv` |

Two smaller observations came out of this check:

- Besides `7/9` (seed `0x5764A5E7`, p=0.0017), the `4/12` treatment for seed
  `0x5764A5E5` was also individually significant before correction
  (p=0.0202). Section 6 of the main report mentions only `7/9`.
- `analysis/summarize_repeated_contention.py` and its compiled `.pyc` have a
  modification time of 23:20:55 on October 1. That is about one minute after
  the last gem5 process finished (23:19:49). Without version control there is
  no way to confirm whether the decision rule itself was edited. The
  timestamps do not by themselves support the statement in Section 5 that the
  rule was "implemented and tested before the new measurements were collected."

## A.3 Observation: the partitioned monitor evicts its own probe lines

Each probe record is the total walk time over the `A` probed lines of one
set. A walk where every line hits costs about `6 + 32A` cycles (38 cycles at
A=1). A single LLC miss adds roughly 120 cycles. In this appendix, a record
counts as **all-hit** when it is at most 20 cycles above the run's
1st-percentile walk time.

| Split | Control all-hit records | Treatment all-hit records | Treatment slow records per interval (of 256) |
|---|---:|---:|---:|
| 1/15 | 100.0% | 80.1% | 51.0 |
| 2/14 | 100.0% | 80.8% | 49.3 |
| 3/13 | 99.6% | 80.2% | 50.7 |
| 4/12 – 8/8 | 93.4 – 93.7% | 75.5 – 75.6% | 62.5 – 62.6 |

About 20–25% of partitioned probe walks include a miss, against at most about
6% in the matched controls. This is the probe-level form of the +18.5 to
+19.4 percentage-point monitor LLC miss-rate increase reported in Section 7.

The misses do **not** come from AES. Way masks keep AES out of the monitor's
ways (24/24 `PASS disjoint`), and the number of misses per interval does not
depend on the activity label (test H3 below: treatment Fisher p ≥ 0.958 at
every split). The pattern points to the monitor's own record buffer:

- `workloads/monitor.c:30` declares `records[16384]` of
  `struct probe_record`. That struct is 24 bytes on RV64, so the array is
  384 KiB, larger than the 256 KiB LLC.
- Each interval writes 256 records. That is 6,144 B, or **96 new cache
  lines**, and those lines must be allocated in the monitor's own `A` ways.
- Eight intervals write 768 lines, which is exactly 3 × 256 sets, so the
  sequence of sets touched should repeat every 8 intervals.
- What the data shows: in each interval the slow records form one or two
  **contiguous bands of LLC sets** (for example, sets 95–152, then 191–255).
  The per-interval counts repeat with **period 8** (1/15, seed `0x5764A5E5`:
  2, 58, 65, 34, 78, 33, 41, 96, then 2, 59, 65, 34, …). The maximum is
  exactly **96**. Across all treatments, 84–98% of intervals have the same
  miss count as the interval 8 earlier.

In the unpartitioned control, the record lines can use any of 16 ways and
LRU evicts older record lines instead of the recently probed lines. With only
`A` ways, the record stream has to evict probe lines. This is a milder form
of the monitor self-thrashing confound found on October 1 for the
fixed-16-line pilot.

A separate, static pattern shows up in both arms. At A ≥ 4, the 16 sets
0, 16, 32, …, 240 have a slow walk in **every** interval, in controls and
treatments alike. These are the ≈16 slow records per interval seen in the
A ≥ 4 controls. Set 128 is always slow at A=3 in both arms, and set 255 is
always slow in treatments from A=3 upward. These sets never pass the all-hit
filter, so H1 and H2 (A.4) exclude them. Their source was not identified.

## A.4 Post-hoc tests

Each test builds one value per interval (64 values per run) and compares the
32 active with the 32 idle intervals. It uses the same SNR, the same 10,000
balanced shuffles from `random.Random(5764)`, and the same Fisher-then-Holm
combination as the main study. p-values are two-sided.

| Test | Per-interval value | Purpose |
|---|---|---|
| **H1** hit-only mean | Mean of the all-hit records only | Removes the label-independent self-eviction misses |
| **H2** set-centred hit-only mean | As H1, after subtracting each set's own mean hit latency | Rules out a shift caused only by which sets survive the filter |
| **H3** miss count | Number of slow records | Tests for an eviction channel: does AES change how many probes miss? |
| **H4** unfiltered mean | Mean of all 256 records | The study's original interval-mean statistic, as a reference |

The all-hit threshold never uses the labels, so the label-permutation null
is still valid after filtering. The 20-cycle band itself was chosen after
looking at latency distributions.

## A.5 Results

Effect sizes are active-minus-idle cycles **per probed line**, averaged over
the three seeds. Every Holm value reported as `3.3e-9` is the smallest value
possible with 10,000 permutations: each seed gave p=1/10,001.

| Split | Control H1 effect | Treatment H1 effect | Share retained | Treatment H1 SNR | Treatment H1 Holm p | Treatment H4 Holm p |
|---|---:|---:|---:|---:|---:|---:|
| 1/15 | +0.245 | +0.225 | 92% | +5.32 | 3.3e-9 | 1.00 |
| 2/14 | +0.292 | +0.092 | 32% | +2.72 | 3.3e-9 | 1.00 |
| 3/13 | +0.346 | +0.098 | 28% | +3.19 | 3.3e-9 | 1.00 |
| 4/12 | +0.365 | +0.052 | 14% | +1.39 | 3.3e-9 | 1.00 |
| 5/11 | +0.363 | +0.077 | 21% | +2.09 | 3.3e-9 | 1.00 |
| 6/10 | +0.368 | +0.071 | 19% | +2.35 | 3.3e-9 | 1.00 |
| 7/9 | +0.382 | +0.062 | 16% | +2.29 | 3.3e-9 | 1.00 |
| 8/8 | +0.380 | +0.059 | 16% | +2.20 | 3.3e-9 | 1.00 |

- **H1:** All **24 of 24** partitioned runs distinguish active from idle
  (each p=0.0001). The effect always has the same sign as the control effect.
- **H2:** Results are nearly identical to H1 (treatment SNR +1.43 to +5.35;
  all 24 runs at p=0.0001). The H1 result is therefore not caused by which
  sets survive the filter.
- **H3:** Treatment miss counts are not label-dependent at any split (no
  individual p < 0.05; Fisher p ≥ 0.958). In the **controls**, miss counts
  *are* label-dependent from A=5 onward (Holm p ≤ 1.3e-8). That is a genuine
  eviction channel: once the monitor fills at least 5 of 16 ways, AES
  activity evicts monitor lines. Partitioning removes that component
  completely.
- **H4:** Unfiltered means agree with the predeclared result (treatments
  non-significant, Holm p = 1.00; controls Holm p = 3.3e-9). This reproduces
  the collapse and also shows that it does not depend on choosing max-set
  over interval-mean.

## A.6 Interpretation

1. **The control leak is mostly a timing effect on LLC hits.** At A=1 to 3,
   control probes essentially never miss, yet active intervals are slower by
   0.25–0.35 cycles per line. That shift is consistent with contention for
   shared resources in the LLC path (tag and data ports, crossbar, MSHRs).
   This mechanism is inferred, not instrumented. At A ≥ 5 an eviction
   component (H3) appears as well.
2. **Way partitioning removes the eviction component but not the timing
   component.** H3 goes to zero in every treatment. Hit-timing still carries
   the AES activity label in every treatment run: at 92% of the control
   effect for 1/15, and at 14–32% for 2/14 through 8/8. Why the 1/15
   reduction is so much smaller than at A ≥ 2 was not determined.
3. **The predeclared collapse is a masking effect.** The monitor's self-evicted
   probes add ~120-cycle outliers to 20–25% of records. That raises the pooled
   standard deviation far above a 0.05–0.25-cycle signal, so both max-set and
   unfiltered statistics lose power. The outliers are label-independent, so
   removing them recovers the signal.
4. **What the main result still supports.** Under the predeclared rule, no
   allocation was distinguishable after Fisher and Holm correction, and that
   finding reproduces exactly. The evidence does **not** support reading it
   as "LLC way partitioning makes AES activity undetectable to a co-resident
   monitor". A monitor that discards its own miss outliers detects the
   activity at every tested allocation.

## A.7 Limitations of this appendix

- It is post-hoc. The tests, the 20-cycle band, and the hit-only framing were
  chosen after the data had been seen, so the p-values describe evidence but
  are not confirmatory. A predeclared replication is needed (A.9).
- Fisher combination assumes the three seed-level tests are independent. The
  deterministic simulator may make that assumption optimistic. Every H1 and
  H2 p-value is already at the permutation floor, so this does not change the
  conclusion.
- Sets that are slow in every interval (A.3) never contribute to H1 or H2.
  That is 16 sets at A ≥ 4 in both arms, set 128 at A=3, and set 255 in
  treatments at A ≥ 3. H1 and H2 therefore use at most 239–256 of the 256
  sets. The exclusion barely differs between arms (one extra set in
  treatments), and it does not depend on the labels.
- The queueing mechanism behind the hit-timing signal is inferred from latency
  data. No gem5 port, crossbar, or MSHR occupancy statistic was examined.
- All results come from gem5 timing, with the same platform limits as Section
  9 of the main report (4 KiB L1D stress configuration, `TimingSimpleCPU`,
  deterministic public seeds).

## A.8 Effect on claims in the main report

| Location | Current wording | Status after this appendix |
|---|---|---|
| §1 | "`1/15` is the first tested allocation and the stable collapse point" | Still true under the predeclared rule; should say it holds for that statistic only |
| §1 | "a local monitor on core 0 can no longer distinguish" (research question) | Not supported. A hit-filtered monitor distinguishes all 8 allocations |
| §4 | "These checks establish that the result is not caused by monitor self-thrashing" | Contradicted. 20–25% of partitioned probe walks are self-evicted (A.3) |
| §6 | `7/9` named as the only individually significant treatment seed | Incomplete. `4/12`, seed `0x5764A5E5`, p=0.0202 |
| §5 | Rule "implemented and tested before the new measurements" | Cannot be confirmed from file timestamps (A.2) |
| §7 | +18–19 pp monitor LLC miss change reported as a performance cost | Also the signature of self-eviction, which affects the security result |
| §9 | Shared MSHRs, queues, ports and interconnect "not isolated" | Now supported by evidence: the remaining signal is consistent with this path |

## A.9 Suggested confirmatory follow-up

A follow-up experiment that would settle the question:

1. Remove the record stream from the monitor's LLC partition during
   measurement. Options: keep per-interval aggregates in registers or a buffer
   small enough to stay in L1, or tag record-buffer addresses with a third
   partition ID.
2. Predeclare H1 (hit-only interval mean, fixed band) and the max-set
   statistic before running anything.
3. Rerun the matched 1/15, 4/12 and 8/8 pairs on all three seeds. The
   predicted outcome: treatment probes miss at the control level (≈0%), and
   the predeclared max-set test becomes significant at 1/15.

## A.10 Reproduction

Run from the project root in WSL (`numpy` required; the Windows Python install
does not have it):

```bash
python3 analysis/posthoc_hit_only_20261011.py --results-root results/contention-repeated-20261001 --out results/posthoc-20261011
```

The script refuses to overwrite an existing output root. Outputs:

- `results/posthoc-20261011/posthoc_per_run.csv`: all 48 runs, with all-hit
  fraction, misses per interval, period-8 repeat fraction, and SNR, p and
  effect size for each of H1–H4.
- `results/posthoc-20261011/posthoc_summary.csv` and `posthoc_summary.json`:
  per-split means and Fisher- and Holm-combined p-values, labelled as post-hoc.
