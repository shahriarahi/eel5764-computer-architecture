# Differential test (simulated)

A: `runs/e2-ow8-s1-n2000` (seed 1466213861)
B: `runs/e2-ow8-s2-n2000` (seed 1466213862)
Arm: victim `r1-scrub`, split 8-8, monitor ways 8, 2000 windows, OFF_PROBE 520192.

Preconditions: PASS (same binaries, arm, schedule and path lengths; the victims encrypted different data: True).

| quantity | value |
|---|---|
| probes.bin byte-identical | False |
| records | 512000 |
| records whose latency differs | 3006 |
| records whose timestamp differs | 408416 |
| windows with a latency difference | 1790 |
| sets with a latency difference | 3 |
| largest latency difference (cycles) | 16 |

sha256 A `5d4b3eb5b23672c3880b6cbe5d462c4b5ff5f27dcf7468038da39cf6f932d36c`
sha256 B `042107a2f79ddca9c3c5c5c0379a61a7db912c94de2b1ac4c7e583592e7f8ad0`

DIFF VERDICT: DIFFERENT
