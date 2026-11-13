# Progress ledger

Branch `experiment/aes-leakage`, started from `experiment/tdma-prototype` at
`45d21e2`. Simulator only. Every entry points to a file, a command or a test.
No defense result exists yet. The gem5 runs so far are the Phase B guard (the
paper's own configuration), the 20-window Phase C smoke runs (machinery checks;
their statistics are observations only), and P1, the 2,000-window positive control
of the unpartitioned configuration, which is a gate for the method and says nothing
about any defense.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| Phase A | code, builds, adapter, analysis, docs, tests (no gem5) | done 2026-11-12 |
| Phase B | build the tracing gem5, run the byte-identical guard | done 2026-11-12, at the group's explicit request; guard PASS, see "Phase B: results" |
| Phase C | P0: 20 windows, no partition, 16 monitor ways, round-1 lookups | done 2026-11-12: attempt 1 FAILED its deadline gate, root-caused, fixed (D0), attempt 2 PASSED; see "Phase C: results" |
| Phase D | P1: 2,000-window positive control | done 2026-11-12: gate G1 PASSED, see "Phase D: results" |
| Phase E | P2 to P4 per `PREREGISTRATION_DRAFT.md` | after D; P4 needs a defense-patched gem5 tree and an adapter change |

## Phase A: deliverables

| # | Deliverable | Evidence |
|---|---|---|
| 1 | `leak_schedule.h` | `tests/test_schedule.py`: constants, key, splitmix64 vectors and plaintext streams agree between the C header (host-compiled) and Python for four seeds, normal and TVLA |
| 2 | `aes_leak_ext.c` | `tests/test_aes_ext.py`: FIPS-197 C.1 through the paper's own encrypt code; round-1 mode loads exactly the 16 round-1 words; checksums equal the numpy reference |
| 3 | `victim_leak.c` | `tests/test_qemu_victim.py`: under `qemu-riscv64` with a fake clock (N = 8) it prints the self-test PASS, the key, the header, and plaintext and ciphertext checksums equal to Python, for all five variants |
| 4 | `monitor_leak.c` | `tests/test_qemu_monitor.py`: N = 4, A = 2 gives a valid `probe_bin_v2` file of N x 256 records with correct interval and set fields |
| 5 | `build.sh`, `build_manifest.json` | `tests/test_build.py`; same CFLAGS as `workloads/build.sh` (tested); two builds of the same N into different directories are byte-identical |
| 6 | `gem5_ext/` | `tests/test_gem5_ext_diff.py` (additions only, default off) and `gem5_syntax_check.sh` (type check against real gem5 headers) |
| 7 | `gem5_build.md` | `tests/test_docs.py` checks the quoted hash, flags and path length against the stored run |
| 8 | `run_leakage.py` | `tests/test_run_leakage.py`: loads the frozen config without running it, overrides, refuses bad builds and gem5 without the victim parameters; driven with a fake `m5` |
| 9 | `analysis/aes_leak_analysis.py` | `tests/test_analysis.py` (run-dir reader, line map, 4-line sbox model, ground truth, way isolation, `synth --run-dir` round trip) and `selftest` |
| 10 | `tests/` | `python3 -B -m unittest discover -s tests -t .` |
| 11 | docs, `preserve.py` | `README.md`, `PREREGISTRATION_DRAFT.md`, this file; `tests/test_preserve.py` |

Scope decision applied (2026-11-12): the analysis does not score key guesses, and
the work is labelled as going beyond the accepted proposal. See `README.md`.

## Phase A: facts established

* **AES code is the paper's.** `aes128_encrypt_block` (288 instructions),
  `aes128_expand_key` (85) and `aes_ttable_init` (171) in `victim_leak_full_scrub`
  are instruction for instruction identical to the paper's `workloads/victim_l1d4k`,
  differing only in 4, 2 and 18 pc-relative address operands (disassembly compared
  with `riscv64-linux-gnu-objdump`, addresses masked).
* **Table layout** (`riscv64-linux-gnu-nm -S`), `victim_leak_full_scrub` against
  the paper's `victim_l1d4k`: 68 contiguous 64-byte lines in both; line offsets 0
  (sbox), 4, 20, 36, 52 (te0..te3) in both; two 4 KiB pages in both. Base address
  `0x14080` against `0x11080` (the same in-page offset). `victim_leak_full_noscrub`
  starts at `0x12040`. `monitor_leak` has `probe_lines` at address 73856, size
  262144, the same as the paper's `monitor_v3_l1d4k`.
* **Tracing patch:** the reference patch applies cleanly to the frozen sources and
  the patched `requestor_partition_manager.cc` type-checks against the real
  gem5 v25.1.0.1 headers (`g++ -fsyntax-only`, two generated headers stood in
  for). A deliberately injected error is caught, and restoring the file restores
  the pass. This was not a gem5 build; the real build is in Phase B below.
