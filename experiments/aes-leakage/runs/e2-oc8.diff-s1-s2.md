# Differential test (simulated)

A: `runs/e2-oc8-s1-n2000` (seed 1466213861)
B: `runs/e2-oc8-s2-n2000` (seed 1466213862)
Arm: victim `r1-scrub`, split off, monitor ways 8, 2000 windows, OFF_PROBE 520192.

Preconditions: PASS (same binaries, arm, schedule and path lengths; the victims encrypted different data: True).

| quantity | value |
|---|---|
| probes.bin byte-identical | False |
| records | 512000 |
| records whose latency differs | 3037 |
| records whose timestamp differs | 401989 |
| windows with a latency difference | 1796 |
| sets with a latency difference | 3 |
| largest latency difference (cycles) | 16 |

sha256 A `916afdc27f4cbcc07bda5c9313b0eab7da9ecce9fe4f2d902050c04bf3f320b8`
sha256 B `a05b32e0f76566029a7fecd1d715987156437b31979b031ecc3042622500365c`

DIFF VERDICT: DIFFERENT
