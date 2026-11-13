# Execution plan: Phase E of the AES leakage follow-up (for Claude Sonnet 5.5)

## Kickoff

**Purpose.** This plan carries out Phase E of a simulator-only follow-up study for
EEL 5764 Group 18: it adds a differential test, an effect-size report and a
collision-count test to an existing analysis, logs the preregistered deviations that
allow them, and then runs up to 30 gem5 simulations in three blocks. You execute it
step by step and stop at every checkpoint until the user writes "go". You do not
redesign anything: where a step needs a judgement, the decision rule is written in
the step.

**Read these first, in this order** (read-only):

1. This file, completely.
2. `postdoc-review/POSTDOC_REVIEW.md`, sections 1, 2 and 5 (why the plan looks like this).
3. `.codex-tmp/aes-leakage-worktree/experiments/aes-leakage/DISCUSSION_BRIEF.md` (what the study is).
4. `.codex-tmp/aes-leakage-worktree/experiments/aes-leakage/PREREGISTRATION_DRAFT.md` and `progress.md`.
5. `postdoc-review/reference/docs/DEVIATIONS_D1_D4.md` and `PREREGISTRATION_OVERLAP.md`.
6. `postdoc-review/reference/README.md` (what each reference file is).

All paths in this file are relative to the workspace root
`C:\Users\shahr\OneDrive\Documents\Fall 26\Computer Architecture` unless they start
with `/` or `~`.

**Guardrails (the accepted course proposal must stay intact).** Check every action
against these four points. If an action would cross one, do not do it; stop and
report.

1. The proposal's research question, metrics and success criterion stay reported
   unchanged: max-set contention SNR, the 10,000-permutation shuffled-label null at
   seed 5764, zero isolation violations, per-core IPC and LLC miss rate against the
   unpartitioned control.
2. The platform and baseline configuration of the proposal's runs are unchanged:
   gem5 v25.1.0.1, RISC-V SE mode, 2 x TimingSimpleCPU at 2 GHz, 4 KiB L1D, 256 KiB
   16-way LLC, DDR3-1600.
3. Nothing guesses, ranks, scores or recovers key bytes; nothing uses an unknown key;
   nothing targets real hardware or services. Known-key attribution with fixed models
   is allowed and is labelled as beyond the proposal.
4. Frozen paper results and checksummed files stay untouched.

**Action boundaries.**

* You may write only in these places:
  * `.codex-tmp/aes-leakage-worktree/experiments/aes-leakage/` (the experiment
    directory), and only the files this plan names;
  * `postdoc-review/exec/` (your log and final report);
  * in WSL: the new tree `~/eel5764/gem5-leak-def` and the log
    `~/eel5764/build_leak_def.log` (Phase 5 only).
* Never modify: anything else in the worktree or the main checkout (`results/`,
  `configs/`, `workloads/`, `gem5_ext/`, `analysis/`, `scripts/`, the paper and
  proposal files); `postdoc-review/` outside `exec/`; the existing gem5 trees
  (`~/eel5764/gem5`, `gem5-leak`, `gem5-timeslot`, `gem5-respq`, `gem5-causal`);
  `DISCUSSION_BRIEF.md` (five tests check it); any text of
  `PREREGISTRATION_DRAFT.md` above the end of the file (it is append-only).
* Run gem5 only for the runs this plan lists, only after the checkpoint that precedes
  them, and never into an existing run directory.
* Git: commit only where a step says so, only on branch `experiment/aes-leakage` in
  the worktree, only with the tests passing. Never push, never change branch, never
  amend, never rebase.
* Never install packages, never send anything to anyone, never edit the paper.
* Do not "improve" the reference code. If a reference file seems wrong, stop and
  report.

**When to stop.** Stop and report (a) at every CHECKPOINT; (b) when an acceptance
check fails after the diagnostic attempts the step allows; (c) when a gem5 run fails
(no automatic retry, ever); (d) when anything is not as this plan describes it;
(e) when a step is marked BLOCKED and its condition is not met.

## Conventions

* Use the Bash tool (Git Bash). Shell state does not persist between calls, so every
  command block below is complete; paste it as it is.
* **WSL commands** go through the wrapper `postdoc-review/w.sh`, which starts in the
  experiment directory inside WSL. The command is one argument in SINGLE quotes:

  ```bash
  bash "/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/w.sh" 'pwd'
  ```

  Expected output: `/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage`.
  Below, a line starting with `W:` means: run the rest of the line as that
  single-quoted argument. Example: `W: nproc` means
  `bash "/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/w.sh" 'nproc'`.
  None of the commands in this plan contains a single quote.
