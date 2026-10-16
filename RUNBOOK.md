# Operations Runbook

> **Current method (updated October 14, 2026):** the final result is the
> record-free v3 study in **Step 10C**, stored in
> `results/updated run/sweep-v3/` and reported in
> `REPORT_UPDATED_RUN_20261011.md` §12. Its finding is that all eight
> allocations are distinguishable. The October 1 repeated study (Step 10B)
> and its `1/15` collapse point are withdrawn, because the monitor evicted
> its own probe lines. The October 1 note below is kept as history.

> **Contention method as of October 1, 2026:** the fixed-16-line sweep in
> `results/contention-l1d4k/` is preserved as an invalidated pilot because its
> monitor self-thrashed under every 1-8-way allocation. Use the repeated,
> depth-matched procedure in Step 10B and
> `results/contention-repeated-20261001/` for final claims.
> `REPORT_REPEATED_20261001.md` is the current report.

How to reproduce this project end to end on this machine, or on a fresh one.
The measured configurations were all run on this machine. For safety, the
contention configurations were launched one split at a time; the all-splits
commands below are equivalent reproduction wrappers. Reported timings are
measurements from this machine, not estimates.

Steps 0–13 document the validated WSL2 reference machine. For native Linux,
another Windows/WSL2 laptop, or an authorized remote Linux server, begin with
the Codex portability workflow in step 14; it discovers the topology and then
maps the validated steps onto that environment.

Follow the steps in order. Steps 0–4 are one-time setup (about 20 minutes,
mostly the gem5 build). The capacity/isolation sweep in steps 5–8 takes about
1 minute. The nine-run contention experiment in steps 9–10 took about 6
minutes on this machine.

---

## 0. What you need

| Requirement | This machine | Notes |
|---|---|---|
| OS | Windows 11 (10.0.26200) | gem5 does not build on native Windows |
| Linux | WSL2, distro `Ubuntu-26.04` | Any recent Ubuntu should work |
| CPU | 20 cores | The build uses `-j14`; lower it on a smaller machine |
| RAM | 15 GB visible to WSL | The gem5 build peaks around 8 GB with `-j14` |
| Free disk | 924 GB on the WSL disk | gem5 checkout + build is **6.0 GB** |
| Internet | Needed for steps 1–2 only | |

### Where things live, and why

Two locations, deliberately:

| What | Where | Why |
|---|---|---|
| gem5 source and build (6 GB) | `~/eel5764/gem5` — **WSL's own disk** | Building across the Windows/WSL file boundary is very slow, and OneDrive would try to sync every build artifact |
| Project files (configs, workloads, results, report) | `C:\Users\shahr\OneDrive\Documents\Fall 26\Computer Architecture` | Backed up by OneDrive; visible to both Windows and WSL |

WSL sees the project folder as:

```
/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture
```

**That path contains spaces.** Always quote it. Unquoted, the shell splits it
at `Fall` and you get confusing "No such file or directory" errors.

### Opening the right shell

Everything runs **inside WSL**. Open a terminal and run:

```bash
wsl -d Ubuntu-26.04
```

Or launch "Ubuntu 26.04" from the Start menu. Then set a shell variable you
will reuse in every later step:

```bash
export PROJ="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
```

This variable does not survive closing the terminal. If you open a new shell,
set it again.

---

## 1. Install build dependencies

One time only. Requires `sudo` (you will be prompted for your WSL password).

```bash
sudo apt-get update
sudo apt-get install -y scons python3-dev m4 zlib1g-dev libprotobuf-dev \
  protobuf-compiler libgoogle-perftools-dev libboost-all-dev pkg-config \
  libhdf5-serial-dev libpng-dev libelf-dev python3-numpy python3-matplotlib
```

Already present on this machine (do **not** install these again): `git`,
`gcc` 15.2.0, `g++`, `make`, `python3` 3.14.4, and the RISC-V cross-compiler
`riscv64-linux-gnu-gcc` 15.2.0.

If `riscv64-linux-gnu-gcc` is missing on a fresh machine, add
`gcc-riscv64-linux-gnu` to the list above.

**Verify:**

```bash
scons --version | head -2
riscv64-linux-gnu-gcc --version | head -1   # expect 15.2.0
python3 -c "import numpy, matplotlib; print('plotting OK')"
```

---

## 2. Get gem5

```bash
mkdir -p ~/eel5764
cd ~/eel5764
git clone --depth 1 --branch v25.1.0.1 https://github.com/gem5/gem5.git gem5
```

**Verify** you are on the exact revision this project was built against:

```bash
cd ~/eel5764/gem5
git describe --tags      # v25.1.0.1
git rev-parse HEAD       # c8222cc67a399bfc01e8658dd14b30d5bfd634f9
```

A different commit is not automatically wrong, but the file and line numbers
cited in `REPORT.md` refer to this one.

> The gem5 source tree is **never modified** by this project. Everything we add
> lives in `gem5_ext/` and is compiled in from outside.

---

## 3. Link the partition extension into WSL

gem5's build needs a Linux-side path to the extension. This creates a symlink
from the WSL home directory to the real folder in the project:

```bash
ln -sfn "$PROJ/gem5_ext" ~/eel5764/gem5_ext
```

**Verify** it points at the project folder:

```bash
readlink -f ~/eel5764/gem5_ext
# /mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/gem5_ext
ls ~/eel5764/gem5_ext
# RequestorPartitionManager.py  SConscript
# requestor_partition_manager.cc  requestor_partition_manager.hh
```

Because it is a symlink, editing `gem5_ext/` in Windows (VS Code, Notepad)
immediately affects what gem5 compiles. No copying step.

---

## 4. Build the simulator

```bash
cd ~/eel5764/gem5
scons build/RISCV/gem5.opt -j14 EXTRAS=$HOME/eel5764/gem5_ext
```

Lower `-j14` if you have fewer cores; `-j$(nproc)` is a safe choice.

**Measured build times on this machine:**

| Build | Wall clock |
|---|---|
| First (clean) build | **11 min 21 s** |
| Rebuild after editing only `gem5_ext/` | **2 min 19 s** |

To keep a log for troubleshooting:

```bash
scons build/RISCV/gem5.opt -j14 EXTRAS=$HOME/eel5764/gem5_ext \
  > ~/eel5764/build.log 2>&1; echo "exit=$?"
```

**Expected warnings — these are normal and not errors:**

```
Warning: Detected GCC version 15.2.0 is not officially supported.
         gem5 supports GCC v11 up to v14.2.
Warning: Header file <capstone/capstone.h> not found.
```

gem5 officially supports GCC up to 14.2. It builds and runs correctly with
15.2 here, but this is recorded in `REPORT.md` as a threat to validity.
Capstone is only used for disassembly features this project does not touch.

**Verify the build succeeded and the extension is present:**

```bash
ls -la ~/eel5764/gem5/build/RISCV/gem5.opt        # ~1.0 GB
printf 'from m5.objects import RequestorPartitionManager as R\nprint("extension OK:", R.type)\n' > /tmp/check_ext.py
~/eel5764/gem5/build/RISCV/gem5.opt -q /tmp/check_ext.py
# expect: extension OK: RequestorPartitionManager
```

