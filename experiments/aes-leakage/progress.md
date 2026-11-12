# Progress ledger

Branch `experiment/aes-leakage`, started from `experiment/tdma-prototype` at
`45d21e2`. Simulator only. Every entry points to a file, a command or a test.
Nothing here is a leakage result: no gem5 run of this experiment's workloads has
been made. The only gem5 run so far is the Phase B guard, which re-ran the
paper's own configuration to check the new gem5 build.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| Phase A | code, builds, adapter, analysis, docs, tests (no gem5) | done 2026-11-12 |
| Phase B | build the tracing gem5, run the byte-identical guard | done 2026-11-12, at the group's explicit request; guard PASS, see "Phase B: results" |
| Phase C | P0: 20 windows, no partition, 16 monitor ways, round-1 lookups | commands in `README.md`; ready, not run |
| Phase D | P1: 2,000-window positive control | after C |
| Phase E | P2 to P4 per `PREREGISTRATION_DRAFT.md` | after D; P4 needs a defense-patched gem5 tree and an adapter change |

## Phase A: deliverables

| # | Deliverable | Evidence |
|---|---|---|
| 1 | `leak_schedule.h` | `tests/test_schedule.py`: constants, key, splitmix64 vectors and plaintext streams agree between the C header (host-compiled) and Python for four seeds, normal and TVLA |
| 2 | `aes_leak_ext.c` | `tests/test_aes_ext.py`: FIPS-197 C.1 through the paper's own encrypt code; round-1 mode loads exactly the 16 round-1 words; checksums equal the numpy reference |
| 3 | `victim_leak.c` | `tests/test_qemu_victim.py`: under `qemu-riscv64` with a fake clock (N = 8) it prints the self-test PASS, the key, the header, and plaintext and ciphertext checksums equal to Python, for all five variants |
| 4 | `monitor_leak.c` | `tests/test_qemu_monitor.py`: N = 4, A = 2 gives a valid `probe_bin_v2` file of N x 256 records with correct interval and set fields |
| 5 | `build.sh`, `build_manifest.json` | `tests/test_build.py`; same CFLAGS as `workloads/build.sh` (tested); two builds of the same N into different directories are byte-identical |
| 6 | `gem5_ext/` | `tests/test_gem5_ext_diff.py` (additions only, default off) and `gem5_syntax_check.sh` (type check against real gem5 headers) |
| 7 | `gem5_build.md` | `tests/test_docs.py` checks the quoted hash, flags and path length against the stored run |
| 8 | `run_leakage.py` | `tests/test_run_leakage.py`: loads the frozen config without running it, overrides, refuses bad builds and gem5 without the victim parameters; driven with a fake `m5` |
| 9 | `analysis/aes_leak_analysis.py` | `tests/test_analysis.py` (run-dir reader, line map, 4-line sbox model, ground truth, way isolation, `synth --run-dir` round trip) and `selftest` |
| 10 | `tests/` | `python3 -B -m unittest discover -s tests -t .` |
| 11 | docs, `preserve.py` | `README.md`, `PREREGISTRATION_DRAFT.md`, this file; `tests/test_preserve.py` |

Scope decision applied (2026-11-12): the analysis does not score key guesses, and
the work is labelled as going beyond the accepted proposal. See `README.md`.

## Phase A: facts established

* **AES code is the paper's.** `aes128_encrypt_block` (288 instructions),
  `aes128_expand_key` (85) and `aes_ttable_init` (171) in `victim_leak_full_scrub`
  are instruction for instruction identical to the paper's `workloads/victim_l1d4k`,
  differing only in 4, 2 and 18 pc-relative address operands (disassembly compared
  with `riscv64-linux-gnu-objdump`, addresses masked).
* **Table layout** (`riscv64-linux-gnu-nm -S`), `victim_leak_full_scrub` against
  the paper's `victim_l1d4k`: 68 contiguous 64-byte lines in both; line offsets 0
  (sbox), 4, 20, 36, 52 (te0..te3) in both; two 4 KiB pages in both. Base address
  `0x14080` against `0x11080` (the same in-page offset). `victim_leak_full_noscrub`
  starts at `0x12040`. `monitor_leak` has `probe_lines` at address 73856, size
  262144, the same as the paper's `monitor_v3_l1d4k`.
* **Tracing patch:** the reference patch applies cleanly to the frozen sources and
  the patched `requestor_partition_manager.cc` type-checks against the real
  gem5 v25.1.0.1 headers (`g++ -fsyntax-only`, two generated headers stood in
  for). A deliberately injected error is caught, and restoring the file restores
  the pass. This was not a gem5 build; the real build is in Phase B below.
* **Splitmix64 test vectors** in the task text were recomputed independently and
  are correct (seed 0, and the three plaintexts of seed 0x5764A5E5).
* **Synthetic false-positive rate** (`synthetic_power.md`, 400 null runs): decision
  rule 15 runs (3.75%), any hypothesis 21 runs (5.25%). Synthetic data only.

## Phase A: binary hashes (`build.sh`, riscv64-linux-gnu-gcc 15.2.0)

`build/n2000/` (N_WIN = 2000):

