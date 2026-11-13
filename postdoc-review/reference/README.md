# postdoc-review/reference

Reference files for `../EXECUTION_PLAN.md`. The plan copies them into
`experiments/aes-leakage/` in the worktree; nothing here is edited during execution.
The code was tested in a mirror copy of the experiment directory (checks V10, V12 and
V14 in `../verify/`); no gem5 simulation was run for those tests.

| File | Copied to (in the experiment directory) | What it is |
|---|---|---|
| `apply_fixes.py` | not copied; run in place | applies two exact source fixes (flat-log crash in `anova_p_min`; `preserve.py` ignores `.claude/`) |
| `tests/test_fixes.py` | `tests/` | fails before the fixes, passes after |
| `analysis/leak_followup.py` | `analysis/` | `diff` (differential test), `effect` (raw-cycle effect, permutation p, margin), `count` (collision-count test) |
| `tests/test_leak_followup.py` | `tests/` | 19 tests of the above |
| `run_leakage_defense.py` | `.` | wrapper around `run_leakage.py` that sets the time slots and the response-queue domains |
| `tests/test_run_leakage_defense.py` | `tests/` | 10 tests with a fake m5 |
| `run_arm.sh` | `.` | launches one gem5 run after pre-flight checks; `DRY_RUN=1` prints only |
| `run_batch.sh` | `.` | runs a batch file, a few runs in parallel, and writes `runs/<batch>.batch.log` |
| `batches/*.txt` | `batches/` | the run lists of blocks E1, E2, E2x and E3 |
| `log_deviations.py` | not copied; run in place | appends D1 to D4 with today's date to the two ledgers; refuses to log one twice |
| `docs/DEVIATIONS_D1_D4.md` | source text for `log_deviations.py` | the exact deviation text |
| `docs/PREREGISTRATION_OVERLAP.md` | `.` | the second preregistration |
| `docs/PROGRESS_TEMPLATES.md` | not copied | text blocks for `README.md` and `progress.md` |

`../w.sh` is the wrapper that runs one command inside WSL from the experiment
directory.