If that last command raises `ImportError`, the `EXTRAS=` path was wrong — check
step 3, then rebuild.

---

## 5. Build the workloads

```bash
cd "$PROJ"
sh workloads/build.sh
```

This compiles seven freestanding RISC-V binaries: `randacc` (core 0),
`stream` (core 1), `chase` (used only by the first pilot), the original
contention-control pair `monitor`/`victim`, and the redesigned pair
`monitor_l1d4k`/`victim_l1d4k`. The redesigned binaries use two-million-cycle
intervals; separately named binaries preserve reproduction of the original
one-million-cycle pilot.

**Verify they are correct.** All three numbers must be `0`:

```bash
cd "$PROJ/workloads"
for b in chase randacc stream monitor victim monitor_l1d4k victim_l1d4k; do
  echo "$b: vector=$(riscv64-linux-gnu-objdump -d $b | grep -cE '\sv[a-z]+[0-9]*\.[vx]|vsetvl') \
gp_refs=$(riscv64-linux-gnu-objdump -d $b | grep -c '(gp)') \
libc_syms=$(riscv64-linux-gnu-nm -u $b | wc -l)"
done
```

Why each must be zero:

- **vector = 0** — gem5 v25.1's `TimingSimpleCPU` mishandles RISC-V vector
  fault-only-first loads. Any vector instruction risks a simulator panic.
- **gp_refs = 0** — without a C runtime nothing initialises the `gp` register,
  so `gp`-relative addressing would read garbage. `-Wl,--no-relax` prevents it.
- **libc_syms = 0** — the binaries are fully self-contained.

**Confirm the binaries match the ones used for the published results:**

```bash
cd "$PROJ" && sha256sum -c results/8-8/workload_sha256.txt
# workloads/randacc: OK
# workloads/stream: OK

sha256sum -c results/contention-l1d4k/8-8/workload_sha256.txt
# workloads/monitor_l1d4k: OK
# workloads/victim_l1d4k: OK
```

A mismatch means a different compiler version produced different code. The
experiment will still run; note the difference when reporting results.

---

## 6. Smoke test (optional but recommended)

Two fast runs that prove the whole chain works before committing to the sweep.
About 1 second each.

```bash
cd "$PROJ"
GEM5=~/eel5764/gem5/build/RISCV/gem5.opt
$GEM5 -q -d /tmp/smoke88 configs/run.py --split 8-8 \
  --warmup-ticks 100000000 --measure-ticks 200000000
```

Expect a final line `OK split=8-8 end_tick=300000000`.

Also confirm the argument validation rejects bad input:

```bash
$GEM5 -q -d /tmp/bad configs/run.py --split 9-9    # A + B must equal 16
$GEM5 -q -d /tmp/bad configs/run.py --split 0-16   # each partition needs >= 1 way
$GEM5 -q -d /tmp/bad configs/run.py --split abc    # expected A-B, A/B or off
```

Each should print a clear error and exit without simulating.

---

## 7. Run the capacity/isolation sweep

Nine configurations, each a fresh gem5 process:

```bash
cd "$PROJ"
bash scripts/run_sweep.sh
```

**Measured: 31.6 seconds** for all nine.

To re-run a subset:

```bash
bash scripts/run_sweep.sh UNPARTITIONED 8-8
```

> **This deletes and recreates `results/<split>/` for each configuration it
> runs.** Nothing else under `results/` is touched — `summary.csv`, `figures/`,
> `pilot/` and `validation/` are left alone. If you want to keep a previous
> run, copy the folder aside first.

Expected output, one line per configuration:

```
== UNPARTITIONED
OK split=off end_tick=5000000000
== 1-15
OK split=1-15 end_tick=5000000000
...
```

The script fails loudly and stops if gem5 exits non-zero, if any of
`stats.txt`, `run_meta.json`, `config.ini`, `simout.txt` is missing or empty,
or if the `OK split=` line is absent. A silent partial run is not possible.

Each `results/<split>/` ends up containing:

| File | What it is |
|---|---|
| `cmd.txt` | The exact command line used |
| `stats.txt` | gem5 statistics — 8 dumps per run |
| `run_meta.json` | Split, way allocation, full config, exit causes |
| `config.ini`, `config.json` | Complete simulated system description |
| `simout.txt` | Workload header lines + the `OK` line |
| `simerr.txt` | gem5 warnings |
| `workload_sha256.txt` | Hashes of the two binaries used |

---

## 8. Analyse the capacity/isolation sweep

```bash
cd "$PROJ"
python3 analysis/analyze.py --require-all
```

`--require-all` makes it fail if any of the nine configurations is missing,
rather than quietly analysing a partial set.

**Expected output** (these exact numbers should reproduce):

```
wrote results/summary.csv
UNPARTITIONED  ipc0=0.239680 ipc1=0.025063 mr0=0.026675 mr1=1.000000  viol=   shared_ways=16 unmapped=0 conflicts=0  PASS sharing observed
         1-15  ipc0=0.066524 ipc1=0.023735 mr0=0.958203 mr1=1.000000  viol= 0 shared_ways= 0 unmapped=0 conflicts=0  PASS disjoint
         2-14  ipc0=0.072875 ipc1=0.023951 mr0=0.845253 mr1=1.000000  viol= 0 shared_ways= 0 unmapped=0 conflicts=0  PASS disjoint
         3-13  ipc0=0.082067 ipc1=0.024096 mr0=0.709193 mr1=1.000000  viol= 0 shared_ways= 0 unmapped=0 conflicts=0  PASS disjoint
         4-12  ipc0=0.094526 ipc1=0.024230 mr0=0.569160 mr1=1.000000  viol= 0 shared_ways= 0 unmapped=0 conflicts=0  PASS disjoint
         5-11  ipc0=0.111641 ipc1=0.024376 mr0=0.429698 mr1=1.000000  viol= 0 shared_ways= 0 unmapped=0 conflicts=0  PASS disjoint
         6-10  ipc0=0.137096 ipc1=0.024559 mr0=0.285322 mr1=1.000000  viol= 0 shared_ways= 0 unmapped=0 conflicts=0  PASS disjoint
          7-9  ipc0=0.178503 ipc1=0.024763 mr0=0.142148 mr1=1.000000  viol= 0 shared_ways= 0 unmapped=0 conflicts=0  PASS disjoint
          8-8  ipc0=0.259680 ipc1=0.025173 mr0=0.000000 mr1=1.000000  viol= 0 shared_ways= 0 unmapped=0 conflicts=0  PASS disjoint
wrote results/figures/{tradeoff,occupancy}.{pdf,png}
```

**The three things that must hold for the run to be valid:**

1. `viol= 0` on every partitioned split — no core's blocks ever appeared
   outside its assigned ways, checked at all 8 stats dumps.
2. `unmapped=0` and `conflicts=0` everywhere — every LLC request was
   attributed to a core, and no cache line was shared between the processes.
