"""preserve.py: sha256 of every new file + frozen-tree check against git.

Each test builds a throw-away git repository, so the real repository is never
touched.
"""
import json
import os
import subprocess
import unittest

from tests import _helpers as h

SCRIPT = h.EXP / "preserve.py"
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + list(args), env=ENV,
                          capture_output=True, text=True, check=True).stdout


def preserve(repo, *args):
    return subprocess.run(
        ["python3", "-B", str(SCRIPT), "--repo", str(repo)] + list(args),
        capture_output=True, text=True)


@h.skip_unless_tool("git")
class Preserve(unittest.TestCase):
    def setUp(self):
        self._tmp = h.tmpdir()
        self.repo = h.Path(self._tmp.name) / "repo"
        for rel, text in (("workloads/victim.c", "v\n"), ("configs/run.py", "c\n"),
                          ("gem5_ext/a.cc", "g\n"), ("analysis/a.py", "a\n"),
                          ("scripts/s.sh", "s\n"), ("results/r/probes.bin", "r\n"),
                          ("README.md", "top\n")):
            self.write(rel, text)
        subprocess.run(["git", "init", "-q", str(self.repo)], env=ENV, check=True)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        self.base = git(self.repo, "rev-parse", "HEAD").strip()
        self.write("experiments/aes-leakage/new.c", "new\n")
        self.write("experiments/aes-leakage/sub/data.txt", "data\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "experiment")
        self.manifest = self.repo / "experiments/aes-leakage/preservation.json"

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def capture(self):
        proc = preserve(self.repo, "capture", "--base", self.base)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return json.loads(self.manifest.read_text())

    def verify(self):
        return preserve(self.repo, "verify", "--base", self.base)

    def test_capture_records_sha256_of_every_new_file(self):
        data = self.capture()
        self.assertEqual(sorted(data["files"]), ["new.c", "sub/data.txt"])
        import hashlib
        self.assertEqual(data["files"]["new.c"],
                         hashlib.sha256(b"new\n").hexdigest())
        self.assertEqual(data["base"], self.base)

    def test_capture_ignores_caches_and_the_manifest_itself(self):
        self.write("experiments/aes-leakage/__pycache__/x.pyc", "z")
        self.capture()
        self.capture()                 # second capture must not list the manifest
        data = json.loads(self.manifest.read_text())
        self.assertEqual(sorted(data["files"]), ["new.c", "sub/data.txt"])

    def test_verify_passes_on_a_clean_state(self):
        self.capture()
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "manifest")
        proc = self.verify()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("PRESERVED", proc.stdout)

    def test_modified_new_file_is_reported(self):
        self.capture()
        self.write("experiments/aes-leakage/new.c", "changed\n")
        proc = self.verify()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("new.c", proc.stdout)

    def test_unexpected_and_missing_files_are_reported(self):
        self.capture()
        self.write("experiments/aes-leakage/extra.c", "x\n")
        (self.repo / "experiments/aes-leakage/new.c").unlink()
        proc = self.verify()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("extra.c", proc.stdout)
        self.assertIn("new.c", proc.stdout)

    def test_uncommitted_change_in_a_frozen_tree_fails(self):
        self.capture()
        self.write("workloads/victim.c", "edited\n")
        proc = self.verify()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("workloads", proc.stdout)

    def test_committed_change_in_a_frozen_tree_fails_via_the_base_diff(self):
        self.write("results/r/probes.bin", "edited\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "oops")
        self.capture()
        proc = self.verify()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("results", proc.stdout)

    def test_committed_change_anywhere_outside_the_experiment_fails(self):
        self.write("README.md", "edited\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "oops")
        self.capture()
        proc = self.verify()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("README.md", proc.stdout)

    def test_untracked_file_outside_the_experiment_fails(self):
        self.capture()
        self.write("stray.txt", "x\n")
        proc = self.verify()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("stray.txt", proc.stdout)

    def test_verify_without_a_manifest_fails_clearly(self):
        proc = self.verify()
        self.assertEqual(proc.returncode, 2)
        self.assertIn("preservation.json", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
