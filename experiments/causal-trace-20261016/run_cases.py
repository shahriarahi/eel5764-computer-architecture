"""Bounded fresh-process runner for causal trace endpoint cases."""

import argparse
import json
import os
from pathlib import Path
import secrets
import string
import subprocess
import sys


# tdma-cd0 holds the aborted 2026-10-18 attempt and is never reused.
DISABLED_ROOT = "tdma-cd1"
# tdma-ct1 holds the A=1 case that failed G3 under the one-to-one delivery matcher.
# tdma-ct2 holds a valid A=1 case and an A=8 case that hit the 240 s bound.
ENABLED_ROOT = "tdma-ct3"
TIMEOUT_SECONDS = 240
# Trace logging through /mnt/c roughly doubles A=8 host time; simulation is unaffected.
TRACE_TIMEOUT_SECONDS = 900


def case_timeout(trace: bool) -> int:
    return TRACE_TIMEOUT_SECONDS if trace else TIMEOUT_SECONDS


def require_new(path: Path) -> None:
    if path.exists():
        raise FileExistsError(path)


def temporary_case_name(parent: Path, probe_argument_length: int) -> str:
    """Staging name giving parent/<name>/probes.bin the reference's exact length."""
    width = probe_argument_length - len(str(parent / "x" / "probes.bin")) + 1
    if width < 1:
        raise ValueError("probe argument length unreachable under this parent")
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(width))


def monitored_range(metadata: dict) -> tuple[int, int]:
    return int(metadata["probe_vaddr_base"]), int(metadata["probe_vaddr_size"])


def build_command(reference: dict, output: Path, trace: bool,
                  executable: Path, adapter: Path, requestor: str,
                  vaddr_base: int, vaddr_size: int) -> list[str]:
    command = list(reference["command"])
    command[0] = str(executable)
    command[command.index("-d") + 1] = str(output)
    old_adapter = next(index for index, item in enumerate(command)
                       if item.endswith("run_contention_tdma.py"))
    command[old_adapter] = str(adapter)
    if trace:
        command[1:1] = ["--debug-flags=CausalTrace", "--debug-file=causal.log"]
        adapter_index = command.index(str(adapter))
        command[adapter_index + 1:adapter_index + 1] = [
            "--causal-trace", "--causal-requestor", requestor,
            "--causal-vaddr-base", hex(vaddr_base),
            "--causal-vaddr-size", hex(vaddr_size),
        ]
    return command


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()
    project = args.baseline_root.resolve()
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    from validate_trace import validate_equivalence, validate_trace_case
    executable = Path("/home/shahriarahi/eel5764/gem5-causal/build/RISCV/gem5.opt")
    root_name = ENABLED_ROOT if args.trace else DISABLED_ROOT
    result_root = project / "results/updated run" / root_name
    require_new(result_root)
    parent = result_root / "seed-5764a5e5"
    # Plan every case, including its exact probe-path length, before creating output.
    planned = []
    for ways in (1, 8):
        name = f"{ways}-{16-ways}"
        reference = project / "results/updated run/tdma-onx/seed-5764a5e5" / name
        manifest = json.loads((reference / "command.json").read_text())
        metadata = json.loads((reference / "run_meta.json").read_text())
        staging_name = temporary_case_name(parent, manifest["probe_argument_length"])
        if len(str(parent / staging_name / "probes.bin")) != manifest["probe_argument_length"]:
            raise ValueError("probe argument length differs from reference")
        planned.append((name, reference, manifest, metadata, staging_name))
    result_root.mkdir()
    parent.mkdir()
    for name, reference, manifest, metadata, staging_name in planned:
        vaddr_base, vaddr_size = monitored_range(metadata)
        final = parent / name
        require_new(final)
        case = parent / staging_name
        case.mkdir()
        command = build_command(
            manifest, case, args.trace, executable,
            here / "run_contention_causal.py", "cpu0.data",
            vaddr_base, vaddr_size,
        )
        (case / "command.json").write_text(json.dumps({
            "command": command, "trace": args.trace,
            "timeout_seconds": case_timeout(args.trace), "reference": str(reference),
        }, indent=2) + "\n")
        try:
            with (case / "launcher.log").open("x") as stream:
                subprocess.run(command, cwd=project, stdout=stream,
                               stderr=subprocess.STDOUT, timeout=case_timeout(args.trace),
                               check=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            result = validate_equivalence(reference, case)
            if args.trace:
                result.update(validate_trace_case(case))
            elif (case / "causal.log").exists() and "CAUSAL_TRACE" in (case / "causal.log").read_text():
                raise ValueError("trace-disabled case emitted causal records")
            (case / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
            case.rename(final)
            print("PASS", root_name, name, json.dumps(result), flush=True)
        except Exception as exc:
            (case / "failure.json").write_text(json.dumps({"error": repr(exc)}, indent=2) + "\n")
            failed = parent / f"{name}.failed.{staging_name}"
            case.rename(failed)
            print("FAILED preserved", failed, repr(exc), flush=True)
            raise


if __name__ == "__main__":
    main()

