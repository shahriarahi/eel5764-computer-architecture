# Phase E execution report

Date finished: 2026-11-12. Worktree head: 2ccad2d. Branch: experiment/aes-leakage. Nothing pushed.

Full command output for every step is in `postdoc-review/exec/LOG.md`. All results are simulator-only
statements about this gem5 configuration (v25.1.0.1, RISC-V SE mode, 2 x TimingSimpleCPU at 2 GHz,
4 KiB L1D, 256 KiB 16-way LLC); no hardware claim is made. Differential verdicts cover the tested
plaintext streams only (seeds S1 to S3).

## Evidence per step

| Step | Command (short) | Output line(s) that show the result | Pass/Fail |
|---|---|---|---|
| 0.1 | `git status`, HEAD, branch | `porcelain-lines=0`, `434b16b`, `experiment/aes-leakage` | Pass |
| 0.2 | WSL `pwd`, `nproc`, test suite | `20`; `Ran 139 tests in 13.991s`, `OK` | Pass |
| 0.3 | `ls` of the reference directories | every name the plan lists is present (7 top-level, 5 batch lists, 3 test files, 3 docs) | Pass |
| 0.4 | create `exec/LOG.md` | file written | Pass |
| 1.1 | copy `test_fixes.py`, run | `Ran 4 tests in 0.893s`, `FAILED (failures=1, errors=2)` (fails as the plan requires) | Pass |
| 1.2 | `apply_fixes.py` | `applied: analysis/aes_leak_analysis.py`, `applied: preserve.py`, `Ran 4 tests`, `OK` | Pass |
| 1.3 | copy new modules, run their tests | `Ran 29 tests in 11.313s`, `OK` | Pass |
| 1.4 | full suite | `Ran 172 tests in 25.127s`, `OK` | Pass |
| 1.5 | `diff` and `effect` on stored runs | `\| p_xor_k \| 2176.722 \| 136.0451 \| 16/16 \| 16/16 \|`, `\| p_only \| -142.009 \| -8.8756 \| 0/16 \| 0/16 \|`, `exact indicator: True`, `RUN HEALTH: PASS`; `DIFF VERDICT: IDENTICAL` appeared only on re-run (see "did not match") | Pass on content |
| 1.6 | `build.sh 500`, dry runs | `wrote .../build/n500/build_manifest.json (6 binaries)`, `DRY RUN: pre-flight passed, nothing was run` twice | Pass |
| 2.1 | `log_deviations.py D1 D2 D3` | two `appended D1, D2, D3 to ...` lines, `PREREGISTRATION_DRAFT.md:4`, `progress.md:4` | Pass |
| 2.2 | ledger edits, suite | `Ran 172 tests in 25.262s`, `OK` | Pass |
| 2.3 | `preserve.py`, commit | `CAPTURED 269 files (base 45d21e259c)`, `PRESERVED: 269 files hash-match ...`, `6986be8`, `0` | Pass |
| 3.1 | `run_batch.sh batches/e1-diff.txt 4` | `BATCH RESULT: PASS`; ten lines `gem5_exit=0 ... OK` (177 to 184 s) | Pass |
| 3.2 | `run_batch.sh batches/e1-full.txt 2` | `BATCH RESULT: PASS`; `e1-p2a` 606 s, `e1-p2b` 670 s, no `probe_deadline` | Pass |
| 3.3 | `analyze` on 12 runs | first pass: 6 unpartitioned/full-AES lines `RUN CHECKS: PASS`, 6 partitioned lines `RUN CHECKS: FAIL` (`way_isolation \| FAIL \| stats lack wayOccupancy`); after the approved fix (3.3a) all 12 `analyze_exit=0 RUN CHECKS: PASS` and six `way_isolation \| PASS \| ... : 0` | Fail, then Pass after fix |
| 3.3a | unplanned parser fix, user-approved | test first: `AssertionError: 0 != 48`, `FAILED (failures=1)`; after fix `Ran 173 tests in 25.152s`, `OK` | Pass |
| 3.4 | 8 `diff` runs | eight `exit=0 DIFF VERDICT: IDENTICAL` | Pass |
| 3.5 | `effect` on P2a, P2b; gate G-P2a | G-P2a lines 1 to 4 all present (see Results); both runs `RUN HEALTH: PASS` | Pass |
| 3.6 | record, pin, commit | `Ran 173 tests`, `OK`; `CAPTURED 459 files`, `PRESERVED: 459 files hash-match`; `974730e`, `0` | Pass |
| 4.1 | preregister overlap, two builds | two `wrote ... (6 binaries)`, twice `"OFF_PROBE": 520192,`; `Ran 173 tests`, `OK`; `a3469eb`, `0` | Pass |
| 4.2 | pilot `e2-pilot-c8-s1-n200` | `gem5_exit=0 seconds=77`, `monitor status=PASS records=51200`, `RUN CHECKS: PASS`, `excess_cycles` max 160.0 | Pass (pilot gate met) |
| 4.3 | `run_batch.sh batches/e2-main.txt 4` | `BATCH RESULT: PASS`; eight lines `gem5_exit=0 ... OK` (738 to 774 s) | Pass |
| 4.4 | `analyze` on 8 runs | eight `analyze_exit=0 RUN CHECKS: PASS` | Pass |
| 4.5 | 4 `diff` runs | `oc8`, `oc1`, `ow8`, `ow1` all `exit=0 DIFF VERDICT: DIFFERENT` | Pass (no gate) |
| 4.6 | `count` on 8 runs | eight `count_exit=0` with the statements below | Pass (no gate) |
| 4.7 | E2x batch, 4.4/4.5/4.6 on it | `BATCH RESULT: PASS` (699 to 723 s); four `RUN CHECKS: PASS`; `fw8`, `fw1` `DIFFERENT`; four `count_exit=0` | Pass |
| 4.8 | record, pin, commit | `Ran 173 tests`, `OK`; `CAPTURED 706 files`, `PRESERVED: 706 files hash-match`; `146dee6`, `0` | Pass |
| 5.1 | `log_deviations.py D4` | `appended D4 to PREREGISTRATION_DRAFT.md`, `appended D4 to progress.md`; `9a37b49`, `0` | Pass |
| 5.2 | new gem5 tree and build | `15` changed files, four `gem5_ext` files; `scons exit=0`, `gem5.opt` 1003677648 bytes | Pass |
| 5.3 | guard `p0d` vs `p0b` | `monitor status=PASS records=5120`, `DIFF VERDICT: IDENTICAL` | Pass |
| 5.4 | `run_batch.sh batches/e3-defense.txt 4` | `BATCH RESULT: PASS`; four lines `gem5_exit=0 ... OK` (1485 to 1549 s) | Pass |
| 5.5 | `analyze` plus defense-on checks | four lines `analyze_exit=0 RUN CHECKS: PASS slots=1 respq=1 prefixes=1 tdma_lines=32 violations=0` | Pass |
| 5.6 | 2 `diff` runs | `e3-od8 exit=0 DIFF VERDICT: IDENTICAL`, `e3-od1 exit=0 DIFF VERDICT: IDENTICAL` | Pass |
| 5.7 | record, pin, commit | `Ran 173 tests`, `OK`; `CAPTURED 783 files`, `PRESERVED: 783 files hash-match`; `2ccad2d`, `0` | Pass |
| 6.1 | suite, `verify`, status, log | `Ran 173 tests in 25.468s`, `OK`; `PRESERVED: 783 files hash-match`; `0`; six commits since `434b16b`; branch `experiment/aes-leakage`, no upstream | Pass |
| 6.2 | this report | written | n/a |

