# AES leakage attribution in gem5: status brief for discussion

EEL 5764 Computer Architecture, Fall 2026, Group 18. Follow-up to the submitted
paper "Evaluating LLC Way Partitioning as a Defense Against Simulated Cross-Core AES
Cache Contention". Status as of 2026-11-12. Final report due 2026-12-01.

## Reading guide

This file is self-contained: nothing needs to be run to follow it. Section 1 is a
two-minute summary. Sections 2 to 7 explain the project and the design from scratch.
Section 8 is what has actually been run, section 9 what was learned, sections 10 and
11 the weak points and the decisions where feedback is wanted. Section 14 maps every
number to the file it came from.

Two ground rules to keep in mind while reading:

* **Everything is simulated.** gem5, RISC-V, a toy T-table AES, a fixed public test
  key. No hardware, no real service, no secret. Every statement is about the simulated
  configuration.
* **No defense has been evaluated yet.** What exists is the instrument, its
  validation, and one positive control (an unprotected configuration where the leak
  is expected). The scientifically interesting runs (way partitioning, the full
  defense) have not been done.

## 1. Summary

* **Question.** The submitted paper asked *whether* a monitor core can tell that AES
  is running on another core, and whether LLC way partitioning (and two further
  mechanisms) stop that. This follow-up asks *what the visible signal encodes*:
  nothing data-dependent, the plaintext alone, or the plaintext combined with the key
  (and the same for the last round); and whether each defense removes
  data-dependent leakage or only the activity signal.
* **Design.** One measurement unit = one *window*: the monitor primes its own cache
  lines, the victim performs exactly one AES encryption of a public plaintext, the
  monitor re-times its lines. Each window is labelled with its plaintext. Hypotheses
  predict which table line the encryption touched; the analysis checks which
  hypothesis explains which monitor set got slower. The analysis uses the known
  public key and does **not** score key guesses.
* **Built and validated.** C workloads, a gem5 extension that traces victim table
  fills, a configuration adapter, an analysis pipeline, and 139 automated tests. A
  new gem5 build with the extension reproduces one stored paper run **byte for
  byte** when the tracing is off.
