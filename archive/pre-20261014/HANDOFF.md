# Handoff — EEL5764 Group 18 gem5 LLC way-partitioning project

Last updated: 2026-10-14. Start a new Claude Code session with:
"Read HANDOFF.md and continue."

## 1. Where things stand

The project is complete and its results are final. The only work left is
documentation tidying (§6).

**Final result (v3 sweep, `results/updated run/sweep-v3/`):**

- LLC way partitioning does **not** hide AES activity at any tested
  allocation, 1/15 through 8/8. All eight are distinguishable after Fisher
  combination and Holm correction, under both statistics.
- The partitioned monitor keeps **100%** of its control's hit-timing signal
  at 1/15, and **70–85%** at 2/14 through 8/8.
- Every allocation passes the self-eviction gate (24/24 pairs).
- There is no stable collapse point and no equivalence point.
- Performance cost is 0.03% or less.
- Interpretation: partitioning removes eviction-based contention but not the
  sub-cycle hit-latency channel. That channel is attributed to shared LLC
  ports, crossbar or queues; the attribution is inferred, not instrumented.

**Retracted:** the October 1 claim that "1/15 is a stable collapse point,
partitioning works". It was an artifact of the monitor evicting its own
probe lines.

## 2. How we got here (short history)

| Date | Step | Outcome |
|---|---|---|
| Oct 1 | Original repeated study (`results/contention-repeated-20261001/`) | Reported "1/15 secure". Numbers reproduce exactly, but the conclusion is invalid. |
| Oct 11 | Post-hoc analysis (`APPENDIX_POSTHOC_20261011.md`) | The monitor's 384 KiB record array evicted 20–25% of its probe lines, in treatments only. |
| Oct 11 | v2 monitor (record-free, `probes.bin`); preregistration; full sweep | 1/15–6/10 distinguishable; 7/9 and 8/8 failed the self-eviction gate |
| Oct 11 | Investigation (`results/updated run/investigation-set191/`) | The gate counted AES-driven delays as misses; the real self-eviction was the global `probe_way_count` line |
| Oct 11 | D2: v3 monitor (hot state in registers), miss-based gate, rerun of 7/9 and 8/8 | Both distinguishable |
| Oct 12 | D3: full v3 sweep (50 processes) | **Final result.** All eight distinguishable. |
| Oct 12 | Updated DOCX reports generated | New files; originals kept |

## 3. Key files

**Documents (project root)**

| File | Role |
|---|---|
| `REPORT_UPDATED_RUN_20261011.md` | **Main technical report.** §12 is the final v3 result; §1–11 are the supporting record. |
| `Group18_EEL5764_Final_Project_Report_Updated.docx` | **Submission report** (short, 3 pages), built from v3 data |
| `Group18_EEL5764_Final_Project_Report_Expanded_Updated.docx` | **Submission report** (expanded, 5 pages) |
| `PREREGISTRATION_V2_20261011.md` | Decision rules, frozen file hashes, deviations D1–D3 |
| `APPENDIX_POSTHOC_20261011.md` | Post-hoc analysis of the October 1 data. Its A.6 attenuation estimate is superseded by §12. |
| `REPORT_REPEATED_20261001.md` | October 1 report, with a revision note added at the top |
| `SUBMISSION_AUDIT_20261001.md` | Audit; its October 11–12 revision block points to the new DOCX files |
| `archive/pre-20261011/` | Exact pre-edit sources, the results checksum manifest, and a README on rerunning old versions |

**Results (`results/`)**

| Folder | Contents |
|---|---|
| `contention-repeated-20261001/` | Original study. **Never modify.** |
| `posthoc-20261011/` | Post-hoc hit-only analysis of the original data |
| `updated run/sweep-v3/` | **Final results:** `summary_v3.csv`, `summary_v3.json`, `per_seed_matched_v3.csv`, `repeated_v3.png` |
| `updated run/sweep/` | v2 sweep (supporting) |
| `updated run/rerun-7-9-8-8/` | D2 rerun |
| `updated run/smoke/` | Smoke test, including the preserved failed attempt |
| `updated run/comparison/` | v1-vs-v2 comparison table and figure |
| `updated run/investigation-set191/` | Trace evidence for the set-191 conflict |

**Code: monitor variants.** One source file, `workloads/monitor.c`; the
variant is chosen by compile flag.

| Binary | Flags | SHA-256 prefix | Runner mode |
|---|---|---|---|
| `monitor_l1d4k` (v1, original) | none | `d25a119b` | `l1d4k` |
| `monitor_v2_l1d4k` | `-DMONITOR_PROBE_SINK_FILE` | `1edbb2d3` | `l1d4k-v2` |
| `monitor_v3_l1d4k` (**final**) | `-DMONITOR_PROBE_SINK_FILE -DMONITOR_HOT_STATE_IN_REGISTERS` | `0722e049` | `l1d4k-v3` |

**Code: pipeline scripts**

