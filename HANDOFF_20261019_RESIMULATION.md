# Session Handoff

- Generated: 2026-10-19T04:16:11Z
- Working directory: C:\Users\shahr\OneDrive\Documents\Fall 26\Computer Architecture (branch `main`, d8c79f2)

## Session goal
Finish the causal timing localization (the 2026-10-16 plan) in gem5, build a defense that makes AES activity indistinguishable, test it against the accepted proposal's own criterion, and update the paper, video deck, and Q&A. This doc also serves as the **re-simulation guide**.

## Decisions
- **Causal trace v2.** Every record carries `sched=<tick>`, the tick passed to `sched*`; it is `request_time`, `completion_time`, `when`, or `curTick()+latency` depending on the hook. The alternative was v1, which logged the scheduling tick and put LLC hit latency inside queue residence. Recorded as spec Amendment 1.
- **CPU delivery matching.** Each request is matched to the first same-address `cpu_delivery` after its crossbar forward. The alternative was one-to-one matching, which fails because the TimingSimpleCPU hook also fires for L1D hits. This change was made after seeing data, and is declared.
- **Defense: per-domain LLC CPU-side response queues** (option 1), with domain prefixes `cpu0.` and `cpu1.`. The alternative was fixed response slots or deadlines (option 2), which were not needed. The trace showed the residual was a same-tick slip of 1 tick in the shared LLC response queue (`PacketQueue` `max(when, curTick+1)`), which crossbar edge alignment turns into +999 ticks.
- **Unsupported cases are fatal.** With split queues, a response retry or an unmapped requestor stops the simulation with `fatal`. The alternative, per-queue retry ordering, was not built. Neither case ever occurred.
- **Success criterion.** The monitor's `probes.bin` must be byte-identical between the AES victim and the quiet victim, which is exact in a deterministic simulator. The proposal's frozen decision code was also run unchanged, as the alternative that p-values alone would offer.
- **View root `tdma-rsv`.** The unchanged `analysis/summarize_sweep_v3.py` was run on copies of the v3 controls plus the defended treatments, rather than writing a new summarizer. Validated first: the same method reproduces the stored sweep-v3 summary exactly.
- **Never reuse a result root.** Failed attempts were kept and new 8-character roots were used instead of deleting them.
- **Paper v2 as a new file** (`Group18_EEL5764_Final_Paper_v2.docx`) built by a new script that imports v1. v1 was not overwritten, and the original research question and negative result are kept.
- **Plain HTML pages, not Claude Docs.** The host never confirmed the Docs connector as first-party.

## Bugs / issues surfaced (all fixed)
- **Queue trace stages missing.** The filter used `system.llc.cpu_side`, but the real name is `system.llc.cpu_side_port-CpuSidePort`. Fixed with `llc_response_queue_name()`.
- **WSL import collision.** WSL Python imported the site-packages `validate` (configobj) instead of `experiments/tdma/validate.py`. Fixed by adding the TDMA path only around the `run_pilot` import.
- **Probe-path length mismatch.** References ran in `.<case>.tmp.XXXXXX` staging directories, so the probe-argument lengths are 138 and 137. Fixed by deriving the staging name from the recorded length, and by validating the length before any directory is created.
- **A=8 trace-on timeout.** The 240 s bound was too short while a 442 MB trace was written through `/mnt/c`. Trace runs now have a 900 s bound.
- **Slow `match_timelines`.** It took about 30 min at A=8 because it was O(n²). Fixed with a bisect window; output is byte-identical, and A=1 went from 45 s to 2 s.
- **Plugin state in commits.** A `.claude/handoff-nudge-state.json` file was swept into commits. Untracked it, and added `.claude/` to the worktree's `info/exclude`.

## Next steps (re-running any simulation)
1. **Shell setup.** Run everything in WSL (`wsl.exe -d Ubuntu-26.04 ...`). From Git Bash, prefix with `MSYS_NO_PATHCONV=1`. Use WSL `python3`; Windows Python lacks matplotlib. Set `R="/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture"` and run commands from `$R`.
2. **Pick new result roots first.** Every runner refuses existing roots, so choose new 8-character names (to keep probe-path lengths) and edit the constants:
   - Causal trace: `DISABLED_ROOT`/`ENABLED_ROOT` in `experiments/causal-trace-20261016/run_cases.py`. Add them to `EXCLUDED_PARTS` in that folder's `preserve.py`.
   - Defense endpoints: `ARMS` in `experiments/respq-defense-20261018/run_respq.py`.
   - Defense sweep: `AES_ROOT`/`QUIET_ROOT` in `run_sweep.py` and `VIEW_ROOT` in `summarize_sweep.py`. Add all of them to that folder's `preserve.py`.
   - Output JSON files are opened exclusively (`open("x")`), so pass a new `--out` path.
