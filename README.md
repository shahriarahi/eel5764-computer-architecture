# LLC Way Partitioning and AES Activity Detection in gem5

EEL5764 Computer Architecture — Group 18, Fall 2026.

This project investigates whether last-level cache (LLC) way partitioning prevents a monitoring process from detecting AES activity on another simulated core. It separates cache-capacity isolation from contention in shared timing resources, using matched controls, a corrected probe monitor, and a follow-up crossbar study.

**Final finding:** AES activity remains distinguishable at every tested allocation, from 1/15 through 8/8 monitor/AES ways. In this simulated configuration, disjoint LLC ways do not eliminate the shared hit-latency channel.

The experiment detects activity using public keys and inputs. It does not attempt key recovery. All quantitative results below are simulation results, not physical hardware measurements.

## Experimental setup

| Component | Configuration |
|---|---|
| Simulator | gem5 v25.1.0.1, RISC-V build |
| CPU model | Two `TimingSimpleCPU` cores, 2 GHz |
| Private L1D | 4 KiB in the final experiment |
| Shared LLC | 256 KiB, 16 ways |
| Allocations | 1/15, 2/14, 3/13, 4/12, 5/11, 6/10, 7/9, 8/8 monitor/AES ways |
| Final sweep | Three public plaintext seeds; 48 matched control/treatment processes and two diagnostic processes |
| Monitor | v3: file-backed probe output, with hot state held in registers |

The monitor compares probe timing during labelled AES-active and idle intervals. The analysis evaluates max-set and hit-only statistics, combines seed-level tests with Fisher's method, and applies Holm correction. Partition occupancy checks and a miss-based gate check isolation and monitor self-eviction. Decision rules and subsequent deviations are recorded in the [preregistration](PREREGISTRATION_V2_20261011.md).

## Final results

The authoritative sweep is [`results/updated run/sweep-v3/`](results/updated%20run/sweep-v3/), discussed in Section 12 of the [technical report](REPORT_UPDATED_RUN_20261011.md).

- All eight allocations remain distinguishable under both statistics.
- All 24 matched pairs pass the final self-eviction gate.
- The partitioned monitor retains approximately 100% of its matched control's hit-timing effect at 1/15, and 70–85% at the other allocations.
- No stable collapse point or equivalence point is found.
- Reported performance cost is at most 0.03% in this workload and simulated configuration.

See the [summary CSV](results/updated%20run/sweep-v3/summary_v3.csv) for per-allocation effects, confidence intervals, decisions, and performance metrics.

### Mechanism study

A [preregistered follow-up](PREREGISTRATION_MECHANISM_20261014.md) varies the shared L1-to-LLC crossbar across four settings at 1/15 and 8/8. Request-layer utilization and the timing effect decrease together.

A near-ideal crossbar removes approximately 100% of the effect at 1/15 and 88% at 8/8. At 8/8, a residual of approximately **+0.033 CPU cycles per probed line** remains in both control and treatment. The study's preregistered outcome is **partial**: the crossbar explains most of the signal, while attribution of the residual to the LLC request path is by elimination and was not separately tested.

Read Section 13 of the [technical report](REPORT_UPDATED_RUN_20261011.md) and the [mechanism summary](results/updated%20run/mech-summary/summary_mechanism.csv).

## Correction history and limitations

**The October 1 conclusion that 1/15 hid AES activity is withdrawn.** The original monitor's recording array evicted its own probe lines. The v2 monitor removed that array; further investigation identified hot-state conflicts and a timing-based gate that confused AES-driven delays with misses. The v3 monitor and corrected gate were fixed before the final sweep. Earlier results remain preserved as the investigation record.

The [independent validation record](VALIDATION_20261014.md) documents reproduced analyses, an independent reimplementation, and a bit-identical re-simulation of one 8/8 control/treatment pair.

These conclusions apply to a deterministic simulator, a small-L1D stress configuration, and this monitor build. The three seeds share one activity schedule and permutation sequence, so they are not independent replicates; the report also provides individual-run significance checks. Partition isolation is checked at statistics snapshots. The near-ideal crossbar is a diagnostic configuration, and bandwidth partitioning was not tested as a defense.

## Project files

| Path | Purpose |
|---|---|
| [Final paper](Group18_EEL5764_Final_Paper.docx) | Project paper, including the mechanism study |
| [Technical report](REPORT_UPDATED_RUN_20261011.md) | Final sweep in Section 12; mechanism study in Section 13 |
| [Project explanation](project%20explanation.md) | Introductory explanation of the method and findings |
| [RUNBOOK.md](RUNBOOK.md) | Environment setup and reproduction; Step 10C covers v2/v3 |
| [HANDOFF.md](HANDOFF.md) | Recorded project status and artifact inventory |
| [`configs/`](configs/) | gem5 simulation configurations |
| [`gem5_ext/`](gem5_ext/) | Partition-manager extension sources |
| [`workloads/`](workloads/) | Monitor, AES workload, build script, and workload binaries |
| [`scripts/`](scripts/) | Experiment runners and report builders |
| [`analysis/`](analysis/) | Statistical analysis and figure generation |
| [`tests/`](tests/) | Automated project tests |
| [`results/`](results/) | Preserved simulation outputs, summaries, and figures |
| [`archive/`](archive/) | Earlier source/document snapshots and checksum manifests |

## Reproduction

The documented reference environment is Windows 11 with WSL2 `Ubuntu-26.04`. Simulation and analysis run inside WSL using Python 3, NumPy, Matplotlib, a RISC-V cross-compiler, and an external gem5 source/build tree. The recorded reference Python version is 3.14.4. The gem5 checkout and build are not included in this repository.

Follow the [runbook](RUNBOOK.md) for dependencies, extension integration, workload compilation, and machine-specific paths. In the reference environment, gem5 lives at `~/eel5764/gem5`, with executable `build/RISCV/gem5.opt`. Adapt the documented paths for a new checkout before running experiments.

From PowerShell, enter the reference WSL distribution:

```powershell
wsl.exe -d Ubuntu-26.04
```

Then change to the project checkout **inside WSL**. The following commands use that Linux shell:

```bash
python3 --version
python3 -B -m unittest discover -s tests -t .
```

To rerun the final sweep after completing setup, select a new results directory:

```bash
python3 scripts/run_repeated_contention_sweep_v3.py --results-root "results/updated run/sweep-v3-repro"
```

The recorded sweep runtime is approximately 45 minutes on the reference machine; runtime elsewhere will vary. The runner refuses to reuse an existing results root unless explicitly resumed.

Preserve existing experiment outputs. Analysis and summarization scripts write into their input directories, so use copies when rechecking archived results. Exact byte reproduction also depends on output-path length because the probe-file argument affects the monitor's stack layout; see the validation record for details.