* **Run so far.** A 20-window smoke run failed its own timing check, was root-caused
  (an LRU cascade caused by the victim's cache-flush walk), fixed with a documented
  deviation, and then passed. The 2,000-window positive control passed its
  preregistered gate: with no partition, the signal carries plaintext combined with
  the key on 16 of 16 bytes.
* **Surprise.** In the unprotected control the channel is **noise-free**: an
  untouched table-line set takes exactly 513 cycles every time (standard deviation
  0.0) and a touched one about 3,100. That makes the statistics easy for the control
  and raises a design question for the defended arms (section 11, question 2).
* **Biggest scientific risk.** The window design measures cache *state* left by one
  encryption; the paper's residual channel was *contention* between concurrent
  traffic. Way partitioning removes state interference by construction, so a null
  result under partitioning would partly be a property of the instrument (section 10,
  item 1; section 11, question 1).
* **Feedback wanted on** the questions in section 11, mainly: whether the window
  design answers the right question for the defenses, whether to add an effect-size
  rule before the defended runs, and whether this extension is appropriate scope for
  the final paper.

## 2. Background: what the submitted paper showed

Setup (gem5 v25.1.0.1, RISC-V syscall-emulation mode): two in-order `TimingSimpleCPU`
cores at 2 GHz; private 16 KiB L1I and a deliberately small 4 KiB 4-way L1D; shared
256 KiB 16-way LLC (256 sets, 64 B lines, LRU); L2 crossbar; DDR3-1600. Core 0 runs a
Prime+Probe-style monitor that times only its **own** memory. Core 1 runs an
educational T-table AES-128 with a public key and public deterministic plaintexts.
The activity label follows a fixed public, non-alternating schedule of 64 intervals
of 2,000,000 cycles (32 active, 32 idle).

Findings of the paper (v2):

* An earlier version concluded that one monitor way (1/15 split) hides AES activity.
  That was an artifact: the monitor's own 384 KiB record array evicted 20 to 25% of
  its probe lines, only in partitioned runs. After a corrected record-free monitor
  and a self-eviction gate, all eight allocations (1/15 through 8/8 monitor/AES ways)
  remain distinguishable; the partitioned monitor keeps 70 to 100% of its matched
  control's signal (control effect +0.292 to +0.401 CPU cycles per probed line).
* The leak is a hit-latency shift, not an eviction. A preregistered crossbar ablation
  locates it in the shared L1-to-LLC crossbar request layer (a near-ideal crossbar
  removes 100% of the effect at 1/15 and 88% at 8/8; a +0.033 cycle residual is
  attributed to the LLC's own request path by elimination).
* Two added mechanisms close the channel: fixed request time slots at the crossbar
  and per-domain LLC response queues. With both, every allocation becomes
  indistinguishable under the same decision rule and the monitor's probe log is
  byte-identical whether the victim runs AES or stays idle (24 of 24
  seed-allocation configurations), at about 6% AES cost.
* The paper's security goal was deliberately narrow: detect whether latency differs
  between public AES-active and idle intervals. It reported "no key recovery".

Design culture of the paper that this follow-up inherits: matched control for every
treatment, preregistered decision rules, a self-eviction gate, frozen earlier results
(checksummed), and a separate gem5 tree for simulator changes.

## 3. The follow-up question

The paper detects *activity*. It never asked what in the data the monitor sees.
T-table AES makes this concrete: in round 1 the byte `i` of the state, `p_i XOR k_i`,
indexes table `Te_(i mod 4)`, so which cache line is touched depends on plaintext and
key. If a monitor can tell which line was touched, the signal is data-dependent.

Three nested questions, each answered per defense configuration:

1. Is there any data-dependent signal, or only an activity (presence) signal?
2. If so, does it depend on the plaintext alone or on the plaintext combined with the
   key? (Round 1.) Same for the ciphertext and last-round key. (Last round.)
3. Does each defense (way partitioning, time slots, per-domain response queues)
   remove the data-dependent part, or only the activity part?

This is the standard *known-key leakage assessment* of a countermeasure (comparable
in spirit to TVLA or known-key correlation tests): the key is handed to the analysis
and nothing tries to find an unknown key.

## 4. Scope and relation to the accepted proposal

The accepted proposal's bounded objective is "activity detection and performance
only; it does not recover or guess key bytes and does not target physical systems".
This follow-up therefore **goes beyond the accepted proposal** (it attributes the
signal to data), and the final paper should list it under changes from the proposal.
Whether the instructor accepts beyond-proposal work in the final paper has **not**
been confirmed.

Decisions already taken to stay as close to the proposal's bound as the question allows:

* An earlier plan ranked the true key among 16 (round 1) or 256 (last round)
  candidates per byte. That key-guess scan was **dropped**. The analysis compares
  three fixed hypotheses per round using the known public key. "Plaintext only" is
  the key-nibble-0 case, so this still separates plaintext from plaintext-plus-key
  without scoring guesses.
* A check of the proposal's own isolation metric (valid LLC blocks outside the
  assigned ways must be zero) was added for partitioned runs.
* The study stays simulator-only.

## 5. Primer: why a probe can see a table line

Skip this section if cache side channels are familiar.

**Prime+Probe on the LLC.** The monitor owns `A` lines in every one of the 256 LLC
sets (here `A = 16`, so it fills the whole LLC). Prime: walk those lines so they are
all resident. Probe: walk them again and time each set. If the victim allocated a
line into set `s` in between, one monitor line of that set was evicted, and probing
set `s` misses.

**The LRU cascade (important for results below).** The monitor walks each set's 16
lines in a fixed order. After a victim allocation, set `s` holds monitor lines
`m1..m15` plus the victim's line `x` (the oldest, `m0`, was evicted). Probing `m0`
misses; the refill evicts the least recently used line, which is now `m1`; probing
`m1` misses and evicts `m2`; and so on. **All 16 lines of the set miss.** A single
victim line therefore costs about 16 DRAM accesses (about 3,100 cycles instead of
513). This amplifies the signal enormously, and it also makes passes slow when many
sets are affected.

**T-table geometry (aes_ttable.c).** Four 1 KiB tables `Te0..Te3` (16 lines each; a
line holds 16 four-byte entries, so the line index is `value >> 4`) and a 256 B
S-box (4 lines; 64 one-byte entries per line, so the line index is `value >> 6`),
68 contiguous 64 B lines across two 4 KiB pages. Rounds 1 to 9: state byte `i`
indexes `Te_(i mod 4)`. The last round uses the S-box. The physical LLC set of each
line is not assumed; the simulator reports it.

**Why the key was changed.** The paper's key `000102...0f` has every upper nibble
equal to 0, so `(p XOR k) >> 4 == p >> 4` and plaintext-only versus
plaintext-with-key cannot be told apart. This study uses the public test key
`f1e2d3c4b5a69788796a5b4c3d2e1f10`, all upper nibbles nonzero.

**Why the plaintext generator was changed.** The paper's workload used a 64-bit
power-of-two LCG whose low byte repeats every 256 encryptions, which would tie
plaintext byte 0 to the window index. This study uses splitmix64.

## 6. Experimental design

### 6.1 The window

One window is 1,048,576 CPU cycles (about 524 microseconds at 2 GHz). Window `j`
starts at `w0 = T0 + j * W` with `T0 = 2,000,000` (the end of the warm-up).

```text
w0           +65,536                 +524,288      +589,824 +593,920                        +1,048,576
|-- scrub ---|---- prime (monitor) ---|-- encrypt --|  gap   |------ probe (monitor) ------|
 victim: flush   monitor fills its       victim runs    4,096     monitor re-times its sets
 its private L1  own 16 lines/set        ONE encryption cycles    and does one writev
```

* **Scrub (victim, optional):** walks a private buffer so the table lines leave the
  4 KiB L1D and the next lookups reach the LLC (otherwise most lookups are absorbed
  by the L1D).
* **Prime (monitor):** must finish before the encryption starts.
* **Encrypt (victim):** exactly one encryption, budget 65,536 cycles. Variants: only
  round 1's 16 table loads (a positive control: only round-1 lines are touched) or
  the full AES.
* **Probe (monitor):** starts 4,096 cycles after the encryption budget ends; must
  finish before the next window.
* Each process checks its own deadlines against the cycle counter and exits with
  status 2 and an error line if one is missed.
* **Output:** 16-byte records `{timestamp, latency, window, set}`, 256 per window, in
  the paper's probe format.

Measurement safeguards inherited from the paper's corrected monitor: probe chains
walked from registers, each result stored in the spare bytes of the just-walked probe
line, one `writev` per window, no new LLC line allocated by the monitor while
measuring.

### 6.2 Victim variants

| Variant | AES | Scrub | Purpose |
|---|---|---|---|
| `r1-scrub` | round 1's 16 loads only | yes | positive control (P0, P1) |
| `full-scrub` | full encryption | yes | main configuration (P2a, P3, P4) |
| `full-noscrub` | full encryption | no | how much leaks if the L1D is not flushed (P2b) |
| `tvla` | full encryption, even windows use a fixed plaintext | yes | optional fixed-vs-random cross-check |

The encryption code is the paper's, `#include`d rather than copied. The three AES
functions in the new victim are instruction-for-instruction identical to those in the
paper's binary (288, 85 and 171 instructions; only 4, 2 and 18 pc-relative address
operands differ).

