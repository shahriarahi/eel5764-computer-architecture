# Preregistration: Record-Free Repeated Contention Study (v2)

Written October 11, 2026, **before any v2 measurement existed**:
`results/updated run/` did not exist when the hashes below were taken. The
smoke test (step 1) is the first v2 data. It uses the same code and is not
used for tuning. If anything listed here changes after data exists, the
change is reported as a deviation.

## Why a v2 study

The October 1 study (`REPORT_REPEATED_20261001.md`) found every partitioned
treatment indistinguishable under the max-set statistic. Post-hoc analysis
(`APPENDIX_POSTHOC_20261011.md`) found two problems:

1. The monitor's 384 KiB record array evicted 20–25% of its own probe lines,
   but only in partitioned runs.
2. Once those misses were removed, a hit-latency signal remained in all 24
   treatments.

v2 removes the cause of problem 1 and tests the problem 2 finding in a
confirmatory way.

## What changes and what does not

| | October 1 (v1) | v2 |
|---|---|---|
| Monitor | `monitor_l1d4k` writes records to a 384 KiB array | `monitor_v2_l1d4k` stores each record in the just-loaded probe line and flushes each interval with `writev` (no new lines allocated) |
| Probe output | `probe,` lines in `simout.txt` | `probes.bin`, 16-byte records |
| Platform, AES workload, seeds, schedule, A=1…8 pairs, 2 A=16 diagnostics | — | Unchanged |
| Statistics | Max-set SNR | Max-set SNR **and** hit-only interval mean (co-primary) |
| Results root | `results/contention-repeated-20261001/` (unchanged) | `results/updated run/` |

## Hypotheses

- **H-fix.** With the record-free monitor, treatment probe walks miss no more
  often than control walks: each pair passes the self-eviction gate.
- **H-leak (prediction from the appendix).** A hit-latency signal survives
  way partitioning. At least `1/15` is distinguishable after correction.
- **H-attenuation.** For A ≥ 2, the treatment effect is smaller than its
  control effect.

## Analysis (fixed)

Per run (`analysis/analyze_contention.py --statistic max-set`):

- **Max-set statistic:** as v1. Maximum per-set SNR, 10,000 balanced label
  shuffles, `random.Random(5764)`.
- **Hit-only statistic:**
  - A walk is all-hit when it is ≤ 20 cycles above the run's 1st-percentile
    walk time (linear interpolation).
  - Each interval's value is the mean of its all-hit walks.
  - Two-sided permutation test with the same 10,000 shuffles.
  - Effect = (active mean − idle mean) / A, in cycles per probed line.

Per allocation (`analysis/summarize_repeated_contention_v2.py`):

1. **Self-eviction gate:** |treatment all-hit fraction − control all-hit
   fraction| ≤ 0.01 in all three seed pairs. If it fails, the allocation is
   `uninterpretable`.
2. **Combination and correction:** Fisher combination across the three seeds,
   then Holm correction across 16 tests (8 allocations × 2 statistics),
   separately for controls and treatments. α = 0.05.
3. **Control validity, per statistic:** all three controls individually
   significant, and the control's Holm p < 0.05.
4. **Classification:**
   - `distinguishable` if any statistic with a valid control has a
     treatment Holm p < 0.05;
   - otherwise `indistinguishable` if both controls are valid;
   - otherwise `invalid control`.
5. **Stable collapse point:** the first allocation that is
   `indistinguishable`, provided every larger allocation is too.
6. **Effect and equivalence:**
   - 90% bootstrap CI of the seed-averaged treatment effect (2,000
     replicates, seed 5764; intervals resampled within each label).
   - `equivalent` if the CI lies inside ±0.02 cycles per line, which is
     TOST at α = 0.05.
   - Stable equivalence point is defined the same way as the stable
     collapse point.
7. **Performance:** the v1 cost metrics, reported descriptively.

## Execution plan

1. **Smoke test:** `--plan smoke`, seed `0x5764A5E5`, A=1 control and `1/15`
   (2 processes), into `results/updated run/smoke/`. It proceeds only if the
   self-eviction gate passes and both runs validate. The smoke test checks
   that the pipeline works; it is not part of the inference.
