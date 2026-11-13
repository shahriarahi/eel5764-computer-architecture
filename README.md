# Final_run: the whole EEL5764 Group 18 project, first step to last

**Branch `Final_run`.** One checkout with everything needed to reproduce the
project, from the first partition sweep (September 27) to the AES leakage
follow-up (finished November 12, 2026). Every result is a **gem5 simulation**
result (v25.1.0.1, RISC-V, syscall-emulation mode), not a hardware measurement.

This README explains, in order, **what we ran, why, how, and where the output
is**, so any group member can repeat any step. For deeper detail, each step
points to the document that recorded it at the time.

---

## 0. What is on this branch

`Final_run` = `main` (paper v1/v2, main pipeline, main results) **merged with**
`experiment/aes-leakage` (which already contains `experiment/tdma-prototype`:
time slots, quiet control, causal trace, response-queue defense, and the AES
leakage study), plus files that were only on the PC until now:

| Added here | What it is |
|---|---|
| `Group18_EEL5764_Final_Paper_v3.docx` / `.pdf` | Latest paper draft (includes the AES leakage extension). See §6 for one correction it still needs. |
| `CLAUDE_CODE_PROMPT.md` | The task specification for the AES leakage study (Nov 2026). |
| `FABLE_POSTDOC_PROMPT.md` | The prompt for the design review that produced the Phase E plan. |
| `postdoc-review/` | `POSTDOC_REVIEW.md` (review memo), `EXECUTION_PLAN.md` (the step-by-step Phase E plan we executed), `exec/LOG.md` (full command output of the execution), `exec/FINAL_REPORT.md` (evidence table), `reference/` (code the plan copied into the experiment), `verify/` (the reviewer's check scripts and their output). |

Unlike the older `REPRODUCE.md` (which used two folders side by side), on this
branch **everything is in one checkout**: `experiments/` sits at the repository
root next to `configs/`, `workloads/`, `scripts/` and `analysis/`.

Not in the repository: the gem5 source and builds (rebuild them, §2), and the
causal-trace logs `results/updated run/tdma-ct1`, `tdma-ct2`, `tdma-ct3`
(67–489 MB; one file exceeds GitHub's 100 MB limit). Their summaries are in
`experiments/causal-trace-20261016/`; regenerate them with `run_cases.py --trace`.

---

## 1. How we worked (the rules behind every step)

These rules explain why the folders look the way they do. Please keep them if
you re-run anything.

1. **Simulator only, public data.** The AES key is a fixed public test constant
   compiled into the workload; plaintexts are deterministic. The monitor only
   times its own memory. No hardware claims are made anywhere.
2. **Preregister, then run.** Every experiment's hypotheses, sample sizes and
   decision rule were written down and committed *before* the data
   (`PREREGISTRATION_*.md` files). Changes after seeing data are logged as
   numbered **deviations** (D0, D1, …) and labelled post-hoc.
3. **Phases with checkpoints.** Each study was split into phases (A, B, C, …).
   A phase only started after the previous phase's gate passed and the group
   said "go". Failed attempts are **kept** as evidence, not deleted.
4. **Never overwrite a result.** Every runner refuses to write into an existing
   run directory. A re-run always gets a **new** name.
5. **Byte-identical guards.** gem5 is deterministic. Before trusting any newly
   patched gem5 build, we re-ran a stored run with the new feature switched off
   and required the output (`probes.bin`) to match **byte for byte**.
6. **Old code stays frozen.** New behaviour is opt-in (new flags, new files).
   Each experiment folder has a `preserve.py` that hashes its files to prove
   nothing outside it changed.
7. **Tooling.** All gem5 work ran in WSL2 `Ubuntu-26.04` on Windows 11. The
   code, analyses and documents were developed with AI coding assistants
   (Claude Code and Codex) under these rules. The final Phase E (§5, Stage 10)
   was executed by a Claude Sonnet 5.5 session (extra-high effort) that
   followed `postdoc-review/EXECUTION_PLAN.md` step by step. Its complete log is
   `postdoc-review/exec/LOG.md`.

---

## 2. One-time setup

### 2.1 Machine and packages

Reference machine: Windows 11, WSL2 `Ubuntu-26.04`, 20 threads, 15 GiB RAM,
GCC 15.2, Python 3.14. Any recent x86-64 Linux should work.

```bash
sudo apt-get update
sudo apt-get install -y scons python3-dev m4 zlib1g-dev libprotobuf-dev \
  protobuf-compiler libgoogle-perftools-dev libboost-all-dev pkg-config \
  libhdf5-serial-dev libpng-dev libelf-dev python3-numpy python3-matplotlib \
  python3-scipy gcc-riscv64-linux-gnu qemu-user
```

`gcc-riscv64-linux-gnu` and `qemu-user` are only needed to **rebuild**
workloads and for some AES tests (those tests skip with a message if a tool is
missing). All workload binaries are committed, so you can simulate without them.

### 2.2 Clone the branch

```bash
git clone --branch Final_run https://github.com/shahriarahi/eel5764-computer-architecture.git
cd eel5764-computer-architecture
R=$(pwd)          # every command below assumes $R = the repository root
```

Clone onto the Linux filesystem (e.g. `~/`) if you can. It is much faster than
`/mnt/c/...`, and OneDrive sync can interfere with multi-GB gem5 output.

### 2.3 Check the clone: run every test suite (about 1 minute, no gem5)

```bash
export PYTHONDONTWRITEBYTECODE=1
cd "$R" && python3 -B -m unittest discover -s tests -t .                       # 70 tests
for d in tdma quiet-control-20261016 causal-trace-20261016 respq-defense-20261018; do
  (cd "$R/experiments/$d" && python3 -B -m unittest discover -p 'test_*.py')  # 10, 5, 64, 13 tests
done
cd "$R/experiments/aes-leakage" && python3 -B -m unittest discover -s tests -t .  # 173 tests
```

All 335 tests passed on this branch on 2026-11-13.

### 2.4 Build gem5 (one unmodified tree plus one patched tree per defense)

All trees are gem5 **v25.1.0.1, commit `c8222cc67a399bfc01e8658dd14b30d5bfd634f9`**,
and the paths below are hard-coded in the runners, so keep them exactly.
Expect the harmless warning "GCC 15.2.0 is not officially supported". Each
build takes about 11–13 min at `-j14`. Do not go above `-j14` with 15 GiB of RAM.

```bash
mkdir -p ~/eel5764 && cd ~/eel5764
git clone --branch v25.1.0.1 https://github.com/gem5/gem5.git gem5
git -C gem5 rev-parse HEAD        # must print c8222cc67a39...

# the partition-manager extension (directory name must stay "gem5_ext")
ln -sfn "$R/gem5_ext" ~/eel5764/gem5_ext
# the AES study's copy of the extension, which adds victim-table tracing
mkdir -p ~/eel5764/leak-ext
ln -sfn "$R/experiments/aes-leakage/gem5_ext" ~/eel5764/leak-ext/gem5_ext
```

| Tree | Used by | How to create it (from `~/eel5764`) | `EXTRAS=` |
|---|---|---|---|
| `gem5` | Stages 1–4 | the clone above, unmodified | `~/eel5764/gem5_ext` |
| `gem5-timeslot` | Stage 5 (time slots), Stage 6 | `git -C gem5 worktree add --detach ../gem5-timeslot c8222cc` then `git apply $R/experiments/tdma/gem5-timeslot.patch` | `~/eel5764/gem5_ext` |
| `gem5-causal` | Stage 7 (causal trace) | same, with `experiments/causal-trace-20261016/gem5-causal.patch` | `~/eel5764/gem5_ext` |
| `gem5-respq` | Stage 8 (response-queue defense) | same, with `experiments/respq-defense-20261018/gem5-respq.patch` | `~/eel5764/gem5_ext` |
| `gem5-leak` | Stage 10, Phases B–E2 | `git -C gem5 worktree add ../gem5-leak c8222cc` (no patch) | `~/eel5764/leak-ext/gem5_ext` |
| `gem5-leak-def` | Stage 10, Phase E3 | `git -C gem5 worktree add ../gem5-leak-def c8222cc` then `git apply $R/experiments/respq-defense-20261018/gem5-respq.patch` (expect 15 changed files) | `~/eel5764/leak-ext/gem5_ext` |

Each later patch already contains the earlier ones (`gem5-respq.patch`
includes the time slots). Build each tree from inside it:

```bash
cd ~/eel5764/<tree> && scons build/RISCV/gem5.opt -j14 EXTRAS=<EXTRAS from the table>
```

Build `gem5.opt`, not `gem5.fast`: the AES runs use `--debug-flags=VictimTable`.
Our executable SHA-256 prefixes were `c259c12e` (gem5), `5a540aed` (timeslot),
`2428f123` (causal) and `66c30701` (respq). A different compiler gives a
different hash, so compare **outputs**, not executables.

---

## 3. The project in one table

| # | Stage (date) | Question | Answer (simulated) | Results |
|---|---|---|---|---|
| 1 | Capacity/isolation sweep (Sep 27) | Does way partitioning isolate LLC capacity? | Yes: all 8 splits keep each core in its own ways | `results/<split>/`, `REPORT.md` |
| 2 | First AES contention sweeps (Sep 28–Oct 1) | Can a monitor see AES activity across partitions? | First answer ("hidden at 1/15") was **wrong** and is withdrawn: the monitor evicted its own lines | `REPORT_REPEATED_20261001.md` |
| 3 | Record-free monitor v2/v3 sweep (Oct 11–12) | Same question, corrected monitor | **All 8 allocations (1/15–8/8) still leak**; 100% of signal kept at 1/15, 70–85% elsewhere; cost ≤ 0.03% | `results/updated run/sweep-v3/` (**primary result**) |
| 4 | Mechanism study (Oct 14) | Where does the leak go? | Through the shared L1→LLC crossbar request layer; a near-ideal crossbar removes 100% (1/15) / 88% (8/8). Outcome `partial` | `results/updated run/mech-summary/` |
| 5 | Request time slots (Oct 15) | Do fixed request slots close it? | Substantially attenuated, **not** closed | `experiments/tdma/RESULTS.md` |
| 6 | Quiet-victim control (Oct 16) | What does "no AES at all" look like? | Reference for byte-identity tests | `experiments/quiet-control-20261016/RESULTS.md` |
| 7 | Causal trace (Oct 16–18) | What exactly leaks past the slots? | A 1-tick same-tick slip in the **shared LLC response queue**, amplified to whole slots | `experiments/causal-trace-20261016/RESULTS.md` |
| 8 | Per-domain response queues (Oct 18) | Does splitting that queue close the channel? | **Yes**: monitor output byte-identical with AES vs quiet victim, 24/24 sweep cases; ~6% AES cost | `experiments/respq-defense-20261018/RESULTS.md` |
| 9 | Paper v2 (Oct 18) | — | `Group18_EEL5764_Final_Paper_v2.docx` | `scripts/build_final_paper_v2.py` |
| 10 | AES leakage attribution (Nov 12) | **What** does the leak encode (plaintext? plaintext⊕key?) and does each defense remove it? | See §5 Stage 10 | `experiments/aes-leakage/runs/`, `postdoc-review/exec/FINAL_REPORT.md` |

---

## 4. Re-analysis without simulating (minutes)

Every stored raw run is in the repository, so all statistics can be recomputed
without gem5. Summarizers **write into the folder they read**, so always work
on a copy:

```bash
cd "$R"
cp -r "results/updated run/sweep-v3" /tmp/sweep-v3-copy
python3 analysis/summarize_sweep_v3.py --results-root /tmp/sweep-v3-copy   # Stage 3 decision table
```

For the AES study, each run has `*.analysis.md`, `*.diff-*.md`, `*.effect.md`
and `*.count.md` next to it in `experiments/aes-leakage/runs/`. The commands
that produce them are in §5 Stage 10.

---

## 5. Re-simulating, stage by stage

General rules for every stage:

* Run from `$R` inside WSL/Linux. Use **new** output names; runners refuse
  existing ones.
* Every gem5 command needs `-r -e`, or `simout.txt` is not written and the
  analysis fails.
* **Output-path length matters.** The monitor receives its output path as an
  argument, which shifts its stack layout. To reproduce a stored run byte for
  byte, the new output path must be the **same length** as the stored one. This
  is why the result roots have 8-character names (`tdma-rsa`, …). Replace a
  name with another of equal length.

### Stage 1: capacity/isolation sweep (`RUNBOOK.md` §7–8)

```bash
bash scripts/run_sweep.sh            # 9 splits, benign kernels (randacc + stream)
python3 analysis/analyze.py --require-all
```

### Stages 2–3: AES contention sweeps (`RUNBOOK.md` §9–10C)

Stage 2 is history; its scripts are kept for the record (`RUNBOOK.md` §9–10B).
The **final** sweep (50 gem5 processes, about 45 min):

```bash
sh workloads/build.sh      # optional: rebuilds the binaries; reproduces the committed hashes
python3 scripts/run_repeated_contention_sweep_v3.py --results-root "results/updated run/sweep-v3-repro"
python3 analysis/summarize_sweep_v3.py --results-root "results/updated run/sweep-v3-repro"
```

Decision rule (`PREREGISTRATION_V2_20261011.md`): max-set SNR and hit-only mean,
Fisher across 3 seeds, Holm over 16 tests, self-eviction gate ≤ 1 point.
Supporting runs (v2 sweep, D2 rerun, post-hoc) are listed in `RUNBOOK.md` §10C.

### Stage 4: mechanism study (`PREREGISTRATION_MECHANISM_20261014.md`, report §13)

```bash
python3 scripts/run_mechanism.py --list-plan     # show the runs first
python3 scripts/run_mechanism.py
```

### Stages 5–8: closing the channel (tree: see §2.4)

Pass `--baseline-root "$R"` (the absolute repository root). Before a re-run,
change the root-name constants to **new 8-character names**:
`DISABLED_ROOT`/`ENABLED_ROOT` in `causal-trace-20261016/run_cases.py`;
`ARMS` in `respq-defense-20261018/run_respq.py`; `AES_ROOT`/`QUIET_ROOT` in
`run_sweep.py` and `VIEW_ROOT` in `summarize_sweep.py`. Also add the new names
to that folder's `preserve.py` exclusions. Output JSON files are opened
exclusively, so give every `--out` a new path.

```bash
E="$R/experiments"
# Stage 5: request time slots (gem5-timeslot). Run each phase only after the previous gate passes.
python3 -B $E/tdma/run_pilot.py --baseline-root "$R" --phase guard
python3 -B $E/tdma/run_pilot.py --baseline-root "$R" --phase pilot
python3 -B $E/tdma/run_pilot.py --baseline-root "$R" --phase remaining
# Stage 6: quiet-victim control
python3 -B $E/quiet-control-20261016/run_control.py --baseline-root "$R" --phase replay
python3 -B $E/quiet-control-20261016/run_control.py --baseline-root "$R" --phase quiet
# Stage 7: causal trace (gem5-causal); add --trace for the full logs (hundreds of MB)
python3 -B $E/causal-trace-20261016/run_cases.py --baseline-root "$R"
# Stage 8: response-queue defense (gem5-respq): endpoints (~13 min), then the sweep (48 runs, ~13 min)
python3 -B $E/respq-defense-20261018/run_respq.py --baseline-root "$R"
python3 -B $E/respq-defense-20261018/compare_arms.py --baseline-root "$R" --out <new>.json
python3 -B $E/respq-defense-20261018/run_sweep.py --baseline-root "$R" --jobs 6
python3 -B $E/respq-defense-20261018/summarize_sweep.py --baseline-root "$R" --out <new>.json
```

Success criterion for Stage 8: the monitor's `probes.bin` is **byte-identical**
between the AES victim and the quiet victim (exact, so no p-values are needed).
The proposal's frozen decision code was also run unchanged on the defended
sweep: every allocation is indistinguishable.

### Stage 9: rebuild paper v2 (optional)

The v2 builder reads `.codex-tmp/tdma-worktree/experiments` (from the old
two-folder layout). On this branch, point that path at the repository itself,
then build. The builder refuses to overwrite, so move the old file first:

```bash
mkdir -p .codex-tmp && ln -sfn .. .codex-tmp/tdma-worktree
mv Group18_EEL5764_Final_Paper_v2.docx Group18_EEL5764_Final_Paper_v2.old.docx
python3 -B scripts/build_final_paper_v2.py
python3 scripts/plot_defense_figure.py     # figures (needs matplotlib)
```

### Stage 10: AES leakage attribution (Nov 2026)

**Question.** Stages 3–8 showed *that* AES activity is visible. This study asks
*what* the visible signal encodes, using the **known public key**: does it
carry the plaintext only, the plaintext XOR key (the AES round-1 table index),
or nothing, and does each defense remove it? This goes **beyond the accepted
proposal**, which the paper says explicitly. No key guessing or key ranking is
done.

**Design in one paragraph.** One *window* = monitor primes its lines → victim
performs exactly one AES encryption of a known plaintext → monitor re-times its
lines. Window schedule constants are in `leak_schedule.h`. A patched gem5
extension (`victim_table_trace.patch`) records which AES table lines the LLC
actually filled (ground truth). Analysis compares fixed hypotheses per byte
(`p ⊕ k`, `p` only, shuffled control) with Holm correction. Later phases add a
**differential test**: run the same arm with two different plaintext seeds;
`IDENTICAL` monitor output means no plaintext information reached the monitor.

Everything below runs from `$R/experiments/aes-leakage`. Details per phase:
`README.md` and `gem5_build.md` there, `progress.md` (ledger),
`PREREGISTRATION_DRAFT.md` (frozen at `675c047`, deviations D0–D4 at its end),
`PREREGISTRATION_OVERLAP.md`, and for Phase E `postdoc-review/EXECUTION_PLAN.md`.
(The status line in `experiments/aes-leakage/README.md` was written before
Phase E. The final status is in `postdoc-review/exec/FINAL_REPORT.md`.)

`run_arm.sh NAME VARIANT BUILD SPLIT WAYS SEED [MODE]` launches one checked
gem5 run (`DRY_RUN=1` only prints it). `run_batch.sh FILE JOBS` runs a list of
those in parallel. The stored run names already exist, so **re-run under new
names of the same length**. For example, replace the leading `e` with `r`:

```bash
cd "$R/experiments/aes-leakage"
for b in e1-diff e1-full e2-main e2-explore e3-defense; do
  sed -E 's/^e([0-9])-/r\1-/' batches/$b.txt > batches/${b/e/r}.txt     # r1-diff.txt, ...
done
```

| Phase | What we did | Command (new names) | Gate / outcome |
|---|---|---|---|
| A | Code, workloads, analysis, 128→173 tests; no gem5 | `python3 -B -m unittest discover -s tests -t .` | tests pass |
| B | Build `gem5-leak` (12 min 38 s); tracing-off guard against stored `sweep-v3/seed-5764a5e5/UNPARTITIONED-A8` | `gem5_build.md` steps 1–4 (output dir must be **139 characters**; the block there computes it) | `probes.bin` SHA-256 `0ee71c23…` — **PASS** |
| C | P0 smoke test, 20 windows | `bash run_arm.sh p0x-r1-scrub-n20 r1-scrub n20 off 16 1466213861` then `python3 -B analysis/aes_leak_analysis.py analyze --run-dir runs/p0x-r1-scrub-n20` | Attempt 1 **failed** a deadline (kept as `runs/p0-…`); fixed by shrinking the scrub to 4 KiB (**D0**); attempt 2 passed |
| D | P1 positive control, 2,000 windows, no partition, 16 monitor ways (11 min) | `bash run_arm.sh p1x-r1-scrub-n2000 r1-scrub n2000 off 16 1466213861` then `analyze --run-dir runs/p1x-r1-scrub-n2000 --nperm 20` | **PASS**: `p⊕k` significant on 16/16 bytes, `p` only and shuffled 0/16 |
| E1 | Window schedule: differential arms (N=500) and full AES (N=2000) | `bash run_batch.sh batches/r1-diff.txt 4`; `bash run_batch.sh batches/r1-full.txt 2`; then `analyze`, `leak_followup.py diff`, `leak_followup.py effect` (below) | All 8 differential tests **IDENTICAL** (8 or 1 monitor ways, unpartitioned or partitioned 8/8 and 1/15); P2a 16/16 bytes |
| E2 | Overlap schedule (victim traffic concurrent with probing; preregistered in `PREREGISTRATION_OVERLAP.md` before any overlap run), round-1 victim, N=2000 | binaries in `build/ovl-n2000` (rebuild: `EXTRA_DEFS="-DLEAK_ALLOW_OVERLAP -DLEAK_OFF_PROBE=520192UL" sh build.sh 2000 "$PWD/build/ovl-n2000"`); `bash run_batch.sh batches/r2-main.txt 4`; exploratory `batches/r2-explore.txt`; then `analyze`, `diff`, `count` | All arms **DIFFERENT** across seeds; key-dependent collision count supported at **8 ways** (unpartitioned and way-partitioned), not at 1 way |
| E3 | Full defense (way partition + request slots + per-domain response queues, D4) | build `gem5-leak-def` (§2.4); guard `bash run_arm.sh p0y-r1-scrub-n20 r1-scrub n20 off 16 1466213861 guard`, `diff` vs `runs/p0b-r1-scrub-n20 --allow-same-seed` must be IDENTICAL; then `bash run_batch.sh batches/r3-defense.txt 4` (~25 min per run) | Both defended arms (8/8 and 1/15) **IDENTICAL** across seeds where way partitioning alone was DIFFERENT |

Analysis commands per run (`N` = run name), exactly as in `EXECUTION_PLAN.md`:

```bash
python3 -B analysis/aes_leak_analysis.py analyze --run-dir runs/N --nperm 20 --out-json runs/N.analysis.json --out-md runs/N.analysis.md
python3 -B analysis/leak_followup.py diff   --a runs/N_seed1 --b runs/N_seed2 --out-json runs/X.diff.json --out-md runs/X.diff.md
python3 -B analysis/leak_followup.py effect --run-dir runs/N --nperm 10000 --out-json runs/N.effect.json --out-md runs/N.effect.md
python3 -B analysis/leak_followup.py count  --run-dir runs/N --nperm 10000 --out-json runs/N.count.json --out-md runs/N.count.md
```

`analyze` must end in `RUN CHECKS: PASS` (exit 0). A partitioned run must also
show `way_isolation | PASS`. `diff` ends in `DIFF VERDICT: IDENTICAL` or
`DIFFERENT`.

**What Stage 10 shows (simulated, tested plaintext streams only).** Without
concurrent traffic (window schedule), cache *state* leaks plaintext⊕key only
when the monitor owns the whole LLC (16 ways). With 8 or 1 monitor ways (the
values tested), partitioned or not, the monitor's output did not depend on the
plaintext.
With concurrent traffic (overlap schedule), the contention channel carries a
key-dependent signal at 8 monitor ways **even with way partitioning**. Adding
request slots and per-domain response queues makes the monitor output
byte-identical across plaintexts.

---

## 6. Known open items (read before writing the final paper, due Dec 1)

1. **Paper v3 needs one correction.** v3 says the way-partitioned 8-way signal is
   "small" (Pearson r 0.06–0.08 vs 0.44–0.46 unpartitioned). A later
   exploratory re-analysis found that this comes from **one cold-start
   window (window 0)** with three outlier walks. Without it the signals are about equal
   (Spearman 0.51–0.53 vs 0.52–0.54; per-line slope 2.83 vs 2.73 cycles).
   So way partitioning leaves the contention signal **intact** at 8 ways.
   The preregistered statements do not change, but v3's abstract, §XI-B/C/D
   and conclusion should be revised. This re-analysis is exploratory and its
   scripts are not in the repository.
2. The group should initial deviations **D1–D4** (`PREREGISTRATION_DRAFT.md`).
3. The P2b rule disagreement (registered rule vs D2) must be stated honestly
   in the paper. See `postdoc-review/exec/FINAL_REPORT.md`.
4. `experiments/aes-leakage/progress.md` "Open items" is stale. The final state
   is in `postdoc-review/exec/FINAL_REPORT.md`.
5. `preserve.py verify` in `experiments/aes-leakage` reports `PRESERVATION FAILED`
   **on this branch**. That is expected: it checks that nothing outside the
   experiment changed since its branch point (`45d21e2`), and this branch
   merges later `main` work (paper v2 builder, figures). Run it on branch
   `experiment/aes-leakage` for a meaningful check.

---

## 7. Troubleshooting we hit

| Symptom | Fix |
|---|---|
| analysis says `simout.txt` missing | gem5 was run without `-r -e` |
| re-run differs from the stored `probes.bin` | output path length differs; keep names the same length |
| `ImportError` for `validate` in `experiments/tdma` | WSL has a site-packages `validate` that shadows it; run from the experiment folder |
| From Git Bash, `/mnt/...` paths get mangled | prefix `wsl.exe` calls with `MSYS_NO_PATHCONV=1` |
| files in WSL `/tmp` disappear | WSL `/tmp` is wiped between `wsl.exe` calls; use a folder in `$HOME` |
| Windows `python` says "No Python at Python310" | use WSL `python3` |
| `prime_deadline` error in an AES run | the window budget was exceeded; see deviation D0 |
| gem5 build is killed | out of memory; use `-j14` or lower |
| panic in `rindex` with glibc binaries | gem5 RVV fault-only-first bug; our workloads are freestanding (`-nostdlib -march=rv64gc`) on purpose |

---

## 8. Where everything is

| Path | Contents |
|---|---|
| `Group18_EEL5764_Final_Paper*.docx` | Paper v1 (Oct 14), v2 (Oct 18), v3 (Nov 12, + `.pdf`) |
| `README_OCTOBER_STUDY.md` | Previous README: the October study in detail |
| `REPRODUCE.md`, `RUNBOOK.md`, `HANDOFF_20261019_RESIMULATION.md` | Earlier reproduction guides (still valid; this README supersedes their two-folder layout) |
| `REPORT_UPDATED_RUN_20261011.md` | Technical report for Stages 3–4 (§12, §13) |
| `PREREGISTRATION_*.md`, `VALIDATION_20261014.md` | Stage 3/4 rules and the independent validation |
| `configs/`, `gem5_ext/`, `workloads/`, `scripts/`, `analysis/`, `tests/` | Main pipeline |
| `results/`, `results/updated run/` | All stored runs (`sweep-v3/` = primary; `tdma-*` = Stages 5–8) |
| `experiments/tdma/`, `quiet-control-20261016/`, `causal-trace-20261016/`, `respq-defense-20261018/` | Stages 5–8: design, preregistration, patch, runners, `RESULTS.md` |
| `experiments/aes-leakage/` | Stage 10: code, binaries (`build/`), batches, all runs (`runs/`), ledgers |
| `postdoc-review/` | Stage 10 review memo, execution plan, execution log and final evidence report |
| `CLAUDE_CODE_PROMPT.md`, `FABLE_POSTDOC_PROMPT.md` | Specifications that started Stage 10 and its review |
| `archive/` | Pre-edit snapshots and checksum manifests |