## Results

### Block E1 (window schedule)

| Arm | Runs | Differential verdict(s) | Notes |
|---|---|---|---|
| unpartitioned, 8 monitor ways | e1-c8-s1/s2 | S1/S2 IDENTICAL | run checks PASS |
| unpartitioned, 1 monitor way | e1-c1-s1/s2 | S1/S2 IDENTICAL | run checks PASS |
| way partition 8/8 | e1-w8-s1/s2/s3 | S1/S2, S1/S3, S2/S3 all IDENTICAL | run checks PASS, way isolation 0 blocks outside |
| way partition 1/15 | e1-w1-s1/s2/s3 | S1/S2, S1/S3, S2/S3 all IDENTICAL | run checks PASS, way isolation 0 blocks outside |

P2a (`e1-p2a-s1-n2000`, registered rule / D2 rule): round-1 bytes 16/16 under both, last-round bytes
16/16 under both, effect 17.3498 cycles per probed line for `p_xor_k` (2.0353 for `lr_c_xor_k10`),
exact slow-versus-touched indicator True (123,471 touched and slow; 0 touched and fast; 0 untouched
and slow), trace recall 1.000 and precision 1.000.

P2b (`e1-p2b-s1-n2000`, no scrub): round-1 bytes 0/16 and last-round bytes 0/16 under both rules;
effect -10.2163 cycles per probed line for `p_xor_k`, fraction of P2a retained -0.5888; exact
indicator False; trace recall 0.316, precision 1.000. The registered z rule additionally supports
`lastround_ciphertext_only` on byte 5 (`c_only`, Holm p 0.0181); the D2 permutation rule supports no
statement. The disagreement is reported as D2 requires and is not interpreted.

