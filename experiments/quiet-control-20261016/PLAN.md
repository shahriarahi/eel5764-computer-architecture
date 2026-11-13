# Quiet-victim diagnostic, 2026-10-16

Authorized: two positive replay cases followed, only on success, by two quiet
cases, A=1 and A=8, public seed 0x5764A5E5, 240 seconds per simulation.
This is a separate diagnostic, not a replacement for the frozen study.

Replay uses the exact stored command with only a same-length output path change.
Require identical probes and simulated statistics (existing TDMA comparison
excludes host and scheduler counters; scheduler validity is checked separately).
New roots are tdma-np0 and tdma-nc0; refuse preexisting roots/cases. Preserve failed
runs. No old input, binary, configuration, result, or log is overwritten.

Quiet cases retain monitor, labels, seed, way masks, clocks, and 4-cycle slots.
The new victim retains startup AES self-test but executes a warmed rdcycle loop
through measurement. The new adapter substitutes executable before instantiate,
keeping original argv[0] to preserve its stack-layout contribution; actual binary
and hash are recorded separately. Startup/code layout still differs.

Validity: 16,384 probes, 65 stats blocks, valid labels/mapping, disjoint ways,
both domains mapped, positive monitor grants and zero victim grants in EACH of
64 measured intervals, zero scheduler violations, explicit zero encryptions.
No existing per-domain counter proves startup transactions drained: report this
limitation even if every grant gate passes. Do not infer response-path causality.

Analysis fixed before new cases: report unchanged 10,000-permutation max-set and
hit-only diagnostics, all-walk signed active-minus-idle cycles/line, and the
existing 2,000-bootstrap 90% mean-effect interval with seed 5764, A=1 then A=8.
Holm-correct separately across the two endpoints for each statistic. Original
labels are nominal labels in quiet cases. Undefined statistics remain undefined.
The +/-0.02 cycles/line mean margin is descriptive evidence, not distributional
indistinguishability. One activity schedule and one seed; no Fisher aggregation.
If validity fails, preserve outputs and report invalid; do not analyze as a
security result or silently rerun. Do not expand to other seeds or allocations.

Run preservation check after execution against preservation-before.json,
covering 6,694 preexisting workspace files. project explanation.md already
differs from the older frozen manifest; preserve its current contents too.
External original gem5 tree is outside this authorization. Isolated gem5 may be
read and executed; no gem5 source modification or rebuild is planned.