* **Splitmix64 test vectors** in the task text were recomputed independently and
  are correct (seed 0, and the three plaintexts of seed 0x5764A5E5).
* **Synthetic false-positive rate** (`synthetic_power.md`, 400 null runs): decision
  rule 15 runs (3.75%), any hypothesis 21 runs (5.25%). Synthetic data only.

## Binary hashes (`build.sh`, riscv64-linux-gnu-gcc 15.2.0), current after Phase C

Rebuilt during Phase C with the 4 KiB scrub (deviation D0 below). The three scrub
binaries (`r1_scrub`, `full_scrub`, `tvla`) changed; `monitor_leak` and the two
no-scrub binaries did not, because the scrub code is compiled out of them. The
Phase A hashes of the changed binaries are in the git history (commits up to
`44099f9`); the first P0 attempt used them.

`build/n2000/` (N_WIN = 2000):

| Binary | sha256 |
|---|---|
| `victim_leak_r1_scrub` | `279b5bcc1cd9ecd9954fbe48363e72724499ec3d4b0dc5c281431677309892cf` |
| `victim_leak_r1_noscrub` | `e3e9eb9a0245803df067c88c01a5447496d8aef04c749178da148aaa0fe82728` |
| `victim_leak_full_scrub` | `a918e035fb6a324d6041b192cc1ae590133828a08ac15632a9eae77241f9477c` |
| `victim_leak_full_noscrub` | `d5fada0f9b37d97edcd9ed91043cbe2417af282c9c7d45da7e589507775bd25d` |
| `victim_leak_tvla` | `f2fee1c37926f71ca9107e95e74629b0ee47940d1d03fc3813f5fcebb2cf8263` |
| `monitor_leak` | `6a6eaae9dc234abec81dd932cc56b06e90b9664aa39e15c9ddeb3162740ea12f` |

`build/n20/` (N_WIN = 20):

| Binary | sha256 |
|---|---|
| `victim_leak_r1_scrub` | `a01c3858959c01205e697ba40298f7da339ddf35577f93ca9749948cfbe7782d` |
| `victim_leak_r1_noscrub` | `6dbcf8c7ad4a67582ef7c8dc0397a6395f875f3afaeb33d200a3d257379e344d` |
| `victim_leak_full_scrub` | `13a3594f2e5d3be6f76ce939f4e1582bba08bb3c184bf39b923567c6bad13599` |
| `victim_leak_full_noscrub` | `f5653093e5a3d643cd864fc4fa52aaf737e5756e80625a8d63ca8cdb01da6ccb` |
| `victim_leak_tvla` | `f6b20b5bb3f7adf48e484cca311a4b04d64c3fac4790abb71cc6172178d4f9bb` |
| `monitor_leak` | `3ac5aad6ce8aa97ca574fd6829ca6700f17813e65f082e6fb8a125382cfdc7df` |

## Phase B: results (2026-11-12)

Run at the group's explicit request; the steps are those of `gem5_build.md`.

| Item | Result |
|---|---|
| Tree | `~/eel5764/gem5-leak`, detached at `c8222cc67a399bfc01e8658dd14b30d5bfd634f9`, clean |
| `EXTRAS` | `~/eel5764/leak-ext/gem5_ext`, a symlink to `experiments/aes-leakage/gem5_ext` |
| Build | `scons build/RISCV/gem5.opt -j14 EXTRAS=...`: exit 0, 12 min 38 s (11:37:43 to 11:50:21). `-j14` rather than `-j$(nproc)` = 20 to stay within this machine's 15 GB of RAM; the project's earlier rebuild notes also use `-j14`; `-j20` was not tried |
| Warnings | GCC 15.2.0 "not officially supported" (as in earlier builds); capstone header not found (not used) |
| Executable | `build/RISCV/gem5.opt`, 1,003,212,864 bytes, sha256 `71845ebf51381bce66fa5926f7ddfb324cab9cfc59128afbc985a7053d2f8c5a` |
| Tracing in the build | `debug/VictimTable.cc` and the patched `requestor_partition_manager.cc` were compiled; `gem5.opt --debug-help` lists `VictimTable: LLC fills of the traced victim table range` |
| Guard | `sweep-v3/seed-5764a5e5/UNPARTITIONED-A8` re-run with the original config from the original project root, output directory of 139 characters (probe path 150, as stored): **`cmp` reports `probes.bin` byte-identical**; both files are 262,144 bytes with sha256 `0ee71c2389afbabf2bb74393dd3b9c2a081c3c6f10ecbacb322a1c239a89848e`; the run took 47.6 s; the guest output matches the stored run (`encryptions=23903 sink=132`, `monitor status=PASS records=16384`) |
| Whole `stats.txt` | Compared with the stored run's, after dropping host-dependent lines: the only differences are `hostOpRate` (wall-clock speed) and the four new `victimTable*` statistics, all zero. Every simulated statistic is identical |