### 6.3 Hypotheses and statistic

For each byte `i` (0..15) and window, a hypothesis predicts which table line was
touched:

| Hypothesis | Predicted line | Role |
|---|---|---|
| `p_xor_k` | `(p_i XOR k_i) >> 4` in `Te_(i mod 4)` | round 1, key-dependent |
| `p_only` | `p_i >> 4` in `Te_(i mod 4)` | round 1, no key |
| `shuffled` | `p_xor_k` with windows permuted | round 1, null control |
| `lr_c_xor_k10` | `InvSbox[c_i XOR k10_i] >> 6` in the S-box | last round, key-dependent |
| `c_only` | `c_i >> 6` in the S-box | last round, no key |
| `lr_shuffled` | `lr_c_xor_k10` with windows permuted | last round, null control |

Statistic ("attribution", location-aware): standardize each monitor set's latency
across windows; for hypothesis `h` and byte `i`, take the sets holding the table's
lines; score = average over lines of (mean latency when `h` predicts that line minus
mean latency otherwise). The z-score uses variance `1/c_in + 1/c_out` per line and
treats lines as independent; the p-value is one-sided normal. A window-shuffling
calibration (`--nperm`) checks that z behaves.

Alongside, a **location-free detection** ANOVA (does partitioning windows by a byte's
value explain latency in any set?) is reported; it cannot distinguish `p` from
`p XOR k` because XOR only relabels classes, and it is flagged unreliable below 10
windows per class.

