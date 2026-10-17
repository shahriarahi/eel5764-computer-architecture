"""Read-only fingerprints; snapshot output is created exclusively, never replaced."""
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKTREE = HERE.parents[1]
ROOT = WORKTREE.parents[1]


def digest(path: Path, deadline: float) -> str:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f"Outside workspace: {path}")
    result = hashlib.sha256()
    with resolved.open("rb") as stream:
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("Preservation audit exceeded 90-second deadline")
            block = stream.read(1024 * 1024)
            if not block:
                break
            result.update(block)
    return result.hexdigest()


def inventory() -> tuple[dict[str, str], list[str]]:
    frozen = json.loads((WORKTREE / "experiments/tdma/preservation.json").read_text())
    expected = dict(frozen["files"])
    names = set(expected)
    for arm in ("tdma-gd0", "tdma-off", "tdma-way", "tdma-onx"):
        directory = ROOT / "results/updated run" / arm
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        names.update(p.relative_to(ROOT).as_posix() for p in directory.rglob("*") if p.is_file())
    tracked = subprocess.check_output(
        ["git", "--no-optional-locks", "ls-files", "-z"], cwd=WORKTREE, timeout=15
    ).decode().split("\0")
    for name in tracked:
        if name:
            path = WORKTREE / name
            if not path.resolve().is_relative_to(HERE):
                names.add(path.relative_to(ROOT).as_posix())
    return expected, sorted(names)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("snapshot", "check"))
    args = parser.parse_args()
    destination = HERE / "preservation-before.json"
    deadline = time.monotonic() + 90
    if args.mode == "snapshot":
        if destination.exists():
            raise FileExistsError(destination)
        expected, names = inventory()
        hashes = {name: digest(ROOT / name, deadline) for name in names}
        previous = [name for name, value in expected.items() if hashes[name] != value]
        data = {"workspace": str(ROOT), "files": hashes,
                "preexisting_frozen_manifest_mismatches": previous,
                "external_baseline_executable": "not accessed; outside authorized scope"}
        with destination.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
        print(f"SNAPSHOT {len(hashes)} files")
        print("PREEXISTING_FROZEN_MISMATCHES " + json.dumps(previous))
    else:
        data = json.loads(destination.read_text(encoding="utf-8"))
        if Path(data["workspace"]).resolve() != ROOT:
            raise ValueError("Snapshot workspace differs")
        changed = []
        for name, expected in data["files"].items():
            path = ROOT / name
            if not path.is_file() or digest(path, deadline) != expected:
                changed.append(name)
        _, names = inventory()
        added = sorted(set(names) - set(data["files"]))
        if changed or added:
            raise SystemExit("PRESERVATION FAILED " + json.dumps({"changed_or_missing": changed, "new_inventory_files": added}))
        print(f"PRESERVED {len(data['files'])} files against pre-control snapshot")
        print("PREEXISTING_FROZEN_MISMATCHES " + json.dumps(data["preexisting_frozen_manifest_mismatches"]))


if __name__ == "__main__":
    main()
