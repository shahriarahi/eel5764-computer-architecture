* **D1 (DATE_LOGGED, before any run of block E1; no partitioned, defended or overlap
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
* **D2 (DATE_LOGGED, before any run of block E1): effect size, permutation p-value and
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
* **D3 (DATE_LOGGED, before any run of block E1): run matrix.** P2a and P2b use
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
* **D4 (DATE_LOGGED, before any run of block E3): the full defense.** The full defense
  (way partition, request time slots, per-domain LLC response queues) is evaluated in
  the overlap schedule only (`PREREGISTRATION_OVERLAP.md`). It uses a gem5 binary
  built in a new tree, `~/eel5764/gem5-leak-def`: the paper's commit `c8222cc` plus
  the stored patch `experiments/respq-defense-20261018/gem5-respq.patch`, built with
  this experiment's `gem5_ext` as `EXTRAS`. The adapter `run_leakage_defense.py` sets
  `tdma_slot_cycles = 4` and `response_domain_prefixes = cpu0. cpu1.`, the values of
  the paper's defense sweep. Guard before any defended run: with the defense off, the
  new binary must reproduce `runs/p0b-r1-scrub-n20/probes.bin` byte for byte (run
  `p0d-r1-scrub-n20`). The existing gem5 trees are not modified.
