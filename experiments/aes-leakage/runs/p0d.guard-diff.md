# Differential test (simulated)

A: `runs/p0b-r1-scrub-n20` (seed 1466213861)
B: `runs/p0d-r1-scrub-n20` (seed 1466213861)
Arm: victim `r1-scrub`, split off, monitor ways 16, 20 windows, OFF_PROBE 593920.

Preconditions: PASS (same binaries, arm, schedule and path lengths; the victims encrypted different data: False).

| quantity | value |
|---|---|
| probes.bin byte-identical | True |
| records | 5120 |
| records whose latency differs | 0 |
| records whose timestamp differs | 0 |
| windows with a latency difference | 0 |
| sets with a latency difference | 0 |
| largest latency difference (cycles) | 0 |

sha256 A `bdc4b47858c2533f56f0fe585666d03cf0605b14073b895a16125998d3f1f0fa`
sha256 B `bdc4b47858c2533f56f0fe585666d03cf0605b14073b895a16125998d3f1f0fa`

DIFF VERDICT: IDENTICAL