Guard output directory: `~/eel5764/guard-leak/` (a 139-character name made of `g`), outside the repository.

## Phase C: results (2026-11-12)

Run at the group's explicit request ("start phase C"), with the Phase B gem5 binary.

**Attempt 1 failed its deadline gate** (`runs/p0-r1-scrub-n20`, the README command
as written, 8 KiB scrub): gem5 exited 0, but `simout.txt` has
`monitor error=prime_deadline window=1`, so the monitor exited with status 2 after
window 0 and `probes.bin` holds one window (4,096 of 81,920 bytes). The monitor
stopped 1,590,375 cycles after T0; window 1's prime began at 1,114,112, so it ran
about 476,263 cycles against a budget of 458,752 (`OFF_ENC - OFF_PRIME`), over by
about 17,500. The monitor made 12,293 LLC accesses, exactly three 4,096-line passes
plus 5, and 6,498 of them (53%) missed. Window 0's probe pass took 210,098 cycles
(median 513 cycles per set; 25 to 28 sets at 3,000 cycles or more, i.e. all 16 lines
missing). The paper's "about 280,000 cycles for an A=16 pass" was a pass of hits,
so the schedule's margin rested on the wrong case.

**Root cause, tested with one variable** (`runs/diag-*`, A=16, unpartitioned, 20
windows, full AES; only the scrub differs; `r1-scrub` in attempt 1 behaves like
`full-scrub`):

| Run | Prime deadline | Monitor LLC miss rate |
|---|---|---|
| `r1-scrub`, 8 KiB scrub (attempt 1) | missed, window 1 | 53% |
| `full-scrub`, 8 KiB scrub | missed, window 1 | 59% |
| `full-noscrub` | all 20 windows complete | 7% |

The victim's scrub walk allocates one LLC line per scrub line in an LLC whose every
set is full of the monitor's lines. Each allocation evicts the LRU monitor line of
its set, and the monitor then primes by walking its 16 lines in the same order, so
the missing line misses, evicts the next-oldest, and so on: all 16 lines of every
affected set miss.

**Fix and deviation D0 (before any analysis data).** The scrub walk is now 4 KiB
(64 lines, `LEAK_SCRUB_BYTES`, default 4096) instead of 8 KiB: the L1D is 4 KiB and
4-way, so 64 consecutive lines put 4 lines in every set and replace every line under
LRU. `W`, `T0` and every offset are unchanged. A test pins the default size
(`tests/test_build.py`, `ScrubBufferSize`).

**Attempt 2 passed** (`runs/p0b-r1-scrub-n20`, 4 KiB scrub, same command):

* gem5 exit 0; `simout.txt` has the FIPS-197 PASS line, the header, the matching
  `pt_checksum`, and `monitor status=PASS records=5120`; no `error=` line;
  `probes.bin` is the full 81,920 bytes; the monitor's LLC miss rate fell to 15%.
* `analyze --run-dir`: `RUN CHECKS: PASS`; the 68 table lines map to distinct logical
  sets (rotation 130) with 0 set mismatches; ground truth recall 1.000 and precision
  1.000 (289 fills in the AES phase, 0 outside it, 68 before measurement), so the 4
  KiB scrub still flushes the L1D completely.
* Observation, not a result (N = 20): `p_xor_k` significant on 16/16 bytes (min Holm
  p 2.75e-15), `p_only` 0/16, `shuffled` 0/16, last-round hypotheses 0/16 (expected
  in round-1 mode).
* The location-free detection table showed the shuffled control significant on 16/16
  bytes: with 20 windows and 16 classes the ANOVA is degenerate. The analysis now
  flags such rows as unreliable (fewer than 10 windows per class); the decision rule
  uses the attribution table only.

**Measured margins, 4 KiB scrub, A = 16** (`runs/diag-margin-*`, `runs/smoke-*`):

* Probe pass (from `probes.bin` timestamps; budget 454,656): `r1-scrub` median
  183,514, max 201,266; `full-scrub` max 340,796; `tvla` max 335,612;
  `full-noscrub` max 232,092.
* Prime pass: with the prime deadline swept, both `r1-scrub` and `full-scrub` fail at
  window 0 for every prime budget up to 334,464 and pass at 393,216, so the prime
  takes between about 335,000 and 393,000 cycles against the actual 458,752 budget
  (1.17x to 1.37x). Every failure in the sweep was at window 0, so the cold first
  prime is the worst case and a run that survives it should survive the rest; this
  is an inference from the sweep, not shown for 2,000 windows.

**Other variants at N = 20** (`runs/smoke-*`; all `monitor status=PASS`, all
`RUN CHECKS: PASS`): `full-scrub` recall 1.000, precision 1.000 (1,243 fills);
`full-noscrub` recall 0.291, precision 1.000 (362 fills), meaning only about 29% of
the table lines the AES touches reach the LLC when the L1D is not scrubbed; `tvla`
runs.