3. `shared_ways=16` on `UNPARTITIONED` — without partitioning, both cores do
   use all the ways. If this were 0, the control would be broken and the
   comparison meaningless.

The script exits non-zero if any configuration reports `FAIL`.

Simulation is deterministic: re-running produces byte-identical `stats.txt`
apart from host-timing lines (`hostSeconds` and similar). Verify with:

```bash
diff <(grep -v '^host' results/8-8/stats.txt) \
     <(grep -v '^host' results/validation/8-8/stats.txt) && echo IDENTICAL
```

---

## 9. Run the AES contention sweep

**Historical method only.** This section reproduces the preserved fixed-16-line
pilot and must not be used to claim a partition threshold. Continue to Step 10A
below for the corrected experiment.

This is a separate experiment from steps 7–8. Core 0 runs the monitor and
core 1 runs the educational T-table AES workload. Both receive a 4 KiB,
four-way private L1D; the shared LLC remains 256 KiB and 16-way.

The monitor primes and probes its own 16-line chain in all 256 LLC sets. The
AES key, plaintext seed, and 32-active/32-idle schedule are fixed public
inputs. The experiment detects activity only; it performs no key recovery.

From a clean contention result root, run all nine configurations:

```bash
cd "$PROJ"
bash scripts/run_contention_sweep.sh
```

The wrapper launches a fresh gem5 process and immediately applies the frozen
10,000-shuffle maximum-set analysis for each of:

```text
UNPARTITIONED 1-15 2-14 3-13 4-12 5-11 6-10 7-9 8-8
```

To run only selected missing configurations:

```bash
bash scripts/run_contention_sweep.sh 4-12 8-8
```

The runner is intentionally non-destructive. If
`results/contention-l1d4k/<split>/` already exists, it stops rather than
replacing it. Failed attempts are preserved as
`<split>.failed.<timestamp>`. The completed result directories in this
project must therefore be archived or moved manually before attempting a
full reproduction.

Each successful configuration must contain:

| File | Requirement |
|---|---|
| `simout.txt` | AES self-test marker, 16,384 probe records, monitor PASS marker, gem5 OK marker |
| `stats.txt` | One measurement dump plus gem5's automatic final dump |
| `run_meta.json` | Exact split, 4 KiB L1D profile, two-million-cycle interval, public label schedule |
| `config.ini`, `config.json` | Complete simulated configuration |
| `cmd.txt` | Exact gem5 command |
| `workload_sha256.txt` | Hashes of `monitor_l1d4k` and `victim_l1d4k` |
| `analysis.json` | Corrected SNR decision, IPC, miss rates, and partition evidence |

For a partitioned run, `analysis.json` is valid only when it reports:

```text
"isolation_validation": "PASS disjoint"
"isolation_violations": 0
"unmapped_lookups": 0
"addr_partition_conflicts": 0
```

The first 4 KiB attempt is preserved under a timestamped failed directory. It
hit `monitor error=probe_deadline` because a 500,000-cycle half-interval was
too short after the smaller L1D increased LLC traffic. The final profile uses
two-million-cycle intervals and probes at the one-million-cycle midpoint; it
does not reduce set coverage or add artificial AES-table eviction.

---

## 10. Summarise the contention sweep

After all nine `analysis.json` files exist:

```bash
cd "$PROJ"
python3 analysis/summarize_contention.py
```

The summarizer refuses partial or method-mismatched inputs. It writes:

```text
results/contention-l1d4k/summary.csv
results/contention-l1d4k/snr_vs_split.pdf
results/contention-l1d4k/contention_tradeoff.pdf
```

The checked-in 300 dpi PNG versions were exported from the same matplotlib
figure objects for visual inspection and report embedding.

Expected headline output:

```text
wrote .../results/contention-l1d4k/summary.csv
collapse_point=1-15
```

The measured decisions are:

| Split | Max-set SNR | Shuffled-max 95th | p | Decision |
|---|---:|---:|---:|---|
| UNPARTITIONED | 34.075979 | 0.842170 | 0.000100 | PASS |
| 1-15 | 0.620168 | 0.890354 | 0.587841 | FAIL |
| 2-14 | 0.586151 | 0.894048 | 0.698730 | FAIL |
| 3-13 | 0.630672 | 0.891628 | 0.563944 | FAIL |
| 4-12 | 0.569734 | 0.889712 | 0.744926 | FAIL |
| 5-11 | 0.631600 | 0.889226 | 0.548445 | FAIL |
| 6-10 | 0.537381 | 0.895379 | 0.838616 | FAIL |
| 7-9 | 0.655326 | 0.885486 | 0.466553 | FAIL |
| 8-8 | 0.619269 | 0.890319 | 0.582442 | FAIL |

`PASS` means AES-active and AES-idle intervals are distinguishable. `FAIL`
means the measured statistic is indistinguishable from the corrected null;
it is not a simulator failure. The first tested collapse point is therefore
`1/15`.

At `1/15`, relative to `UNPARTITIONED`:

- Monitor IPC falls from 0.487557 to 0.114773: 76.4596% cost.
- AES IPC falls from 0.672815 to 0.672674: 0.0210% cost.
- Monitor LLC miss rate rises from 0.320541 to 0.996678: +67.6137 percentage points.
- AES LLC miss rate falls from 0.002522 to 0.00000762: -0.2515 percentage points.

This historical conclusion is superseded. The fixed 16-line monitor exceeded
every tested 1-8-way allocation and drove its own miss rate to approximately
99.7%. The results remain available for audit, but not as defense evidence.

---

## 10A. Run the corrected depth-matched AES contention sweep

The corrected monitor takes a required depth `A` and walks exactly `A` lines
per LLC set. For every partitioned split `A/(16-A)`, the runner first executes
an unpartitioned control with the same `A`, binary, public AES inputs, schedule,
and seeds. A treatment is interpretable only when its matched control is
distinguishable from the shuffled-label null.

The out-of-tree partition manager also validates address mapping directly.
For monitor requests inside `probe_lines`, it compares the logical set derived
from the virtual array offset with the physical LLC set. A constant rotation is
allowed; missing virtual addresses or any rotation mismatch fail validation.

From a result root that does not already exist, run:

```bash
cd "$PROJ"
sh workloads/build.sh
cd ~/eel5764/gem5
scons build/RISCV/gem5.opt -j14 EXTRAS=$HOME/eel5764/gem5_ext
cd "$PROJ"
bash scripts/run_corrected_contention_sweep.sh
```

The default output root is `results/contention-corrected-20261001-v2/`. It
contains the original 16-line unpartitioned control, eight depth-matched
unpartitioned controls, eight partitioned treatments, `summary_matched.csv`,
and PDF/300-dpi PNG figures. Existing case directories are never replaced.

Every case requires 16,384 probe records, two stats blocks,
`probe_mapping_validation = PASS congruent`, and zero set-mapping mismatches.
Every partitioned treatment additionally requires `PASS disjoint`, zero
isolation violations, zero unmapped lookups, and zero address conflicts.

Summarize an existing corrected root with:

```bash
python3 analysis/summarize_matched_contention.py \
  --results-root results/contention-corrected-20261001-v2
```

The October 1 measurement produced `first_tested_indistinguishable=1-15` but
`stable_collapse_point=none`: later allocations regained statistical
significance. Therefore, do not report `1/15` as a monotonic threshold.

---

## 10B. Run the repeated matched-control sweep

This is the final proposal-facing experiment. It uses three predeclared public
AES plaintext seeds: `0x5764A5E5`, `0x5764A5E6`, and `0x5764A5E7`. For each
seed, it runs eight A-line unpartitioned controls and eight `A/(16-A)`
treatments. Two A=16 unpartitioned diagnostics are added but excluded from
inference, producing exactly 50 fresh gem5 processes.

The AES seed is a validated runtime argument, so every case uses the same
victim binary. The result root is immutable by default and the runner supports
`--resume` after an interruption without replacing completed cases.

```bash
cd "$PROJ"
sh workloads/build.sh
python3 scripts/run_repeated_contention_sweep.py \
  --results-root results/contention-repeated-20261001
```

List the exact 50-process plan without running gem5:

```bash
python3 scripts/run_repeated_contention_sweep.py --list-plan
```

Recompute the aggregate from saved outputs:

```bash
python3 analysis/summarize_repeated_contention.py \
  --results-root results/contention-repeated-20261001
```

For each allocation, the analysis combines the three seed-specific p-values
with Fisher's method, then applies Holm familywise correction across the eight
allocations at alpha 0.05. Controls and treatments are corrected as separate
families. Every control must also pass individually. A stable collapse point
requires the treatment at that allocation and all larger monitor allocations
to be indistinguishable after correction.

The measured repeated result is `stable_collapse_point=1-15`. All 24 controls
were individually distinguishable; all eight treatments were indistinguishable
after Fisher/Holm correction. The closest treatment to the corrected boundary
was `7/9` with `Holm p=0.061546`, and one of its three individual runs was
significant. Interpret `1/15` as the first sufficient tested allocation under
this predefined test, not as proof of equivalence or elimination of all shared
resource channels.

The sweep completed 50 processes in 45.73 minutes and produced 819,200 probe
records, 100 statistics blocks, 50 congruent mapping validations, and 24
disjoint-way validations with zero isolation violations.

> **Superseded (October 11–14, 2026).** The `1/15` collapse point above is
> withdrawn. This monitor wrote a 384 KiB record array during measurement,
> which evicted 20–25% of its own probe lines, but only in partitioned runs.
> The corrected v3 study (§10C) finds every allocation distinguishable. The
> commands in this section still reproduce the October 1 data exactly.

---

## 10C. Run the updated record-free study (v2 and v3 monitors)

This is the **final** experiment. Every new behaviour is opt-in, so the
commands in §10B are unaffected. The rules, hashes and deviations D1–D3 are in
`PREREGISTRATION_V2_20261011.md`. The results are in
`REPORT_UPDATED_RUN_20261011.md` §12.

| Monitor | Build flags | SHA-256 prefix | Runner mode |
|---|---|---|---|
| `monitor_l1d4k` (v1) | none | `d25a119b` | `l1d4k` |
| `monitor_v2_l1d4k` | `-DMONITOR_PROBE_SINK_FILE` | `1edbb2d3` | `l1d4k-v2` |
| `monitor_v3_l1d4k` (final) | `-DMONITOR_PROBE_SINK_FILE -DMONITOR_HOT_STATE_IN_REGISTERS` | `0722e049` | `l1d4k-v3` |

- **v2** writes each 16-byte record into the probe line it has just loaded,
  then flushes each interval to `probes.bin` with `writev`.
- **v3** also keeps the way count and file descriptor in registers during
  measurement.
- `workloads/build.sh` builds all three, and rebuilding reproduces the hashes
  above.
- The config options behind the modes are `--monitor-sink file` and
  `--monitor-variant v3`.

**Final v3 sweep.** This runs 50 processes in about 45 minutes. The runner
refuses to reuse an existing root.

```bash
cd "$PROJ"
sh workloads/build.sh
python3 scripts/run_repeated_contention_sweep_v3.py \
  --results-root "results/updated run/sweep-v3-repro"
```

To recompute the decision rule from saved runs, run the summarizer on a
**copy**, because it writes its outputs into the root it reads:

```bash
python3 analysis/summarize_sweep_v3.py --results-root "<copy of sweep-v3>"
```

The summarizer applies the rule below.

- **Statistics:** two co-primary statistics, max-set SNR and hit-only
  interval mean.
- **Combination and correction:** Fisher combination across the three seeds,
  then Holm correction over 16 tests (8 allocations × 2 statistics) per arm.
- **Self-eviction gate:** the fraction of walks more than 100 cycles above
  the floor may differ by at most 1 point per pair.
- **Effect estimate:** a 90% bootstrap CI, with a ±0.02 cycles-per-line
  equivalence margin.

**Measured result:**

- 24/24 pairs pass the gate.
- All eight allocations are distinguishable.
- `stable_collapse_point=None` and `stable_equivalence_point=None`.
- The treatment retains 100% of the control's signal at 1/15 and 70–85% at
  2/14–8/8.
- Cost is at most 0.029%.

**Supporting runs** (each refuses to reuse an existing root):

```bash
# v2 sweep (preregistered; 7/9 and 8/8 fail the original gate)
python3 scripts/run_repeated_contention_sweep_v2.py --plan smoke \
  --results-root "results/updated run/smoke-repro"
python3 scripts/run_repeated_contention_sweep_v2.py --plan full \
  --results-root "results/updated run/sweep-repro"
# D2 rerun of 7/9 and 8/8 with the v3 monitor (12 processes)
python3 scripts/run_rerun_v3.py --results-root "results/updated run/rerun-repro"
# post-hoc analysis of the October 1 data, and the v1-vs-v2 comparison
python3 analysis/posthoc_hit_only_20261011.py --out results/posthoc-repro
python3 analysis/compare_v1_v2.py --out "results/updated run/comparison-repro"
```

**Word reports.** Use the Windows Python; it needs only the standard library.
The builder reads the two original DOCX templates and the sweep-v3 results,
and refuses to overwrite its outputs. Delete or move the two `_Updated` files
first:

```bash
python -I -B -X utf8 scripts/build_updated_reports.py
```

**Reproducibility notes:**

- A v3 run is byte-reproducible only at the same output-path length, because
  the probe-file path is a monitor argument and shifts its stack layout.
  `results/updated run/repro-v3/` is a bit-exact re-simulation of one 8/8
  pair.
- Holm values of `6.6e-9` are the permutation floor for 3 seeds × 16 tests.
- `VALIDATION_20261014.md` records a full independent re-derivation.

---

## 11. Optional: re-run the workload-sizing pilots

Not needed to reproduce the results — the pilots are archived under
`results/pilot/` with their `stats.txt` and `run_meta.json`. They are
documented in `REPORT.md` §3 because the 128 KiB working set was chosen
**after** seeing pilot data, and that choice should be auditable.