**Decision rule (preregistered).** alpha = 0.05 with Holm correction over the 96
tests (6 hypotheses x 16 bytes) of one run. A data hypothesis is *supported* if it is
significant on at least one byte **and beats** its key-free alternative and its
shuffled control (higher z) on those bytes. Four statements: `round1_plaintext_plus_key`,
`round1_plaintext_only`, `lastround_c_xor_k10`, `lastround_ciphertext_only`.

**Ground truth.** The gem5 partition manager is invoked when the LLC allocates a
block. An extension logs, for the victim's requests inside the table address range,
the table line and physical set. The analysis compares per-window fills with the
lines the encryption algorithmically touches (recall and precision). The trace
records allocations only: a line that stays resident in the LLC leaves no fill.

### 6.4 Run matrix (preregistered, frozen at commit 675c047)

| ID | Purpose | Variant | `--split` | monitor ways | N windows | Seeds |
|---|---|---|---|---|---|---|
| P0 | smoke test | r1-scrub | off | 16 | 20 | S1 |
| P1 | positive control | r1-scrub | off | 16 | 2000 | S1 |
| P2a | full AES, scrub | full-scrub | off | 16 | 4000 | S1 |
| P2b | full AES, no scrub | full-noscrub | off | 16 | 4000 | S1 |
| P3a-c / P3a-t | control / way-partitioned 8/8 | full-scrub | off / 8-8 | 8 | 4000 | S1,S2,S3 |
| P3b-c / P3b-t | control / way-partitioned 1/15 | full-scrub | off / 1-15 | 1 | 4000 | S1,S2,S3 |
| P4a-t / P4b-t | full defense at 8/8 and 1/15 | full-scrub | 8-8 / 1-15 | 8 / 1 | 4000 | S1,S2,S3 |
| T | optional TVLA cross-check | tvla | off | 16 | 2000 | S1 |

Seeds are the paper's three public seeds (0x5764A5E5 = 1466213861, and the next two).
As in the paper they are repeated deterministic inputs of a deterministic simulator,
not independent replicates. Each partitioned treatment is paired with an
unpartitioned control of the same monitor depth, seed and binary; a treatment is
interpreted only if its control supports `round1_plaintext_plus_key`.

## 7. Implementation and process

**Components** (all under `experiments/aes-leakage/`; nothing outside it changes):

* `leak_schedule.h`: the schedule, key and plaintext stream (single source of truth;
  Python parses it).
* `victim_leak.c`, `monitor_leak.c`, `aes_leak_ext.c`: the workloads.
* `build.sh`: builds six binaries with the paper's compiler flags and writes a
  manifest with hashes and the `nm` layout; builds are reproducible.
* `gem5_ext/`: copy of the paper's partition-manager extension plus optional victim
  tracing (off by default).
* `run_leakage.py`: configuration adapter that loads the frozen paper config without
  running it, overrides a few tables, sets the tracing parameters, and writes
  `leak_config.json`; it refuses fake-clock builds, hash mismatches and a gem5 binary
  without the tracing parameters.
* `analysis/aes_leak_analysis.py`: reads a run directory, validates it, builds the
  line-to-set map, evaluates the hypotheses, compares with the trace, writes JSON and
  Markdown; also a synthetic run generator.
