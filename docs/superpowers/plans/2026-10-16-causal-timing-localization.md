# Causal Timing Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce validated per-request timing traces that locate the first stage at which the scheduled monitor's AES-active and idle timing diverge.

**Architecture:** Preserve the completed quiet control, then create a separate `gem5-causal` worktree from gem5 commit `c8222cc`. Apply the existing request-TDMA patch and add disabled-by-default, monitor-filtered trace hooks. A Python runner checks trace-off and trace-on equivalence before a strict parser matches stage timelines and reports segment effects.

**Tech Stack:** Windows PowerShell, WSL2 Ubuntu 26.04, Python 3.14, `unittest`, C++17, gem5 v25.1.0.1 classic caches, RISC-V `TimingSimpleCPU`.

**Spec:** `docs/superpowers/specs/2026-10-16-causal-timing-localization-design.md`

## Global Constraints

- Work on branch `experiment/tdma-prototype` in `.codex-tmp\tdma-worktree`.
- Create the simulator worktree only at `/home/shahriarahi/eel5764/gem5-causal`; do not modify `/home/shahriarahi/eel5764/gem5` or `gem5-timeslot`.
- Base the causal simulator on gem5 commit `c8222cc67a399bfc01e8658dd14b30d5bfd634f9` and the retained `experiments/tdma/gem5-timeslot.patch`.
- Do not install or upgrade dependencies.
- Preserve all existing binaries, results, logs, and the frozen way-partitioning study.
- Trace changes are disabled by default and may not alter simulated packet timing.
- Limit scientific runs to seed `0x5764A5E5`, A=1 and A=8, with 4-cycle request slots.
- Use new eight-character result roots so the probe-file argument length matches `tdma-onx`: `tdma-cd0` for trace-disabled and `tdma-ct0` for trace-enabled.
- Preserve failed runs and refuse any pre-existing output case.
- Use PowerShell for host commands and explicit `wsl.exe -d Ubuntu-26.04 --exec ...` calls for Linux tools.

## Review Focus

- A response retry may produce repeated send attempts; matching must retain retries while allowing exactly one successful dequeue.
- A probe timeline may cross an interval boundary; label it by CPU-delivery tick and report the crossing rather than dropping it.
- A packet may lose its virtual address or requestor identity; count and reject the case instead of silently omitting it.
- Trace-on logging may perturb host runtime but must leave probe bytes and simulated statistics unchanged.
- An address sequence may be missing, duplicated, or reordered at one stage; fail matching with the first index and stage that disagree.

---

### Task 1: Verify and checkpoint the completed quiet control

**Files:**
- Add: `experiments/quiet-control-20261016/**`

**Interfaces:**
- Consumes: the existing untracked quiet-control artifacts and raw cases under `results/updated run/tdma-np0` and `tdma-nc0`.
- Produces: one reviewed commit containing the control source, provenance, analysis, and recorded results; no raw-result edits.

- [ ] **Step 1: Re-run the focused control tests and preservation audit**

Run from the experimental worktree:

```powershell
python -B -m unittest discover -s experiments\quiet-control-20261016 -p test_control.py
python -B experiments\quiet-control-20261016\preserve.py check
```

Expected: 5 tests pass; preservation reports 6,694 protected files and only the recorded pre-existing `project explanation.md` mismatch.

- [ ] **Step 2: Re-run the project and TDMA unit suites**

```powershell
python -B -m unittest discover -s tests -p 'test_*.py'
python -B -m unittest discover -s experiments\tdma -p 'test_*.py'
```

Expected: 70 project tests and 10 TDMA tests pass.

- [ ] **Step 3: Audit the quiet artifacts before staging**

Confirm `RESULTS.md` labels all values as simulated, the analysis JSON matches its table, and no raw output path is staged.

- [ ] **Step 4: Commit the quiet control**

```powershell
git add -- experiments/quiet-control-20261016
git commit -m "Record quiet-victim negative control"
```

### Task 2: Implement strict trace parsing and request matching

**Files:**
- Create: `experiments/causal-trace-20261016/trace_analysis.py`
- Create: `experiments/causal-trace-20261016/test_trace_analysis.py`

**Interfaces:**
- Produces: `TraceEvent`, `parse_trace_line(line: str) -> TraceEvent | None`, `read_trace(path: Path) -> list[TraceEvent]`, `match_timelines(events: list[TraceEvent]) -> list[dict[str, TraceEvent | list[TraceEvent]]]`, `latency_rows(timelines: list[dict], metadata: dict) -> list[dict]`, and `summarize_segments(rows: list[dict]) -> dict`.
- Matching requires the fixed stage names from the spec and returns retry attempts as an ordered list within each timeline.

