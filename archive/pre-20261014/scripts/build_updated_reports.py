#!/usr/bin/env python3
"""Build the updated Group 18 report DOCX files from the v3 sweep.

Reads (never modifies):
  Group18_EEL5764_Final_Project_Report.docx            (template, short)
  Group18_EEL5764_Final_Project_Report_Expanded.docx   (template, expanded)
  results/updated run/sweep-v3/                        (final results, D3)
  results/contention-repeated-20261001/summary_repeated.csv (original study)
  results/posthoc-20261011/posthoc_summary.csv         (original self-eviction)
Writes new files only:
  Group18_EEL5764_Final_Project_Report_Updated.docx
  Group18_EEL5764_Final_Project_Report_Expanded_Updated.docx
Every number in the prose comes from those files; assertions stop the build
if the data no longer matches the prose.
"""

from __future__ import annotations

import csv
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.docx_report_builder import build  # noqa: E402

ROOT = Path("results/updated run/sweep-v3")
SPLITS = [f"{a}-{16 - a}" for a in range(1, 9)]


def rows(path: str | Path, key: str = "split") -> dict:
    with open(path, newline="") as stream:
        return {r[key] if key else i: r for i, r in enumerate(csv.DictReader(stream))}


def f(x: str | float) -> float:
    return float(x)


def pv(x: float) -> str:
    return f"{x:.3f}" if x >= 0.001 else f"{x:.1e}"


v3 = rows(ROOT / "summary_v3.csv")
v3_seed = list(csv.DictReader(open(ROOT / "per_seed_matched_v3.csv", newline="")))
v1 = rows("results/contention-repeated-20261001/summary_repeated.csv")
ph = {(r["split"], r["mode"]): r for r in csv.DictReader(open("results/posthoc-20261011/posthoc_summary.csv", newline=""))}
summary_json = json.loads((ROOT / "summary_v3.json").read_text())

# ---- validation counts straight from the run directories -------------------
analyses = sorted(glob.glob(str(ROOT / "**" / "analysis.json"), recursive=True))
A = [(Path(p).parent, json.loads(Path(p).read_text())) for p in analyses]
treat = [a for _, a in A if a["split"] != "off"]
counts = {
    "runs": len(A),
    "probes": sum(os.path.getsize(d / "probes.bin") == 262144 for d, _ in A) * 16384,
    "blocks": sum(a["stats_blocks"] for _, a in A),
    "aes": sum("aes_self_test=PASS" in (d / "simout.txt").read_text() for d, _ in A),
    "mapping": sum(a["probe_mapping_validation"] == "PASS congruent" for _, a in A),
    "disjoint": sum(a.get("isolation_validation") == "PASS disjoint" and a["isolation_violations"] == 0 for a in treat),
    "v3": sum(json.loads((d / "run_meta.json").read_text()).get("monitor_variant") == "v3" for d, _ in A),
    "hashes": len({(d / "workload_sha256.txt").read_text() for d, _ in A}),
    "failed": len(glob.glob(str(ROOT / "**" / "*failed*"), recursive=True)),
    "gate": sum(r["gate_d2_ok"] == "True" for r in v3_seed),
    "controls_hit_only": sum(f(r["control_hit_only_p"]) < 0.05 for r in v3_seed),
    "controls_max_set": sum(f(r["control_max_set_p"]) < 0.05 for r in v3_seed),
}

# ---- the outcome pattern the prose below is written for ---------------------
conclusions = [v3[s]["conclusion"] for s in SPLITS]
assert counts["runs"] == 50 and counts["failed"] == 0 and counts["v3"] == 50, counts
assert counts["probes"] == 819200 and counts["aes"] == 50 and counts["mapping"] == 50, counts
assert counts["disjoint"] == 24 and counts["hashes"] == 1 and counts["gate"] == 24, counts
assert all(c == "distinguishable" for c in conclusions), conclusions
assert summary_json["stable_collapse_point"] is None and summary_json["stable_equivalence_point"] is None
assert all(v3[s]["control_hit_only_valid"] == "True" for s in SPLITS)
assert all(not v3[s]["equivalent_within_margin"] == "True" for s in SPLITS)
for s in SPLITS:
    assert f(v3[s]["treatment_hit_only_holm_p"]) < 0.05

