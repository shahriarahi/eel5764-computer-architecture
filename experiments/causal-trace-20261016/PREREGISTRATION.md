# Causal timing localization — preregistration

Frozen 2026-10-18, before any `tdma-cd0` or `tdma-ct0` output exists. Governs
plan Task 6. The spec is
`docs/superpowers/specs/2026-10-16-causal-timing-localization-design.md`,
including Amendment 1 (trace version 2). All values come from deterministic
gem5 simulation, not from hardware.

## Instrument

- Project commit with the frozen code: `6020dc6` on `experiment/tdma-prototype`.
- Executable: `/home/shahriarahi/eel5764/gem5-causal/build/RISCV/gem5.opt`,
  SHA-256 `2428f123e172097d3dc9f269250e439d2ee9caf223b39a0bce76085678c5cca3`.
- Trace version 2. Structural evidence is in `structural-04`.
- References: the stored scheduled cases
  `results/updated run/tdma-onx/seed-5764a5e5/{1-15,8-8}` (4-cycle request slots).

## Execution order

Each command runs from the project root:

1. `python3 -B experiments/causal-trace-20261016/run_cases.py --baseline-root <root>`
   writes `tdma-cd0`: A=1, then A=8, with tracing disabled.
2. `python3 -B experiments/causal-trace-20261016/run_cases.py --baseline-root <root> --trace`
   writes `tdma-ct0`: A=1, then A=8, with tracing enabled.

Step 2 starts only after both step-1 cases pass G1 and G4. The first failed
gate stops execution. A failed case is preserved as `<case>.failed.<suffix>`
with `failure.json`. Nothing is rerun into an existing root.

## Gates

- **G1, trace-off equivalence.** `probes.bin` is byte-identical to the
  reference, and simulated statistics match it. The comparison excludes host
  fields and `tdma*` lines (`run_pilot.stats_rows`).
- **G2, trace-on equivalence.** Same test as G1, applied to the trace-on case.
  Since both runs are checked against the same reference, G1 plus G2 imply
  trace-on/trace-off equivalence.
- **G3, trace validity.** `match_timelines` succeeds, which requires complete,
  ordered, address-matched timelines and exactly one dequeue per request. In
  addition, every record parses as version 2 and every
  `latency_rows` ordering check passes.
- **G4, scheduler counters.** Every `system.l2bus.tdma*` line in the case's
  statistics equals the reference line. `tdmaOverruns`,
  `tdmaDownstreamRefusals`, and `tdmaExpressBypasses` are zero. This gate
  exists because G1 excludes `tdma*` lines.
- **G5, preservation.** `preservation-prerun.json` is created exclusively
  immediately before step 1. After step 2, `preserve.py check` against it must
  report no changed and no added files. Deviations from the older
  `preservation-before.json` were audited before this snapshot:
  - 10 changed or missing files: nine lecture PDFs moved byte-identically into
    `lecture slides/`, plus one SDD progress note.
  - 598 added files: the scaffolding from aborted build 01, course material,
    and `.claude` state.
  - No protected result, binary, or configuration file was among them.

## Analysis (`analyze.py`, one JSON per case)

- **Interval schedule.** It comes from the case's `run_meta.json`.
  `start_tick = reset_tick` and `epoch_ticks = epoch_cycles × 500`, with the
  64 stored activity labels. A request belongs to the interval that contains
  its `cpu_delivery` tick. Timelines delivered before `reset_tick` or at or
  after `measurement_end_tick` are counted and excluded.
- **Segments.** Each segment uses scheduled readiness:
  - LLC service: `llc.sched − admit`.
  - Enqueue: `enqueue.sched − llc.sched`.
  - Queue residence: `dequeue − enqueue.sched`.
  - Transit to crossbar: `xbar − dequeue`.
  - Crossbar to CPU delivery: `delivery − xbar`.

  Checkpoints accumulate from admission: `cumulative_llc_ready`,
  `cumulative_enqueue`, `cumulative_dequeue`, `cumulative_xbar`, and
  `admit_to_cpu`.
- **Effect.** For each field, requests are first averaged within each
  interval. The effect is the mean of the 32 active interval means minus the
  mean of the 32 idle interval means, computed exactly with rational
  arithmetic. It is reported in ticks and in CPU cycles (ticks ÷ 500).
- **Primary report.** All analyzed requests, all intervals.
- **Declared secondary reports:**
  1. LLC hits only (`outcome=hit`). This subset is the closest analogue of the
     hit-only endpoint, but it is not identical. The endpoint excludes whole
     probe walks containing a miss; this subset excludes individual LLC fills.
  2. LLC fills only.
  3. Every report repeated with interval 0 separated. The quiet control found a
     startup-only difference there.
  4. `upstream_gap`, from the previous monitor delivery to the next admission.
     It is descriptive only, because it mixes CPU issue, L1D handling, and TDMA
     admission wait.
- **Earliest divergence.** The candidate is the first checkpoint, in pipeline
  order, with a nonzero exact effect. The result is unresolved in three cases:
  - That checkpoint has the same tick as its predecessor for every request.
  - Its predecessor is admission and its value is zero for every request.
  - No checkpoint diverges. The report then states that any residual lies
    before `request_admit` and describes `upstream_gap`.

## Interpretation rules and claim limits

- An earliest divergence at `cumulative_llc_ready` implicates LLC service, the
  time from admission to scheduled readiness.
- At `cumulative_dequeue` it implicates waiting in the shared LLC response
  queue.
- At `cumulative_xbar` it implicates the transit from that queue to the
  crossbar.
- At `admit_to_cpu` it implicates the path after crossbar forwarding.
- Each segment's effect is reported next to the total `admit_to_cpu` effect, so
  later cancellation or amplification is visible. No fixed share threshold is
  applied.
- This is one public seed, two allocations, and deterministic runs. The results
  are descriptive localization only. They make no significance claim, no claim
  that one structure is the sole cause, and no claim of indistinguishability.
  No defense is implemented or tested.
- The trace measures latency per LLC request, while the stored endpoint is
  hit-only latency per probed line. Both may be shown side by side, but they
  will not be equated.

## Storage

Raw cases stay under `results/updated run/tdma-cd0` and `tdma-ct0`. The trace
logs are expected to be roughly 45 MB at A=1 and 350 MB at A=8. Raw outputs are
not copied into git. `RESULTS.md` records the SHA-256 of every raw `causal.log`,
`probes.bin`, and `stats.txt.gz`, and git holds only the analysis JSON.
