# Execution log

Plan: `postdoc-review/EXECUTION_PLAN.md`. Executor: Claude Sonnet 5.5. Started 2026-11-12.
Reading list (plan "Kickoff") read in full before step 0.1: the plan, `POSTDOC_REVIEW.md`
(sections 1 to 9), `DISCUSSION_BRIEF.md`, `PREREGISTRATION_DRAFT.md`, `progress.md`,
`reference/docs/DEVIATIONS_D1_D4.md`, `reference/docs/PREREGISTRATION_OVERLAP.md`,
`reference/README.md`. Nothing in the plan crosses the four guardrails for Phases 0 to 2.

## Phase 0. Orientation and baseline

### 0.1 Starting state

Command (Git Bash):

```
WT=".../.codex-tmp/aes-leakage-worktree"; git -C "$WT" status --porcelain; echo "porcelain-lines=$(git -C "$WT" status --porcelain | wc -l)"; git -C "$WT" rev-parse --short HEAD; git -C "$WT" branch --show-current
```

Output:

```
porcelain-lines=0
434b16b
experiment/aes-leakage
```

Acceptance: `porcelain-lines=0`, `434b16b`, `experiment/aes-leakage`. All three: PASS.

### 0.2 Wrapper and test suite

Command: `W: pwd; nproc; python3 -B -m unittest discover -s tests -t . 2>&1 | tail -4`

Output:

```
/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage
20
----------------------------------------------------------------------
Ran 139 tests in 13.991s

OK
```

Acceptance: `Ran 139 tests` and `OK`: PASS.

### 0.3 Reference files present

Command: `W: ls <reference> <reference>/batches <reference>/tests <reference>/docs`

Output:

```
postdoc-review/reference:
README.md
analysis
apply_fixes.py
batches
docs
log_deviations.py
run_arm.sh
run_batch.sh
run_leakage_defense.py
tests

postdoc-review/reference/batches:
e1-diff.txt
e1-full.txt
e2-explore.txt
e2-main.txt
e3-defense.txt

postdoc-review/reference/docs:
DEVIATIONS_D1_D4.md
PREREGISTRATION_OVERLAP.md
PROGRESS_TEMPLATES.md

postdoc-review/reference/tests:
test_fixes.py
test_leak_followup.py
test_run_leakage_defense.py
```

Acceptance: every name the plan lists appears (`apply_fixes.py`, `log_deviations.py`,
`run_arm.sh`, `run_batch.sh`, `run_leakage_defense.py`, `analysis`, `README.md`; five
batch files; three test files; three doc files): PASS.

### 0.4 Log created

This file. Written 2026-11-12 after 0.1 to 0.3.

## CHECKPOINT 0: reported; user wrote "go".

## Phase 1. Fixes and new analysis code (no gem5)

### 1.1 Failing test first

Command: `W: cp <reference>/tests/test_fixes.py tests/ && python3 -B -m unittest tests.test_fixes 2>&1 | tail -3`

```
Ran 4 tests in 0.893s

FAILED (failures=1, errors=2)
```

Acceptance: fails now, as expected: PASS.

### 1.2 Apply the two source fixes

Command: `W: python3 -B <reference>/apply_fixes.py . && python3 -B -m unittest tests.test_fixes 2>&1 | tail -3`

```
applied: analysis/aes_leak_analysis.py
applied: preserve.py
Ran 4 tests in 0.679s

OK
```

Acceptance: both `applied:` lines and `OK`: PASS.

### 1.3 New modules, launchers, batch lists, tests

Command: `W: R=<reference>; cp analysis/leak_followup.py, run_leakage_defense.py, run_arm.sh, run_batch.sh, batches/*.txt, the two test files; python3 -B -m unittest tests.test_leak_followup tests.test_run_leakage_defense 2>&1 | tail -3`

```
Ran 29 tests in 11.313s

OK
```

Acceptance: `Ran 29 tests`, `OK`: PASS.

### 1.4 Whole suite

Command: `W: python3 -B -m unittest discover -s tests -t . 2>&1 | tail -4`

```
----------------------------------------------------------------------
Ran 172 tests in 25.127s

OK
```

Acceptance: `Ran 172 tests` and `OK`: PASS.

### 1.5 Tools on the stored runs

Command (as in the plan):
`W: python3 -B analysis/leak_followup.py diff --a runs/p0b-r1-scrub-n20 --b runs/p0c-r1-scrub-n20 --allow-same-seed | tail -1; python3 -B analysis/leak_followup.py effect --run-dir runs/p1-r1-scrub-n2000 --nperm 10000 --out-json runs/p1-r1-scrub-n2000.effect.json --out-md runs/p1-r1-scrub-n2000.effect.md | grep -E "p_xor_k|p_only|exact indicator|RUN HEALTH"`

First run printed, for the `effect` part:

```
| p_xor_k | 2176.722 | 136.0451 | 16/16 | 16/16 |
| p_only | -142.009 | -8.8756 | 0/16 | 0/16 |
Slow-versus-touched over the 68 table-line sets: touched and slow 29095, touched and fast 0, untouched and slow 0, untouched and fast 106905 (136000 cells); exact indicator: True.
RUN HEALTH: PASS
```

and NOTHING for the `diff ... | tail -1` part. Cause (diagnostic re-run, no file changed
in the experiment directory): the diff tool ends its output with a blank line after the
verdict, so `tail -1` returns an empty line. Full tail of the re-run, exit status 0:

```
| sets with a latency difference | 0 |
| largest latency difference (cycles) | 0 |

sha256 A `bdc4b47858c2533f56f0fe585666d03cf0605b14073b895a16125998d3f1f0fa`
sha256 B `bdc4b47858c2533f56f0fe585666d03cf0605b14073b895a16125998d3f1f0fa`

DIFF VERDICT: IDENTICAL

```

Acceptance: `DIFF VERDICT: IDENTICAL` (present, one line above the last blank line),
`p_xor_k` row, `p_only` row (starts `| p_only | -142.009`, ends `| 0/16 | 0/16 |`),
`exact indicator: True`, `RUN HEALTH: PASS`: PASS on content. Deviation from the plan's
literal command: with `| tail -1` the verdict line is not shown. Reported at Checkpoint 1.
Later steps 3.4 and 4.5 use `tail -1` on a `.md` file; I will check the verdict line
explicitly there if `tail -1` comes back empty.

**Slip, disclosed:** the diagnostic re-run wrote its output to `/tmp/diff15.out` inside
WSL, which is outside the places the plan allows me to write. I deleted it immediately
(`ls /tmp/diff15.out` -> `No such file or directory`). It touched nothing in the
repository or in any gem5 tree. I will use the pipe-to-`cat -A | tail` form instead of a
temp file from now on.

### 1.6 Pre-flight without gem5

Command: `W: sh build.sh 500 2>&1 | tail -1; for b in e1-diff e1-full; do DRY_RUN=1 bash run_batch.sh batches/$b.txt | tail -1; done`

```
wrote /mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage/build/n500/build_manifest.json (6 binaries)
DRY RUN: pre-flight passed, nothing was run
DRY RUN: pre-flight passed, nothing was run
```

Acceptance: manifest line with `(6 binaries)` and two `DRY RUN: pre-flight passed`: PASS.

### Worktree state after Phase 1 (read-only check, not a plan step)

`git status --porcelain`: 13 lines, all under `experiments/aes-leakage/`; branch
`experiment/aes-leakage`, HEAD `434b16b`, nothing committed.

