# Separate fixed-slot endpoint experiment

Written before any TDMA efficacy run. The accepted proposal and earlier data
are unchanged. This evaluates way partitioning plus an additional scheduler.

## Frozen design

- Same v3 monitor, AES binary, 4 KiB L1D, 256 KiB 16-way LLC, public inputs,
  original clocks, 64 labelled intervals and output-path lengths.
- Alternating domain 0/1 slots, 4 cycles each on the 1 GHz shared crossbar.
  A request launches only at a slot start; at most one request per slot;
  unused slots are idle. Slot phase is absolute simulated tick zero.
- A in {1,8}. Arms: original unpartitioned, original way-only, new way-plus-slot.
  Seeds 0x5764A5E5, E6, E7. Six first-seed pilot processes, then twelve
  additional processes only if structural/functional validation passes.
- Original arms use the original executable. No tuning from efficacy outcomes.
  Any later change is a dated deviation recorded before another efficacy run.

## Gates and outcomes

1. C++ scheduling unit tests, real gem5 reads/quiet-domain/writeback tests,
   and an explicit fail-fast test for downstream refusal must pass.
2. Four first-seed disabled cases (A=1,8, control and treatment) must reproduce
   original probe bytes and simulated statistics, excluding new TDMA counters
   and host-runtime statistics. Any discrepancy stops efficacy testing.
3. Each efficacy case must pass AES self-test, 16,384 valid probe records,
   65 stats blocks, mapping congruence, and 64 disjoint-way snapshots for
   partitioned arms. TDMA grants must occur for both domains, withholding
   must occur, and overrun/refusal/express-bypass counters must be zero.
4. A failure is preserved and reported, never silently excluded or replaced.
   The first prototype intentionally does not support downstream refusal;
   encountering it makes the trial invalid, not a negative security result.

Prediction: scheduling reduces the active-minus-idle hit-latency effect at
both endpoints relative to way-only. A remaining signal is an acceptable
experimental outcome and stops expansion to A=1..8.

## Analysis fixed before efficacy data

- Use existing `max_set_permutation_test`: maximum over 256 sets, 10,000
  balanced label shuffles, seed 5764. Retain eligible-set rules unchanged.
- Compute the existing hit-only statistic and signed cycles-per-line effect.
  Combine three seed p-values by Fisher; apply Holm across the two endpoints,
  separately for each arm. Apply the same explicitly separate two-endpoint
  families to hit-only p-values. Alpha is 0.05.
- Use existing 2,000-replicate, 90% bootstrap CI with RNG seed 5764. Process
  arms off, way, onx, each in A=1,8 order, with seeds E5,E6,E7. Mean equivalence
  requires the entire CI strictly inside +/-0.02 cycles per probed line.
- The max-set and hit-only analyses answer different questions. An endpoint
  advances only if its matched controls validate, the scheduled arm loses
  max-set and hit-only significance after declared corrections, and its mean
  equivalence check passes. Report every individual seed result as well.
- An undefined statistic is reported as undefined, not assigned an invented
  p-value. The inference gate then remains unresolved and expansion stops.
  Also report the signed all-walk active-minus-idle mean per line descriptively,
  including constant observations; this does not replace undefined inference.
- Report whole-measurement instruction/cycle totals for IPC, demand LLC
  accesses/misses, completed AES encryptions, cycles/encryption and throughput
  relative to matched original arms. IPC includes busy waiting; useful AES
  throughput is the primary performance interpretation.
- This endpoint experiment does not prove distributional indistinguishability.
  No held-out classifier or adversarial adaptive schedule is evaluated here.
  Shared activity schedule across seeds limits independence/generalization.

## Preservation and reproduction

Retain new source, patch, build log, executable hashes, commands, validation,
and outputs separately. Verify the original 3,042-file manifest and baseline
executable hash after execution. The isolated source base is gem5 c8222cc.

## Deviations

None at initial registration. Source/build fixes before efficacy data do not
constitute efficacy tuning; record them in `progress.md` and retain logs.