* **Git and preserve.py** use Windows tools from Git Bash (WSL git cannot open this
  worktree). A line starting with `G:` is run directly in Git Bash. In `G:` lines,
  `$WT` and `$EXP` are not defined for you; each `G:` block defines them itself.
* Inside `W:` commands these WSL paths are used:
  * `REF=/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference`
    (written out in full in each command);
  * the experiment directory is the starting directory, so `runs/...`,
    `analysis/...`, `tests/...` are relative to it.
* **Long runs.** A Bash tool call in the foreground is limited to 10 minutes. Steps
  marked "background" must be started with the Bash tool's `run_in_background` set to
  true; wait for the completion notice, then read the log the step names. Do not
  start a second copy.
* **Seeds.** S1 = 1466213861, S2 = 1466213862, S3 = 1466213863.
* **The test suite** is `W: python3 -B -m unittest discover -s tests -t . 2>&1 | tail -4`.
  "Tests pass" means its last line is `OK` and the count is the one the step states.
* **Log.** Append to `postdoc-review/exec/LOG.md` after every step: the step number,
  the command, and the output lines that the step's "Expected" and "Acceptance" name.
  Quote real output; never write "passed" without the line that shows it.
* **Failure rule (default).** If an acceptance check fails: read the relevant log,
  re-run the check once, and make at most one more diagnostic attempt that changes no
  file. If it still fails, stop and report. Never change a gate, an expected value or
  a test to make a check pass.
* A git warning "LF will be replaced by CRLF" is harmless; ignore it.

## Decisions only the user can make

| ID | Decision | Blocks | Unblocked by the user writing |
|---|---|---|---|
| A | The instructor accepts beyond-proposal work in the final paper | Phase 4 onward (blocks E2 and E3 exist only for the extension) | "instructor approved", or "run E2 and E3 regardless" |
| B | The group has read deviations D1 to D3 | Step 2.1 | "D1 to D3 approved" (at checkpoint 1) |
| C | The group has read `PREREGISTRATION_OVERLAP.md` and D4 | Step 4.1 | "overlap preregistration approved" (at checkpoint 3) |
| D | Whether to run the exploratory block E2x | Step 4.7 | "include E2x" (at checkpoint 4b) |

## Phase 0. Orientation and baseline (no changes; 15 min)

**0.1 Goal: confirm the starting state.**

```bash
G: WT="/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree"; git -C "$WT" status --porcelain; echo "porcelain-lines=$(git -C "$WT" status --porcelain | wc -l)"; git -C "$WT" rev-parse --short HEAD; git -C "$WT" branch --show-current
```

Expected: `porcelain-lines=0`, `434b16b`, `experiment/aes-leakage`.
Acceptance: all three. On failure: stop and report (do not clean anything).

**0.2 Goal: the wrapper and the test suite work.**

```
W: pwd; nproc; python3 -B -m unittest discover -s tests -t . 2>&1 | tail -4
```

Expected: the experiment directory path, `20`, `Ran 139 tests in ...`, `OK`.
Acceptance: `Ran 139 tests` and `OK`.

**0.3 Goal: the reference files are present.**

```
W: ls "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference" "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference/batches" "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference/tests" "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference/docs"
```

Acceptance: these names appear: `apply_fixes.py`, `log_deviations.py`, `run_arm.sh`,
`run_batch.sh`, `run_leakage_defense.py`, `analysis`, `README.md`; batches
`e1-diff.txt`, `e1-full.txt`, `e2-main.txt`, `e2-explore.txt`, `e3-defense.txt`; tests
`test_fixes.py`, `test_leak_followup.py`, `test_run_leakage_defense.py`; docs
`DEVIATIONS_D1_D4.md`, `PREREGISTRATION_OVERLAP.md`, `PROGRESS_TEMPLATES.md`.

**0.4** Create `postdoc-review/exec/LOG.md` with a first line `# Execution log` and
the outputs of 0.1 to 0.3.

**CHECKPOINT 0.** Report the three outputs. Wait for "go".

## Phase 1. Fixes and new analysis code (no gem5; 30 min)

**1.1 Goal: add the failing test first.**

```
W: cp "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference/tests/test_fixes.py" tests/ && python3 -B -m unittest tests.test_fixes 2>&1 | tail -3
```