**Gate G0** (`PREREGISTRATION_DRAFT.md`, section 4): met by attempt 2.

Run directories in `runs/`: `p0-r1-scrub-n20` (attempt 1, kept as evidence of the
failure; its `leak_config.json` records the Phase A binary hashes), `diag-full-scrub-a16-n20`
and `diag-full-noscrub-a16-n20` (the single-variable comparison),
`p0b-r1-scrub-n20` (attempt 2), `diag-margin-*` (the prime-deadline sweep; its
temporary builds were in `/tmp` and are not kept), `smoke-*` (the other three variants), and `*.analysis.{json,md}`.

## Phase D: results (2026-11-12)

Run at the group's standing approval ("From now on, I give you approval"), after
the preregistration was frozen at `675c047` (section 10 of the draft). P1 is
`runs/p1-r1-scrub-n2000`, the README Phase D command verbatim: `r1-scrub`,
`--split off`, `--monitor-ways 16`, `build/n2000` (`victim_leak_r1_scrub`
`279b5bcc...`, `monitor_leak` `6a6eaae9...`), gem5 `71845ebf...`.

| Item | Result |
|---|---|
| Duration | 12:11:14 to 12:22:14, `real` 10 min 59.5 s (the README estimate was about 12 minutes) |
| Run | gem5 exit 0; `monitor status=PASS records=512000`; no `error=` line, so no deadline was missed in 2,000 windows |
| Files | `probes.bin` 8,192,000 B (sha256 `0f6a57bcb349bd25...`), `victim_table.trace` 2,993,601 B (`a508662c004af0c2...`) |
| Run checks | all PASS; 68 table lines mapped to distinct logical sets (rotation 130) |
| **Gate G1** | **PASS**: `p_xor_k` significant on 16/16 bytes (mean z 84.7; Holm p below double precision), `p_only` 0/16, `shuffled` 0/16 |
| Decision rule | `round1_plaintext_plus_key` supported (bytes 0 to 15); the other three statements not supported; every byte labelled `plaintext_plus_key` |
| Other hypotheses | `lr_c_xor_k10`, `c_only`, `lr_shuffled` all 0/16 (round-1 mode has no last-round lookups, so they act as extra null controls) |
| Detection (location-free) | `first_round` 16/16, `shuffled` 0/16, `last_round` 0/16, `c_line` 0/16; all rows reliable |
| Ground truth | 29,095 fills, all inside the AES phase, 0 outside, 68 before measurement; recall 1.000 and precision 1.000; 14.55 fills per window |

What this shows: in the unpartitioned, 16-way, round-1-only configuration the
measurement chain works end to end, and the signal carries plaintext combined with
the key (the key-dependent model is supported, the key-free one is not). It is a
positive control by design. It says nothing about way partitioning or the other
defenses.

Detail (`runs/p1-r1-scrub-n2000.detail.txt`, from `runs/p1_detail.py`, an ad hoc
script not covered by tests):

* **The control channel is noise-free.** A table-line set the AES did not touch took
  exactly 513 cycles every time (sd 0.0, 106,905 observations); a touched set took a
  median 3,127 (mean 3,155). A slow set (1,000 cycles or more) appeared in 100.0% of
  touched windows and 0.00% of untouched ones: the monitor sees exactly which table
  lines were touched. Three sets that are not table lines are slow in more than 99%
  of windows (constant victim data such as the stack).
* **Per-byte strength is uniform:** z from 84.3 (byte 8) to 85.0 (byte 15). `p_only`
  scores z between -8.0 and -3.2: anti-correlated, as expected, because the true line
  differs from `p >> 4` at every byte (every key nibble is nonzero).
* **Deadline margins over 2,000 windows:** probe pass min 170,100, median 180,752,
  p99 185,078, max 196,662 cycles against a 454,656 budget (worst-case headroom
  2.31x); median 180,808 over the first 200 windows and 180,952 over the last 200, so
  no drift; window 0 is the slowest. No prime-deadline miss occurred, which is
  consistent with the earlier inference that the cold window 0 is the worst case for
  the prime (this run does not measure the prime duration itself).
* **Calibration on real data:** with the windows shuffled, 0.3% of z exceed 2.33
  (nominal 1%) and the shuffled z has sd 0.72 (nominal 1): the analytic z is
  conservative here.

## Phase E preparation (2026-11-12)

Done after an outside review (`postdoc-review/POSTDOC_REVIEW.md` in the main
checkout) and before any Phase E run. No gem5 run is part of this entry.

