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
- **Step 1, attempt 2: failed before simulation.** The runner's own guard
  raised `probe argument length differs from reference` (126 vs 138). The
  `tdma-onx` references ran in `.<case>.tmp.XXXXXX` staging directories, while
  `run_cases.py` named staging with the final-name length. The leftover is an
  empty `tdma-cd0/seed-5764a5e5/plom`. It is preserved, with
  `tdma-cd0/FAILED.json` added as the only new file.
- **Fix and deviation.** Staging names are now derived from the reference
  `probe_argument_length` and checked for every case before any directory is
  created. **Deviation from the preregistration:** the roots are
  `tdma-cd1`/`tdma-ct1` instead of `tdma-cd0`/`tdma-ct0`, and `preserve.py`
  excludes them. The new names have the same length, so the probe paths still
  match the references exactly. Nothing else in the frozen plan changes.
- **Step 1, attempt 3: passed.** Both `tdma-cd1` cases passed G1 and G4
  (1,040 `tdma*` lines, 0 violations). The run took 184 s.
- **Step 2, attempt 1: A=1 passed G2 and failed G3.** Probe bytes and simulated
  statistics matched `tdma-onx`, but the error was
  `cpu_delivery: expected 33024 events, found 98560`. Per the preregistration,
  execution stopped and A=8 was not run. The case is preserved as
  `tdma-ct1/seed-5764a5e5/1-15.failed.wzagvjiuodbtukpd`.
  - **Cause.** The CPU hook also fires for L1D hits, which never reach the L2
    bus. Each of the 33,024 crossbar forwards is followed in tick order by a
    same-address delivery. The other 65,536 deliveries have no forward. The
    short structural window contained no L1D hits, so it could not expose this.
- **Post-hoc matcher change (deviation; made after seeing data).** A
  timeline's delivery is now the first `cpu_delivery` at or after its forward.
  It must have the same address, and same-tick duplicates are rejected. Other
  deliveries are counted as `l1d_deliveries`. Re-validating the preserved case
  read-only gives 33,024 timelines and 65,536 L1D deliveries. Step 2 reruns
  into the new root `tdma-ct2`. The executable, gates G1, G2, G4, and G5, and
  the analysis rules are unchanged.
- **Step 2, attempt 2.** A=1 passed G2, G3, and G4: 33,024 timelines and
  65,536 L1D deliveries. Its `causal.log` and `probes.bin` are byte-identical
  to the preserved `tdma-ct1` A=1 case. A=8 hit the 240 s runner timeout after
  writing 226 MB of trace and half the probe records. It is preserved as
  `tdma-ct2/seed-5764a5e5/8-8.failed.lvuythtwjblxjtq`.
- **Deviation.** Trace-enabled cases now have a 900 s bound; trace-disabled
  cases keep 240 s. This bound is runner-only, and deterministic simulation does
  not depend on it. Both endpoints rerun into the fresh root `tdma-ct3`, so the
  analysis comes from one complete root. The repeated A=1 run doubles as a third
  determinism check.
