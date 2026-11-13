# Differential test (simulated)

A: `runs/e2-fw8-s1-n2000` (seed 1466213861)
B: `runs/e2-fw8-s2-n2000` (seed 1466213862)
Arm: victim `full-scrub`, split 8-8, monitor ways 8, 2000 windows, OFF_PROBE 520192.

Preconditions: PASS (same binaries, arm, schedule and path lengths; the victims encrypted different data: True).

| quantity | value |
|---|---|
| probes.bin byte-identical | False |
| records | 512000 |
| records whose latency differs | 18289 |
| records whose timestamp differs | 452439 |
| windows with a latency difference | 2000 |
| sets with a latency difference | 14 |
| largest latency difference (cycles) | 24 |

sha256 A `74c74989de2d7ae4b7907ad8793ccd54933146f5424f7befefe02dccda101b97`
sha256 B `b4c75858b8d8beb7cc587cafa9b26cb0b7a09ca3b3c35eb557e0809bdd822f7a`

DIFF VERDICT: DIFFERENT
