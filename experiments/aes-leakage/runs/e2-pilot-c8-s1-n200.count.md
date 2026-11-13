# Collision-count test, location-free (simulated)

Run `runs/e2-pilot-c8-s1-n200`: victim `r1-scrub`, split off, monitor ways 8, 200 windows, seed 1466213861; overlap schedule: True (OFF_PROBE 520192, OFF_ENC 524288).
Pearson r between a per-window model count and a per-window monitor feature; two-sided permutation p (10000 shuffles, seed 5764), Holm over 8 tests.

| feature | mean | sd | max |
|---|---|---|---|
| excess_cycles | -3.010 | 12.622 | 160.0 |
| delayed_walks | 0.525 | 0.556 | 3.0 |

| model | feature | r | Holm p |
|---|---|---|---|
| lines_all_rounds | excess_cycles | +0.2175 | 0.028 |
| lines_all_rounds | delayed_walks | -0.0396 | 1 |
| lines_round1_p_xor_k | excess_cycles | +0.2175 | 0.028 |
| lines_round1_p_xor_k | delayed_walks | -0.0396 | 1 |
| lines_round1_p_only | excess_cycles | +0.0145 | 1 |
| lines_round1_p_only | delayed_walks | -0.0062 | 1 |
| shuffled | excess_cycles | +0.0072 | 1 |
| shuffled | delayed_walks | +0.0379 | 1 |

| statement | supported |
|---|---|
| count_dependent | yes |
| round1_count_plaintext_plus_key | yes |
| round1_count_plaintext_only | no |