```
 M experiments/aes-leakage/analysis/aes_leak_analysis.py
 M experiments/aes-leakage/preserve.py
?? experiments/aes-leakage/analysis/leak_followup.py
?? experiments/aes-leakage/batches/
?? experiments/aes-leakage/build/n500/
?? experiments/aes-leakage/run_arm.sh
?? experiments/aes-leakage/run_batch.sh
?? experiments/aes-leakage/run_leakage_defense.py
?? experiments/aes-leakage/runs/p1-r1-scrub-n2000.effect.json
?? experiments/aes-leakage/runs/p1-r1-scrub-n2000.effect.md
?? experiments/aes-leakage/tests/test_fixes.py
?? experiments/aes-leakage/tests/test_leak_followup.py
?? experiments/aes-leakage/tests/test_run_leakage_defense.py
```

## CHECKPOINT 1 (analysis code changed): reported; user wrote "D1 to D3 approved" (decision B).

## Phase 2. Log D1 to D3, document, commit (no gem5)

### 2.1 Deviations logged before any Phase E data

Command: `W: python3 -B <reference>/log_deviations.py . D1 D2 D3 && grep -c "^\* \*\*D[0-9] (" PREREGISTRATION_DRAFT.md progress.md`

```
appended D1, D2, D3 to PREREGISTRATION_DRAFT.md (dated 2026-11-12)
appended D1, D2, D3 to progress.md (dated 2026-11-12)
PREREGISTRATION_DRAFT.md:4
progress.md:4
```

Acceptance: two `appended D1, D2, D3` lines, `:4` and `:4`: PASS.

### 2.2 Ledgers updated

Edits (Edit tool, experiment directory, text from `PROGRESS_TEMPLATES.md`):

* `README.md`: the `PREREGISTRATION_DRAFT.md` row now reads "(frozen at `675c047`; deviations
  in its section 11)".
* `README.md`: four rows (`analysis/leak_followup.py`, `run_arm.sh`, `run_batch.sh`,
  `run_leakage_defense.py`) inserted directly after the `analysis/power_synth.py` row.
* `progress.md`: block "Phase E preparation (2026-11-12)" inserted directly before
  `## Environment changes made for Phase A and B`. Placeholders filled from this log:
  step 1.1 line `FAILED (failures=1, errors=2)`; step 1.5 verdict `DIFF VERDICT: IDENTICAL`;
  step 1.5 row `p_xor_k | 2176.722 | 136.0451 | 16/16 | 16/16` with the pipes written as `\|` so
  the table cell stays one cell (the template's literal text would have split the row);
  exact indicator `True`; test line `Ran 172 tests`, `OK` (step 1.4 line quoted).

Suite after the edits (`W: python3 -B -m unittest discover -s tests -t . 2>&1 | tail -4`):

```
----------------------------------------------------------------------
Ran 172 tests in 25.262s

OK
```

Acceptance: `Ran 172 tests`, `OK`: PASS.

### 2.3 Pin and commit

Command (Git Bash): `cd "$EXP" && python -B preserve.py capture && python -B preserve.py verify`

```
CAPTURED 269 files (base 45d21e259c)
PRESERVED: 269 files hash-match; frozen trees and everything outside experiments/aes-leakage/ unchanged since 45d21e259c
```

Before `git add`, `git status --porcelain` listed 17 paths, all under `experiments/aes-leakage/`
(6 modified, 11 untracked); 0 paths outside it.

Commit command: plan's step 2.3 `git add -A experiments/aes-leakage && git commit -q -m ... -m ...`,
with a third `-m` carrying the session's `Co-Authored-By` attribution line (the plan's text
is otherwise unchanged).

```
6986be8
0
experiment/aes-leakage
6986be8 Phase E preparation: differential test, effect size, deviations D1 to D3
```

Acceptance: 7-character hash and `0`: PASS. `git log 434b16b..HEAD` shows only this commit.
**COMMIT_PREP = 6986be8.** Nothing pushed, branch unchanged, no amend or rebase.

## CHECKPOINT 2 (before any gem5 run): reported; user wrote "go".

## Phase 3. Block E1: window schedule (gem5, `~/eel5764/gem5-leak`, no interconnect defense)

### 3.1 Ten differential arms (background)

Command: `W: bash run_batch.sh batches/e1-diff.txt 4` (Bash tool, `run_in_background`).
Exit code 0. `runs/e1-diff.batch.log`:

```
batch e1-diff started 2026-11-12 18:09:48, 4 in parallel
e1-c8-s1-n500 gem5_exit=0 seconds=177 OK 
e1-c8-s2-n500 gem5_exit=0 seconds=177 OK 
e1-c1-s1-n500 gem5_exit=0 seconds=182 OK 
e1-c1-s2-n500 gem5_exit=0 seconds=179 OK 
e1-w8-s1-n500 gem5_exit=0 seconds=179 OK 
e1-w8-s2-n500 gem5_exit=0 seconds=177 OK 
e1-w8-s3-n500 gem5_exit=0 seconds=177 OK 
e1-w1-s1-n500 gem5_exit=0 seconds=184 OK 
e1-w1-s2-n500 gem5_exit=0 seconds=183 OK 
e1-w1-s3-n500 gem5_exit=0 seconds=181 OK 
batch e1-diff finished 2026-11-12 18:18:46
BATCH RESULT: PASS
```

Acceptance: last line `BATCH RESULT: PASS`; ten lines ending in `OK`: PASS. Wall time 8 min 58 s
(18:09:48 to 18:18:46); the plan expected about 9 minutes.

### 3.2 Two unprotected full-AES runs (background)

Command: `W: bash run_batch.sh batches/e1-full.txt 2` (`run_in_background`). Exit code 0.
`runs/e1-full.batch.log`:

```
batch e1-full started 2026-11-12 18:18:54, 2 in parallel
e1-p2a-s1-n2000 gem5_exit=0 seconds=606 OK 
e1-p2b-s1-n2000 gem5_exit=0 seconds=670 OK 
batch e1-full finished 2026-11-12 18:30:04
```

The batch's own output ends `BATCH RESULT: PASS`. Acceptance: `BATCH RESULT: PASS`: PASS. No
`probe_deadline` error (an `error=` line would have made `run_arm.sh` print something other
than `OK`). Wall time 11 min 10 s (plan: 11 to 15 minutes).

### 3.3 Registered analysis and run checks on all twelve runs: FAILED, STOPPED

Command (as in the plan): `W: for n in $(grep -h -v "^#" batches/e1-diff.txt batches/e1-full.txt | cut -d" " -f1); do python3 -B analysis/aes_leak_analysis.py analyze --run-dir runs/$n --nperm 20 --out-json ... --out-md ... > runs/$n.analysis.log 2>&1; echo "$n analyze_exit=$? $(tail -1 runs/$n.analysis.log)"; done`

```
e1-c8-s1-n500 analyze_exit=0 RUN CHECKS: PASS
e1-c8-s2-n500 analyze_exit=0 RUN CHECKS: PASS
e1-c1-s1-n500 analyze_exit=0 RUN CHECKS: PASS
e1-c1-s2-n500 analyze_exit=0 RUN CHECKS: PASS
e1-w8-s1-n500 analyze_exit=1 RUN CHECKS: FAIL
e1-w8-s2-n500 analyze_exit=1 RUN CHECKS: FAIL
e1-w8-s3-n500 analyze_exit=1 RUN CHECKS: FAIL
e1-w1-s1-n500 analyze_exit=1 RUN CHECKS: FAIL
e1-w1-s2-n500 analyze_exit=1 RUN CHECKS: FAIL
e1-w1-s3-n500 analyze_exit=1 RUN CHECKS: FAIL
e1-p2a-s1-n2000 analyze_exit=0 RUN CHECKS: PASS
e1-p2b-s1-n2000 analyze_exit=0 RUN CHECKS: PASS
```