Expected: `Ran 4 tests in ...` and `FAILED (failures=1, errors=2)`.
Acceptance: the tests fail now (they must: the fixes are not applied yet). If they
pass, stop and report.

**1.2 Goal: apply the two source fixes** (flat-log crash in
`analysis/aes_leak_analysis.py`, function `anova_p_min`; `.claude/` exclusion in
`preserve.py`, function `list_files`).

```
W: python3 -B "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference/apply_fixes.py" . && python3 -B -m unittest tests.test_fixes 2>&1 | tail -3
```

Expected: `applied: analysis/aes_leak_analysis.py`, `applied: preserve.py`,
`Ran 4 tests in ...`, `OK`.
Acceptance: both `applied:` lines and `OK`. On `ERROR: anchor not found`: stop.

**1.3 Goal: add the new modules, launchers, batch lists and their tests.**

```
W: R="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference"; cp "$R/analysis/leak_followup.py" analysis/ && cp "$R/run_leakage_defense.py" "$R/run_arm.sh" "$R/run_batch.sh" . && mkdir -p batches && cp "$R"/batches/*.txt batches/ && cp "$R/tests/test_leak_followup.py" "$R/tests/test_run_leakage_defense.py" tests/ && python3 -B -m unittest tests.test_leak_followup tests.test_run_leakage_defense 2>&1 | tail -3
```

Expected: `Ran 29 tests in ...`, `OK`.

**1.4 Goal: the whole suite passes with the additions.**

```
W: python3 -B -m unittest discover -s tests -t . 2>&1 | tail -4
```

Acceptance: `Ran 172 tests` and `OK`.

**1.5 Goal: the tools work on the stored runs** (acceptance that exercises real data).

```
W: python3 -B analysis/leak_followup.py diff --a runs/p0b-r1-scrub-n20 --b runs/p0c-r1-scrub-n20 --allow-same-seed | tail -1; python3 -B analysis/leak_followup.py effect --run-dir runs/p1-r1-scrub-n2000 --nperm 10000 --out-json runs/p1-r1-scrub-n2000.effect.json --out-md runs/p1-r1-scrub-n2000.effect.md | grep -E "p_xor_k|p_only|exact indicator|RUN HEALTH"
```

Expected: `DIFF VERDICT: IDENTICAL`; a row `| p_xor_k | 2176.722 | 136.0451 | 16/16 | 16/16 |`;
a row starting `| p_only | -142.009`, ending `| 0/16 | 0/16 |`; `exact indicator: True`;
`RUN HEALTH: PASS`. Takes about one minute.
Acceptance: all five.

**1.6 Goal: all planned run commands pass their pre-flight checks without running gem5.**

```
W: sh build.sh 500 2>&1 | tail -1; for b in e1-diff e1-full; do DRY_RUN=1 bash run_batch.sh batches/$b.txt | tail -1; done
```

Expected: `wrote .../build/n500/build_manifest.json (6 binaries)` and twice
`DRY RUN: pre-flight passed, nothing was run`.

**CHECKPOINT 1 (analysis code changed).** Report the outputs of 1.1 to 1.6. Show the
user the three bullets D1, D2 and D3 from
`postdoc-review/reference/docs/DEVIATIONS_D1_D4.md` and ask for decision B. Wait for
"D1 to D3 approved". Do not commit yet.

## Phase 2. Log D1 to D3, document, commit (no gem5; 30 min)

**2.1 Goal: log the deviations before any Phase E data exist.** BLOCKED until
decision B.

```
W: python3 -B "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference/log_deviations.py" . D1 D2 D3 && grep -c "^\* \*\*D[0-9] (" PREREGISTRATION_DRAFT.md progress.md
```

Expected: two `appended D1, D2, D3 to ...` lines, then `PREREGISTRATION_DRAFT.md:4`
and `progress.md:4`.
On `ERROR: ... already logged`: stop (do not log twice).

**2.2 Goal: update the ledgers.** With the Edit tool, in the experiment directory:

* `README.md`: replace
  `| \`PREREGISTRATION_DRAFT.md\` | hypotheses, N, seeds, decision rule (DRAFT, not frozen) |`
  with
  `| \`PREREGISTRATION_DRAFT.md\` | hypotheses, N, seeds, decision rule (frozen at \`675c047\`; deviations in its section 11) |`.
* `README.md`: directly after the line that starts with
  `| \`analysis/power_synth.py\` |`, insert the four rows given under "README rows,
  Phase 2" in `postdoc-review/reference/docs/PROGRESS_TEMPLATES.md`.
