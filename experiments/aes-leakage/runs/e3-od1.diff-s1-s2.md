# Differential test (simulated)

A: `runs/e3-od1-s1-n2000` (seed 1466213861)
B: `runs/e3-od1-s2-n2000` (seed 1466213862)
Arm: victim `r1-scrub`, split 1-15, monitor ways 1, 2000 windows, OFF_PROBE 520192.

Preconditions: PASS (same binaries, arm, schedule and path lengths; the victims encrypted different data: True).

| quantity | value |
|---|---|
| probes.bin byte-identical | True |
| records | 512000 |
| records whose latency differs | 0 |
| records whose timestamp differs | 0 |
| windows with a latency difference | 0 |
| sets with a latency difference | 0 |
| largest latency difference (cycles) | 0 |

sha256 A `f243ce3e6a6ce617607d2d3736520fb79b0a0b93d02f3b823a26065ed5801588`
sha256 B `f243ce3e6a6ce617607d2d3736520fb79b0a0b93d02f3b823a26065ed5801588`

DIFF VERDICT: IDENTICAL
