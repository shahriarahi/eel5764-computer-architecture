# Response-queue defense — execution history

## 2026-10-18

- **Design and preregistration.** The user approved the design. It is recorded
  in `DESIGN.md`, and `PREREGISTRATION.md` and the code were committed in
  `d99f041`, before any output existed.
- **Worktree.** `gem5-respq` was created from `c8222cc` with `gem5-causal.patch`
  applied. Its source tree is identical to `gem5-causal`. `prepare_gem5.py`
  then applied the edits.
- **Build.** `respq-build-01` used a build directory seeded from `gem5-causal`.
  It exited 0 after 333 s and compiled 873 units. The executable is
  `66c30701…`.
- **Runs.** `preservation-prerun.json` recorded 12,617 files. `run_respq.py`
  ran all eight cases in order and they passed, in 784 s.
- **Outcome.** The primary outcome passed: 0 differing records at A=1 and A=8.
  R3 passed with one explained user/OneDrive addition under
  `lecture slides/`. Test suites passed under both Pythons.
- **Sweep.** The preregistration (`a9db877`) and the outcome script
  (`ed2c88f`) were committed before any results existed. The view-root method
  reproduced the stored v3 summary exactly.
- **Run.** `run_sweep.py` ran all 48 cases and they passed, in 785 s with
  6 jobs.
- **Outcome.** `summarize_sweep.py` reported both primary outcomes as PASS:
  the collapse point is 1/15 and byte identity holds in 24/24 cases. No
  protected file changed.