| Item | Evidence |
|---|---|
| Flat-log crash fixed | `anova_p_min` in `analysis/aes_leak_analysis.py` returned through `np.nanargmax` on an all-NaN slice when every set was constant; `tests/test_fixes.py` failed before the fix (`FAILED (failures=1, errors=2)`) and passes after it |
| `preserve.py` no longer pins `.claude/` | assistant-session state under `.claude/` was rewritten by other sessions after the last capture and made `verify` fail; test in `tests/test_fixes.py` |
| `analysis/leak_followup.py` | `diff`, `effect`, `count`; `tests/test_leak_followup.py` (19 tests) |
| `run_leakage_defense.py`, `run_arm.sh`, `run_batch.sh`, `batches/` | `tests/test_run_leakage_defense.py` (10 tests); dry run of both E1 batch files passed |
| Stored runs re-read with the new tools | `p0b` against `p0c`: `DIFF VERDICT: IDENTICAL`; P1 effect: `\| p_xor_k \| 2176.722 \| 136.0451 \| 16/16 \| 16/16 \|`, exact indicator `True`; output in `runs/p1-r1-scrub-n2000.effect.md` |
| `build/n500` | `sh build.sh 500` |
| Deviations D1, D2, D3 | logged in `PREREGISTRATION_DRAFT.md` section 11 and in the deviations log below, before any Phase E run |
| Test suite | `Ran 172 tests`, `OK` (step 1.4: `Ran 172 tests in 25.127s`) |

The status line at the top of `PREREGISTRATION_DRAFT.md` ("DRAFT. Not frozen.")
predates the freeze recorded in its section 10 and is superseded by it; the frozen
text is not edited.

## Phase E, block E1: results (2026-11-12)

Window schedule, gem5 `71845ebf...` (`~/eel5764/gem5-leak`), no interconnect defense.
Deviations D1 to D3 were logged at commit `6986be8` before these runs.

| Arm | Runs | N | Run checks | Differential verdict |
|---|---|---|---|---|
| unpartitioned, 8 monitor ways | `e1-c8-s1-n500`, `e1-c8-s2-n500` | 500 | PASS | IDENTICAL |
| unpartitioned, 1 monitor way | `e1-c1-s1-n500`, `e1-c1-s2-n500` | 500 | PASS | IDENTICAL |
| way partition 8/8 | `e1-w8-s{1,2,3}-n500` | 500 | PASS, way isolation PASS | S1/S2 IDENTICAL, S1/S3 IDENTICAL, S2/S3 IDENTICAL |
| way partition 1/15 | `e1-w1-s{1,2,3}-n500` | 500 | PASS, way isolation PASS | S1/S2 IDENTICAL, S1/S3 IDENTICAL, S2/S3 IDENTICAL |

| Run | Registered rule | D2 rule | Effect (cycles per probed line) | Trace recall / precision |
|---|---|---|---|---|
| `e1-p2a-s1-n2000` (full AES, scrub) | round 1 16/16, last round 16/16; statements `round1_plaintext_plus_key`, `lastround_c_xor_k10` | statements `round1_plaintext_plus_key`, `lastround_c_xor_k10` | `p_xor_k` 17.3498; `lr_c_xor_k10` 2.0353 | 1.000 / 1.000 |
| `e1-p2b-s1-n2000` (full AES, no scrub) | round 1 0/16, last round 0/16; statement `lastround_ciphertext_only` (byte 5 only, `c_only` Holm p 0.0181) | statements none | `p_xor_k` -10.2163, -0.5888 of P2a | 0.316 / 1.000 |

Gate G-P2a: met. Probe-pass duration of P2a: not measured here; no `probe_deadline`
error occurred: true. Wall time: 8 min 58 s for the ten N = 500 runs, 11 min 10 s for
the two N = 2000 runs.

What this shows: in the window schedule the monitor's probe log did not depend on the
plaintext stream in any of the eight seed pairs: the unpartitioned 8-way and 1-way
arms and both way-partitioned arms were byte-identical across seeds. In the
unprotected full-AES run with scrub (P2a) the signal carries plaintext combined with
the key on 16/16 round-1 bytes and 16/16 last-round bytes, and the slow-versus-touched
table is exact (123,471 touched and slow, 0 touched and fast, 0 untouched and slow).
Without the scrub (P2b) the trace sees 31.6% of the touched lines, no round-1
statement is supported, and the one statement the registered z rule supports
(`lastround_ciphertext_only`, byte 5) is not supported under the D2 permutation rule;
this disagreement between the two rules is reported here as D2 requires. A
differential verdict covers the tested plaintext streams only.

