# Prompt for Claude Code (Opus 5.5) or Codex: AES leakage-attribution study

*EEL 5764 Computer Architecture (Fall 2026, Dr. Sandip Ray), Group 18. This is a follow-up to our semester project "Evaluating LLC Way Partitioning as a Defense Against Simulated Cross-Core AES Cache Contention". Our final report is due Dec 1, 2026.*

## How to use

1. Unzip the bundle into the repo root, so that `experiments/aes-leakage/` contains `analysis/aes_leak_analysis.py` and `victim_table_trace.patch`.
2. Open Claude Code in the repo. Optionally start in plan mode (Shift+Tab) so it proposes a plan before editing.
3. Paste the prompt below as your first message.
4. Work phase by phase. The prompt tells the agent to stop at each boundary.

**If a request still gets flagged:**

- Paste the "Context" section on its own first and let the model confirm it understands the project.
- Then send Phase A only. Phase A is plain C, Python, and tests, with nothing gem5-specific running.
- Keep your own wording in the same register as the paper: "defense evaluation", "leakage measurement", "simulated", "public key".

No wording can guarantee a request won't be flagged. What helps most is stating accurately what the work is. That's what the context block does, and it's all true for this project.

---

## The prompt (copy everything in the block)

````text
CONTEXT — please read first
This is a graduate course project for EEL 5764 Computer Architecture
(University of Florida, Fall 2026, instructor Dr. Sandip Ray). The course
guidelines list "Hardware Security & Side-Channels ... way-partitioned secure
caches" as a suggested research track, and gem5 as the preferred platform.
Our group (Group 18) already completed and submitted a study in this repo:
"Evaluating LLC Way Partitioning as a Defense Against Simulated Cross-Core
AES Cache Contention". It found that way partitioning removes eviction-based
contention but leaves a crossbar timing channel. It also showed that two
added mechanisms (fixed request time slots and per-domain LLC response
queues) close that channel. The paper is in the repo root
(Group18_EEL5764_Final_Paper*.docx, REPORT_UPDATED_RUN_20261011.md).

This follow-up is a DEFENSE-EVALUATION study. The paper measured only WHETHER
AES activity is visible. We now want to measure WHAT the residual signal
encodes: nothing data-dependent, plaintext only, or plaintext combined with
the key. We also want to check whether each defense (way partitioning, time
slots, response queues) removes data-dependent leakage, not just the
activity signal. This is the standard known-key leakage assessment used in
side-channel evaluation, comparable to TVLA and known-key correlation tests.

Scope and safety properties (keep all of these):
- Everything runs inside the gem5 simulator (v25.1.0.1, RISC-V
  syscall-emulation mode). There is no real hardware, no real service, no
  network, and no third-party software or crypto library.
- The AES is the repo's own educational T-table implementation. The key is
  a fixed PUBLIC test constant compiled into the workload and printed in its
  output, and the plaintexts are public and deterministic. The analysis is
  handed the key; it never needs to find an unknown key.
- Outputs are evaluation metrics for a course report: per-hypothesis
  significance, SNR, and where the true public key ranks among alternatives
  (a guessing-entropy-style leakage metric). These quantify how much data
  each defense configuration leaks.
- The "monitor" process only times accesses to its OWN memory, exactly as in
  the submitted paper.