Acceptance (twelve lines, each `analyze_exit=0 RUN CHECKS: PASS`): **NOT MET**, six of twelve fail.

Failure rule applied (read the log; re-run once; at most one more diagnostic that changes no file):

* Log read: in every one of the six `.analysis.md` files, line 15 is
  `| way_isolation | FAIL | stats lack wayOccupancy |`. All other checks pass for the
  partitioned runs (`e1-w8-s1-n500`: `aes_self_test_pass`, `config_matches_simout`,
  `checksum_matches`, `monitor_status_pass` all PASS; `monitor records=128000 windows=500 errors=[]`).
* Re-run once, stdout only (no output files written): same result,
  `| way_isolation | FAIL | stats lack wayOccupancy |`, `RUN CHECKS: FAIL`.
* Diagnostic (read-only): `grep -c wayOccupancy runs/e1-w8-s1-n500/stats.txt` = 96, so the
  stats are there. Their spelling is
  `system.llc.partitioning_manager.wayOccupancy_p0::way0   256   # Valid blocks per [partition][way]...`.
  The stored paper run `results/8-8/stats.txt` uses the same spelling.
* Cause: `analysis/aes_leak_analysis.py:383`,
  `_WAY_OCC = re.compile(r"^\S+?::(p\d+|other)::way(\d+)\s+(\d+)\b")`, requires
  `::p0::way0` after the stat name; gem5 writes `_p0::way0`. `parse_way_occupancy` therefore
  returns `{}`, `isolation_violations` is skipped (`violations = -1`, line 697), and the check
  prints "stats lack wayOccupancy" (line 623). The test fixtures
  (`tests/test_analysis.py:62-68`) and the synthetic generator (`analysis/aes_leak_analysis.py:970`)
  use the same wrong spelling `wayOccupancy::p0::way0`, which is why 172 tests pass while a real
  partitioned run cannot. No earlier run was partitioned (P0, P1 and the smoke runs were not).
* Incidental, not a check result: the first lines of `e1-w8-s1-n500/stats.txt` show
  `wayOccupancy_p0::way0..way7 = 256`, `way8..way13 = 0`, `wayOccupancy_p1::way8 = 197`, and
  `p1::way0, way7, way15 = 0`. This looks like isolation but I did NOT compute the metric, so
  `way_isolation` is unproven for these six runs.

Nothing was changed to make the check pass. Not run: 3.4 onward. Files written by 3.3 are the
plan's named `runs/<n>.analysis.{json,md,log}` for all twelve runs. Stopped under rule (b).

CHECKPOINT (unplanned): reported to the user with one recommendation; user wrote "Go".

### 3.3a Fix of the isolation-check parser (approved by the user, outside the plan's file list)

