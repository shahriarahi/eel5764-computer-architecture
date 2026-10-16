# Contention Sweep and Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the eight missing partitioned monitor/AES runs with the validated 4 KiB method, analyze all nine configurations, generate figures, and write the evidence-backed final report.

**Architecture:** Extend the existing safe control runner to accept one validated split without replacing results, then provide an all-splits wrapper. Extend the existing per-run analyzer with direct way-occupancy evidence and add a separate summarizer for CSV, collapse-point selection, and plots.

**Tech Stack:** gem5 25.1.0.1, RISC-V SE workloads, Bash, Python 3 standard library, matplotlib 3.10.7.

**Spec:** `docs/superpowers/specs/2026-09-28-contention-l1d4k-redesign.md`

## Global Constraints

- Preserve all existing raw outputs and failed attempts.
- Use the frozen 4 KiB L1D, two-million-cycle interval, 10,000-shuffle, seed-5764 method.
- Run every configuration as a fresh gem5 process.
- Make no AES key inference and no claim that way partitioning isolates shared queues or interconnects.
- Every quantitative report statement must trace to `analysis.json`, `stats.txt`, or `simout.txt`.

## Review Focus

- Invalid or duplicate split names must fail before gem5 starts.
- Existing result directories must never be replaced.
- A partitioned result must fail analysis if any observed block occupies a disallowed way.
- Summary generation must fail on missing or mismatched analyses.
- Collapse-point reporting must select only the first tested partition whose corrected decision is `FAIL`.

---

### Task 1: Safe partitioned runner

**Files:**
- Modify: `scripts/run_contention_control.sh`
- Create: `scripts/run_contention_sweep.sh`
- Modify: `analysis/analyze_contention.py`
- Modify: `tests/test_analyze_contention.py`

**Interfaces:**
- Consumes: `run_contention.py --split`, existing 4 KiB workload profile.
- Produces: one immutable `results/contention-l1d4k/<split>/` directory and partition-evidence fields in `analysis.json`.

- [x] Write failing tests for permitted-way occupancy and violations.
- [x] Run the targeted tests and observe the missing interface failure.
- [x] Implement split validation, non-overwriting execution, and direct partition-evidence parsing.
- [x] Run the full Python suite and Bash syntax checks.

### Task 2: Sweep summary and figures

**Files:**
- Create: `analysis/summarize_contention.py`
- Create: `tests/test_summarize_contention.py`

**Interfaces:**
- Consumes: nine validated `analysis.json` files.
- Produces: `results/contention-l1d4k/summary.csv`, `snr_vs_split.pdf`, and `contention_tradeoff.pdf`.

- [x] Write failing tests for ordering, missing results, and first-null allocation.
- [x] Run the targeted tests and observe import/interface failures.
- [x] Implement strict summary parsing, CSV output, and publication-labelled plots.
- [x] Run the full Python suite; the plot smoke test will use the completed measured sweep in Task 3.

### Task 3: Execute and report

**Files:**
- Modify: `REPORT.md`
- Modify: `RUNBOOK.md`

**Interfaces:**
- Consumes: all nine raw result directories, analyses, summary CSV, and figures.
- Produces: final measured report and reproducible commands.

- [x] Run the eight missing splits separately and retain real outputs.
- [x] Analyze every new split with the frozen max-set test.
- [x] Generate and inspect the final CSV and figures.
- [x] Update the report with measured collapse point, IPC/miss-rate costs, evidence paths, and limitations.
- [x] Run final tests, artifact validation, and report consistency checks.