Gate G-P2a: **met**. (1) P2a analysis has `round1_plaintext_plus_key | yes` and
`round1_plaintext_only | no`. (2) `Recall 1.000, precision 1.000`. (3) P2a effect file has
`round1_plaintext_plus_key | yes`. (4) both runs ended `RUN HEALTH: PASS` (terminal output of
step 3.5; the line is not written into the `.effect.md`).

### Block E2 (overlap, no interconnect defense)

Pilot: `excess_cycles` mean -3.010, sd 12.622, max 160.0; `delayed_walks` mean 0.525. Gate met.

| Arm | Verdict | count_dependent (s1, s2) | round1 plaintext+key (s1, s2) | round1 plaintext only (s1, s2) | Interpretable? |
|---|---|---|---|---|---|
| OC8 unpartitioned, 8 ways | DIFFERENT | yes, yes | yes, yes | no, no | reference arm |
| OC1 unpartitioned, 1 way | DIFFERENT | no, no | no, no | no, no | reference arm |
| OW8 way partition 8/8 | DIFFERENT | yes, yes | yes, yes | no, no | yes (OC8 DIFFERENT) |
| OW1 way partition 1/15 | DIFFERENT | no, no | no, no | no, no | yes (OC1 DIFFERENT) |
| FW8 (exploratory) | DIFFERENT | yes, yes | not read | not read | exploratory; only `count_dependent` read |
| FW1 (exploratory) | DIFFERENT | yes, yes | not read | not read | exploratory; only `count_dependent` read |

Size of the signal (`lines_round1_p_xor_k` against `excess_cycles`, r and Holm p): OC8 +0.4559
(0.0008) and +0.4421 (0.0008); OW8 +0.0834 (0.0008) and +0.0611 (**0.0384**); OC1 and OW1 all
within -0.032 to -0.012, Holm p 1. OW8 is therefore supported but at about 14 to 18% of OC8's
correlation, and its second run is the closest to the 0.05 line of any run called significant.
Largest |r| observed: +0.4559, `lines_round1_p_xor_k` against `excess_cycles`, `e2-oc8-s1-n2000`.
Key-free model and shuffled control: Holm p is 1 in every row except one shuffled control (0.6615).
Largest observed differences between seeds: 16 cycles in 3 sets (8 ways), 4 cycles in 10 sets
(1 way). At depth 1, `oc1` and `ow1` logs differ in only 162 of 8,192,000 bytes per seed.
Under the overlap preregistration's reading: OW8 is DIFFERENT with `round1_count_plaintext_plus_key`
supported, so under way partitioning alone the crossbar channel carries a key-dependent collision
count (small, near the threshold in one run); OW1 is DIFFERENT with no statement supported, so the
log depends on the plaintext stream but not through the collision count at this N. "Not supported"
is absence of detection at N = 2000, not proof of absence.

### Block E3 (overlap, full defense)

Guard p0d vs p0b: `DIFF VERDICT: IDENTICAL` (`monitor status=PASS records=5120`). Defense checks, all
four runs: `tdma_slot_cycles` 4, `respq` true, `response_domain_prefixes=cpu0. cpu1.`, 32 `.tdma`
statistic lines, 12 lines for the three time-slot violation counters per run, all 0; way isolation 0.

| Arm | Verdict |
|---|---|
| OD8 full defense, 8/8 (`e3-od8-s1/s2-n2000`) | IDENTICAL (no latency or timestamp differs; sha256 of both probe logs equal) |
| OD1 full defense, 1/15 (`e3-od1-s1/s2-n2000`) | IDENTICAL (no latency or timestamp differs; sha256 of both probe logs equal) |

The same arms without the interconnect defense (OW8, OW1) were DIFFERENT. Limits: the verdict covers
the two tested plaintext streams; the new binary's guard compared a stored window-schedule run with
the defense off, not an overlap-schedule run.

## Deviations logged

| ID | Date | Commit | Logged before which runs |
|---|---|---|---|
| D1 | 2026-11-12 | 6986be8 | block E1 (no partitioned, defended or overlap data existed) |
| D2 | 2026-11-12 | 6986be8 | block E1 |
| D3 | 2026-11-12 | 6986be8 | block E1 |
| D4 | 2026-11-12 | 9a37b49 | block E3 (the defended runs) |

D0 predates this plan (commit `675c047`). The isolation-parser fix of step 3.3a is recorded in
`progress.md` as a tool bug fix, not as a protocol deviation (the gate is unchanged).

## Commits

| Name | Hash | Subject |
|---|---|---|
| COMMIT_PREP | 6986be8 | Phase E preparation: differential test, effect size, deviations D1 to D3 |
| COMMIT_E1 | 974730e | Phase E block E1: window-schedule runs and differential tests |
| COMMIT_OVL_PREREG | a3469eb | Preregister the overlap experiment before any overlap run |
| COMMIT_E2 | 146dee6 | Phase E block E2: overlap schedule without interconnect defense |
| COMMIT_D4 | 9a37b49 | Log deviation D4 before the full-defense runs |
| COMMIT_E3 | 2ccad2d | Phase E block E3: full defense in the overlap schedule |

