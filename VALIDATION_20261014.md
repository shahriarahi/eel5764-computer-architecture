# Validation of the LLC way-partitioning project (October 14, 2026)

**Scope.** This is an independent check of every step and every result
listed in `HANDOFF.md`. It covers:

- the October 1 study;
- the post-hoc analysis;
- the v2 sweep;
- the D2 investigation and rerun;
- the final v3 sweep (D3);
- the comparison;
- the Word reports.

**Method.** Each result was reproduced from raw artifacts in two ways:

1. The project's own pipeline was re-run on **scratch copies**, and its
   outputs were compared byte for byte.
2. A separate reimplementation written for this validation was run. It
   imports no project code and uses its own RNG.

In addition, one v3 matched pair and one October 1 case were re-simulated in
gem5. Every number in the documents was then compared against the result
files.

**No existing file was modified.** The 1,292 files under `results/updated run/`
and all 25 root documents hash the same before and after this validation.
The October 1 manifest still verifies, with 1,022 files reported
`ALL_UNCHANGED`. The only new files are listed in §5.

## 1. Verdict

**The final result is valid and fully reproducible.** LLC way partitioning
does not hide AES activity at any allocation from 1/15 to 8/8:

- All eight allocations are distinguishable.
- 24/24 matched pairs pass the self-eviction gate.
- There is no collapse point and no equivalence point.
- At 1/15 the treatment retains 99.6% of the control's hit-timing signal.
  From 2/14 to 8/8 it retains 69.6–85.0%.
- The cost is at most 0.029%.

Every number in `HANDOFF.md` §1, in report §12, and in both `_Updated.docx`
files matches the data. No error was found that changes any conclusion.

The findings in §3 are documentation and interpretation issues. The most
important is §3.4: two older documents still state the withdrawn "1/15
collapse" conclusion and do not point to the new result.

## 2. What was checked

| # | Claim or step | How it was checked | Result |
|---|---|---|---|
| 1 | 58 tests pass | `python3 -B -m unittest discover -s tests -t .` in WSL | **PASS**: 58/58 OK |
| 2 | Frozen file hashes (prereg D1–D3) | `sha256sum` of all 17 listed files | **PASS**: every file matches its latest logged hash |
| 3 | Binaries rebuild to their hashes | `build.sh` run on a copy of `workloads/` | **PASS**: all 9 binaries byte-identical, including v1 `d25a119b`, v2 `1edbb2d3`, v3 `0722e049` and victim `5ef763fa` |
| 4 | v1 code path unchanged | `diff` against `archive/pre-20261011/workloads/monitor.c` | **PASS**: every hunk is a pure addition inside `#ifdef` blocks |
| 5 | v3 loop touches only probe lines (D2) | `objdump` of `monitor_v3_l1d4k` | **PASS**: the loop at `0x1047a`–`0x10542` loads only `ld a4,0(a4)` (pointer chase) and stores only into the probe slot. `probe_way_count` is read once, before the loop |
| 6 | October 1 results untouched | `sha256sum -c archive/pre-20261011/results_manifest.sha256` | **PASS**: 1,022 files, `ALL_UNCHANGED` |
| 7 | v3 sweep validation counts (§12) | Independent parser over raw files | **PASS** on every item:<br>• 50 runs, 0 failed directories, 819,200 records, interval and set order and timestamps valid<br>• AES 50/50, mapping 50/50, 24/24 disjoint with 0 violations, way lists match each split<br>• 1 hash set, 50/50 v3, 100 stats blocks |
| 8 | v3 per-run analysis and summary | Project analyzer and summarizer re-run on a copy | **PASS**: all 50 `analysis.json`, `summary_v3.csv`, `summary_v3.json`, `per_seed_matched_v3.csv` and the PNG are byte-identical. The PDF differs only in its `CreationDate` |
| 9 | v3 statistics and decision rule | Independent numpy reimplementation, run with a different RNG; see the breakdown below this table | **PASS**: all 8 conclusions identical, no collapse or equivalence point |
| 10 | Holm floor `6.6e-9` | Arithmetic | **PASS**: one run's floor is p = 1/10,001. Fisher-combining three such p-values gives 4.10e-10, and Holm × 16 gives 6.56e-9 |
| 11 | October 1 study (50 runs) | Analyzer and summarizer re-run on a copy | **PASS**: 50/50 `analysis.json` and all 4 summary files byte-identical |
| 12 | Post-hoc analysis (appendix) | `posthoc_hit_only_20261011.py` with `--out` set to scratch | **PASS**: all 3 outputs byte-identical. H1 table, H3 (treatment Fisher p ≥ 0.958, controls label-dependent from A=5), and 75.6–80.8% all-hit confirmed |
| 13 | Smoke test, D1 | Copy re-analyzed; failed directory inspected | **PASS**: 2/2 identical. The failed attempt `UNPARTITIONED-A1.failed.20261011T212728` is preserved |
| 14 | v2 sweep (report §4–§6) | Copy re-analyzed and re-summarized | **PASS**: 50/50 identical, summaries identical. The §5 and §6 tables match `summary_v2.csv` |
| 15 | D2 combined summary (§11.3) | `summarize_rerun_v3.py` on a copy | **PASS**: 12/12 `analysis.json` and both CSVs identical. The JSON differs only in its embedded source path. One cosmetic rounding slip, see §3.5 |
| 16 | v1-vs-v2 comparison (§7) | `compare_v1_v2.py` with `--out` set to scratch | **PASS**: CSV and PNG byte-identical. §7.1–§7.4 match |
| 17 | Set-191 investigation | Its scripts re-run, plus an independent "always-slow set" scan | **PASS**: see the breakdown below this table |
| 18 | §12.2 path-length claim | `cmp` of 12 `probes.bin` files, rerun vs sweep-v3 | **PASS**: 6/6 controls identical, 5/6 treatments differ (seed e6 7/9 identical), as stated |
| 19 | Preregistration order | File modification times and log timestamps | **CONSISTENT**: see the timeline below this table. Modification times are weak evidence (there is no version control), but nothing contradicts the stated order |
| 20 | Updated DOCX reports | Rebuilt from a scratch tree with `build_updated_reports.py`; text checked against the CSVs | **PASS**: all asserts pass, and 18/18 zip members per file are identical to the shipped DOCX files. Every number checked. One wording issue, see §3.5 |
| 21 | Re-simulation (gem5) | One v3 matched pair, seed e5 at 8/8, with the same output-path length, plus the October 1 case seed e5 1/15 in `l1d4k` mode | **PASS** (bit-exact): see the breakdown below this table |

