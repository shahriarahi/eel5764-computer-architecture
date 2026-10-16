# Pre-October-11 code and results: preservation record

On October 11, 2026, a record-free monitor (`monitor_v2_l1d4k`) and a
co-primary hit-only statistic were added for a corrected rerun. This folder
proves that everything before that change is preserved and can still be
rerun.

## 1. Earlier results are untouched

`results_manifest.sha256` lists the SHA-256 of all 1,022 files that existed
under `results/` before the change (every result root except the new
`results/posthoc-20261011/`). No file in those roots has a modification time
later than October 1, 2026, 23:29. To check them at any time, run from the
project root:

```bash
sha256sum --quiet -c archive/pre-20261011/results_manifest.sha256 && echo ALL_UNCHANGED
```

## 2. Exact copies of the files changed on October 11

| Archived original | Verified against |
|---|---|
| `workloads/monitor.c` | Compiles to `d25a119b…2e79`, the `monitor_l1d4k` hash recorded in every October 1 run |
| `analysis/analyze_contention.py` | Byte size and compiled bytecode identical to the `.pyc` Python cached on October 1, 22:32 |
| `configs/run_contention.py` | Byte size and compiled bytecode identical to the `.pyc` Python cached on October 1, 22:32 |
| `workloads/build.sh` | Original byte size (974) |
| `scripts/run_contention_control.sh` | Original byte size (4,520) |

The prebuilt `workloads/monitor_l1d4k` and `workloads/victim_l1d4k` binaries
were never rebuilt or modified.

## 3. How to rerun a previous version

**With the current code (simplest).** Every new behaviour is opt-in. With the
original modes and arguments (`l1d4k` or `baseline`, and no `--monitor-sink`),
the current scripts run the original binaries with the original command line
and write the original metadata. This was verified end to end on October 11:
`seed-5764a5e5/1-15` from the repeated study was rerun into a scratch folder,
and the output was compared with the October 1 run.

| Output | Comparison |
|---|---|
| `analysis.json`, `run_meta.json`, `config.ini`, `config.json`, `workload_sha256.txt` | Byte-identical |
| 16,384 probe records in `simout.txt` | Byte-identical |
| `stats.txt` | Identical apart from host wall-clock statistics |
| `cmd.txt` | Differs only in the output directory |

The repeated study can be rerun with `scripts/run_repeated_contention_sweep.py`
and `analysis/summarize_repeated_contention.py`, which were not modified. Pass
a fresh `--results-root`, because the runner refuses to reuse an existing
root.

**With the archived originals (exact provenance).** Copy the project to a
separate folder. Overwrite the five files above with the copies from this
folder, keeping their relative paths, then run the original commands from
`RUNBOOK.md`. Do not overwrite the files in the working project.

## 4. Documents revised on October 11

`REPORT_REPEATED_20261001.md` was revised in place. It starts with a dated
revision note that lists every qualified section and quotes the replaced
wording for §4 and §5. `SUBMISSION_AUDIT_20261001.md` only gained a dated
revision block at the top; its October 1 text is unchanged below it. No
number in either document was changed.
