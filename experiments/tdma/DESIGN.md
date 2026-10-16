# Time-slot follow-up: proposal compliance review

Date: 2026-10-15. Status: review complete; implementation and simulation not started.

## Evidence reviewed

- `Group18_EEL5764_Final_Project_Proposal_Aligned.docx`, especially the research question, bounded objective, independent variables, and success criterion.
- `HANDOFF.md`, course-deliverable status and proposed science extensions.
- `REPORT_UPDATED_RUN_20261011.md`, sections 12 and 13.
- `configs/run_contention.py`, `gem5_ext/SConscript`, and the mechanism runner.
- `RUNBOOK.md`, external gem5 build location and recorded build times.

The submitted proposal PDF is outside this workspace. Its contents were not
independently checked during this review. The aligned local proposal and the
handoff are the evidence available within the authorized directory.

## Compliance conclusion

The original experiment asks whether A/(16-A) way partitioning alone removes
AES-active/idle distinguishability. It specifies 48 inferential cases and two
diagnostics, fixed workload inputs, and max-set permutation inference with
Fisher combination and Holm correction. Its reported v3 outcome remains that
all eight allocations are distinguishable.

Time scheduling adds another independent variable and changes the defense.
It therefore does not belong in the original proposal's 50-case experiment.
It is compatible with preserving that proposal only as an explicitly separate,
exploratory follow-up: way partitioning PLUS time scheduling. Section 13.3
already identifies per-domain arbitration as a possible additional defense;
section 13.4 explicitly says that mitigation was not tested.

Do not revise the accepted proposal, relabel old results, replace the original
negative conclusion, or claim that way partitioning alone now succeeds.

## Candidate prototype for design review

Question: with the original way masks retained, does deterministic,
non-work-conserving service of the shared LLC request path attenuate the
remaining activity signal at A=1 and A=8?

Use alternating monitor/AES slots on a common simulated clock. Unused slots
stay idle. Domain identification must cover demand traffic and writebacks;
requests must not borrow the other domain's slot. Track request duration,
slot overruns, retry/backpressure, and per-domain waiting. Retrying traffic
must not acquire a shared queue or crossbar reservation across another
domain's slot. Check the actual gem5 port/retry implementation before choosing
the insertion point or slot length. A timer that merely delays each request
does not establish these properties.

This is a new scheduler subsystem, not an existing configuration switch.
Crossbar scheduling alone does not establish isolation of LLC internals,
MSHRs, memory-controller queues, or DRAM. A residual signal is a valid outcome.
No constant completion bound has yet been established.

## Proposed test gates

1. Scheduler-level checks: idle slots are not borrowed; no wrong-domain grant,
   packet loss, retry deadlock, or unaccounted slot overrun. Exercise demand
   reads and dirty writebacks, including downstream backpressure.
2. Disabled-mode regression: compare output and probe bytes with a matched
   existing v3 run, retaining its output-path length and workload hashes.
3. Pilot A=1 and A=8, first seed 0x5764A5E5: matched fresh unmodified control,
   way-only treatment, and way-plus-slot treatment. A pilot is not the final
   three-seed inference. Keep the original 64-interval schedule and binaries.
4. If structural gates pass, run all three predeclared seeds at both depths.
   Preserve mapping, occupancy, record-count, and AES self-test gates. Report
   the original max-set analysis and the existing hit-latency equivalence
   analysis separately. Failure to reject a difference is not equivalence.
5. Report per-core IPC, LLC misses, AES useful-work throughput, waiting and
   retry statistics. Record the shared schedule across seeds as a limitation.
   Only consider the full A=1..8 sweep after both endpoint assessments pass;
   preregister its inference family before running it.

All new outputs must use a new results directory. Log the additional defense,
slot parameters, hypotheses, and analysis before simulation. Do not edit raw
data, frozen workloads, original results, or the baseline gem5 executable.

## Authorization boundary

The gem5 checkout/build is at `~/eel5764/gem5` inside WSL, outside the launched
workspace. The runbook records a 2 min 19 s extension rebuild and roughly
40 minutes for the earlier mechanism experiment. These are historical timings,
not estimates measured for this prototype. Inspecting that checkout, making
an isolated build, and running potentially long simulations require explicit
authorization under the supplied directory and runtime rules.

The explicitly invoked Superpowers brainstorming workflow also requires design
review before implementing a new subsystem. This document is the compliance
review and candidate design, not evidence of a tested mitigation.
