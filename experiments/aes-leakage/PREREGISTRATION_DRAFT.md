# Preregistration (DRAFT): what does the LLC channel encode, and do the defenses remove it?

**Status: DRAFT. Not frozen. No gem5 data from this experiment exist.** Before the
first P1 run the group reads this file, changes what it wants, and then freezes it
(section 10). Anything changed after data exist is logged as a deviation in
section 11. Simulator only; public key; public inputs.

## 1. Question and scope

The submitted paper measured whether AES activity is visible. This study asks what
the visible signal encodes: nothing data-dependent, plaintext only, or plaintext
combined with the key; and whether way partitioning, request time slots and
per-domain response queues remove data-dependent leakage or only the activity
signal.

This goes **beyond the accepted proposal**, whose bounded objective is "activity
detection and performance only" and which "does not recover or guess key bytes".
The final paper should list it under changes from the proposal. To stay as close to
that bound as the question allows, the analysis **does not score key guesses**: it
uses the known public key and compares fixed hypotheses (section 5). The key is
`f1e2d3c4b5a69788796a5b4c3d2e1f10`; every upper nibble is nonzero, so `(p ^ k) >> 4`
differs from `p >> 4` at all 16 bytes (the paper's key `000102...0f` cannot tell
them apart).

## 2. Design

* **Unit of observation: one window** (prime, one encryption, probe), labelled with
  that window's public plaintext. Schedule in `leak_schedule.h`: `T0` = 2,000,000
  cycles, `W` = 1,048,576, prime at `+65,536`, encryption at `+524,288` with a
  65,536-cycle budget, probe at `+593,920`.
* **Plaintexts:** splitmix64 from the workload seed; window `j` uses two draws
  (low word, high word), little-endian. The paper's 64-bit LCG repeats its low byte
  every 256 encryptions, which would tie plaintext byte 0 to the window index.
* **Seeds:** S1 = 0x5764A5E5 = 1466213861, S2 = 0x5764A5E6 = 1466213862,
  S3 = 0x5764A5E7 = 1466213863 (the paper's three public seeds). As in the paper,
  the three seeds are repeated deterministic inputs, not independent replicates.
* **Platform:** the paper's: gem5 v25.1.0.1 (commit c8222cc6), two
  `TimingSimpleCPU` at 2 GHz, 4 KiB 4-way L1D, 256 KiB 16-way LLC (LRU), L2 crossbar.
* **Scrub:** the variants with scrub walk a private 4 KiB buffer (64 lines, the size
  of the 4-way L1D) before each encryption so the table lookups reach the LLC; see D0.
  Without the scrub (`full-noscrub`) the N = 20 smoke run showed only about 29% of the
  table lines the AES touches reaching the LLC (recall 0.291, precision 1.000).
* **Monitor:** the paper's v3 measurement safeguards (probe chains walked from
  registers, results stored in the spare bytes of the just-walked line, one `writev`
  per window, no new LLC line allocated while measuring).

## 3. Runs

`--victim-variant`, `--split` and `--monitor-ways` are the arguments of
`run_leakage.py` (commands in `README.md` and `gem5_build.md`). Each partitioned run
(`-t`) is paired with an unpartitioned control (`-c`) of the same monitor depth,
seed, binary and schedule; the only intended difference is whether the way masks are
enabled, as in the paper.

| ID | Purpose | `--victim-variant` | `--split` | `--monitor-ways` | N | Seeds |
|---|---|---|---|---|---|---|
| P0 | smoke test | r1-scrub | off | 16 | 20 | S1 |
| P1 | positive control | r1-scrub | off | 16 | 2000 | S1 |
| P2a | full AES, with scrub | full-scrub | off | 16 | 4000 | S1 |
| P2b | full AES, no scrub | full-noscrub | off | 16 | 4000 | S1 |
| P3a-c | control for 8/8 | full-scrub | off | 8 | 4000 | S1, S2, S3 |
| P3a-t | way partitioned 8/8 | full-scrub | 8-8 | 8 | 4000 | S1, S2, S3 |
| P3b-c | control for 1/15 | full-scrub | off | 1 | 4000 | S1, S2, S3 |
| P3b-t | way partitioned 1/15 | full-scrub | 1-15 | 1 | 4000 | S1, S2, S3 |
| P4a-t | full defense at 8/8 | full-scrub | 8-8 | 8 | 4000 | S1, S2, S3 |
| P4b-t | full defense at 1/15 | full-scrub | 1-15 | 1 | 4000 | S1, S2, S3 |
| T | optional fixed-vs-random (TVLA) cross-check | tvla | off | 16 | 2000 | S1 |