| Script | Purpose |
|---|---|
| `scripts/run_repeated_contention_sweep_v3.py` | Final 50-process sweep |
| `analysis/summarize_sweep_v3.py` | Final decision rule |
| `scripts/run_rerun_v3.py` | D2 rerun of 7/9 and 8/8 |
| `analysis/summarize_rerun_v3.py` | Combined summary for the D2 rerun |
| `scripts/run_repeated_contention_sweep_v2.py` | v2 sweep |
| `analysis/summarize_repeated_contention_v2.py` | v2 summary |
| `analysis/analyze_contention.py` | Per-run analysis; reads `probes.bin` and computes the hit-only statistic for file-sink runs |
| `analysis/posthoc_hit_only_20261011.py` | Post-hoc analysis of the original data |
| `analysis/compare_v1_v2.py` | v1-vs-v2 comparison |
| `scripts/build_updated_reports.py` | Builds both updated DOCX files; uses `scripts/docx_report_builder.py` |
| `configs/run_contention.py` | gem5 config; options `--monitor-sink file`, `--monitor-variant v3` |
| `tests/` | 58 tests, all passing |

## 4. Environment and how to run things

- **Host:** Windows. gem5 runs in **WSL2 `Ubuntu-26.04`**. The source tree
  is at `~/eel5764/gem5`, the binary at `build/RISCV/gem5.opt` (v25.1.0.1).
  The partition-manager extension is in `gem5_ext/`.
- Run simulations and analysis from the project root inside WSL. The
  Windows Python has no numpy.

```bash
wsl.exe -d Ubuntu-26.04 -e bash -lc "cd '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture' && <command>"
```

- **Tests:**

```bash
python3 -B -m unittest discover -s tests -t .
```

- **Rebuild the workloads:** `workloads/build.sh`. Rebuilding reproduces all
  three hashes above.
- **Rerun the final sweep** into a new folder (about 45 min; the runner
  refuses to reuse an existing root):

```bash
python3 scripts/run_repeated_contention_sweep_v3.py --results-root "results/updated run/sweep-v3-repro"
```

- **Rebuild the DOCX reports** with the Windows Python, standard library
  only. It refuses to overwrite, so delete the `_Updated` files first:

```bash
python -I -B -X utf8 scripts/build_updated_reports.py
```

- **Check that the October 1 results are untouched:**

```bash
sha256sum --quiet -c archive/pre-20261011/results_manifest.sha256 && echo ALL_UNCHANGED
```

## 5. Rules and preferences

These are also stored in Claude's project memory.

- **Never modify earlier runs or results.** New results go in new folders
  under `results/updated run/`. Earlier code paths stay the default; new
  behaviour is opt-in through a compile flag, runner mode or CLI option.
  After any change to `monitor.c`, check that the v1 and v2 binaries still
  rebuild to their hashes.
- **Write new documents as new files.** Don't overwrite the originals,
  including the original DOCX files.
- **Logging changes:** any change to the analysis rules or the monitor after
  data exists is logged as a deviation in `PREREGISTRATION_V2_20261011.md`
  before rerunning.
- **Recommendations:** the user prefers that Claude go with its own
  recommendation rather than offer A/B/C choices. Still ask before
  installing packages, deleting outside `./results`, overwriting user files,
  or starting long (more than 2 min) simulation runs that weren't requested.
- **Scope:** simulator only, public key and public inputs, activity
  detection only. No key recovery.

## 6. Open items (all optional)

1. Open both `_Updated.docx` reports in Microsoft Word and check the page
   breaks. They were rendered via a Word-to-PDF export and look fine.
2. `RUNBOOK.md` hasn't been updated with the v2/v3 steps (`l1d4k-v2` and
   `l1d4k-v3` modes, the v3 sweep runner, the DOCX builder).
3. `project explanation.md`, the beginner explanation, still describes the
   October 1 conclusion.
4. Add a one-line note to `APPENDIX_POSTHOC_20261011.md` A.6 pointing to
   report §12, since its 14–32% attenuation estimate is superseded.
5. The aligned proposal DOCX describes the original method only. It doesn't
   claim results, so revising it is optional.
6. Science extensions, if wanted:
   - instrument LLC port, crossbar and MSHR occupancy to confirm the timing
     channel;
   - test bandwidth partitioning;
   - more seeds;
   - a larger L1D.

## 7. Gotchas

- **Path length matters.** v3 runs are byte-reproducible only with the same
  output-path length; with a different length the summary statistics still
  agree to three decimals. The monitor receives the probe-file path as an
  argument, which shifts its stack layout.
- **Rendering tools.** The host has no pandoc, LibreOffice or pdftoppm. To
  render a DOCX:
  1. Export it to PDF through Word COM in PowerShell
     (`Word.Application`, `ExportAsFixedFormat(path, 17)`).
  2. Render the PDF pages to PNG with the WinRT `Windows.Data.Pdf` API.
- **`gem5 --debug-ignore` didn't filter the L1 caches.** LLC traces then
  include L1 lines and get large (about 1.2 GB for 2 intervals). Write
  traces to a temp folder and filter them afterwards.
- **Statistical floor.** Holm-adjusted p-values of `6.6e-9` are the
  permutation floor for 3 seeds × 16 tests, not exact values.
