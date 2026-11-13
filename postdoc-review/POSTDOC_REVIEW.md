# Review of the AES leakage-attribution follow-up (Group 18, EEL 5764)

Reviewed 2026-11-12 against `DISCUSSION_BRIEF.md` at worktree head `434b16b`, the
accepted proposal and the submitted v2 paper. Simulator-only study; nothing here
proposes hardware work. No gem5 simulation was run for this review.

**Evidence labels.** *Files* are cited as `file:line`, relative to
`.codex-tmp/aes-leakage-worktree/experiments/aes-leakage/` unless a longer path is
given. *gem5* means the v25.1.0.1 source under `~/eel5764/gem5/src/`. *Literature*
entries are in section 8. *Vnn* is a check in `postdoc-review/verify/`, re-runnable
from its `README.md`. Tags: **[run-verified]** (I executed a check; its script and
output are saved), **[source-verified]** (checked in code, gem5 source or a paper I
opened), **[unverified]** (with the pilot that would settle it).

## 1. Verdict

The instrument is sound and well tested, and P1 is a clean positive control. Phase E
as registered is not sound: most of it cannot produce an interpretable result, and
the part that matters to the paper's own finding is not in it. Make three changes
before any Phase E run.

1. **Judge partitioned and defended arms by a differential test** (same arm, different
   plaintext seeds, compare probe logs byte for byte), not by z-scores. The registered
   matched controls cannot leak, and the registered analysis crashes on a flat log.
2. **Add raw-cycle effect sizes with a permutation p-value and a 0.02-cycle margin**
   wherever statistics are still used. The registered z cannot tell a 2,642-cycle
   effect from a 0.007-cycle one.
3. **Replace the window-schedule P4 with one small, separately preregistered overlap
   experiment** that uses a collision-count model, and cite the frozen paper data,
   which already answer the full-defense question.

## 2. Decision table

"Added simulation hours" are relative to the registered Phase E (20 runs at
N = 4000, 22.0 min each by V01: 7.3 h).

| Q | Recommendation | Tag | Proposal impact | Added sim. hours |
|---|---|---|---|---|
| 1 | State-only is not enough; keep the window schedule for the state channel, add one overlap experiment with a collision-count model, and cite the frozen cross-seed identity for the full defense | [run-verified] for the facts; [unverified] that the overlap arm shows a signal | additive | +1.5 (+0.7 exploratory) |
| 2 | Differential test first; raw-cycle effect size with a 0.02 cycles-per-probed-line margin where logs differ | [run-verified] | additive | 0 |
| 3 | Keep z as registered but decide on a 10,000-shuffle permutation p-value (seed 5764) of the raw-cycle statistic, plus the exact slow-versus-touched table | [run-verified] | additive | 0 |
| 4 | N = 2000 for the two unprotected full-AES runs, N = 500 for differential arms | [run-verified] | none | -6.5 |
| 5 | Accept D0 (4 KiB scrub) | [run-verified] | none | 0 |
| 6 | Present it as a labelled extension; ask the instructor this week; keep the proposal's sections unchanged | [source-verified] | additive | 0 |
| 7 | No conflict; build one new tree from the stored defense patch plus the tracing `EXTRAS`, guard it byte for byte, and run the full defense in the overlap schedule only | [run-verified] for the patch; [unverified] for the build | additive | +0.7 |
| 8 | Keep the last round as a secondary result for P2a only; headline is round 1 | [run-verified] | none | 0 |
| 9 | Run block E1 first (50 min of simulation); cut in the order given in section 6 | [run-verified] for the times | none | 0 |

Net: about 3.1 h of simulation (3.8 h with the exploratory arms) instead of 7.3 h.

## 3. The nine questions

### Q1. Does the window design answer the right question for the defenses?

**Recommendation.** No. Keep the window schedule for what it measures (cache state),
judge it by a differential test, and add one separately preregistered overlap
experiment for the contention channel, analysed with a location-free collision-count
model. Do not run P4 in the window schedule at all.