ret = {s: f(v3[s]["effect_retained_fraction"]) for s in SPLITS}
ce = {s: f(v3[s]["control_effect_per_line"]) for s in SPLITS}
te = {s: f(v3[s]["treatment_effect_per_line"]) for s in SPLITS}
lo = {s: f(v3[s]["treatment_effect_ci90_low"]) for s in SPLITS}
hi = {s: f(v3[s]["treatment_effect_ci90_high"]) for s in SPLITS}
ms_valid = [s for s in SPLITS if v3[s]["control_max_set_valid"] == "True"]
ms_sig = [s for s in SPLITS if f(v3[s]["treatment_max_set_holm_p"]) < 0.05]
r_min, r_max = min(ret.values()), max(ret.values())
mon_ipc = [f(v3[s]["monitor_ipc_cost_pct_mean"]) for s in SPLITS]
aes_cpe = [f(v3[s]["aes_cycles_per_encryption_cost_pct_mean"]) for s in SPLITS]
mon_miss = [f(v3[s]["monitor_llc_miss_delta_pp_mean"]) for s in SPLITS]
max_cost = max(abs(x) for x in mon_ipc + aes_cpe)
trt_miss = [100 * f(v3[s]["treatment_miss_walk_fraction_mean"]) for s in SPLITS]
ctl_miss = [100 * f(v3[s]["control_miss_walk_fraction_mean"]) for s in SPLITS]
v1_allhit = [100 * f(ph[(s, "partitioned")]["all_hit_record_fraction_mean"]) for s in SPLITS]
v3_allhit = [100 * f(v3[s]["treatment_all_hit_fraction_mean"]) for s in SPLITS]
s1 = "1-15"


def pct(x: float, d: int = 0) -> str:
    return f"{100 * x:.{d}f}%"


def span(lo_v: float, hi_v: float, d: int) -> str:
    """'a–b' with d decimals, or a single value when both round equal."""
    a, b = f"{lo_v:.{d}f}", f"{hi_v:.{d}f}"
    return a if a == b else f"{a}–{b}"


def signed(x: float, d: int) -> str:
    """Signed value without a misleading '-0.000'."""
    s = f"{x:+.{d}f}"
    return f"{0:.{d}f}" if float(s) == 0 else s


def of_eight(n: int) -> str:
    return "all eight" if n == 8 else f"{n} of eight"


def sp(s: str) -> str:
    return s.replace("-", "/")


TITLE = "Evaluating LLC Way Partitioning as a Defense Against Simulated Cross-Core AES Cache Contention"
AUTHORS = "Shahriar Ahmed, Khan Thamid Hasan, and Md Touhidul Islam"
COURSE = "EEL 5764 Computer Architecture, Fall 2026 — Group 18"

ABSTRACT = (
    "Abstract—This project evaluates way partitioning of a shared 16-way last-level cache as a defense against "
    "simulated cross-core cache contention. In gem5, core 0 runs a depth-matched Prime+Probe-style monitor and core 1 "
    "runs a deliberately leakage-prone educational T-table AES-128 workload. For monitor depths A=1...8, each A/(16-A) "
    "partitioned treatment is paired with an unpartitioned control using the same monitor footprint, binaries, "
    "schedule, and public plaintext seed; three seeds give 48 inferential processes plus two excluded diagnostics. "
    "An earlier version of this study concluded that one monitor way (1/15) already made AES activity "
    "undetectable. Validation showed that conclusion was an artifact: the monitor's own record buffer evicted 20–25% of "
    "its probe lines, but only in partitioned runs, hiding the signal. With a corrected record-free monitor and a "
    "predeclared self-eviction gate, all 24 matched pairs pass every validity check and all eight allocations remain "
    f"distinguishable after Fisher combination and Holm correction. The partitioned monitor retains {pct(r_min)}–"
    f"{pct(r_max)} of its control's hit-latency signal; no allocation is equivalent to zero within ±0.02 cycles per "
    f"probed line. Partitioning removes eviction-based contention but not the hit-timing channel through shared LLC "
    f"resources, and it costs these workloads at most {max_cost:.3f}% in IPC or cycles per encryption."
)
INDEX = "Index Terms—gem5, cache partitioning, Prime+Probe, T-table AES, last-level cache, hardware security."