Tool fix made during E1 (not a protocol deviation; the gate is unchanged): the
`way_isolation` run check could not read any real partitioned run, because
`analysis/aes_leak_analysis.py` expected the stat name `wayOccupancy::p0::way0` while
gem5 writes `wayOccupancy_p0::way0` (also in the paper's stored `results/8-8/stats.txt`).
The six `e1-w*` runs first reported `way_isolation | FAIL | stats lack wayOccupancy`.
The pattern now accepts both spellings; the test was written first and failed with
`AssertionError: 0 != 48` (class `WayIsolationRealGem5Spelling` in
`tests/test_analysis.py`), the suite is now 173 tests, and the six runs were
re-analysed (analysis only, no gem5): all six show
`way_isolation | PASS | valid LLC blocks outside the assigned ways: 0`.

## Phase E, block E2: results (2026-11-12)

Overlap schedule (`OFF_PROBE` = 520,192 by compile flags; `build/ovl-n200`,
`build/ovl-n2000`), victim `r1-scrub`, no interconnect defense. Preregistered in
`PREREGISTRATION_OVERLAP.md` at commit `a3469eb` before any overlap run.

Pilot `e2-pilot-c8-s1-n200`: `monitor status=PASS records=51200`; run checks PASS;
`excess_cycles` mean -3.010, sd 12.622, max 160.0; `delayed_walks` mean 0.525. Pilot gate:
met.

| Arm | Runs | Differential verdict | `count_dependent` (S1, S2) | `round1_count_plaintext_plus_key` (S1, S2) | `round1_count_plaintext_only` (S1, S2) |
|---|---|---|---|---|---|
| OC8: unpartitioned, 8 ways | `e2-oc8-s{1,2}-n2000` | DIFFERENT | yes, yes | yes, yes | no, no |
| OC1: unpartitioned, 1 way | `e2-oc1-s{1,2}-n2000` | DIFFERENT | no, no | no, no | no, no |
| OW8: way partition 8/8 | `e2-ow8-s{1,2}-n2000` | DIFFERENT | yes, yes | yes, yes | no, no |
| OW1: way partition 1/15 | `e2-ow1-s{1,2}-n2000` | DIFFERENT | no, no | no, no | no, no |

Interpretability: OW8 is interpreted only if OC8 is `DIFFERENT`: yes; OW1 only
if OC1 is `DIFFERENT`: yes. Exploratory arms FW8 and FW1 (victim `full-scrub`, way
partition only; run at the user's decision D, "include E2x"): run; differential verdict
DIFFERENT for both; `count_dependent` yes, yes (FW8) and yes, yes (FW1); the round-1
statements are not read from these arms. All 12 runs passed their run checks, and the
four way-partitioned registered runs and four FW runs show
`way_isolation | PASS` with 0 blocks outside the assigned ways. Largest |r| observed:
`lines_round1_p_xor_k` (equal to `lines_all_rounds` for this victim) against
`excess_cycles`, +0.4559, `e2-oc8-s1-n2000`.

What this shows: in the overlap schedule the monitor's log depends on the plaintext
stream in all four registered arms, including both way-partitioned arms (verdict
`DIFFERENT`), whereas the window-schedule way-partitioned arms of E1 were `IDENTICAL`
(different victim and N, so this is a comparison, not a single-variable result). With an
8-way monitor, both OC8 and OW8 support `count_dependent` and
`round1_count_plaintext_plus_key` and not the plaintext-only statement, which under the
overlap preregistration's reading means that under way partitioning alone (8/8) the
crossbar channel carries a key-dependent collision count. The effect is much smaller
when partitioned: r between the key-dependent count and `excess_cycles` is +0.4559 and
+0.4421 for OC8 but +0.0834 (Holm p 0.0008) and +0.0611 (Holm p 0.0384) for OW8, about
14 to 18% of OC8's, with the second OW8 run close to the 0.05 line. With a 1-way monitor
no statement is supported in either OC1 or OW1 although the logs differ (at most 4
cycles in 10 sets, against 16 cycles in 3 sets at 8 ways); by the preregistered reading,
OW1 is `DIFFERENT` with no statement supported, so the monitor's log depends on the
plaintext stream but not through the collision count at this N. At depth 1 the
partitioned and unpartitioned logs differ in only 162 of 8,192,000 bytes (each seed).
"Not supported" is absence of detection at N = 2000, not proof of absence.

## Phase E, block E3: results (2026-11-12)

Full defense (way partition, request time slots of 4 cycles, per-domain LLC response
queues) in the overlap schedule. Deviation D4 logged at commit `9a37b49` before
these runs.

| Item | Result |
|---|---|
| Tree | `~/eel5764/gem5-leak-def`: `c8222cc` plus `experiments/respq-defense-20261018/gem5-respq.patch`; `git status --porcelain` lists 15 files |
| Build | `scons build/RISCV/gem5.opt -j14 EXTRAS=$HOME/eel5764/leak-ext/gem5_ext`: `scons exit=0`, 2026-11-12 19:43:09 to 19:55:26; executable 1003677648 bytes |
| Guard | `p0d-r1-scrub-n20` (defense binary, defense off) against `p0b-r1-scrub-n20`: `DIFF VERDICT: IDENTICAL` |
| Defense active | per run: `tdma_slot_cycles` 4, `respq` true, `response_domain_prefixes=cpu0. cpu1.`, time-slot violation counters sum 0 |

| Arm | Runs | Run checks | Differential verdict |
|---|---|---|---|
| OD8: full defense, 8/8 | `e3-od8-s{1,2}-n2000` | PASS, way isolation PASS | IDENTICAL |
| OD1: full defense, 1/15 | `e3-od1-s{1,2}-n2000` | PASS, way isolation PASS | IDENTICAL |

What this shows: with the full defense in the overlap schedule the monitor's probe logs
are byte-identical across seeds S1 and S2 at both monitor depths (no record differs in
latency or in timestamp), where the same runs without the interconnect defense (OW8 and
OW1 of block E2: same victim, build, split, depth and seeds) were `DIFFERENT`, and OW8
supported the key-dependent collision-count statement. The defense was on in all four
runs: the slot, response-queue and prefix settings were present, the three time-slot
violation counters (`tdmaOverruns`, `tdmaDownstreamRefusals`, `tdmaExpressBypasses`)
exist in the statistics (12 lines per run) and are all 0, and the proposal's isolation
metric is 0. Limits: the differential verdict covers the tested plaintext streams
only, and the byte-for-byte guard of the new gem5 binary was a stored window-schedule
run with the defense off, not an overlap-schedule run. The defended runs took 1,485 to
1,549 s each, against 738 to 774 s for the undefended overlap runs.

## Environment changes made for Phase A and B

With the group's approval, in WSL `Ubuntu-26.04`: `qemu-user` (provides
`qemu-riscv64`) and `python3-scipy` were installed with `apt-get`. A second git
worktree `.codex-tmp/aes-leakage-worktree` (gitignored directory) holds this
branch. For Phase B: a new gem5 worktree `~/eel5764/gem5-leak` (which adds
metadata under `~/eel5764/gem5/.git/worktrees/`), the symlink directory
`~/eel5764/leak-ext/`, the build log `~/eel5764/build_leak.log`, and the guard
output under `~/eel5764/guard-leak/`; none of the existing gem5 trees was
modified. Nothing outside this experiment directory was modified in the
repository; `preserve.py verify` checks that.

For Phase E block E3: a new gem5 worktree `~/eel5764/gem5-leak-def` (which adds
metadata under `~/eel5764/gem5/.git/worktrees/`) and the build log
`~/eel5764/build_leak_def.log`; none of the existing gem5 trees was modified.

## Open items

* **Effect-size rule (raised after P1, before any P3 data).** The frozen decision rule
  uses significance only. P1 shows a deterministic, noise-free baseline (sd 0.0 in
  untouched sets), and `standardize()` treats a zero-variance column as having sd 1
  (one cycle), so in a noise-free arm the z is effectively measured in cycles, while
  an arm with tiny nonzero jitter is standardized by that jitter. A deterministic
  residual of a cycle or less could then count as "supported" without being
  meaningful, and arms may not be comparable. The paper handled this with an
  equivalence margin of 0.02 cycles per line. Recommendation: before P3, log a
  deviation (D1) that adds a reported effect size (cycles per predicted line) and a
  materiality threshold to the decision rule. Not done: it changes the registered rule,
  so it needs the group's decision.
* **N for P2 to P4.** The sizing in the preregistration used synthetic noise (6
  cycles) and an assumed effect of 4 to 40 cycles. The real unpartitioned baseline has
  zero noise and a 2,642-cycle effect, so N = 4000 is probably more than the controls
  need. N for the partitioned and defended arms depends on a residual effect that is
  still unknown. The registered N = 4000 stands unless a deviation is logged.

* The tracing code's enabled behaviour is now verified at N = 20 (fills recorded,
  68 lines mapped, recall and precision 1.000 with scrub); P1 tests it at 2,000
  windows.