**Why.**
*Files.* The monitor touches no memory between its prime and its probe
(`monitor_leak.c:161-182`), and the probe starts 4,096 cycles after the encryption
budget ends (`leak_schedule.h:27-35`). Nothing the victim sends can overlap a monitor
access, so the two interconnect mechanisms have nothing to act on: a window-schedule
P4 must equal P3.
*Existing data.* V06 compared the frozen paper probe logs across the three plaintext
seeds. Under the full defense they are byte-identical at 8 of 8 allocations; under way
partitioning alone they differ at 8 of 8 (1,425 to 5,860 of 16,384 latency records).
That is a differential result with about 24,000 encryptions per run and concurrent
traffic. It already shows that, with the full defense, the monitor's observation did
not depend on the plaintext stream for those seeds, and that with way partitioning
alone it did. What it does not show is *what* crosses under partitioning alone. That
is the open question, and only an overlap schedule can ask it.
*Literature.* Ge et al. (Time Protection, section 2.2 to 2.3) separate
capacity-limited resources, which an OS can protect by flushing or partitioning, from
bandwidth-limited interconnects, for which protection "would require time-multiplexing
the interconnect". That is the paper's time-slot mechanism. Paccagnella et al. built
the first on-chip cross-core side channel that works despite LLC partitioning and
stress that the channel "only sees contention due to spatially coarse-grained events
such as private cache misses". Kiriansky et al. scope DAWG's guarantee to the "cache
state" channel. So partitioning is a state defense by design, and a contention monitor
sees *that* and *when* the victim missed its private cache, not *which line* it
fetched.
*gem5.* The shared resource is one request `Layer` per destination port. A request
from either core calls `reqLayers[...]->tryTiming()` (`mem/coherent_xbar.cc:166-171`),
and the layer then stays busy until `clockEdge(headerLatency) + pkt->payloadDelay`
(`mem/coherent_xbar.cc:191`, `:352`; `BaseXBar::Layer::occupyLayer`, `mem/xbar.cc:164-181`).
That time depends on the packet's size, not on its address, so what the channel can
carry is occupancy and timing.
*Leakage model.* With the scrub, the victim sends one LLC request for the first use of
each table line in an encryption. The data-dependent quantity a contention monitor can
see is the number of distinct lines used: a collision count, the quantity Bonneau and
Mironov exploit through encryption time, as opposed to the access-pattern leakage of
Osvik, Shamir and Tromer that the registered hypotheses model. For round 1 the count
under `p XOR k` and under `p` alone are nearly uncorrelated (r = -0.07, V13), so a
key-dependent and a key-free model remain distinguishable without scoring any guess.
*Can the current statistic see it?* No. In V13 (a model, not gem5) a count-dependent
delay gives 0/16 bytes under the registered rule and 0 to 1 of 16 under the
location-free ANOVA, while a count statistic detects it with permutation p = 1/10001.
*Timing.* The overlap needs `OFF_PROBE` = 520,192 and nothing else; for monitor depths
8 and 1 the pass (70,906 and 12,574 cycles in the stored runs) covers the encryption
and ends well inside the window (V01). It builds from `-D` flags alone and changes
only `monitor_leak` (V09). A 16-way monitor cannot be used: its pass takes 170,000 to
341,000 cycles and the victim evicts it.

**How verified.** V05, V06, V09, V01 **[run-verified]**; V13 is analysis. That the
overlap arm shows any delay is **[unverified]**: pilot `e2-pilot-c8-s1-n200`
(`r1-scrub`, unpartitioned, 8 ways, overlap build, N = 200, 1.1 min); expected
`monitor status=PASS` and a nonzero `excess_cycles` maximum.

