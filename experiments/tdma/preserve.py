"""Capture/verify original files without writing into the original study."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture", "verify"))
    parser.add_argument("root", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--gem5", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "capture":
        names = subprocess.check_output(["git", "ls-files", "-z"], cwd=args.root).decode().split("\0")
        files = {n: digest(args.root / n) for n in names if n}
        for path in (args.root / "results").rglob("*"):
            if path.is_file():
                files[str(path.relative_to(args.root))] = digest(path)
        data = {"root": str(args.root), "files": files,
                "gem5": str(args.gem5), "gem5_sha256": digest(args.gem5)}
        with args.manifest.open("x") as stream:
            json.dump(data, stream, indent=2)
        print(f"CAPTURED {len(files)} original files and baseline executable")
    else:
        data = json.loads(args.manifest.read_text())
        changed = [n for n, h in data["files"].items()
                   if not (args.root / n).is_file() or digest(args.root / n) != h]
        if digest(args.gem5) != data["gem5_sha256"]:
            changed.append("BASELINE GEM5 EXECUTABLE")
        if changed:
            raise SystemExit("PRESERVATION FAILED: " + repr(changed))
        print(f"PRESERVED {len(data['files'])} original files and baseline executable")


if __name__ == "__main__":
    main()
