#!/usr/bin/env python3
"""Hash-pin the experiment's files and prove nothing else in the repository
changed.  Standard library only.

  preserve.py capture [--base REV]   write experiments/aes-leakage/preservation.json
  preserve.py verify  [--base REV]   check it

verify checks three things and exits 1 if any fails:
  1. every file under experiments/aes-leakage/ (except caches and the manifest
     itself) has the recorded sha256, and none was added or removed;
  2. the frozen trees (workloads, configs, gem5_ext, analysis, scripts,
     results) are unchanged: nothing differs in the working tree, and nothing
     was committed to them since the base revision;
  3. nothing outside experiments/aes-leakage/ changed at all, neither in the
     working tree nor in any commit since the base revision.
The base defaults to the merge-base with experiment/tdma-prototype (the branch
this work started from).  Comparing against the base, not only against HEAD,
matters: a frozen file that was edited and then committed would pass a plain
"unchanged against HEAD" test.

Run it with a git that can open this worktree (the worktree was created by
Windows git, so use Windows Python from Git Bash or PowerShell; WSL's git
cannot follow its .git file).
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FROZEN_TREES = ("workloads", "configs", "gem5_ext", "analysis", "scripts",
                "results")
MANIFEST_NAME = "preservation.json"
DEFAULT_BASE_BRANCH = "experiment/tdma-prototype"


class GitError(Exception):
    pass


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def list_files(exp_dir):
    """Relative posix paths of every file to pin."""
    files = []
    for path in sorted(Path(exp_dir).rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(exp_dir).as_posix()
        if rel == MANIFEST_NAME or rel.endswith(".pyc"):
            continue
        files.append(rel)
    return files


def git(repo, *args):
    proc = subprocess.run(["git", "-C", str(repo)] + list(args),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise GitError("git %s failed: %s" % (" ".join(args), proc.stderr.strip()))
    return proc.stdout


def resolve_base(repo, base):
    if base:
        return git(repo, "rev-parse", base).strip()
    return git(repo, "merge-base", "HEAD", DEFAULT_BASE_BRANCH).strip()


def committed_changes(repo, base, *paths):
    out = git(repo, "diff", "--name-only", "-z", base, "HEAD", *(["--"] + list(paths)
                                                                  if paths else []))
    return [p for p in out.split("\0") if p]


def working_changes(repo, *paths):
    """Paths with any working-tree or index change, incl. untracked files."""
    out = git(repo, "status", "--porcelain", "-z", "--untracked-files=all",
              *(["--"] + list(paths) if paths else []))
    entries, result, skip = out.split("\0"), [], False
    for entry in entries:
        if skip:                       # old path of a rename/copy
            skip = False
            continue
        if len(entry) > 3:
            result.append(entry[3:])
            skip = entry[0] in "RC"
    return result


def capture(repo, exp_dir, base):
    files = {rel: sha256_of(exp_dir / rel) for rel in list_files(exp_dir)}
    data = {"format": "aes-leakage-preservation-v1", "base": base,
            "exp_dir": exp_dir.relative_to(repo).as_posix(), "files": files}
    (exp_dir / MANIFEST_NAME).write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n")
    print("CAPTURED %d files (base %s)" % (len(files), base[:10]))


def verify(repo, exp_dir, base_override):
    manifest = exp_dir / MANIFEST_NAME
    if not manifest.is_file():
        print("%s is missing; run `preserve.py capture` first" % MANIFEST_NAME)
        return 2
    data = json.loads(manifest.read_text())
    base = resolve_base(repo, base_override) if base_override else data["base"]
    problems = []

    current = set(list_files(exp_dir))
    recorded = data["files"]
    for rel in sorted(set(recorded) - current):
        problems.append("missing file: %s" % rel)
    for rel in sorted(current - set(recorded)):
        problems.append("unexpected file (not in manifest): %s" % rel)
    for rel in sorted(current & set(recorded)):
        if sha256_of(exp_dir / rel) != recorded[rel]:
            problems.append("changed file (sha256 differs): %s" % rel)

    prefix = exp_dir.relative_to(repo).as_posix() + "/"
    for tree in FROZEN_TREES:
        for path in working_changes(repo, tree):
            problems.append("frozen tree %s: uncommitted change: %s" % (tree, path))
        for path in committed_changes(repo, base, tree):
            problems.append("frozen tree %s: committed change since base: %s" %
                            (tree, path))
    for path in committed_changes(repo, base):
        if not path.startswith(prefix):
            problems.append("outside %s: committed change since base: %s" %
                            (prefix, path))
    for path in working_changes(repo):
        if not path.startswith(prefix):
            problems.append("outside %s: uncommitted change: %s" % (prefix, path))

    if problems:
        print("PRESERVATION FAILED:")
        for line in problems:
            print("  " + line)
        return 1
    print("PRESERVED: %d files hash-match; frozen trees and everything outside "
          "%s unchanged since %s" % (len(recorded), prefix, base[:10]))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("capture", "verify"))
    parser.add_argument("--repo", type=Path, default=HERE.parents[1])
    parser.add_argument("--exp-dir", type=Path)
    parser.add_argument("--base", help="base revision (default: merge-base "
                                       "with %s)" % DEFAULT_BASE_BRANCH)
    args = parser.parse_args()
    repo = args.repo.resolve()
    exp_dir = (args.exp_dir or repo / "experiments" / "aes-leakage").resolve()
    try:
        if args.mode == "capture":
            capture(repo, exp_dir, resolve_base(repo, args.base))
            return 0
        return verify(repo, exp_dir, args.base)
    except GitError as exc:
        print("ERROR: %s\n(run preserve.py with a git that can open this "
              "worktree)" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
