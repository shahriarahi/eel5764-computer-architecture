# Causal timing localization after request TDMA

Date: 2026-10-16

## Purpose

Determine where the residual AES-active/idle timing difference first appears
after LLC way partitioning and fixed-slot request admission. The experiment is
diagnostic. It will identify a candidate shared path for a later defense; it
will not claim indistinguishability or implement that defense.

The frozen way-partitioning study and completed request-TDMA endpoint study
remain unchanged. Existing binaries, raw outputs, and the isolated
`gem5-timeslot` source/build are read-only inputs.

## Evidence entering this experiment

The fixed-slot scheduler substantially reduced the hit-only timing effect but
left a detectable residual at both endpoint allocations. A separately scoped
quiet-victim control has also been completed locally at A=1 and A=8 for public
seed `0x5764A5E5`. Its recorded result did not reproduce the positive residual
when the victim performed no measured AES work or shared-cache traffic. This
weakens an explanation based only on monitor periodicity or fixed labels, but
does not identify any response structure as causal.

The quiet-control artifacts are currently untracked under
`experiments/quiet-control-20261016/`. They must be independently verified and
checkpointed before causal-trace implementation begins.

## Chosen approach

Create a separate WSL gem5 worktree and executable at
`/home/shahriarahi/eel5764/gem5-causal`. Apply the already tested request-TDMA
change there, then add filtered, debug-only causal tracing. Do not modify the
original gem5 tree, `gem5-timeslot`, or either existing executable.

The trace will contain only monitor probe transactions. This retains the
request-level evidence needed for localization without logging every
instruction fetch and data access during the full measurement.

Two rejected alternatives are:

- Trace every timing packet using broad debug flags. This produces a much
  larger log and makes correct probe matching harder to audit.
- Add aggregate latency counters only. These reduce output size but cannot show
  the first stage at which matched requests diverge.

## Trace scope and stages

The implementation will record these stage events where they exist in the
gem5 v25.1.0.1 classic-cache timing path:

1. `request_admit`: the monitor request is admitted by the shared coherent
   crossbar after its TDMA eligibility check.
2. `llc_response_ready`: the shared LLC has completed the work that determines
   when its response can be scheduled toward the CPU side.
3. `response_enqueue`: the response enters the LLC CPU-side response queue.
4. `response_send_attempt`: the queued response attempts transmission.
5. `response_retry`: a failed send remains queued or is retried after the
   downstream receiver becomes available.
6. `response_dequeue`: the response leaves that queue successfully.
7. `xbar_response_forward`: the coherent crossbar accepts and forwards the
   response toward the monitor-side cache.
8. `cpu_delivery`: the timing CPU receives the completed monitor data access.

The exact source hooks recorded by the quiet-control investigation must be
rechecked against the clean isolated source before editing. If a named semantic
stage does not have one unambiguous hook, implementation stops and the spec is
revised rather than assigning a misleading label.

## Probe filtering

Trace eligibility requires all of the following:

- the requestor is the monitor data-side requestor;
- the request carries a virtual address;
- that address is within the configured monitor probe region;
- the packet belongs to a timing request/response path being studied.

The monitor requestor identity, probe virtual base, and probe-region size come
from explicit configuration parameters. No numeric requestor ID or address is
hard-coded. Disabled tracing follows the original path and creates no trace
events.

## Trace record

Each event is a single structured line with a fixed schema:

```text
CAUSAL_TRACE version=1 tick=<tick> stage=<stage> component=<name> requestor=<id> cmd=<command> paddr=<address> vaddr=<address> size=<bytes>
```

Retry-related records include an outcome field. Missing required packet
metadata is counted and causes validation failure; it is not silently omitted.
The trace format uses integer ticks and integer addresses so parsing does not
depend on locale or host timing.

## Request matching and latency decomposition

The monitor uses serialized dependent accesses, so the analyzer will match
records by ordered probe-address occurrence within each stage. It will verify
the address sequence and event count before computing latencies. A mismatch,
duplicate terminal event, negative duration, or missing required stage makes
the case invalid.

For each successfully matched request, the analyzer derives:

- admission to LLC-ready latency;
- LLC-ready to response-queue enqueue latency;
- queue residence and retry latency;
- successful dequeue to crossbar forwarding latency;
- crossbar forwarding to CPU delivery latency;
- total admission-to-delivery latency.

Requests are assigned to the existing 64 labelled intervals by their
`cpu_delivery` tick, matching the completion-time interpretation of the probe
records. Requests whose timeline crosses an interval boundary are counted and
reported explicitly.

For every latency segment, the analyzer first averages matched requests within
each interval, then reports the signed active-minus-idle mean over the 32 active
and 32 idle interval means. It also reports the cumulative latency at every
checkpoint so an early difference that is later cancelled remains visible.
The quiet control found a startup-only difference in interval 0, so the analyzer
reports both the frozen all-interval result and a declared sensitivity result
with interval 0 separated; it never silently drops that interval.