## Items skipped, and why

Nothing in the plan was skipped. E2x (step 4.7) was run after the user's decision D ("Go with your
recommendation", read as "include E2x"). Not done because the plan or the action boundaries exclude
it: the paper was not edited; no message (including the instructor question) was sent; nothing was
pushed; the `Open items` list in `progress.md` was not rewritten (see below).

## Anything that did not match the plan

1. **Step 1.5.** `diff ... | tail -1` printed nothing because the tool ends its output with a blank
   line after the verdict; `DIFF VERDICT: IDENTICAL` was confirmed on a re-run. The same happens in
   5.3 (`--out-md` makes the last stdout line `wrote runs/p0d.guard-diff.md`); the verdict was read
   from the `.md` file.
2. **Step 3.3: six partitioned runs failed `way_isolation`** ("stats lack wayOccupancy"). Cause:
   `analysis/aes_leak_analysis.py:383` expected `wayOccupancy::p0::way0` but gem5 writes
   `wayOccupancy_p0::way0` (also in the paper's stored `results/8-8/stats.txt`); the test fixtures
   and the synthetic generator used the wrong spelling, so no earlier test or run could catch it. I
   stopped under rule (b) and reported; the user answered "Go" to a single recommendation; the fix
   was made test-first (one new test, `WayIsolationRealGem5Spelling`), the pattern now accepts both
   spellings, and the six runs were re-analysed (no gem5). **Every later "Ran 172 tests" acceptance
   in the plan therefore reads 173.** The gate itself (`violations == 0`) was not touched.
3. **A write outside the permitted places.** In step 1.5's diagnostic re-run I wrote output to
   `/tmp/diff15.out` in WSL. I deleted it at once and confirmed it was gone; nothing in the repository
   or in any gem5 tree was touched.
4. **Decision wording.** The user's second answer at Checkpoint 3 was labelled "B"; the checkpoint had
   asked for A and C, so it was read as decision C. A bare "Go" at Checkpoint 4b did not include
   "include E2x", so E2x was not started then; "Go with your recommendation" afterwards was read as
   decision D. Both readings are recorded in `LOG.md`.
5. **Step 2.2 template adaptation.** The P1 effect row contains `|` characters; in the
   `progress.md` table I wrote them as `\|` so the cell stays one cell. A short "Tool fix made during
   E1" paragraph was added to the E1 block.
6. **Timings.** E1 differential batch 8 m 58 s (expected about 9); E1 full batch 11 m 10 s
   (11 to 15); E2 main 25 m 41 s (25 to 30); E2x 12 m 4 s (about 15); gem5 build 12 m 17 s
   (about 13); E3 defended batch **25 m 49 s (expected about 15)** because defended runs take about
   1,500 s each against about 750 s undefended.
7. **Commit trailers.** Each commit carries a `Co-Authored-By` line in addition to the plan's message,
   as the session's attribution rule requires.
8. **`progress.md` "Open items" is stale.** It still says the effect-size rule is "not done", that N =
   4000 stands, that P4 needs a defense-patched tree and that the preregistration is a draft. D1 to
   D4 and the E3 build supersede these. The plan names no edit of that section, so I left it.
9. **Working directory drift.** Some `cd` commands moved the tool's working directory; every command
   used absolute paths, so no result was affected.

## Decisions still open for the user

1. **Writing the paper section.** Decision A is "instructor approved", so the extension section is
   unblocked; it is your task. Suggested honest wording of the main findings: in the window schedule
   way partitioning removed the data dependence (eight `IDENTICAL` pairs); in the overlap schedule
   way partitioning alone left a small, key-dependent collision-count signal at 8 monitor ways
   (r about 0.06 to 0.08, one run at Holm p 0.0384) and none detected at 1 way; the full defense made
   the logs byte-identical at both depths. State the limits: tested streams only, one key, one
   workload, one cache configuration, a deterministic simulator, seeds are repeated inputs.
2. **Group review of D1 to D4.** The review suggested each member read and initial D1 to D4 in
   `progress.md`. You approved D1 to D3 and D4 was logged; I added no initials.
3. **P2b rule disagreement.** The paper should state that the registered z rule and the D2
   permutation rule disagree on one P2b statement (`lastround_ciphertext_only`, byte 5), and which
   rule governs (D2 says supported only if both agree).
4. **The stale `Open items` list** in `progress.md` (item 8 above): update it, or leave it as a
   historical note.
5. **Whether and when to merge or push** `experiment/aes-leakage`. It has six local commits and no
   upstream; I never pushed.