2. **Full sweep:** `--plan full`, 50 fresh processes (48 matched and 2
   diagnostics), into `results/updated run/sweep/`. The v2 summarizer runs
   automatically at the end.
3. A failed gate is reported as it is. The analysis is not tuned after the
   data is seen.

```bash
python3 scripts/run_repeated_contention_sweep_v2.py --plan smoke
python3 scripts/run_repeated_contention_sweep_v2.py --plan full
```

## Frozen file hashes (SHA-256)

```text
7079e70df0ce2ae104183cabf974affbc6265ad8c90b7563ca5c7b91a415cc92  workloads/monitor_v2_l1d4k
5ef763fa8290f5b8ff026b71a883706ccf6b10151ddfc5951f24012a832f46a1  workloads/victim_l1d4k
4edd465c6e06e1b87fa301b12a4a54c23003d104460b18e48d145117cc4d71a8  workloads/monitor.c
3196c9ec31405bc7b98eae602e32469b3fe6aa93a754986451f21b43748e021c  configs/run_contention.py
0e3430c616952aecec2c9a72849879cf5665239e7fd840930fd843908a107e85  scripts/run_contention_control.sh
2c8a63fa186ea6f0f0fdd9be8110d92d75cc6fd3b394a96e4894bdd5cb52e51b  scripts/run_repeated_contention_sweep.py
2a2fd94e9199635ba20392dfc7c5dd744c0c78126658593307f3c811f65a900e  scripts/run_repeated_contention_sweep_v2.py
7aa38dad96ec332acdeffef5042305fb95cc5b662174be63302618e1463d40a7  analysis/analyze_contention.py
b9e8144adc174fe8c86d57d1e59e76497d92af391eacf1b548d7b3813910ec81  analysis/summarize_repeated_contention.py
c2a82ade582cffb0b6ea97b78afd0071b2c746265f969c5d57e2b6510780cd3d  analysis/summarize_repeated_contention_v2.py
d094e7440a3bcc2698f2a59902748bf127c4c009521127508cc093d70508bc0b  gem5_ext/requestor_partition_manager.cc
```

The earlier results are protected separately by
`archive/pre-20261011/results_manifest.sha256`.

## Deviations

**D1 (October 11, during the smoke test; before any full-sweep data).**

- **What happened:** the first smoke process (A=1 control) simulated
  correctly and wrote a complete 262,144-byte `probes.bin`. It then failed
  the runner's output check, because the monitor's final status line
  interleaved with the victim's completion line in the shared stdout. The
  original monitor had avoided this only because formatting 16,384 text
  records delayed its output.
- **Fix:** the v2 monitor now waits one more interval (2M cycles) after
  measurement ends before printing. This happens after the measurement
  statistics are dumped, so no measured quantity changes.
- **Not changed:** no analysis code, threshold, or decision rule. The v1
  binary still hashes to `d25a119b…`. The failed process is preserved as
  `results/updated run/smoke/seed-5764a5e5/UNPARTITIONED-A1.failed.20261011T212728/`.
- **Updated hashes:**

```text
1edbb2d3d18914abcc6da44b6de00d0ad3bf400c89881b7f81e6c5b513fa33a6  workloads/monitor_v2_l1d4k
aa4128f3404d91578be8989614d9bebefc4c148a8cb6d4d6ee0302df1f5ccb64  workloads/monitor.c
```

**D2 (October 11, after the full sweep; approved by the user before the
rerun).** This deviation was made *after* the sweep's results were seen.

**Why.** At 7/9 and 8/8 the sweep failed the self-eviction gate
(`results/updated run/investigation-set191/README.md`). Two causes:

1. Most of the gap came from 20–100-cycle delays that occur only while AES
   is active. That is the signal being measured, and the 20-cycle gate proxy
   counted it as misses.
2. The rest came from one genuine self-evicted set (logical 191), caused by
   the global `probe_way_count` line. It was re-fetched from the LLC from
   A=4 upward.

**Changes.**

