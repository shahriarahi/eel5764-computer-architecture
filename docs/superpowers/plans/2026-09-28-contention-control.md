# Simulated Cache-Contention Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the unpartitioned simulated monitor/AES control and decide reproducibly whether public AES activity is visible above a shuffled-label null.

**Architecture:** Two finite, `rdcycle`-synchronized RISC-V workloads share the established two-core gem5 hierarchy. The monitor buffers per-set probe latencies until measurement ends; a separate analysis module validates the complete log, aggregates by interval, and applies the predeclared SNR/permutation rule.

**Tech Stack:** Freestanding C11/RISC-V, gem5 v25.1.0.1 Python configuration, Python 3 standard library, `unittest`, POSIX shell under WSL2.

**Spec:** `docs/superpowers/specs/2026-09-28-contention-control-design.md`

## Global Constraints

- Run only in gem5 RISC-V SE mode; never target or measure physical hardware.
- Detect only public active/idle labels; implement no AES key inference.
- Use conventional four 1 KiB T-tables with no artificial private-cache eviction.
- Preserve all existing isolation workloads, outputs, and report claims.
- Stop after the unpartitioned analysis regardless of PASS or FAIL.
- Do not replace an existing `results/contention/UNPARTITIONED` directory.
- Use Python standard-library tests and the already-installed toolchains only.

## Review Focus

- A monitor record outside its interval must fail instead of being silently reassigned.
- Duplicate or missing interval/set pairs must fail before SNR computation.
- An imbalanced or mismatched public label schedule must fail validation.
- Zero within-group pooled variance must report undefined SNR explicitly.
- Logging after the measurement boundary must not enter the first stats block used for IPC or miss-rate statistics; gem5's preserved automatic final block is ignored.

---

### Task 1: Statistical Contract

**Files:**
- Create: `tests/test_analyze_contention.py`
- Create: `analysis/analyze_contention.py`

**Interfaces:**
- Produces: `snr(active: list[float], idle: list[float]) -> float`; `permutation_test(samples: list[float], labels: list[int], permutations: int = 10000, seed: int = 5764) -> dict[str, float]`; validated log parsing and a CLI that writes `analysis.json`.

- [ ] Write unit tests for the predeclared SNR value, reproducible permutation output, complete 64-by-256 log parsing, duplicate/missing records, timestamp bounds, label mismatch, and zero pooled variance.
- [ ] Run `python -m unittest tests.test_analyze_contention -v` and confirm failure because `analysis.analyze_contention` does not exist.
- [ ] Implement only the tested parsing, statistics, gem5-stat extraction, JSON output, and CLI behavior.
- [ ] Re-run the focused test and the full `python -m unittest discover -s tests -v` suite.

### Task 2: AES and Public Schedule

**Files:**
- Create: `tests/test_aes_ttable.c`
- Create: `tests/test_contention_schedule.c`
- Create: `workloads/aes_ttable.h`
- Create: `workloads/aes_ttable.c`
- Create: `workloads/contention_common.h`

**Interfaces:**
- Produces: `aes_ttable_init(void)`, `aes128_expand_key(const uint8_t key[16], uint32_t round_keys[44])`, `aes128_encrypt_block(const uint8_t in[16], uint8_t out[16], const uint32_t round_keys[44])`, and shared timing/label constants.

- [ ] Write portable C tests for the public AES-128 known-answer vector and the exact 64-label 32/32 schedule.
- [ ] Compile the tests and confirm failure because the AES and schedule headers are absent.
- [ ] Implement the minimal portable AES T-table component and schedule constants.
- [ ] Compile with warnings as errors and run both tests successfully.

### Task 3: Freestanding Workloads

**Files:**
- Create: `workloads/victim.c`
- Create: `workloads/monitor.c`
- Modify: `workloads/build.sh`
- Modify: `workloads/README.md`

**Interfaces:**
- Consumes: Task 2 AES API and shared schedule.
- Produces: freestanding `workloads/victim` and `workloads/monitor`; monitor CSV records prefixed `probe,`; victim header containing `aes_self_test=PASS`, public key, plaintext seed, and label schedule.

- [ ] Add source-level/build smoke assertions for required log fields and binary properties, then observe them fail before the new workloads exist.
- [ ] Implement `victim.c` with deterministic inputs and exact active/idle scheduling.
- [ ] Implement `monitor.c` with its own 16-way-by-256-set dependent probe chains, deadline checks, in-memory records, and post-measurement buffered output.
- [ ] Extend the existing build script and README without changing the three existing workloads' behavior.
- [ ] Build under WSL2 and verify ELF target, no undefined symbols, no RISC-V vector instructions, and no `gp`-relative references.

### Task 4: Contention Simulation Path

**Files:**
- Create: `configs/run_contention.py`
- Create: `scripts/run_contention_control.sh`

**Interfaces:**
- Consumes: `workloads/monitor`, `workloads/victim`, and the existing `RequestorPartitionManager` extension.
- Produces: `results/contention/UNPARTITIONED/{stats.txt,run_meta.json,config.ini,config.json,simout.txt,simerr.txt,cmd.txt,workload_sha256.txt}` with a first measurement-only stats block and a preserved automatic final block.

- [ ] Add static/smoke checks for split validation, workload ordering, phase lengths, output-directory refusal, and required output markers; observe failure with the files absent.
- [ ] Implement the dedicated configuration using the existing hierarchy and partition mapping.
- [ ] Implement a control runner that refuses to overwrite prior output and verifies every expected artifact and marker.
- [ ] Run syntax/static checks before launching gem5.

### Task 5: Unpartitioned Validation

**Files:**
- Create at runtime: `results/contention/UNPARTITIONED/` and its files.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: `results/contention/UNPARTITIONED/analysis.json` and a PASS or FAIL scientific decision.

- [ ] Run `bash scripts/run_contention_control.sh` in WSL2 and capture its real output.
- [ ] Run `python3 analysis/analyze_contention.py --results results/contention/UNPARTITIONED` and capture observed SNR, null threshold, p-value, sample counts, IPC, and miss rates.
- [ ] Run the full unit suite and workload binary checks again.
- [ ] Report files changed, exact verification commands, real outputs, and anything unverified. Do not begin the partition sweep.

