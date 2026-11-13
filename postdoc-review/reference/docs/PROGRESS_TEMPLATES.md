# Text blocks for `README.md` and `progress.md`

Used by `postdoc-review/EXECUTION_PLAN.md`. Copy a block exactly, then replace every
`<...>` placeholder with the real value from your log. Do not copy the headings of
this file that start with `# ` or the sentences in italics.

---

*README rows, Phase 2. Insert directly after the row that starts with*
`| \`analysis/power_synth.py\` |`:

| `analysis/leak_followup.py` | differential test, raw-cycle effect size with permutation p-value, collision-count test (deviations D1, D2) |
| `run_arm.sh` | launches one gem5 run with checked arguments (`DRY_RUN=1` prints the command only) |
| `run_batch.sh` | runs the runs listed in a file under `batches/`, a few in parallel |
| `run_leakage_defense.py` | wrapper that adds request time slots and per-domain LLC response queues (deviation D4) |

---

*README row, Phase 4. Insert directly after the row that starts with*
`| \`PREREGISTRATION_DRAFT.md\` |`:

| `PREREGISTRATION_OVERLAP.md` | second, separate preregistration: the overlap (contention) schedule and the collision-count test |

---

*progress.md block, Phase 2. Insert directly before the line*
`## Environment changes made for Phase A and B`:

## Phase E preparation (<YYYY-MM-DD>)

Done after an outside review (`postdoc-review/POSTDOC_REVIEW.md` in the main
checkout) and before any Phase E run. No gem5 run is part of this entry.

| Item | Evidence |
|---|---|
| Flat-log crash fixed | `anova_p_min` in `analysis/aes_leak_analysis.py` returned through `np.nanargmax` on an all-NaN slice when every set was constant; `tests/test_fixes.py` failed before the fix (`<line from step 1.1>`) and passes after it |
| `preserve.py` no longer pins `.claude/` | assistant-session state under `.claude/` was rewritten by other sessions after the last capture and made `verify` fail; test in `tests/test_fixes.py` |
| `analysis/leak_followup.py` | `diff`, `effect`, `count`; `tests/test_leak_followup.py` (19 tests) |
| `run_leakage_defense.py`, `run_arm.sh`, `run_batch.sh`, `batches/` | `tests/test_run_leakage_defense.py` (10 tests); dry run of both E1 batch files passed |
| Stored runs re-read with the new tools | `p0b` against `p0c`: `<verdict line from step 1.5>`; P1 effect: `<p_xor_k row from step 1.5>`, exact indicator `<True/False>`; output in `runs/p1-r1-scrub-n2000.effect.md` |
| `build/n500` | `sh build.sh 500` |
| Deviations D1, D2, D3 | logged in `PREREGISTRATION_DRAFT.md` section 11 and in the deviations log below, before any Phase E run |
| Test suite | `<Ran ... tests line>` |

The status line at the top of `PREREGISTRATION_DRAFT.md` ("DRAFT. Not frozen.")
predates the freeze recorded in its section 10 and is superseded by it; the frozen
text is not edited.

---

*progress.md block, Phase 3. Insert directly before the line*
`## Environment changes made for Phase A and B`:

## Phase E, block E1: results (<YYYY-MM-DD>)

Window schedule, gem5 `71845ebf...` (`~/eel5764/gem5-leak`), no interconnect defense.
Deviations D1 to D3 were logged at commit `<COMMIT_PREP>` before these runs.

| Arm | Runs | N | Run checks | Differential verdict |
|---|---|---|---|---|
| unpartitioned, 8 monitor ways | `e1-c8-s1-n500`, `e1-c8-s2-n500` | 500 | <PASS/FAIL> | <verdict> |
| unpartitioned, 1 monitor way | `e1-c1-s1-n500`, `e1-c1-s2-n500` | 500 | <PASS/FAIL> | <verdict> |
| way partition 8/8 | `e1-w8-s{1,2,3}-n500` | 500 | <PASS/FAIL>, way isolation <PASS/FAIL> | S1/S2 <verdict>, S1/S3 <verdict>, S2/S3 <verdict> |
| way partition 1/15 | `e1-w1-s{1,2,3}-n500` | 500 | <PASS/FAIL>, way isolation <PASS/FAIL> | S1/S2 <verdict>, S1/S3 <verdict>, S2/S3 <verdict> |