P4 is the way partition plus request time slots plus per-domain response queues;
its controls are P3a-c and P3b-c. **P4 needs work not done in Phase A:** a gem5
tree with the time-slot and response-queue patches (like `~/eel5764/gem5-respq`)
rebuilt with this experiment's `EXTRAS`, and `run_leakage.py` must pass the
time-slot parameters through (the existing `experiments/tdma` adapter shows how).
That change will be made in Phase E and logged in section 11.

## 4. Gates (stop and debug if one fails)

* **G0 (P0):** `analyze` ends with `RUN CHECKS: PASS`; no `error=` line in
  `simout.txt` (a missed deadline exits with status 2); all 68 table lines are
  mapped to distinct logical sets; `victimTableSetMismatches` = 0; table fills in
  the trace fall inside the AES phase.
* **G1 (P1):** `p_xor_k` significant on 16/16 bytes, `p_only` on 0/16, `shuffled`
  on 0/16 (Holm, alpha = 0.05). Otherwise stop.
* **Control validity (P3, P4):** a treatment is interpreted only if its matched
  control supports `round1_plaintext_plus_key` (section 5). If the control does not,
  the pair is reported as uninterpretable, not as "defended".
* **Isolation (partitioned runs):** the `way_isolation` run check passes (zero valid
  LLC blocks outside the assigned ways, the proposal's isolation metric). A
  violation invalidates that run.
* **Self-test and checksums:** the FIPS-197 line and the victim's plaintext and
  ciphertext checksums match the Python reference (`config_matches_simout`,
  `checksum_matches`).

## 5. Hypotheses, test statistic and decision rule

Per byte `i` and window, each hypothesis predicts which table line the encryption
touches; the statistic is, averaged over the table's lines, the mean latency of the
monitor set holding that line when it is predicted minus when it is not, with a
one-sided z (normal approximation, lines treated as independent; checked by window
shuffling with `--nperm`). Round 1 uses the 16-line `Te_(i%4)` tables, the last
round the 4-line sbox (`x >> 6`).

| Hypothesis | Predicted line | Role |
|---|---|---|
| `p_xor_k` | `(p_i ^ k_i) >> 4` in `Te_(i%4)` | round 1, key-dependent |
| `p_only` | `p_i >> 4` in `Te_(i%4)` | round 1, no key |
| `shuffled` | `p_xor_k` with the windows permuted | round 1 null control |
| `lr_c_xor_k10` | `InvS[c_i ^ k10_i] >> 6` in the sbox | last round, key-dependent |
| `c_only` | `c_i >> 6` in the sbox | last round, no key |
| `lr_shuffled` | `lr_c_xor_k10` with the windows permuted | last round null control |

* **Family and error rate:** alpha = 0.05 with Holm over the 96 tests (6
  hypotheses x 16 bytes) of one run.
* **Decision rule (key-guess free):** a data hypothesis is **supported** if it is
  significant on at least one byte **and beats** its key-free alternative and its
  shuffled control (higher z) on those bytes. The four statements are
  `round1_plaintext_plus_key`, `round1_plaintext_only`, `lastround_c_xor_k10` and
  `lastround_ciphertext_only`.
* **Reading:** `round1_plaintext_plus_key` supported and `round1_plaintext_only` not:
  the channel carries plaintext combined with the key. The reverse: plaintext
  only. Neither: no round-1 data dependence detected at this N.
* **Matched pairs:** for each treatment, report which statements hold, the per-byte
  labels (`plaintext_plus_key`, `plaintext_only`, `ambiguous`, `none`), and the
  fraction of the control's mean score the treatment retains. "Not supported" is
  absence of detection at this N, not proof of absence; section 7 gives power.
* **Location-free detection** (ANOVA over byte-value classes) is reported but not
  part of the rule: it cannot separate `p` from `p ^ k`.

## 6. Sample size and cost

* P1: N = 2000. P2 and P3/P4: N = 4000. The choice rests on the synthetic power
  table below; the real effect size is unknown until P1 and P2 run.
* **Cost (estimates, not measurements of this experiment):** a window is 1,048,576
  cycles. At the roughly 3 million simulated cycles per second measured for earlier
  runs on this host, N = 2000 takes about 12 minutes and N = 4000 about 23 minutes
  per run. P2 to P4 is 20 runs: about 7.8 hours sequentially; several can run in
  parallel, as the earlier sweeps did.
* **Data size (calculated):** `probes.bin` is N x 256 x 16 bytes: 8.2 MB at
  N = 2000, 16.4 MB at N = 4000.

## 7. Synthetic power (not gem5)

`synthetic_power.md` is produced by `analysis/power_synth.py` from the synthetic
generator in `analysis/aes_leak_analysis.py`. It assumes every touched line is
visible with latency rise `delta` and Gaussian noise (6 cycles). It sizes N and
checks the rule; it says nothing about the real effect.

* On data with **no** data dependence (every lookup index random, N = 1000, 400
  runs): the decision rule fired in 15 runs (3.75%) and any of the six hypotheses was
  significant on some byte in 21 runs (5.25%), consistent with the nominal 5%.
* Round-1 attribution on full AES: with `delta` = 10 it is supported in every run
  from N = 250 (15.2 of 16 bytes significant at N = 1000); with `delta` = 4 it is
  supported in 6 of 6 runs from N = 2000 (6.0 bytes at 2000, 13.8 at 4000).
* **Last round (sbox, 4 lines):** much weaker. With `delta` = 40 it is supported
  in every run from N = 1000; with `delta` = 10 in at most 1 of 6 runs even at
  N = 4000. A failure to support the last-round statements at modest effect sizes
  is a power limit, not evidence that a defense works.

## 8. Limitations (stated before any data)

1. **State, not contention.** The encryption ends at least 4,096 cycles before the
   probe starts and the monitor accesses no memory in between, so no victim memory
   traffic overlaps a monitor access. These windows measure cache-state leakage.
   The paper's crossbar timing channel needs concurrent traffic and cannot appear
   here. Way partitioning removes cache-state interference by construction, so a
   null result under partitioning must not be read as removing the crossbar
   channel's data dependence. An overlap variant (encrypt during the probe) is **not**
   part of this registration; the offsets can be overridden with `-D` (see
   `leak_schedule.h`) if the group later wants one.
2. **The trace records LLC allocations only** (gem5 calls the partition manager at
   allocation). Partitioned runs keep the tables resident in the AES ways, so
   little or nothing is expected in their trace; low recall there is not an error.
3. The analysis SNR is a variance ratio, not the proposal's
   `|mean difference| / pooled SD`.
4. One key, one workload, one cache configuration; the seeds are repeated inputs of
   a deterministic simulator.
5. Run-to-run byte identity depends on path lengths (the paper's gotcha); only the
   Phase B guard depends on it.

## 9. What would change the plan

* P0 or P1 fails a gate: stop, diagnose, and log it.
* **(Happened in P0, see D0.)** The deadline margins were exceeded in P0: I had
  assumed an A = 16 pass takes about 280,000 cycles (the paper's figure for a pass of
  hits), leaving about 179,000 and 174,000 cycles of slack. With an 8 KiB scrub the
  prime took about 476,000 cycles against a 458,752 budget. The remedy was to shorten
  the victim's scrub, logged as D0. Measured with the 4 KiB scrub at A = 16: the
  prime takes between about 335,000 and 393,000 cycles (budget 458,752) and the
  probe pass about 183,000 to 341,000 (budget 454,656), depending on the variant.
  Any later run whose monitor misses a deadline stops with an error; the cold
  window 0 is the worst case for the prime.

## 10. Freezing procedure

1. The group edits this file.
2. `python preserve.py capture`, commit, and record the commit hash here.
3. Run P1.

**Frozen at commit `675c047` (2026-11-12), before the first P1 run.** The content of
this file as of that commit is the registered design. The freeze was made when the
group told me to proceed with Phase D ("From now on, I give you approval"), without
edits from the group, so the draft's values (N = 2000 for P1 and 4000 for P2 to P4,
the seeds, the gates, the decision rule) stand as written. This paragraph is the only
later edit. Changes after this point are logged in section 11.

## 11. Deviations

* **D0 (2026-11-12, before any analysis data; found by gate G0 in the P0 smoke
  run):** the victim's scrub walk is 4 KiB (64 lines, the size of the L1D) instead of
  the 8 KiB in the task text. The 8 KiB walk allocates 128 LLC lines per window in an
  unpartitioned LLC full of the monitor's lines; the monitor's next prime then
  cascades through the affected sets and took about 476,000 cycles against its
  458,752-cycle budget, so the monitor exited with `prime_deadline`. A single-variable
  comparison (scrub on or off) isolated the cause, and the 4 KiB walk still flushes the
  L1D (recall and precision 1.000 in the smoke runs). `W`, `T0` and all offsets are
  unchanged. Evidence: `progress.md`, "Phase C: results".
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
