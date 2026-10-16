# Investigation: residual "self-eviction" at 7/9 and 8/8 (October 11, 2026)

In the updated run, the 7/9 and 8/8 allocations failed the self-eviction
gate. Their treatment all-hit fraction was 97.2–97.7%, against about 99.5% in
the control, and the tolerance is 1 percentage point. This folder explains
why. It is analysis only: no result in `../sweep/` was changed.

## Finding 1: most of the gap is AES-driven delay, not self-eviction

The gate counts a probe walk as "slow" when it is more than 20 cycles above
the run's 1st-percentile walk time. In the treatments, the slow walks that
grow with `A` occur **only in AES-active intervals**. They are 20–100 cycle
delays, not full LLC misses (a miss adds about 120 cycles or more).

Rate of 20–100-cycle slow walks, per 1,000 walks, excluding always-slow
sets, all three seeds:

| A | Control, active / idle | Treatment, active / idle |
|---|---|---|
| 4 | 0.12 / 0 | 1.39 / 0 |
| 6 | 0.69 / 0 | 5.86 / 0 |
| 7 | 1.18 / 0 | 29.49 / 0 |
| 8 | 2.33 / 0 | 41.26 / 0 |

These events are part of the leak itself: large contention delays that the
gate's proxy mistakes for misses. They account for about 1.5–2.0 of the
1.8–2.3 point gate gap at 7/9 and 8/8. The analysis script is
`slow_split.py`.

## Finding 2: the genuine self-eviction is one line holding `probe_way_count`

From A=4 upward, logical set **191** is slow in every interval, in
treatments only. That is 1 of 256 sets, or 0.39 points, the same at 4/12
through 8/8.

An LLC trace of one 8/8 run (seed `0x5764A5E5`, ticks 11e9–13e9, `Cache`
debug flag) shows that **exactly one** non-probe line ever occupies the
monitor's ways:

| | |
|---|---|
| Physical line | `0x1040` (virtual `0x11040`) |
| Physical set | 65 (= logical 191, given the measured rotation of 130) |
| Way | 1 |
| Activity | 64 `ReadSharedReq` hits and 64 `WritebackDirty` in two intervals |

Contents (`nm`): `probe_way_count` (`0x11040`), `sink_fd` (`0x11048`), and
the start of `sink_iov` (`0x11050`).

The mechanism:

1. The monitor reads the global `probe_way_count` for every set it walks:
   in `walk_set`'s loop bound and in `slot_for_set`.
2. That line sits in L1D set 1, the same L1D set as the probe lines of every
   logical set with `s ≡ 15 (mod 16)`.
3. When `A ≥ 4`, those A probe lines plus the global line exceed the 4-way
   L1D. The global line is evicted, written back dirty, and fetched again
   from the LLC several times per interval.
4. Each refetch makes it most-recently-used in LLC physical set 65, so it
   permanently holds one of the monitor's `A` ways there. Logical set 191's
   `A` probe lines then fit in only `A − 1` ways, and one probe line is
   evicted every interval.
5. In the control there are 16 ways, so the extra line is harmless. At
   `A ≤ 3`, `A` probe lines plus the global line fit in the 4-way L1D, so
   the line is never refetched and ages out of the LLC.

Evidence files:

- `llc_trace_phys_0x1040.txt`: every LLC event for this line in the window
- `llc_trace_phys_set65_all.txt`: every LLC event in physical set 65
- `trace_owners.py`: the script that lists non-probe lines in monitor ways

## Finding 3: set 0, both arms, A ≥ 4

Logical set 0 is about 29 cycles slow in every interval in **both** arms.
That is one extra LLC hit, not a miss. It cancels in the gate and was not
investigated further.

## Side observation

A traced rerun with a different output path gave a `probes.bin` that differs
slightly from the sweep's. The monitor receives the probe-file path as an
argument, so its stack layout depends on the path length. The overall
pattern is unchanged: always-slow sets [0, 191], 2.85% vs 2.84% slow. Exact
byte-for-byte reproduction of a v2 run therefore needs the same output path
length.

## Suggested fix (not applied)

Copy `probe_way_count` into a local `const` before measurement starts, and
pass it to `walk_set`/`slot_for_set`, so the global's line is never touched
during probing. Then:

1. Check one 8/8 run: set 191 should no longer be always slow.
2. Rerun 7/9 and 8/8.

Separately, the gate proxy needs a decision. Counting 20–100-cycle delays as
self-eviction penalises the very signal being measured. Two alternatives: use
idle intervals only, or count only walks more than 100 cycles over the floor.
Changing the preregistered gate after seeing the data must be reported as a
deviation.
