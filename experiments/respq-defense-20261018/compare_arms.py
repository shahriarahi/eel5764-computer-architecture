"""Preregistered primary and secondary outcomes for the response-queue defense."""

import argparse
import json
from pathlib import Path
import re

from run_respq import SEED_DIR, compare_probes


def encryptions(case: Path) -> int:
    found = re.findall(r"^victim measurement_complete encryptions=(\d+)\b",
                       (case / "simout.txt").read_text(), re.MULTILINE)
    if len(found) != 1:
        raise ValueError(f"{case}: expected one victim completion record")
    return int(found[0])


def labelled(comparison: dict, case: Path) -> dict:
    labels = json.loads((case / "run_meta.json").read_text())["contention"]["activity_labels"]
    comparison["differing_interval_labels"] = [labels[i] for i in comparison["differing_intervals"]]
    return comparison


def outcomes(results: Path) -> dict:
    report = {"label": "simulated (gem5), seed 0x5764A5E5", "allocations": {}}
    passed = True
    for name in ("1-15", "8-8"):
        case = lambda root: results / root / SEED_DIR / name  # noqa: E731
        primary = labelled(compare_probes(case("tdma-rda"), case("tdma-rdq")), case("tdma-rda"))
        passed &= primary["byte_identical"]
        aes = {root: encryptions(case(root)) for root in ("tdma-way", "tdma-onx", "tdma-rda")}
        report["allocations"][name] = {
            "primary_defense_aes_vs_defense_quiet": primary,
            "baseline_tdma_aes_vs_tdma_quiet": labelled(
                compare_probes(case("tdma-onx"), case("tdma-nc0")), case("tdma-onx")),
            "defense_aes_vs_tdma_aes": compare_probes(case("tdma-onx"), case("tdma-rda")),
            "defense_quiet_vs_tdma_quiet": compare_probes(case("tdma-nc0"), case("tdma-rdq")),
            "aes_encryptions": aes,
            "aes_throughput_change_percent": {
                "vs_way_only": 100 * (aes["tdma-rda"] / aes["tdma-way"] - 1),
                "vs_request_tdma": 100 * (aes["tdma-rda"] / aes["tdma-onx"] - 1),
            },
        }
    report["primary_outcome"] = "PASS" if passed else "FAIL"
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = outcomes(args.baseline_root / "results/updated run")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(report["primary_outcome"], json.dumps({
        name: {"differing": a["primary_defense_aes_vs_defense_quiet"]["differing_records"],
               "baseline_differing": a["baseline_tdma_aes_vs_tdma_quiet"]["differing_records"]}
        for name, a in report["allocations"].items()}))


if __name__ == "__main__":
    main()