**What would prove it wrong.** A way-partitioned window-schedule arm that is
`DIFFERENT` across seeds (then state leakage survives partitioning and the window
design has more to say), or a pilot with no delayed walk at all (then this overlap
schedule does not recreate the paper's channel).

**Preregistration action.** Create `PREREGISTRATION_OVERLAP.md` from
`postdoc-review/reference/docs/PREREGISTRATION_OVERLAP.md` and commit it before any
overlap run (draft 2026-11-12). Its decision rule: "Differential test per arm.
`IDENTICAL`: the monitor's observation did not depend on the encrypted data for these
plaintext streams; the arm is finished. Otherwise the collision-count test: Pearson r
between a per-window model count and a per-window monitor feature, two-sided
permutation p from 10,000 shuffles, seed 5764, Holm over 8 tests, alpha 0.05. An arm
supports a statement only if both of its runs do."

**Proposal compatibility.** Additive; known-key, fixed models, no guess is scored;
the proposal's runs and metrics are untouched.

### Q2. Effect-size rule or differential test?

**Recommendation.** The differential test is the primary decision for every
partitioned, defended or shallow-monitor arm. Where logs differ, report the raw effect
in cycles per probed line and require at least 0.02 for "supported".

**Why.** *Files.* `standardize()` divides each set by its own standard deviation and
substitutes 1 when it is zero (`analysis/aes_leak_analysis.py:240-243`); the decision
uses significance and rank only (`:644-664`). V03 shows the consequence: z is 84.92
for a 2,642-cycle, a 10-cycle and a 1-cycle effect, and an effect of 0.0074 cycles is
"supported" on 16/16 bytes. The same 0.82-cycle effect gives z of 85, 59 or 15
depending on unrelated background jitter, so arms are not comparable. Worse for the
plan: on a perfectly flat log the analysis raises `ValueError` at `:264` (V11), and a
flat log is the expected outcome of a working defense.
*Why differential.* The simulator is deterministic: `runs/p0b-r1-scrub-n20` and its
repeat `runs/p0c-r1-scrub-n20` have byte-identical probe logs (V10), as did the
Phase B guard (`progress.md:105`). In a
deterministic system, identical logs for different inputs is the definition of
non-interference for those inputs; the paper already used this argument for the idle
victim (Section IX.D). Goodwill et al. frame leakage assessment as detecting whether
"sensitive intermediates" influence the measurement at all, without key extraction; a
differential test is that idea with the noise removed.
*Why a margin too.* Lakens: a non-significant test is "not evidence of absence", and
equivalence needs a stated smallest effect of interest. The paper's own margin is
0.02 cycles per probed line; reusing it keeps the two studies comparable. P1's effect
is 136.05 cycles per probed line (V10), about 6,800 times the margin.

**How verified.** V03, V10, V11 **[run-verified]**. The reference tool refuses
mismatched arms, unequal path lengths and equal seeds (`reference/tests/`, 6 tests).

**What would prove it wrong.** Two runs of one arm with the *same* seed that differ.
Then gem5 is not deterministic for that arm and identity proves nothing. The plan
re-checks this on the defense binary (`p0d` against `p0b`).

**Preregistration action.** Log D1 and D2 from
`postdoc-review/reference/docs/DEVIATIONS_D1_D4.md` before block E1 (draft
2026-11-12; must be committed before the affected arms run). D1 in one sentence: "For
every arm with `--split` other than `off`, and for every unpartitioned arm with fewer
than 16 monitor ways, the primary outcome is a differential test … `IDENTICAL` is
reported as: the monitor's observation did not depend on the encrypted data for these
plaintext streams; no statistical statement is made." D2's rule: "A statement is
reported as supported only if it is supported under the registered rule, its
permutation p-value is below 0.05 after Holm, and its raw effect is at least 0.02
cycles per probed line."

**Limit to state in the paper.** A differential test covers the tested streams only
(two or three seeds of 500 to 2,000 plaintexts each).

**Proposal compatibility.** Additive; the proposal's SNR and 10,000-permutation null
are reported unchanged for the proposal's runs.

### Q3. Is the statistic overkill, or wrong?

**Recommendation.** Both, in different arms. Keep the registered z in the output, but
take the inferential p-value from a permutation test of the raw-cycle statistic
(10,000 window shuffles, seed 5764, Holm over the same 96 tests), and for the
unprotected arms lead with the exact slow-versus-touched table.

**Why.** *Overkill in the control.* In P1 "set is slow" equals "line touched" in
136,000 of 136,000 cells; untouched sets take exactly 513 cycles (V02). A p-value
below double precision says less than that table. *Wrong near determinism.* The normal
approximation assumes many roughly Gaussian contributions; with columns that are
constant except for rare events it gave 29 false positives in 300 null runs (9.7%;
any hypothesis significant in 15.7%; V03). On P1 itself the analytic z is too
conservative (shuffled sd 0.72, `progress.md:235-237`), so it is miscalibrated in both
directions. A permutation test needs no distributional assumption and matches the
proposal's own 10,000-permutation, seed-5764 convention. Its smallest p-value,
1/10001, survives Holm over 96 tests (0.0096 < 0.05); the tool refuses a smaller
shuffle count (V10).

**Rejected alternative.** A mutual-information estimate: with an exact indicator it
equals the entropy of the line index, and elsewhere it needs a bias correction that
would have to be preregistered and defended. Doychev et al. show the right tool for
bounding information in a deterministic cache model is static analysis, not an
estimator.

**How verified.** V02, V03, V10 **[run-verified]**: on P1 the permutation rule gives
`p_xor_k` 16/16, `p_only` 0/16, `shuffled` 0/16, the same decision as the registered
rule.

**What would prove it wrong.** P2a deciding differently under the permutation rule
and the registered rule. D2 requires reporting both if that happens.

**Preregistration action.** Part of D2 (draft 2026-11-12, before block E1): "…(b) a
one-sided permutation p-value from 10,000 window shuffles with seed 5764, Holm over
the same 96 tests, alpha = 0.05, (c) the slow-versus-touched table over the 68
table-line sets…".

**Proposal compatibility.** Additive.

### Q4. Sample size

**Recommendation.** N = 2000 for P2a and P2b, using the existing `build/n2000`;
N = 500 for every differential arm.

**Why.** The synthetic sizing assumed 6 cycles of noise; the real channel has none.
V02: the P1 gate already passes at N = 25 and z grows as the square root of N, so N
buys nothing for a control. V04: a full encryption touches 57.7 of 64 Te lines, which
cuts the round-1 contrast from 2,177 to about 272 cycles and the last-round contrast
to about 33, but with zero noise the registered rule still reaches 16/16 for round 1
from N = 250 and for the last round from N = 1000 (0/16 at N = 500) on all three
seeds. N = 2000 keeps a factor of two for the last round and needs no new build. A
differential test does not gain power with N; N = 500 is chosen for plaintext
coverage and costs 2.8 min per run.

**Rejected alternative.** One N = 4000 everywhere "for matched comparisons": matching
N matters for a noisy z, not for an exact comparison, and it costs 6.5 h.

**How verified.** V01, V02, V04 **[run-verified]** (V04's forecast assumes every
touched line stays visible in full-AES mode; the 20-window smoke run supports it:
1,243 touched-and-slow, 0 errors).

**What would prove it wrong.** P2a at N = 2000 with `p_xor_k` on fewer than 16 bytes,
or a `probe_deadline` error: the full-AES probe pass has only 1.16x worst-case
headroom (V01). Either stops the block.

**Preregistration action.** D3 (draft 2026-11-12, before block E1): "P2a and P2b use
N = 2000 (the existing `build/n2000`) instead of 4000, seed S1. P3 becomes: victim
`full-scrub`, N = 500 (`build/n500`); way-partitioned 8/8 and 1/15 with seeds S1, S2
and S3; unpartitioned with 8 and with 1 monitor ways with seeds S1 and S2; all judged
by D1. P4 in the window schedule and the optional run T are dropped."

**Proposal compatibility.** None; only the extension's own N changes.

### Q5. Is D0 (4 KiB scrub) acceptable?

**Recommendation.** Yes. Keep it.

**Why.** The L1D in the run's own `config.ini` is 4 KiB, 4-way, `LRURP`
(`runs/p1-r1-scrub-n2000/config.ini`, section `system.cpu1.dcache`), so 64 consecutive
lines put 4 lines in each of the 16 sets and displace everything under true LRU. The
evidence is direct: trace recall and precision are 1.000 over 29,095 touched lines in
2,000 windows (`runs/p1-r1-scrub-n2000.analysis.md:53`). The deviation was logged
before analysis data existed and has a one-variable root cause.

**Rejected alternative.** Widening the window to 2^21 cycles keeps the task text's
8 KiB but doubles every run for no gain in validity.

**How verified.** **[run-verified]** from stored P1 output and `config.ini`.

**What would prove it wrong.** Trace recall below 1.000 in P2a (full AES touches four
times as many lines per window).

**Preregistration action.** None; D0 stands. Fix the stale comment at
`victim_leak.c:114` ("128 lines") only if the binaries are rebuilt anyway, because it
changes a hashed source file.

**Proposal compatibility.** None.

### Q6. Scope

**Recommendation.** Present it as one clearly labelled section after the proposal's
results, titled as an extension, and email the instructor now. Do not weave it into
Sections VII to X.

**Why.** The proposal's bound is explicit ("does not recover or guess key bytes"),
and the paper repeats it. A known-key assessment is a different activity from key
recovery: Goodwill et al. state that a device can fail their test "without full key
extraction", and the method's whole point is to avoid mounting attacks. The dropped
key-guess scan and the fixed-hypothesis design keep the study on the right side of
that line; the collision-count models added here are again fixed and key-known. The
risk is presentational, so the label, the section boundary and the instructor's
answer matter more than any further technical restriction.

**How verified.** **[source-verified]**: proposal section 1 ("Bounded objective"),
paper Section I.A, `README.md:24-33`, Goodwill et al. section 1.

**What would prove it wrong.** The instructor declining. Section 7 has the fallback.

**Preregistration action.** None. Decision only the student can take: send the
instructor the question (two sentences and the paragraph in section 7) before block
E2, because E2 and E3 are the parts that exist only for the extension.

**Proposal compatibility.** Additive, and only if labelled.

### Q7. P4 and combining the tracing extension with the defense patches

**Recommendation.** There is no conflict. Build one new tree,
`~/eel5764/gem5-leak-def`, from commit `c8222cc` plus the stored patch
`experiments/respq-defense-20261018/gem5-respq.patch`, with this experiment's
`gem5_ext` as `EXTRAS`; guard it; run the full defense in the overlap schedule only.

**Why.** *Trees.* `gem5-timeslot` holds the time slots only; `gem5-respq` holds both
mechanisms (V08). *Overlap.* The tracing extension lives entirely in `EXTRAS`
(`gem5-leak` has 0 modified files); the defense patch touches 15 files under `src/`,
none of them the extension's, and no line of it mentions the partition manager. The
manager is called from `mem/cache/base.cc:1694-1695` and
`mem/cache/tags/base_set_assoc.hh:207-209`; the patch's `base.cc` hunks are at old
lines 44, 79, 117 and 339. The stored patch has the same 30 hunks as the live tree and
passes `git apply --check` on a clean `c8222cc`. *Adapter.* The paper's adapters set
`tdma_slot_cycles`, `tdma_port_domains` and `response_domain_prefixes` inside a wrapped
`m5.instantiate` (`experiments/tdma/run_contention_tdma.py:36-46`,
`experiments/respq-defense-20261018/run_contention_respq.py:35-52`); `run_leakage.py`
wraps the same hook (`run_leakage.py:244-254`). The reference wrapper chains them and
is tested with a fake m5 (10 tests, V10). The line map survives the statistics reset
because it is copied from a member in `preDumpStats`
(`gem5_ext/requestor_partition_manager.cc:251-261`).

**Rejected alternative.** Reusing the existing `gem5-respq` binary: it lacks the
`victim_*` parameters, so `run_leakage.py` refuses it and the analysis has no line
map.

**How verified.** V08, V10, V12 **[run-verified]**. The build itself is
**[unverified]**: 13 min at `-j14`; guard `p0d-r1-scrub-n20` (0.1 min) must be
byte-identical to `p0b-r1-scrub-n20`.

**What would prove it wrong.** A guard mismatch, or a nonzero `tdmaOverruns`,
`tdmaDownstreamRefusals` or `tdmaExpressBypasses` counter in a defended run.

**Preregistration action.** D4 (draft 2026-11-12; commit before any block E3 run):
"The full defense … is evaluated in the overlap schedule only. It uses a gem5 binary
built in a new tree, `~/eel5764/gem5-leak-def` … Guard before any defended run: with
the defense off, the new binary must reproduce `runs/p0b-r1-scrub-n20/probes.bin` byte
for byte (run `p0d-r1-scrub-n20`). The existing gem5 trees are not modified."

**Proposal compatibility.** Additive; the paper's four trees and results stay
untouched.

### Q8. Value of the last-round analysis

**Recommendation.** Keep it as a secondary result for P2a only. Make round 1 the
headline and make no last-round claim for any defended arm.

**Why.** The S-box has four lines and a full encryption touches all four in 96.3% of
windows, so the contrast is 0.012 (V04). The synthetic power table was right to call
it weak under 6 cycles of noise, but the real channel has none: the forecast is 16/16
bytes at N = 2000 on all three seeds. It costs nothing extra in P2a. For defended arms
the differential test already covers every round at once.

**How verified.** V04 **[run-verified]** (synthetic, built from P1's measured
latencies).

**What would prove it wrong.** P2a with `lr_c_xor_k10` on 0 bytes at N = 2000. Report
it as a power limit, as the preregistration already says
(`PREREGISTRATION_DRAFT.md:154-157`).

**Preregistration action.** Last sentence of D2: "The last-round statements are
secondary and are interpreted for P2a only."

**Proposal compatibility.** None.

### Q9. Timeline

**Recommendation.** Do the code and deviations this week, run block E1 (50 minutes of
simulation) before the video, and treat everything after E1 as optional in the cut
order of section 6. Stop new runs on 2026-11-24.

**Why.** E1 alone gives the extension a complete, defensible story: what the
unprotected channel encodes (P2a, P2b) and that way partitioning removes the state
channel (differential). The video (Nov 17) and Q&A (Nov 19 to 20) need the proposal's
results, which are frozen and finished.

**How verified.** Times from V01 and V07 **[run-verified]**: 3.19 million cycles per
second, 0.67 GiB per run, 20 cores, so four parallel runs are safe.

**What would prove it wrong.** E1 not finishing in one working session.

**Preregistration action.** None.

**Proposal compatibility.** None.

## 4. The brief's limitations (section 10, items 1 to 9)

1. **State, not contention: mitigate.** Overlap experiment (Q1) plus the frozen
   cross-seed result (V06). State it as the reason the window schedule says nothing
   about the two interconnect mechanisms.
2. **Trace sees allocations only: accept.** Under D1 the trace is not needed for
   defended arms; the line map survives regardless (Q7).
3. **Noise-free baseline against the statistic: mitigate.** D1 and D2. The brief
   understated it: the rule is magnitude-blind and inflates false positives (V03).
4. **D0: accept.** Q5.
5. **Generality: keep** as a stated limitation, in the paper's words.
6. **Different SNR: accept.** Never call the variance ratio "SNR" in the paper; the
   proposal's SNR appears only with the proposal's runs.
7. **20-window statistics are observations: keep.**
8. **Cost figures are estimates: resolved.** Use the measured 3.19 million cycles per
   second (V01).
9. **Preregistration frozen without group edits: mitigate.** D1 to D4 and the overlap
   preregistration are the group's review point. Each member should read and initial
   them in `progress.md` before block E1. Only the student can arrange that.

## 5. Problems the brief missed

Ranked by threat to the conclusions.

1. **The registered matched controls cannot leak.** The stored unpartitioned controls
   at monitor depth 1, 4 and 8 have 0 LLC replacements and 0 monitor misses in 9 of 9
   runs, against about 738,000 AES accesses each (V05). The victim's footprint is a
   few pages, at most about 2 lines per LLC set, so 8 + 2 < 16 and nothing is ever
   evicted. By the registered gate (`PREREGISTRATION_DRAFT.md:84-86`) every P3 and P4
   pair would be "uninterpretable": 18 runs and 6.6 h for no result. The paper's
   matched-control logic was built for a hit-latency channel and does not transfer to
   a state channel. [run-verified on the paper's binaries; this study's victim adds
   one 4 KiB scrub page, so the inference is **[unverified]** for it: block E1's four
   `e1-c*` runs test it, expected `IDENTICAL`.]
2. **The analysis crashes on the outcome a working defense produces.** A flat log
   raises `ValueError` in `anova_p_min` (`analysis/aes_leak_analysis.py:264`, V11).
   A three-line fix and a test are in `postdoc-review/reference/`.
3. **The frozen data already contain a differential result** the brief does not use
   (V06): full defense identical across seeds at 8 of 8 allocations, partition-only
   different at 8 of 8. The brief's "no defense has been evaluated yet" is true of
   this harness only.
4. **The decision rule has no effect size and is miscalibrated** on near-constant
   data (V03). The brief's item 3 mentions the zero-variance substitution but not the
   9.7% false-positive rate or that a 0.007-cycle effect passes.
5. **Full AES is a different regime from P1.** 57.7 of 64 Te lines are touched per
   encryption, the round-1 contrast is 8 times smaller, and the probe pass has 1.16x
   worst-case headroom against its deadline (V04, V01). The brief sizes P2 from P1's
   2,642-cycle figure.

**Mismatches between the brief and the files** (files win):

* `PREREGISTRATION_DRAFT.md:3` still reads "Status: DRAFT. Not frozen. No gem5 data
  from this experiment exist", while `:199` records the freeze. `README.md:62` repeats
  "(DRAFT, not frozen)". The brief says frozen. A test requires the word "DRAFT" to
  stay in the file, so correct the status sentence without removing that word.
* The brief's "2,642-cycle effect" is mean-touched minus mean-untouched. The
  registered statistic's own raw effect is 2,177 cycles per predicted line (V02),
  because a line not predicted for one byte is often touched by another.
* `victim_leak.c:114` still says "128 lines" after D0 changed the walk to 64.
* `preserve.py verify` currently fails: it pins
  `.claude/handoff-nudge-state.json`, assistant-session state that other sessions
  rewrote at 12:58, 22 minutes after the manifest was captured. Nothing in the
  experiment changed; the brief's "nothing outside the directory changed" check
  cannot be reproduced until this is fixed (fix and test in `reference/`).

## 6. Revised run plan to December 1

Details, commands and gates are in `EXECUTION_PLAN.md`. Times are simulation minutes
from V01; wall time assumes four runs in parallel.

| Block | Runs | N | Sim. min | Wall | New code |
|---|---|---|---|---|---|
| Preparation | none | - | 0 | half a day | two fixes, `leak_followup.py`, `run_arm.sh`, D1 to D3 |
| E1 window schedule | P2a, P2b (S1); unpartitioned depth 8 and 1 (S1, S2); 8/8 and 1/15 (S1, S2, S3) | 2000; 500 | 22 + 28 = 50 | 20 min | none beyond preparation |
| E2 overlap, no interconnect defense | pilot; depth 8 and 1, unpartitioned and partitioned (S1, S2), `r1-scrub` | 200; 2000 | 1 + 88 = 89 | 35 min | overlap builds, `PREREGISTRATION_OVERLAP.md` |
| E3 full defense, overlap | build, guard, 8/8 and 1/15 (S1, S2) | 20; 2000 | 44 (+13 build) | 30 min | `run_leakage_defense.py`, new tree, D4 |
| E2x exploratory | full-AES overlap, 8/8 and 1/15 (S1, S2) | 2000 | 44 | 15 min | none |

Suggested dates: preparation and E1 by Nov 16; instructor's answer by Nov 20; E2 and
E3 Nov 21 to 23; writing Nov 24 to 28; buffer to Dec 1.

**Cut order if time runs short** (first cut first): E2x; the last-round statements;
P2b; E3's runs (cite V06 instead: the frozen data already show cross-seed identity
under the full defense); E2's collision-count attribution (keep its differential
test); all of E2. Never cut: the proposal's own results, D1 to D3, P2a, and the
partitioned differential arms of E1.

