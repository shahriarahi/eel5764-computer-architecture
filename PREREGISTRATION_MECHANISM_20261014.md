# Preregistration: crossbar mechanism study

Written October 14, 2026, **before any mechanism data existed**. When the
hashes below were taken, no `results/updated run/mech-*` or `guard-*` folder
existed. If anything listed here changes after data exists, the change is
reported as a deviation at the end of this file.

## Why

The final v3 result (`REPORT_UPDATED_RUN_20261011.md` §12) is that way
partitioning leaves a hit-timing signal at every allocation. Its mechanism is
**inferred, not instrumented** (§12.4). This study tests one specific
mechanism.

The existing v3 statistics point to it:

- **Shared crossbar layer.** Both cores reach the LLC through one coherent
  crossbar, `system.l2bus` (`L2XBar`: 32-byte width, header latency 1, on
  the 1 GHz system clock). It has **one request layer into the LLC**
  (`reqLayer0`), shared by both cores. Its response layers are one per
  core, so they are not shared.
- **Layer load.** `reqLayer0` is busy for about 6–7% of the measurement
  window. AES's L1D sends about 2.2M packets through it, and the monitor
  sends about 0.79M.
- **No LLC blocking.** `system.llc.blockedCycles::*` = 0 in every v3 arm,
  so MSHR exhaustion does not explain the signal.
- **The size fits.** A collision costs about 1–3 crossbar cycles, which is
  about 2–6 CPU cycles. At about 7% utilization, the expected delay is about
  0.2–0.4 cycles per probed line. The measured effect is +0.28 to +0.40.

## Hypothesis and predictions

**H-xbar.** The active-minus-idle hit-latency shift is caused by queueing at
the shared crossbar request layer `system.l2bus.reqLayer0`.

**P1. Occupancy follows AES activity.** With the default crossbar,
per-interval `reqLayer0` occupancy is higher in AES-active than in AES-idle
intervals. This must hold in all four default-crossbar cells (A ∈ {1, 8} ×
{control, treatment}). Each run is tested with the same 10,000-permutation
test as the hit-only statistic; the three seeds are combined with Fisher's
method; and the four cells get a Holm correction at α = 0.05. The
active-minus-idle occupancy difference must be positive.

**P2. The effect tracks utilization.** Across the four crossbar settings,
the partitioned treatment's effect falls as mean `reqLayer0` utilization
falls. The test is a Spearman correlation ≥ 0.8 over the four settings, at
both A = 1 and A = 8.

**P3. A near-ideal crossbar removes the effect.** With the near-ideal
crossbar (setting `ide`), the treatment effect's 90% bootstrap CI lies
inside ±0.02 cycles per line, at both A = 1 and A = 8.

**Outcome:**

| Outcome | Rule |
|---|---|
| `confirmed` | P1 and P3 hold |
| `partial` | P1 holds and P3 fails, but the `ide` treatment effect is reduced by at least 50% relative to `std` at both A. The crossbar contributes, and the residual is attributed by elimination to the LLC's own shared request path (its single CPU-side port and response queue). |
| `not supported` | Anything else |

P2 is reported as supporting evidence and does not decide the outcome.

## Design

The platform and workloads are those of the v3 study, unchanged:

- gem5 v25.1.0.1; `gem5.opt` hash below;
- RISC-V SE mode, 2 × `TimingSimpleCPU` at 2 GHz;
- 4 KiB L1D and a 256 KiB 16-way LRU LLC;
- `monitor_v3_l1d4k` and `victim_l1d4k`;
- public seeds `0x5764A5E5`–`E7`;
- the same label schedule.

For each of four crossbar settings × 3 seeds × A ∈ {1, 8} × {matched
unpartitioned control, `A/(16−A)` treatment}, there are **48 fresh
processes**. All use `--stats-per-interval`, which writes one gzipped
statistics block per labelled interval (64, plus gem5's automatic final
block).

