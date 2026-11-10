# Reproducing the project

Everything here runs in gem5 (simulation only). Pick the level you need; each
level builds on the one before it.

| Level | What you get | Needs | Time |
|---|---|---|---|
| 1. Read | Paper, data, code | A clone | Minutes |
| 2. Re-analyze | Every statistic recomputed from the stored raw runs | Python 3 (figures also need `matplotlib`, `numpy`) | Minutes |
| 3. Rebuild the paper | `Group18_EEL5764_Final_Paper_v2.docx` from the data | Level 2 + the two-folder layout below | Minutes |
| 4. Re-simulate | New gem5 runs | Linux or WSL2 and a gem5 build (about 6 GB); no RISC-V compiler | Hours |

## The two-folder layout

The repository has two branches that are used side by side:

- `main`: the paper, its builders, the main pipeline (`configs/`, `workloads/`,
  `gem5_ext/`, `analysis/`, `scripts/`), and the main results.
- `experiment/tdma-prototype`: the Section IX defense experiments
  (`experiments/`) and their results (`results/updated run/tdma-*`).

The paper builder expects the experiment branch checked out at
`.codex-tmp/tdma-worktree` inside the `main` checkout:

```bash
git clone https://github.com/shahriarahi/eel5764-computer-architecture.git
cd eel5764-computer-architecture
git worktree add .codex-tmp/tdma-worktree experiment/tdma-prototype
```

## Level 2: re-analyze

```bash
python3 -m unittest discover -s tests          # 70 tests, stdlib only
python3 analysis/summarize_sweep_v3.py --help  # main decision table
```

Each experiment folder under `.codex-tmp/tdma-worktree/experiments/` has its own
tests (`python3 -m unittest discover -p 'test_*.py'` from inside the folder) and a
`RESULTS.md` that names its inputs and outputs.

## Level 3: rebuild the paper

The builder reads the defense decision table from the `main` checkout and
refuses to overwrite an existing paper:

```bash
cp -r ".codex-tmp/tdma-worktree/results/updated run/tdma-rsv" "results/updated run/"
mv Group18_EEL5764_Final_Paper_v2.docx Group18_EEL5764_Final_Paper_v2.old.docx
python3 -B scripts/build_final_paper_v2.py
```

With unchanged data the new docx is byte-identical to the committed one.

## Level 4: re-simulate

1. **Install and build gem5.** Follow `RUNBOOK.md` sections 1 to 4: build
   dependencies, gem5 v25.1.0.1 (commit `c8222cc`) cloned to `~/eel5764/gem5`,
   the symlink `~/eel5764/gem5_ext` -> this repository's `gem5_ext/`, then
   `scons build/RISCV/gem5.opt -j<cores> EXTRAS=$HOME/eel5764/gem5_ext`.
   Keep gem5 on the Linux filesystem, not on a Windows or synced folder.
2. **Main study (paper Sections VI to VIII).** `RUNBOOK.md` section 10C
   (`scripts/run_repeated_contention_sweep_v3.py`, 50 runs, about 45 minutes)
   and `scripts/run_mechanism.py`. Set `GEM5=/path/to/gem5.opt` if your build
   is not at `~/eel5764/gem5/build/RISCV/gem5.opt`.
3. **Defense experiments (Section IX).** Each needs its own patched gem5 tree.
   Every patch applies to a clean `c8222cc` and already contains the earlier ones:

   | Tree (must be at this path) | Patch |
   |---|---|
   | `~/eel5764/gem5-timeslot` | `experiments/tdma/gem5-timeslot.patch` |
   | `~/eel5764/gem5-causal` | `experiments/causal-trace-20261016/gem5-causal.patch` |
   | `~/eel5764/gem5-respq` | `experiments/respq-defense-20261018/gem5-respq.patch` |

   ```bash
   git -C ~/eel5764/gem5 worktree add --detach ../gem5-respq c8222cc
   cd ~/eel5764/gem5-respq
   git apply <path-to-worktree>/experiments/respq-defense-20261018/gem5-respq.patch
   scons build/RISCV/gem5.opt -j<cores> EXTRAS=$HOME/eel5764/gem5_ext
   ```

   Run commands are in `HANDOFF_20261019_RESIMULATION.md` (Next steps, items 2
   and 3). Pass `--baseline-root` as the absolute path of the `main` checkout.
4. **Use new result folders.** Every runner refuses to write into an existing
   result folder, so the committed results cannot be overwritten. Before a
   rerun, change the root-name constants listed in the handoff (item 2) to new
   8-character names.

The workload binaries in `workloads/` and
`experiments/quiet-control-20261016/quiet_victim` are committed, so no RISC-V
compiler is needed. gem5 is deterministic: with the same gem5 build, a rerun
reproduces the stored `probes.bin` byte for byte. Our builds (Ubuntu 26.04,
GCC 15.2) had `gem5.opt` SHA-256 prefixes `c259c12e` (gem5), `5a540aed`
(timeslot), `2428f123` (causal), and `66c30701` (respq); another compiler gives
a different hash, so compare the outputs instead.

## Not in the repository

The causal-trace logs `results/updated run/tdma-ct1`, `tdma-ct2`, and `tdma-ct3`
(67 to 489 MB; one file is 442 MB, above GitHub's limit). Their summaries are in
`experiments/causal-trace-20261016/`; regenerate the logs with `run_cases.py
--trace` if needed. See `results/updated run/LOCAL_ONLY_RESULTS.md` on the
experiment branch.