- [ ] **Step 1: Write failing parser tests**

Add tests for a valid version-1 record, a non-trace line returning `None`, malformed integers, unknown versions/stages, missing metadata, and a retry record with `outcome=blocked`.

- [ ] **Step 2: Run the parser tests and confirm the expected failure**

```powershell
python -B -m unittest discover -s experiments\causal-trace-20261016 -p test_trace_analysis.py
```

Expected: import or missing-interface failure because `trace_analysis.py` does not exist.

- [ ] **Step 3: Implement `TraceEvent`, `parse_trace_line`, and `read_trace`**

Use a frozen dataclass for an immutable parsed record. Parse decimal ticks and sizes plus hexadecimal addresses explicitly; reject missing fields with line-number context.

- [ ] **Step 4: Run the parser tests**

Expected: parser tests pass.

- [ ] **Step 5: Write failing timeline-matching tests**

Cover one complete timeline, multiple retries followed by one successful dequeue, address reorder, missing stage, duplicate terminal event, negative stage duration, and a request that crosses an interval boundary.

- [ ] **Step 6: Run matching tests and confirm they fail because the functions are absent**

- [ ] **Step 7: Implement `match_timelines`, `latency_rows`, and `summarize_segments`**

Match ordered address occurrences. Assign labels by `cpu_delivery` tick. Report per-segment and cumulative interval means, all-interval active-minus-idle effects, the interval-0-separated sensitivity result, retry counts, and boundary-crossing counts.

- [ ] **Step 8: Run the focused tests and commit**

```powershell
python -B -m unittest discover -s experiments\causal-trace-20261016 -p test_trace_analysis.py
git add -- experiments/causal-trace-20261016/trace_analysis.py experiments/causal-trace-20261016/test_trace_analysis.py
git commit -m "Add strict causal trace analysis"
```

### Task 3: Add causal configuration and exact gem5 patch generation

**Files:**
- Create: `experiments/causal-trace-20261016/run_contention_causal.py`
- Create: `experiments/causal-trace-20261016/prepare_gem5.py`
- Create: `experiments/causal-trace-20261016/causal_trace_filter.hh`
- Create: `experiments/causal-trace-20261016/test_causal_trace_filter.cc`
- Create: `experiments/causal-trace-20261016/test_config.py`
- Create during preparation: `experiments/causal-trace-20261016/gem5-causal.patch`
- Modify in `/home/shahriarahi/eel5764/gem5-causal`: `src/mem/SConscript`, `src/mem/XBar.py`, `src/mem/coherent_xbar.hh`, `src/mem/coherent_xbar.cc`, `src/mem/cache/base.cc`, `src/mem/cache/cache.cc`, `src/mem/packet_queue.cc`, `src/cpu/simple/timing.cc`
- Create in the isolated source: `src/mem/causal_trace.hh`, `src/mem/causal_trace.cc`, `src/mem/tdma_schedule.hh`

**Interfaces:**
- Consumes: baseline `configs/run_contention.py`, monitor symbol metadata, and the existing TDMA adapter behavior.
- Produces: `validate_trace_config(enabled: bool, requestor: str, base: int, size: int, llc: str, queue: str) -> None`; gem5 parameters `causal_trace_requestor`, `causal_trace_vaddr_base`, `causal_trace_vaddr_size`, `causal_trace_llc_name`, and `causal_trace_queue_name`; C++ helpers `configureCausalTrace(...)`, `causalTraceEligible(const PacketPtr)`, and `emitCausalTrace(...)`.

- [ ] **Step 1: Write failing Python configuration tests**

Test disabled defaults, complete enabled configuration, zero-size range, missing requestor/component names, overflow of `base + size`, and preservation of the two-domain TDMA mapping.

- [ ] **Step 2: Run the Python tests and observe the missing-module failure**

- [ ] **Step 3: Implement the causal configuration adapter**

Reuse the existing baseline through `runpy`; configure the already connected `system.l2bus` before instantiation. Resolve the monitor requestor by name in C++, and write an exclusive `causal_config.json` in the output directory.

- [ ] **Step 4: Run the Python tests until green**

- [ ] **Step 5: Write the standalone C++ filter tests before the filter**

Test requestor equality, inclusive base/exclusive end, overflow rejection, disabled behavior, and component-name equality. Compile must fail because the header is absent.