Scope: tool bug, not a protocol deviation. The gate is unchanged (`violations == 0`, the
proposal's isolation metric); only the stat-name pattern that feeds it changed.

1. Test first. Added class `WayIsolationRealGem5Spelling` (one test method) to
   `tests/test_analysis.py`, after `WayIsolation`, leaving every existing test untouched. Its
   fixture lines use gem5's real spelling `wayOccupancy_p0::way0` (8/8 layout, 48 rows).
   Command: `W: python3 -B -m unittest tests.test_analysis.WayIsolationRealGem5Spelling 2>&1 | tail -8`

   ```
       self.assertEqual(len(occ), 48)             # 3 rows x 16 ways
   AssertionError: 0 != 48
   Ran 1 test in 0.022s
   FAILED (failures=1)
   ```

   (It fails now, for the stated reason: the parser reads 0 of 48 rows.)

2. Fix. `analysis/aes_leak_analysis.py:383`, one line plus a two-line comment:
   `r"^\S+?::(p\d+|other)::way(\d+)\s+(\d+)\b"` became
   `r"^\S+?(?:::|_)(p\d+|other)::way(\d+)\s+(\d+)\b"`. Strictly additive: everything the old
   pattern accepted is still accepted.

3. Green. `W: python3 -B -m unittest tests.test_analysis.WayIsolationRealGem5Spelling tests.test_analysis.WayIsolation 2>&1 | tail -4`
   gave `Ran 5 tests in 0.087s`, `OK`. Whole suite:

   ```
   Ran 173 tests in 25.152s

   OK
   ```

   **From here on the plan's "Ran 172 tests" acceptances read "Ran 173 tests".**

4. Re-ran step 3.3 (same command, restricted to the six `e1-w*` runs; analysis only, no gem5):

   ```
   e1-w8-s1-n500 analyze_exit=0 RUN CHECKS: PASS
   e1-w8-s2-n500 analyze_exit=0 RUN CHECKS: PASS
   e1-w8-s3-n500 analyze_exit=0 RUN CHECKS: PASS
   e1-w1-s1-n500 analyze_exit=0 RUN CHECKS: PASS
   e1-w1-s2-n500 analyze_exit=0 RUN CHECKS: PASS
   e1-w1-s3-n500 analyze_exit=0 RUN CHECKS: PASS
   ```

   Plan's check `W: grep -c "way_isolation | PASS" runs/e1-w*.analysis.md`: six files, each `:1`.
   Detail line in all six: `| way_isolation | PASS | valid LLC blocks outside the assigned ways: 0 |`.

Step 3.3 acceptance (twelve lines `analyze_exit=0 RUN CHECKS: PASS`; six partitioned files show
`way_isolation | PASS`): now MET (the six unpartitioned lines are from the first run above).
Recorded in `progress.md` (step 3.6) as a tool bug fix and in the E1 commit message.

### 3.4 Differential tests (deviation D1)

Command (as in the plan; each line also writes `runs/e1-<arm>.diff-<a>-<b>.{json,md}`):
`W: for p in "c8 s1 s2" "c1 s1 s2" "w8 s1 s2" "w8 s1 s3" "w8 s2 s3" "w1 s1 s2" "w1 s1 s3" "w1 s2 s3"; do set -- $p; python3 -B analysis/leak_followup.py diff --a runs/e1-$1-$2-n500 --b runs/e1-$1-$3-n500 --out-json ... --out-md ... > /dev/null; echo "e1-$1 $2 $3 exit=$? $(tail -1 runs/e1-$1.diff-$2-$3.md)"; done`

```
e1-c8 s1 s2 exit=0 DIFF VERDICT: IDENTICAL
e1-c1 s1 s2 exit=0 DIFF VERDICT: IDENTICAL
e1-w8 s1 s2 exit=0 DIFF VERDICT: IDENTICAL
e1-w8 s1 s3 exit=0 DIFF VERDICT: IDENTICAL
e1-w8 s2 s3 exit=0 DIFF VERDICT: IDENTICAL
e1-w1 s1 s2 exit=0 DIFF VERDICT: IDENTICAL
e1-w1 s1 s3 exit=0 DIFF VERDICT: IDENTICAL
e1-w1 s2 s3 exit=0 DIFF VERDICT: IDENTICAL
```

A read-only `grep -H "DIFF VERDICT" runs/e1-*.diff-*.md` confirmed the same eight verdicts (on the
`.md` files `tail -1` works; only the tool's stdout ends in a blank line, see 1.5).
Decision rule: no `INVALID`, no exit 2; all `IDENTICAL`: continue. No effect/count follow-up
needed. The review's forecast (eight `IDENTICAL`) held, including `c8` and `c1`, the arms that
test the review's claim that an unpartitioned shallow monitor is never evicted.
Caveat: no arm in E1 can show the diff tool's sensitivity by itself (all eight are IDENTICAL);
sensitivity rests on P2a, where the same log clearly depends on the plaintext (3.5).

### 3.5 Effect sizes for the unprotected runs (deviation D2)

Command (as in the plan): `W: python3 -B analysis/leak_followup.py effect --run-dir runs/e1-p2a-s1-n2000 --nperm 10000 --out-json ... --out-md ... | tail -24; python3 -B analysis/leak_followup.py effect --run-dir runs/e1-p2b-s1-n2000 --nperm 10000 --reference runs/e1-p2a-s1-n2000 --out-json ... --out-md ... | tail -28`

P2a (`e1-p2a-s1-n2000`, `full-scrub`, 16 ways):

```
| hypothesis | mean effect (cycles per set walk) | per probed line | bytes significant | significant and material |
| p_xor_k | 277.597 | 17.3498 | 16/16 | 16/16 |
| p_only | -22.868 | -1.4293 | 0/16 | 0/16 |
| shuffled | 0.449 | 0.0281 | 0/16 | 0/16 |
| lr_c_xor_k10 | 32.566 | 2.0353 | 16/16 | 16/16 |
| c_only | 2.056 | 0.1285 | 0/16 | 0/16 |
| lr_shuffled | -3.484 | -0.2177 | 0/16 | 0/16 |
statements: round1_plaintext_plus_key yes [0..15]; round1_plaintext_only no; lastround_c_xor_k10 yes [0..15]; lastround_ciphertext_only no
Slow-versus-touched over the 68 table-line sets: touched and slow 123471, touched and fast 0, untouched and slow 0, untouched and fast 12529 (136000 cells); exact indicator: True.
RUN HEALTH: PASS
```

P2b (`e1-p2b-s1-n2000`, `full-noscrub`, 16 ways, reference P2a):

```
| p_xor_k | -163.461 | -10.2163 | 0/16 | 0/16 |
| p_only | 19.854 | 1.2409 | 0/16 | 0/16 |
| shuffled | -2.829 | -0.1768 | 0/16 | 0/16 |
| lr_c_xor_k10 | 28.370 | 1.7731 | 0/16 | 0/16 |
| c_only | -1.607 | -0.1005 | 0/16 | 0/16 |
| lr_shuffled | 1.545 | 0.0966 | 0/16 | 0/16 |
statements: all four "no"
Slow-versus-touched: touched and slow 39588, touched and fast 83883, untouched and slow 8, untouched and fast 12521; exact indicator: False.
Against reference: p_xor_k -10.2163 of 17.3498 retained (-0.5888); lr_c_xor_k10 1.7731 of 2.0353 retained (0.8712)
RUN HEALTH: PASS
```

Gate G-P2a (read-only greps on the stored files):

1. `e1-p2a-s1-n2000.analysis.md`: `| round1_plaintext_plus_key | yes | [0, ..., 15] |` and `| round1_plaintext_only | no | [] |`: yes.
2. Same file: `Recall 1.000, precision 1.000; 123471 fills in the AES phase, 0 outside it, 68 before measurement; mean fills per window 61.74.`: yes.
3. `e1-p2a-s1-n2000.effect.md`: `| round1_plaintext_plus_key | yes | [0, ..., 15] |`: yes.
4. Both runs end with `RUN HEALTH: PASS`: yes, in the step 3.5 output above. (The line is printed
   to the terminal by `effect` and is not written into the `.effect.md`; a grep of the `.md`
   files for it finds nothing, which is expected, not a failure.)

**Gate G-P2a: MET.** Secondary, not part of the gate: P2a last round `lr_c_xor_k10` 16/16 bytes,
2.0353 cycles per probed line; registered `lastround_c_xor_k10` yes.

Registered z rule vs D2 rule (D2: report both and state the disagreement):

* P2a: they agree (round 1 and last round supported on 16/16 bytes under both).
* P2b: DISAGREE. Registered rule: `p_xor_k` 0/16, `lr_c_xor_k10` 0/16, but `c_only` 1/16 (byte 5,
  Holm p 0.0181), so `lastround_ciphertext_only` = yes [5]. D2 rule (permutation p, Holm,
  0.02 margin): all four statements no, `c_only` 0/16. Consistent with D2's stated reason (the
  normal approximation is miscalibrated on near-constant columns); not interpreted further.
  P2b trace: `Recall 0.316, precision 1.000; 39024 fills` (the N = 20 smoke run gave 0.291).

### 3.6 Record, pin, commit

* `progress.md`: block "Phase E, block E1: results (2026-11-12)" inserted directly before
  `## Environment changes made for Phase A and B`, from the template, placeholders filled
  from this log; plus a short "Tool fix made during E1" paragraph for the isolation parser
  (an addition to the template; stated in the file as not a protocol deviation).
* Suite: `Ran 173 tests in 25.314s`, `OK` (173 because of the 3.3a test, as logged).
* `preserve.py`: `CAPTURED 459 files (base 45d21e259c)`; `PRESERVED: 459 files hash-match; frozen
  trees and everything outside experiments/aes-leakage/ unchanged since 45d21e259c`.
* Before `git add`: 84 status paths, 2 modified (`analysis/aes_leak_analysis.py`,
  `tests/test_analysis.py`), the rest new `runs/e1-*` files (59 MB), all under
  `experiments/aes-leakage/`; 0 paths outside it. Earlier run directories (`p1-*`) are tracked,
  so committing these follows precedent.
* Commit with the plan's subject, one sentence per result in the body, and the session's
  `Co-Authored-By` trailer:

```
974730e
0
experiment/aes-leakage
974730e Phase E block E1: window-schedule runs and differential tests
6986be8 Phase E preparation: differential test, effect size, deviations D1 to D3
```

**COMMIT_E1 = 974730e.** Nothing pushed, branch unchanged, no amend or rebase.

## CHECKPOINT 3: reported; user wrote "go , A: yes he accepts / B: yes they have read".

Reading of the answers (recorded so it can be corrected): decision A = "instructor approved"
(the instructor accepts beyond-proposal work). The second answer is labelled "B" but the
checkpoint asked for decisions A and C (decision B, D1 to D3, was approved earlier), so it is
read as decision C = "overlap preregistration approved" (the group has read
`PREREGISTRATION_OVERLAP.md` and D4). Decision D (include E2x) is not yet asked.

## Phase 4. Block E2: overlap schedule, no interconnect defense

### 4.1 Preregister the overlap experiment before any overlap run

Command: `W: R=<reference>; test ! -e PREREGISTRATION_OVERLAP.md && cp "$R/docs/PREREGISTRATION_OVERLAP.md" . && EXTRA_DEFS="-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL" sh build.sh 200 "$PWD/build/ovl-n200" 2>&1 | tail -1 && EXTRA_DEFS="..." sh build.sh 2000 "$PWD/build/ovl-n2000" 2>&1 | tail -1 && grep -h OFF_PROBE build/ovl-n200/build_manifest.json build/ovl-n2000/build_manifest.json`

```
wrote .../experiments/aes-leakage/build/ovl-n200/build_manifest.json (6 binaries)
wrote .../experiments/aes-leakage/build/ovl-n2000/build_manifest.json (6 binaries)
    "-DLEAK_OFF_PROBE=520192UL"
    "OFF_PROBE": 520192,
    "-DLEAK_OFF_PROBE=520192UL"
    "OFF_PROBE": 520192,
```

Expected: two `wrote ... (6 binaries)` lines and twice `"OFF_PROBE": 520192,`: PASS (the grep also
prints the compile-flag line, which is fine).

Edit: `README.md`, row `| \`PREREGISTRATION_OVERLAP.md\` | second, separate preregistration: the
overlap (contention) schedule and the collision-count test |` added directly after the
`PREREGISTRATION_DRAFT.md` row (text from `PROGRESS_TEMPLATES.md`).

Suite: `Ran 173 tests in 25.359s`, `OK` (173, not the plan's 172: see 3.3a).

Pin: `CAPTURED 474 files (base 45d21e259c)`; `PRESERVED: 474 files hash-match; frozen trees and
everything outside experiments/aes-leakage/ unchanged since 45d21e259c`.

Staged set (before commit), all under `experiments/aes-leakage/`, 0 outside:
`README.md`, `preservation.json` (modified); `PREREGISTRATION_OVERLAP.md`, `build/ovl-n200/`,
`build/ovl-n2000/` (new).

Commit message: the plan's subject and body, plus the session's `Co-Authored-By` trailer.

```
a3469eb
0
experiment/aes-leakage
a3469eb Preregister the overlap experiment before any overlap run
974730e Phase E block E1: window-schedule runs and differential tests
6986be8 Phase E preparation: differential test, effect size, deviations D1 to D3
```

Acceptance: `git status --porcelain | wc -l` prints `0`: PASS.
**COMMIT_OVL_PREREG = a3469eb.** No overlap run exists at this commit. Nothing pushed.

## CHECKPOINT 4a (before the pilot run): reported; user wrote "go".

### 4.2 Pilot (one gem5 run, foreground)

Command (as in the plan): `W: bash run_arm.sh e2-pilot-c8-s1-n200 r1-scrub ovl-n200 off 8 1466213861 2>&1 | tail -6; python3 -B analysis/aes_leak_analysis.py analyze --run-dir runs/e2-pilot-c8-s1-n200 --out-json ... --out-md ... | tail -1; python3 -B analysis/leak_followup.py count --run-dir runs/e2-pilot-c8-s1-n200 --nperm 10000 --out-json ... --out-md ... | tail -24`

```
run_arm: e2-pilot-c8-s1-n200 gem5_exit=0 seconds=77
run_arm: e2-pilot-c8-s1-n200 victim aes_self_test=PASS
run_arm: e2-pilot-c8-s1-n200 victim pt_checksum=21e368fc7c924d329fa8506022a58219 ct_checksum=00000000000000000000000000000000
run_arm: e2-pilot-c8-s1-n200 monitor status=PASS records=51200
RUN CHECKS: PASS
```

(`ct_checksum` is all zeros because the `r1-scrub` victim computes round 1 only; the analysis
treats the ciphertext checksum as not applicable in round-1 mode.) The `count` output was cut
at the top by `tail -24`; the full table, from `runs/e2-pilot-c8-s1-n200.count.md`:

```
Run `runs/e2-pilot-c8-s1-n200`: victim `r1-scrub`, split off, monitor ways 8, 200 windows, seed 1466213861; overlap schedule: True (OFF_PROBE 520192, OFF_ENC 524288).
Pearson r between a per-window model count and a per-window monitor feature; two-sided permutation p (10000 shuffles, seed 5764), Holm over 8 tests.

| feature | mean | sd | max |
| excess_cycles | -3.010 | 12.622 | 160.0 |
| delayed_walks | 0.525 | 0.556 | 3.0 |

| model | feature | r | Holm p |
| lines_all_rounds | excess_cycles | +0.2175 | 0.028 |
| lines_all_rounds | delayed_walks | -0.0396 | 1 |
| lines_round1_p_xor_k | excess_cycles | +0.2175 | 0.028 |
| lines_round1_p_xor_k | delayed_walks | -0.0396 | 1 |
| lines_round1_p_only | excess_cycles | +0.0145 | 1 |
| lines_round1_p_only | delayed_walks | -0.0062 | 1 |
| shuffled | excess_cycles | +0.0072 | 1 |
| shuffled | delayed_walks | +0.0379 | 1 |

| statement | supported |
| count_dependent | yes |
| round1_count_plaintext_plus_key | yes |
| round1_count_plaintext_only | no |
RUN HEALTH: PASS
```

Pilot gate (`PREREGISTRATION_OVERLAP.md` section 6):

1. `run_arm: e2-pilot-c8-s1-n200 gem5_exit=0 seconds=77` and `monitor status=PASS records=51200`;
   the `run_arm` output (4 lines, all that `tail -6` returned) has no `error=` line: MET.
2. `RUN CHECKS: PASS`: MET.
3. `| excess_cycles | -3.010 | 12.622 | 160.0 |`: max 160.0 is greater than 0 (no `0.0`): MET.

**Pilot gate: MET.** The overlap schedule did recreate delayed walks (`delayed_walks` mean 0.525 per
window, max 3). Caution for the report: N = 200, one run, one seed; the Holm p of 0.028 for
`lines_*` vs `excess_cycles` is close to alpha = 0.05 and the preregistered rule needs both
runs of an arm (N = 2000) before any statement counts. The pilot is a gate check, not a result.
`lines_all_rounds` and `lines_round1_p_xor_k` are identical here because the `r1-scrub` victim
uses only round-1 lookups.

## CHECKPOINT 4b (before the block of E2 runs): reported; the user wrote "Go" (no decision D).

Decision D was not given by that message, so E2x was provisionally skipped and step 4.3 was
started on its own (batch `e2-main`, 4 in parallel, background).

Afterwards the user wrote "Go with your recommendation". My recommendation in the 4b report
was "include E2x", so this is read as decision D = "include E2x" (recorded so it can be
corrected). Step 4.7 will run after 4.3 to 4.6, in the plan's order, not concurrently.

### 4.3 Eight registered overlap runs (background)

Command: `W: bash run_batch.sh batches/e2-main.txt 4` (`run_in_background`). Exit code 0.
`runs/e2-main.batch.log`:

```
batch e2-main started 2026-11-12 18:56:46, 4 in parallel
e2-oc8-s1-n2000 gem5_exit=0 seconds=741 OK 
e2-oc8-s2-n2000 gem5_exit=0 seconds=738 OK 
e2-oc1-s1-n2000 gem5_exit=0 seconds=766 OK 
e2-oc1-s2-n2000 gem5_exit=0 seconds=769 OK 
e2-ow8-s1-n2000 gem5_exit=0 seconds=751 OK 
e2-ow8-s2-n2000 gem5_exit=0 seconds=746 OK 
e2-ow1-s1-n2000 gem5_exit=0 seconds=774 OK 
e2-ow1-s2-n2000 gem5_exit=0 seconds=770 OK 
batch e2-main finished 2026-11-12 19:22:27
BATCH RESULT: PASS
```

Acceptance: `BATCH RESULT: PASS`: PASS. Wall time 25 min 41 s (plan: 25 to 30 minutes).

### 4.4 Run checks

Command (as in the plan): `W: for n in $(grep -v "^#" batches/e2-main.txt | cut -d" " -f1); do python3 -B analysis/aes_leak_analysis.py analyze --run-dir runs/$n --nperm 20 --out-json ... --out-md ... > runs/$n.analysis.log 2>&1; echo "$n analyze_exit=$? $(tail -1 runs/$n.analysis.log)"; done`

```
e2-oc8-s1-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-oc8-s2-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-oc1-s1-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-oc1-s2-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-ow8-s1-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-ow8-s2-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-ow1-s1-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-ow1-s2-n2000 analyze_exit=0 RUN CHECKS: PASS
```

Acceptance: eight lines `analyze_exit=0 RUN CHECKS: PASS`: PASS. (Trace recall near 0 is expected
in these arms; not a failure.)

### 4.5 Differential tests per arm

Command (as in the plan): `W: for a in oc8 oc1 ow8 ow1; do python3 -B analysis/leak_followup.py diff --a runs/e2-$a-s1-n2000 --b runs/e2-$a-s2-n2000 --out-json ... --out-md ... > /dev/null; echo "e2-$a exit=$? $(tail -1 runs/e2-$a.diff-s1-s2.md)"; done`

```
e2-oc8 exit=0 DIFF VERDICT: DIFFERENT
e2-oc1 exit=0 DIFF VERDICT: DIFFERENT
e2-ow8 exit=0 DIFF VERDICT: DIFFERENT
e2-ow1 exit=0 DIFF VERDICT: DIFFERENT
```

Read-only extra check of the two partitioned arms' run checks
(`grep -H way_isolation runs/e2-ow*-n2000.analysis.md`): all four runs
`| way_isolation | PASS | valid LLC blocks outside the assigned ways: 0 |`.

Decision rule: no `INVALID`, no exit 2: continue. Interpretability (overlap preregistration
section 6): `ow8` is interpreted only if `oc8` is `DIFFERENT`: **holds** (oc8 DIFFERENT);
`ow1` only if `oc1` is `DIFFERENT`: **holds** (oc1 DIFFERENT). No step was skipped.

Size of the differences, from `runs/e2-<arm>.diff-s1-s2.md` (512,000 records per run):

| Arm | records whose latency differs | sets with a latency difference | largest latency difference (cycles) |
|---|---|---|---|
| oc8 | 3037 | 3 | 16 |
| oc1 | 1989 | 10 | 4 |
| ow8 | 3006 | 3 | 16 |
| ow1 | 1989 | 10 | 4 |

### 4.6 Collision-count test for every run

Command (as in the plan; run in the background so the 8 x 10,000-shuffle loop could not hit
the foreground cap): `W: for n in $(grep -v "^#" batches/e2-main.txt | cut -d" " -f1); do python3 -B analysis/leak_followup.py count --run-dir runs/$n --nperm 10000 --out-json ... --out-md ... > runs/$n.count.log 2>&1; echo "$n count_exit=$? $(grep -E "^\| (count_dependent|round1_count_plaintext_plus_key|round1_count_plaintext_only) " runs/$n.count.md | tr "\n" " ")"; done`

```
e2-oc8-s1-n2000 count_exit=0 | count_dependent | yes | | round1_count_plaintext_plus_key | yes | | round1_count_plaintext_only | no |
e2-oc8-s2-n2000 count_exit=0 | count_dependent | yes | | round1_count_plaintext_plus_key | yes | | round1_count_plaintext_only | no |
e2-oc1-s1-n2000 count_exit=0 | count_dependent | no | | round1_count_plaintext_plus_key | no | | round1_count_plaintext_only | no |
e2-oc1-s2-n2000 count_exit=0 | count_dependent | no | | round1_count_plaintext_plus_key | no | | round1_count_plaintext_only | no |
e2-ow8-s1-n2000 count_exit=0 | count_dependent | yes | | round1_count_plaintext_plus_key | yes | | round1_count_plaintext_only | no |
e2-ow8-s2-n2000 count_exit=0 | count_dependent | yes | | round1_count_plaintext_plus_key | yes | | round1_count_plaintext_only | no |
e2-ow1-s1-n2000 count_exit=0 | count_dependent | no | | round1_count_plaintext_plus_key | no | | round1_count_plaintext_only | no |
e2-ow1-s2-n2000 count_exit=0 | count_dependent | no | | round1_count_plaintext_plus_key | no | | round1_count_plaintext_only | no |
```

Acceptance: eight lines with `count_exit=0`: PASS. No gate on the outcome. An arm supports a
statement only if both of its runs show `yes`:

| Arm | count_dependent | round1_count_plaintext_plus_key | round1_count_plaintext_only |
|---|---|---|---|
| OC8 (unpartitioned, 8 ways) | supported | supported | not supported |
| OC1 (unpartitioned, 1 way) | not supported | not supported | not supported |
| OW8 (way partition 8/8) | supported | supported | not supported |
| OW1 (way partition 1/15) | not supported | not supported | not supported |

Read-only observation, not a plan step (`cmp` on finished runs): `probes.bin` of `oc1` vs `ow1`
differs in 162 bytes for each seed (of 8,192,000); `oc8` vs `ow8` differs in 491,119 bytes (s1)
and 489,788 bytes (s2). So the identical diff statistics for `oc1` and `ow1` above come from
near-identical logs, not from a coincidence in the tool.

### 4.7 Exploratory full-AES arms (decision D = include E2x)

Command: `W: bash run_batch.sh batches/e2-explore.txt 4` (`run_in_background`); started after 4.6
finished. Exit code 0. `runs/e2-explore.batch.log`:

```
batch e2-explore started 2026-11-12 19:23:34, 4 in parallel
e2-fw8-s1-n2000 gem5_exit=0 seconds=704 OK 
e2-fw8-s2-n2000 gem5_exit=0 seconds=699 OK 
e2-fw1-s1-n2000 gem5_exit=0 seconds=723 OK 
e2-fw1-s2-n2000 gem5_exit=0 seconds=714 OK 
batch e2-explore finished 2026-11-12 19:35:38
BATCH RESULT: PASS
```

Acceptance (as for 4.3): `BATCH RESULT: PASS`: PASS. Wall time 12 min 4 s (plan: about 15 minutes).
Run list (`batches/e2-explore.txt`): victim `full-scrub`, `ovl-n2000`, splits 8-8 and 1-15 with 8 and 1
monitor ways, seeds S1 and S2.

Steps 4.4, 4.5 and 4.6 with `batches/e2-explore.txt` and `for a in fw8 fw1` (one background command):

```
e2-fw8-s1-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-fw8-s2-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-fw1-s1-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-fw1-s2-n2000 analyze_exit=0 RUN CHECKS: PASS
e2-fw8 exit=0 DIFF VERDICT: DIFFERENT
e2-fw1 exit=0 DIFF VERDICT: DIFFERENT
e2-fw8-s1-n2000 count_exit=0 | count_dependent | yes | | round1_count_plaintext_plus_key | yes | | round1_count_plaintext_only | no |
e2-fw8-s2-n2000 count_exit=0 | count_dependent | yes | | round1_count_plaintext_plus_key | yes | | round1_count_plaintext_only | no |
e2-fw1-s1-n2000 count_exit=0 | count_dependent | yes | | round1_count_plaintext_plus_key | no | | round1_count_plaintext_only | no |
e2-fw1-s2-n2000 count_exit=0 | count_dependent | yes | | round1_count_plaintext_plus_key | no | | round1_count_plaintext_only | no |
```

All four FW runs: `| way_isolation | PASS | valid LLC blocks outside the assigned ways: 0 |`.
Difference sizes: fw8 18289 records differ, 14 sets, largest 24 cycles; fw1 22234 records differ,
67 sets, largest 6 cycles.

Per the plan ("Read only `count_dependent` from these arms") only `count_dependent` is carried into
`progress.md`: yes, yes for FW8 and yes, yes for FW1. The round-1 columns above are printed by the
command and are not interpreted (the FW arms use a full encryption, for which round-1 statements
are low-power: preregistration section 8, item 4).

### Largest |r| and the OC8 / OW8 correlations (read-only, from the saved count tables)

Largest |r| over the 12 `-n2000` count tables: `lines_round1_p_xor_k` (equal to `lines_all_rounds`
for this victim) vs `excess_cycles`, +0.4559, `e2-oc8-s1-n2000`. `lines_round1_p_xor_k` vs
`excess_cycles`, per run (Holm p): oc8-s1 +0.4559 (0.0008), oc8-s2 +0.4421 (0.0008), ow8-s1
+0.0834 (0.0008), ow8-s2 +0.0611 (**0.0384**), oc1-s1 -0.0119 (1), oc1-s2 -0.0300 (1), ow1-s1
-0.0120 (1), ow1-s2 -0.0321 (1), fw8-s1 -0.0466 (0.155), fw8-s2 -0.0623 (0.0426), fw1-s1 +0.0210 (1),
fw1-s2 +0.0241 (1). The key-free model `lines_round1_p_only` and the shuffled control are
not significant in any of these runs (Holm p is 1 in every row except the shuffled control of
fw8-s2, 0.6615). OW8's correlation is about 14 to 18% of OC8's and its second run
is the closest to the 0.05 line of any run called significant.

### 4.8 Record, pin, commit

* `progress.md`: block "Phase E, block E2: results (2026-11-12)" inserted directly before
  `## Environment changes made for Phase A and B` (after the E1 block), from the template with
  placeholders filled from this log; the template's "Exploratory arms" and "Largest |r|" fields
  filled as above.
* Suite: `Ran 173 tests in 25.041s`, `OK`.
* `preserve.py`: `CAPTURED 706 files (base 45d21e259c)`; `PRESERVED: 706 files hash-match; frozen
  trees and everything outside experiments/aes-leakage/ unchanged since 45d21e259c`.
* Staged set: 117 paths, all under `experiments/aes-leakage/` (0 outside); modified tracked files
  `progress.md`, `preservation.json`; about 103 MB of new `runs/e2-*` data (local only).
* Commit (plan subject; body = verdicts and statements; session `Co-Authored-By` trailer):

```
146dee6
0
experiment/aes-leakage
146dee6 Phase E block E2: overlap schedule without interconnect defense
a3469eb Preregister the overlap experiment before any overlap run
974730e Phase E block E1: window-schedule runs and differential tests
6986be8 Phase E preparation: differential test, effect size, deviations D1 to D3
```

**COMMIT_E2 = 146dee6.** Nothing pushed, branch unchanged, no amend or rebase.

## CHECKPOINT 5: reported; user wrote "go".

## Phase 5. Block E3: full defense in the overlap schedule

### 5.1 Log D4 before any defended run

Command: `W: python3 -B <reference>/log_deviations.py . D4`

```
appended D4 to PREREGISTRATION_DRAFT.md (dated 2026-11-12)
appended D4 to progress.md (dated 2026-11-12)
```

Acceptance: two `appended D4 to ...` lines: PASS (deviation entries are now 5 in each ledger, D0 to
D4; checked with `grep -c "^\* \*\*D[0-9] ("`: `PREREGISTRATION_DRAFT.md:5`, `progress.md:5`).

Suite: `Ran 173 tests in 25.154s`, `OK`. Pin: `CAPTURED 706 files (base 45d21e259c)`;
`PRESERVED: 706 files hash-match; frozen trees and everything outside experiments/aes-leakage/
unchanged since 45d21e259c`. Staged set: `PREREGISTRATION_DRAFT.md`, `progress.md`,
`preservation.json` (3 paths, all modified).

Commit (plan subject and body, plus the session `Co-Authored-By` trailer):

```
9a37b49
0
experiment/aes-leakage
```

**COMMIT_D4 = 9a37b49.** No defended run exists at this commit. Nothing pushed.

### 5.2 New gem5 tree (set-up part)

Command: `W: test ! -e ~/eel5764/gem5-leak-def && git -C ~/eel5764/gem5 worktree add ~/eel5764/gem5-leak-def c8222cc67a399bfc01e8658dd14b30d5bfd634f9 && cd ~/eel5764/gem5-leak-def && git apply <worktree>/experiments/respq-defense-20261018/gem5-respq.patch && git status --porcelain | wc -l && ls -l ~/eel5764/leak-ext/gem5_ext/`

```
Preparing worktree (detached HEAD c8222cc)
HEAD is now at c8222cc misc: Hotfix Release: v25.1.0.1 (#3082)
15
total 24
-rwxrwxrwx 1 shahriarahi shahriarahi  2763 Nov 12 11:04 RequestorPartitionManager.py
-rwxrwxrwx 1 shahriarahi shahriarahi   445 Nov 12 11:04 SConscript
-rwxrwxrwx 1 shahriarahi shahriarahi 11384 Nov 12 11:05 requestor_partition_manager.cc
-rwxrwxrwx 1 shahriarahi shahriarahi  4742 Nov 12 11:04 requestor_partition_manager.hh
```

Expected `15` and the four `gem5_ext` files: PASS. The directory did not exist before (the `test ! -e`
guard passed). The only effect on `~/eel5764/gem5` is the worktree metadata `git worktree add`
writes under its `.git/worktrees/`.

Build (background): `W: cd ~/eel5764/gem5-leak-def && { echo "build started ..."; scons build/RISCV/gem5.opt -j14 EXTRAS=$HOME/eel5764/leak-ext/gem5_ext < /dev/null; echo "scons exit=$?"; echo "build finished ..."; } > ~/eel5764/build_leak_def.log 2>&1; tail -3 ~/eel5764/build_leak_def.log; ls -l ~/eel5764/gem5-leak-def/build/RISCV/gem5.opt`
Started after the set-up above. Exit code 0. Result (last lines of the command, plus the log's
first line read separately):

```
build started 2026-11-12 19:43:09
         This host has no capstone library installed.
scons exit=0
build finished 2026-11-12 19:55:26
-rwxr-xr-x 1 shahriarahi shahriarahi 1003677648 Nov 12 19:55 /home/shahriarahi/eel5764/gem5-leak-def/build/RISCV/gem5.opt
```

Acceptance: `scons exit=0` and a `gem5.opt` of about 1.0 GB (1,003,677,648 bytes): PASS. Build time
12 min 17 s (plan: about 13 minutes at `-j14`). The capstone line is a warning the plan's notes and
`progress.md` (Phase B) already mention for earlier builds.

### 5.3 Guard: defense off, the new binary reproduces a stored run byte for byte

Command: `W: bash run_arm.sh p0d-r1-scrub-n20 r1-scrub n20 off 16 1466213861 guard 2>&1 | tail -4; python3 -B analysis/leak_followup.py diff --a runs/p0b-r1-scrub-n20 --b runs/p0d-r1-scrub-n20 --allow-same-seed --out-json runs/p0d.guard-diff.json --out-md runs/p0d.guard-diff.md | tail -1`

```
run_arm: p0d-r1-scrub-n20 gem5_exit=0 seconds=17
run_arm: p0d-r1-scrub-n20 victim aes_self_test=PASS
run_arm: p0d-r1-scrub-n20 victim pt_checksum=8a277d047af75bcd12f1988659916941 ct_checksum=00000000000000000000000000000000
run_arm: p0d-r1-scrub-n20 monitor status=PASS records=5120
wrote runs/p0d.guard-diff.md
```

With `--out-md` the tool's last stdout line is `wrote runs/p0d.guard-diff.md`, so the verdict was read from
the file (`grep -H "DIFF VERDICT" runs/p0d.guard-diff.md`):

```
runs/p0d.guard-diff.md:DIFF VERDICT: IDENTICAL
```

Acceptance: `monitor status=PASS records=5120` and `IDENTICAL`: PASS (`--allow-same-seed` is the
documented flag for a deliberate same-seed comparison). The new binary may be used for the defended
runs.

## CHECKPOINT 6 (before the defended runs): reported; user wrote "go".

### 5.4 Four defended runs (background)

Command: `W: bash run_batch.sh batches/e3-defense.txt 4` (`run_in_background`). Exit code 0.
`runs/e3-defense.batch.log`:

```
batch e3-defense started 2026-11-12 20:02:23, 4 in parallel
e3-od8-s1-n2000 gem5_exit=0 seconds=1492 OK 
e3-od8-s2-n2000 gem5_exit=0 seconds=1485 OK 
e3-od1-s1-n2000 gem5_exit=0 seconds=1549 OK 
e3-od1-s2-n2000 gem5_exit=0 seconds=1540 OK 
batch e3-defense finished 2026-11-12 20:28:12
BATCH RESULT: PASS
```

Acceptance: `BATCH RESULT: PASS`: PASS. Wall time 25 min 49 s (plan: about 15 minutes; the defended
runs take about 1,500 s each against about 750 s for the undefended overlap runs). Run list
(`batches/e3-defense.txt`): `r1-scrub`, `ovl-n2000`, splits 8-8 and 1-15, 8 and 1 monitor ways,
seeds S1 and S2, mode `defense`: identical to the OW8 and OW1 lines of `e2-main.txt` except for
the defense argument (and the gem5 binary).

### 5.5 The defense was really on, and the run checks pass

Command (as in the plan, verbatim): `W: for n in $(grep -v "^#" batches/e3-defense.txt | cut -d" " -f1); do python3 -B analysis/aes_leak_analysis.py analyze ... > runs/$n.analysis.log 2>&1; echo "$n analyze_exit=$? $(tail -1 runs/$n.analysis.log) slots=$(grep -c "\"tdma_slot_cycles\": 4" runs/$n/defense_config.json) respq=$(grep -c "\"respq\": true" runs/$n/defense_config.json) prefixes=$(grep -c "^response_domain_prefixes=cpu0. cpu1." runs/$n/config.ini) tdma_lines=$(grep -c "\.tdma" runs/$n/stats.txt) violations=$(grep -E "\.(tdmaOverruns|tdmaDownstreamRefusals|tdmaExpressBypasses) " runs/$n/stats.txt | awk "{s+=\$2} END {print s+0}")"; done`

```
e3-od8-s1-n2000 analyze_exit=0 RUN CHECKS: PASS slots=1 respq=1 prefixes=1 tdma_lines=32 violations=0
e3-od8-s2-n2000 analyze_exit=0 RUN CHECKS: PASS slots=1 respq=1 prefixes=1 tdma_lines=32 violations=0
e3-od1-s1-n2000 analyze_exit=0 RUN CHECKS: PASS slots=1 respq=1 prefixes=1 tdma_lines=32 violations=0
e3-od1-s2-n2000 analyze_exit=0 RUN CHECKS: PASS slots=1 respq=1 prefixes=1 tdma_lines=32 violations=0
```

Acceptance per line (`analyze_exit=0 RUN CHECKS: PASS`, `slots=1`, `respq=1`, `prefixes=1`, `tdma_lines` at
least 1, `violations=0`): all four PASS.

Non-vacuity check (read-only, my own addition because `awk` prints `0` when nothing matches): in
each run `grep -E "\.(tdmaOverruns|tdmaDownstreamRefusals|tdmaExpressBypasses) " stats.txt` finds
12 lines (3 counters, two statistics dumps, two stat paths, e.g. `system.l2bus.tdmaOverruns`),
all with value 0. `grep -H way_isolation runs/e3-*.analysis.md`: all four
`| way_isolation | PASS | valid LLC blocks outside the assigned ways: 0 |`.

### 5.6 Differential tests

Command (as in the plan): `W: for a in od8 od1; do python3 -B analysis/leak_followup.py diff --a runs/e3-$a-s1-n2000 --b runs/e3-$a-s2-n2000 --out-json ... --out-md ... > /dev/null; echo "e3-$a exit=$? $(tail -1 runs/e3-$a.diff-s1-s2.md)"; done`

```
e3-od8 exit=0 DIFF VERDICT: IDENTICAL
e3-od1 exit=0 DIFF VERDICT: IDENTICAL
```

Detail from the `.md` files: for both arms `records whose latency differs 0`, `records whose
timestamp differs 0`, `sets with a latency difference 0`, `largest latency difference (cycles) 0`;
sha256 of run A equals run B (od8 `2671df08...17e4`, od1 `f243ce3e...1588`).

Forecast (`IDENTICAL` twice) held; it was not a gate. No `INVALID`, no `DIFFERENT`, so the
`count` follow-up of the plan's decision rule was not needed.

Comparison, for the record: the same two arms without the interconnect defense (OW8, OW1 of
block E2) were `DIFFERENT` (3,006 and 1,989 of 512,000 latency records differ). Limit: the
guard (5.3) compared the new binary with the defense off on a stored window-schedule run, not
on an overlap-schedule run.

### 5.7 Record, pin, commit

* `progress.md`: block "Phase E, block E3: results (2026-11-12)" inserted directly before
  `## Environment changes made for Phase A and B`, from the template, placeholders filled from
  this log ("time-slot violation counters sum 0"); the template's sentence added at the end of the
  "Environment changes" section.
* Suite: `Ran 173 tests in 25.283s`, `OK`.
* `preserve.py`: `CAPTURED 783 files (base 45d21e259c)`; `PRESERVED: 783 files hash-match; frozen
  trees and everything outside experiments/aes-leakage/ unchanged since 45d21e259c`.
* Staged set: 30 paths, all under `experiments/aes-leakage/` (0 outside); modified tracked files
  `progress.md`, `preservation.json`; about 35 MB of new `runs/e3-*` and `runs/p0d*` data.
* Commit (plan subject; body = guard verdict, defense checks, two verdicts; session
  `Co-Authored-By` trailer):

```
2ccad2d
0
experiment/aes-leakage
2ccad2d Phase E block E3: full defense in the overlap schedule
9a37b49 Log deviation D4 before the full-defense runs
146dee6 Phase E block E2: overlap schedule without interconnect defense
a3469eb Preregister the overlap experiment before any overlap run
974730e Phase E block E1: window-schedule runs and differential tests
6986be8 Phase E preparation: differential test, effect size, deviations D1 to D3
```

**COMMIT_E3 = 2ccad2d.** Nothing pushed, branch unchanged, no amend or rebase.

## CHECKPOINT 7: reported; user wrote "Go".

## Phase 6. Close (no gem5)

### 6.1 Final verification

Suite (`W: python3 -B -m unittest discover -s tests -t . 2>&1 | tail -4`):

```
Ran 173 tests in 25.468s

OK
```

Git Bash: `cd "$EXP" && python -B preserve.py verify; git status --porcelain | wc -l; git log --oneline 434b16b..HEAD; git branch -vv | grep "^\*"`:

```
PRESERVED: 783 files hash-match; frozen trees and everything outside experiments/aes-leakage/ unchanged since 45d21e259c
0
2ccad2d Phase E block E3: full defense in the overlap schedule
9a37b49 Log deviation D4 before the full-defense runs
146dee6 Phase E block E2: overlap schedule without interconnect defense
a3469eb Preregister the overlap experiment before any overlap run
974730e Phase E block E1: window-schedule runs and differential tests
6986be8 Phase E preparation: differential test, effect size, deviations D1 to D3
* experiment/aes-leakage    2ccad2d Phase E block E3: full defense in the overlap schedule
```

Acceptance: `Ran 173 tests` (the plan says 172; 173 because of the approved isolation-parser test,
3.3a) and `OK`; a `PRESERVED:` line; `0`; the six commits of this plan and no others; nothing
pushed (I never ran `git push`; `git for-each-ref` shows no upstream for the branch; `origin` is
configured but unused): PASS.

### 6.2 Final report

Written to `postdoc-review/exec/FINAL_REPORT.md` from the template (evidence table for every step,
results for E1, E2 and E3, deviations, commits, skipped items, mismatches with the plan, open
decisions). The paper was not edited.

## DONE.
