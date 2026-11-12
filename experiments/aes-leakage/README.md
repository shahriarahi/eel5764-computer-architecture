# AES leakage attribution (follow-up experiment)

EEL 5764, Group 18. A simulator-only follow-up to "Evaluating LLC Way
Partitioning as a Defense Against Simulated Cross-Core AES Cache Contention".
The submitted paper measured **whether** AES activity is visible to a monitor on
another core. This experiment asks **what** the visible signal encodes, and
whether each defense removes data-dependent leakage or only the activity signal.

**Status (Phases A to D complete):** the code, builds, adapter, analysis and tests
exist and pass, the tracing gem5 is built and passes the byte-identical guard, the
20-window smoke run (P0) passes after one pre-data change (D0: the victim's scrub
walk is 4 KiB), and the 2,000-window positive control (P1) passes its gate: with no
partition and 16 monitor ways, the signal carries plaintext combined with the key.
No defense has been evaluated yet; Phase E is next. See `progress.md`.

## Scope, and how it relates to the accepted proposal

* Everything runs inside gem5 v25.1.0.1 (RISC-V, syscall-emulation). No hardware,
  network, service or third-party crypto library is involved. The AES is the
  repository's own educational T-table code; the key
  `f1e2d3c4b5a69788796a5b4c3d2e1f10` is a fixed **public** test constant compiled
  into the workload and printed in its output, and the plaintexts are public and
  deterministic. The monitor times only its **own** memory, as in the paper.
* **This work goes beyond the accepted proposal.** The proposal's bounded
  objective is "activity detection and performance only"; it "does not recover or
  guess key bytes". Attributing the signal to plaintext, plaintext-with-key or
  ciphertext extends that scope, so the final paper should list it under changes
  from the proposal.
* **The analysis does not score key guesses.** An earlier plan ranked the true key
  among 16 or 256 candidates per byte. That was dropped: the analysis uses the
  known public key and compares three fixed hypotheses per round (`p ^ k`, `p`
  only, a shuffled control). "Plaintext only" is the key-nibble-0 case, so this
  still separates plaintext from plaintext-plus-key.
* The original study is untouched: nothing outside `experiments/aes-leakage/`
  changes. `preserve.py` checks that, including commits since the branch point.

## One window

One **window** is the unit of observation: the monitor primes its own lines, the
AES workload performs exactly one encryption, the monitor re-times its lines. Each
window is labelled with its own public plaintext. Offsets are CPU cycles from the
window start `w0 = T0 + j * W` (constants in `leak_schedule.h`):

| Event | Offset | Cycles |
|---|---|---|
| victim scrubs its private cache (variants with scrub) | 0 | |
| monitor primes (deadline: before the encryption) | `OFF_PRIME` | 65,536 |
| victim encrypts (deadline: `OFF_ENC_END`) | `OFF_ENC` | 524,288 |
| encryption budget ends | `OFF_ENC_END` | 589,824 |
| monitor probes (deadline: before the next window) | `OFF_PROBE` | 593,920 |
| next window | `W` | 1,048,576 |

`T0` = 2,000,000 cycles (the 1e9-tick warm-up at 2 GHz). A deadline miss makes
the process exit with status 2 and an error line.

## Files

| File | Purpose |
|---|---|
| `README.md` | this overview and the commands |
| `DISCUSSION_BRIEF.md` | self-contained status brief for a reader who will not run anything |
| `PREREGISTRATION_DRAFT.md` | hypotheses, N, seeds, decision rule (frozen at `675c047`; deviations in its section 11) |
| `progress.md` | ledger: what was done, with evidence |
| `gem5_build.md` | Phase B commands: build the tracing gem5 and run the guard |
| `leak_schedule.h` | window schedule, public key, splitmix64 plaintext stream, TVLA mode, fake clock |
| `leak_params.py` | reads `leak_schedule.h` so Python cannot drift from the C schedule |
| `aes_leak_ext.c` | `#include`s the frozen `workloads/aes_ttable.c`; adds a round-1-only lookup mode |
| `aes_leak_ext.h` | prototype of that mode |
| `victim_leak.c` | the AES workload (one encryption per window) |
| `monitor_leak.c` | the monitor (one prime and one probe per window, one `writev`) |
| `build.sh` | builds six RISC-V binaries for a given `N_WIN` |
| `write_manifest.py` | writes `build_manifest.json` (sha256 and `nm` layout) |
| `build/n2000/` | binaries and manifest for 2,000 windows |
| `build/n20/` | binaries and manifest for 20 windows (the P0 smoke run) |
| `gem5_ext/` | copy of the frozen extension plus optional victim-table tracing |
| `victim_table_trace.patch` | the reference patch, applied unchanged to make `gem5_ext/` |
| `gem5_syntax_check.sh` | syntax-only compile of the tracing source against real gem5 headers |
| `run_leakage.py` | gem5 configuration adapter around the frozen `configs/run_contention.py` |
| `analysis/aes_leak_analysis.py` | run-directory analysis, synthetic generator, selftest |
| `analysis/power_synth.py` | synthetic power and false-positive tables |
| `analysis/leak_followup.py` | differential test, raw-cycle effect size with permutation p-value, collision-count test (deviations D1, D2) |
| `run_arm.sh` | launches one gem5 run with checked arguments (`DRY_RUN=1` prints the command only) |
| `run_batch.sh` | runs the runs listed in a file under `batches/`, a few in parallel |
| `run_leakage_defense.py` | wrapper that adds request time slots and per-domain LLC response queues (deviation D4) |
| `synthetic_power.md` | output of that script (synthetic data, not gem5) |
| `preserve.py` | sha256 of every file here and a check that nothing else changed |
| `preservation.json` | its manifest |
| `tests/` | the test suite |

