# AES leakage analysis (simulated)

Simulator-only run, public key `f1e2d3c4b5a69788796a5b4c3d2e1f10`, plaintext seed 1466213861.
Windows: 20 analysed of 20 (drop_first=0); victim `r1-scrub`; split off; monitor ways 16.

## Run checks

| check | result | detail |
|---|---|---|
| aes_self_test_pass | PASS | FIPS-197 known-answer line in simout.txt |
| config_matches_simout | PASS | simout header {'key_hex': 'f1e2d3c4b5a69788796a5b4c3d2e1f10', 'seed': 1466213861, 'windows': 20, 'rounds1': 1, 'scrub': 1, 'tvla': 0} vs leak_config {'key_hex': 'f1e2d3c4b5a69788796a5b4c3d2e1f10', 'seed': 1466213861, 'windows': 20, 'rounds1': 1, 'scrub': 1, 'tvla': 0} |
| checksum_matches | PASS | victim pt/ct checksum 8a277d047af75bcd12f1988659916941/00000000000000000000000000000000 vs python 8a277d047af75bcd12f1988659916941/dc66ddb100aab00151d8eff4a8d52612 (ct not computed in round-1 mode) |
| monitor_status_pass | PASS | monitor records=5120 windows=20 errors=[] |
| table_fills_have_vaddr | PASS | victimTableMissingVaddr=0 |

Rotation 130; 68 table lines mapped to distinct logical sets.

## Attribution (location-aware, known key, Holm over 96 tests)

| hypothesis | bytes significant | mean z | min Holm p |
|---|---|---|---|
| p_xor_k | 16/16 | 7.85 | 2.75e-15 |
| p_only | 0/16 | -0.92 | 1 |
| shuffled | 0/16 | -0.35 | 1 |
| lr_c_xor_k10 | 0/16 | 0.00 | 1 |
| c_only | 0/16 | 0.00 | 1 |
| lr_shuffled | 0/16 | 0.00 | 1 |

Round 1 (Te tables, 16 lines) per-byte labels: {'plaintext_plus_key': 16}

Last round (sbox, 4 lines) per-byte labels: {'none': 16}

## Decision (preregistered rule, alpha = 0.05)

| statement | supported | bytes |
|---|---|---|
| round1_plaintext_plus_key | yes | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] |
| round1_plaintext_only | no | [] |
| lastround_c_xor_k10 | no | [] |
| lastround_ciphertext_only | no | [] |

## Detection (location-free ANOVA; cannot tell p from p^k)

| partition | bytes significant |
|---|---|
| first_round | 13/16 |
| last_round | 0/16 |
| c_line | 1/16 |
| shuffled | 16/16 |

## Ground truth from the simulator trace

Recall 1.000, precision 1.000; 289 fills in the AES phase, 0 outside it, 68 before measurement; mean fills per window 14.45. The trace records LLC allocations only, so lines that stay resident in the LLC leave no fill.

Null calibration: 0.008 of 640 shuffled z > 2.33 (expect ~0.01), sd 0.74 (expect ~1).
