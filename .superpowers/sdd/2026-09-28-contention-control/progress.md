# SDD ledger — plan: docs/superpowers/plans/2026-09-28-contention-control.md

Setup ruling: the project directory is not a Git repository, so no isolated worktree, task commits, merge base, or generated review package is available — execute in the current project directory as explicitly requested and preserve every existing file/result — cost if wrong: changes lack Git rollback and must be reviewed by file list and tests.

Pre-flight: Task 1 produces validated samples and metrics consumed by Task 5; interfaces match.
Pre-flight: Task 2 produces AES and schedule APIs consumed by Task 3; interfaces match.
Pre-flight: Task 3 produces `monitor`/`victim` binaries and log markers consumed by Task 4; interfaces match.
Pre-flight: Task 4 produces the result artifact set consumed by Task 5; interfaces match.

Task 1 ruling: the initial seed test compared the 95th percentile, but this discrete null distribution gives the same percentile under two seeds; compare corrected empirical p-values instead — this still proves the PRNG seed affects the null draws — cost if wrong: a regression that ignores the seed might escape if it coincidentally preserves the p-value.
Task 1: complete (no Git commits available; tests: `python -m unittest discover -s tests -v` → 11/11 pass).
Task 2: complete (no Git commits available; tests: WSL `gcc -std=c11 -Wall -Wextra -Werror` known-answer and schedule binaries → 2/2 pass).
Task 3: complete (no Git commits available; tests: Python 11/11, portable C 2/2, RISC-V workload build/ELF checks PASS).
Task 4 ruling: use a staging result directory and preserve failed runs under timestamped names rather than writing directly to the final path — this permits diagnosis and retry without deleting raw output — cost if wrong: recorded command paths name the staging directory that was later moved.
Task 4: complete (no Git commits available; tests: Python 16/16, Python byte-compilation PASS, shell syntax PASS).
Task 5 ruling: gem5 executes configs as `__m5_main__`, not `__main__`; support both while keeping ordinary imports side-effect free — cost if wrong: a different gem5 launcher name would again exit without running the configuration.
Task 5 ruling: gem5 automatically writes a second final statistics block after post-measurement logging; preserve both raw blocks and analyze only the explicitly dumped first block — cost if wrong: choosing the wrong block would contaminate IPC and miss rate with serialization work.
Task 5: complete (no Git commits available; control artifacts PASS structural validation; analysis decision FAIL with SNR 0.123071, null95 0.502195, p 0.619938; Python 17/17, portable C 2/2, RISC-V binary checks PASS).

Final review: self-review (subagent dispatch not permitted for this task). Review Focus checked: interval timestamps, complete/unique pairs, cross-component labels, zero variance, and measurement-only first stats block all have tests. No Critical, Important, or Minor findings. Partitioned contention runs were deliberately not reviewed because the failed control forbids them; causal attribution for the failed signal was also set aside because the data supports consistency with private-L1 residency, not proof.

