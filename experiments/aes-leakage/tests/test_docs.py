"""The documentation must trace to files and executable facts.

These tests do not judge prose; they check that numbers, hashes, paths and
commands quoted in the docs match the files they cite, and that documented gem5
commands are accepted by the baseline configuration's own validators.
"""
import hashlib
import json
import re
import subprocess
import unittest

from tests import _helpers as h

BUILD_MD = h.EXP / "gem5_build.md"
README = h.EXP / "README.md"
PREREG = h.EXP / "PREREGISTRATION_DRAFT.md"
PROGRESS = h.EXP / "progress.md"
STORED_RUN = (h.REPO / "results" / "updated run" / "sweep-v3" /
              "seed-5764a5e5" / "UNPARTITIONED-A8")


def text(path):
    return path.read_text()


class AllDocsExist(unittest.TestCase):
    def test_deliverable_docs_exist(self):
        for path in (BUILD_MD, README, PREREG, PROGRESS):
            self.assertTrue(path.is_file(), path.name)


class BuildInstructions(unittest.TestCase):
    def test_contains_the_exact_commands_from_the_task(self):
        doc = text(BUILD_MD)
        self.assertIn("git -C ~/eel5764/gem5 worktree add ~/eel5764/gem5-leak "
                      "c8222cc67a399bfc01e8658dd14b30d5bfd634f9", doc)
        self.assertRegex(doc, r"scons build/RISCV/gem5\.opt -j\$\(nproc\) "
                              r"EXTRAS=\S+/gem5_ext")

    def test_extras_path_ends_in_gem5_ext_because_sources_include_it(self):
        for match in re.findall(r"EXTRAS=(\S+)", text(BUILD_MD)):
            self.assertTrue(match.endswith("/gem5_ext"), match)

    @unittest.skipUnless(STORED_RUN.is_dir(), "stored paper run not present")
    def test_guard_quotes_the_stored_probes_hash_and_command(self):
        doc = text(BUILD_MD)
        stored = hashlib.sha256((STORED_RUN / "probes.bin").read_bytes()).hexdigest()
        self.assertIn(stored, doc)
        cmd = text(STORED_RUN / "cmd.txt")
        flags = cmd.split("configs/run_contention.py", 1)[1].strip()
        self.assertIn(flags, doc, "guard must use the stored run's flags")

    @unittest.skipUnless(STORED_RUN.is_dir(), "stored paper run not present")
    def test_guard_output_path_length_matches_the_stored_run(self):
        # The monitor receives the probe path as an argument; a different path
        # length shifts its stack and breaks byte identity.
        config = text(STORED_RUN / "config.json")
        path = re.search(r'"(/[^"]*/probes\.bin)"', config).group(1)
        stored_dir_length = len(path) - len("/probes.bin")
        doc = text(BUILD_MD)
        self.assertIn("STORED_LEN=%d" % stored_dir_length, doc)
        block = re.search(r"```bash guard-outdir\n(.*?)```", doc, re.S).group(1)
        for home in ("/home/shahriarahi", "/home/someone", "/root"):
            proc = subprocess.run(
                ["bash", "-c", block + '\necho "${#OUT}"'], capture_output=True,
                text=True, env={"HOME": home, "PATH": "/usr/bin:/bin"})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(int(proc.stdout.strip().splitlines()[-1]),
                             stored_dir_length, home)

    def test_guard_runs_from_the_original_project_root_like_the_stored_run(self):
        doc = text(BUILD_MD)
        self.assertIn('cd "$R"', doc)
        self.assertIn("-r -e -d", doc)


