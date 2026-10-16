# Separate Time-Slot Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after user review. Steps use checkbox syntax for tracking.

**Goal:** Test whether fixed request-service slots attenuate the residual activity signal at 1/15 and 8/8 without changing the original study.

**Architecture:** Patch only an isolated gem5 v25.1.0.1 source worktree; leave the original checkout and executable unchanged. Add a disabled-by-default, two-domain scheduler before the coherent crossbar's request arbitration. Keep all project changes on a separate project branch/worktree, and place new results in previously nonexistent directories in the original project root so output-path lengths can match existing experiments.

**Tech Stack:** gem5 C++/Python, RISC-V SE, existing WSL toolchain, Python standard-library unittest; no new dependencies.

**Spec:** `docs/TIME_SLOT_PROPOSAL_REVIEW_20261015.md`, approved by the user with the requirement that prior work remain undisturbed. This plan narrows the first prototype to fail explicitly on unsupported backpressure rather than asserting a general-purpose timing-isolation implementation.

## Global Constraints

- Preserve the accepted proposal and its original negative result.
- Preserve A/(16-A) masks, frozen v3 monitor/AES binaries, seeds and 64-interval schedule.
- Do not edit old results or raw data, or overwrite the baseline gem5 executable.
- All timing-slot findings are a separate exploratory follow-up, not a replacement for original inference.
- No full A=1..8 sweep until both endpoint assessments pass and its inference is preregistered.
- User has authorized the external WSL checkout inspection, isolated build and long-running tests.

## Review Focus

- Dirty writebacks: all non-express requests, including data-bearing evictions, must obey slots and fit their reserved transport window.
- Retry callbacks: wrong-slot traffic must remain outside the stock shared request-layer waiting list.
- Downstream refusal: stop explicitly and preserve diagnostics; no claim of support for an unbounded LLC stall.
- Functional loading and coherence: preserve functional/atomic operations; report express-snoop bypasses and disallow an isolation claim if any occur in the measured window.
- Reproducibility: original binary arguments and probe-path lengths must match; changed path layout invalidates a byte-comparison claim.

## Task 1: Isolation and preservation

- [ ] Create a project worktree inside `.codex-tmp/tdma-worktree` on a new branch; this parent is already ignored. Use a separate WSL gem5 source worktree at `~/eel5764/gem5-timeslot`, based on c8222cc67a399bfc01e8658dd14b30d5bfd634f9, with its own build directory.
- [ ] Save a preservation manifest in the experiment directory, including original tracked-file hashes and existing-result inventory, before implementation. Compare it again after execution. Never repair a mismatch by overwriting the original.
- [ ] Baseline verification already run: `python3 -m unittest discover -s tests -p 'test_*.py'` through WSL: 70 tests, 0.039 s, OK. Original gem5 checkout has no changes.

Baseline SHA-256 values observed before implementation:

```text
c259c12e9cfafed8da49b5ac0e556719e72d6f700c13c208eaafc41f46c6730f  original gem5.opt
1d18d4fc006b4b0a1c6d13191018bbf698df39d3d85cf19194133b1ba100f96b  configs/run_contention.py
0722e049dcdf93baae19f6813b2b06a5301d647c177b1cc0bb4ea3946f7ec9c2  workloads/monitor_v3_l1d4k
5ef763fa8290f5b8ff026b71a883706ccf6b10151ddfc5951f24012a832f46a1  workloads/victim_l1d4k
4bdaeeca025b2282a319fe3cc7af5e8be3e2201dba9707b4dd6586a44a08f37d  aligned proposal DOCX
```

## Task 2: Scheduler and configuration, with failing tests first

**New project files:** `experiments/tdma/gem5-timeslot.patch`, `experiments/tdma/slot_schedule.hh`, `experiments/tdma/test_slot_schedule.cc`, `experiments/tdma/run_contention_tdma.py`, `experiments/tdma/test_config.py`.

**Isolated gem5 files patched:** `src/mem/XBar.py`, `src/mem/coherent_xbar.hh`, `src/mem/coherent_xbar.cc`. The patch and its base commit travel with the experiment.

