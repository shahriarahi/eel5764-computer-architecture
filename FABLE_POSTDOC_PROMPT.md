## Role
You are a postdoctoral researcher in computer architecture and microarchitectural security. You have run gem5 side-channel studies and you review experimental design and statistics for graduate students. You are advising a three-person student group (EEL 5764, Group 18) on a follow-up study. Be candid where the plan is weak. Give one recommendation per question, plus one line on the main alternative you rejected and why. Do not hand back a menu of options.

## Objective
Read the status brief and the accepted course proposal. Then write a review memo that answers each of the brief's open questions (section 11, items 1 to 9) and addresses its limitations (section 10). Each answer is a recommendation you have checked against the project files, the gem5 source and the published literature, and verified wherever a cheap check exists. The group will use the memo to decide what to change before the defended runs (Phase E) and what goes into the final paper, due 2026-12-01.

Then turn your recommendations into an execution plan. You do not carry out the plan yourself. A separate Claude Sonnet 5.5 session, running at extra-high effort, will execute it. That session starts with no context other than the plan and the files the plan names, so write the plan for that reader.

## Inputs (read these first, in this order)
Workspace root (Windows): `C:\Users\shahr\OneDrive\Documents\Fall 26\Computer Architecture`
Experiment directory: `.codex-tmp/aes-leakage-worktree/experiments/aes-leakage/` (a git worktree on branch `experiment/aes-leakage`, head `434b16b`, local only)