* `progress.md`: insert the block "Phase E preparation" from the same templates file
  directly before the line `## Environment changes made for Phase A and B`, replacing
  each `<...>` placeholder with the real value from your log.

Acceptance: the suite passes (`Ran 172 tests`, `OK`); the documentation tests read
these files.

**2.3 Goal: pin and commit.**

```bash
G: EXP="/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage"; cd "$EXP" && python -B preserve.py capture && python -B preserve.py verify
```

Expected: `CAPTURED <n> files (base ...)` then a line starting `PRESERVED:`.
On `PRESERVATION FAILED`: read the listed paths. If every path is inside
`experiments/aes-leakage/`, run the same command once more; otherwise stop.

```bash
G: WT="/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree"; git -C "$WT" add -A experiments/aes-leakage && git -C "$WT" commit -q -m "Phase E preparation: differential test, effect size, deviations D1 to D3" -m "Adds analysis/leak_followup.py (diff, effect, count), run_arm.sh, run_batch.sh, run_leakage_defense.py, batch lists and tests; fixes the flat-log crash in anova_p_min and stops preserve.py pinning .claude session state. Logs deviations D1 to D3 before any Phase E run. No gem5 run in this commit." && git -C "$WT" log -1 --format=%h && git -C "$WT" status --porcelain | wc -l
```

Expected: a 7-character hash and `0`. Record the hash in the log as `COMMIT_PREP`.
Run the test suite once before this command; commit only if it passes.

**CHECKPOINT 2 (before any gem5 run).** Report `COMMIT_PREP`, the test line and the
`PRESERVED:` line. State that the next phase runs 12 gem5 simulations (about 20
minutes of wall time). Wait for "go".

## Phase 3. Block E1: window schedule (gem5; 45 min)

Runs (all with `~/eel5764/gem5-leak`, no interconnect defense):

| Batch file | Runs | N | Parallel | Expected wall time |
|---|---|---|---|---|
| `batches/e1-diff.txt` | `e1-c8-s{1,2}-n500`, `e1-c1-s{1,2}-n500`, `e1-w8-s{1,2,3}-n500`, `e1-w1-s{1,2,3}-n500` | 500 | 4 | about 9 min |
| `batches/e1-full.txt` | `e1-p2a-s1-n2000`, `e1-p2b-s1-n2000` | 2000 | 2 | 11 to 15 min |

**3.1 Goal: run the ten differential arms.** Background.

```
W: bash run_batch.sh batches/e1-diff.txt 4
```

Expected: last line `BATCH RESULT: PASS`; `runs/e1-diff.batch.log` has ten lines
ending in `OK`.
On `BATCH RESULT: FAIL` or exit status 3: stop and report the batch log and the
`runs/<name>.launch.log` of each failed run. Do not re-run.

**3.2 Goal: run the two unprotected full-AES runs.** Background.

```
W: bash run_batch.sh batches/e1-full.txt 2
```

Expected: `BATCH RESULT: PASS`. A `monitor error=probe_deadline` is possible here (the
measured margin is 1.16x); if it occurs, stop and report, do not re-run.

**3.3 Goal: registered analysis and run checks for all twelve runs.**

```
W: for n in $(grep -h -v "^#" batches/e1-diff.txt batches/e1-full.txt | cut -d" " -f1); do python3 -B analysis/aes_leak_analysis.py analyze --run-dir runs/$n --nperm 20 --out-json runs/$n.analysis.json --out-md runs/$n.analysis.md > runs/$n.analysis.log 2>&1; echo "$n analyze_exit=$? $(tail -1 runs/$n.analysis.log)"; done
```

Expected: twelve lines, each `analyze_exit=0 RUN CHECKS: PASS`.
Acceptance: all twelve. A partitioned run (`e1-w*`) must show `way_isolation | PASS`
in its `.analysis.md`; check with
`W: grep -c "way_isolation | PASS" runs/e1-w*.analysis.md` (expected: six files, each `:1`).

**3.4 Goal: the differential tests (deviation D1).**

```
W: for p in "c8 s1 s2" "c1 s1 s2" "w8 s1 s2" "w8 s1 s3" "w8 s2 s3" "w1 s1 s2" "w1 s1 s3" "w1 s2 s3"; do set -- $p; python3 -B analysis/leak_followup.py diff --a runs/e1-$1-$2-n500 --b runs/e1-$1-$3-n500 --out-json runs/e1-$1.diff-$2-$3.json --out-md runs/e1-$1.diff-$2-$3.md > /dev/null; echo "e1-$1 $2 $3 exit=$? $(tail -1 runs/e1-$1.diff-$2-$3.md)"; done
```

