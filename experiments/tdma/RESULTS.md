# Separate time-slot prototype: results

Completed October 15, 2026 (local time). Simulation measurements, not physical-hardware measurements.

The fixed-slot request scheduler substantially attenuated the channel but did
**not** make AES activity indistinguishable under the preregistered tests.
The accepted proposal, its original way-partitioning result, all 3,042 original
files in the preservation manifest, and the baseline gem5 executable remain
unchanged. The full A=1..8 sweep was not started because the endpoint inference
gates did not pass.

## Added implementation

- `slot_schedule.hh`: integer-tick ownership, strict future retry, one launch per slot, strict transport bound.
- `gem5-timeslot.patch`: disabled-by-default admission scheduling in the isolated coherent crossbar; grant/withholding/violation counters.
- `run_contention_tdma.py`: adapter around the unchanged original configuration; maps actual cache and MMU-walker peers to their owning domain.
- `run_structural.py`, `test_traffic.py`: real gem5 reads, idle-peer, dirty-writeback and forced-refusal tests.
- `run_pilot.py`, `validate.py`: fresh processes, new output directories, frozen fingerprints and per-interval gates.
- `summarize.py`, `verify_results.py`: unchanged original statistical functions, whole-window performance aggregation, final preservation audit.

The experiment is on branch `experiment/tdma-prototype`, in
`.codex-tmp/tdma-worktree`. The isolated gem5 source/build is
`~/eel5764/gem5-timeslot` in WSL. No merge or push was performed.

## Simulation design

Same v3 monitor, AES binary, A/(16-A) masks, cache sizes, clocks and 64 labelled
intervals as the prior study. Two alternating 4 ns slots, one request launch
per slot; unused slots remain idle. Transfers finish strictly before the next
slot. Downstream refusal or an unsupported express-snoop bypass aborts rather
than silently breaking the schedule.

There are 18 efficacy processes: 3 public seeds x 2 allocations x 3 arms
(unpartitioned, way-only, way-plus-slot). Four additional disabled guards
validate the isolated executable against original outputs. The three seeds
share one activity schedule, limiting independence and generalization.

## Active-minus-idle hit-latency effect

Values are simulated cycles per probed line, averaged over three public seeds.
Intervals are the sampling unit. CIs are the preregistered 90% bootstrap estimates.

| Allocation | Unpartitioned | Way-only | Way + slots | Scheduled 90% CI | Mean-equivalence margin +/-0.02 |
|---|---:|---:|---:|---|---|
| 1/15 | 0.347451 | 0.345984 | 0.039892 | [0.032308, 0.048177] | FAIL |
| 8/8 | 0.401036 | 0.279303 | 0.003959 | [0.002954, 0.004932] | PASS |

Relative to way-only, the signed hit-latency effect is reduced by approximately
88.5% at 1/15 and 98.6% at 8/8. These are reductions of the measured mean effect,
not security guarantees.

| Scheduled allocation | Max-set Fisher/Holm p | Hit-only Fisher/Holm p | Interpretation |
|---|---:|---:|---|
| 1/15 | 1.0 | 8.2051e-10 | Max-set does not detect; hit-only detects; mean-equivalence fails |
| 8/8 | 1.0 | 2.8232e-9 | Max-set does not detect; hit-only detects despite mean-equivalence |

The maximum-set statistic and the hit-only interval-mean statistic aggregate
different observations. Losing significance in the former does not erase the
signal detected by the latter. Both unpartitioned and way-only control cells
remain significant. All six scheduled individual runs also have significant
hit-only p-values. Combined p-values follow the declared Fisher/Holm analysis;
the shared schedule and finite permutation floor limit their interpretation.

## Simulated useful-work cost

AES throughput is completed encryptions per fixed active-cycle budget;
comparison below is against the matched way-only arm.

| Allocation | AES throughput change from adding slots |
|---|---:|
| 1/15 | -5.9723% |
| 8/8 | -5.9316% |

Whole-window per-core IPC, LLC miss rates, AES completion counts and cycles per
encryption are retained in `summary-final/summary.json` and its per-run JSONs.
IPC includes busy waiting and should not substitute for useful AES throughput.

## Exact verification and real output

Run from the experiment directory in WSL (PowerShell can invoke these through
`wsl.exe --cd <experiment-directory> --exec ...`):

```text
python3 verify_results.py --baseline-root '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture'
```

Actual output:

```text
PASS 18/18 efficacy cases: records, mapping, isolation and scheduler gates
PASS 4/4 disabled guards: identical probes and simulated statistics
PASS 12/12 fresh baseline arms: identical probes to original study
PRESERVED 3042 original files and baseline executable
PASS final summary: six cells, three public seeds each
```

From the isolated project worktree:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
Ran 70 tests in 0.038s
OK
python3 -m unittest discover -s experiments/tdma -p 'test_*.py'
Ran 10 tests in 0.020s
OK
```

C++ slot-policy command (from the experiment directory):

```text
g++ -std=c++17 -Wall -Wextra -Werror test_slot_schedule.cc -o /tmp/tdma-slot-test
/tmp/tdma-slot-test
PASS slot ownership, boundaries, strict retry, single grant, transport bound
```

Actual gem5 structural command: `python3 run_structural.py --out structural-03`.
All four tests passed. Domain 0 received exactly 250 grants with the peer busy
and with the peer quiet. The dirty-writeback test exercised 226 writeback
grants. Grant timestamps respected ownership and one launch per slot. The
forced-refusal test emitted the intended failure diagnostic. All six scheduled
efficacy runs have zero overrun, downstream-refusal and express-bypass counters;
all partitioned runs passed 64/64 disjoint-way snapshots.

The exact fresh-run and analysis commands, from the experiment directory:

```text
python3 run_pilot.py --baseline-root '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture' --phase pilot
python3 run_pilot.py --baseline-root '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture' --phase remaining
python3 summarize.py --baseline-root '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture' --out summary-final --wait-seconds 1200
```

Each process's exact arguments are also retained in `cmd.txt` and `command.json`.

Build 03 exited zero in 98.6 s after the final header change; prior build logs,
compiler details, executable hashes and commands are in `build_manifest.json`
and `build-logs/`. The original executable retains SHA-256
`c259c12e9cfafed8da49b5ac0e556719e72d6f700c13c208eaafc41f46c6730f`.

## Unverified and intentionally not expanded

- The exact source of the residual delay has not been instrumented. Scheduling
  request ingress does not isolate all later LLC service and response paths.
- No distributional classifier, adaptive attacker, key recovery or physical
  hardware evaluation was performed. Mean equivalence at 8/8 is not a proof of
  indistinguishability.
- This prototype deliberately stops on downstream refusal. General retry-
  tolerant timing isolation is not implemented or claimed.
- No slot-size tuning, additional mitigation or full allocation sweep was
  performed after seeing efficacy outcomes.
- Earlier harness/setup failures are retained separately and documented in
  `progress.md`. They are not efficacy observations or silently excluded trials.