- [ ] **Step 6: Implement the minimal pure C++ filter and run its tests**

```powershell
wsl.exe -d Ubuntu-26.04 --cd '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/tdma-worktree' --exec g++ -std=c++17 -Wall -Wextra -Werror experiments/causal-trace-20261016/test_causal_trace_filter.cc -o /tmp/causal-trace-filter-test
wsl.exe -d Ubuntu-26.04 --exec /tmp/causal-trace-filter-test
```

Expected: `PASS causal trace filtering`.

- [ ] **Step 7: Create the isolated gem5 worktree**

Verify `/home/shahriarahi/eel5764/gem5-causal` does not exist, then create it detached at `c8222cc`. Apply the retained TDMA patch before causal edits.

- [ ] **Step 8: Write and run a failing static hook test in `test_config.py`**

The test checks that preparation output contains all eight declared stage names and all required source paths. It fails before causal patch generation.

- [ ] **Step 9: Implement exact checked source edits in `prepare_gem5.py`**

Emit only eligible monitor probe packets. Add `llc_response_ready` at both LLC hit and miss response-scheduling sites; add queue events around `PacketQueue::schedSendTiming` and `sendDeferredPacket`; add crossbar and CPU-delivery events only after successful acceptance. Preserve request retries as repeated attempts with explicit outcomes.

- [ ] **Step 10: Generate the retained patch, run all Task 3 tests, and commit**

```powershell
python -B -m unittest discover -s experiments\causal-trace-20261016 -p test_config.py
wsl.exe -d Ubuntu-26.04 --exec /tmp/causal-trace-filter-test
git add -- experiments/causal-trace-20261016
git commit -m "Add filtered gem5 causal trace instrumentation"
```

### Task 4: Add bounded execution and perturbation validation

**Files:**
- Create: `experiments/causal-trace-20261016/run_cases.py`
- Create: `experiments/causal-trace-20261016/validate_trace.py`
- Create: `experiments/causal-trace-20261016/preserve.py`
- Create before execution: `experiments/causal-trace-20261016/preservation-before.json`
- Create: `experiments/causal-trace-20261016/test_runner.py`

**Interfaces:**
- Consumes: the causal executable, stored `tdma-onx` commands, `trace_analysis.py`, and existing TDMA validation helpers.
- Produces: `build_command(reference: dict, output: Path, trace: bool) -> list[str]`, `validate_equivalence(reference: Path, candidate: Path) -> dict`, `validate_trace_case(case: Path) -> dict`, read-only `snapshot(root: Path) -> dict[str, str]`/`check(snapshot_path: Path) -> None`, and two exclusive result roots `tdma-cd0`/`tdma-ct0`.

- [ ] **Step 1: Write failing runner tests**

Test eight-character roots, refusal of existing roots/cases, executable and adapter replacement, exact trace debug arguments, per-case timeout, failure preservation, and identical probe argument length.

- [ ] **Step 2: Run the tests and confirm missing interfaces fail**

- [ ] **Step 3: Implement command construction and exclusive case creation**

Use fresh-process execution, a 240-second timeout per simulation, an exclusive staging directory, and atomic rename on success or `.failed.<suffix>` preservation on error.

- [ ] **Step 4: Write failing validation tests**

Test probe mismatch, simulated-stat mismatch, trace-off records unexpectedly present, missing stage, reordered address, duplicate delivery, and trace-on/off equivalence.

- [ ] **Step 5: Implement equivalence and trace validation**

Reuse the existing TDMA scheduler/mapping/way gates. Exclude only declared trace counters and host-runtime fields from statistical comparison.

- [ ] **Step 6: Write failing preservation tests, then implement the snapshot**

Test exclusive snapshot creation, detection of a changed protected file, exclusion of new causal outputs, and clear reporting of any pre-existing frozen-manifest mismatch. Generate `preservation-before.json` only after the tests pass and before creating either result root.

- [ ] **Step 7: Run the focused tests and commit**

```powershell
python -B -m unittest discover -s experiments\causal-trace-20261016 -p 'test_*.py'
git add -- experiments/causal-trace-20261016/run_cases.py experiments/causal-trace-20261016/validate_trace.py experiments/causal-trace-20261016/preserve.py experiments/causal-trace-20261016/preservation-before.json experiments/causal-trace-20261016/test_runner.py
git commit -m "Add bounded causal trace runner and gates"
```

### Task 5: Build and structurally validate the isolated simulator