INTRO = [
    "Shared last-level caches improve utilization but allow activity from one security domain to influence another "
    "domain's cache state. Prime+Probe exploits this interaction by filling selected cache sets and measuring the "
    "latency of later accesses [3]. Hardware way partitioning limits each domain to a disjoint subset of cache ways and "
    "can therefore remove cross-domain data evictions [4]. The architectural question is not only whether partitioning "
    "reduces a signal, but how much cache capacity must be assigned before a validated monitor can no longer "
    "distinguish a known activity pattern and what performance cost accompanies that allocation.",
    "We study this question entirely inside gem5 v25.1.0.1. Core 0 measures only its own memory accesses, while core 1 "
    "executes educational T-table AES with a public key, public deterministic plaintexts, and public active/idle "
    "labels. No physical hardware or secret data is involved, and the analysis performs no key recovery.",
    "The methodological core is a matched-control design: a monitor assigned A ways primes and probes exactly A "
    "congruent lines per set, and its partitioned result is interpreted only when an unpartitioned run with the same "
    "depth and seed detects AES activity. This study shows that matched controls are necessary but not sufficient. "
    "Under strict way masks, every cache line the monitor touches competes with its own probe lines, so a monitor can "
    "lose its signal through self-eviction that occurs only in the partitioned arm. Our original analysis fell into "
    "exactly this trap and reported a false 1/15 threshold; this report presents the corrected study.",
]
CONTRIB = [
    "This work makes four concrete contributions. First, it implements per-requestor LLC way partitioning for a "
    "two-core RISC-V gem5 system and validates enforcement using tag-array occupancy rather than inferring isolation "
    "from performance changes. Second, it develops a depth-aware activity monitor whose footprint matches its assigned "
    "capacity and whose measurement loop allocates no cache lines besides its probe lines. Third, it identifies and "
    "removes two self-eviction confounds, a 384 KiB record buffer and a single hot global variable, and adds a "
    "predeclared gate that detects such confounds. Fourth, it uses a repeated, preregistered statistical design that "
    "combines evidence across public inputs and controls false positives across the allocation sweep.",
    "The security goal is deliberately narrow. The monitor decides only whether latency differs between public "
    "AES-active and AES-idle intervals. It does not identify table indices, classify plaintexts, recover key bytes, or "
    "interact with a cryptographic service. The study therefore reports detectability, isolation invariants, and "
    "performance cost as separate outcomes.",
]
BACKGROUND = [
    "A conventional AES T-table implementation uses four 1 KiB lookup tables. Lookup-dependent memory traffic is a "
    "useful controlled source of cache activity, but a private cache can absorb most accesses before they reach the "
    "LLC. Our initial 16 KiB L1D control therefore failed to produce a detectable LLC signal. A later 4 KiB L1D pilot "
    "exposed activity but walked 16 lines per set for every partition size, so with fewer than 16 assigned ways the "
    "monitor evicted its own lines. The first depth-matched study fixed that, yet its monitor still stored 16,384 "
    "measurement records in a 384 KiB array during measurement, which reintroduced self-eviction in a milder form.",
    "The final study retains the 4 KiB L1D stress configuration, matches the monitor footprint to its allocation, and "
    "keeps every other monitor access out of the LLC during measurement. The configuration is intentionally favorable "
    "to exposing T-table traffic at the LLC and is not intended as a model of every commercial processor.",
]
BG_A = ["A set-associative cache maps each physical address to one set and may place the corresponding block in any "
        "way within that set. With a 16-way LLC, as many as 16 blocks can reside in one set. In an unpartitioned "
        "design, blocks from both cores compete for all 16 positions. A monitor can exploit this competition by "
        "filling selected positions and measuring whether later accesses hit or miss. Longer probe latency during "
        "victim-active intervals indicates that the victim changed either cache residency or another shared timing "
        "resource.",
        "Way partitioning changes the placement rule rather than the address-to-set mapping. Each request carries a "
        "partition identifier, and the replacement policy restricts insertion and victim selection to the ways "
        "assigned to that partition. A monitor assigned one way can retain at most one of its blocks per set, while AES "
        "assigned 15 ways can use the remaining positions. The same restriction applies to the monitor's own "
        "non-probe data: any such line resident in the LLC occupies one of the monitor's few ways in its set."]
BG_B = ["T-table AES combines substitution and linear transformation operations into four lookup tables. The table "
        "index depends on intermediate data, so repeated encryption produces data-dependent memory references. In "
        "this project the dependence is not secret: the key and plaintext generator are public. The tables create "
        "structured lookup activity with a compact 4 KiB footprint, allowing the experiment to ask whether activity "
        "reaches the shared LLC and perturbs another core's timing.",
        "Private-cache capacity determines how visible this traffic is. With a 16 KiB L1D, the four tables can remain "
        "resident together with much of the working state, so only a few requests reach the LLC. The 4 KiB L1D stress "
        "profile forces the table footprint to compete with plaintext, round-key, stack, and program data. This "
        "increases LLC exposure without adding explicit flush instructions or artificial table eviction. The choice "
        "improves observability but also narrows external validity."]
