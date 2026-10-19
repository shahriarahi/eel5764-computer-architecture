# Per-domain LLC response queues — preregistration

Frozen 2026-10-18, before any `tdma-rga`, `tdma-rgq`, `tdma-rda`, or
`tdma-rdq` output exists. Design: `DESIGN.md`. All values are simulated.
The configuration is seed `0x5764A5E5`, A=1 (1/15) and A=8 (8/8), with way
partitioning and 4-cycle request TDMA in every arm.

## Arms and order (`run_respq.py`, stop at the first failure)

| Order | Arm | Root | Victim | Split response queues | Reference |
|---|---|---|---|---|---|
| 1 | guard-aes | `tdma-rga` | AES | off | `tdma-onx` |
| 2 | guard-quiet | `tdma-rgq` | quiet | off | `tdma-nc0` |
| 3 | defense-aes | `tdma-rda` | AES | `cpu0.`, `cpu1.` | — |
| 4 | defense-quiet | `tdma-rdq` | quiet | `cpu0.`, `cpu1.` | — |

Each arm runs A=1, then A=8. Every run uses a fresh process, a 240 s bound,
and a staging path whose probe argument has the reference's exact length.
A failure is preserved as `<case>.failed.<stage>`, and roots are never reused.

## Gates

- **R1, guards.** Probes are byte-identical to the reference, simulated
  statistics are equal (`run_pilot.stats_rows`), `tdma*` counter lines are
  identical with zero violations, and `system.llc.response_domain_prefixes`
  is empty. Together these test both the disabled-path code change and the new
  adapter, on the AES path and the quiet path.
- **R2, defense validity.** gem5 exits 0. A `fatal` for an unmapped requestor
  or a response retry counts as a failure. The prefixes are `cpu0. cpu1.`, and
  scheduler violations are zero.
- **R3, preservation.** A pre-run fingerprint of the project is taken. Changes
  under `.claude/` are listed but exempt, exactly as in the causal experiment.
  Every other file must be unchanged afterwards.

## Primary outcome

For each allocation, compare the defense-aes `probes.bin` with the
defense-quiet `probes.bin` record by record (16-byte records, 64 intervals).

- **PASS, indistinguishable for this pair:** 0 differing records at both
  A=1 and A=8.
- **FAIL:** any differing record. Report the count, the differing intervals
  with their activity labels, and the first differing record.

The baseline is the request-TDMA pair (`tdma-onx` against `tdma-nc0`), which
differs in 1,705 records at A=1 and 1,184 at A=8. Every differing interval is
active.

## Secondary outcomes (descriptive)

- The same record comparison for each defense arm against its no-defense
  counterpart: defense-aes against `tdma-onx`, and defense-quiet against
  `tdma-nc0`.
- AES throughput. Encryptions come from `victim measurement_complete
  encryptions=N`. Defense-aes is compared with the stored single-seed
  `tdma-way` (way-only) and `tdma-onx` (request TDMA) cases.
- Monitor hit latency is not re-tested statistically. Byte-identical
  observations carry no activity information for this pair. Differing
  observations fail the primary outcome on their own.

## If the primary outcome fails

The run stops after the record comparison. Before any further change, a
diagnosis with the version-2 causal trace (`--debug-flags=CausalTrace`) on the
defense-aes case is proposed. No second defense is built without a new design
agreement.

## Claim limits

- A PASS means byte-level noninterference for this one victim pair, seed, and
  activity schedule in gem5. It is not a proof for all inputs and not a
  hardware claim.
- Broadening to other seeds, keys, and an independent schedule is a separate,
  later step.
- The gem5 same-tick convention that this defense targets may not correspond
  to real arbitration.
