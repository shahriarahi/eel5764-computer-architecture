"""Read-only fingerprints for the response-queue defense experiment."""

import hashlib
import argparse
import json
from pathlib import Path


EXCLUDED_PARTS = {".git", "tdma-rga", "tdma-rgq", "tdma-rda", "tdma-rdq",
                  "respq-defense-20261018"}


def snapshot(root: Path) -> dict[str, str]:
    values = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and not any(part in EXCLUDED_PARTS for part in relative.parts):
            values[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def write_snapshot(path: Path, root: Path, values: dict[str, str]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump({"root": str(root.resolve()), "files": values}, stream, indent=2)
        stream.write("\n")


def check(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    root = Path(data["root"])
    current = snapshot(root)
    changed = sorted(name for name, digest in data["files"].items()
                     if current.get(name) != digest)
    added = sorted(set(current) - set(data["files"]))
    if changed or added:
        raise ValueError(f"preservation mismatch changed={changed} added={added}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("snapshot", "check"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "snapshot":
        values = snapshot(args.root.resolve())
        write_snapshot(args.manifest, args.root, values)
        print(f"SNAPSHOT {len(values)} files")
    else:
        check(args.manifest)
        print("PRESERVATION PASS")


if __name__ == "__main__":
    main()