1. **Monitor v3:** `-DMONITOR_PROBE_SINK_FILE -DMONITOR_HOT_STATE_IN_REGISTERS`.
   The measurement loop keeps the way count and probe fd in registers. Its
   disassembly contains only probe-chain loads and probe-slot stores. A
   scratch check of one 8/8 run showed no always-slow sets, and walks more
   than 100 cycles over the floor fell from 0.41% to 0.02%. The v1
   (`d25a119b…`) and v2 (`1edbb2d3…`) binaries still rebuild identically.
2. **Gate:** a walk now counts as a miss only when it is more than 100 cycles
   above the run's 1st-percentile walk time. The tolerance stays at 1
   percentage point per seed pair. The original gate is still computed and
   reported next to it.
3. **Rerun:** 7/9 and 8/8 × 3 seeds × {control, treatment}, 12 fresh
   processes, into `results/updated run/rerun-7-9-8-8/`.
4. **Combined analysis:**
   - 1/15–6/10 come from the sweep (v2 monitor, read only), and 7/9 and 8/8
     from the rerun (v3 monitor).
   - Statistics, the 16-test Holm family, the bootstrap CI and the
     equivalence margin are unchanged.
   - Both gates are applied to all eight allocations.
   - Output: `analysis/summarize_rerun_v3.py`.

**Unchanged:** `analysis/analyze_contention.py` and
`analysis/summarize_repeated_contention_v2.py` keep their preregistered
hashes. The sweep's files are not modified.

```text
0722e049dcdf93baae19f6813b2b06a5301d647c177b1cc0bb4ea3946f7ec9c2  workloads/monitor_v3_l1d4k
bb77a209d34c7f869ac1247b9e939ad89f896d3f7404838caf0504e2b45e2946  workloads/monitor.c
649be9288afa440b3c1ef421f955f46ce649c4494b91ca32653152bae9dd69ff  configs/run_contention.py
0060a3bd90c1997657ea400366b8aaf8b34b3fbb3e8284d99ed7f12cbb7ee3e2  scripts/run_contention_control.sh
bf9fb7a14b025c671e1076c86d9fccf4a843699fc5fb10068ca947a0be09d291  scripts/run_rerun_v3.py
2294f5a293a6673a6ef5dbc597e6f2154f2fa9a638eeb2f9e7c14170819de2e3  analysis/summarize_rerun_v3.py
```

**D3 (October 12, before any D3 data; requested by the user).** A full
confirmatory sweep with the v3 monitor, so that every allocation uses the
same monitor build.

- **Plan:** the same 50 processes (48 matched + 2 A=16 diagnostics), runner
  mode `l1d4k-v3`, into `results/updated run/sweep-v3/`.
- **Decision rule:** the v2 rule with the D2 gate, applied to one root.
  Output from `analysis/summarize_sweep_v3.py`.
- **Earlier roots:** `sweep/`, `smoke/` and `rerun-7-9-8-8/` are not
  modified.
- **Reporting:** whatever the outcome, D3 becomes the primary updated-run
  result, and earlier updated-run numbers are kept as supporting records.

```text
3e9078b83c11459c1294da18259f97d1cc1804b4d8e60aa8e3105cde8bfda94a  scripts/run_repeated_contention_sweep_v3.py
d919dd8ae24437954396f88ea72f6deb0a5a81b54f4115565ebd9c9c2a168437  analysis/summarize_sweep_v3.py
0722e049dcdf93baae19f6813b2b06a5301d647c177b1cc0bb4ea3946f7ec9c2  workloads/monitor_v3_l1d4k
7aa38dad96ec332acdeffef5042305fb95cc5b662174be63302618e1463d40a7  analysis/analyze_contention.py
2294f5a293a6673a6ef5dbc597e6f2154f2fa9a638eeb2f9e7c14170819de2e3  analysis/summarize_rerun_v3.py
```

**Caveat (D2).** 1/15–6/10 still use the v2 monitor. Its set-191 conflict
affects one set (0.39 points of walks) from 4/12 to 6/10. Rerunning those
allocations with v3 would make the monitor consistent across all eight.
