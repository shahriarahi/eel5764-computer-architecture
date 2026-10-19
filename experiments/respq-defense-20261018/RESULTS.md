# Per-domain LLC response queues — results

2026-10-18. All values are **simulated** in gem5 v25.1.0.1 with RISC-V
TimingSimpleCPU and classic caches. They are not hardware measurements. The
configuration is seed `0x5764A5E5` at A=1 (1/15) and A=8 (8/8), and every arm
uses way partitioning plus 4-cycle request TDMA.

## Answer

**The primary outcome passes.** With one LLC CPU-side response queue per
domain, the monitor's entire observation file (`probes.bin`, 16,384 records)
is **byte-identical** whether the victim runs AES or the quiet victim. This
holds at both allocations. Under request TDMA alone, the same pair differs in
1,705 records (A=1) and 1,184 records (A=8).

For this victim pair, seed, and activity schedule, the monitor's observations
contain no information about victim activity in this model. That is
byte-level noninterference. It is not a proof for other inputs, and it is not
a hardware claim.

| | A=1 | A=8 |
|---|---:|---:|
| Request TDMA: AES vs quiet differing records (`tdma-onx` vs `tdma-nc0`) | 1,705 | 1,184 |
| **Defense: AES vs quiet differing records (`tdma-rda` vs `tdma-rdq`)** | **0** | **0** |
| Defense AES probes = stored quiet reference `tdma-nc0` | yes | yes |
| Victim LLC data accesses, defense AES / defense quiet | 694,708 / 1 | 694,708 / 1 |
| AES encryptions, defense (vs way-only, vs request TDMA) | 22,486 (−5.98%, 0.00%) | 22,486 (−5.93%, 0.00%) |

The victim is genuinely active in the defended run. Its AES self-test passes,
it completes 22,486 encryptions, and it makes about 695 k shared-LLC data
accesses. The monitor's observations still match the run in which the victim
makes one. The split queues add no throughput cost beyond request TDMA. The
roughly 6% cost relative to way-only partitioning comes from request TDMA.

The SHA-256 prefixes of the identical probe files are `bb7a83fe…` (A=1) and
`aecc8059…` (A=8).

## Gates

| Gate | Result |
|---|---|
| R1: disabled AES guard (`tdma-rga`) reproduces `tdma-onx` | PASS: probes byte-identical, simulated stats equal, 1,040 `tdma*` lines equal, 0 violations (A=1, A=8) |
| R1: disabled quiet guard (`tdma-rgq`) reproduces `tdma-nc0` | PASS, the same checks (A=1, A=8) |
| R2: defense arms valid | PASS: exit 0, so no unmapped-requestor or response-retry `fatal`; `system.llc.response_domain_prefixes=cpu0. cpu1.`; 0 scheduler violations |
| R3: preservation (12,617 files) | PASS for every protected file, with one explained addition, described below |

The R3 addition is
`lecture slides/pdfcoffee.com_computer-architecture-a-quantitative-approach-5th-edition-pdf-free.pdf`.
It appeared during the run window but kept its original modification time of
2026-08-31. It is course material copied in by the user or by OneDrive, not
experiment output.

The defense changed the simulation in a specific way. Defense AES differs from
undefended `tdma-onx` in exactly the records, and the intervals, by which
`tdma-onx` differs from the quiet run. Defense quiet is byte-identical to
`tdma-nc0`, which is expected because the quiet victim generates almost no
competing responses. The baseline, request-TDMA, and causal executables are
unchanged (`c259c12e…`, `5a540aed…`, `2428f123…`).

## What was built

- `response_domain_prefixes` is a new `BaseCache` parameter, empty by default.
  On `system.llc` it is set to `["cpu0.", "cpu1."]` by
  `run_contention_respq.py`. That matches the request-TDMA domain mapping.
- `CacheResponsePort::schedTimingResp` routes each response to its domain's
  queue. Domain 0 keeps the original queue and its name.
- A requestor that maps to no domain, or to more than one, is `fatal`. Any
  response retry is also `fatal` while queues are split. Neither occurred.
- The patch is in `gem5-respq.patch`, applied on `c8222cc` plus the causal
  patch. The executable SHA-256 is `66c30701…f61f8` (`build_manifest.json`).
- Tests (Windows and WSL Python): 9 new, plus 64 causal, 10 TDMA, and 70
  project tests, all OK. The C++ domain-mapping test passes.

## Commands executed

```text
# WSL, project root (784 s for all eight cases)
python3 -B .codex-tmp/tdma-worktree/experiments/respq-defense-20261018/run_respq.py --baseline-root <root>
# Windows, experiment directory
python -B compare_arms.py --baseline-root <root> --out analysis/outcome.json
```

## Limits and next steps

- **Coverage.** The result covers one victim pair (AES against quiet) under one
  key, one seed, and one activity schedule that the three public seeds share.
  The next preregistered steps are the other two seeds; AES runs with different
  keys and plaintexts compared against each other, not only against quiet; and
  an independent activity schedule.