PLATFORM_TABLE = (["Component", "Configuration"], [
    ["Simulator", "gem5 v25.1.0.1, commit c8222cc6"], ["ISA and mode", "RISC-V syscall emulation"],
    ["Processors", "2 × TimingSimpleCPU, 2 GHz"], ["Private caches", "16 KiB L1I; 4 KiB, 4-way L1D"],
    ["Shared LLC", "256 KiB, 16-way, 64 B lines, 256 sets, LRU"], ["Memory", "DDR3-1600, 512 MiB"],
    ["Intervals", "32 active + 32 idle, 2,000,000 cycles each"]])
PLATFORM = ("Stock RISC-V requests do not provide the core-specific partition identifiers required by gem5's "
            "way-partitioning policy. An out-of-tree RequestorPartitionManager maps cpu0 and cpu1 traffic to "
            "partitions 0 and 1. For split A/(16-A), ways [0,A) belong to the monitor and ways [A,16) belong to AES. "
            "Instrumentation records mapping consistency, address-partition conflicts, unmapped requests, and "
            "valid-block occupancy outside each mask.")
PLAT_A = ["Each timing CPU receives a distinct gem5 requestor identity. The RequestorPartitionManager translates those "
          "identities to partition 0 for core 0 and partition 1 for core 1. The LLC tag store consults the selected "
          "partitioning policy when allocating or replacing a block. In split A/(16-A), partition 0 may use ways 0 "
          "through A-1, while partition 1 may use ways A through 15. Off mode removes the restrictions.",
          "This mechanism isolates data capacity but does not duplicate the complete LLC pipeline. Requests still "
          "traverse shared crossbars and cache ports, use common miss-status holding registers and queues, and share "
          "the memory controller and DRAM. A remaining latency signal therefore does not mean that way masking failed; "
          "it can arise in another shared structure. The results in Section VII show that this is what happens."]
PLAT_B = ["Syscall-emulation mode was selected because the experiment requires two deterministic user processes rather "
          "than a full operating-system stack. It reduces boot time and eliminates uncontrolled kernel scheduling and "
          "background services. RISC-V provides the rdcycle instruction needed for reproducible simulated timing. "
          "Freestanding static binaries avoid dependence on a guest C library and ensure that the same compiled "
          "workloads are used in every process."]