The localization candidate is the earliest checkpoint whose active and idle
interval-mean vectors differ in the observed deterministic run. Effect size and
the behavior of later checkpoints determine whether that candidate plausibly
accounts for the final latency difference. This is descriptive localization,
not an independence-based significance claim or proof that one structure is
the sole cause. If matching, tick resolution, or simultaneous checkpoints make
the earliest point ambiguous, the result is reported as unresolved.

## Experimental cases and gates

Initial localization is limited to A=1 and A=8 with public seed
`0x5764A5E5` and the existing 4-cycle request slots.

For each endpoint:

1. Run a trace-disabled causal-build guard.
2. Require byte-identical probe output and matching simulated statistics
   against the corresponding stored scheduled case, excluding declared new
   trace counters and host-runtime fields.
3. Run the same case with tracing enabled.
4. Require trace-on and trace-off probe bytes and simulated statistics to
   match under the same exclusions.
5. Validate scheduler invariants and every trace matching invariant before
   analyzing stage latencies.

The first-seed endpoint runs are for localization, not three-seed security
inference. No additional seeds, allocations, defense implementation, or
efficacy sweep is authorized by this specification.

## Implementation boundaries

New project-side files belong under `experiments/causal-trace-20261016/` and
have one responsibility each:

- an exact patch/preparation tool for the clean isolated gem5 worktree;
- a configuration adapter that enables filtering and tracing without editing
  the frozen baseline configuration;
- a bounded runner with exclusive output creation and preserved failures;
- a strict trace parser and latency analyzer;
- focused unit tests for configuration, parsing, matching, and validation;
- provenance, progress, and result records.

The gem5 changes must be disabled by default. They may add configuration,
debug tracing, and validation counters, but must not delay, reschedule, or
otherwise change simulated packet behavior.

## Failure handling and preservation

- Never reuse, overwrite, move, or delete an existing output directory.
- Preserve a failed case with its command, partial trace, simulator output,
  and explicit failure record.
- Reject incomplete requestor/address configuration before simulation.
- Reject trace records with unsupported schema versions or unknown stages.
- Treat response backpressure and retries as measured events, not automatic
  errors, unless matching becomes ambiguous.
- Fingerprint protected project files before execution and verify them after
  execution.
- Record source commit, patch hash, executable hash, complete commands, and
  simulator exit status.

## Testing strategy

Implementation follows test-driven development.

- Parser tests begin with hand-written trace records and cover each stage,
  retries, malformed records, missing metadata, and unknown versions.
- Matching tests prove valid ordered matching and reject missing, reordered,
  duplicated, or negative-time events.
- Configuration tests prove tracing is disabled by default and reject partial
  filters.
- A small structural gem5 test proves each hook emits the expected stage and
  that disabled tracing emits none.
- Existing request-TDMA C++ and Python tests must still pass.
- Trace-off, then trace-on perturbation guards must pass before scientific
  analysis.

## Runtime and authorization boundaries

Creating or modifying `/home/shahriarahi/eel5764/gem5-causal` is outside the
launched Windows workspace and requires explicit authorization. Building the
new executable or starting simulations expected to exceed two minutes also
requires separate approval immediately before execution. No dependency
installation is planned.

## Amendment 1 — 2026-10-18: scheduled ticks (trace version 2)

Structural validation showed that version-1 records misplace two stage
boundaries. The `llc_response_ready` and `response_enqueue` hooks run when the
LLC *schedules* its response, logging `curTick()`, while the response becomes
ready at a later tick passed to `schedTimingResp`/`schedSendTiming`. For LLC
hits the version-1 `admit_to_llc_ready` was 0 and the hit latency appeared
inside `queue_residence`, so LLC service and response-queue waiting could not
be separated. Under the "one unambiguous hook" rule above, implementation
stopped and the trace was revised:

- Records are `version=2` and add `sched=<tick>`: the tick passed to the
  `sched*` call at that hook (`request_time` for an LLC hit, `completion_time`
  for an MSHR fill, `when` at enqueue, `curTick()+latency` at the crossbar
  forward), and `curTick()` at every other hook. `sched < tick` is invalid.
- The two LLC hooks report `outcome=hit` (`BaseCache::handleTimingReqHit`) and
  `outcome=fill` (`Cache::serviceMSHRTargets`), giving an exact hit/fill split.
- Segments use scheduled readiness: LLC service is `llc.sched - admit.tick`;
  queue residence is `dequeue.tick - enqueue.sched` (waiting beyond readiness,
  including retries).
- `upstream_gap`, the previous monitor delivery to the next admission, is
  added as a descriptive segment because admission is traced only after the
  TDMA check. It combines CPU issue, L1D handling, and admission wait.

Hooks log already computed values only; they do not change scheduling. The
version-1 executable is retained as `build/RISCV/gem5.opt.causal-v1`.

## Success criteria

The work is complete when:

- the quiet control is verified and checkpointed;
- the isolated causal build passes unit and structural tests;
- trace-disabled and trace-enabled perturbation guards pass at A=1 and A=8;
- every analyzed monitor request has an auditable, validated stage timeline;
- the earliest observed active/idle divergence is reported with its practical
  limits, or the report states that the trace resolution did not localize it;
- all original studies, binaries, and outputs remain unchanged.