* `preserve.py`: sha256 of every file here, and proof that nothing outside the
  directory changed (in the working tree and in commits since the branch point).

**Testing.** 139 automated tests (five of them check this brief's own hashes,
headings and section numbering). Highlights: the C and Python plaintext streams
agree for several seeds; the AES extension passes the FIPS-197 known-answer test and
matches an independent numpy AES over up to 200 windows; the actual RISC-V binaries
run under qemu-user (with a fake clock, so format and checksums only, not timing);
the tracing patch type-checks against the real gem5 headers; the analysis recovers
known answers from synthetic runs (including a false-positive-rate check: on data
with no data dependence the decision rule fired in 15 of 400 runs, 3.75%, and any
hypothesis in 21 of 400, 5.25%); documented commands are validated against the
baseline config's own validators.

**Process integrity.** The implementation was done by an AI coding assistant working
under the student's direction, in phases with gates (A: code and tests; B: build the
tracing gem5 and run a byte-identical guard; C: 20-window smoke run; D: 2,000-window
positive control; E: the defense runs). The student approved the phases and the scope
decisions. The preregistration was frozen at commit `675c047` before the first
2,000-window run, at the student's instruction to proceed and **without edits from
the rest of the group**. Earlier paper results remain untouched and checksummed.

## 8. What has been run

All runs: gem5.opt built from the paper's gem5 commit plus the tracing extension
(executable sha256 `71845ebf51381bce...`).

### Phase B: build and the byte-identical guard

The new binary was built in 12 min 38 s. The guard re-ran one stored paper case,
`sweep-v3/seed-5764a5e5/UNPARTITIONED-A8`, with the paper's original config and the
tracing left off. The new `probes.bin` is **byte-identical** to the stored one
(sha256 `0ee71c2389afbabf2bb74393dd3b9c2a081c3c6f10ecbacb322a1c239a89848e`) and the
guest output matches (23,903 encryptions). The whole `stats.txt` differs only in a
wall-clock host-speed line and the four new, zero tracing statistics. Two details
mattered: the stored run ran from the project root, and its probe path was 150
characters (the monitor receives the path as an argument, which shifts its stack), so
the guard had to match both.

### Phase C: the smoke run failed, and why

P0 as specified (20 windows, unpartitioned, 16 monitor ways, round-1 lookups, 8 KiB
scrub) exited normally but the monitor reported `prime_deadline` at window 1 and wrote
only one window. Its prime pass took about 476,263 cycles against a 458,752-cycle
budget. The schedule had assumed about 280,000 cycles per A=16 pass (the paper's
figure, which was a pass of *hits*).

Cause, tested by changing one variable (scrub on or off; A=16, unpartitioned, full
AES unless noted):

| Run | Prime deadline | Monitor LLC miss rate |
|---|---|---|
| `r1-scrub`, 8 KiB scrub (the failed P0) | missed at window 1 | 53% |
| `full-scrub`, 8 KiB scrub | missed at window 1 | 59% |
| `full-noscrub` | all 20 windows complete | 7% |

The victim's scrub walk allocates one LLC line per scrub line into an LLC full of the
monitor's lines; the monitor's next prime, walking in the same order, cascades through
every affected set (section 5). From the miss counts this is on the order of 3,000
misses per prime (an estimate derived from the counts, not a direct measurement).

**Fix (deviation D0, logged before any analysis data):** the scrub walk is 4 KiB (64
lines, the size of the 4-way L1D) instead of 8 KiB. 64 consecutive lines put 4 lines
in each of the 16 L1D sets and replace every line under LRU. `W`, `T0` and all offsets
are unchanged. The re-run (P0 attempt 2) passed all checks; a third run reproduced it
byte for byte, so gem5 is deterministic for this experiment.

Measured margins with the 4 KiB scrub at A=16: the prime takes between about 335,000
and 393,000 cycles (found by sweeping the deadline; budget 458,752), and the probe pass
183,000 to 341,000 depending on the variant (budget 454,656). All failures in the sweep
occurred at window 0, so the cold first prime is the worst case.

