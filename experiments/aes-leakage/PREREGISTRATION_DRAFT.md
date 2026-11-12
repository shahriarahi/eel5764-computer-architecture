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
* The deadline margins (prime and probe at A = 16 take about 280,000 cycles each in
  the paper's results; the schedule leaves about 179,000 and 174,000 cycles of
  slack) are exceeded in P0: shorten the monitor pass or lengthen the window before
  any data are taken, and log it.

## 10. Freezing procedure

1. The group edits this file.
2. `python preserve.py capture`, commit, and record the commit hash here.
3. Run P1.

Frozen at commit: (not yet).

## 11. Deviations

None yet.