## 7. Draft paper text

> **Extension beyond the proposal: what the monitor's signal encodes.** The accepted
> proposal covers activity detection and performance only, and Sections IV to X report
> it unchanged. This section adds one question the proposal did not ask: when the
> monitor's timing changes, does the change depend on the data being encrypted? We
> answer it as a known-key leakage assessment inside the simulator. The AES key is a
> fixed public test constant that the workload prints, the plaintexts are public, and
> the analysis is given the key in advance. It compares fixed, key-known hypotheses
> about which table lines an encryption uses with the monitor's timing. It never
> guesses, ranks or recovers key bytes, uses no unknown key, and involves no hardware
> or external system. Because gem5 is deterministic, the main test is differential:
> the same configuration is run with different public plaintext streams, and
> byte-identical monitor logs show that the monitor's observation did not depend on
> the data for those streams. The results describe what each defense removes in this
> simulated configuration; they are not an attack and make no claim about real
> processors.

Fallback if the instructor declines beyond-proposal work: delete this section and its
figures, so that Sections I to XII match the submitted v2 paper, and offer the study
as a separately labelled appendix or leave it out.

## 8. Sources

Opened in this review. "Full text" means I read the pages cited; "abstract" means
only the abstract page, and only the abstract's claims are used.

1. Q. Ge, Y. Yarom, T. Chothia, G. Heiser, "Time Protection: The Missing OS
   Abstraction", EuroSys 2019. DOI 10.1145/3302424.3303976;
   https://arxiv.org/abs/1810.05345. Full text, sections 2.2 to 3.2. Supports:
   capacity-limited versus bandwidth-limited channels; flushing and partitioning for
   stateful resources; interconnects need time-multiplexing or bandwidth partitioning;
   LLC partitioning by colouring or CAT.