**Check 9 in detail.** Agreement between the reimplementation and the
project's results:

- **Exact match:** gates (D2 and original), miss and all-hit fractions,
  floors, interval means, effects, retained fraction, and every cost metric.
- **Max-set SNR:** max error 3e-15.
- **Bootstrap CI:** endpoints within 0.0011.
- **Permutation p-values:** within Monte Carlo error. Every value the
  summary reports at the floor is also at the floor here.

**Check 17 in detail.**

- Slow-walk rates match the README table exactly (1.39 / 5.86 / 29.49 / 41.26
  per 1,000 active walks, and 0 idle in the 20–100-cycle band).
- The trace has 64 `ReadSharedReq` events and 64 `WritebackDirty` events, all
  in set `0x41` way 1. `0x1040` is the only non-probe line in the monitor's
  ways.
- The address arithmetic checks out:
  - `0x11040` falls in L1D set 1;
  - the probe sets with s ≡ 15 (mod 16) also map to L1D set 1;
  - logical set 191 plus the rotation of 130 gives physical set 65.
- In v2 treatments, sets {0, 191} are always slow at A ≥ 4. In every v3 run
  (rerun and sweep) **no** set is always slow.

**Check 19 timeline.**

| Stage | Order of events |
|---|---|
| v2 | Post-hoc 21:03 → v2 analyzer, summarizer and runner 21:24–21:25 → smoke test 21:26 → D1 failure 21:27 → v2 rebuild 21:28 → sweep 21:30:41 |
| D2 | Investigation 22:52 → v3 code 23:04–23:07 → rerun 23:08:11 |
| D3 | v3 runner and summarizer 01:01–01:02 → preregistration last saved 01:02:27.8 → sweep-v3 plan 01:02:28.7 |

**Check 21 in detail.**

- **v3 pair (seed e5, control and 8/8 treatment):** `probes.bin`,
  `run_meta.json` and `stats.txt` (excluding host-time lines) are identical,
  so the re-analyzed effect, p-values and IPC are identical too. `config.*`
  differs only in the output path, and `simout.txt` only in its date and path
  header lines.
- **October 1 case:** all 16,384 probe lines, `stats.txt`, `run_meta.json`
  and `config.*` are identical.

## 3. Findings

### 3.1 The "+0.26 pp monitor LLC miss" is a one-time start-up refill, not ongoing self-eviction

The monitor's LLC miss delta is +0.2624 pp at **every** allocation, with a
standard deviation of 0 across seeds. The raw stats explain it:

| | Count |
|---|---|
| Control monitor data misses | 0 |
| Treatment monitor data misses | exactly **86 × A**, in every seed |
| Monitor data accesses, both arms | 32,768 × A (64 intervals × 2 walks × 256 sets × A lines) |

