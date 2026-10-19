# Per-domain LLC response queues — design

2026-10-18. This design was approved by the user after the causal localization in
`experiments/causal-trace-20261016/RESULTS.md`. It is a simulated defense
prototype, not a hardware design.

## Problem addressed

With way partitioning and request TDMA enabled, the only divergence observed in
the traced path is in LLC hit responses. The shared LLC has one CPU-side
response queue. If a victim response and a monitor response are ready on the
same tick, `PacketQueue::schedSendEvent` sends the second one at
`curTick() + 1`. The crossbar then rounds that 1-tick slip up to its next 1 GHz
edge, adding 999 ticks. The next monitor request can then miss its TDMA slot,
which costs a further 8 ns.

The monitor's observations already differ from a quiet victim's, but only in
active intervals: 1,705 of 16,384 probe records at A=1 and 1,184 at A=8.

## Change

The LLC gets one response queue per security domain. Each queue has its own
send event, so responses in different domains never serialize against each
other inside the cache.

- **New `BaseCache` parameter.** `response_domain_prefixes` is a list of
  requestor-name prefixes, one per domain. The default is empty, which keeps
  the single shared queue and unchanged behavior. The configuration sets
  `["cpu0.", "cpu1."]` on `system.llc` only. That matches the existing TDMA
  domain mapping, where each core's cache and page-table-walker traffic belongs
  to that core's domain.
- **Routing.** `CacheResponsePort::schedTimingResp` hides the inherited
  non-virtual method. It routes each response by its requestor's domain. All
  four coherent-cache response sites call it through `cpuSidePort`. Domain 0
  keeps the original queue, whose name is
  `system.llc.cpu_side_port-CpuSidePort`, so the causal trace filter still
  follows the monitor. Domains 1 and above get new queues labelled
  `CpuSidePort-domain<N>`.
- **Lookup.** The requestor-to-domain result is cached per `RequestorID`. A
  requestor that matches no prefix, or more than one, is `fatal`. Mapping is
  never silent.
- **Retries.** With split queues enabled, any response retry is `fatal`. A
  single port shared by several queues would need per-queue retry ordering,
  which this prototype does not implement. Both causal endpoints recorded zero
  retries, so this gate checks an assumption rather than changing normal
  behavior.
- **Functional accesses.** `trySatisfyFunctional` checks every queue.

The crossbar is unchanged. It already keeps a separate response layer for each
destination port, so responses to different cores on the same tick do not
contend there. Way masks and request TDMA are unchanged.

## Invariants

1. With the parameter empty, simulated behavior is identical. A disabled guard
   must reproduce `tdma-onx` (AES) and `tdma-nc0` (quiet) probes byte-for-byte,
   with equal simulated statistics.
2. No new statistics. This keeps the guard's statistics comparison exact.
3. Requests, way allocation, MSHRs, the write buffer, tags, and DRAM are not
   modified. Any channel through them remains.

## Success criterion

The success criterion is byte-level noninterference, which is a deterministic
test. Under the defense, the monitor's `probes.bin` must be byte-identical
whether the victim runs AES or the quiet victim, at A=1 and at A=8, for seed
`0x5764A5E5`. Anything short of 0 differing records is reported as a failure,
with the count and the intervals involved. Seeds, keys, and activity
schedules are only broadened after this passes.

## Limits

- Byte-identity covers only the victim pair and inputs tested.
- The same-tick rule is a gem5 modelling convention, so whether it matters in
  real hardware is not evaluated.
- Paths outside the response queue are not changed by this defense: LLC fills
  through shared DRAM, and anything before request admission.