class DocumentedGem5Commands(unittest.TestCase):
    """Every documented run_leakage.py command line must be acceptable to the
    baseline config's own validators (split sums to 16, monitor depth equals the
    monitor's allocation, variant exists)."""

    @classmethod
    def setUpClass(cls):
        cls.rl = h.load_module("rl_for_docs", h.EXP / "run_leakage.py")
        cls.baseline = cls.rl.load_baseline(h.REPO)

    def commands(self, path):
        joined = text(path).replace("\\\n", " ")
        return [line for line in joined.splitlines()
                if "run_leakage.py" in line and "--split" in line]

    def test_readme_and_preregistration_list_runnable_commands(self):
        total = 0
        for path in (README, PREREG):
            for line in self.commands(path):
                total += 1
                variant = re.search(r"--victim-variant (\S+)", line)
                split = re.search(r"--split (\S+)", line).group(1)
                ways = int(re.search(r"--monitor-ways (\d+)", line).group(1))
                self.assertIsNotNone(variant, line)
                self.assertIn(variant.group(1), self.rl.VARIANTS, line)
                parsed = self.baseline.parse_split(split)
                self.baseline.validate_monitor_ways(parsed, ways)
        self.assertGreaterEqual(total, 2)

    def test_gem5_commands_redirect_output_so_simout_exists(self):
        # run_leakage's analysis reads simout.txt, which only exists with -r -e
        for path in (README,):
            for line in self.commands(path):
                self.assertIn("-r -e", line)


class ReadmeFileTable(unittest.TestCase):
    def test_every_file_named_in_the_readme_table_exists(self):
        names = re.findall(r"^\| `([^`]+)` \|", text(README), re.M)
        self.assertGreater(len(names), 10)
        for name in names:
            target = name.rstrip("/")
            if any(ch in target for ch in "*<>"):
                continue
            self.assertTrue((h.EXP / target).exists(), name)

    def test_states_simulator_only_and_the_scope_decision(self):
        doc = text(README).lower()
        self.assertIn("simulator", doc)
        self.assertIn("public", doc)
        self.assertIn("beyond the accepted proposal", doc)
        self.assertIn("does not score key guesses", doc)


class Preregistration(unittest.TestCase):
    def test_run_table_rows_are_accepted_by_the_baseline_validators(self):
        rl = h.load_module("rl_for_prereg", h.EXP / "run_leakage.py")
        baseline = rl.load_baseline(h.REPO)
        rows = re.findall(
            r"^\| (P\d\w*(?:-[ct])?|T) \| [^|]+ \| (\S+) \| (\S+) \| (\d+) \| "
            r"(\d+) \| [^|]+ \|$", text(PREREG), re.M)
        self.assertGreaterEqual(len(rows), 10, "run table not found")
        for run_id, variant, split, ways, n_win, *_ in rows:
            self.assertIn(variant, rl.VARIANTS, run_id)
            baseline.validate_monitor_ways(baseline.parse_split(split), int(ways))
            self.assertTrue(1 <= int(n_win) <= 65535, run_id)

    def test_states_the_decision_rule_and_no_key_guessing(self):
        doc = text(PREREG)
        for phrase in ("Holm", "0.05", "does not score key guesses",
                       "beats", "matched", "DRAFT"):
            self.assertIn(phrase, doc, phrase)

    def test_seeds_are_given_in_hex_and_decimal_consistently(self):
        doc = text(PREREG)
        for value in (0x5764A5E5, 0x5764A5E6, 0x5764A5E7):
            self.assertIn(str(value), doc)
            self.assertIn("0x%X" % value, doc)

    def test_quoted_synthetic_table_exists_and_is_labelled_synthetic(self):
        self.assertIn("synthetic_power.md", text(PREREG))
        self.assertTrue((h.EXP / "synthetic_power.md").is_file())
        self.assertIn("synthetic", text(PREREG).lower())


class ProgressLedger(unittest.TestCase):
    def test_binary_hashes_in_the_ledger_match_the_committed_manifest(self):
        manifest = json.loads(
            (h.EXP / "build" / "n2000" / "build_manifest.json").read_text())
        doc = text(PROGRESS)
        for name, info in manifest["binaries"].items():
            self.assertIn(info["sha256"], doc, name)

    def test_names_every_phase(self):
        doc = text(PROGRESS)
        for phase in ("Phase A", "Phase B", "Phase C", "Phase D", "Phase E"):
            self.assertIn(phase, doc)


if __name__ == "__main__":
    unittest.main()