The delta is therefore 86/32,768 = 0.2624%, independent of A.

Where the timed slow walks fall:

- Every timed walk more than 100 cycles above the floor is in **interval 0**,
  the first walk after the stats reset.
- Controls have 1 such walk (set 0). Treatments have 3 (sets 0, 145, 146).

The 86 × A misses are therefore a deterministic refill at the start of
measurement, almost entirely in interval 0's untimed prime pass. Interval 0 is
idle-labelled, and the hit-only statistic drops those walks, so this does not
create or mask the signal.

- **Effect on conclusions:** none.
- **Recommendation:** where report §12, the DOCX files and the handoff quote
  "+0.26 percentage points", say that it is a one-time refill at the start of
  measurement. As written, a reader could take it for ongoing self-eviction.

### 3.2 The D2 gate is too loose to detect the confound it was built for

The D2 gate allows a 1-percentage-point difference in miss-walk fraction:

- The observed differences are at most 0.012 points.
- The v2 set-191 conflict, the real confound, caused 0.40 points, and it
  **passes** this gate. That is visible in §11.3's 4/12–6/10 rows.

So the gate cannot rule out a confound of the size that actually occurred. It
was also set after the v2 data was seen. The report says the second point;
the first is not said.

The v3 data does not depend on the gate, because there is direct evidence of
no self-eviction:

- no always-slow sets in any v3 run;
- timed misses only in interval 0;
- treatment miss walks of 3/16,384 against 1/16,384 in controls.

**Recommendation:** in any future revision, cite that direct evidence
alongside the gate, and state the gate's sensitivity.

### 3.3 The three seeds share one label schedule and one permutation sequence

All three seeds use the **same** activity schedule, with only the AES
plaintexts differing. Every permutation test also uses `random.Random(5764)`.
So the Fisher combination assumes independence between seed-level tests that
share a schedule, a shuffle sequence, and a deterministic simulator. The
documents mention the independence assumption but not these shared parts.

The conclusion does not depend on Fisher:

- Every one of the 24 v3 treatment runs is individually significant on the
  hit-only statistic at the floor, p = 1/10,001.
- A Bonferroni correction over all 24 runs still gives p ≤ 0.0024.

**Recommendation:** add one sentence to the threats sections.

### 3.4 Older documents still state the withdrawn conclusion (the most important fix)

| File | Problem |
|---|---|
| `REPORT_REPEATED_20261001.md` | §1 still says "`1/15` is the first tested allocation and the stable collapse point". The October 11 revision note only limits this to the max-set statistic. The file **never points to** `REPORT_UPDATED_RUN_20261011.md` and never says the conclusion is withdrawn. The handoff says this file "carries a revision note", but that note predates the reversal. |
| `project explanation.md` | Still teaches the 1/15 collapse point (lines 97–148). This is handoff open item 3. |
| `RUNBOOK.md` | No v2 or v3 steps (`l1d4k-v2`, `l1d4k-v3`, sweep-v3 runner, DOCX builder). This is handoff open item 2. |
| `APPENDIX_POSTHOC_20261011.md` A.6 | Its "14–32% retained" is superseded by §12 (70–85%), with no pointer. This is handoff open item 4. |
| `REPORT_UPDATED_RUN_20261011.md` §1–§8 | These sections still state the v2 answer ("7/9 and 8/8: uninterpretable", "91–100%", §8 "7/9 and 8/8 were not evaluated … remaining source not identified"). Only the top banner marks them as superseded. |
| `PREREGISTRATION_V2_20261011.md` | The closing "Caveat (D2)", which says 1/15–6/10 still use v2, is resolved by D3. It should be marked as such, as a dated note added after the fact. |
| `SUBMISSION_AUDIT_20261001.md` | The header still says "status downgraded to NOT READY" and "See `PREREGISTRATION_V2…` once it exists". The October 12 update names the new DOCX files but never says whether the status is restored. |

### 3.5 Minor numeric and wording slips (no effect on conclusions)

- **Report §11.3, final bullet:** "monitor IPC cost is 0.027–0.030%". The
  7/9 value is 0.0265%, so the range should read 0.026–0.030%.
- **Both DOCX files, §VII:** "The control effect rises from +0.347 … at A=1
  to +0.401 at A=8". The control effect is not monotone: 0.347, **0.292**,
  0.338, 0.362, 0.383, 0.391, 0.392, 0.401. Suggested wording: "ranges from
  +0.29 to +0.40".
- **"Retains 70–85%" (handoff, DOCX):** the exact range is 69.6–85.0%, and
  69.6% rounds to 70%. This is fine.
