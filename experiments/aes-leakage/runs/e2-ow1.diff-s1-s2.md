# Differential test (simulated)

A: `runs/e2-ow1-s1-n2000` (seed 1466213861)
B: `runs/e2-ow1-s2-n2000` (seed 1466213862)
Arm: victim `r1-scrub`, split 1-15, monitor ways 1, 2000 windows, OFF_PROBE 520192.

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

sha256 A `c388543784a000efed69761cbfe57f32d2240dcf483cc3b0afb2cf04b3e7836c`
sha256 B `9816103d3e61d239ad647a19cd9c735c98dd2d7048f85505fa58d3b429babd09`

DIFF VERDICT: DIFFERENT
