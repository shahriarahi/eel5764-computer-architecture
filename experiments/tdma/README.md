# Separate fixed-slot prototype

Exploratory follow-up to the original way-partitioning study. The original
proposal, source, workloads, executable and results are preserved. New code
is on branch `experiment/tdma-prototype` in a separate project worktree.

The prototype alternates 4 ns request-service slots between the monitor and
AES domains. Each slot permits at most one launch; idle slots stay idle.
All normal request traffic, including dirty writebacks, obeys the schedule.
Transfers must finish strictly before the next slot. Unsupported downstream
refusal, express-snoop bypass or unexpected request-layer contention stops
the simulation explicitly. This is not a general-purpose stall-tolerant
interconnect or an indistinguishability proof.

## Files

- `DESIGN.md`, `PLAN.md`, `PREREGISTRATION.md`: scope, execution plan and frozen experiment rules.
- `gem5-timeslot.patch`, `slot_schedule.hh`, `prepare_gem5.py`: isolated simulator change and its source helper.
- `run_contention_tdma.py`: parameter adapter around the unchanged original config.
- `run_structural.py`, `test_traffic.py`: actual gem5 structural tests.
- `run_pilot.py`, `validate.py`, `summarize.py`: endpoint runs, validation and analysis.
- `preserve.py`, `preservation.json`, `progress.md`: preservation evidence and execution ledger.

## Verification and fresh runs

From PowerShell at the original project root:

```powershell
$tdmaDirectory = Join-Path (Get-Location) '.codex-tmp\tdma-worktree\experiments\tdma'
$tdmaProject = '/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture'
wsl.exe --cd "$tdmaDirectory" --exec python3 -m unittest discover -p 'test_*.py'
wsl.exe --cd "$tdmaDirectory" --exec python3 run_structural.py
wsl.exe --cd "$tdmaDirectory" --exec python3 run_pilot.py --baseline-root "$tdmaProject" --phase guard
wsl.exe --cd "$tdmaDirectory" --exec python3 run_pilot.py --baseline-root "$tdmaProject" --phase pilot
wsl.exe --cd "$tdmaDirectory" --exec python3 run_pilot.py --baseline-root "$tdmaProject" --phase remaining
```

Run each phase only after the preceding gates pass. Existing output
directories are refused; these commands intentionally do not overwrite or
resume previous runs. Analysis requires an explicitly new `--out` directory.

The isolated executable is `~/eel5764/gem5-timeslot/build/RISCV/gem5.opt` in
WSL. The original executable remains `~/eel5764/gem5/build/RISCV/gem5.opt`.
The retained patch applies to gem5 commit c8222cc67a399bfc01e8658dd14b30d5bfd634f9;
the requestor-partition extension remains the original `gem5_ext`.

Results are new directories under the original project root:
`results/updated run/tdma-gd0`, `tdma-off`, `tdma-way`, `tdma-onx`.
Their eight-character names preserve the monitor's probe-path argument
length. First-seed pilot observations are not the final three-seed inference.
See `progress.md` for current execution status; only actual results establish
whether a gate passed.
