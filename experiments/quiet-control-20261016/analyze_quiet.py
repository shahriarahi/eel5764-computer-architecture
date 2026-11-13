"""Read quiet cases; save the predeclared diagnostic in a fresh directory."""
import argparse
import json
from pathlib import Path
import random
import sys

sys.dont_write_bytecode = True
from run_control import HERE, TDMA, validate_quiet, write_json
from summarize import security_statistics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    args = parser.parse_args()
    project = args.baseline_root.resolve()
    sys.path.insert(0, str(project))
    from analysis.analyze_contention import parse_probe_binary
    from analysis.summarize_repeated_contention import holm_adjust
    from analysis.summarize_repeated_contention_v2 import bootstrap_ci
    out = HERE / "analysis"
    out.mkdir(exist_ok=False)
    rows = []
    rng = random.Random(5764)
    for ways in (1, 8):
        case = project / "results/updated run/tdma-nc0/seed-5764a5e5" / f"{ways}-{16-ways}"
        validation = validate_quiet(project, case, ways)
        meta = json.loads((case / "run_meta.json").read_text())
        c = meta["contention"]
        matrix, labels = parse_probe_binary(case / "probes.bin", expected_labels=c["activity_labels"],
                                            start_cycle=c["start_cycle"], epoch_cycles=c["epoch_cycles"],
                                            interval_count=c["interval_count"], set_count=c["llc_sets"])
        row = {"ways": ways, "validation": validation, "nominal_labels": labels}
        row.update(security_statistics(project, matrix, labels, ways))
        if "hit_only" in row:
            hit = row["hit_only"]
            low, high = bootstrap_ci([(hit["hit_only_interval_means"], labels, ways)], rng)
            row.update(ci90=[low, high], mean_equivalent=(-0.02 < low and high < 0.02))
        write_json(out / f"A{ways}.json", row)
        rows.append(row)
        print("ANALYZED", ways, "all_walk_delta", row["all_walk_delta_cycles_per_line"], flush=True)
    for statistic, field in (("max_set", "empirical_p"), ("hit_only", "hit_only_p")):
        if all(statistic in row for row in rows):
            adjusted = holm_adjust({str(row["ways"]): row[statistic][field] for row in rows})
            for row in rows:
                row[statistic + "_holm_p"] = adjusted[str(row["ways"])]
    summary = []
    for row in rows:
        cell = {key: value for key, value in row.items()
                if key not in ("validation", "nominal_labels", "max_set", "hit_only")}
        if "hit_only" in row:
            cell["hit_only_delta_cycles_per_line"] = row["hit_only"]["hit_only_delta_per_line"]
        summary.append(cell)
    report = {"rows": summary, "claim_limit": "Single-schedule diagnostic; nominal activity labels; startup drain unverified; no indistinguishability or response-causality claim"}
    write_json(out / "summary.json", report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
