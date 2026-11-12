# Raw-cycle effect size (simulated)

Run `runs/p1-r1-scrub-n2000`: victim `r1-scrub`, split off, monitor ways 16, 2000 windows, seed 1466213861.
Permutation p-values: 10000 window shuffles, seed 5764 (smallest possible p 0.000100); Holm over 96 tests; alpha 0.05; materiality margin 0.02 cycles per probed line.

| hypothesis | mean effect (cycles per set walk) | per probed line | bytes significant | significant and material |
|---|---|---|---|---|
| p_xor_k | 2176.722 | 136.0451 | 16/16 | 16/16 |
| p_only | -142.009 | -8.8756 | 0/16 | 0/16 |
| shuffled | 9.479 | 0.5924 | 0/16 | 0/16 |
| lr_c_xor_k10 | 0.000 | 0.0000 | 0/16 | 0/16 |
| c_only | 0.000 | 0.0000 | 0/16 | 0/16 |
| lr_shuffled | 0.000 | 0.0000 | 0/16 | 0/16 |

| statement (significant, beats its alternative and its shuffled control, and material) | supported | bytes |
|---|---|---|
| round1_plaintext_plus_key | yes | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] |
| round1_plaintext_only | no | [] |
| lastround_c_xor_k10 | no | [] |
| lastround_ciphertext_only | no | [] |

Slow-versus-touched over the 68 table-line sets: touched and slow 29095, touched and fast 0, untouched and slow 0, untouched and fast 106905 (136000 cells); exact indicator: True.