Smoke runs of the other variants at N = 20 all ran cleanly. Worth noting:
`full-noscrub` had trace recall **0.291**: without the scrub only about 29% of the
table lines the AES touches ever reach the LLC. `full-scrub` had recall 1.000 and
precision 1.000.

### Phase D: P1, the 2,000-window positive control

Unpartitioned LLC, 16 monitor ways, round-1 lookups only, 2,000 windows, 10 min 59 s.

| Check | Result |
|---|---|
| Run | exit 0; `monitor status=PASS records=512000` (2,000 windows x 256 sets = 512,000 probe records, 8.19 MB); no deadline missed |
| `p_xor_k` | significant on **16/16** bytes (mean z 84.7) |
| `p_only`, `shuffled` | **0/16** each |
| `lr_c_xor_k10`, `c_only`, `lr_shuffled` | 0/16 each (round-1 mode has no last-round lookups, so these are extra null controls) |
| Decision rule | `round1_plaintext_plus_key` supported; the other three statements not |
| Location-free detection | `first_round` 16/16; all other partitions 0/16; all rows reliable |
| Trace | 29,095 fills, all inside the AES phase, none outside; recall 1.000, precision 1.000 |

This met the preregistered gate (`p_xor_k` 16/16, `p_only` 0/16, `shuffled` 0/16). It
validates the measurement chain; because it is an unprotected configuration with
round-1 lookups only, a positive result was the expected outcome.

## 9. Findings so far

1. **Measurement chain validated.** Fills traced by the simulator coincide exactly with
   the algorithmically touched lines; monitor sets slow down exactly when their line
   was touched.
2. **The unprotected channel is noise-free** (P1): untouched table-line sets take
   exactly 513 cycles in all 106,905 observations (about 32 cycles per LLC hit x 16);
   touched sets have median 3,127 and mean 3,155; a slow set (>= 1,000 cycles) appears
   in 100.0% of touched windows and 0.00% of untouched ones. The monitor learns
   exactly which table lines were touched. Three sets that are not table lines are slow
   in more than 99% of windows (constant victim data such as the stack).
3. **Strength is uniform across bytes** (z from 84.3 to 85.0). `p_only` scores z of
   -8.0 to -3.2: anti-correlated, as expected, since the true line differs from
   `p >> 4` at every byte (every key nibble is nonzero). With the paper's key this
   check could not have worked.
4. **Timing has a thin but verified margin** (prime about 1.17x to 1.37x; probe pass
   2.31x in P1, worst window 196,662 of 454,656 cycles, no drift over 2,000 windows).
   The paper's "about 280,000 cycles per pass" is not transferable to passes that
   follow victim allocations.
5. **The L1D flush matters a lot.** Without the scrub only about 29% of the touched
   lines reach the LLC (N = 20 smoke run).
6. **The location-free ANOVA is invalid at small N**: with 20 windows and 16 classes
   even the shuffled control came out significant on 16/16 bytes; the analysis now
   flags such rows as unreliable. The decision rule never used that table.
7. **The analytic z is conservative on real data:** with windows shuffled, 0.3% of z
   exceed 2.33 (nominal 1%) and the shuffled z has sd 0.72 (nominal 1).
8. **Synthetic power sizing is pessimistic.** It assumed 6 cycles of noise and a 4 to
   40 cycle effect; the real control has zero noise and a 2,642-cycle effect.

## 10. Limitations and threats to validity

1. **State, not contention.** In this schedule the encryption ends at least 4,096
   cycles before the probe starts and the monitor performs no memory access in
   between, so no victim traffic overlaps any monitor access. The windows measure
   cache-state leakage. The paper's residual channel (the shared crossbar request
   layer) needs concurrent traffic and cannot appear here. Way partitioning removes
   cache-state interference by construction, so a null result under partitioning must
   not be read as removing the contention channel's data dependence. An overlap
   variant (encrypt during the probe) exists as a build-time possibility (the offsets
   can be overridden) but is not part of the preregistration.
2. **The trace sees allocations only** (gem5 calls the manager when the LLC allocates
   a block). Partitioned runs keep the tables resident in the AES ways, so little or
   nothing is expected in their trace; low recall there is not an error.