To re-run a sizing experiment, build `randacc` at a different working set and
pass it explicitly:

```bash
cd "$PROJ"
riscv64-linux-gnu-gcc -O2 -march=rv64gc -mabi=lp64d -static -nostdlib \
  -ffreestanding -fno-builtin -fno-tree-loop-distribute-patterns \
  -Wl,--no-relax -DWS_BYTES="(192*1024)" -o /tmp/randacc_192 workloads/randacc.c

~/eel5764/gem5/build/RISCV/gem5.opt -q -d /tmp/ws192_88 configs/run.py \
  --split 8-8 --workloads "/tmp/randacc_192,workloads/stream"
```

---

## 12. Troubleshooting

Every entry below is an error actually hit while building this project.

### `fatal: Failed to open file ./hello` / workload not found
The path has spaces. Quote it: `cd "$PROJ"`, not `cd $PROJ`.

### `panic: Page table fault when accessing virtual address 0x8000...`
A workload was linked against the system C library. Ubuntu 26.04's static
glibc targets RVA23 and uses vector fault-only-first loads (`vle8ff.v`) in
`strrchr`; gem5 v25.1's `TimingSimpleCPU` raises a fault instead of trimming
`vl`, so start-up crashes. Rebuild with `workloads/build.sh`, which passes
`-nostdlib -march=rv64gc`. Confirm with the vector check in step 5.

### `panic: Segment outside the bounds of the image data`
The binary's writable data is entirely uninitialised (`.bss`), and gem5's ELF
loader rejects a zero-size segment whose file offset is past end-of-file. The
fix is already in `workloads/common.h` (`rw_segment_anchor`, one initialised
word). If you write a new workload, include that header.

### `ImportError: cannot import name 'RequestorPartitionManager'`
gem5 was built without the extension. Re-run step 4 with the `EXTRAS=` argument
and check `readlink -f ~/eel5764/gem5_ext` resolves to the project folder.

### `sudo: interactive authentication is required`
Only affects non-interactive/automated shells. At a normal terminal, `sudo`
prompts and works. To run as root without a password from a Windows terminal:
`wsl -d Ubuntu-26.04 -u root -e bash -lc '<command>'`.

### A workload appears to run but does no memory traffic
GCC can fold loads from a never-written static buffer into constants, leaving a
loop that touches no memory. Both workloads read through a `volatile` pointer to
prevent this. Symptom: implausibly high IPC and near-zero LLC accesses. Check
the disassembly for actual load instructions.

### The build fails or behaves oddly after editing `gem5_ext/`
Force a clean rebuild of just the extension's objects:

```bash
rm -rf ~/eel5764/gem5/build/RISCV/gem5_ext
scons build/RISCV/gem5.opt -j14 EXTRAS=$HOME/eel5764/gem5_ext
```

### Starting completely over
```bash
rm -rf ~/eel5764/gem5          # deletes the 6 GB checkout and build
```
Then repeat steps 2–4. This does **not** touch the project folder.

---

## 13. Scope and interpretation

### What it covers

The study as actually carried out:

1. Whether gem5's LLC way partitioning confines each core's cache blocks to
   disjoint ways — verified directly from the tag array, at 8 points per run,
   for all eight partitioned splits.
2. What each split costs each core, in IPC and LLC miss rate, measured against
   an unpartitioned control.
3. Whether a simulated cache-contention monitor distinguishes public
   AES-active from AES-idle intervals, and the first tested partition at which
   that statistic becomes indistinguishable from a shuffled-label null.

Steps 0–10 reproduce these measurements.

### Historical pilot and redesign boundary

The original 16 KiB-L1D unpartitioned control remains in
`results/contention/UNPARTITIONED`. It failed its predeclared interval-mean
test (`SNR=0.123071`, null95 `0.502195`, `p=0.619938`) after the AES core made
only six measured LLC demand accesses. That result has not been overwritten or
reclassified.

The completed sweep in steps 9–10 is a separately declared method: symmetric
4 KiB L1D caches, two-million-cycle intervals, and a maximum per-set SNR whose
shuffled null recomputes the maximum across all 256 sets. This correction is
important because selecting the largest of 256 uncorrected SNRs would inflate
the false-positive rate.

The redesigned unpartitioned control produced `SNR=34.075979`, null95
`0.842170`, and `p=0.000100`; all eight disjoint-way configurations were
indistinguishable from their corrected nulls. Exact design decisions and the
deadline-feasibility amendment are recorded in
`docs/superpowers/specs/2026-09-28-contention-l1d4k-redesign.md`.

### What can be added without going near that boundary

These are straightforward extensions of the existing setup:

- **Solo-core baselines** — run each workload with the other core idle, to turn
  the current inference about core 1's slowdown (attributed to shared bus and
  DRAM contention) into a direct measurement.
- **A second workload pair**, so the cost curve does not rest on one synthetic
  kernel.
- **Sensitivity sweeps** — different LLC sizes, associativity, or replacement
  policy.

---

## 14. Reproducing on another computer with Codex

This section is for handing the project to Codex on a different laptop,
workstation, or authorized remote Linux server. It does not replace steps
0–13; it tells Codex how to discover the new environment and apply those
steps without silently changing the experiment.

### Before starting Codex

1. Copy the complete project directory to the new computer, or to an
   authorized remote Linux server. Preserve source files, `AGENTS.md`, this
   runbook, and `REPORT.md`. If the goal is a fresh reproduction, keep the
   existing `results/` as reference evidence but choose a new project copy or
   move the reference results aside manually; the contention runner will not
   overwrite them.
2. Start Codex with the copied project directory as its workspace. If Codex
   runs directly on a remote server, start it inside the remote project root.
   If Codex runs on the laptop and will use SSH, configure and test the SSH
   host alias yourself first. Do not paste passwords, private keys, tokens, or
   API keys into the prompt.
3. Paste the prompt below into a new Codex task. Replace only the bracketed
   values that apply. Use `not applicable` for unused remote fields.

Supported execution topologies:

| Topology | Build location | Project location |
|---|---|---|
| Native Linux | Linux-native filesystem | Any writable Linux path |
| Windows + WSL2 | WSL filesystem for the 6 GB gem5 tree | Windows-mounted path or WSL path |
| Codex running on an authorized remote Linux server | Remote Linux-native filesystem | Remote writable path |
| Laptop Codex using an existing SSH connection | Remote Linux-native filesystem | Remote writable path; copy back only requested final artifacts |