2. R. Paccagnella, L. Luo, C. W. Fletcher, "Lord of the Ring(s): Side Channel Attacks
   on the CPU On-Chip Ring Interconnect Are Practical", USENIX Security 2021.
   https://arxiv.org/abs/2103.03443. Full text, pages 1 to 2. Supports: a contention
   channel works despite LLC partitioning; it sees coarse events such as private cache
   misses; it uses temporal patterns.
3. J. Bonneau, I. Mironov, "Cache-Collision Timing Attacks Against AES", CHES 2006.
   DOI 10.1007/11894063_16; https://www.jbonneau.com/doc/BM06-CHES-aes_cache_timing.pdf.
   Full text, pages 1 to 5. Supports: cache collisions between lookups change timing
   and carry relations between key bytes; contrast with access-pattern attacks.
4. D. A. Osvik, A. Shamir, E. Tromer, "Cache Attacks and Countermeasures: the Case of
   AES", CT-RSA 2006. DOI 10.1007/11605805_1; https://eprint.iacr.org/2005/271.
   Abstract. Supports: cache state leaks memory access patterns of table-lookup AES.
5. V. Kiriansky, I. Lebedev, S. Amarasinghe, S. Devadas, J. Emer, "DAWG: A Defense
   Against Cache Timing Attacks in Speculative Execution Processors", MICRO 2018.
   DOI 10.1109/MICRO.2018.00083; https://eprint.iacr.org/2018/418. Abstract. Supports:
   way partitioning with protection domains targets the cache-state channel.
