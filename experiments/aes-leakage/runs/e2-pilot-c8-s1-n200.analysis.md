# AES leakage analysis (simulated)

Simulator-only run, public key `f1e2d3c4b5a69788796a5b4c3d2e1f10`, plaintext seed 1466213861.
Windows: 200 analysed of 200 (drop_first=0); victim `r1-scrub`; split off; monitor ways 8.

## Run checks

| check | result | detail |
|---|---|---|
| aes_self_test_pass | PASS | FIPS-197 known-answer line in simout.txt |
| config_matches_simout | PASS | simout header {'key_hex': 'f1e2d3c4b5a69788796a5b4c3d2e1f10', 'seed': 1466213861, 'windows': 200, 'rounds1': 1, 'scrub': 1, 'tvla': 0} vs leak_config {'key_hex': 'f1e2d3c4b5a69788796a5b4c3d2e1f10', 'seed': 1466213861, 'windows': 200, 'rounds1': 1, 'scrub': 1, 'tvla': 0} |
| checksum_matches | PASS | victim pt/ct checksum 21e368fc7c924d329fa8506022a58219/00000000000000000000000000000000 vs python 21e368fc7c924d329fa8506022a58219/85a645fc818cbe0459dceb488511880a (ct not computed in round-1 mode) |
| monitor_status_pass | PASS | monitor records=51200 windows=200 errors=[] |
| table_fills_have_vaddr | PASS | victimTableMissingVaddr=0 |

Rotation 130; 68 table lines mapped to distinct logical sets.

## Attribution (location-aware, known key, Holm over 96 tests)

| hypothesis | bytes significant | mean z | min Holm p |
|---|---|---|---|
| p_xor_k | 0/16 | 0.00 | 1 |
| p_only | 0/16 | 0.00 | 1 |
| shuffled | 0/16 | 0.00 | 1 |
| lr_c_xor_k10 | 0/16 | 0.00 | 1 |
| c_only | 0/16 | 0.00 | 1 |
| lr_shuffled | 0/16 | 0.00 | 1 |

Round 1 (Te tables, 16 lines) per-byte labels: {'none': 16}

Last round (sbox, 4 lines) per-byte labels: {'none': 16}

## Decision (preregistered rule, alpha = 0.05)

| statement | supported | bytes |
|---|---|---|
| round1_plaintext_plus_key | no | [] |
| round1_plaintext_only | no | [] |
| lastround_c_xor_k10 | no | [] |
| lastround_ciphertext_only | no | [] |

## Detection (location-free ANOVA; cannot tell p from p^k)

| partition | bytes significant | reliable |
|---|---|---|
| first_round | 0/16 | yes |
| last_round | 0/16 | yes |
| c_line | 0/16 | yes |
| shuffled | 0/16 | yes |

## Ground truth from the simulator trace

Recall 0.000, precision n/a; 0 fills in the AES phase, 0 outside it, 68 before measurement; mean fills per window 0.00. The trace records LLC allocations only, so lines that stay resident in the LLC leave no fill.