| Binary | sha256 |
|---|---|
| `victim_leak_r1_scrub` | `17d0c032de589992892124659c710cd53ea2e51e10a48c7204dbc32bad15223a` |
| `victim_leak_r1_noscrub` | `e3e9eb9a0245803df067c88c01a5447496d8aef04c749178da148aaa0fe82728` |
| `victim_leak_full_scrub` | `a2977953632fecaf8da5811fff775585644e979e03d6e6f3dbc2da6d0c1fd392` |
| `victim_leak_full_noscrub` | `d5fada0f9b37d97edcd9ed91043cbe2417af282c9c7d45da7e589507775bd25d` |
| `victim_leak_tvla` | `6d977ea000c8bf3dc67d3cc61836baeae40241bdc7a03b72b78f171e74f678bb` |
| `monitor_leak` | `6a6eaae9dc234abec81dd932cc56b06e90b9664aa39e15c9ddeb3162740ea12f` |

`build/n20/` (N_WIN = 20):

| Binary | sha256 |
|---|---|
| `victim_leak_r1_scrub` | `9077499630bcf5f87c23f0e40c23b83dde55c55636405bbc20f05b07e7cc561e` |
| `victim_leak_r1_noscrub` | `6dbcf8c7ad4a67582ef7c8dc0397a6395f875f3afaeb33d200a3d257379e344d` |
| `victim_leak_full_scrub` | `73fd2d808eb3021f43db5dc80f5a89b08741b8c7c0cd7328cd01ca59e3561d85` |
| `victim_leak_full_noscrub` | `f5653093e5a3d643cd864fc4fa52aaf737e5756e80625a8d63ca8cdb01da6ccb` |
| `victim_leak_tvla` | `7f79ac2661ff294dbaf288c64b4ffd17187e969f3a05a7dad5e092dfabf4af6f` |
| `monitor_leak` | `3ac5aad6ce8aa97ca574fd6829ca6700f17813e65f082e6fb8a125382cfdc7df` |

## Phase B: results (2026-11-12)

Run at the group's explicit request; the steps are those of `gem5_build.md`.

| Item | Result |
|---|---|
| Tree | `~/eel5764/gem5-leak`, detached at `c8222cc67a399bfc01e8658dd14b30d5bfd634f9`, clean |
| `EXTRAS` | `~/eel5764/leak-ext/gem5_ext`, a symlink to `experiments/aes-leakage/gem5_ext` |
| Build | `scons build/RISCV/gem5.opt -j14 EXTRAS=...`: exit 0, 12 min 38 s (11:37:43 to 11:50:21). `-j14` rather than `-j$(nproc)` = 20 to stay within this machine's 15 GB of RAM; the project's earlier rebuild notes also use `-j14`; `-j20` was not tried |
| Warnings | GCC 15.2.0 "not officially supported" (as in earlier builds); capstone header not found (not used) |
| Executable | `build/RISCV/gem5.opt`, 1,003,212,864 bytes, sha256 `71845ebf51381bce66fa5926f7ddfb324cab9cfc59128afbc985a7053d2f8c5a` |
| Tracing in the build | `debug/VictimTable.cc` and the patched `requestor_partition_manager.cc` were compiled; `gem5.opt --debug-help` lists `VictimTable: LLC fills of the traced victim table range` |
| Guard | `sweep-v3/seed-5764a5e5/UNPARTITIONED-A8` re-run with the original config from the original project root, output directory of 139 characters (probe path 150, as stored): **`cmp` reports `probes.bin` byte-identical**; both files are 262,144 bytes with sha256 `0ee71c2389afbabf2bb74393dd3b9c2a081c3c6f10ecbacb322a1c239a89848e`; the run took 47.6 s; the guest output matches the stored run (`encryptions=23903 sink=132`, `monitor status=PASS records=16384`) |
| Whole `stats.txt` | Compared with the stored run's, after dropping host-dependent lines: the only differences are `hostOpRate` (wall-clock speed) and the four new `victimTable*` statistics, all zero. Every simulated statistic is identical |

Guard output directory: `~/eel5764/guard-leak/` (a 139-character name made of `g`), outside the repository.

## Environment changes made for Phase A and B

With the group's approval, in WSL `Ubuntu-26.04`: `qemu-user` (provides
`qemu-riscv64`) and `python3-scipy` were installed with `apt-get`. A second git
worktree `.codex-tmp/aes-leakage-worktree` (gitignored directory) holds this
branch. For Phase B: a new gem5 worktree `~/eel5764/gem5-leak` (which adds
metadata under `~/eel5764/gem5/.git/worktrees/`), the symlink directory
`~/eel5764/leak-ext/`, the build log `~/eel5764/build_leak.log`, and the guard
output under `~/eel5764/guard-leak/`; none of the existing gem5 trees was
modified. Nothing outside this experiment directory was modified in the
repository; `preserve.py verify` checks that.

## Open items

* The tracing code is built and the default-off behaviour is verified, but its
  enabled behaviour (fills recorded, sets mapped) has not run yet: that is P0.
* P4 needs a gem5 tree with the time-slot and response-queue patches rebuilt with
  this `EXTRAS`, and `run_leakage.py` must pass the time-slot parameters through.
* The preregistration is a draft: N, seeds and gates await the group's edits and
  the freeze in section 10.
* Whether the final paper may include work beyond the accepted proposal has not
  been confirmed with the instructor.

## Deviations log

None.
