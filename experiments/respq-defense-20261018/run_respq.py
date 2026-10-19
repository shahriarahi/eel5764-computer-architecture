"""Bounded fresh-process runner: disabled guards, then per-domain response-queue defense arms."""

import argparse
from dataclasses import dataclass
import gzip
import hashlib
import json
import os
from pathlib import Path
import secrets
import string
import subprocess
import sys


HERE = Path(__file__).resolve().parent
TDMA = HERE.parent / "tdma"
EXECUTABLE = Path("/home/shahriarahi/eel5764/gem5-respq/build/RISCV/gem5.opt")
TIMEOUT_SECONDS = 240
SEED_DIR = "seed-5764a5e5"
VIOLATIONS = ("tdmaOverruns", "tdmaDownstreamRefusals", "tdmaExpressBypasses")
ADAPTER_SUFFIXES = ("run_contention_tdma.py", "quiet_adapter.py")


@dataclass(frozen=True)
class Arm:
    name: str
    root: str
    reference_root: str
    respq: bool


# Guards first: the disabled build must reproduce both stored references.
ARMS = (
    Arm("guard-aes", "tdma-rga", "tdma-onx", False),
    Arm("guard-quiet", "tdma-rgq", "tdma-nc0", False),
    Arm("defense-aes", "tdma-rda", "tdma-onx", True),
    Arm("defense-quiet", "tdma-rdq", "tdma-nc0", True),
)


def stats_rows(path: Path) -> list[str]:
    # TDMA must precede site-packages (its "validate" collides with one) only for this import.
    sys.path.insert(0, str(TDMA))
    try:
        from run_pilot import stats_rows as tdma_stats_rows
    finally:
        sys.path.remove(str(TDMA))
    return tdma_stats_rows(path)


def staging_name(parent: Path, probe_argument_length: int) -> str:
    width = probe_argument_length - len(str(parent / "x" / "probes.bin")) + 1
    if width < 1:
        raise ValueError("probe argument length unreachable under this parent")
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(width))


def build_command(reference: dict, output: Path, executable: Path, adapter: Path,
                  respq: bool) -> list[str]:
    command = list(reference["command"])
    command[0] = str(executable)
    command[command.index("-d") + 1] = str(output)
    index = next(i for i, item in enumerate(command) if item.endswith(ADAPTER_SUFFIXES))
    command[index] = str(adapter)
    if respq:
        command.insert(index + 1, "--respq")
    return command


def compare_probes(left: Path, right: Path) -> dict:
    a = (left / "probes.bin").read_bytes()
    b = (right / "probes.bin").read_bytes()
    if len(a) != len(b) or len(a) % 16:
        raise ValueError("probe files differ in length or are not whole records")
    records = len(a) // 16
    per_interval = records // 64
    differing = [i for i in range(records) if a[16 * i:16 * i + 16] != b[16 * i:16 * i + 16]]
    return {
        "records": records,
        "differing_records": len(differing),
        "differing_intervals": sorted({i // per_interval for i in differing}),
        "first_differing_record": differing[0] if differing else None,
        "byte_identical": not differing,
    }


def tdma_lines(case: Path) -> list[str]:
    with gzip.open(case / "stats.txt.gz", "rt") as stream:
        return [line.strip() for line in stream if ".tdma" in line]


def tdma_counter_gate(reference: Path | None, case: Path) -> dict:
    actual = tdma_lines(case)
    if not actual:
        raise ValueError("no tdma counters in case statistics")
    if reference is not None and tdma_lines(reference) != actual:
        raise ValueError("tdma counter lines differ from reference")
    for line in actual:
        fields = line.split()
        if fields[0].rsplit(".", 1)[-1] in VIOLATIONS and float(fields[1]) != 0:
            raise ValueError(f"scheduler violation {fields[0]}={fields[1]}")
    return {"tdma_lines": len(actual), "violations": 0}


def llc_prefixes(case: Path) -> str:
    section = None
    for line in (case / "config.ini").read_text().splitlines():
        if line.startswith("["):
            section = line.strip("[]")
        elif section == "system.llc" and line.startswith("response_domain_prefixes="):
            return line.split("=", 1)[1]
    raise ValueError("system.llc has no response_domain_prefixes parameter")


def validate(arm: Arm, reference: Path, case: Path) -> dict:
    prefixes = llc_prefixes(case)
    if arm.respq != (prefixes == "cpu0. cpu1."):
        raise ValueError(f"unexpected system.llc response_domain_prefixes={prefixes!r}")
    result = {"response_domain_prefixes": prefixes}
    if arm.respq:
        result.update(tdma_counter_gate(None, case))
        result["probes_vs_reference"] = compare_probes(reference, case)
    else:
        if (reference / "probes.bin").read_bytes() != (case / "probes.bin").read_bytes():
            raise ValueError("guard probe bytes differ from reference")
        if stats_rows(reference / "stats.txt.gz") != stats_rows(case / "stats.txt.gz"):
            raise ValueError("guard simulated statistics differ from reference")
        result.update(tdma_counter_gate(reference, case))
        result["equivalence"] = "byte-identical probes and matching simulated statistics"
    return result


def run_arm(project: Path, arm: Arm, ways_list: list[int]) -> None:
    results = project / "results/updated run"
    root = results / arm.root
    if root.exists():
        raise FileExistsError(root)
    parent = root / SEED_DIR
    planned = []
    for ways in ways_list:
        name = f"{ways}-{16 - ways}"
        reference = results / arm.reference_root / SEED_DIR / name
        manifest = json.loads((reference / "command.json").read_text())
        stage = staging_name(parent, manifest["probe_argument_length"])
        if len(str(parent / stage / "probes.bin")) != manifest["probe_argument_length"]:
            raise ValueError("probe argument length differs from reference")
        planned.append((name, reference, manifest, stage))
    root.mkdir()
    parent.mkdir()
    executable_sha = hashlib.sha256(EXECUTABLE.read_bytes()).hexdigest()
    for name, reference, manifest, stage in planned:
        case = parent / stage
        case.mkdir()
        command = build_command(manifest, case, EXECUTABLE, HERE / "run_contention_respq.py",
                                arm.respq)
        (case / "command.json").write_text(json.dumps({
            "arm": arm.name, "command": command, "reference": str(reference),
            "timeout_seconds": TIMEOUT_SECONDS, "executable_sha256": executable_sha,
            "probe_argument_length": manifest["probe_argument_length"],
        }, indent=2) + "\n")
        try:
            with (case / "launcher.log").open("x") as stream:
                subprocess.run(command, cwd=project, stdout=stream, stderr=subprocess.STDOUT,
                               timeout=TIMEOUT_SECONDS, check=True,
                               env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            result = validate(arm, reference, case)
            (case / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
            case.rename(parent / name)
            print("PASS", arm.name, name, json.dumps(result), flush=True)
        except Exception as exc:
            (case / "failure.json").write_text(json.dumps({"error": repr(exc)}, indent=2) + "\n")
            failed = parent / f"{name}.failed.{stage}"
            case.rename(failed)
            print("FAILED preserved", failed, repr(exc), flush=True)
            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--arms", nargs="+", default=[arm.name for arm in ARMS],
                        choices=[arm.name for arm in ARMS])
    args = parser.parse_args()
    project = args.baseline_root.resolve()
    for arm in ARMS:
        if arm.name in args.arms:
            run_arm(project, arm, [1, 8])


if __name__ == "__main__":
    main()
