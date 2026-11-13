# Causal timing localization — results

2026-10-18. All values are **simulated** (gem5 v25.1.0.1, RISC-V
TimingSimpleCPU, classic caches). None are hardware measurements. There is one
public seed, `0x5764A5E5`. The allocations are A=1 (1/15) and A=8 (8/8), and
request TDMA uses 4-cycle slots. A gem5 tick is 1 ps, and 500 ticks equal one
2 GHz CPU cycle.

## Answer

When interval 0 is separated, as the preregistration declared, the
**earliest observed active/idle divergence for LLC hits is at the response-queue
dequeue**. In active intervals, a small number of monitor hit responses leave
the shared LLC CPU-side response queue **one tick later** than scheduled. The
crossbar's clock-edge alignment turns each one-tick slip into a **full 1 ns
cycle** (+999 ticks). That accounts for the whole instrumented in-path effect at
both allocations. LLC service time for hits is **exactly equal** in active and
idle intervals.

The primary all-interval report places the earliest divergence at LLC service
instead. That result is driven by cold-miss fills in interval 0, which is
labelled idle: the startup artifact the quiet control also found. Both reports
are shown below.

This is descriptive localization from deterministic runs. It does not show
that this structure is the sole cause, it makes no significance claim, and it
does not show that the effect is indistinguishable or defended.

## Gates (all passed for the analyzed cases)

| Gate | A=1 | A=8 |
|---|---|---|
| G1 trace-off vs `tdma-onx`: probes byte-identical, simulated stats equal (`tdma-cd1`) | PASS | PASS |
| G2 trace-on vs `tdma-onx`: same test (`tdma-ct3`) | PASS | PASS |
| G3 complete matched timelines | 33,024 | 264,192 |
| G4 `tdma*` counters identical to reference; 0 overruns, refusals, and bypasses | PASS (1,040 lines) | PASS (1,040 lines) |
| G5 no protected file changed or added since `preservation-prerun.json` (12,414 files) | PASS | PASS |

The two G5 differences are hook-written `.claude/handoff-nudge-state.json`
files, which the pre-run amendment exempts. The A=1 `causal.log` is
byte-identical across three independent runs (`tdma-ct1`, `tdma-ct2`,
`tdma-ct3`). Retries: 0. Boundary crossings: 0.

The trace logged every monitor request that reached the L2 bus. Another 65,536
monitor deliveries per case were L1D hits with no L2 stages. Timelines
delivered during warmup were excluded: 256 at A=1 and 2,048 at A=8. LLC paths:
32,682 hits and 86 fills at A=1; 261,456 hits and 688 fills at A=8.

## Stage effects (active − idle interval means, ticks)

Interval 0 separated, which is the declared sensitivity report:

| Segment | A=1 hits | A=8 hits | A=1 all | A=8 all |
|---|---:|---:|---:|---:|
| LLC service (`llc.sched − admit`) | **0** | **0** | +1.831 | +2.792 |
| Ready → enqueue | 0 | 0 | 0 | 0 |
| Queue residence (`dequeue − enqueue.sched`) | **+0.002** | **+0.002** | +0.002 | +0.002 |
| Dequeue → crossbar forward | 0 | 0 | 0 | 0 |
| Crossbar forward → CPU delivery | **+2.313** | **+2.035** | +2.313 | +2.042 |
| Total, admission → delivery | +2.315 | +2.037 | +4.146 | +4.837 |
| Requests | 32,255 | 258,040 | 32,256 | 258,048 |
| Earliest divergence | `cumulative_dequeue` | `cumulative_dequeue` | `cumulative_llc_ready` | `cumulative_llc_ready` |

In the all-request columns, the LLC-service effect comes entirely from the
fills that remain after interval 0 is removed: one at A=1 and eight at A=8.
Primary all-interval report, all requests: the effect from admission to
delivery is −334.961 ticks (A=1) and −184.258 ticks (A=8), and the earliest
divergence is `cumulative_llc_ready`. Of the 86 and 688 fills, 85 and 680 fall
in interval 0, which is labelled idle. Their long service times dominate that
interval's means.