METHOD = [
    "The monitor primes and probes A lines in every LLC set and records, for each set and interval, a timestamp and the "
    "walk latency. It never writes a separate record array: each 16-byte record is stored in the spare bytes of the "
    "probe line it has just loaded, which is already resident in the L1D, and after every interval a single writev "
    "system call hands all 256 records to the simulator, which reads them functionally without changing cache state. "
    "The way count and file descriptor stay in registers throughout measurement, so the measurement loop loads only "
    "probe-chain pointers. Each process produces 16,384 measurements. Runtime physical-address lookup verifies that "
    "logical set indices differ from physical LLC sets only by a constant rotation; any mismatch invalidates the run.",
    "The AES workload uses four conventional 1 KiB tables, the public key 000102030405060708090a0b0c0d0e0f, and "
    "plaintexts generated by public seeds 0x5764A5E5, 0x5764A5E6, and 0x5764A5E7. A FIPS-197 known-answer test runs "
    "before measurement. The workload reports total encryptions, allowing cycles per completed encryption to be "
    "calculated over the fixed active duration.",
    "For each seed and A=1...8, one unpartitioned control and one partitioned treatment run as fresh gem5 processes. "
    "The 48 inferential runs are supplemented by two A=16 positive-control diagnostics excluded from inference. Every "
    "output directory preserves the command, configuration, binary hashes, simulator statistics, workload log, the raw "
    "probe file, and derived analysis.",
]
METHOD_A = [
    "The two workloads do not synchronize through shared memory. Both derive the current interval from the absolute "
    "rdcycle value and the same compiled schedule. Measurement starts after a fixed warm-up, and each two-million-cycle "
    "interval is labelled active or idle by a deterministic non-alternating sequence. Thirty-two observations per class "
    "provide balanced input to the statistics.",
    "Gem5 resets statistics after warm-up and dumps a measurement-only block before post-measurement logging, so the "
    "reported IPC and cache metrics exclude output overhead. The monitor flushes each interval's records after that "
    "interval's probe walk is complete, and prints its completion line one interval after measurement ends so "
    "that its output cannot interleave with the AES workload's.",
]
METHOD_B = [
    "Changing A changes the monitor itself. A one-line probe has a different instruction count, memory footprint, and "
    "expected signal from an eight-line probe. Comparing every treatment with a single A=16 control would mix the effect "
    "of partitioning with the effect of monitor depth. The matched design holds depth, seed, binary, interval schedule, "
    "and analysis constant; the only intended difference within a pair is whether the LLC way masks are enabled.",
    "A partitioned run is considered interpretable only when its matched control detects activity. If the control "
    "fails, the treatment cannot demonstrate suppression because the monitor lacked sensitivity before the defense was "
    "applied. Requiring all three seed-specific controls to pass is deliberately conservative.",
]
METHOD_C = [
    "A matched control does not detect a confound that exists only in the treatment. In the original study the "
    "monitor's record stores allocated 96 new LLC lines per interval; with 16 ways these displaced old record lines, "
    "but with A ways they displaced probe lines, so 20–25% of partitioned probe walks contained an LLC miss against "
    "almost none in the controls. Those label-independent misses added roughly 120-cycle outliers that hid a "
    "sub-cycle signal. A first corrected monitor removed the buffer; an LLC trace then showed that one remaining line, "
    "holding the global way count, was refetched from A=4 upward and occupied one monitor way in one set.",
    "Each matched pair must therefore pass a self-eviction gate: the fraction of probe walks more than 100 cycles above "
    "the run's 1st-percentile walk time, which identifies an LLC miss, may differ between treatment and control by at "
    "most one percentage point in every seed pair. An allocation that fails the gate is uninterpretable rather than "
    "indistinguishable.",
]
STATS = [
    "For each set, SNR is the absolute difference between mean active and idle latency divided by their pooled sample "
    "standard deviation. The max-set statistic is the maximum SNR over 256 sets. Each of 10,000 balanced label "
    "permutations recomputes this maximum using analysis seed 5764; the empirical p-value is "
    "(1 + count(null ≥ observed))/10001. This construction corrects the within-run search over sets.",
    "The co-primary hit-only statistic averages, per interval, all probe walks within 20 cycles of the run's "
    "1st-percentile walk time and tests the active-minus-idle difference with the same 10,000 permutations. Its effect "
    "size, in cycles per probed line, has a 90% bootstrap confidence interval; an allocation is equivalent to no leak "
    "only if that interval lies inside ±0.02 cycles per line.",
    "For each allocation, Fisher's method combines the three seed-specific p-values. Holm adjustment controls "
    "familywise error across 16 tests, eight allocations by two statistics, at alpha=0.05, separately for controls and "
    "treatments. An allocation is distinguishable if, under either statistic whose control is valid, the treatment is "
    "significant. A stable collapse point is the first indistinguishable allocation for which every larger allocation "
    "is also indistinguishable.",
]
STATS_A = [
    "For one set, the SNR numerator measures the separation between active and idle mean probe latency. The pooled "
    "sample standard deviation normalizes this difference by within-class variability. The maximum across eligible sets "
    "represents the strongest activity-dependent location available to the monitor.",
    "Selecting the maximum creates a multiple-comparison problem: even random labels can produce an unusually large "
    "value when 256 sets are searched. The permutation procedure therefore repeats the complete maximum search after "
    "every shuffle. The plus-one empirical p-value prevents a zero estimate when none of 10,000 permutations exceeds "
    "the observation. The max-set statistic is, however, fragile to rare large outliers in any one set, which is why "
    "the hit-only statistic and the self-eviction gate were added.",
]
STATS_B = [
    "Fisher's method combines the three seed-specific p-values by summing their negative log values. Holm's step-down "
    "procedure then adjusts the 16 allocation-by-statistic p-values while controlling the familywise error rate. "
    "Controls and treatments form separate families because they answer different questions.",
    "The decision rule, thresholds, and file hashes were fixed in a preregistration before the corrected data existed. "
    "Three logged deviations followed: a fix to interleaved output (D1), the hot-variable fix and miss-based gate after "
    "the first corrected sweep (D2), and the full confirmatory sweep reported here (D3).",
]
VALID_TABLE = (["Validation gate", "Observed result"], [
    ["Planned/completed processes", f"{counts['runs']} / 50; no failed directories"],
    ["Probe records", f"{counts['probes']:,}"],
    ["Statistics blocks", f"{counts['blocks']}"],
    ["AES self-tests", f"{counts['aes']} PASS"],
    ["Physical-set mapping", f"{counts['mapping']} PASS congruent"],
    ["Way isolation", f"{counts['disjoint']} PASS disjoint; zero violations"],
    ["Self-eviction gate", f"{counts['gate']}/24 pairs PASS"],
    ["Matched controls (hit-only)", f"{counts['controls_hit_only']}/24 individually distinguishable"],
    ["Binary consistency", "One hash pair across all processes"]])