TASK
You are working in the git repo `eel5764-computer-architecture`. Start from
branch `experiment/tdma-prototype` and create branch
`experiment/aes-leakage`. Before writing code, read README.md, HANDOFF.md,
experiments/tdma/README.md, workloads/{victim.c,monitor.c,aes_ttable.c,
common.h,contention_common.h,build.sh}, configs/run_contention.py and
gem5_ext/*. Then propose a short plan and wait for my approval.

Build a self-contained experiment in `experiments/aes-leakage/`. The unit of
observation changes from a 2M-cycle labelled interval to one WINDOW: the
monitor fills its own lines, the AES workload performs exactly one
encryption, and the monitor re-times its lines. Each window is labelled with
that window's public plaintext.

HARD CONSTRAINTS
1. Do NOT modify anything outside experiments/aes-leakage/ (workloads/,
   configs/, gem5_ext/, analysis/, scripts/, results/ are frozen and
   checksummed). Reuse them only by #include, import or reading.
2. Do NOT build or run gem5 unless I explicitly say so. Write the code, the
   build instructions and the run commands, and stop at the phase
   boundaries below. You may run the host compiler, riscv64-linux-gnu-gcc,
   qemu-riscv64 and Python tests.
3. Freestanding RISC-V workloads only: same flags as workloads/build.sh
   (-nostdlib -ffreestanding -march=rv64gc -Wl,--no-relax), using
   workloads/common.h for syscalls.
4. Keep the corrected monitor's measurement safeguards: probe chains walked
   from registers, results stored in spare bytes of the just-walked probe
   line, one writev per window, no new LLC lines allocated by the monitor
   during measurement, deadline misses exit(2) with an error line.
5. Every claim in docs must trace to a file or test output. Make no claims
   about results that have not been run.

VERIFIED FACTS TO DESIGN AROUND
- The current public key 000102..0f has every upper nibble 0, so
  (p^k)>>4 == p>>4 and the experiment could not tell plaintext-only from
  plaintext-with-key effects. Use the public test key
  f1e2d3c4b5a69788796a5b4c3d2e1f10, printed by the workload at start.
- The current workload's 64-bit LCG puts its low 8 bits in plaintext bytes
  0 and 8, which repeat every 256 encryptions (a confound with window
  index). Use splitmix64 instead:
  x += 0x9E3779B97F4A7C15; z = x; z = (z^(z>>30))*0xBF58476D1CE4E5B9;
  z = (z^(z>>27))*0x94D049BB133111EB; return z^(z>>31).
  Window j's plaintext = two draws (lo, hi), little-endian bytes lo then hi.
  Seed 0 must give e220a8397b1dcdaf, 6e789e6aa1b965f4. Seed 0x5764A5E5 must
  give plaintexts f6ed4a34b9791097c4913c9a13836d05,
  c0bf76b584bd288872038fba14d23fa0, c798222a46fd16059a4932beb89488b5.
- aes_ttable.c: te0..te3 (1 KiB, 16 lines each). Rounds 1..9: byte i
  (row i%4) indexes Te_(i%4). The last round uses the 256 B sbox (4 lines,
  64 entries/line), so its line = InvSbox[c_i ^ k10_i] >> 6.
  The tables are static. In the current build they are 68 contiguous 64 B
  lines (sbox, te0, te1, te2, te3) across two 4 KiB pages, so each line's
  physical LLC set must be measured, not assumed.
- Monitor output format probe_bin_v2: 16-byte little-endian records
  {u64 timestamp, u32 latency, u16 interval, u16 cache_set}, 256 per
  interval; cache_set is LOGICAL. Physical = (logical + rotation) % 256,
  with rotation in stats key
  system.llc.partitioning_manager.probeSetRotation.
- gem5 calls PartitionManager::readPacketPartitionID only when the LLC
  ALLOCATES a block, 3 times per fill (src/mem/cache/base.cc ~1695,
  tags/base.cc ~115, tags/base_set_assoc.hh ~208). This is the right hook
  for simulator-side ground truth of which AES table lines reach the LLC.
- config: warm-up 1e9 ticks = 2,000,000 CPU cycles (2 GHz, 500 ticks/cycle).
  LLC 256 KiB 16-way mostly_incl LRU; L1D 4 KiB 4-way (profile "4KiB").
- Measured in existing results: an A=16 timing pass over 256 sets is ~280k
  cycles, A=8 ~70k; gem5 host speed ~3M simulated cycles/s.

DELIVERABLES (all under experiments/aes-leakage/)
1. leak_schedule.h
   T0=2000000, W=1048576, OFF_PRIME=65536, OFF_ENC=524288,
   OFF_ENC_END=OFF_ENC+65536, OFF_PROBE=OFF_ENC_END+4096, N_WIN (-D,
   default 2000, max 65535), splitmix64, next_plaintext(state, j, tvla,
   fixed, pt). TVLA mode: even windows use the fixed plaintext but still
   draw two words. Optional -DLEAK_FAKE_CLOCK makes rdcycle a monotonically
   increasing counter so qemu-user tests can run.
2. aes_leak_ext.c
   `#include "../../workloads/aes_ttable.c"` (so encryption is byte-identical
   to the paper's), then add only aes128_first_round_lookups(input, rk),
   which performs exactly round 1's 16 table loads into a volatile sink.
   This is a positive-control mode.
3. victim_leak.c (the AES workload; the name matches the repo's victim.c)
   argv: <plaintext seed>. Run the FIPS-197 self-test as in victim.c. Print
   `victim leak_format=v1 key=<hex> seed=<n> windows=<N> rounds1=<0|1>
   scrub=<0|1> tvla=<0|1>`. Per window: compute the plaintext before the
   window; wait_until(w0); if SCRUB, walk a private 8 KiB buffer (64 B
   stride) so the next lookups reach the LLC; deadline
   rdcycle <= w0+OFF_PRIME; wait_until(w0+OFF_ENC); encrypt (or round-1
   lookups only if ROUNDS1); deadline rdcycle <= w0+OFF_ENC_END; XOR-fold
   the ciphertext into a 16-byte checksum. At the end print
   `ct_checksum=<hex>`, then wait two windows and exit 0.
4. monitor_leak.c
   Derived from monitor.c's MONITOR_PROBE_SINK_FILE +
   MONITOR_HOT_STATE_IN_REGISTERS path, keeping the symbol name
   `probe_lines` (the config finds it with nm). Per window: walk own lines
   at w0+OFF_PRIME, deadline before w0+OFF_ENC; time them at w0+OFF_PROBE,
   record {timestamp, latency, interval=j, set}; deadline before w0+W; one
   writev. Header line
   `monitor format=probe_bin_v2 windows=<N> sets=256 ways=<A>`.
   Exit after T0+(N+1)*W.
5. build.sh
   Builds victim_leak_{r1,full}_{scrub,noscrub}, victim_leak_tvla and
   monitor_leak with N_WIN as a parameter; writes build_manifest.json with
   sha256 of every binary and nm addresses of te0..te3, sbox and
   probe_lines.
6. gem5_ext/ (copy of ../../gem5_ext plus simulator-side table tracing)
   New params: victim_requestor_name (""), victim_vaddr_base (0),
   victim_vaddr_size (0), victim_set_count (256). Defaults must leave
   behaviour identical. In readPacketPartitionID, for the AES workload's
   requestor with a vaddr inside the table range, dedupe per
   (curTick, block), then record each line's physical set (store set+1 in a
   member vector so a stats reset cannot erase it; count mismatches if a
   line's set changes), increment stat Vector victimTableFills[line], and
   DPRINTF(VictimTable, "victim_fill line=%u set=%u vaddr=%#x paddr=%#x\n").
   Expose in preDumpStats: victimTableLineSetPlusOne (Vector),
   victimTableSetMismatches, victimTableMissingVaddr. Add
   DebugFlag("VictimTable") to SConscript. The directory must be named
   gem5_ext because the sources include "gem5_ext/...".
   A reference diff, victim_table_trace.patch, is provided: review it and
   use or improve it. It has NOT been compiled.
7. gem5_build.md
   Exact commands for a separate tree, without running them:
   `git -C ~/eel5764/gem5 worktree add ~/eel5764/gem5-leak c8222cc67a399bfc01e8658dd14b30d5bfd634f9`,
   then `scons build/RISCV/gem5.opt -j$(nproc) EXTRAS=<abs path>/experiments/aes-leakage/gem5_ext`.
   Also a guard procedure: with tracing disabled, rerun sweep-v3
   seed-5764a5e5 UNPARTITIONED-A8 and require byte-identical probes.bin.
8. run_leakage.py (gem5 config adapter; follow experiments/tdma's pattern)
   importlib-load configs/run_contention.py WITHOUT running its main, then
   override: EXPERIMENT_PROFILES["4KiB"] workloads -> absolute paths of
   monitor_leak and the chosen AES build, epoch_cycles=W;
   CONFIG["contention"]["interval_count"]=N_WIN;
   MONITOR_VARIANT_BINARIES["v3"] -> monitor_leak. Wrap m5.instantiate to
   set the tracing params on system.llc.partitioning_manager from nm of the
   AES binary (range = min..max of sbox/te0..te3), and write
   leak_config.json (key, seed, W, T0, offsets, N_WIN, variant flags, table
   vaddrs, line offset of each table, binary hashes). Accept
   --victim-variant {r1-scrub, full-scrub, full-noscrub, tvla} plus the
   original flags (--split, --monitor-ways, --l1d-size 4KiB,
   --monitor-sink file, --monitor-variant v3, --workload-seed). Refuse to
   run on a gem5 binary that lacks the victim_* params. Recommended
   invocation:
   gem5.opt --debug-flags=VictimTable --debug-file=victim_table.trace -d <out>
   run_leakage.py ...
9. analysis/aes_leak_analysis.py
   Start from the provided prototype (numpy+scipy; its selftest passes) and
   adapt it:
   a) `analyze --run-dir DIR` reads probes.bin (probe_bin_v2; verify
      interval and set fields), the first stats block of stats.txt
      (rotation, victimTableLineSetPlusOne, mismatches), simout.txt (key,
      seed, rounds1, ct_checksum, PASS lines), leak_config.json and the
      optional victim_table.trace.
   b) Build the table->logical-set map per line from stats: logical =
      (phys - rotation) % 256. Fail if any of the 68 lines is unmapped or
      mismatches > 0.
   c) Leakage models: round 1 uses 16 lines per Te table; the last round
      uses the sbox with 4 lines (x >> 6). Generalise location_scores and
      the detection partitions to n_lines.
   d) Ground truth: parse victim_table.trace (regex on "victim_fill
      line=(\d+) set=(\d+)", tick = leading integer, cycle = tick/500,
      window = (cycle - T0)//W). Compare per-window filled lines with the
      algorithmically touched lines. Report recall and precision, fills
      outside the AES phase, and mean fills per window.
   e) Keep the selftest. Extend synthetic data to the sbox last round and
      to an arbitrary per-line set map, and add `synth --run-dir` that
      writes a complete fake run directory (probes.bin in v2 format, a
      minimal stats.txt, simout.txt, leak_config.json, trace) so the
      run-dir path is tested end to end.
   f) Output JSON plus a short Markdown summary table suitable for the
      course report.
10. tests/ (python -m unittest discover)
    - splitmix and plaintext vectors (Python vs a host-compiled C check of
      leak_schedule.h)
    - aes_leak_ext.c compiled for the host with a stub harness: FIPS-197
      C.1 KAT; ciphertext checksum over N windows equals Python's
    - qemu-riscv64 functional run of victim_leak (LEAK_FAKE_CLOCK, N=8):
      prints the self-test PASS, the key, and a checksum matching Python
    - qemu-riscv64 run of monitor_leak alone (fake clock, N=4, A=2): writes
      a valid probe_bin_v2 file of N*256 records
    - analysis selftest and synth --run-dir round trip
    - gem5_ext copy differs from ../../gem5_ext only by the tracing additions
    Skip qemu tests with a clear message if qemu-riscv64 or
    riscv64-linux-gnu-gcc are missing.
11. Docs: README.md (overview and commands), PREREGISTRATION_DRAFT.md
    (hypotheses, N, seeds, key, alpha 0.05 with Holm, decision rule: a data
    hypothesis is supported if significant on >= 1 byte AND the true public
    key ranks first on those bytes; matched control/treatment pairs as in
    the paper), progress.md (ledger), and preserve.py (sha256 of every new
    file plus a check that the frozen trees are unchanged against git HEAD).

PHASES (stop and report at each boundary; do not continue without approval)
Phase A: items 1-6 and 8-11, plus tests. Report the test output, the binary
         hashes, and the nm table layout of the new AES build.
Phase B: gem5_build.md commands for me to run. Wait until I report a
         successful build and the guard result.
Phase C: give the exact commands for P0 (20 windows, --split off,
         --monitor-ways 16, r1-scrub) and how to check them with
         `analyze --run-dir`.
Phase D/E: P1 positive control (2,000 windows). Then P2-P4 per the
         preregistration: full AES, no scrub, A=8 matched control,
         way-partitioned 8/8 and 1/15, and the full defense (time slots +
         per-domain response queues). I run gem5; you analyse the results
         I provide.

QUALITY BAR
- The paper's numbers must stay reproducible: no frozen file changes, and
  the guard run is byte-identical.
- Mark every assumption. Small, reviewable commits with clear messages.
````
