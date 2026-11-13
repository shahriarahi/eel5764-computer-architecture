# Result folders kept out of git

Recorded 2026-11-09. These gem5 output folders exist only in the original
workspace (`results/updated run/` under the OneDrive project folder on the
group's Windows machine). They are not committed, so a clone of this
repository does not contain them.

| Folder | Size | Contents | Why it is not committed |
|---|---|---|---|
| `tdma-ct3` | 489 MB | Causal-trace runs used in paper Section IX.B (`causal.log` is 68 MB at 1/15 and 442 MB at 8/8) | `causal.log` exceeds GitHub's 100 MB file limit |
| `tdma-ct2` | 283 MB | Causal-trace attempt preserved after the 8/8 case hit the runner timeout | Failed attempt; large trace |
| `tdma-ct1` | 67 MB | First causal-trace attempt, preserved after failure | Failed attempt; large trace |

What these runs did and what they found is recorded in
`experiments/causal-trace-20261016/RESULTS.md`; per-file SHA-256 hashes
taken before later runs are in that experiment's `preservation-*.json`
files.

Every other `tdma-*` result folder is committed on this branch: the request
time-slot pilot (`tdma-gd0`, `tdma-off`, `tdma-onx`, `tdma-way`), the quiet
control (`tdma-np0`, `tdma-nc0`), the causal-trace disabled-path runs
(`tdma-cd0`, a preserved failed attempt, and `tdma-cd1`), and the folders
cited by the final paper's Section IX tables (`tdma-rsv`, `tdma-rsa`,
`tdma-rsq`, `tdma-rda`, `tdma-rdq`, `tdma-rga`, `tdma-rgq`).