6. G. Goodwill, B. Jun, J. Jaffe, P. Rohatgi, "A testing methodology for side-channel
   resistance validation", NIST Non-Invasive Attack Testing Workshop, 2011.
   https://csrc.nist.gov/csrc/media/events/non-invasive-attack-testing-workshop/documents/08_goodwill.pdf.
   Full text, pages 1 to 3. Supports: leakage assessment by hypothesis test on
   sensitive intermediates; failing does not require key extraction.
7. T. Schneider, A. Moradi, "Leakage Assessment Methodology: A Clear Roadmap for
   Side-Channel Evaluations", CHES 2015. DOI 10.1007/978-3-662-48324-4_25;
   https://eprint.iacr.org/2015/207. Abstract. Supports: Welch's t-test as the
   standard architecture-independent assessment.
8. D. Lakens, "Equivalence Tests: A Practical Primer for t Tests, Correlations, and
   Meta-Analyses", Social Psychological and Personality Science 8(4), 2017.
   DOI 10.1177/1948550617697177. Full text (Europe PMC, PMC5502906). Supports:
   non-significance is not evidence of absence; equivalence needs a smallest effect
   size of interest.
9. G. Doychev, D. Feld, B. Köpf, L. Mauborgne, J. Reineke, "CacheAudit: A Tool for the
   Static Analysis of Cache Side Channels", USENIX Security 2013.
   https://eprint.iacr.org/2013/253. Abstract. Supports: for a deterministic cache
   model, leakage bounds come from static analysis, for observers of cache state, of
   hit and miss traces, and of time.