3. **Noise-free baseline vs the statistic.** The frozen rule uses significance only.
   The standardization treats a zero-variance column as having sd 1 (one cycle), so
   in a noise-free arm the z is effectively measured in cycles, while an arm with
   tiny nonzero jitter is standardized by that jitter. A deterministic residual of a
   cycle or less could count as "supported" without being meaningful, and arms may not
   be comparable. See question 2.
4. **Deviation D0** changes the task text's scrub size (8 KiB to 4 KiB). It rests on
   one root-cause experiment and was made before analysis data existed; it assumes the
   L1D uses (near-)LRU replacement, which was checked indirectly through trace recall.
5. **Generality.** One key, one workload, one cache configuration (a small 4 KiB L1D
   stress configuration that is deliberately favorable to exposing T-table traffic), a
   deterministic simulator in which the three seeds are repeated inputs. The paper
   shares these limits.
6. **Different SNR.** The analysis' variance-ratio SNR is not the proposal's
   `|mean difference| / pooled SD`.
7. **The 20-window statistics in the smoke runs are observations only.** P1 is the
   first full-size run and is a gate, not a result about any defense.
8. **Cost figures are estimates.** Run times use about 3 million simulated cycles per
   second (measured for earlier runs); P1 took 10 min 59 s against an estimate of
   about 12 min.
9. **The preregistration was frozen by the assistant at the student's instruction,
   without group edits.** It is a faithful freeze of the draft, but the group has not
   reviewed it line by line.

## 11. Questions for discussion

Each item gives the current plan and the reasoning, so a different view can be
substituted.

1. **Does the window design answer the right question for the defenses?**
   *Current plan:* run P2 to P4 as registered; treat the results as statements about
   cache-state leakage and say so. *Concern:* the paper's remaining channel was
   contention, which this design cannot see. *Option:* a second, separately
   preregistered experiment in which the encryption overlaps the probe pass, to test
   whether data-dependent information crosses the crossbar. *Question:* is state-only
   enough for the final paper, or is the overlap variant needed to say anything about
   the time-slot and response-queue defenses?
2. **Effect-size rule on a deterministic noise-free system.** *Current plan (before any
   P3 data):* log a deviation (D1) that adds, to every treatment, a reported effect
   in cycles per predicted line and the fraction of the control's effect retained,
   plus a materiality threshold (the paper used an equivalence margin of 0.02 cycles
   per line). *Alternative:* because the simulator is deterministic, a **differential
   test** in the spirit of the paper's byte-identical idle-victim check: run the same
   arm with two different plaintext streams and compare the probe logs; byte-identical
   logs would show zero data dependence for those streams with no statistics at all
   (it would not cover all plaintexts, whereas the 4,000-window statistic aggregates
   over many). This alternative is a suggestion, not implemented. *Question:* which
   is more convincing for a deterministic simulator, or both?
3. **Is the statistic overkill, or wrong?** One-sided normal z, lines treated as
   independent, Holm over 96 tests, calibration only by window shuffling. *Question:*
   would a permutation test, an exact test on the touched/untouched indicator, or a
   mutual-information estimate be more defensible given the zero-noise control?
4. **Sample size.** Registered N = 4,000 for P2 to P4 (about 23 minutes per run,
   estimate; about 20 runs, about 8 hours sequentially). P1 suggests the controls
   need far fewer; the defended arms depend on an unknown residual. *Question:*
   reduce N for the controls, or keep one N for all arms for matched comparisons?
5. **Is D0 (4 KiB scrub) acceptable?** The alternative that keeps the 8 KiB walk is to
   widen the window (for example 2^21 cycles), which doubles every run's time.
6. **Scope.** Is it acceptable to present this as a clearly labelled extension beyond
   the accepted proposal, with the key-guess scan dropped? How should it be worded so
   it is not read as a key-recovery study?
7. **P4 (full defense).** It needs a gem5 tree with the time-slot and response-queue
   patches rebuilt with this extension and an adapter change. Any concern about
   combining the tracing extension with those patches?