**Files:**
- Create: `experiments/causal-trace-20261016/test_trace_traffic.py`
- Create: `experiments/causal-trace-20261016/run_structural.py`
- Create: `experiments/causal-trace-20261016/test_structural.py`
- Create: `experiments/causal-trace-20261016/build_manifest.json`
- Create: `experiments/causal-trace-20261016/build-logs/causal-build-01.log`

**Interfaces:**
- Consumes: patched `/home/shahriarahi/eel5764/gem5-causal` and the unchanged `gem5_ext` extension path.
- Produces: a causal `build/RISCV/gem5.opt`, executable/source hashes, and structural evidence for enabled and disabled tracing.

- [ ] **Step 1: Write the structural harness and validator test first**

The enabled case must exercise one filtered read through all eight stages. The disabled case must contain no `CAUSAL_TRACE` record. Add a malformed/incomplete trace fixture that the validator rejects.

- [ ] **Step 2: Run the structural test against the old executable and confirm the expected missing-trace failure**

- [ ] **Step 3: Build the isolated executable**

```powershell
wsl.exe -d Ubuntu-26.04 --exec scons -C /home/shahriarahi/eel5764/gem5-causal build/RISCV/gem5.opt -j14 EXTRAS=/home/shahriarahi/eel5764/gem5_ext
```

Capture complete output in the new build log and record commit, patch, and executable hashes.

- [ ] **Step 4: Run enabled and disabled structural cases**

Require the eight-stage enabled timeline, no disabled records, zero scheduler violations, and no simulated-time change caused by tracing.

- [ ] **Step 5: Run all unit and regression suites**

```powershell
python -B -m unittest discover -s experiments\causal-trace-20261016 -p 'test_*.py'
python -B -m unittest discover -s experiments\tdma -p 'test_*.py'
python -B -m unittest discover -s tests -p 'test_*.py'
```

- [ ] **Step 6: Commit build and structural evidence**

```powershell
git add -- experiments/causal-trace-20261016
git commit -m "Validate causal trace hooks in isolated gem5"
```

### Task 6: Run endpoint guards, analyze traces, and report localization

**Files:**
- Create: `experiments/causal-trace-20261016/PREREGISTRATION.md`
- Create: `experiments/causal-trace-20261016/analysis/A1.json`
- Create: `experiments/causal-trace-20261016/analysis/A8.json`
- Create: `experiments/causal-trace-20261016/analysis/summary.json`
- Create: `experiments/causal-trace-20261016/RESULTS.md`
- Create: `experiments/causal-trace-20261016/progress.md`

**Interfaces:**
- Consumes: validated causal executable, stored scheduled reference cases, and Tasks 2-5 interfaces.
- Produces: two trace-disabled guards, two trace-enabled cases, validated stage effects, and a bounded causal-localization report.

- [ ] **Step 1: Freeze execution order and reporting rules before scientific runs**

Record A=1 then A=8 for trace-disabled, followed by A=1 then A=8 for trace-enabled. Record the all-interval and interval-0-separated reports, matching failure rules, and claim limits.

- [ ] **Step 2: Run the two trace-disabled guards**

Require byte-identical probes and matching simulated statistics against the stored `tdma-onx` first-seed cases before continuing.

- [ ] **Step 3: Run the two trace-enabled cases**

Require trace-on/off equivalence, valid TDMA counters, and complete matched timelines. Preserve and stop on the first invalid case.

- [ ] **Step 4: Analyze both endpoints**

Write per-stage segment and cumulative active-minus-idle effects, retry counts, boundary crossings, interval-0 sensitivity, and the earliest resolvable checkpoint. Mark simultaneous or insufficiently resolved stages as unresolved.

- [ ] **Step 5: Verify preservation and the full test suite**

Run the quiet-control preservation check, causal tests, TDMA tests, project tests, and a read-only comparison of protected original files.

- [ ] **Step 6: Write `RESULTS.md` with measured/simulated labels and limits**

Report the actual executed commands and outputs. Do not infer response-path causality unless the first divergence is resolved there; do not propose a defense as tested.

- [ ] **Step 7: Commit the completed diagnostic**

```powershell
git add -- experiments/causal-trace-20261016
git commit -m "Report causal timing localization results"
```

- [ ] **Step 8: Final verification**

Confirm the branch diff contains only the quiet control, causal experiment, design, and plan; confirm both original gem5 worktrees and frozen outputs are unchanged; report anything that remains unverified.