- [ ] Write and run failing C++ slot-policy tests: ownership alternates, slot boundaries are exact, next eligible tick is strictly future for a missed slot, one launch per slot, and a 64-byte transfer plus header fits before the next slot. Use integer ticks, never host-wall-clock timing.
- [ ] Add disabled-by-default parameters `tdma_slot_cycles=0` and explicit per-CPU-side-port domain assignments. Validate complete two-domain coverage. Domain mapping comes from actual connected CPU/cache ports, not assumed vector ordering.
- [ ] When enabled, launch only at a slot boundary, once per slot, alternating domain 0 then 1. Use 4 cycles at the original 1 GHz crossbar clock: 4 ns per slot, 8 ns frame. Idle slots are never borrowed. This value is chosen from the existing 3 ns maximum 64-byte crossbar transport occupancy; it is not a measured security result or a completion bound.
- [ ] Reject early/wrong-slot arrivals before touching `reqLayers`. Track per-port pending retries and wake eligible ports at their domain boundary, using deterministic round-robin order within a domain. Check packet duration before admission. Stop with an explicit diagnostic if downstream rejection would enter the stock shared peer-wait state; likewise stop on unexpected request-layer contention or transport overrun. Preserve all failed-run outputs.
- [ ] Count grants per domain, withheld requests, transport violations, downstream refusals, and express-snoop bypasses. Disabled mode must use the original path without scheduling events.
- [ ] Create a separate config entry point, leaving `configs/run_contention.py` unchanged. Reuse the frozen baseline configuration with only opt-in TDMA parameters and explicit baseline project-root selection; preserve baseline workload command lines and clocks. Test disabled settings and reject invalid slot/domain settings before simulation.
- [ ] Run C++ and Python unit tests; build only the isolated executable with the unchanged requestor-partition extension. Record the exact command, source patch and executable hashes, and compiler output.

## Task 3: Structural smoke tests and disabled regression

**New files:** `experiments/tdma/test_traffic.py`, `experiments/tdma/validate.py`.

- [ ] Exercise both-domain reads, a quiet domain, writebacks and forced downstream refusal. Validate actual gem5 grants; the refusal test must fail with the intended diagnostic rather than hang or corrupt a packet. Bound every simulation with a simulated-tick limit and host timeout.
- [ ] Run the isolated executable with TDMA disabled at A=1 and A=8, both unpartitioned and partitioned, first seed only. Use root `tdma-gd0` (eight characters) and existing case names. Compare probe bytes against corresponding original results, with matching path lengths. Compare relevant simulated statistics, allowing only documented new disabled parameters/counters and host-runtime fields.
- [ ] Stop before efficacy testing if structural checks or disabled regression fail. Diagnose and log any correction before rerunning; do not alter the reference outputs.

## Task 4: Preregister and execute the endpoint pilot

**New files:** `experiments/tdma/PREREGISTRATION.md`, `experiments/tdma/run_pilot.py`, `experiments/tdma/test_runner.py`, `experiments/tdma/summarize.py`.

- [ ] Before any efficacy data, freeze slot settings, structural gates, hypotheses, seeds, run order, analysis and failure rules. Record that seed runs share one activity schedule.
- [ ] Test runner planning and refusal to overwrite existing directories. Output roots `tdma-off`, `tdma-way`, `tdma-onx` have the same eight-character length as `sweep-v3`; retain corresponding original case names and original absolute workload paths. Use an equal-length staging path if staging is necessary.
- [ ] First run six fresh processes: A in {1,8}, seed 0x5764A5E5, with unpartitioned baseline, way-only baseline, and way-plus-slot treatment. Use the original executable/config for the first two arms. Validate self-test, probe records/layout, all 64 mapping and disjoint-way snapshots, and scheduler counters. Do not infer equivalence from this one-seed pilot.
- [ ] If valid, complete the same endpoint design for seeds E6 and E7: 18 efficacy processes total. Retain all failed runs separately; no automatic tuning from observed efficacy results.
- [ ] Apply the existing max-set permutation analysis (10,000 permutations, seed 5764), Fisher combination and a separately declared Holm family across the two endpoint allocations for each arm. Report the existing hit-only 90% bootstrap interval against the existing +/-0.02 cycles/line margin, without treating that mean-only check as distributional indistinguishability. Report IPC, miss rate, AES throughput, scheduler diagnostics and losses of useful work.
- [ ] Conclude only about this workload and tested observations. A residual signal or invalid structural gate stops expansion; statistical nonsignificance alone does not authorize the full sweep. A distributional attack evaluation remains necessary before a broader indistinguishability claim.
- [ ] Recheck the preservation manifest and original executable hash; report exact commands and real output. Do not push or merge experimental code into the original study automatically.

## Review checkpoint

The user has approved the separate follow-up design and long-running isolated execution. The explicitly invoked writing-plans workflow requires review of this newly written implementation plan before implementation. Recommended execution method: native, in this session, because the scheduler, configuration and validation are tightly coupled. No subagent dispatch is needed for planning.
