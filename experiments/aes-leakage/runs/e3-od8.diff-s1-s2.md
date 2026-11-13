# Differential test (simulated)

A: `runs/e3-od8-s1-n2000` (seed 1466213861)
B: `runs/e3-od8-s2-n2000` (seed 1466213862)
Arm: victim `r1-scrub`, split 8-8, monitor ways 8, 2000 windows, OFF_PROBE 520192.

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

sha256 A `2671df083cee874ae11f0dafdc6b57190e597ee05fe6f19309e0c74f1f6417e4`
sha256 B `2671df083cee874ae11f0dafdc6b57190e597ee05fe6f19309e0c74f1f6417e4`

DIFF VERDICT: IDENTICAL