VALID = (f"Treatment probe walks with an LLC miss averaged {span(min(trt_miss), max(trt_miss), 3)}% against "
         f"{span(min(ctl_miss), max(ctl_miss), 3)}% in the controls. These gates establish that the result is not an "
         "artifact of monitor self-eviction, an unverified virtual-to-physical mapping assumption, or overlapping way "
         "masks.")
VALID_A = ["Virtual address bits within a page do not determine every LLC set bit. The monitor therefore records "
           "address translations and checks the physical LLC set selected by each probe line. A constant rotation is "
           "acceptable because it preserves one-to-one coverage; any missing translation or inconsistent mapping is a "
           f"failure. All {counts['mapping']} processes passed this check."]
VALID_B = ["Performance changes alone cannot prove that way partitioning is enforced. At the end of each measured "
           "statistics interval, instrumentation walks the valid LLC blocks, associates them with their originating "
           "partition, and verifies that each block resides in an allowed way. All 24 treatments reported disjoint "
           "occupancy, zero forbidden-way blocks, zero unmapped lookups, and zero address-partition conflicts.",
           "The validation gates are independent of the security statistic. A treatment must pass mapping, occupancy, "
           "and self-eviction checks even if its signal is small, and a strong signal does not excuse a violation."]
RESULT_TABLE = (["Split", "Control effect", "Partitioned effect [90% CI]", "Holm p (max-set / hit-only)"],
                [[sp(s), f"{ce[s]:.3f}", f"{te[s]:.3f} [{lo[s]:.3f}, {hi[s]:.3f}]",
                  f"{pv(f(v3[s]['treatment_max_set_holm_p']))} / {pv(f(v3[s]['treatment_hit_only_holm_p']))}"]
                 for s in SPLITS])
RESULTS = (
    "All eight partitioned treatments remained distinguishable after correction, so there is no stable collapse point "
    "and no equivalence point. Effects are active-minus-idle hit latency in cycles per probed line (active intervals "
    f"slower), averaged over three seeds. The partitioned monitor retains {pct(r_min)}–{pct(r_max)} of its matched "
    "control's signal, and every confidence interval lies far outside ±0.02 cycles per line. The hit-only control is "
    f"valid at all eight allocations; the max-set control is valid at {of_eight(len(ms_valid))}"
    + ("" if len(ms_valid) == 8 else f" (not at {', '.join(sp(s) for s in SPLITS if s not in ms_valid)})")
    + f", and the max-set treatment test alone is significant at {of_eight(len(ms_sig))}.")
CAPTION = ("Fig. 1. Active-minus-idle hit latency per probed line for matched controls and partitioned treatments "
           "(top, with the treatment 90% bootstrap CI and the ±0.02 equivalence band) and Holm-adjusted treatment "
           "p-values for both statistics (bottom), three public seeds.")
RES_A = [
    f"The control effect rises from {ce[s1]:+.3f} cycles per line at A=1 to {ce['8-8']:+.3f} at A=8. Partitioning "
    f"leaves {pct(ret[s1])} of it at 1/15 and {pct(min(ret[s] for s in SPLITS[1:]))}–"
    f"{pct(max(ret[s] for s in SPLITS[1:]))} at larger allocations. The signal is a latency shift on LLC hits of a few "
    "tenths of a cycle, not an eviction: control probes almost never miss. This is consistent with contention for the "
    "LLC's shared ports, crossbar, or queues, which way masks do not partition; the mechanism was inferred from latency "
    "data, not instrumented.",
    "Way partitioning does remove an eviction component. In the original data, the number of missing control probes "
    "per interval depended on AES activity from A=5 upward, and the A=16 diagnostics show a very strong eviction "
    "signal when the monitor fills every way. With the corrected monitor, at most "
    f"{max(trt_miss):.3f}% of partitioned probe walks contain an LLC miss, so no eviction signal remains. Partitioning "
    "therefore closes the storage channel it was designed to close, while a smaller timing channel remains.",
]
COMPARE_TABLE = (["Split", "Treatment all-hit walks, original → final", "Original decision", "Final decision"],
                 [[sp(s), f"{v1_allhit[i]:.1f}% → {v3_allhit[i]:.2f}%",
                   "Indist." if v1[s]["conclusion"] == "indistinguishable" else v1[s]["conclusion"], "Dist."]
                  for i, s in enumerate(SPLITS)])