- **Interval autocorrelation:** a moving-block bootstrap (block length 4)
  gives CIs within 0.001 of the reported ones, so autocorrelation does not
  change the intervals.

### 3.6 Caveats that are correctly stated and still hold

- The mechanism (ports, crossbar, queues) is inferred, not instrumented.
- The isolation evidence is a tag-occupancy snapshot taken at each stats dump
  (`preDumpStats`), not continuous monitoring. The expanded DOCX describes it
  correctly.
- The size of the hit-timing effect depends on the monitor build. The 1/15
  control effect is +0.086 with v2 and +0.347 with v3, so "retained %" figures
  are specific to this monitor. §12.1 says so.

## 4. Recommended document fixes

Listed in priority order. All of them are text edits; none changes a result.
All were applied on October 14 (§6).

1. **`REPORT_REPEATED_20261001.md`:** add a dated note at the top saying the
   1/15 conclusion is withdrawn, with a pointer to report §12 and
   `HANDOFF.md`.
2. **`project explanation.md`:** update it to the v3 result.
3. **`REPORT_UPDATED_RUN_20261011.md`:**
   - mark §1–§8 as "v2 record (superseded)" in their headings;
   - correct 0.027 to 0.026 in §11.3;
   - describe the +0.26 pp as a start-up refill (§3.1);
   - add §3.2 and §3.3 to the threats.
4. **`RUNBOOK.md`:** add the v2 and v3 steps.
5. **Appendix A.6 and the preregistration's D2 caveat:** add pointer notes.
6. **`SUBMISSION_AUDIT_20261001.md`:** state the current status.
7. **DOCX:** "the control effect ranges from +0.29 to +0.40". This needs the
   builder changed, and the `_Updated` files regenerated as new files, per
   the project's rules.

## 5. Files created by this validation

- `VALIDATION_20261014.md`: this report.
- `results/updated run/repro-v3/`: the step-21 re-simulation. This is a new
  folder, and no earlier result was touched.
- Scratch only (session temp directory): the copies used for re-analysis,
  `independent_check.py`, `slow_walks.py`, `always_slow.py`, the step scripts
  and logs.

## 6. Fixes applied (October 14, 2026, at the user's request)

Before any edit, every changed file was copied unchanged to
`archive/pre-20261014/`, with checksums in `manifest.sha256`.

**No result file was changed, and neither was the analysis or workload code.**
The only code change is the report builder's prose. The original template
DOCX files are unchanged.

| File | Change |
|---|---|
| `REPORT_REPEATED_20261001.md` | A dated "Conclusion withdrawn" note at the top, pointing to report §12, `HANDOFF.md` and this file. The original text is unchanged. |
| `project explanation.md` | Rewritten from "The corrected experiment" onward. It now covers the record-array mistake, the v2/v3 fixes, the v3 results table, why partitioning does not stop the hit-timing channel, the costs, and the limits. The opening sections are unchanged. |
| `REPORT_UPDATED_RUN_20261011.md` | Changes:<br>• §1, §4, §5, §6 and §8 headings marked as the v2 record, with notes<br>• §11.3: 0.027% corrected to 0.026%<br>• §12: the +0.26 pp explained (§3.1)<br>• new §12.4, final threats (§3.2, §3.3, the non-monotone control effect, the snapshot isolation check)<br>• new §12.5, validation summary<br>• §12.3: note on the regenerated DOCX files |
| `RUNBOOK.md` | Changes:<br>• new top banner<br>• superseded note on §10B<br>• new **§10C** with the v2/v3 monitors, sweep, rerun, post-hoc, comparison and DOCX builder commands<br>• quick reference, file map and key facts updated |
| `APPENDIX_POSTHOC_20261011.md` | A dated note at the top and inline in A.6: 14–32% is superseded by 70–85% |
| `PREREGISTRATION_V2_20261011.md` | A dated note after "Caveat (D2)": resolved by D3. No rule, threshold or hash changed. |
| `SUBMISSION_AUDIT_20261001.md` | October 14 status: **READY**, with the list of files to submit |
| `scripts/build_updated_reports.py` | Three prose fixes. New assertions check that:<br>• all miss walks are in interval 0<br>• the seeds share one schedule<br>• every treatment run is individually significant |
| Both `_Updated.docx` files | Regenerated with the fixed builder. Word reports 3 and 5 pages, the same as before. The rendered pages were inspected. They are byte-identical to a scratch build made first. |
| `HANDOFF.md` | Status, history, file map, open items and gotchas updated |

**Afterwards:**

- All 1,292 pre-existing files under `results/updated run/` were unchanged.
- The October 1 manifest still reports `ALL_UNCHANGED`.
- The 58 tests still pass.
