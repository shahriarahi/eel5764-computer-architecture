"""Read only experiment data; write analysis exclusively to a new directory."""
import argparse
import gzip
import json
from pathlib import Path
import random
import statistics
import sys
import time
from run_pilot import SEEDS, build_plan, case_path
from validate import validate_case


def numeric_blocks(path: Path) -> list[dict[str, float]]:
    blocks = []
    current = None
    with gzip.open(path, "rt") as stream:
        for line in stream:
            if line.startswith("---------- Begin Simulation Statistics"):
                current = {}
            elif line.startswith("---------- End Simulation Statistics"):
                if current is None:
                    raise ValueError("statistics end without begin")
                blocks.append(current)
                current = None
            elif current is not None:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        current[parts[0]] = float(parts[1])
                    except ValueError:
                        continue
    if current is not None:
        raise ValueError("unterminated statistics block")
    return blocks


def security_statistics(project: Path, matrix: list[list[float]], labels: list[int], ways: int) -> dict:
    sys.path.insert(0, str(project))
    from analysis.analyze_contention import max_set_permutation_test, hit_only_test, AnalysisError
    interval_means = [statistics.mean(row) for row in matrix]
    active = [value for value, label in zip(interval_means, labels) if label == 1]
    idle = [value for value, label in zip(interval_means, labels) if label == 0]
    result = {"all_walk_delta_cycles_per_line": (statistics.mean(active) - statistics.mean(idle)) / ways}
    try:
        result["max_set"] = max_set_permutation_test(matrix, labels)
    except AnalysisError as exc:
        result["max_set_error"] = str(exc)
    try:
        result["hit_only"] = hit_only_test(matrix, labels, ways)
    except AnalysisError as exc:
        result["hit_only_error"] = str(exc)
    return result


def analyze_case(project: Path, arm: str, seed: int, ways: int) -> dict:
    sys.path.insert(0, str(project))
    from analysis.analyze_contention import parse_probe_binary, parse_workload_metadata
    case = project / case_path(arm, seed, ways)
    validation = validate_case(project, case, ways, arm != "off", 4 if arm == "onx" else 0)
    meta = json.loads((case / "run_meta.json").read_text())
    c = meta["contention"]
    matrix, labels = parse_probe_binary(case / "probes.bin", expected_labels=c["activity_labels"],
                                        start_cycle=c["start_cycle"], epoch_cycles=c["epoch_cycles"],
                                        interval_count=c["interval_count"], set_count=c["llc_sets"])
    print("ANALYZE", arm, hex(seed), ways, flush=True)
    result = {"arm": arm, "seed": seed, "ways": ways, "validation": validation, "labels": labels}
    result.update(security_statistics(project, matrix, labels, ways))
    blocks = numeric_blocks(case / "stats.txt.gz")[:64]
    result.update(parse_workload_metadata(case / "simout.txt", expected_monitor_ways=ways,
                                         expected_workload_seed=seed,
                                         active_cycles=labels.count(1) * c["epoch_cycles"]))
    for core in (0, 1):
        cycles = sum(b[f"system.cpu{core}.numCycles"] for b in blocks)
        instructions = sum(b[f"system.cpu{core}.thread_0.numInsts"] for b in blocks)
        result[f"ipc_core{core}"] = instructions / cycles
        accesses = sum(b.get(f"system.llc.demandAccesses::cpu{core}.{kind}", 0)
                       for b in blocks for kind in ("inst", "data"))
        misses = sum(b.get(f"system.llc.demandMisses::cpu{core}.{kind}", 0)
                     for b in blocks for kind in ("inst", "data"))
        if not accesses:
            raise ValueError("no LLC accesses")
        result[f"llc_miss_rate_core{core}"] = misses / accesses
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=0,
                        help="bounded total wait for cases currently being simulated")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.baseline_root))
    from analysis.summarize_repeated_contention import fisher_combined_p, holm_adjust
    from analysis.summarize_repeated_contention_v2 import bootstrap_ci
    seeds = SEEDS[:1] if args.pilot_only else SEEDS
    rows = []
    deadline = time.monotonic() + args.wait_seconds
    for arm, seed, ways in build_plan(seeds):
        validation = args.baseline_root / case_path(arm, seed, ways) / "validation.json"
        while not validation.is_file() and time.monotonic() < deadline:
            time.sleep(2)
        row = analyze_case(args.baseline_root, arm, seed, ways)
        (args.out / f"{arm}-{seed:08x}-A{ways}.json").write_text(json.dumps(row, indent=2))
        rows.append(row)
    summary = []
    rng = random.Random(5764)
    for arm in ("off", "way", "onx"):
        group = {ways: [r for r in rows if r["arm"] == arm and r["ways"] == ways] for ways in (1, 8)}
        max_valid = all("max_set" in r for values in group.values() for r in values)
        max_p = (holm_adjust({str(a): fisher_combined_p([r["max_set"]["empirical_p"] for r in group[a]]) for a in (1, 8)}) if max_valid else {})
        hit_valid = all("hit_only" in r for values in group.values() for r in values)
        hit_p = (holm_adjust({str(a): fisher_combined_p([r["hit_only"]["hit_only_p"] for r in group[a]]) for a in (1, 8)}) if hit_valid else {})
        for ways in (1, 8):
            values = group[ways]
            cell = {"arm": arm, "ways": ways, "seeds": len(seeds),
                    "all_walk_delta_cycles_per_line_mean": statistics.mean(r["all_walk_delta_cycles_per_line"] for r in values),
                    "aes_encryptions_mean": statistics.mean(r["aes_encryptions"] for r in values),
                    "aes_cycles_per_encryption_mean": statistics.mean(r["aes_cycles_per_encryption"] for r in values),
                    "llc_miss_rate_core0_mean": statistics.mean(r["llc_miss_rate_core0"] for r in values),
                    "llc_miss_rate_core1_mean": statistics.mean(r["llc_miss_rate_core1"] for r in values),
                    "ipc0_mean": statistics.mean(r["ipc_core0"] for r in values),
                    "ipc1_mean": statistics.mean(r["ipc_core1"] for r in values)}
            if max_valid:
                cell["max_set_holm_p"] = max_p[str(ways)]
            else:
                cell["max_set_status"] = "undefined; inference unresolved; no expansion"
            if hit_valid:
                low, high = bootstrap_ci([(r["hit_only"]["hit_only_interval_means"], r["labels"], ways) for r in values], rng)
                cell.update(effect_cycles_per_line=statistics.mean(r["hit_only"]["hit_only_delta_per_line"] for r in values),
                            ci90=[low, high], mean_equivalent=(-0.02 < low and high < 0.02),
                            hit_only_holm_p=hit_p[str(ways)])
            else:
                cell["hit_only_status"] = "undefined; no expansion"
            summary.append(cell)
    for cell in summary:
        control = next(x for x in summary if x["arm"] == "off" and x["ways"] == cell["ways"])
        way_only = next(x for x in summary if x["arm"] == "way" and x["ways"] == cell["ways"])
        cell["aes_throughput_change_percent"] = 100 * (cell["aes_encryptions_mean"] / control["aes_encryptions_mean"] - 1)
        cell["aes_throughput_change_vs_way_only_percent"] = 100 * (cell["aes_encryptions_mean"] / way_only["aes_encryptions_mean"] - 1)
    report = {"pilot_only": args.pilot_only, "rows": summary,
              "claim_limit": "Endpoint activity tests; no distributional indistinguishability proof"}
    (args.out / "summary.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