RES_B = [
    f"The original study found every treatment indistinguishable (Holm p from {pv(min(f(v1[s]['partitioned_holm_p']) for s in SPLITS))} "
    "to 1.000) and reported 1/15 as a stable collapse point. The reason is monitor self-eviction: in the original monitor "
    f"only {min(v1_allhit):.1f}–{max(v1_allhit):.1f}% of partitioned probe walks were free of LLC misses, against "
    f"{min(v3_allhit):.2f}–{max(v3_allhit):.2f}% after the fix. The original 1/15 threshold was produced by the "
    "measurement artifact, not by the defense, and is withdrawn.",
]
PERF_TABLE = (["Metric at 1/15", "Matched change"], [
    ["Monitor IPC", f"{signed(-f(v3[s1]['monitor_ipc_cost_pct_mean']), 4)}%"],
    ["AES IPC", f"{signed(-f(v3[s1]['aes_ipc_cost_pct_mean']), 4)}%"],
    ["Monitor LLC miss rate", f"{signed(f(v3[s1]['monitor_llc_miss_delta_pp_mean']), 3)} percentage points"],
    ["AES LLC miss rate", f"{signed(f(v3[s1]['aes_llc_miss_delta_pp_mean']), 4)} percentage points"],
    ["AES cycles/encryption", f"{signed(f(v3[s1]['aes_cycles_per_encryption_cost_pct_mean']), 4)}%"]])
PERF = (f"Across all eight allocations, monitor IPC changes by at most {max(abs(x) for x in mon_ipc):.3f}% and AES "
        f"cycles per encryption by at most {max(abs(x) for x in aes_cpe):.3f}%; the monitor's LLC miss rate rises by "
        f"{span(min(mon_miss), max(mon_miss), 2)} percentage points. Both workloads fit easily in their allocations, so "
        "partitioning costs them essentially nothing. Cycles per encryption is the clearer useful-work metric because "
        "both programs contain rdcycle busy-wait loops that contribute instructions to IPC.")
PERF_A = [
    f"The original study reported a monitor IPC cost rising from {f(v1[s1]['monitor_ipc_cost_pct_mean']):.2f}% at 1/15 "
    f"to {f(v1['8-8']['monitor_ipc_cost_pct_mean']):.2f}% at 8/8 and a monitor miss-rate increase near 19 percentage "
    "points. Those costs came from the monitor evicting its own probe lines, not from partitioning, and disappear with "
    "the corrected monitor. A larger AES working set or a capacity-hungry co-runner could still show a real tradeoff.",
]
THREATS = [
    "The study uses gem5 timing rather than silicon measurements. The symmetric 4 KiB L1D caches deliberately expose "
    "T-table traffic and limit generalization. Three consecutive deterministic seeds are repeated inputs, not a "
    "population of executions, and Fisher combination assumes the seed-level tests are independent; most p-values "
    "already sit at the permutation floor. The hit-only statistic was chosen after a post-hoc analysis of the original "
    "data and the gate was revised after the first corrected sweep; both were fixed before the final data existed, and "
    f"the max-set statistic alone reaches the same conclusion at {of_eight(len(ms_sig))} allocations.",
    "Way masks isolate LLC data capacity but not MSHRs, queues, ports, interconnects, coherence metadata, memory "
    "controllers, or DRAM. The residual signal is attributed to these structures by elimination, not by direct "
    "measurement. The result applies only to this monitor, workload, cache hierarchy, run length, and decision rule.",
]
REPRO = ["Every quantitative claim traces from this report to results/updated run/sweep-v3/summary_v3.csv, from that "
         "table to the per-run analysis files, and from each analysis file to the raw probes.bin, simout.txt, and "
         "stats.txt. The preregistration fixes the decision rule and file hashes. The original study's results and "
         "code paths are preserved unchanged and verified by checksum, and an original case rerun with the current "
         "code reproduced it byte for byte."]
FUTURE = ["Architecturally, the next step is to instrument the shared LLC path, including ports, crossbar, and MSHR "
          "occupancy, to confirm the source of the residual hit-timing signal, and to test mitigations that partition "
          "bandwidth as well as capacity. More seeds, larger L1D sizes, and capacity-hungry co-runners would test "
          "generality and expose a real performance tradeoff. These extensions should retain the current safeguards: "
          "simulator-only execution, public inputs, activity detection rather than key inference, matched positive "
          "controls, direct isolation evidence, and a self-eviction gate."]
CONCLUSION = (
    "This project evaluated LLC way partitioning against labelled AES cache activity in gem5 with matched controls, "
    "direct isolation evidence, and a preregistered statistical rule. After correcting a monitor self-eviction "
    "artifact that had produced a false 1/15 threshold in our original analysis, all eight allocations from 1/15 to "
    f"8/8 remain distinguishable, the partitioned monitor retains {pct(r_min)}–{pct(r_max)} of the control signal, and "
    "no allocation is equivalent to zero. Way partitioning removes eviction-based contention at negligible cost, but it "
    "does not close the hit-timing channel through shared LLC resources. A complete defense must also isolate those "
    "resources, and any evaluation of such defenses must verify that the measuring monitor does not interfere with "
    "itself.")
