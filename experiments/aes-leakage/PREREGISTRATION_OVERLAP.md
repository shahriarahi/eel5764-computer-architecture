# Preregistration: does a contention channel carry data-dependent information?

**Status: registered at the commit that adds this file, before any run with the
overlap schedule exists.** Simulator only (gem5 v25.1.0.1, RISC-V SE mode); fixed
public test key; public plaintexts. This is a second, separate experiment next to
`PREREGISTRATION_DRAFT.md`, whose limitation 1 states that the window schedule
measures cache state and cannot see a contention channel. Changes after data exist
are logged in section 9.

## 1. Question and scope

The submitted paper found that way partitioning leaves a hit-timing channel through
the shared L1-to-LLC crossbar, and that request time slots plus per-domain LLC
response queues close it. This experiment asks whether that channel carries
information about the data being encrypted, and whether the full defense removes it.

It goes **beyond the accepted proposal**, as `PREREGISTRATION_DRAFT.md` does. The
analysis uses the known public key `f1e2d3c4b5a69788796a5b4c3d2e1f10`. It **does not
score key guesses**: it compares fixed, key-known models and nothing ranks, guesses or
recovers key bytes.

## 2. Schedule

The window of `leak_schedule.h` with one change, made by compile flags only
(`EXTRA_DEFS="-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL"`; no source file
changes): the monitor's probe pass starts at `OFF_PROBE` = 520,192 =
`OFF_ENC` - 4,096, so the encryption at 524,288 runs while the monitor is walking its
lines. `T0`, `W`, `OFF_PRIME`, `OFF_ENC` and the 4 KiB scrub (D0) are unchanged. Only
monitor depths 8 and 1 are used: their probe passes take about 70,900 and 12,600
cycles in the paper's stored runs, so the pass ends before the window does and covers
the encryption. A 16-way monitor is not used: in an unpartitioned LLC it would be
evicted by the victim, which mixes cache state with contention.

## 3. Leakage model

A contention channel shows that the victim sent a request to the LLC, and when; it
does not show which address was requested. With the scrub, the victim sends one LLC
request for the first use of each table line in an encryption (later uses hit its
L1D). The data-dependent quantity is therefore the **number of distinct table lines**
an encryption uses (a collision count), not the position of a line. The registered
location-aware statistic of `PREREGISTRATION_DRAFT.md` cannot detect this model
(`tests/test_leak_followup.py`,
`test_the_registered_location_aware_rule_misses_this_channel`).

## 4. Arms

Victim `r1-scrub` (round-1 lookups only) is the registered victim, because in a full
encryption round 1 supplies only about a quarter of the distinct lines. Seeds S1 =
1466213861 and S2 = 1466213862. N = 2000 (`build/ovl-n2000`).

| Arm | `--split` | monitor ways | defense | run directories |
|---|---|---|---|---|
| pilot | off | 8 | none | `e2-pilot-c8-s1-n200` (N = 200, `build/ovl-n200`) |
| OC8 | off | 8 | none | `e2-oc8-s1-n2000`, `e2-oc8-s2-n2000` |
| OC1 | off | 1 | none | `e2-oc1-s1-n2000`, `e2-oc1-s2-n2000` |
| OW8 | 8-8 | 8 | way partition | `e2-ow8-s1-n2000`, `e2-ow8-s2-n2000` |
| OW1 | 1-15 | 1 | way partition | `e2-ow1-s1-n2000`, `e2-ow1-s2-n2000` |
| OD8 | 8-8 | 8 | full defense (D4) | `e3-od8-s1-n2000`, `e3-od8-s2-n2000` |
| OD1 | 1-15 | 1 | full defense (D4) | `e3-od1-s1-n2000`, `e3-od1-s2-n2000` |
| FW8, FW1 (exploratory) | 8-8, 1-15 | 8, 1 | way partition, victim `full-scrub` | `e2-fw8-s{1,2}-n2000`, `e2-fw1-s{1,2}-n2000` |

## 5. Analysis and decision rule

1. **Differential test** per arm (`leak_followup.py diff`, the two seeds).
   `IDENTICAL`: the monitor's observation did not depend on the encrypted data for
   these plaintext streams; the arm is finished. Anything else continues.
2. **Collision-count test** per run (`leak_followup.py count`): Pearson r between a
   per-window model count and a per-window monitor feature, two-sided permutation
   p-value from 10,000 window shuffles with seed 5764, Holm over the 8 tests of one
   run, alpha = 0.05. Features: `excess_cycles` (sum over the 256 walks of latency
   minus that set's median latency) and `delayed_walks` (number of walks above their
   set's median). Models: `lines_all_rounds` (distinct table lines the encryption
   uses), `lines_round1_p_xor_k` (distinct round-1 lines under the key-dependent
   model), `lines_round1_p_only` (the same without the key), `shuffled`.
3. **Statements**, per run: `count_dependent` (the `lines_all_rounds` model is
   significant on a feature and its |r| exceeds the shuffled control's);
   `round1_count_plaintext_plus_key` (the key-dependent round-1 model is significant,
   beats the shuffled control and has the larger |r| of the two round-1 models);
   `round1_count_plaintext_only` (the reverse). An arm supports a statement only if
   both of its runs do.
4. The registered location-aware analysis (`aes_leak_analysis.py analyze`) is run on
   every run for its run checks (self-test, checksums, monitor status, way isolation)
   and its attribution table is reported.
5. **Reading.** OW arms `DIFFERENT` and `round1_count_plaintext_plus_key` supported:
   under way partitioning alone the crossbar channel carries a key-dependent collision
   count. OW arms `DIFFERENT` and no statement supported: the monitor's log depends on
   the plaintext stream, but not through the collision count at this N. OD arms
   `IDENTICAL`: with the full defense the monitor's observation is independent of the
   data for these streams, in a schedule where the undefended channel is open.

## 6. Gates

* **Pilot.** `e2-pilot-c8-s1-n200` must finish with `monitor status=PASS`, no
  `error=` line, and `RUN CHECKS: PASS`. If its `count` output shows `excess_cycles`
  with maximum 0 (no walk is ever delayed), the overlap schedule did not recreate the
  paper's channel: stop, report, and do not run the other arms.
* **Run checks** for every run as in `PREREGISTRATION_DRAFT.md`, section 4; a
  partitioned run must pass `way_isolation`.
* **Defense guard** (D4) before any OD run.
* **Interpretability.** OW and OD results are interpreted only if the two OC8 runs
  (or the two OC1 runs for depth 1) are `DIFFERENT`, that is, only if the undefended
  channel is visible at that depth in this schedule.

## 7. Power (not measured)

The size of the effect is unknown until the pilot runs. In synthetic data in which
each first use of a table line delays one walk by 4 cycles with probability 0.3, the
count test supports `round1_count_plaintext_plus_key` at N = 2000
(`tests/test_leak_followup.py`). The paper measured that 9.4% of walks were delayed
at 1/15 under continuous AES traffic; one round-1 pass sends about 14.6 requests per
window. "Not supported" is absence of detection at this N, not proof of absence; the
differential test is the stronger statement in both directions.

## 8. Limitations

1. One key, one workload, one cache configuration, a deterministic simulator; the
   seeds are repeated public inputs, not independent replicates.
2. A differential test covers the tested plaintext streams only.
3. The schedule places one encryption inside one probe pass; continuous traffic, as
   in the paper, is not measured here.
4. The FW arms use a full encryption, for which the round-1 statements are
   low-power; they are exploratory and only `count_dependent` is read from them.
5. Simulated, not hardware: every statement concerns this simulated configuration.

## 9. Deviations

None yet.