| Setting | Root | gem5 options | Request packet occupancy (no data) | Writeback occupancy (64 B) |
|---|---|---|---|---|
| `std` (default) | `mech-std` | none | 1 cycle at 1 GHz = 1 ns | 3 ns |
| `wid` | `mech-wid` | `--l2bus-width 128` | 1 ns | 2 ns |
| `clk` | `mech-clk` | `--l2bus-clock cpu` | 0.5 ns | 1.5 ns |
| `ide` (near-ideal) | `mech-ide` | `--l2bus-width 512 --l2bus-header-latency 0 --l2bus-clock cpu` | ≤ 0.5 ns (clock alignment only) | 0.5 ns |

Occupancy per packet is `clockEdge(header_latency)` plus `ceil(size/width)`
cycles for data packets (gem5 `BaseXBar::calcPacketTiming`). Changing the
crossbar also shifts the base hit latency. That is expected and does not
matter, because every effect is a within-run active-minus-idle difference.

**Runner:** `python3 scripts/run_mechanism.py`. Each root has the same name
length as `sweep-v3`, so the monitor's probe-file argument matches the v3
sweep.

**Analysis:** `python3 analysis/summarize_mechanism.py`, which writes to
`results/updated run/mech-summary/`. It reuses the v3 statistics unchanged:

- `hit_only_test` and `permutation_test` from `analysis/analyze_contention.py`;
- `fisher_combined_p` and `holm_adjust`;
- `bootstrap_ci` (2,000 replicates, seed 5764, cells processed in a fixed
  order), with the ±0.02 margin.

**Per-run validation.** A run that fails any check is reported, and the
analysis stops. Each run must show:

- AES self-test PASS;
- monitor PASS with 16,384 records;
- `probes.bin` of 262,144 B with a valid layout;
- 65 stats blocks;
- probe mapping congruent, summed over intervals;
- for treatments, way isolation `PASS disjoint` in **all 64**
  per-interval occupancy snapshots;
- the `mechanism` metadata matching its setting.

## Execution plan and checkpoints

1. **Guard (not inference).** Re-simulate seed `0x5764A5E5` 8/8, control and
   treatment, with the **modified** config and default options, using the
   unchanged `scripts/run_contention_control.sh l1d4k-v3`. The output goes to
   `results/updated run/guard-mx/` (same name length as `sweep-v3`).
   `probes.bin` and `stats.txt` (excluding `host*` lines) must be
   bit-identical to `sweep-v3`. **If not, stop.**
2. **Smoke test (not inference).** Run one `ide` 8/8 treatment, seed e5,
   into `results/updated run/mech-smoke/`, then run `analyze_run` on it. This
   checks that `header_latency 0` and per-interval dumping work end to end.
   It is not used for tuning, and no threshold is set from it.
3. **Full study:** `python3 scripts/run_mechanism.py` (48 processes, about
   50 minutes), then the analysis.
4. **Sanity check S1 (reported, not a gate).** The 12 `std` runs'
   `probes.bin` files are compared with `sweep-v3`. If they are identical,
   per-interval dumping did not perturb the measurement.

## What does not change

No earlier result, binary or analysis rule changes. The code changes are
opt-in:

- `configs/run_contention.py` gains `--l2bus-width`,
  `--l2bus-header-latency`, `--l2bus-clock` and `--stats-per-interval`.
- With none given, no SimObject parameter or metadata key changes. Step 1
  verifies this, and unit tests check `mechanism_options()`.
- The pre-change file is archived in `archive/pre-mechanism-20261014/`
  (`649be928…`, the D2-logged hash).

## Frozen file hashes (SHA-256)