* P4 needs a gem5 tree with the time-slot and response-queue patches rebuilt with
  this `EXTRAS`, and `run_leakage.py` must pass the time-slot parameters through.
* The preregistration is a draft: N, seeds and gates await the group's edits and
  the freeze in section 10.
* Whether the final paper may include work beyond the accepted proposal has not
  been confirmed with the instructor.

## Deviations log

* **D0 (2026-11-12, before any analysis data; found by the P0 gate):** the victim's
  scrub walk was reduced from 8 KiB (the task text) to 4 KiB, because the 8 KiB walk
  made the A = 16 prime miss its deadline. `W`, `T0` and all offsets are as
  specified. Evidence and the single-variable test are in "Phase C: results".
* **D1 (2026-11-12, before any run of block E1; no partitioned, defended or overlap
  data exist): how partitioned arms and shallow-monitor arms are judged.** For every
  arm with `--split` other than `off`, and for every unpartitioned arm with fewer than
  16 monitor ways, the primary outcome is a differential test. The same arm is run
  with two or three of the public plaintext seeds, with the same binaries, schedule
  and build directory and with run-directory names of equal length, and the monitors'
  `probes.bin` files are compared (`analysis/leak_followup.py diff`). `IDENTICAL`
  (byte-identical files) is reported as: the monitor's observation did not depend on
  the encrypted data for these plaintext streams; no statistical statement is made.
  `LATENCY_IDENTICAL` (only timestamps differ) is reported as such and treated as
  `DIFFERENT` for the decision. `DIFFERENT` sends the arm to the analysis of D2.
  Reasons: gem5 is deterministic for this experiment (P0 attempt 2 and its repeat are
  byte-identical) and the P1 control is noise-free, so a p-value adds nothing where
  the log does not change at all; and the registered analysis could not run on a
  perfectly flat log (`np.nanargmax` on an all-NaN slice; fixed in this commit, test
  `tests/test_fixes.py`). The control-validity gate of section 4 no longer applies to
  these arms: in the paper's stored unpartitioned controls at monitor depth 1, 4 and 8
  the LLC replaced no block during measurement (9 of 9 runs: 0 replacements, 0 monitor
  misses), so an unpartitioned monitor with fewer than 16 ways is never evicted and
  cannot be a positive control for cache-state leakage. The positive control for the
  state channel is P2a (16 monitor ways). Limit: a differential test covers the tested
  plaintext streams only.
