# Differential test (simulated)

A: `runs/e2-oc1-s1-n2000` (seed 1466213861)
B: `runs/e2-oc1-s2-n2000` (seed 1466213862)
Arm: victim `r1-scrub`, split off, monitor ways 1, 2000 windows, OFF_PROBE 520192.

Preconditions: PASS (same binaries, arm, schedule and path lengths; the victims encrypted different data: True).

| quantity | value |
|---|---|
| probes.bin byte-identical | False |
| records | 512000 |
| records whose latency differs | 1989 |
| records whose timestamp differs | 179634 |
| windows with a latency difference | 1264 |
| sets with a latency difference | 10 |
| largest latency difference (cycles) | 4 |

sha256 A `884210fff8f59bcc0a056006856426a6e695912820e5ba8c12184ae659bb8c20`
sha256 B `13675408f66fcaccf8fc73b4f213b263b4011a77508c54977fe3648c749db422`

DIFF VERDICT: DIFFERENT
