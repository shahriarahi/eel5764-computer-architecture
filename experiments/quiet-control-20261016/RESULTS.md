# Quiet-victim diagnostic results — October 16, 2026

Four authorized simulations completed: two positive replays and two quiet-victim
controls. These are gem5 simulation measurements, not hardware measurements.
All 6,694 protected preexisting files match the pre-control snapshot.

## Files added

All source additions are in this directory; no existing tracked source was edited.

- `PLAN.md`: design and analysis declared before new simulations.
- `quiet_victim.c`: startup AES self-test followed by a continuous warmed polling
  loop; no AES encryptions during measurement.
- `quiet_adapter.py`: substitutes only the victim executable before instantiation;
  preserves original argv[0] and records the actual executable/hash separately.
- `run_control.py`: exclusive output roots, 240-second per-case timeout, replay
  comparison, and mandatory per-interval quiet/scheduler gates.
- `test_control.py`: five tests of quiet interval validity.
- `analyze_quiet.py`: unchanged project statistical functions, diagnostic output
  in the new `analysis` directory.
- `preserve.py`, `preservation-before.json`: pre/post fingerprints for existing files.
- `quiet_victim`, `build.json`, `build.log`, `quiet_victim.disassembly.txt`: new
  executable, exact build command/hash, compiler output, and instruction listing.
- `analysis/A1.json`, `analysis/A8.json`, `analysis/summary.json`: measured diagnostic
  results; endpoint-adjusted p-values are in the summary.

New raw runs are under the ORIGINAL workspace's `results/updated run/tdma-np0`
(replays) and `results/updated run/tdma-nc0` (quiet), each with
`seed-5764a5e5/1-15` and `seed-5764a5e5/8-8`. Each retains command, output,
statistics, probe bytes, configuration, and validation. Existing `tdma-*` runs
were neither overwritten nor moved. Nothing was committed, pushed, or merged.

## Execution and validity

| Case | Wall seconds | Outcome |
|---|---:|---|
| Replay 1/15 | 49.643 | Byte-identical probes; matching simulated statistics |
| Replay 8/8 | 50.375 | Byte-identical probes; matching simulated statistics |
| Quiet 1/15 | 48.858 | All 64 quiet-interval gates pass |
| Quiet 8/8 | 47.322 | All 64 quiet-interval gates pass |

Both quiet cases have 16,384 valid records, 65 statistics blocks, congruent probe
mapping, 64/64 disjoint-way snapshots, positive monitor grants, zero victim
grants in every measured interval, and zero scheduler violations. Both report
zero encryptions. Missing supplemental victim demand counters are recorded as
null, not treated as zero.

Disassembly at 0x10456–0x1045a contains only `rdcycle a5` and a register branch;
both instructions fit one cache line. The same loop spans warmup and the full
measurement interval. Existing compiler returned exit 0 with no warnings.

All four command manifests match isolated gem5 SHA-256:
`5a540aed00f58ba43fe94065ecb5cd714cde043c670b38c240ded938e50070a5`.

## Simulated timing diagnostics

Values are nominal-active minus nominal-idle CPU cycles per probed line. Labels
do not denote AES activity in these quiet cases. One seed and one fixed schedule.

| Allocation | Hit-only difference | Hit-only 90% bootstrap CI | All-walk difference | Max-set Holm p | Hit-only Holm p |
|---|---:|---|---:|---:|---:|
| 1/15 | -0.0016115211 | [-0.0048345634, 0] | -0.0384521484 | 1.0 | 1.0 |
| 8/8 | -0.0002014401 | [-0.0006043204, 0] | -0.0209197998 | 1.0 | 1.0 |

Both hit-only intervals lie strictly within the declared +/-0.02 mean-effect
margin. Neither declared test detects a nominal-label difference after the
separate two-endpoint Holm corrections. This does not establish equality of
timing distributions. All-walk effects are separately reported and were not
subject to the hit-only mean-equivalence gate.

The hit-only interval means are constant across intervals 1–63; only interval 0
differs, and its nominal label is idle. For 1/15, the first mean is
33.06719367588933 cycles/walk versus 33.015625 thereafter; for 8/8 it is
257.0671936758893 versus 257.015625. This accounts arithmetically for the small
negative hit-only differences. No interval was excluded from declared analysis.
The physical source of that first-interval difference is not established.

## Commands and actual verification output

Executed from the original Windows workspace (each simulator child had a
240-second timeout in the runner):

```powershell
wsl.exe --cd '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture' --exec python3 -B '.codex-tmp/tdma-worktree/experiments/quiet-control-20261016/run_control.py' --baseline-root '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture' --phase replay
wsl.exe --cd '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture' --exec python3 -B '.codex-tmp/tdma-worktree/experiments/quiet-control-20261016/run_control.py' --baseline-root '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture' --phase quiet
```

Both commands exited 0 and printed PASS for both endpoints. Complete validation
objects are retained in each new case's `validation.json`.

Analysis executed as this child command under `subprocess.run(..., check=True,
timeout=110)` in WSL; it exited 0 in approximately 1.8 seconds:

```text
python3 -B .codex-tmp/tdma-worktree/experiments/quiet-control-20261016/analyze_quiet.py --baseline-root '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture'
```

Actual analysis output includes:

```text
ANALYZED 1 all_walk_delta -0.0384521484375
ANALYZED 8 all_walk_delta -0.0209197998046875
```

Executed from the experimental worktree:

```powershell
python -B experiments\quiet-control-20261016\preserve.py check
python -B -m unittest discover -s tests -p 'test_*.py'
python -B -m unittest discover -s experiments\tdma -p 'test_*.py'
```

Actual outputs:

```text
PRESERVED 6694 files against pre-control snapshot
PREEXISTING_FROZEN_MISMATCHES ["project explanation.md"]
Ran 70 tests in 0.305s
OK
Ran 10 tests in 0.015s
OK
```

New gate tests, executed from the original workspace:

```powershell
python -B -m unittest discover -s '.codex-tmp\tdma-worktree\experiments\quiet-control-20261016' -p test_control.py
```

Actual final output: `Ran 5 tests in 0.000s`, `OK`. The initial test invocation
preceded the new runner and failed with `ModuleNotFoundError: No module named
'run_control'`; the completed runner then passed all five tests.

## Limits and next step

The earlier positive hit-only residual was not reproduced by the quiet control.
This weakens an explanation based solely on the unchanged monitor and labels
under these conditions; it does not identify a response queue or any other
victim-dependent shared path as causal. Startup layout differs between binaries.
Zero new victim grants does not prove every startup transaction had drained:
the existing executable lacks a per-domain outstanding-completion counter.

The next investigation should correlate request admission, LLC-ready scheduling,
response enqueue/retry, and CPU delivery in the isolated gem5 source, followed by
a trace-on/off perturbation check. Verified source hooks include cache/base.cc:342,
cache/cache.cc:907, packet_queue.cc:107/204/208/216, coherent_xbar.cc:488/534,
and cpu/simple/timing.cc:911/1141. No tracing instrumentation or defense was added
in this experiment. No additional seeds, allocation sweep, hardware tests, or
held-out attacker were run.

The older preservation-manifest mismatch in `project explanation.md` predates
this work; its current bytes were also preserved by the new snapshot. The
original WSL baseline executable was outside this approval and was not audited.