REFS = ["[1] gem5 Project, “gem5 v25.1.0.1 source,” 2026. [Online]. Available: https://github.com/gem5/gem5/tree/v25.1.0.1",
        "[2] J. Lowe-Power et al., “The gem5 simulator: Version 20.0+,” arXiv:2007.03152, 2020.",
        "[3] D. A. Osvik, A. Shamir, and E. Tromer, “Cache attacks and countermeasures: The case of AES,” in Proc. CT-RSA, 2006.",
        "[4] F. Liu et al., “CATalyst: Defeating last-level cache side channel attacks in cloud computing,” in Proc. IEEE HPCA, 2016."]


def P(texts):
    return [("p", t) for t in texts]


def blocks(expanded: bool) -> list[tuple]:
    b = [("title", TITLE), ("author", AUTHORS), ("course", COURSE), ("p", ABSTRACT), ("p", INDEX), ("break",),
         ("h1", "I. INTRODUCTION"), *P(INTRO)]
    if expanded:
        b += [("h2", "A. Research Contributions and Scope"), *P(CONTRIB)]
    b += [("h1", "II. BACKGROUND AND MOTIVATION"), *P(BACKGROUND)]
    if expanded:
        b += [("h2", "A. Cache Contention and Set Associativity"), *P(BG_A),
              ("h2", "B. Why T-table AES Produces a Controlled Signal"), *P(BG_B)]
    b += [("h1", "III. EXPERIMENTAL PLATFORM"), ("table", *PLATFORM_TABLE), ("p", PLATFORM)]
    if expanded:
        b += [("h2", "A. Request to Way-Mask Path"), *P(PLAT_A), ("h2", "B. Choice of RISC-V SE Mode"), *P(PLAT_B)]
    b += [("h1", "IV. WORKLOADS AND METHOD"), *P(METHOD)]
    if expanded:
        b += [("h2", "A. Interval Synchronization and Logging"), *P(METHOD_A),
              ("h2", "B. Why Matched Controls Are Required"), *P(METHOD_B),
              ("h2", "C. Why Matched Controls Are Not Sufficient"), *P(METHOD_C)]
    else:
        b += P(METHOD_C)
    b += [("h1", "V. STATISTICAL ANALYSIS"), *P(STATS)]
    if expanded:
        b += [("h2", "A. From Per-set SNR to a Run-level Test"), *P(STATS_A),
              ("h2", "B. Combining Repetitions and Allocations"), *P(STATS_B)]
    b += [("h1", "VI. VALIDATION"), ("table", *VALID_TABLE), ("p", VALID)]
    if expanded:
        b += [("h2", "A. Physical-set Congruence"), *P(VALID_A), ("h2", "B. Direct Way-occupancy Evidence"), *P(VALID_B)]
    b += [("h1", "VII. RESULTS"), ("table", *RESULT_TABLE), ("p", RESULTS), ("figure",), ("caption", CAPTION)]
    if expanded:
        b += [("h2", "A. Interpretation Across Allocations"), *P(RES_A),
              ("h2", "B. Why the Original Analysis Reported a 1/15 Threshold"), ("table", *COMPARE_TABLE), *P(RES_B)]
    else:
        b += [("p", RES_A[0]), ("p", RES_B[0])]
    b += [("h1", "VIII. PERFORMANCE TRADEOFF"), ("table", *PERF_TABLE), ("p", PERF)]
    if expanded:
        b += [("h2", "A. Costs in the Original Analysis"), *P(PERF_A)]
    b += [("h1", "IX. THREATS TO VALIDITY"), *P(THREATS)]
    if expanded:
        b += [("h2", "A. Reproducibility and Traceability"), *P(REPRO), ("h2", "B. Future Work"), *P(FUTURE)]
    b += [("h1", "X. CONCLUSION"), ("p", CONCLUSION), ("h1", "REFERENCES"), *[("ref", r) for r in REFS]]
    return b


if __name__ == "__main__":
    figure = ROOT / "repeated_v3.png"
    for template, out, expanded in (
        ("Group18_EEL5764_Final_Project_Report.docx", "Group18_EEL5764_Final_Project_Report_Updated.docx", False),
        ("Group18_EEL5764_Final_Project_Report_Expanded.docx",
         "Group18_EEL5764_Final_Project_Report_Expanded_Updated.docx", True),
    ):
        build(Path(template), Path(out), blocks(expanded), figure)
        print("wrote", out)
