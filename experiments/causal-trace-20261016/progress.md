# Causal trace — execution history

## 2026-10-18

- **Structural tracing.**
  - `structural-01` and `structural-02` (version 1) failed to log the queue
    stages. The cause was a queue-name filter mismatch:
    `system.llc.cpu_side` versus gem5's
    `system.llc.cpu_side_port-CpuSidePort`.
  - `structural-02` also exposed that the validator wrongly required a
    `response_retry` event.
  - `structural-03` passed (commit `38a1edd`).
- **Trace version 2 (spec Amendment 1).** Version-1 hooks logged scheduling
  ticks, not readiness ticks, which put LLC hit latency inside queue residence.
  After the rebuild (`causal-build-05`, 88 s), `structural-04` passed (commit
  `fa8d4ea`). The version-1 executable is kept as `gem5.opt.causal-v1`.
- **Freeze.** Preregistered at `99daa23`, with the `.claude` preservation
  exemption at `edaae2d`. `preservation-prerun.json` was created with
  12,414 files.
- **Step 1, attempt 1: failed before simulation.** `run_cases.py` raised
  `ImportError: cannot import name 'validate_case' from 'validate'`
  (`/usr/lib/python3/dist-packages/validate`). An earlier change had moved the
  TDMA helper directory after site-packages. The import ran before result-root
  creation, so no `tdma-cd0` output exists. The fix scopes the TDMA path to the
  `run_pilot` import, and `test_imports.py` now runs under both Windows and WSL
  Python. G4 is implemented as `gates.py`.