8. **Value of the last-round analysis.** The S-box has 4 lines and the last round only
   16 lookups, so last-round attribution is a weaker test; synthetic sizing says it
   needs a strong effect and N of about 1,000 or more. Keep it, or restrict the paper
   to round 1?
9. **Timeline.** The final report is due 2026-12-01 (19 days after this brief). Which
   parts of this would the postdoc cut or reorder if time runs short?

## 12. What comes next

* **Phase E, runs that need no new work:** P2a and P2b (full AES, unpartitioned, with
  and without scrub) and the controls and way-partitioned treatments P3a/P3b.
* **P4** needs the extra build and adapter work in question 7.
* Before the defended arms: decisions on questions 1 and 2, logged as deviations with
  dates, before the corresponding data exist.
* All results will be reported against the frozen decision rule, with every deviation
  listed.

## 13. Glossary

* **LLC / way partitioning.** Last-level cache; restricting each security domain to a
  subset of the cache ways.
* **Prime+Probe.** Fill (prime) cache lines you own, wait, re-time (probe) them; slow
  accesses mean someone else used those sets.
* **LRU cascade.** Walking lines in the same order after one was evicted causes every
  subsequent line in that set to miss (section 5).
* **Window.** One prime / encrypt / probe cycle; the unit of observation here.
* **Scrub.** A victim-side walk over a private buffer to flush its own L1D so that
  table lookups reach the LLC.
* **Round 1 / last round.** The first and the final round of AES-128; round 1 lookups
  are indexed by `plaintext XOR key`, the last round uses the S-box.
* **Attribution / detection.** Location-aware test of which hypothesis explains which
  set slowed; location-free test of whether any set depends on a byte.
* **Holm correction.** Step-down multiple-comparison correction controlling the
  family-wise error rate.
* **TVLA.** Test vector leakage assessment: fixed-versus-random Welch t-test.
* **Deviation (D0).** A change to the preregistered or specified design, logged with
  its reason and the evidence.
* **Matched control.** The same monitor depth, seed and binary without partitioning.
* **Guard run.** A re-run of a stored paper case that must reproduce byte for byte.

## 14. Provenance: where each number comes from

All paths relative to `experiments/aes-leakage/` on branch `experiment/aes-leakage`.

| Claim | File |
|---|---|
| Paper results (section 2) | `Group18_EEL5764_Final_Paper_v2.pdf` at the project root |
| Schedule constants, key, plaintext stream | `leak_schedule.h` |
| Binary hashes, table layout | `build/n2000/build_manifest.json`, `progress.md` |
| Guard result and whole-stats comparison | `gem5_build.md`, `progress.md` ("Phase B: results") |
| P0 failure, diagnosis, margins, smoke runs | `progress.md` ("Phase C: results"); runs `runs/p0-r1-scrub-n20`, `runs/diag-*`, `runs/p0b-r1-scrub-n20`, `runs/p0c-r1-scrub-n20`, `runs/smoke-*` |
| P1 results | `runs/p1-r1-scrub-n2000/`, `runs/p1-r1-scrub-n2000.analysis.md`, `runs/p1-r1-scrub-n2000.detail.txt` |
| Preregistration, decision rule, deviation D0 | `PREREGISTRATION_DRAFT.md` (frozen at commit `675c047`) |
| Synthetic power and false-positive rates | `synthetic_power.md` |
| Test suite | `tests/` (139 tests) |
| Nothing outside the directory changed | `preserve.py`, `preservation.json` |

Key commits on `experiment/aes-leakage` (local, not pushed): schedule header and AES
extension `d103fd2`; workloads, build, tracing copy `67c3f04`; analysis, adapter,
preservation `6b99700`; docs `58f1262`; Phase B record `44099f9`; Phase C and D0
`675c047`; preregistration freeze `2c287ce`; Phase D `ab2650e`.

Key constants: `T0` = 2,000,000; `W` = 1,048,576; prime at +65,536; encryption at
+524,288 with a 65,536-cycle budget; probe at +593,920; N up to 65,535 (the record's
window field is 16 bits).