| Run | Registered rule | D2 rule | Effect (cycles per probed line) | Trace recall / precision |
|---|---|---|---|---|
| `e1-p2a-s1-n2000` (full AES, scrub) | round 1 <n>/16, last round <n>/16; statements <list> | statements <list> | `p_xor_k` <value>; `lr_c_xor_k10` <value> | <r> / <p> |
| `e1-p2b-s1-n2000` (full AES, no scrub) | round 1 <n>/16, last round <n>/16 | statements <list> | `p_xor_k` <value>, <fraction> of P2a | <r> / <p> |

Gate G-P2a: <met / not met>. Probe-pass duration of P2a: not measured here; no
`probe_deadline` error occurred: <true/false>. Wall time: <minutes> for the ten
N = 500 runs, <minutes> for the two N = 2000 runs.

What this shows: <two or three sentences, facts only; for example whether the
monitor's log changes with the plaintext stream in each arm>. A differential verdict
covers the tested plaintext streams only.

---

*progress.md block, Phase 4. Insert directly before the line*
`## Environment changes made for Phase A and B`:

## Phase E, block E2: results (<YYYY-MM-DD>)

Overlap schedule (`OFF_PROBE` = 520,192 by compile flags; `build/ovl-n200`,
`build/ovl-n2000`), victim `r1-scrub`, no interconnect defense. Preregistered in
`PREREGISTRATION_OVERLAP.md` at commit `<COMMIT_OVL_PREREG>` before any overlap run.

Pilot `e2-pilot-c8-s1-n200`: `<monitor status line>`; run checks <PASS/FAIL>;
`excess_cycles` mean <v>, sd <v>, max <v>; `delayed_walks` mean <v>. Pilot gate:
<met / not met>.

| Arm | Runs | Differential verdict | `count_dependent` (S1, S2) | `round1_count_plaintext_plus_key` (S1, S2) | `round1_count_plaintext_only` (S1, S2) |
|---|---|---|---|---|---|
| OC8: unpartitioned, 8 ways | `e2-oc8-s{1,2}-n2000` | <verdict> | <yes/no>, <yes/no> | <yes/no>, <yes/no> | <yes/no>, <yes/no> |
| OC1: unpartitioned, 1 way | `e2-oc1-s{1,2}-n2000` | <verdict> | | | |
| OW8: way partition 8/8 | `e2-ow8-s{1,2}-n2000` | <verdict> | | | |
| OW1: way partition 1/15 | `e2-ow1-s{1,2}-n2000` | <verdict> | | | |

Interpretability: OW8 is interpreted only if OC8 is `DIFFERENT`: <yes/no>; OW1 only
if OC1 is `DIFFERENT`: <yes/no>. Exploratory arms FW8 and FW1: <run / not run>;
`count_dependent` <values>. Largest |r| observed: <model, feature, value, run>.

What this shows: <two or three sentences, facts only>. "Not supported" is absence of
detection at N = 2000, not proof of absence.

---

*progress.md block, Phase 5. Insert directly before the line*
`## Environment changes made for Phase A and B`:

## Phase E, block E3: results (<YYYY-MM-DD>)

Full defense (way partition, request time slots of 4 cycles, per-domain LLC response
queues) in the overlap schedule. Deviation D4 logged at commit `<COMMIT_D4>` before
these runs.

| Item | Result |
|---|---|
| Tree | `~/eel5764/gem5-leak-def`: `c8222cc` plus `experiments/respq-defense-20261018/gem5-respq.patch`; `git status --porcelain` lists <n> files |
| Build | `scons build/RISCV/gem5.opt -j14 EXTRAS=$HOME/eel5764/leak-ext/gem5_ext`: `<scons exit line>`, <start> to <finish>; executable <bytes> bytes |
| Guard | `p0d-r1-scrub-n20` (defense binary, defense off) against `p0b-r1-scrub-n20`: `<verdict line>` |
| Defense active | per run: `tdma_slot_cycles` 4, `respq` true, `response_domain_prefixes=cpu0. cpu1.`, time-slot violation counters sum <n> |

| Arm | Runs | Run checks | Differential verdict |
|---|---|---|---|
| OD8: full defense, 8/8 | `e3-od8-s{1,2}-n2000` | <PASS/FAIL>, way isolation <PASS/FAIL> | <verdict> |
| OD1: full defense, 1/15 | `e3-od1-s{1,2}-n2000` | <PASS/FAIL>, way isolation <PASS/FAIL> | <verdict> |

What this shows: <two or three sentences, facts only>.

*Also add this sentence at the end of the section*
`## Environment changes made for Phase A and B`:

For Phase E block E3: a new gem5 worktree `~/eel5764/gem5-leak-def` (which adds
metadata under `~/eel5764/gem5/.git/worktrees/`) and the build log
`~/eel5764/build_leak_def.log`; none of the existing gem5 trees was modified.
