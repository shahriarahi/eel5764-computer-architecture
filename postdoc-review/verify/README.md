# postdoc-review/verify

Every check behind a **[run-verified]** tag in `../POSTDOC_REVIEW.md`. No gem5
simulation was run for any of them. All checks are read-only with respect to the
experiment worktree, the frozen paper results and the gem5 trees; they write only
under this directory (`out/` and `_tmp/`).

Run from this directory inside WSL (`Ubuntu-26.04`). `python3 -B` keeps
`__pycache__` out of the experiment directory.

```bash
cd "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/verify"
```

| ID | What it checks | Command | Saved output |
|---|---|---|---|
| V01 | Schedule arithmetic, measured probe and prime margins, run time per N, overlap offsets | `python3 -B v01_schedule_timing.py` | `out/v01_schedule_timing.txt` |
| V02 | P1 re-analysis: slow-versus-touched table, raw effect in cycles, z versus N, permutation p | `python3 -B v02_p1_reanalysis.py` | `out/v02_p1_reanalysis.txt` |
| V03 | Behaviour of the registered z and Holm rule on noise-free synthetic data | `python3 -B v03_statistic_behaviour.py` | `out/v03_statistic_behaviour.txt` |
| V04 | Line coverage of a full encryption; noise-free power of the rule; 20-window full-AES smoke run | `python3 -B v04_full_aes_saturation.py` | `out/v04_full_aes_saturation.txt` |
| V05 | LLC replacements and monitor misses in the stored unpartitioned controls at depth 1, 4, 8 | `python3 -B v05_matched_control.py` | `out/v05_matched_control.txt` |
| V06 | Byte identity of the frozen paper probe logs across the three plaintext seeds | `python3 -B v06_cross_seed_identity.py` | `out/v06_cross_seed_identity.txt` |
| V07 | Host cores and memory, memory of one gem5 run, the 139-test suite | `bash v07_host_and_tests.sh` | `out/v07_host_and_tests.txt` |
| V08 | File overlap between the tracing extension and the defense patches; `git apply --check` of the stored defense patch on a clean tree | `bash v08_gem5_tree_overlap.sh` | `out/v08_gem5_tree_overlap.txt` |
| V09 | The overlap schedule builds from `-D` flags alone; the analysis accepts it; command syntax | `bash v09_overlap_build_and_syntax.sh` | `out/v09_overlap_build_and_syntax.txt` |
| V10 | The reference code in `../reference/` passes its 33 tests; the two source fixes apply; the 139 existing tests still pass (in a mirror copy) | `bash v10_reference_code_tests.sh` | `out/v10_reference_code_tests.txt` |
| V11 | The existing analysis on a perfectly flat probe log | `python3 -B v11_flat_log_analysis.py` | `out/v11_flat_log_analysis.txt` |
| V12 | Every build and run command of `../EXECUTION_PLAN.md`, dry-run and validated (needs V10's mirror) | `bash v12_plan_commands_dry_run.sh` | `out/v12_plan_commands_dry_run.txt` |
| V13 | A model of a contention channel: which leakage model it carries and which statistic sees it | `python3 -B v13_contention_model.py` | `out/v13_contention_model.txt` |
| V14 | The batch launcher (with a FAKE gem5: no simulation) and the deviation logger, in the mirror (needs V10 and V12) | `bash v14_launchers_and_ledgers.sh` | `out/v14_launchers_and_ledgers.txt` |

`_common.py` holds shared loaders. `_tmp/` is scratch (a mirror copy of the
experiment directory used by V10 and V12, and test builds); it can be deleted and
is rebuilt by V10. V13 is a model, not a measurement: it is cited as analysis,
never as evidence about gem5.

Timing: V02 about 1 minute, V03 about 2 minutes, V10 about 2 minutes, V12 about
30 seconds, the rest a few seconds each.

## What each check showed

* **V01.** Budgets: prime 458,752 cycles, probe 454,656. Measured probe pass at 16
  monitor ways: 196,662 worst case in P1 (2.31x headroom); 340,796 in the 20-window
  full-AES smoke run (1.33x). Worst-case bound for full AES: 393,381 cycles (1.16x).
  Run time from P1: 3.19 million simulated cycles per second, so 2.8 min at N = 500,
  11.0 min at N = 2000, 22.0 min at N = 4000. The overlap offsets
  (`OFF_PROBE = 520192`) fit for monitor depths 1 and 8.
* **V02.** In P1 "set is slow" equals "line touched" in 136,000 of 136,000 cells.
  Raw effect 2,176.7 cycles per predicted line. z / sqrt(N) is 1.7 to 1.9 from
  N = 25 to 2000, and the 16/16 gate already passes at N = 25. Permutation
  p = 1/10001.
* **V03.** z is 84.92 for a 2,642-cycle, a 10-cycle and a 1-cycle effect. A
  0.0074-cycle effect is still significant on 16/16 bytes. On data with no data
  dependence and rare one-off 2-cycle delays the rule fired in 29 of 300 runs (9.7%;
  nominal 5%). One 0.82-cycle effect gives z of 85, 59 or 15 depending on background
  jitter.
* **V04.** A full encryption touches 57.7 of 64 Te lines. The round-1 contrast is
  0.103 (about 272 cycles instead of 2,177); the last-round contrast is 0.012 (about
  33 cycles). Noise-free, the rule gives round 1 on 16/16 bytes from N = 250 and the
  last round on 16/16 from N = 1000 (0/16 at N = 500).
* **V05.** The stored unpartitioned controls at monitor depth 1, 4 and 8 have 0 LLC
  replacements and 0 monitor misses in the measurement block, against about 738,000
  AES accesses. The way-partitioned runs have 140 (1/15) and 693 (8/8).
* **V06.** Under the full defense the monitor's probe log is byte-identical across
  the three seeds at 8 of 8 allocations. Under way partitioning alone it differs at
  8 of 8 (1,425 to 5,860 of 16,384 latency records differ).
* **V07.** 20 cores, 14.6 GiB available, 0.67 GiB per gem5 run. 139 tests pass in
  14.2 s.
* **V08.** `gem5-timeslot` holds the time slots only; `gem5-respq` holds both
  defenses. The tracing extension lives entirely in `EXTRAS`; the stored defense
  patch touches no file of it and contains no line mentioning the partition manager.
  The patch applies cleanly to a clean tree at `c8222cc`.
* **V09.** The overlap schedule builds with
  `-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL`; only `monitor_leak` changes;
  without the first flag the header's static assert refuses it.
* **V10.** `test_fixes.py` fails before `apply_fixes.py` and passes after; 29 further
  new tests pass; 172 tests pass in the mirror (2 skipped: they need the stored paper
  results). On the real P1 run the effect tool reports 2,176.722 cycles per set walk
  (136.05 per probed line), 16/16 bytes, exact indicator.
* **V11.** The existing analysis raises `ValueError` (`np.nanargmax`, all-NaN slice)
  on a flat probe log.
* **V12.** 30 planned runs: 0 pre-flight failures; 5 deliberately wrong invocations
  are refused; all 30 command lines pass the baseline config's validators.
* **V13 (model).** A contention channel carries a collision count, not a line
  address. The registered rule finds 0/16 bytes; a count statistic finds it
  (permutation p = 1/10001).

* **V14.** With a fake gem5, a ten-run batch at four in parallel writes ten summary
  lines, reports the one injected deadline error as `FAIL`, and refuses a second
  start. The deviation logger appends D1 to D4 with the date, leaves the first 216
  lines of the preregistration unchanged, and refuses to log one twice.

## Not covered here

* The final text of `../EXECUTION_PLAN.md`, `../reference/docs/PROGRESS_TEMPLATES.md`
  and `../reference/README.md` was written after testing stopped at the student's
  instruction, and the two subagent reviews were not run (memo section 9).

* Anything that needs a gem5 run. Those items carry **[unverified]** in the memo,
  each with the pilot that would settle it.
* `preserve.py verify` was run once with Windows Python and reported
  `changed file (sha256 differs): .claude/handoff-nudge-state.json`. That file was
  last written at 12:58 on 2026-11-12 by other assistant sessions, 22 minutes after
  the manifest was captured and before this review started. `git status --porcelain`
  in the worktree was empty at the start and at the end of the review.