The preregistered `upstream_gap` covers the time from the previous delivery to
the next admission. Its mean is dominated by 55–68 inter-walk pauses per label
of about 0.47–0.49 ms each, so it is **not** a latency measure. The A=1 hit value
of +112.971 ticks should not be read as one. Its short-gap pattern is
explained below.

## Exploratory mechanism (post-hoc; `explore_mechanism.py`, `analysis/exploratory_mechanism.json`)

The table counts each LLC hit after interval 0 by activity label, queue
residence, and crossbar forwarding latency (`xbar.sched − xbar.tick`):

| Label | Queue residence | Forward latency | A=1 | A=8 |
|---|---:|---:|---:|---:|
| idle | 0 | 1,000 | 15,870 | 126,975 |
| idle | **1** | **1,999** | 2 | 1 |
| active | 0 | 1,000 | 16,343 | 130,796 |
| active | **1** | **1,999** | 40 | 268 |

- **One-to-one.** Every one-tick dequeue slip, and only those slips, produces
  the 1,999-tick forward. The time from forward to CPU delivery is a constant
  500 ticks for every hit.
- **gem5 source.** `PacketQueue::schedSendEvent` applies
  `when = max(when, curTick() + 1)` (`src/mem/packet_queue.cc`). A second
  response ready on the same tick in the same queue is therefore sent one tick
  later. `BaseXBar::calcPacketTiming` adds `clockEdge() − curTick()` to
  `headerDelay` (`src/mem/xbar.cc`), which rounds a packet that arrives one
  tick after an edge up to the next 1 GHz edge.
- **Downstream at the TDMA gate.** Every admission falls at frame phase 0
  (8,000-tick frame). After each delayed hit, the CPU's next admission is
  either absorbed into the same slot or misses it and waits one full frame:

  | Next gap after a delayed hit | A=1 active | A=1 idle | A=8 active | A=8 idle |
  |---|---:|---:|---:|---:|
  | Absorbed (−1,000 vs normal) | 26 | 2 | 253 | 1 |
  | Missed slot (+7,000, a full 8 ns frame) | 14 | 0 | 15 | 0 |

- **Not observed.** The trace records only monitor packets. The packet that
  shares the queue on those ticks is *inferred* to be victim-side traffic
  because the slips cluster in active intervals (40:2 and 268:1). It was not
  observed. Whether a same-tick one-tick serialization reflects real hardware
  arbitration, rather than a gem5 modelling convention, was not evaluated.

## Relation to the endpoint result

The stored scheduled-arm hit-only effect is 0.039892 CPU cycles per probed line
at 1/15 and 0.003959 at 8/8. Those are three-seed means from
`experiments/tdma/RESULTS.md`. The traced in-path hit effect here is 2.315 and
2.037 ticks per L2 request, which is 0.0046 and 0.0041 cycles. The two metrics
aggregate different units: per probed line including L1D-resident probes,
versus per L2 request. They also come from different seed sets, so they are
**not equated**. The trace does show that the instrumented L2 path diverges
only through the dequeue-slip and edge-alignment chain, and that this chain
also reaches the next request's TDMA admission.

## Implication for the next step (no defense implemented or tested)

The handoff's decision rule says that a response-path divergence points to
per-domain response queues with fixed return arbitration. This result fits that
rule, with one refinement. The observed effect enters as **same-tick
serialization in the shared LLC CPU-side response queue**, which crossbar
clock-edge alignment and the request-slot gate then amplify. A defense would
need to remove the cross-domain same-tick ordering, for example through
per-domain response queues or fixed response slots. It would also need to keep
the crossbar edge from amplifying any remaining sub-cycle difference. This is a
hypothesis to design and test, not a result.

## Deviations from the preregistration

Each deviation is recorded in `progress.md` with its cause:

1. Result roots are `tdma-cd1` and `tdma-ct3`, not `tdma-cd0` and `tdma-ct0`.
   Roots are never reused, and the earlier roots hold preserved attempts:
   - `tdma-cd0`: aborted before simulation by a probe-path-length mismatch
     (`FAILED.json`).
   - `tdma-ct1`: A=1 case that failed G3 under one-to-one delivery matching.
   - `tdma-ct2`: valid A=1 case, plus an A=8 case that hit the 240 s bound.
2. **Post-hoc matcher change.** Each request's delivery is the first
   same-address delivery after its crossbar forward, because the CPU hook also
   fires for L1D hits. Re-validating the preserved `tdma-ct1` case gives the
   same counts.
3. Trace-enabled cases have a 900 s runner bound instead of 240 s. The bound is
   runner-only; simulated results do not depend on it.
4. Harness fixes that do not change simulation: a scoped TDMA helper import, a
   staging name derived from the reference probe-path length, and an O(n log n)
   attempt lookup with byte-identical output.
5. The exploratory mechanism analysis above is post-hoc.

## Commands executed

From the project root, in WSL:

```text
python3 -B .codex-tmp/tdma-worktree/experiments/causal-trace-20261016/run_cases.py --baseline-root <root>          # tdma-cd1, 184 s
python3 -B .codex-tmp/tdma-worktree/experiments/causal-trace-20261016/run_cases.py --baseline-root <root> --trace  # tdma-ct3, 5,145 s (mostly the pre-fix A=8 validation)
```

From `experiments/causal-trace-20261016` (Windows Python):

```text
python -B gates.py <tdma-onx case> <case>                      # G4, four cases
python -B analyze.py <tdma-ct3 case> --out analysis/A{1,8}.json
python -B explore_mechanism.py <tdma-ct3 1-15> <tdma-ct3 8-8> --out analysis/exploratory_mechanism.json
```

Tests, run under both Windows and WSL Python: 64 causal, 10 TDMA, 70 project,
and 5 quiet-control, all OK.

## Provenance

- Executable: `gem5-causal/build/RISCV/gem5.opt`, SHA-256 `2428f123…5cca3`
  (see `build_manifest.json`). gem5 base `c8222cc`, TDMA patch `b63cd7b0…`,
  causal patch `587861d5…`.
- Raw outputs are under `results/updated run/`. They are not committed:
  - `tdma-cd1`: 2.4 MB.
  - `tdma-ct3`: 489 MB. The A=8 `causal.log` is 441,693,178 bytes.
- SHA-256 of the analyzed raw files:

| File | SHA-256 |
|---|---|
| `tdma-cd1/.../1-15/probes.bin` = `tdma-ct3/.../1-15/probes.bin` | `d2720c2347512d0bffb0913421c1fb08460649809539baf1faf0f5b6cee840e9` |
| `tdma-cd1/.../8-8/probes.bin` = `tdma-ct3/.../8-8/probes.bin` | `475806f76fd861983fd2e5d5ae0220e76a5dc6635fd5b18f0387e8f26afa882a` |
| `tdma-ct3/.../1-15/causal.log` | `e516543e7693df14113978bf284e95b41dfad1d259c48a019ffd6e2c05c56a5c` |
| `tdma-ct3/.../8-8/causal.log` | `5757a51645862fb89488b10979eaf3b461d13f968c304c0e5223d1eefc72b323` |
| `tdma-ct3/.../1-15/stats.txt.gz` | `f1e866c9b6feba2d5e4d6443b3b84e0692036f8ace3994e8c10f81936370b3d1` |
| `tdma-ct3/.../8-8/stats.txt.gz` | `98cecc4f5a58de1585645f4bb02d5b81be8f4a6ea60873a66e732d0993cfa21b` |

## Limits

- **Scope.** There is one seed with a shared activity schedule, two
  allocations, and deterministic runs. No held-out attacker or classifier was
  used, nor any hardware.
- **Coverage before admission.** Admission is traced only after the TDMA
  check, so delays before it are visible only through the mixed
  `upstream_gap`.
- **Unobserved sharer.** The identity of the packet that shares the queue is
  inferred, not traced.
- **Startup.** Interval 0 contains the cold-start fills. The all-interval
  primary report is dominated by them.