```text
1d18d4fc006b4b0a1c6d13191018bbf698df39d3d85cf19194133b1ba100f96b  configs/run_contention.py
d755471c18fe4284fe041c3404ab6fba50567d6554b25b0b06832e6901844802  scripts/run_mechanism.py
bfe17713d21809b9935a2b6e86c222f18eaa88d9cbac4e5b2d14d3db4b570584  analysis/summarize_mechanism.py
552b3730a60b9cb50464e4af5e22160922f455b66bf7a4f478e29ebcdab86a05  tests/test_mechanism.py
fcf9b0a737a76bad4a472b7ece704f3ad93f7dab84bfcf4741240a98469fd14d  tests/test_run_contention_config.py
0722e049dcdf93baae19f6813b2b06a5301d647c177b1cc0bb4ea3946f7ec9c2  workloads/monitor_v3_l1d4k
5ef763fa8290f5b8ff026b71a883706ccf6b10151ddfc5951f24012a832f46a1  workloads/victim_l1d4k
7aa38dad96ec332acdeffef5042305fb95cc5b662174be63302618e1463d40a7  analysis/analyze_contention.py
b9e8144adc174fe8c86d57d1e59e76497d92af391eacf1b548d7b3813910ec81  analysis/summarize_repeated_contention.py
c2a82ade582cffb0b6ea97b78afd0071b2c746265f969c5d57e2b6510780cd3d  analysis/summarize_repeated_contention_v2.py
2294f5a293a6673a6ef5dbc597e6f2154f2fa9a638eeb2f9e7c14170819de2e3  analysis/summarize_rerun_v3.py
0060a3bd90c1997657ea400366b8aaf8b34b3fbb3e8284d99ed7f12cbb7ee3e2  scripts/run_contention_control.sh
d094e7440a3bcc2698f2a59902748bf127c4c009521127508cc093d70508bc0b  gem5_ext/requestor_partition_manager.cc
c259c12e9cfafed8da49b5ac0e556719e72d6f700c13c208eaafc41f46c6730f  ~/eel5764/gem5/build/RISCV/gem5.opt
```

All 70 unit tests passed when these hashes were taken.

## Limits stated in advance

- Changing the crossbar changes the platform, so the ablation tests this
  simulated system, not silicon.
- A `partial` or `not supported` outcome attributes any residual to the
  LLC's own shared request path by elimination only. gem5's classic cache
  exposes no per-port queueing statistic.
- AES LLC misses are rare (about 4 per run), so `membus` and DRAM cannot
  carry the signal. The study does not test them.
- The three seeds share one schedule (see §12.4 of the main report). Each
  run's own p-value is also reported.

## Deviations (none; see the execution record)

None yet.

## Execution record

Appended as each step completed.

- **Step 1, guard (October 14, ~12:55): PASS.** `results/updated run/guard-mx/`
  was run with the modified config at default options.
  - Seed e5, 8/8, both arms: `probes.bin`, `run_meta.json` and `stats.txt`
    (excluding `host*` lines) are bit-identical to `sweep-v3`.
  - `config.ini` and `config.json` differ only in the output-path string.
- **Step 2, smoke test (October 14, ~13:00): PASS.** `results/updated run/mech-smoke/`
  holds one `ide` 8/8 treatment, seed e5.
  - `config.ini` shows `width=512`, `header_latency=0` and
    `clk_domain=system.cpu_clk_domain`.
  - The run passes AES, monitor, mapping, 64/64 isolation snapshots, 65 stats
    blocks and 0 LLC blocked cycles.
  - Only pipeline-health fields were inspected. The effect size was not
    looked at, and nothing was changed.
- **Step 3, full study:** started at the time stamped in
  `results/updated run/mech_log.txt`, with no change to any frozen file.
- **Step 3, full study (October 14, 13:00:26–13:41:03): COMPLETE.**
  - 48/48 runs passed validation.
  - S1: 12/12 `std` probe files are identical to `sweep-v3`, so per-interval
    dumping did not perturb the measurement.
  - Analysis: `results/updated run/mech-summary/`. Re-running it into a
    scratch folder gave byte-identical CSV, JSON and PNG files.
  - **P1 PASS:** request-layer occupancy is higher in AES-active intervals in
    all four `std` cells (Fisher p = 4.1e-10 each).
  - **P2 PASS:** Spearman ρ = 1.0 at A = 1 and at A = 8.
  - **P3 FAIL:**

    | `ide` treatment | Effect (cycles per line) | 90% CI | Reduction vs `std` | Equivalent to 0? |
    |---|---|---|---|---|
    | A = 1 | +0.0001 | [0.000, 0.000] | 100% | yes |
    | A = 8 | +0.033 | [0.032, 0.034] | 88% | no |

  - **Preregistered outcome: `partial`.**
  - **Descriptive, not preregistered:** the A = 8 residual is equal in the
    control and the treatment (+0.033 in both). The extra delays come in
    +2-CPU-cycle steps, which is one cycle of the LLC's 1 GHz clock; the LLC
    stays on the system clock in every setting. This fits the preregistered
    by-elimination attribution to the LLC's own request path.

No deviations.
