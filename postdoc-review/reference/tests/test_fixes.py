"""Two small fixes (see progress.md, Phase E preparation):

* the analysis must survive a probe log in which every set is constant, the
  expected outcome of a partitioned or defended arm;
* preserve.py must not pin assistant-session state under `.claude/`.
"""
import json
import os
import subprocess
import unittest

from tests import _helpers as h

SCRIPT = h.EXP / "preserve.py"
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")


class FlatProbeLog(unittest.TestCase):
    def analyse_flat(self, **kwargs):
        a = h.load_analysis()
        with h.tmpdir() as tmp:
            run_dir = h.Path(tmp) / "flat"
            a.synth_run(run_dir, n=300, rounds1=False, delta=0.0, noise=0.0,
                        **kwargs)
            return a, a.analyze_run_dir(run_dir, nperm=2)

    def test_flat_unpartitioned_log_is_analysed_and_supports_nothing(self):
        a, res = self.analyse_flat()
        self.assertTrue(res["run_checks"]["all_passed"])
        for name in ("round1_plaintext_plus_key", "round1_plaintext_only",
                     "lastround_c_xor_k10", "lastround_ciphertext_only"):
            self.assertFalse(res["decision"][name], name)
        for hyp in a.HYPOTHESES:
            self.assertEqual(res["attribution"][hyp]["bytes_significant"], 0)
        for row in res["detection"].values():
            self.assertEqual(row["bytes_significant"], 0)

    def test_flat_partitioned_log_also_passes_the_isolation_check(self):
        a, res = self.analyse_flat(split="8-8", ways=8)
        names = {c["name"]: c["ok"] for c in res["run_checks"]["checks"]}
        self.assertTrue(names["way_isolation"])
        self.assertIn("RUN CHECKS", "RUN CHECKS")      # rendering must not fail
        self.assertIn("Decision", a.render_markdown(res))


@h.skip_unless_tool("git")
class PreserveIgnoresSessionState(unittest.TestCase):
    def setUp(self):
        self._tmp = h.tmpdir()
        self.repo = h.Path(self._tmp.name) / "repo"
        self.exp = self.repo / "experiments" / "aes-leakage"
        self.write("README.md", "top\n")
        subprocess.run(["git", "init", "-q", str(self.repo)], env=ENV, check=True)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.write("experiments/aes-leakage/data.txt", "data\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "experiment")
        (self.repo / ".git" / "info" / "exclude").write_text(".claude/\n")
        self.write("experiments/aes-leakage/.claude/state.json", "{}\n")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo)] + list(args),
                              env=ENV, capture_output=True, text=True,
                              check=True).stdout

    def write(self, rel, text):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def preserve(self, *args):
        return subprocess.run(
            ["python3", "-B", str(SCRIPT), "--repo", str(self.repo)] + list(args),
            capture_output=True, text=True)

    def test_session_state_is_not_pinned_and_may_change(self):
        proc = self.preserve("capture", "--base", self.base)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        files = json.loads((self.exp / "preservation.json").read_text())["files"]
        self.assertIn("data.txt", files)
        self.assertFalse([f for f in files if ".claude" in f], files)
        self.write("experiments/aes-leakage/.claude/state.json", '{"n": 2}\n')
        proc = self.preserve("verify")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_a_real_file_change_is_still_caught(self):
        self.preserve("capture", "--base", self.base)
        self.write("experiments/aes-leakage/data.txt", "changed\n")
        proc = self.preserve("verify")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("data.txt", proc.stdout)


if __name__ == "__main__":
    unittest.main()