* **D2 (2026-11-12, before any run of block E1): effect size, permutation p-value and
  materiality.** The registered z statistic and Holm rule stay as registered and are
  reported for every arm. In addition, for every arm that is interpreted statistically
  (P2a, P2b, and any arm that D1 reports as `DIFFERENT`), `analysis/leak_followup.py
  effect` reports (a) the raw effect of each hypothesis in CPU cycles per set walk and
  per probed line (per set walk divided by the monitor depth), (b) a one-sided
  permutation p-value from 10,000 window shuffles with seed 5764, Holm over the same
  96 tests, alpha = 0.05, (c) the slow-versus-touched table over the 68 table-line
  sets, and (d) for arms other than P2a, the fraction of P2a's effect that is
  retained. A statement is reported as supported only if it is supported under the
  registered rule, its permutation p-value is below 0.05 after Holm, and its raw
  effect is at least 0.02 cycles per probed line (the paper's equivalence margin).
  Where the registered rule and this rule disagree, both results are reported and the
  disagreement is stated. Reasons: `standardize()` divides each set by its own standard
  deviation, so z is the same for a 2,642-cycle and a 1-cycle effect; on near-constant
  columns the normal approximation gave 29 false positives in 300 synthetic null runs
  (9.7%, nominal 5%). The last-round statements are secondary and are interpreted for
  P2a only.
* **D3 (2026-11-12, before any run of block E1): run matrix.** P2a and P2b use
  N = 2000 (the existing `build/n2000`) instead of 4000, seed S1. P3 becomes: victim
  `full-scrub`, N = 500 (`build/n500`); way-partitioned 8/8 and 1/15 with seeds S1, S2
  and S3; unpartitioned with 8 and with 1 monitor ways with seeds S1 and S2; all judged
  by D1. P4 in the window schedule and the optional run T are dropped. Reasons: on
  synthetic full-AES data built from the two latencies measured in P1 (513 and 3,155
  cycles, no noise) the registered rule reaches 16/16 bytes for round 1 from N = 250
  and for the last round from N = 1000; a differential test depends on N only through
  the number of plaintexts covered; P4 in the window schedule cannot differ from P3,
  because that schedule has no concurrent traffic for the two interconnect mechanisms
  to act on (section 8, item 1); T is a fixed-versus-random test, which the
  differential test subsumes in a deterministic simulator. Block E1 run directories:
  `e1-p2a-s1-n2000`, `e1-p2b-s1-n2000`, `e1-c8-s{1,2}-n500`, `e1-c1-s{1,2}-n500`,
  `e1-w8-s{1,2,3}-n500`, `e1-w1-s{1,2,3}-n500`.
* **D4 (2026-11-12, before any run of block E3): the full defense.** The full defense
  (way partition, request time slots, per-domain LLC response queues) is evaluated in
  the overlap schedule only (`PREREGISTRATION_OVERLAP.md`). It uses a gem5 binary
  built in a new tree, `~/eel5764/gem5-leak-def`: the paper's commit `c8222cc` plus
  the stored patch `experiments/respq-defense-20261018/gem5-respq.patch`, built with
  this experiment's `gem5_ext` as `EXTRAS`. The adapter `run_leakage_defense.py` sets
  `tdma_slot_cycles = 4` and `response_domain_prefixes = cpu0. cpu1.`, the values of
  the paper's defense sweep. Guard before any defended run: with the defense off, the
  new binary must reproduce `runs/p0b-r1-scrub-n20/probes.bin` byte for byte (run
  `p0d-r1-scrub-n20`). The existing gem5 trees are not modified.