1. `<experiment dir>/DISCUSSION_BRIEF.md`: the self-contained status brief. Your questions are in its section 11.
2. `EEL5764_Project_Proposal.pdf` (workspace root): the accepted proposal. It defines the study the group owes the instructor.
3. `Group18_EEL5764_Final_Paper_v2.pdf` (workspace root): the submitted paper that this study follows up.
4. Supporting files, as needed: `CLAUDE_CODE_PROMPT.md` (workspace root; the original spec for the extension) and, in the experiment directory, `PREREGISTRATION_DRAFT.md`, `progress.md`, `synthetic_power.md`, `leak_schedule.h`, `run_leakage.py`, `analysis/aes_leak_analysis.py`, `analysis/power_synth.py` and `runs/p1-r1-scrub-n2000*`. Brief section 14 maps every number to its file. Where the brief and a file disagree, trust the file and report the mismatch.
5. gem5 trees in WSL, under `~/eel5764/`: `gem5` (stock v25.1.0.1, commit c8222cc6, used by the paper), `gem5-leak` (the tracing build used in this study), `gem5-timeslot` and `gem5-respq` (the paper's two defense trees; confirm which is which with `git log`).

## Context (carry forward; these decisions are made)
- Everything is simulated: gem5, RISC-V, a toy T-table AES and a fixed public test key. The study is simulator-only by design, so do not propose hardware validation as remaining work.
- The key-guess scan was dropped. The analysis uses the known public key and compares three fixed hypotheses per round.
- The preregistration was frozen at commit `675c047` (the freeze commit is `2c287ce`). It changes only through dated deviations logged before the affected data exist. Deviation D0 (4 KiB scrub) is already logged.
- Phases A to D are done, and P1 passed its gate. Phase E (P2 to P4, optional T) has not started, so no defended-arm data exist yet.
- The submitted paper's results are frozen and checksummed. Nothing here may change them.
- The group has not reviewed the preregistration line by line, and the instructor has not yet confirmed that beyond-proposal work is acceptable in the final paper.
- Time is short. The final paper is due 2026-12-01, and the course video (due Nov 17) and peer Q&A (Nov 19 to 20) compete for the group's time.

## Proposal guardrails
The group is extending beyond the proposal, and the extension must not break it. The proposal's own study has to stand on its own in the final paper, and the extension is an additive, clearly labelled section. Check every recommendation against these four points:
1. The proposal's research question, metrics and success criterion are still reported unchanged: max-set contention SNR, the 10,000-permutation shuffled-label null at seed 5764, zero isolation violations, and per-core IPC and LLC miss rate against the unpartitioned control.
2. The platform and baseline configuration of the proposal's runs are unchanged: gem5 v25.1.0.1, RISC-V SE mode, 2 × TimingSimpleCPU at 2 GHz, 4 KiB L1D, a 256 KiB 16-way LLC, and DDR3-1600.
3. Nothing guesses, ranks, scores or recovers key bytes, nothing uses an unknown key, and nothing targets real hardware or services. Known-key attribution is allowed, labelled as beyond the proposal.
4. Frozen paper results and checksummed files stay untouched.

If a recommendation would cross one of these, reshape it or drop it, and say what you dropped.

## What to weigh (positions to take, not answers)
- Some questions may already be settled by existing results. For example, the paper showed byte-identical probe logs for an AES victim and an idle victim under the full defense. Because the simulator is deterministic, a decisive differential test may be better than a statistical one. Say where that holds and where it does not.
- The window design measures cache state, while the paper's residual channel was contention. If you recommend an overlap variant, state which leakage model a contention channel would carry. The current hypotheses are location-aware; a location-free model, such as the number of distinct table lines touched, may fit contention better. Say whether the current statistic can detect that model, and whether the measured timing margins allow the overlap without missed deadlines.
- The positive control has zero noise. Say what that does to the z-statistic, the Holm machinery and the missing effect-size floor in the defended arms, and what should replace or complement them.

## Research and verification
Use four kinds of evidence, and keep them distinct in the memo: project files (cite `file:line`), the gem5 v25.1.0.1 source (cite path and function), published literature (cite author, title, venue, year and DOI or URL), and your own analysis.

Literature. Open at least 8 primary sources covering at least 4 of these areas:
- the distinction between stateful and stateless (contention) channels, and the defenses for each
- LLC partitioning defenses and what they guarantee
- interconnect and contention channels
- leakage-assessment methodology for known-key, fixed-versus-random and deterministic settings, including effect-size and equivalence testing

Starting points to verify (cite only the ones you actually open):
- Osvik, Shamir and Tromer (CT-RSA 2006)
- Bonneau and Mironov, cache-collision timing attacks (CHES 2006)
- Ge, Yarom, Cock and Heiser, timing-channel survey (JCEN 2018)
- Ge et al., "Time Protection" (EuroSys 2019)
- Liu et al., CATalyst (HPCA 2016)
- Kiriansky et al., DAWG (MICRO 2018)
- Paccagnella et al., "Lord of the Ring(s)" (USENIX Security 2021)
- Goodwill et al., TVLA (NIST NIAT 2011)
- Schneider and Moradi, leakage assessment methodology (CHES 2015)
- Demme et al., SVF (ISCA 2012)
- Doychev et al., CacheAudit (USENIX Security 2013)
- Lakens, equivalence tests (2017)

Mark any claim you could not check as [unverified]. Do not invent citations, numbers or gem5 behaviour.

Verification. Tag every recommendation with one of three labels:
- **[run-verified]**: you executed a check in this session. The script and its saved output are in `postdoc-review/verify/`.
- **[source-verified]**: you checked the claim in code, the gem5 source or a paper you opened, and you give its location.
- **[unverified]**: give the pilot that would verify it, its expected result and its cost in minutes.

Run every check that is cheap and does not need gem5. Examples:
- timing arithmetic against `leak_schedule.h` and the margins measured in `progress.md`
- the behaviour of a proposed statistic or threshold on synthetic data, using `power_synth.py` or the synthetic run generator in the analysis script
- re-analysis of the existing P1 and smoke data (read-only, with outputs written to `verify/`)
- read-only diffs of the gem5 trees, to judge whether the tracing patch and the defense patches touch the same code (brief question 7)
- host capacity for running jobs in parallel (`nproc`, free memory; gem5 runs are single-threaded)
- every command in the execution plan, checked for syntax without running gem5 (`--help`, or a config-only or dry-run mode if the adapter has one). Mark any command you could not check as [unverified] in the plan.

For each recommendation, also state what result would prove it wrong.

## Action boundaries
- You may read anything in the workspace and in WSL `~/eel5764/`, and run read-only commands, Python analysis and the test suite.
- Write only inside `postdoc-review/` at the workspace root.
- Edit nothing under `.codex-tmp/aes-leakage-worktree/`: `preserve.py` hashes every file in the experiment directory, and five tests check the brief itself. Also leave `results/`, the paper files and the gem5 trees unchanged.
- Ask me before you run gem5 at all. The preregistration requires the decisions on questions 1 and 2 to be logged before defended-arm data exist, and a run of any partitioned, defended or overlap configuration would create that data. If a short run on an unprotected configuration would settle something, describe it (command, N, expected result, minutes) and ask.
- Also ask before installing packages, making any git write (commit, branch, push), or sending anything to the group or the instructor.

## Environment notes
- Run Linux tools through WSL: `wsl.exe -d Ubuntu-26.04 -e bash -lc '...'`. From Git Bash, prefix the command with `MSYS_NO_PATHCONV=1`.
- The workspace root in WSL is `/mnt/c/Users/shahr/OneDrive/Documents/Fall 26/Computer Architecture`. Quote it, because it contains spaces.
- Run the tests in WSL from the experiment directory with `python3 -B -m unittest discover -s tests -t .` (139 tests). Use WSL `python3`, because the Windows `python` launcher is unreliable.
- WSL git cannot open this worktree, so use Windows git for git commands there.

## Deliverables
**1. `postdoc-review/POSTDOC_REVIEW.md`**, about 4,000 to 6,000 words, in this order:
1. Verdict (150 words or fewer): is the plan sound, and which three changes should be made before Phase E?
2. Decision table: one row per question 1 to 9, with columns for the recommendation (one line), verification tag, proposal impact (none, additive, or changes something) and added simulation hours.
3. One section per question, each covering:
   - the recommendation
   - why, with citations
   - how it was verified
   - what would prove it wrong
   - the preregistration action: exact deviation text ready to log, dated as a draft and stating that it must be logged before the affected arms run
   - a one-line proposal-compatibility verdict
4. Brief section 10, items 1 to 9: keep, mitigate or accept, one or two lines each.
5. Problems the brief missed: at most 5, ranked by how much they threaten the conclusions.
6. Revised run plan to Dec 1. This is a summary; the details belong in the execution plan.
   - the runs in order, with N, parallelism and simulation hours, based on measured times (P1 took 10 min 59 s for 2,000 windows)
   - which runs need new code
   - the order in which to cut work if time runs short
7. Draft paper text (200 words or fewer) for the "beyond the proposal" paragraph. Word it so that no reader takes it for a key-recovery study, and add a one-line fallback for the case where the instructor declines beyond-proposal work.
8. Sources: every source you opened and what it supports.
9. Review log: findings from the two reviews described under Done means (the memo review and the Sonnet dry read of the plan), and how you resolved each one.

**2. `postdoc-review/EXECUTION_PLAN.md`**: the plan that Sonnet 5.5 will execute. Sonnet follows instructions literally and will not see this prompt or the memo unless the plan points it there, so write the plan to these requirements:
- **Kickoff block.** Open with three sentences on the plan's purpose, the files to read first, the guardrails and action boundaries restated in full, and when to stop.
- **Phases and checkpoints.** Split the work into phases, each ending in a checkpoint. At a checkpoint, Sonnet stops, reports its evidence and waits for my "go". Place a checkpoint before any gem5 run, before each block of Phase E runs and after any change to the analysis code.
- **What each step contains:**
  - its goal
  - the exact files
  - the exact commands, including the WSL wrapper
  - the expected output
  - an acceptance check that exercises the result (tests, an analysis run or a hash), not just a re-read of the file
  - what to do on failure: how many diagnostic attempts to make, then stop and report
  - a time estimate
- **No open choices.** Where judgement is needed, give the decision rule. A step that depends on a decision only I can make (such as the instructor's answer) is marked blocked, with what unblocks it.
- **Exact sequences for fragile operations:**
  - each deviation is written, dated and committed before the runs it governs
  - a new run directory never reuses an existing name
  - `preserve.py capture` follows every edit under the experiment directory
  - the tests pass before every commit
  - commits stay local on `experiment/aes-leakage` and are never pushed
- **Code changes** (for example a new statistic, effect-size reporting, the overlap variant or the P4 adapter change, whichever you recommend): name the file and function, the tests to write first and the command that proves the change works.
- **Runs:** for each run give the exact command, the run directory name and N. Also give which runs may go in parallel (checked against the host's cores and memory), the expected wall time, and the analysis command and gate that decide pass or fail.
- **Final-report template** at the end, for Sonnet to fill in: evidence for each step, deviations logged, items skipped and decisions still open.

**3. `postdoc-review/verify/`**: every script and output behind a [run-verified] tag, plus a `README.md` that lists one command per check.

**4. A closing chat message** of 250 words or fewer: the verdict, the three changes, what remains unverified, the decisions only I can make, and the one-line message I should paste to start the Sonnet session.

## Done means
- [ ] Each of questions 1 to 9 has exactly one recommendation and a verification tag. Proof: the decision table.
- [ ] Each [run-verified] item re-runs from `verify/README.md` and reproduces its saved output.
- [ ] At least 8 primary sources were opened, and each is cited with a DOI or URL. No citation refers to a source you did not open.
- [ ] Every recommendation has a proposal-compatibility line, and none crosses a guardrail.
- [ ] The worktree is unchanged. Proof: run `git status --porcelain` in the worktree at the start and at the end of the session, and confirm the outputs match. The test suite still passes in WSL.
- [ ] Every plan step has its commands, expected output, acceptance check, failure rule and time estimate. Every gem5 run sits behind a checkpoint, and the plan leaves no choice unresolved.
- [ ] One fresh-context subagent has reviewed the memo against these criteria and the guardrails, and its findings and your fixes are in the review log.
- [ ] A Sonnet subagent (model `sonnet`), given only `EXECUTION_PLAN.md` and the files the plan names, has listed every point where it would have to guess or could not run a command. You fixed each one, and the list is in the review log.

Beyond those two reviews, use a subagent for the literature sweep only if it grows past about 8 sources; otherwise work directly.

Post a one-line plan before you start, and a one-line update after each stage: reading, literature, verification, writing and review. Every claim that a check passed must cite the tool output behind it.
