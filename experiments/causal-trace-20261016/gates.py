"""Preregistered G4: scheduler counters, which the G1/G2 statistics comparison excludes."""

import argparse
import gzip
import json
from pathlib import Path


VIOLATIONS = ("tdmaOverruns", "tdmaDownstreamRefusals", "tdmaExpressBypasses")


def tdma_lines(path: Path) -> list[str]:
    with gzip.open(path / "stats.txt.gz", "rt") as stream:
        return [line.strip() for line in stream if ".tdma" in line]


def tdma_counter_gate(reference: Path, case: Path) -> dict:
    expected, actual = tdma_lines(reference), tdma_lines(case)
    if not actual:
        raise ValueError("no tdma counters in case statistics")
    if expected != actual:
        raise ValueError("tdma counter lines differ from reference")
    for line in actual:
        fields = line.split()
        name = fields[0].rsplit(".", 1)[-1]
        if name in VIOLATIONS and float(fields[1]) != 0:
            raise ValueError(f"scheduler violation {fields[0]}={fields[1]}")
    return {"tdma_lines": len(actual), "violations": 0}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    print("PASS G4", args.case, json.dumps(tdma_counter_gate(args.reference, args.case)))


if __name__ == "__main__":
    main()