Binaries: `victim_leak_{r1,full}_{scrub,noscrub}` (round-1 lookups only or full
AES; with or without a 4 KiB private-cache walk before each encryption, see
deviation D0 in `PREREGISTRATION_DRAFT.md`),
`victim_leak_tvla` (full AES with scrub, even windows use a fixed plaintext) and
`monitor_leak`. The tables are 68 contiguous 64-byte lines (sbox 4, te0..te3 16
each) across two 4 KiB pages; the physical LLC set of each line is measured by the
simulator, not assumed.

## Commands

All commands run inside WSL2 `Ubuntu-26.04` from `experiments/aes-leakage/`
unless noted. Tests need `riscv64-linux-gnu-gcc`, `qemu-riscv64`, `numpy` and
`scipy`; a test that needs a missing tool is skipped with a message naming it.

```bash
python3 -B -m unittest discover -s tests -t .          # whole suite
python3 -B analysis/aes_leak_analysis.py selftest      # AES / PRNG known answers + synthetic end-to-end
python3 -B analysis/aes_leak_analysis.py synth --run-dir /tmp/fake --n 2000
python3 -B analysis/aes_leak_analysis.py analyze --run-dir /tmp/fake
sh build.sh 2000                                       # rebuild build/n2000 (N_WIN = 2000)
bash gem5_syntax_check.sh                              # pre-build type check, no build
python3 -B analysis/power_synth.py --quick             # synthetic power table (add --out FILE)
```

Run `preserve.py` with a git that can open this worktree (it was created by
Windows git): Windows Python from Git Bash or PowerShell.

```bash
python preserve.py capture     # after the final commit of a phase
python preserve.py verify
```

## Phases

| Phase | What | Status |
|---|---|---|
| A | code, builds, adapter, analysis, tests (no gem5) | done, see `progress.md` |
| B | build the tracing gem5 and run the byte-identical guard | done 2026-11-12, guard PASS, see `progress.md` |
| C | P0 smoke run: 20 windows | done 2026-11-12: attempt 1 failed a deadline, fixed (D0), attempt 2 passed, see `progress.md` |
| D | P1 positive control: 2,000 windows | done 2026-11-12: gate G1 passed, see `progress.md` |
| E | P2 to P4 per `PREREGISTRATION_DRAFT.md` | after D |

Phase C needs the Phase B guard to have passed; it has.

### Phase C: P0 (20 windows, no partition, 16 monitor ways, round-1 lookups)

`-r -e` is required: without it gem5 does not write `simout.txt`, which the
analysis reads.

Already run: `runs/p0-r1-scrub-n20` is attempt 1 (it failed `prime_deadline`, kept as
evidence) and `runs/p0b-r1-scrub-n20` is attempt 2 (passed). To repeat it, use a new
directory name, as below.

```bash
WT='/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture/.codex-tmp/aes-leakage-worktree'
cd "$WT" && mkdir -p experiments/aes-leakage/runs
RUN=experiments/aes-leakage/runs/p0c-r1-scrub-n20
~/eel5764/gem5-leak/build/RISCV/gem5.opt -r -e --debug-flags=VictimTable --debug-file=victim_table.trace -d "$RUN" experiments/aes-leakage/run_leakage.py --victim-variant r1-scrub --build-dir experiments/aes-leakage/build/n20 --split off --monitor-ways 16
python3 -B experiments/aes-leakage/analysis/aes_leak_analysis.py analyze --run-dir "$RUN" --out-json "$RUN.analysis.json" --out-md "$RUN.analysis.md"
```