3. **Commands.** Experiment paths are under `.codex-tmp/tdma-worktree/experiments/`.
   - **Original v3 sweep:** see `RUNBOOK.md` §10C and `scripts/run_repeated_contention_sweep_v3.py`. It uses the unchanged `~/eel5764/gem5` build.
   - **Time slots:** `python3 -B experiments/tdma/run_pilot.py --baseline-root "$R" --phase guard|pilot|remaining`, then `verify_results.py`.
   - **Quiet control:** `python3 -B experiments/quiet-control-20261016/run_control.py --baseline-root "$R" --phase replay|quiet`.
   - **Causal trace:** `python3 -B experiments/causal-trace-20261016/run_cases.py --baseline-root "$R" [--trace]`, then `python -B analyze.py <case> --out analysis/<new>.json`.
   - **Defense endpoints (about 13 min):** `python3 -B experiments/respq-defense-20261018/run_respq.py --baseline-root "$R"`, then `compare_arms.py --baseline-root "$R" --out analysis/<new>.json`.
   - **Defense sweep (48 runs, about 13 min):** `python3 -B experiments/respq-defense-20261018/run_sweep.py --baseline-root "$R" --jobs 6`, then `python3 -B summarize_sweep.py --baseline-root "$R" --out analysis/<new>.json`.
4. **Rebuilding a gem5 tree.** Only needed if a WSL tree is lost.
   - Create the worktree: `git -C ~/eel5764/gem5 worktree add --detach ../<name> c8222cc`.
   - Apply the patch: `git apply <experiment>/gem5-*.patch`. `gem5-causal.patch` includes TDMA. For respq, apply `gem5-causal.patch`, then run `python3 respq-defense-20261018/prepare_gem5.py`.
   - Build inside the tree: `scons build/RISCV/gem5.opt -j14 EXTRAS=/home/shahriarahi/eel5764/gem5_ext`.
   - Expected executable SHA-256 prefixes: gem5 `c259c12e`, timeslot `5a540aed`, causal `2428f123`, respq `66c30701`.
5. **After any rerun.**
   - Run every test suite in both Pythons: `discover -s <dir> -p 'test_*.py'` for `tests`, `experiments/tdma`, `causal-trace-20261016`, and `respq-defense-20261018`.
   - Run that experiment's `preserve.py check` against a fresh pre-run snapshot.
   - Then rebuild the paper: delete or rename `Group18_EEL5764_Final_Paper_v2.docx` (its builder refuses to overwrite), then run `python -B scripts/build_final_paper_v2.py`. Regenerate figures with WSL `python3 scripts/plot_defense_figure.py [--slide]` after deleting the old PNGs.
   - Determinism check: the same command gives byte-identical outputs.
6. **Optional new experiment.** Not started: run AES-vs-AES byte-identity with different keys or plaintexts, and use an independent activity schedule. This would broaden the defense claim.

## Files touched
- **Experiment branch** (`experiment/tdma-prototype`, pushed `1cdd42c`, in `.codex-tmp/tdma-worktree`):
  - `experiments/causal-trace-20261016/*`: trace v2, analyzer, gates, `RESULTS.md`, `progress.md`.
  - `experiments/respq-defense-20261018/*`: design, two preregistrations, patch, runners, results.
  - `docs/superpowers/specs/2026-10-16-causal-timing-localization-design.md`: Amendment 1.
- **`main`** (pushed `d8c79f2`): `Group18_EEL5764_Final_Paper_v2.docx`, `scripts/build_final_paper_v2.py`, `scripts/plot_defense_figure.py`, `results/updated run/defense-figures/*`, `VIDEO_SCRIPT_20261018.md` (14 slides, 651 words), `PEER_QA_ANSWER_BANK_20261018.html` (33 answers), `PROJECT_MAP.html` (file locations).
- **WSL trees:** new `~/eel5764/gem5-respq`; `gem5-causal` was rebuilt for v2, and the v1 executable is kept as `gem5.opt.causal-v1`.
- **Artifacts:** deck EKjoDCPUhVNbgpuURU4WYH (v9, 14 slides), Q&A 85ibvJ4uADnwyPJbjRd82v (v2), map 1QxCHgXyYGtFXZgvMzpQRi.
- **Raw outputs, PC only, not in git:** `results/updated run/tdma-{cd0,cd1,ct1,ct2,ct3,np0,nc0,rga,rgq,rda,rdq,rsa,rsq,rsv}` (about 900 MB in OneDrive).

## Open questions
- Should `experiment/tdma-prototype` be merged into `main`, and should the merged `paper-v2-defense` branch be deleted?
- `project explanation.md` has the user's uncommitted edit, still untouched. Commit it or leave it?
- Should the 840 MB of trace logs (`tdma-ct1/ct2/ct3`) be compressed or moved off OneDrive? This was never done, because raw outputs are preserved as-is.