- **Defense mechanism.** The defense removes a gem5-modelled same-tick
  serialization (`PacketQueue` adds `curTick() + 1`). Whether real arbitration
  behaves the same way was not evaluated.
- **Untouched paths.** Shared structures not exercised differently by this
  pair could still leak with other workloads: DRAM, which the monitor rarely
  reaches; the MSHRs; and the write buffer. A byte-identity test with more
  varied victims is the way to find out.
- **Retries.** Response retries are unsupported, not isolated. A workload that
  causes response backpressure would stop the simulation with `fatal` instead of
  leaking silently.

---

# Defense sweep over the proposal's design (`PREREGISTRATION_SWEEP.md`)

The sweep covers the three public seeds at A=1…8. The full defense combines way
partitioning, 4-cycle request TDMA, and per-domain LLC response queues. It is
judged by the accepted proposal's own success criterion, using the
**unchanged** frozen decision code (`analysis/summarize_sweep_v3.py`) and the
stored v3 unpartitioned controls. All values are simulated.

## Answer: both primary outcomes pass

| Allocation | Way partitioning only (v3, frozen) | **Full defense** | Control effect → defended effect (cycles/line) | Defended 90% CI |
|---|---|---|---:|---|
| 1/15 | distinguishable | **indistinguishable** | +0.347 → −0.002 | [−0.003, −0.001] |
| 2/14 | distinguishable | **indistinguishable** | +0.292 → −0.001 | [−0.002, −0.000] |
| 3/13 | distinguishable | **indistinguishable** | +0.338 → −0.001 | [−0.001, −0.000] |
| 4/12 | distinguishable | **indistinguishable** | +0.362 → −0.000 | [−0.001, −0.000] |
| 5/11 | distinguishable | **indistinguishable** | +0.383 → −0.000 | [−0.001, +0.000] |
| 6/10 | distinguishable | **indistinguishable** | +0.391 → −0.000 | [−0.001, −0.000] |
| 7/9 | distinguishable | **indistinguishable** | +0.392 → −0.000 | [−0.000, −0.000] |
| 8/8 | distinguishable | **indistinguishable** | +0.401 → −0.000 | [−0.000, −0.000] |

- **Proposal criterion: PASS.** Treatment Holm p = 1 for both co-primary
  statistics, max-set SNR and hit-only, at every allocation. The self-eviction
  gate passes 3/3 at every allocation. The **stable collapse point is 1/15**,
  and the stable ±0.02 equivalence point is also 1/15. Under way partitioning
  alone, the same code finds no collapse point.
- **Byte identity: PASS, 24/24.** In every seed × allocation configuration,
  the defended monitor's `probes.bin` is byte-identical between the AES victim
  and the quiet victim.
- **Remaining effects.** The tiny negative values come from the startup
  interval, interval 0, which is labelled idle. The quiet control shows the
  same pattern, and the quiet victim produces byte-identical probes, so it
  carries no information about AES.

## Cost

The cost is measured against the matched unpartitioned controls, averaged over
the three seeds. The numbers come from the frozen summarizer's own fields.

| Allocation | Monitor IPC | AES IPC | AES cycles/encryption | Monitor LLC miss (pp) |
|---|---:|---:|---:|---:|
| 1/15 | +0.18% | +2.41% | +6.35% | +0.262 |
| 8/8 | +0.18% | +2.39% | +6.30% | +0.262 |

Allocations 2/14 to 7/9 fall between these rows. Positive values denote cost.
Against the v3 way-only treatments, AES completes 5.95% fewer encryptions,
within a range of 5.93–5.98% across all 24 cases.

The endpoint runs in the first part of this file attribute the extra cost to
request TDMA. There, split response queues changed AES encryptions by 0.00%
relative to request TDMA alone. That attribution is measured at seed `E5`, at
A=1 and A=8, and is not separately measured at the other 22 configurations.

## Validity and provenance

- **Per-case gates.** All 48 cases passed. gem5 exited 0 with no requestor or
  retry `fatal`. The prefixes were `cpu0. cpu1.` and there were 0 scheduler
  violations. For the AES runs, the unchanged analyzer also reported `PASS
  congruent` mapping, `PASS disjoint` ways with 0 violations, the hit-only
  statistic present, and encryptions above zero.
- **Method check.** This ran before any sweep output existed. A view root built
  from copies of the original `sweep-v3` runs reproduces the stored
  `summary_v3.json` exactly.
- **Preservation.** No protected file changed; there were 12,617, including
  all of `sweep-v3`. The new files are the sweep outputs (`tdma-rsa`,
  `tdma-rsq`, and `tdma-rsv`) and three course files the user added
  (textbook and lecture material).
- **Run time.** 785 s at six concurrent processes. The outcome record is in
  `analysis/sweep_outcome.json`, and the decision tables are in
  `results/updated run/tdma-rsv/summary_v3.{json,csv}` and
  `repeated_v3.{pdf,png}`.

## Limits

The three public seeds vary the plaintexts, but they share one key and one
activity schedule, as in the original study. The result covers this design in
gem5.