10. Q. Ge, Y. Yarom, D. Cock, G. Heiser, "A Survey of Microarchitectural Timing
    Attacks and Countermeasures on Contemporary Hardware", Journal of Cryptographic
    Engineering, 2018. DOI 10.1007/s13389-016-0141-6; https://eprint.iacr.org/2016/613.
    Abstract. Supports: classifying attacks by the shared resource they use.

Not opened, so not cited as evidence: Liu et al. (CATalyst), Demme et al. (SVF), Wang
et al. (HPCA 2014). T. Bourgeat et al., "MI6" (https://arxiv.org/abs/1812.09822): the
abstract was opened but says nothing about per-domain queues, so it supports no claim
here.

## 9. Review log

**The two subagent reviews were not run.** The brief for this review asked for a
fresh-context review of the memo and a Sonnet dry read of `EXECUTION_PLAN.md`. Before
they started, the student instructed: "don't test. Just write the plan for sonnet
5.5". Both reviews are therefore outstanding, and neither "done" criterion that
depends on them is met.

What stands in for them, and what does not:

* The plan's commands were not read by a second reader. They were checked
  mechanically instead: all 30 run commands pass the launcher's pre-flight and the
  baseline config's validators (V12); the launchers were exercised end to end with a
  fake gem5 (V14); the reference code passes 33 new tests and leaves the 139 existing
  ones passing in a mirror copy (V10).
* Self-review found and fixed four defects in my own work before delivery: a
  permutation count too small for a Holm family of 96 (the tool now refuses it); a
  round-1 collision count that is too diluted in a full encryption (the overlap
  experiment now registers the round-1-only victim); parallel appends that lost
  summary lines on the Windows-mounted file system (the batch launcher now assembles
  its summary serially); a false "overlap" match on a file basename in V08.
* Not checked by anyone but me: the wording of the memo against the guardrails, and
  whether a literal reader would have to guess anywhere in the plan. Steps 2.2, 3.6,
  4.8 and 5.7 of the plan (hand edits of `README.md` and `progress.md` from
  templates) are the places where that risk is highest.
* Written after the instruction to stop testing, and so not exercised: the final text
  of `EXECUTION_PLAN.md`, `reference/docs/PROGRESS_TEMPLATES.md` and
  `reference/README.md`.