Native Windows and macOS may act as clients, but they are not validated direct
gem5 build targets for this project. If neither Linux, WSL2, nor an authorized
remote Linux host is available, Codex must stop and explain the incompatibility.
OpenAI also documents that Codex environments can be backed by a laptop or a
remote/self-hosted sandbox; that is an optional Codex deployment mechanism,
not a requirement of this project:
[OpenAI self-hosted environments](https://developers.openai.com/api/docs/guides/agents-api/environments/self-hosted).

### 1. Recommended prompt — Codex

Copy everything inside the following block into Codex:

```text
## Objective

Reproduce the complete gem5 LLC way-partitioning and simulated AES cache-
contention project contained in this workspace. Work as an evidence-driven
research assistant: discover the available execution topology, build and run
the project on a supported Linux environment, verify every phase using real
output, and report exact measured results without inventing or substituting
values.

## Supplied context

- Local project root: [PROJECT_ROOT]
- Optional existing SSH host alias: [SSH_HOST_ALIAS_OR_NOT_APPLICABLE]
- Optional remote project root: [REMOTE_PROJECT_ROOT_OR_NOT_APPLICABLE]
- Preferred remote gem5 root: [REMOTE_GEM5_ROOT_OR_NOT_APPLICABLE]
- Intended action: fresh reproduction on this computer or authorized server
- The project contains AGENTS.md, RUNBOOK.md, REPORT.md, configs/, workloads/,
  gem5_ext/, scripts/, analysis/, tests/, and reference results.

## Non-negotiable constraints

1. Read AGENTS.md and RUNBOOK.md completely before changing files or running
   project commands. Treat them as binding project instructions.
2. Work only inside the supplied project root and the explicitly selected
   Linux gem5 build directory. Do not inspect unrelated user directories.
3. First detect and report one of these topologies:
   a. native Linux;
   b. Windows with WSL2;
   c. Codex already executing on an authorized remote Linux server;
   d. Codex on a client computer with an existing authorized SSH connection
      to a Linux server;
   e. unsupported.
4. Native Linux, WSL2, and authorized remote Linux are supported. Native
   Windows and macOS are clients only, not direct gem5 build targets. If no
   supported Linux execution target exists, stop with evidence; do not invent
   Docker, VM, cloud, or cross-compilation workarounds.
5. For WSL2, keep the gem5 checkout/build on the WSL-native filesystem. The
   project may remain under /mnt/c if that is where it was supplied.
6. For remote Linux:
   - Confirm the host is explicitly authorized before using it.
   - Use only an already configured SSH alias or a Codex session already
     running on that host.
   - Never request, print, copy, or store passwords, private keys, access
     tokens, API keys, or complete SSH configuration.
   - Ask before transferring the project or results.
   - Keep the gem5 checkout, build, intermediate output, and active simulation
     results on the remote Linux filesystem.
   - Copy back only user-requested final artifacts, to verified unused local
     paths. Never overwrite local evidence.
7. Before installing or upgrading a dependency, show the missing dependency
   and exact proposed command, then wait for approval.
8. Before a command expected to exceed approximately two minutes—including
   the first gem5 build—show the command, expected purpose, and available
   disk/RAM evidence, then wait for approval.
9. Ask before deleting, moving, or overwriting any file; editing an existing
   source or documentation file also requires a clear explanation of why it
   is necessary. Prefer a fresh project copy and new result paths.
10. Never run git reset --hard, force push, rebase, or publish anything.
11. Do not modify the scientific method merely to make a run pass. Preserve:
    - gem5 v25.1.0.1, commit c8222cc67a399bfc01e8658dd14b30d5bfd634f9;
    - RISC-V syscall-emulation mode;
    - two TimingSimpleCPU cores at 2 GHz;
    - private L1 caches and one shared 256 KiB, 16-way LLC;
    - the supplied RequestorPartitionManager extension;
    - the fixed public AES key, plaintext seed, and 32-active/32-idle labels;
    - symmetric 4 KiB L1D caches for the redesigned contention sweep;
    - one monitor binary with an explicit depth `A`, matched unpartitioned
      controls for A=1 through 8, and `A/(16-A)` treatments;
    - direct logical-to-physical LLC-set rotation validation;
    - 64 two-million-cycle contention intervals;
    - maximum per-set SNR with 10,000 shuffled-label maxima, seed 5764, and
      the existing alpha-0.05 decision rule.
12. This is simulator-only defensive research. Do not run the monitor or AES
    workload on physical hardware, add key recovery, infer key bytes, scan
    unrelated processes, or connect to unauthorized systems.
13. Do not claim a command passed unless you ran it and read its real output.
    Clearly label measured, simulated, and derived quantities. Never invent
    results, timings, paths, versions, citations, or successful checks.

## Execution procedure

### Phase A — topology and resource discovery

Perform read-only checks first. Report:

- OS/kernel and whether this is native Linux, WSL2, or remote Linux.
- Current project root and whether AGENTS.md and RUNBOOK.md are present.
- CPU count, available RAM, and free space on the proposed gem5 filesystem.
- Existing versions or absence of git, Python, SCons, C/C++ compiler,
  riscv64-linux-gnu-gcc, NumPy, and matplotlib.
- Whether ~/eel5764/gem5 or the selected remote gem5 directory already exists.
- Whether project result directories already exist.

Do not install, copy, delete, build, or simulate during discovery. If an
existing gem5 tree or result directory is found, inspect it without changing
it and explain how it affects the reproduction plan.

### CHECKPOINT A

Present the discovered topology, exact paths, resources, missing dependencies,
and proposed commands. Wait for approval for any dependency installation,
project transfer, or long build.

### Phase B — obtain and build gem5

After approval:

1. Follow RUNBOOK.md steps 1–4 for the detected topology.
2. Obtain exactly gem5 tag v25.1.0.1 and verify commit
   c8222cc67a399bfc01e8658dd14b30d5bfd634f9.
3. Keep the gem5 source unmodified. Link or reference the supplied gem5_ext/
   through EXTRAS as documented.
4. Build only build/RISCV/gem5.opt.
5. Verify that RequestorPartitionManager imports successfully.

If the selected compiler differs from the recorded GCC 15.2 environment,
record the difference; do not claim byte-identical binaries.

### CHECKPOINT B

Report exact checkout tag/commit, build command, exit status, relevant warnings,
binary path, and extension-import output. Stop on any failed verification.

### Phase C — build and test workloads

1. Run workloads/build.sh inside the project.
2. Verify all seven RISC-V binaries named in RUNBOOK.md.
3. Confirm no vector instructions, gp-relative references, or undefined libc
   symbols using the documented checks.
4. Run the complete Python unit-test suite and C/build checks documented by
   the project.

### CHECKPOINT C

Report compiler version, build output, binary formats, verification counts,
and test results. Do not simulate if workload validation fails.

### Phase D — capacity/isolation sweep

1. Confirm whether results/UNPARTITIONED and results/1-15 through results/8-8
   already exist. Never replace them without explicit approval.
2. On a fresh result copy, run scripts/run_sweep.sh.
3. Run analysis/analyze.py --require-all.
4. Require zero isolation violations, zero unmapped lookups, zero address
   conflicts, and direct sharing evidence in the unpartitioned control.

### CHECKPOINT D

Report all nine IPC/miss-rate rows, direct way-occupancy validation, output
paths, and any differences from the reference results. Values that differ are
new measurements, not errors to be silently replaced.

### Phase E — corrected depth-matched AES-contention sweep

1. Choose a new result root. Never reuse or replace
   `results/contention-l1d4k/`; that fixed-16-line sweep is an invalidated
   historical pilot.
2. Run `scripts/run_corrected_contention_sweep.sh`. It launches the original
   A=16 unpartitioned control and eight matched pairs: unpartitioned A-line
   control followed by `A/(16-A)` treatment for A=1 through 8.
3. After every case, require 16,384 probe records, two stats blocks, workload
   completion markers, and a valid `analysis.json`.
4. Require every matched control to be distinguishable before its treatment
   runs. If a control fails, preserve outputs and stop; do not tune parameters.
5. For all cases require `PASS congruent`, nonzero checked probe addresses,
   zero missing virtual addresses, and zero set-mapping mismatches.
6. For partitioned treatments additionally require `PASS disjoint`, zero
   isolation violations, zero unmapped lookups, and zero address conflicts.
7. Run `analysis/summarize_matched_contention.py --results-root <new-root>`.

### CHECKPOINT E

Report the observed and null SNR, p-value, decision, IPC, and LLC miss rate for
all eight matched pairs; the first tested indistinguishable split; whether a
stable collapse point exists; per-core matched-control costs; physical-set and
way-isolation evidence; CSV and figure paths; and all preserved failed
attempts. Never call the first suppression a threshold when a later split is
distinguishable.

### Phase F — final verification and handoff

1. Run the complete test suite again.
2. Verify every expected result file, record count, stats-block count, CSV row,
   and figure exists and is nonempty.
3. Compare new results with reference results without overwriting either set.
4. Explain threats to validity: simulation versus silicon, deterministic
   inputs, one run per split, timing-model fidelity, finite run length, and
   shared resources outside LLC data-way partitioning.
5. Do not edit REPORT.md to replace its reference measurements unless the
   user explicitly asks for a new-machine report. If asked, cite only the new
   machine's real artifacts.

## Exact response format

For every completed phase, respond in this order:

1. Files created or changed, with paths and a one-line description.
2. Exact commands executed.
3. Real output and exit status.
4. Measured or derived results, explicitly labelled.
5. Differences from the reference machine.
6. What remains unverified.
7. The next required approval or the next safe phase.

Use `DONE <phase> — <one-line verified result>` only when every required check
for that phase passed. Never print DONE for a partial or inferred result.

## Failure handling

- Preserve failed build and simulation outputs; do not delete them to make a
  later attempt look clean.
- Diagnose from the earliest concrete error and show it before proposing a
  fix.
- If network access, sudo, SSH, storage, RAM, compiler availability, or Codex
  tool access blocks progress, report the exact blocker and the minimal user
  action required.
- If a remote connection drops, inspect the remote process and output state
  before resuming. Do not automatically launch a duplicate gem5 process.
- If the environment differs materially from the validated method, stop and
  ask rather than silently adapting the experiment.
```

### 2. Requested variants

None requested. This is the Codex-specific version; no Claude or universal
variant is included.

### 3. Assumptions and unresolved items

Confirmed:

- The project may run on native Linux, WSL2, or an authorized remote Linux
  server.
- Native Windows or macOS may be the client computer but not the direct gem5
  build target.
- The project directory will be supplied to Codex before the prompt is used.

Resolved at runtime by Codex:

- Exact project and gem5 paths.
- Whether Codex executes directly on the Linux host or uses an existing SSH
  connection.
- Which dependencies are already installed.
- Whether existing results require a fresh project copy or different output
  location.

The prompt cannot guarantee identical host timings, compiler-generated binary
hashes, or results across different gem5/compiler environments. Codex must
measure and report differences rather than conceal them.

### 4. Material adaptation notes

This prompt uses Codex-oriented Markdown phases, checkpoints, shell/file
actions, and an exact progress-report contract. It does not assume a specific
Codex model, desktop application version, remote-host feature, or automatic
approval behavior. Remote execution is described in terms of observable
access—Codex already running on Linux or an existing authorized SSH path—so
the scientific workflow remains usable across Codex interfaces.

### 5. Relevant verified settings

No Codex model or reasoning setting is required or verified; use the interface
defaults. The prompt assumes only that the selected Codex environment can read
the project and, after user approval, execute shell commands on the chosen
Linux target. OpenAI's current self-hosted-environment documentation confirms
that a Codex execution environment may be a laptop or remote sandbox, but
self-hosted Agents API setup is optional and not required by this runbook.

### 6. Test checklist for the prompt

Before trusting this handoff on another machine, confirm the Codex session
handles these cases correctly:

| Case | Observable pass condition |
|---|---|
| Native Linux workstation | Selects Linux-native gem5/project paths and never invokes WSL |
| Windows laptop with WSL2 | Keeps gem5 under the WSL filesystem and correctly quotes the mounted project path |
| Codex already on remote Linux | Uses remote-local paths and does not attempt a second SSH hop |
| Laptop Codex with SSH alias | Confirms authorization and connection, never requests or prints credentials |
| Native Windows/macOS without Linux | Stops as unsupported and proposes no unapproved workaround |
| Missing dependency | Shows evidence and exact install command, then waits |
| Existing gem5 checkout | Inspects tag/commit and preserves it rather than recloning blindly |
| Existing result directory | Refuses to overwrite it and requests a fresh location |
| Build expected over two minutes | Shows resource evidence and waits for approval before starting |
| Failed simulation | Preserves the failed directory and reports the earliest error |
| Different numerical result | Labels it as a new measurement and preserves both new and reference evidence |
| Successful reproduction | Produces nine valid rows for each sweep, verified figures, test output, and an evidence-backed final handoff |

---

## 15. Quick reference

Full reproduction from a clean machine:

```bash
# one-time setup (~20 min, mostly the build)
sudo apt-get update && sudo apt-get install -y scons python3-dev m4 \
  zlib1g-dev libprotobuf-dev protobuf-compiler libgoogle-perftools-dev \
  libboost-all-dev pkg-config libhdf5-serial-dev libpng-dev libelf-dev \
  python3-numpy python3-matplotlib
mkdir -p ~/eel5764 && cd ~/eel5764
git clone --depth 1 --branch v25.1.0.1 https://github.com/gem5/gem5.git gem5
export PROJ="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"
ln -sfn "$PROJ/gem5_ext" ~/eel5764/gem5_ext
cd ~/eel5764/gem5 && scons build/RISCV/gem5.opt -j14 EXTRAS=$HOME/eel5764/gem5_ext

# capacity/isolation experiment (~1 min)
cd "$PROJ"
sh workloads/build.sh
bash scripts/run_sweep.sh
python3 analysis/analyze.py --require-all

# corrected monitor/AES experiment (17 fresh gem5 processes)
bash scripts/run_corrected_contention_sweep.sh
python3 analysis/summarize_matched_contention.py \
  --results-root results/contention-corrected-20261001-v2

# final record-free v3 study (50 fresh gem5 processes, ~45 min; see §10C)
python3 scripts/run_repeated_contention_sweep_v3.py \
  --results-root "results/updated run/sweep-v3-repro"
```

### Project file map

| Path | Purpose |
|---|---|
| `gem5_ext/` | `RequestorPartitionManager` — supplies the per-core partition IDs stock gem5 lacks on RISC-V, plus the `wayOccupancy` statistics used as isolation evidence |
| `configs/run.py` | The two-core isolation/cost system. All tunables in one `CONFIG` dict at the top |
| `configs/run_contention.py` | Finite monitor/AES system with selectable 16 KiB pilot or 4 KiB redesigned profile and a measurement-only first stats dump |
| `workloads/` | Isolation kernels, monitor, public T-table AES workload, separately timed redesigned binaries, shared schedule, build script, and README |
| `scripts/run_sweep.sh` | Runs the nine capacity/isolation configurations; replaces only the selected capacity result directories |
| `scripts/run_contention_control.sh` | Runs one validated contention split in baseline or `l1d4k` mode; never replaces a completed result |
| `scripts/run_contention_sweep.sh` | Runs selected or all nine 4 KiB contention configurations and analyzes each immediately |
| `scripts/run_corrected_contention_sweep.sh` | Runs the A=16 control plus eight depth-matched control/treatment pairs into a separate immutable root |
| `scripts/run_repeated_contention_sweep.py` | Runs the predeclared three-seed plan: 48 matched cases plus two excluded diagnostics, exactly 50 gem5 processes |
| `analysis/analyze.py` | Parses capacity-study stats, applies isolation rules, writes `results/summary.csv` and capacity figures |
| `analysis/analyze_contention.py` | Validates 16,384 probe records, applies the corrected fixed-seed null test, and checks direct way occupancy |
| `analysis/summarize_contention.py` | Requires all nine contention analyses, writes the contention CSV, selects the collapse point, and generates PDF figures |
| `analysis/summarize_matched_contention.py` | Requires eight valid matched pairs, writes the corrected CSV and figures, and distinguishes first suppression from stable collapse |
| `analysis/summarize_repeated_contention.py` | Combines three seed-specific p-values with Fisher's method, applies Holm correction across allocations, aggregates performance, and writes repeated-study figures |
| `results/<split>/` | Per-configuration outputs |
| `results/summary.csv` | The parsed results table |
| `results/figures/` | `tradeoff` and `occupancy`, as PDF and 300 dpi PNG |
| `results/pilot/`, `results/validation/` | Archived pilot runs and the reproducibility check |
| `results/contention/UNPARTITIONED/` | Preserved original 16 KiB failed contention pilot |
| `results/contention-l1d4k/<split>/` | Redesigned raw logs, stats, metadata, hashes, and per-split `analysis.json` |
| `results/contention-l1d4k/summary.csv` | Complete nine-row contention security/performance table |
| `results/contention-l1d4k/*.{pdf,png}` | SNR and combined trade-off figures |
| `results/contention-corrected-20261001-v2/` | Corrected 17-run dataset, matched summary, physical-set evidence, and figures |
| `results/contention-repeated-20261001/` | October 1 repeated dataset (v1 monitor). Its conclusion is withdrawn; never modify |
| `scripts/run_repeated_contention_sweep_v2.py`, `_v3.py`, `scripts/run_rerun_v3.py` | Record-free v2 sweep, final v3 sweep, and D2 rerun runners (§10C) |
| `analysis/summarize_repeated_contention_v2.py`, `summarize_rerun_v3.py`, `summarize_sweep_v3.py` | v2, D2-combined, and final v3 decision rules |
| `analysis/posthoc_hit_only_20261011.py`, `analysis/compare_v1_v2.py` | Post-hoc analysis of the October 1 data; v1-vs-v2 comparison |
| `scripts/build_updated_reports.py`, `scripts/docx_report_builder.py` | Build both `_Updated.docx` reports from the v3 results |
| `results/posthoc-20261011/` | Post-hoc hit-only analysis of the October 1 data |
| `results/updated run/sweep-v3/` | **Final results:** `summary_v3.csv`, `summary_v3.json`, `per_seed_matched_v3.csv`, `repeated_v3.png` |
| `results/updated run/{smoke,sweep,rerun-7-9-8-8,comparison,investigation-set191,repro-v3}/` | Supporting records: v2 smoke test and sweep, D2 rerun, comparison, set-191 trace evidence, and the validation re-simulation |
| `REPORT.md` | Preserved historical report for the invalid fixed-16-line pilot |
| `REPORT_CORRECTED_20261001.md` | Preserved corrected single-seed report |
| `REPORT_REPEATED_20261001.md` | October 1 report. Its conclusion is withdrawn, and a note at the top says so |
| `REPORT_UPDATED_RUN_20261011.md` | **Main technical report.** §12 is the final v3 result |
| `PREREGISTRATION_V2_20261011.md`, `APPENDIX_POSTHOC_20261011.md` | Decision rules, hashes, and deviations D1–D3; post-hoc appendix |
| `VALIDATION_20261014.md`, `HANDOFF.md` | Independent validation of every step; current project state |
| `Group18_EEL5764_Final_Project_Report_Updated.docx`, `..._Expanded_Updated.docx` | Submission reports built from the v3 results |
| `Group18_EEL5764_Final_Project_Proposal_Aligned.docx` | Current proposal aligned exactly with the 50-process methodology |
| `SUBMISSION_AUDIT_20261001.md` | Final claim, artifact, test, and submission-set audit |
| Earlier proposal DOCX/PDF files | Preserved historical proposal revisions; do not use as the current proposal |

### Key facts for citation

| Item | Value |
|---|---|
| gem5 version | v25.1.0.1, commit `c8222cc67a399bfc01e8658dd14b30d5bfd634f9` |
| ISA / mode | RISC-V, syscall emulation (SE) |
| CPU model | 2 × `TimingSimpleCPU` @ 2 GHz |
| LLC | 256 KiB, 16-way, 64 B lines, 256 sets, LRU |
| Capacity measurement window | 1 ms warm-up, then 4 ms in 8 segments |
| Redesigned contention window | 1 ms warm-up, then 64 × 2,000,000 CPU cycles (64 ms total) |
| Contention statistic | Maximum per-set SNR; 10,000 shuffled-label maxima; seed 5764; alpha 0.05 |
| Repeated plaintext seeds | `0x5764A5E5`, `0x5764A5E6`, `0x5764A5E7` |
| Repeated inference | Fisher combination across seeds; Holm correction across eight allocations; alpha 0.05 |
| Final inference (v3) | Max-set SNR + hit-only mean; Fisher across seeds; Holm across 16 tests per arm; self-eviction gate; ±0.02 cycles/line equivalence margin |
| Stable collapse point | **None.** All eight allocations are distinguishable (v3 sweep). The October 1 `1/15` result is withdrawn |
| Retained hit-timing signal | 100% at `1/15`; 70–85% at `2/14`–`8/8` |
| Mean matched change at `1/15` (v3) | Monitor IPC −0.0085%; AES cycles/encryption 0.000%; monitor LLC miss rate +0.26 pp (a one-time refill at the start of measurement) |
| Host compiler | GCC 15.2.0 (gem5 officially supports ≤ 14.2) |
