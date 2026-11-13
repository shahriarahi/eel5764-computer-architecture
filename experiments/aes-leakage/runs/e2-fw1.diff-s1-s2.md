# Differential test (simulated)

A: `runs/e2-fw1-s1-n2000` (seed 1466213861)
B: `runs/e2-fw1-s2-n2000` (seed 1466213862)
Arm: victim `full-scrub`, split 1-15, monitor ways 1, 2000 windows, OFF_PROBE 520192.

Preconditions: PASS (same binaries, arm, schedule and path lengths; the victims encrypted different data: True).

| quantity | value |
|---|---|
| probes.bin byte-identical | False |
| records | 512000 |
| records whose latency differs | 22234 |
| records whose timestamp differs | 275465 |
| windows with a latency difference | 2000 |
| sets with a latency difference | 67 |
| largest latency difference (cycles) | 6 |

sha256 A `ca376191d0052568827c86220525919c09109d5bb3553af625a559ac3c33e1bd`
sha256 B `09ad3bc1e625e616be59e325968e319ec193703857ce15299bde8d1b25e6283f`

DIFF VERDICT: DIFFERENT
