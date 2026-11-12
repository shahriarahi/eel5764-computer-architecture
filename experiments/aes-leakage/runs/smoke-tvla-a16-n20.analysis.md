# AES leakage analysis (simulated)

Simulator-only run, public key `f1e2d3c4b5a69788796a5b4c3d2e1f10`, plaintext seed 1466213861.
Windows: 20 analysed of 20 (drop_first=0); victim `tvla`; split off; monitor ways 16.

## Run checks

| check | result | detail |
|---|---|---|
| aes_self_test_pass | PASS | FIPS-197 known-answer line in simout.txt |
| config_matches_simout | PASS | simout header {'key_hex': 'f1e2d3c4b5a69788796a5b4c3d2e1f10', 'seed': 1466213861, 'windows': 20, 'rounds1': 0, 'scrub': 1, 'tvla': 1} vs leak_config {'key_hex': 'f1e2d3c4b5a69788796a5b4c3d2e1f10', 'seed': 1466213861, 'windows': 20, 'rounds1': 0, 'scrub': 1, 'tvla': 1} |
| checksum_matches | PASS | victim pt/ct checksum e5bef135f0419b04c5281d895a47a2ef/9017dc97a15c09f04b5784582546119c vs python e5bef135f0419b04c5281d895a47a2ef/9017dc97a15c09f04b5784582546119c |
| monitor_status_pass | PASS | monitor records=5120 windows=20 errors=[] |
| table_fills_have_vaddr | PASS | victimTableMissingVaddr=0 |

Rotation 130; 68 table lines mapped to distinct logical sets.

## TVLA fixed-vs-random (Welch t)

fixed=10 random=10, max |t| = 185.71, sets with |t| > 4.5: [71, 76, 108, 110, 115, 116, 119, 197]