The simulation itself should take well under a minute (about 25 million
simulated cycles at the roughly 3 million cycles per second measured on this
host for earlier runs; an estimate, not a measurement of this experiment).

What P0 must show (these are the gate conditions, not results):

* gem5 exits normally; `simout.txt` has `victim aes_self_test=PASS`, the
  `victim leak_format=v1 ...` line, the matching `pt_checksum`, and
  `monitor status=PASS records=5120`, and no `error=` line (a deadline miss
  prints one and exits with status 2);
* `analyze` ends with `RUN CHECKS: PASS`, which includes: simout header equals
  `leak_config.json`, the victim checksum equals the Python one, and no
  `victimTableMissingVaddr`;
* `analyze` does not stop with an error: all 68 table lines are mapped to
  distinct logical sets and `victimTableSetMismatches` is 0;
* the ground-truth block shows fills inside the AES phase and none outside it
  after the warm-up. The trace records LLC allocations only, so how many of the
  touched lines appear as fills depends on the monitor evicting them; for an
  unpartitioned 16-way monitor I expect most, but that is an expectation, not a
  claim.

Send me `p0-r1-scrub-n20.analysis.md`, `simout.txt`, and the first lines of
`stats.txt` and `victim_table.trace`.

### Phase D: P1 (2,000 windows), only after P0 passes

Already run on 2026-11-12 (`runs/p1-r1-scrub-n2000`; it took 10 min 59 s). To repeat
it, use a new directory name.

```bash
RUN=experiments/aes-leakage/runs/p1b-r1-scrub-n2000
~/eel5764/gem5-leak/build/RISCV/gem5.opt -r -e --debug-flags=VictimTable --debug-file=victim_table.trace -d "$RUN" experiments/aes-leakage/run_leakage.py --victim-variant r1-scrub --build-dir experiments/aes-leakage/build/n2000 --split off --monitor-ways 16
python3 -B experiments/aes-leakage/analysis/aes_leak_analysis.py analyze --run-dir "$RUN" --nperm 20 --out-json "$RUN.analysis.json" --out-md "$RUN.analysis.md"
```

Estimated about 12 minutes (2,000 windows of 1,048,576 cycles at about 3 million
cycles per second; an estimate). The preregistered P1 gate: `p_xor_k` significant
on 16/16 bytes, `p_only` and `shuffled` on 0/16, otherwise stop and debug.

## Reading the output

`analyze` prints a Markdown summary (also `--out-md`) and writes JSON
(`--out-json`). It never writes into the run directory. Exit status: 0 all run
checks pass; 1 a run check failed (results are still printed); 2 the run cannot be
attributed (unmapped table lines, bad probe file, ...).

* **Attribution (location-aware)** is the main result: for each byte and each
  hypothesis, does the hypothesis's predicted table line explain which monitor
  set is slower. Holm correction is applied over all 96 tests.
* **Detection (location-free)** says that a byte matters somewhere, but cannot
  tell `p` from `p ^ k`: XOR with a constant only relabels classes.
* **Ground truth** compares simulator-side LLC fills of the table lines with the
  lines the encryption algorithmically touches.

## Caveats (also in the preregistration)

* **Detection table needs windows.** Its ANOVA has 16 classes for the Te tables, so
  below about 160 windows it is flagged unreliable (the shuffled control comes out
  significant in a 20-window run). Only the attribution table feeds the decision rule.
* **State, not contention.** In this schedule the encryption ends at least 4,096
  cycles before the probe starts and the monitor performs no memory access in
  between, so no victim memory traffic overlaps a monitor access. The windows
  measure cache-state leakage. The paper's crossbar timing channel needs
  concurrent traffic and cannot appear here.
* **The trace sees fills only.** gem5 calls the partition manager when the LLC
  allocates a block (`base.cc:1695`, `tags/base.cc:115`,
  `tags/base_set_assoc.hh:208`), so a line that stays resident in the LLC leaves
  no trace.
* The analysis SNR is a variance ratio (Mangard); it is not the proposal's
  `|mean difference| / pooled SD`.
* `synthetic_power.md` comes from a synthetic generator, not from gem5.
* Simulated, not hardware: every statement here concerns this simulated
  configuration.