Expected (the review's forecast, not a gate): eight lines `exit=0 DIFF VERDICT: IDENTICAL`.
Decision rule:
* `DIFF VERDICT: INVALID` or `exit=2` on any line: stop and report.
* `IDENTICAL` on all lines: continue.
* `DIFFERENT` or `LATENCY_IDENTICAL` for an arm: this is a finding, not a failure. For
  each run of that arm also run
  `W: python3 -B analysis/leak_followup.py effect --run-dir runs/<name> --nperm 10000 --reference runs/e1-p2a-s1-n2000 --out-json runs/<name>.effect.json --out-md runs/<name>.effect.md | tail -30`
  and
  `W: python3 -B analysis/leak_followup.py count --run-dir runs/<name> --nperm 10000 --out-json runs/<name>.count.json --out-md runs/<name>.count.md | tail -25`,
  record the outputs, and continue.

**3.5 Goal: effect sizes for the unprotected runs (deviation D2).**

```
W: python3 -B analysis/leak_followup.py effect --run-dir runs/e1-p2a-s1-n2000 --nperm 10000 --out-json runs/e1-p2a-s1-n2000.effect.json --out-md runs/e1-p2a-s1-n2000.effect.md | tail -24; python3 -B analysis/leak_followup.py effect --run-dir runs/e1-p2b-s1-n2000 --nperm 10000 --reference runs/e1-p2a-s1-n2000 --out-json runs/e1-p2b-s1-n2000.effect.json --out-md runs/e1-p2b-s1-n2000.effect.md | tail -28
```

Gate G-P2a (all four must hold; otherwise stop and report, and do not start Phase 4):
1. `runs/e1-p2a-s1-n2000.analysis.md` has `| round1_plaintext_plus_key | yes |` and
   `| round1_plaintext_only | no |`.
2. The same file has `Recall 1.000, precision 1.000`.
3. `runs/e1-p2a-s1-n2000.effect.md` has `| round1_plaintext_plus_key | yes |`.
4. Both runs end with `RUN HEALTH: PASS`.
The last-round rows are secondary: record them, they are not part of the gate.

**3.6 Goal: record, pin, commit.** In `progress.md`, insert the block "Phase E, block
E1: results" from `PROGRESS_TEMPLATES.md` directly before
`## Environment changes made for Phase A and B`, filled with the real values. Then run
the test suite (`Ran 172 tests`, `OK`), then the two `G:` commands of step 2.3 with
the commit message
`-m "Phase E block E1: window-schedule runs and differential tests" -m "<one sentence per result: the eight verdicts, gate G-P2a, the P2a and P2b effect sizes>"`.
Record the hash as `COMMIT_E1`.

**CHECKPOINT 3.** Report: the two batch logs, the twelve analyze lines, the eight
verdict lines, the gate, the P2a and P2b effect tables, `COMMIT_E1`. Ask for decisions
A and C. Wait for "go" together with the answers.

## Phase 4. Block E2: overlap schedule, no interconnect defense (gem5; 75 min)

BLOCKED until decision A (either answer) and decision C.

**4.1 Goal: preregister the overlap experiment before any overlap run exists.**

```
W: R="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference"; test ! -e PREREGISTRATION_OVERLAP.md && cp "$R/docs/PREREGISTRATION_OVERLAP.md" . && EXTRA_DEFS="-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL" sh build.sh 200 "$PWD/build/ovl-n200" 2>&1 | tail -1 && EXTRA_DEFS="-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL" sh build.sh 2000 "$PWD/build/ovl-n2000" 2>&1 | tail -1 && grep -h OFF_PROBE build/ovl-n200/build_manifest.json build/ovl-n2000/build_manifest.json
```

Expected: two `wrote ... (6 binaries)` lines and twice `"OFF_PROBE": 520192,`.
Then, with the Edit tool, add to `README.md` the row under "README rows, Phase 4" in
`PROGRESS_TEMPLATES.md`, directly after the row for `PREREGISTRATION_DRAFT.md`.
Then: test suite (`Ran 172 tests`, `OK`); the two `G:` commands of step 2.3 with
`-m "Preregister the overlap experiment before any overlap run" -m "Adds PREREGISTRATION_OVERLAP.md and the overlap builds (OFF_PROBE 520192 by compile flags only). No overlap run exists at this commit."`.
Record the hash as `COMMIT_OVL_PREREG`.
Acceptance: `git -C "$WT" status --porcelain | wc -l` prints `0`.

**CHECKPOINT 4a (before the pilot run).** Report `COMMIT_OVL_PREREG`. Wait for "go".

**4.2 Goal: the pilot** (one run, about 2 minutes, foreground).

```
W: bash run_arm.sh e2-pilot-c8-s1-n200 r1-scrub ovl-n200 off 8 1466213861 2>&1 | tail -6; python3 -B analysis/aes_leak_analysis.py analyze --run-dir runs/e2-pilot-c8-s1-n200 --out-json runs/e2-pilot-c8-s1-n200.analysis.json --out-md runs/e2-pilot-c8-s1-n200.analysis.md | tail -1; python3 -B analysis/leak_followup.py count --run-dir runs/e2-pilot-c8-s1-n200 --nperm 10000 --out-json runs/e2-pilot-c8-s1-n200.count.json --out-md runs/e2-pilot-c8-s1-n200.count.md | tail -24
```

Pilot gate (from `PREREGISTRATION_OVERLAP.md`, section 6):
1. `run_arm: e2-pilot-c8-s1-n200 gem5_exit=0 ...` and a line
   `... monitor status=PASS records=51200`; no `error=` line.
2. `RUN CHECKS: PASS`.
3. In the count output, the row `| excess_cycles | <mean> | <sd> | <max> |` has
   `<max>` greater than 0.
If 1 or 2 fails: stop and report. If 3 fails (`<max>` is `0.0`): the overlap schedule
did not recreate the channel; stop, report, and do not run the rest of block E2.

**CHECKPOINT 4b (before the block of E2 runs).** Report the pilot's three outputs,
including the full count table. Ask for decision D. Wait for "go".

**4.3 Goal: the eight registered overlap runs.** Background; about 25 to 30 minutes.

```
W: bash run_batch.sh batches/e2-main.txt 4
```

Expected: `BATCH RESULT: PASS`. On failure: stop and report.

**4.4 Goal: run checks.**

```
W: for n in $(grep -v "^#" batches/e2-main.txt | cut -d" " -f1); do python3 -B analysis/aes_leak_analysis.py analyze --run-dir runs/$n --nperm 20 --out-json runs/$n.analysis.json --out-md runs/$n.analysis.md > runs/$n.analysis.log 2>&1; echo "$n analyze_exit=$? $(tail -1 runs/$n.analysis.log)"; done
```

Expected: eight lines `analyze_exit=0 RUN CHECKS: PASS`. Trace recall near 0 is
expected in these arms (the tables stay resident); it is not a failure.

**4.5 Goal: differential tests per arm.**

```
W: for a in oc8 oc1 ow8 ow1; do python3 -B analysis/leak_followup.py diff --a runs/e2-$a-s1-n2000 --b runs/e2-$a-s2-n2000 --out-json runs/e2-$a.diff-s1-s2.json --out-md runs/e2-$a.diff-s1-s2.md > /dev/null; echo "e2-$a exit=$? $(tail -1 runs/e2-$a.diff-s1-s2.md)"; done
```

Decision rule: `INVALID` or `exit=2`: stop. Otherwise record the four verdicts and
continue. Interpretability (section 6 of the overlap preregistration): the `ow8`
result is interpreted only if `oc8` is `DIFFERENT`; `ow1` only if `oc1` is
`DIFFERENT`. Record which holds; do not skip any step because of it.

**4.6 Goal: collision-count test for every run.**

```
W: for n in $(grep -v "^#" batches/e2-main.txt | cut -d" " -f1); do python3 -B analysis/leak_followup.py count --run-dir runs/$n --nperm 10000 --out-json runs/$n.count.json --out-md runs/$n.count.md > runs/$n.count.log 2>&1; echo "$n count_exit=$? $(grep -E "^\| (count_dependent|round1_count_plaintext_plus_key|round1_count_plaintext_only) " runs/$n.count.md | tr "\n" " ")"; done
```

Expected: eight lines with `count_exit=0`. Record the three statements per run. An arm
supports a statement only if both of its runs show `yes` for it. There is no gate on
the outcome: every combination is a result.

**4.7 Goal (only with decision D = "include E2x"): the exploratory full-AES arms.**
Background, about 15 minutes: `W: bash run_batch.sh batches/e2-explore.txt 4`; then
steps 4.4 and 4.6 with `batches/e2-explore.txt` in place of `batches/e2-main.txt`, and
step 4.5 with `for a in fw8 fw1`. Read only `count_dependent` from these arms.
Without decision D: skip and list it under "items skipped".

**4.8 Goal: record, pin, commit.** Insert "Phase E, block E2: results" from the
templates into `progress.md` (same place as before), run the test suite, then the two
`G:` commands of step 2.3 with
`-m "Phase E block E2: overlap schedule without interconnect defense" -m "<verdicts and statements>"`.
Record `COMMIT_E2`.

**CHECKPOINT 5.** Report the pilot, the batch log, the four verdicts, the statements
table, `COMMIT_E2`. Wait for "go".

## Phase 5. Block E3: full defense in the overlap schedule (gem5; 60 min)

BLOCKED until decision A (either answer).

**5.1 Goal: log D4 before any defended run.**

```
W: python3 -B "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/postdoc-review/reference/log_deviations.py" . D4
```

Expected: two `appended D4 to ...` lines. Then the test suite, then the two `G:`
commands of step 2.3 with
`-m "Log deviation D4 before the full-defense runs" -m "The full defense is evaluated in the overlap schedule only, with a new gem5 tree built from the stored defense patch plus this experiment's gem5_ext."`.
Record `COMMIT_D4`.

**5.2 Goal: a new gem5 tree with both defenses and the tracing extension.** The only
permitted effect on `~/eel5764/gem5` is the worktree metadata that `git worktree add`
writes.

```
W: test ! -e ~/eel5764/gem5-leak-def && git -C ~/eel5764/gem5 worktree add ~/eel5764/gem5-leak-def c8222cc67a399bfc01e8658dd14b30d5bfd634f9 && cd ~/eel5764/gem5-leak-def && git apply "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree/experiments/respq-defense-20261018/gem5-respq.patch" && git status --porcelain | wc -l && ls -l ~/eel5764/leak-ext/gem5_ext/
```

Expected: `15` (10 modified and 5 new files) and the four files of `gem5_ext`.
If `~/eel5764/gem5-leak-def` already exists: stop and report.

Build, in the background (about 13 minutes; `-j14`, not more: the host has 15 GiB):

```
W: cd ~/eel5764/gem5-leak-def && { echo "build started $(date "+%F %T")"; scons build/RISCV/gem5.opt -j14 EXTRAS=$HOME/eel5764/leak-ext/gem5_ext < /dev/null; echo "scons exit=$?"; echo "build finished $(date "+%F %T")"; } > ~/eel5764/build_leak_def.log 2>&1; tail -3 ~/eel5764/build_leak_def.log; ls -l ~/eel5764/gem5-leak-def/build/RISCV/gem5.opt
```

Expected: `scons exit=0` and a `gem5.opt` of about 1.0 GB. A warning that GCC 15.2.0
is not officially supported is normal.
On `scons exit` other than 0: report the last 40 lines of the log and stop.

**5.3 Goal: guard. With the defense off, the new binary reproduces a stored run byte
for byte.**

```
W: bash run_arm.sh p0d-r1-scrub-n20 r1-scrub n20 off 16 1466213861 guard 2>&1 | tail -4; python3 -B analysis/leak_followup.py diff --a runs/p0b-r1-scrub-n20 --b runs/p0d-r1-scrub-n20 --allow-same-seed --out-json runs/p0d.guard-diff.json --out-md runs/p0d.guard-diff.md | tail -1
```

Expected: `monitor status=PASS records=5120` and `DIFF VERDICT: IDENTICAL`.
Acceptance: `IDENTICAL`. Anything else: stop and report; run nothing with this binary.

**CHECKPOINT 6 (before the defended runs).** Report the build tail, the binary size,
the guard verdict, `COMMIT_D4`. Wait for "go".

**5.4 Goal: the four defended runs.** Background, about 15 minutes.

```
W: bash run_batch.sh batches/e3-defense.txt 4
```

Expected: `BATCH RESULT: PASS`.

**5.5 Goal: the defense was really on, and the run checks pass.**

```
W: for n in $(grep -v "^#" batches/e3-defense.txt | cut -d" " -f1); do python3 -B analysis/aes_leak_analysis.py analyze --run-dir runs/$n --nperm 20 --out-json runs/$n.analysis.json --out-md runs/$n.analysis.md > runs/$n.analysis.log 2>&1; echo "$n analyze_exit=$? $(tail -1 runs/$n.analysis.log) slots=$(grep -c "\"tdma_slot_cycles\": 4" runs/$n/defense_config.json) respq=$(grep -c "\"respq\": true" runs/$n/defense_config.json) prefixes=$(grep -c "^response_domain_prefixes=cpu0. cpu1." runs/$n/config.ini) tdma_lines=$(grep -c "\.tdma" runs/$n/stats.txt) violations=$(grep -E "\.(tdmaOverruns|tdmaDownstreamRefusals|tdmaExpressBypasses) " runs/$n/stats.txt | awk "{s+=\$2} END {print s+0}")"; done
```

Acceptance, for each of the four lines: `analyze_exit=0 RUN CHECKS: PASS`, `slots=1`,
`respq=1`, `prefixes=1`, `tdma_lines` at least 1, `violations=0`. Any other value:
stop and report (the run is not a valid defended run).

**5.6 Goal: differential tests.**

```
W: for a in od8 od1; do python3 -B analysis/leak_followup.py diff --a runs/e3-$a-s1-n2000 --b runs/e3-$a-s2-n2000 --out-json runs/e3-$a.diff-s1-s2.json --out-md runs/e3-$a.diff-s1-s2.md > /dev/null; echo "e3-$a exit=$? $(tail -1 runs/e3-$a.diff-s1-s2.md)"; done
```

Expected (forecast, not a gate): `IDENTICAL` twice. `INVALID`: stop. `DIFFERENT` or
`LATENCY_IDENTICAL`: a finding; run the `count` command of step 4.6 on both runs of
that arm and record it.

**5.7 Goal: record, pin, commit.** Insert "Phase E, block E3: results" from the
templates into `progress.md`; also add to the "Environment changes" section the
sentence given there. Test suite, then the two `G:` commands of step 2.3 with
`-m "Phase E block E3: full defense in the overlap schedule" -m "<guard verdict, defense checks, two verdicts>"`.
Record `COMMIT_E3`.

**CHECKPOINT 7.** Report everything from 5.3 to 5.7. Wait for "go".

## Phase 6. Close (no gem5; 20 min)

**6.1**

```
W: python3 -B -m unittest discover -s tests -t . 2>&1 | tail -4
```

```bash
G: EXP="/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree/experiments/aes-leakage"; WT="/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree"; cd "$EXP" && python -B preserve.py verify; git -C "$WT" status --porcelain | wc -l; git -C "$WT" log --oneline 434b16b..HEAD; git -C "$WT" branch -vv | grep "^\*"
```

Acceptance: `Ran 172 tests`, `OK`; a `PRESERVED:` line; `0`; the commits of this plan
and no others; nothing was pushed (you never ran `git push`).

**6.2** Write `postdoc-review/exec/FINAL_REPORT.md` from the template below. Do not
edit the paper; the paper text is BLOCKED on decision A = "instructor approved" and is
the user's task.

## Final-report template (`postdoc-review/exec/FINAL_REPORT.md`)

```markdown
# Phase E execution report

Date finished: <YYYY-MM-DD>. Worktree head: <hash>. Branch: experiment/aes-leakage. Nothing pushed.

## Evidence per step
| Step | Command (short) | Output line(s) that show the result | Pass/Fail |
|---|---|---|---|
| 0.1 | git status / HEAD | ... | |
| ... one row per step of this plan, in order ... | | | |

## Results
### Block E1 (window schedule)
| Arm | Runs | Differential verdict(s) | Notes |
| unpartitioned, 8 monitor ways | e1-c8-s1/s2 | | |
| unpartitioned, 1 monitor way | e1-c1-s1/s2 | | |
| way partition 8/8 | e1-w8-s1/s2/s3 | | |
| way partition 1/15 | e1-w1-s1/s2/s3 | | |
P2a (registered rule / D2 rule): round-1 bytes ../16, last-round bytes ../16, effect ... cycles per probed line, exact indicator ..., recall ...
P2b: effect ... cycles per probed line, fraction of P2a retained ..., recall ...
Gate G-P2a: <met / not met, with the four lines>

### Block E2 (overlap, no interconnect defense)
Pilot: excess_cycles mean/sd/max ..., delayed_walks mean ...
| Arm | Verdict | count_dependent (s1, s2) | round1 plaintext+key (s1, s2) | round1 plaintext only (s1, s2) | Interpretable? |

### Block E3 (overlap, full defense)
Guard p0d vs p0b: ... Defense checks: ... | Arm | Verdict |

## Deviations logged
| ID | Date | Commit | Logged before which runs |

## Commits
| Name | Hash | Subject |

## Items skipped, and why
## Anything that did not match the plan
## Decisions still open for the user
```
