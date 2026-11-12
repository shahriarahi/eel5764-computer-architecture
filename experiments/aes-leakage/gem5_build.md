# Phase B: build the tracing gem5, then run the byte-identical guard

**Status: commands only. Nothing below has been run.** The one check that needs
no gem5 build, a syntax-only compile of the tracing source, passed in Phase A
(step 0). Everything runs inside WSL2 `Ubuntu-26.04`. Run each step yourself;
send back what step 5 asks for.

## 0. Pre-build check (no build, safe to repeat)

```bash
cd "/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree"
bash experiments/aes-leakage/gem5_syntax_check.sh
```

Expected last line: `syntax check PASS`. It type-checks `requestor_partition_manager.cc`
against the real gem5 v25.1.0.1 headers (once for the frozen original as a
control, once for the experiment's copy). Two generated headers that depend on
the new parameters are stood in for, so this is not a build: the real build in
step 3 is the first complete test of the tracing patch.

## 1. A separate tree at the paper's gem5 commit

```bash
git -C ~/eel5764/gem5 worktree add ~/eel5764/gem5-leak c8222cc67a399bfc01e8658dd14b30d5bfd634f9
```

The original tree (`~/eel5764/gem5`) and the other trees (`gem5-timeslot`,
`gem5-causal`, `gem5-respq`) are not touched.

## 2. A space-free `EXTRAS` path whose last component is `gem5_ext`

The sources include `"gem5_ext/..."`, so the extras directory must keep the name
`gem5_ext`. The repository path contains spaces, so give the same directory a
space-free path with a symlink, as `~/eel5764/gem5_ext` already does for the
frozen copy:

```bash
WT='/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree'
mkdir -p ~/eel5764/leak-ext
ln -s "$WT/experiments/aes-leakage/gem5_ext" ~/eel5764/leak-ext/gem5_ext
```

The target is `<abs path>/experiments/aes-leakage/gem5_ext`, exactly what the
task specifies for `EXTRAS`.

## 3. Build

```bash
cd ~/eel5764/gem5-leak
scons build/RISCV/gem5.opt -j$(nproc) EXTRAS=$HOME/eel5764/leak-ext/gem5_ext
```

When Phase B was run on this 15 GB machine it used `-j14` instead of
`-j$(nproc)` (20 here), as the project's earlier rebuild notes do; the build took
12 min 38 s. Expect the same "GCC 15.2.0 is not officially supported" warning as in the
earlier builds. Build `gem5.opt`, not `gem5.fast`: the
`--debug-flags=VictimTable` runs need the trace statements compiled in.

## 4. Guard: tracing disabled must reproduce the stored paper run byte for byte

With the tracing parameters left at their defaults, the new binary must behave
exactly like the one that produced `results/updated run/sweep-v3/` . The guard
re-runs one stored case, `seed-5764a5e5/UNPARTITIONED-A8`, with the ORIGINAL
config (no adapter) and requires an identical `probes.bin`.

Two conditions come from the stored run's own files (`cmd.txt`, `config.json`):

* It ran from the project root, so `argv[0]` of both workloads was
  `$R/workloads/...`. Run from `$R`, not from the worktree.
* The monitor receives the probe path as an argument, and the path length shifts
  its stack layout. The stored run wrote to a staging directory
  (`.UNPARTITIONED-A8.tmp.39qbQC`) whose absolute path is 139 characters
  (probe path: 150). The output directory must have the same length; the block
  below computes a directory name of exactly that length from your `$HOME`.

```bash guard-outdir
STORED_LEN=139
PREFIX=$HOME/eel5764/guard-leak/
PAD=$(( STORED_LEN - ${#PREFIX} ))
OUT=$PREFIX$(printf 'g%.0s' $(seq 1 $PAD))
```

```bash
R='/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture'
STORED="$R/results/updated run/sweep-v3/seed-5764a5e5/UNPARTITIONED-A8/probes.bin"
# (run the guard-outdir block above first, in the same shell)
mkdir -p "$(dirname "$OUT")"
cd "$R"
~/eel5764/gem5-leak/build/RISCV/gem5.opt -r -e -d "$OUT" configs/run_contention.py --split off --l1d-size 4KiB --monitor-ways 8 --workload-seed 1466213861 --monitor-sink file --monitor-variant v3
cmp "$OUT/probes.bin" "$STORED" && echo "GUARD PASS: probes.bin byte-identical" || echo "GUARD FAIL"
sha256sum "$OUT/probes.bin" "$STORED"
```

The stored file's SHA-256 is
`0ee71c2389afbabf2bb74393dd3b9c2a081c3c6f10ecbacb322a1c239a89848e`; both
lines printed by `sha256sum` must show it. The stored run's files are
timestamped 01:14 to 01:15, so expect on the order of a minute or two (64
intervals of 2,000,000 cycles).

Notes:

* `stats.txt` of the new binary has four extra statistic names (the
  `victimTable...` family, all zero); the guard compares `probes.bin` only, as
  the task specifies.
* `$R/configs/run_contention.py` may be a later revision than the one that made
  the stored run (the October 14 mechanism study added opt-in `--l2bus-*`
  options). Its default behaviour is unchanged; the October 14 `guard-mx` run
  documents that.
* If the guard fails, stop. Send both hashes and the output of
  `cmp -l "$OUT/probes.bin" "$STORED" | head`.

## 5. What to send back

1. `sha256sum ~/eel5764/gem5-leak/build/RISCV/gem5.opt`
2. The `GUARD PASS` / `GUARD FAIL` line and the two SHA-256 values.
3. If `scons` failed: the first error lines (the first complete compile of the
   tracing patch happens here).

Do not start Phase C (the 20-window smoke run, in `README.md`) until the guard
has passed.
