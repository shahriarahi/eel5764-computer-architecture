# Cache-partitioning research handoff — October 16, 2026

## Read this first

We are investigating whether AES activity can become indistinguishable to a
cross-core cache monitor while retaining disjoint A/(16-A) LLC way partitions.
The accepted way-partitioning study is preserved. A separate fixed-slot request
scheduler is implemented, tested, and pushed to an experimental GitHub branch.
It reduces the measured signal but **does not establish indistinguishability**.

The latest work explored additional defenses. Those defenses are hypotheses:
no response-queue isolation, completion-deadline mechanism, or epoch defense has
been implemented or simulated. The next recommended step is causal localization
of the residual timing signal, followed by a targeted experimental defense.

This is a new handoff. The older `HANDOFF.md` remains unchanged.

## Workspace, repository, and checkpoint

- Windows workspace: `C:\Users\shahr\OneDrive\Documents\Fall 26\Computer Architecture`
- Shell: PowerShell; the gem5 build and simulations use the previously authorized WSL environment.
- Private repository: <https://github.com/shahriarahi/eel5764-computer-architecture>
- Original project branch: `main`, baseline checkpoint `6872f08`.
- Experimental branch: [`experiment/tdma-prototype`](https://github.com/shahriarahi/eel5764-computer-architecture/tree/experiment/tdma-prototype).
- Latest experimental commit: `acb7855e30271619433e9dcb8a11adf947f3fff3`.
- Experimental project worktree: `.codex-tmp\tdma-worktree` beneath this workspace.
- Prototype files: `.codex-tmp\tdma-worktree\experiments\tdma`.
- Isolated WSL gem5 source/build: `/home/shahriarahi/eel5764/gem5-timeslot`.
- Original WSL source/build: `/home/shahriarahi/eel5764/gem5`.
- gem5 base: v25.1.0.1, commit `c8222cc67a399bfc01e8658dd14b30d5bfd634f9`.
- Python observed: Windows 3.14.7; WSL 3.14.4. Recheck the active environment before running scripts.

The experimental worktree was clean and tracking its remote at handoff creation.
The branch has been pushed; it has **not been merged into main**. An older
sentence in `experiments/tdma/RESULTS.md` says no push was performed. That sentence
predates the push and is superseded by this checkpoint.

The three experimental commits are:

1. `a1fe4e4` — isolated fixed-slot prototype and validation harness.
2. `07b4f99` — endpoint results and preservation audit.
3. `acb7855` — proposal review and approved prototype plan.

## Preserve the original proposal and study

The local proposal is `Group18_EEL5764_Final_Project_Proposal_Aligned.docx`:
“Evaluating LLC Way Partitioning as a Defense Against Simulated Cross-Core AES
Cache Contention.” Do not rewrite its research question or replace the original
negative result with the newer mitigation experiment.

The original design uses two RISC-V TimingSimpleCPU cores, classic caches, and a
256 KiB, 16-way, 64-byte-line LLC. The monitor owns ways [0,A); AES owns [A,16).
CPU clocks are 2 GHz and the system clock is 1 GHz. Each execution has 64 labelled
intervals: 32 active and 32 idle, each lasting two million CPU cycles.

The frozen study has 48 inferential executions: three public seeds, A=1..8, and
matched unpartitioned/partitioned arms; two A=16 executions are diagnostic.
Seeds `0x5764A5E5`, `0x5764A5E6`, and `0x5764A5E7` share an activity schedule;
they are not three independent activity schedules. The final v3 study found
detectable activity at all eight allocations. The earlier October 1 conclusion
was withdrawn because of a monitor self-eviction confound; use the corrected v3
monitor and final results.

The scheduler is a separate follow-up independent variable. Keep the proposal,
original configuration, monitor/AES binaries, logs, and baseline executable
unchanged. The preservation manifest covers 3,042 original files plus the
baseline executable. Do not stage experimental copies onto `main` accidentally.

## Completed fixed-slot prototype

The scheduler gates request admission at the shared coherent crossbar. Domains
alternate 4 ns slots, making an 8 ns frame. A domain may launch one request at
its slot start; unused slots remain idle. Transfers must finish strictly before
the next slot. The implementation covers ordinary requests and dirty writebacks
and maps cache and MMU-walker ports to the owning CPU domain.

This is request-ingress scheduling, not complete LLC service or response-path
isolation. Downstream refusal, unsupported express-snoop bypass, unexpected
request-layer contention, and transport overruns are explicit failures. General
retry-tolerant timing isolation is not implemented.

The isolated build uses `build/RISCV/gem5.opt`. No modification was made to the
original executable. The baseline EXTRAS path remains
`/home/shahriarahi/eel5764/gem5_ext`; it points to the original Windows `gem5_ext`.

Important prototype files, relative to `experiments/tdma`:

| File | Purpose |
|---|---|
| `DESIGN.md`, `PLAN.md`, `PREREGISTRATION.md` | Scope, execution plan, and declared endpoint analysis |
| `gem5-timeslot.patch`, `slot_schedule.hh` | Isolated gem5 changes and integer-tick slot policy |
| `prepare_gem5.py` | Applies changes against checked source anchors |
| `run_contention_tdma.py` | Adapter around the unchanged original configuration |
| `run_pilot.py` | Fresh-process execution, bounded runtime, fresh output directories |
| `run_structural.py`, `test_traffic.py` | Real gem5 structural traffic tests |
| `validate.py` | Record, mapping, way-isolation, and scheduler checks |
| `summarize.py`, `summary-final/summary.json` | Statistical analysis and final six-cell summary |
| `verify_results.py`, `preservation.json` | Read-only final audit and original-file fingerprints |
| `RESULTS.md`, `progress.md`, `build_manifest.json` | Results, execution history, and build provenance |

Proposal review and plan are also retained at
`docs/TIME_SLOT_PROPOSAL_REVIEW_20261015.md` and
`docs/superpowers/plans/2026-10-15-time-slot-prototype.md` in the experimental
worktree. Copies exist in the original workspace.

## Measured simulation results

There are 18 completed efficacy executions: three seeds × two allocations
(1/15 and 8/8) × three arms (`off`, `way`, `onx`). Four additional disabled guards
checked the experimental executable against original behavior. The full A=1..8
sweep was not started because the endpoint inference gates did not both pass.

Values below are simulated active-minus-idle hit-only latency, in CPU cycles
per probed line, averaged over the three seeds. Confidence intervals are the
declared 90% bootstrap estimates. These are not hardware measurements.

| Allocation | Unpartitioned | Way-only | Way + request slots | Scheduled 90% CI | Mean equivalence within ±0.02 |
|---|---:|---:|---:|---|---|
| 1/15 | 0.347451 | 0.345984 | 0.039892 | [0.032308, 0.048177] | FAIL |
| 8/8 | 0.401036 | 0.279303 | 0.003959 | [0.002954, 0.004932] | PASS |

| Scheduled allocation | Max-set Fisher/Holm p | Hit-only Fisher/Holm p | AES throughput change versus way-only |
|---|---:|---:|---:|
| 1/15 | 1.0 | 8.2051e-10 | -5.9723% |
| 8/8 | 1.0 | 2.8232e-9 | -5.9316% |

The two statistics aggregate different observations. A nonsignificant max-set
test does not override the detectable hit-only signal. Passing mean equivalence
at 8/8 does not establish equality of timing distributions. The shared schedule
and finite permutation floor also limit interpretation of combined p-values.
No key recovery, held-out classifier, adaptive attacker, or hardware evaluation
was performed.

Raw outputs are retained under `results/updated run/tdma-gd0`, `tdma-off`,
`tdma-way`, and `tdma-onx` in the original workspace. These paths were selected
to preserve executable/configuration path-length conditions. After completion,
280 output files were copied byte-identically into the experimental worktree
and committed. Preserve both copies; do not move or overwrite the originals.

## Verification already performed

The following command ran from the experimental `experiments/tdma` directory
in WSL. This is recorded execution evidence, not a claim of a fresh audit when
this handoff file was written:

```text
python3 verify_results.py --baseline-root '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture'
```

Actual output:

```text
PASS 18/18 efficacy cases: records, mapping, isolation and scheduler gates
PASS 4/4 disabled guards: identical probes and simulated statistics
PASS 12/12 fresh baseline arms: identical probes to original study
PRESERVED 3042 original files and baseline executable
PASS final summary: six cells, three public seeds each
```

Other completed checks:

- `python3 -m unittest discover -s tests -p 'test_*.py'`: 70 tests, OK.
- `python3 -m unittest discover -s experiments/tdma -p 'test_*.py'`: 10 tests, OK.
- `g++ -std=c++17 -Wall -Wextra -Werror test_slot_schedule.cc -o /tmp/tdma-slot-test`, then `/tmp/tdma-slot-test`: passed ownership, boundary, strict-retry, single-grant, and transport-bound checks.
- `python3 run_structural.py --out structural-03`: passed reads, idle-peer, dirty-writeback, and expected forced-refusal behavior. The forced-refusal test intentionally aborts.
- All six scheduled efficacy executions had zero scheduler violations and disjoint treatment-way snapshots.
- Original project and original gem5 tracked files were unchanged; output-copy fingerprints matched.

The isolated build used:

```text
scons build/RISCV/gem5.opt -j14 EXTRAS=/home/shahriarahi/eel5764/gem5_ext
```

Existing toolchain warnings include GCC 15 outside gem5's stated supported
range and absent Capstone. The executable built and passed the recorded tests;
these warnings were not resolved by installing dependencies. Failed early
structural runs remain preserved in `structural-01` and `structural-02`; use
`progress.md` for the harness fixes and build history.

## What the latest source inspection established

In gem5's cache source, `src/mem/cache/base.hh` has one CPU-side response queue
and CPU-side port for this cache. `src/mem/packet_queue.cc` handles a failed
response send by retaining the packet and waiting for retry. Response routing
through per-CPU crossbar response layers happens after the shared LLC queue.

This confirms a remaining shared structure, **not its causal responsibility**
for the measured residual. LLC service timing, response backpressure, other
transient state, or a fixed-label/monitor-periodicity confound still require
localization. Earlier runs with zero MSHR blocking do not rule out other queues.

The prior mechanism study is in `REPORT_UPDATED_RUN_20261011.md` and
`PREREGISTRATION_MECHANISM_20261014.md`. It implicated the shared request layer;
a near-ideal crossbar still left a small 8/8 residual. That evidence motivated
request TDMA but does not identify the current residual's source.

## Candidate defenses — all untested here

| Candidate | Mechanism to investigate | Condition or limitation |
|---|---|---|
| Per-domain response queues plus fixed response slots | Separate response buffering/retry state and reserve return bandwidth; retain way masks and request TDMA | Recommended first mitigation if tracing implicates the shared return path; queue capacity and backpressure must also be isolated |
| Full LLC service scheduling | Schedule demand, writeback, memory-return, and coherence service; isolate transient resources as needed | More complete than ingress scheduling; identify all shared service paths before claiming isolation |
| Fixed completion deadlines | Hold responses until a predetermined deadline relative to a reserved grant | Requires isolated buffering and a justified worst-case bound; late completion is a violation, not permission to move the deadline |
| Fixed epochs with guard/drain intervals | Give each domain a fixed service window and drain transient work before handover | No early borrowing; observed maximum drain time is not a worst-case proof; DRAM state needs separate treatment if in scope |

These are proposed adaptations. No security or performance outcome is known
for them in this project. Random delay alone is not a demonstrated solution:
an attacker may average noise while the underlying activity dependence remains.

## Sources and usable implementation references

- [MI6, MICRO 2019](https://people.csail.mit.edu/bthom/micro19.pdf), particularly §§5.4.2–5.4.3: discusses strict arbitration, response queues, and shared pipeline paths that remain after storage partitioning. Its storage partitioning differs from our A/(16-A) way split; adapting its principles is our proposal.
- [RiscyOO repository](https://github.com/csail-csg/riscy-OOO): useful processor baseline, not verified here as a complete release of MI6's security modifications.
- [Citadel repository](https://github.com/mit-enclaves/citadel): related implementation pointers. Its README describes hardware changes as forthcoming; do not present it as a verified drop-in hardware artifact.
- [Timing-channel protection for a shared memory controller, HPCA 2014](https://www.csl.cornell.edu/~suh/pubs/tp-hpca2014.pdf), §3.3: per-domain queues, static turns, and draining/state-management principles. Applying these memory-controller ideas to an LLC is a proposed adaptation.
- [Timing Compartments report record](https://ecommons.cornell.edu/entities/publication/ca16b1e8-0f68-4204-9ea8-b0078d942981): the abstract was checked; the full report PDF was not successfully retrieved. Do not imply it was fully read.
- [TimingCompartments author repository](https://github.com/aferr/TimingCompartments), inspected at `8c826a55fd5ed95b24a13489d97cb62a9586ee25`: a modified gem5/DRAMSim2 implementation reference. It has not been built here and compatibility with gem5 v25.1 is unverified.
- [`split_rport_cache.hh`](https://github.com/aferr/TimingCompartments/blob/8c826a55fd5ed95b24a13489d97cb62a9586ee25/src/mem/cache/split_rport_cache.hh): per-thread response queues and thread-specific response/retry interfaces.
- [`split_mshr_cache.hh`](https://github.com/aferr/TimingCompartments/blob/8c826a55fd5ed95b24a13489d97cb62a9586ee25/src/mem/cache/split_mshr_cache.hh): per-thread MSHR and write-buffer structures. Use as a design reference, not code assumed compatible with current gem5.

## Recommended continuation

1. Read `RESULTS.md`, `DESIGN.md`, `PREREGISTRATION.md`, and this handoff. Check the branch and preservation audit before modifying the isolated experiment.
2. Define a separate negative control using the same monitor and labels but no victim shared-cache traffic. Keep original binaries and frozen results intact. This tests whether monitor periodicity and the fixed label schedule can explain a residual.
3. Add targeted timestamps in the isolated build: request admission, LLC response-ready, response enqueue/dequeue, retry, and delivery. Compare matched monitor requests by index to find the first timing divergence.
4. If divergence arises in the response path, design per-domain response queues and fixed return arbitration. If it appears earlier, target LLC internal service instead. Obtain agreement on that concrete design before implementation.
5. Retest structural properties and 1/15 plus 8/8 first. Expand only after validity and endpoint gates pass. Preserve fresh output directories and explicit failure records.
6. Use independent activity schedules and held-out distributional attacks or declared equivalence bounds for stronger evidence. Neither a small mean nor p>0.05 alone establishes indistinguishability.

Do not rerun the frozen original sweep merely to continue this exploration.
Ask before overwriting/deleting files, installing dependencies, pushing changes,
editing raw logs, or starting newly scoped long commands, unless the existing
authorization clearly covers the action. No new mitigation implementation,
build, or simulation was started during the research exploration or handoff.
