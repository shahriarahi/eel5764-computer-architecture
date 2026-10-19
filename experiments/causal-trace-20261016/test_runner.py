import json
import tempfile
import unittest
from pathlib import Path

from preserve import check, snapshot, write_snapshot
from run_cases import (
    DISABLED_ROOT, ENABLED_ROOT, build_command, monitored_range, require_new,
    temporary_case_name,
)
from validate_trace import validate_equivalence


class RunnerTests(unittest.TestCase):
    def test_root_names_preserve_reference_length(self) -> None:
        self.assertEqual((len(DISABLED_ROOT), len(ENABLED_ROOT)), (8, 8))

    def test_refuses_existing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError):
                require_new(Path(directory))

    def test_staging_name_matches_reference_probe_argument_length(self) -> None:
        # References ran inside ".<case>.tmp.XXXXXX" staging directories.
        root = Path("/mnt/c/project/results/updated run")
        for name in ("1-15", "8-8"):
            reference = root / "tdma-onx/seed-5764a5e5" / f".{name}.tmp.J72AuC" / "probes.bin"
            parent = root / "tdma-cd1/seed-5764a5e5"
            staging = temporary_case_name(parent, len(str(reference)))
            self.assertEqual(len(str(parent / staging / "probes.bin")), len(str(reference)))
            self.assertNotEqual(staging, name)

    def test_staging_name_rejects_unreachable_length(self) -> None:
        with self.assertRaisesRegex(ValueError, "probe argument length"):
            temporary_case_name(Path("/a/long/parent/directory"), 10)

    def test_new_roots_avoid_the_aborted_attempt(self) -> None:
        self.assertNotIn(DISABLED_ROOT, {"tdma-cd0", "tdma-ct0"})
        self.assertNotIn(ENABLED_ROOT, {"tdma-cd0", "tdma-ct0"})

    def test_builds_disabled_and_enabled_commands(self) -> None:
        reference = {"command": ["/old/gem5.opt", "-d", "/old/out",
                                  "/old/run_contention_tdma.py", "--baseline-root", "/project",
                                  "--tdma-slot-cycles", "4"],
                     "probe_argument_length": 25}
        disabled = build_command(reference, Path("/new/output"), False,
                                 Path("/new/gem5.opt"), Path("/new/adapter.py"),
                                 "cpu0.data", 0x1000, 0x2000)
        self.assertEqual(Path(disabled[0]), Path("/new/gem5.opt"))
        adapter_value = str(Path("/new/adapter.py"))
        self.assertIn(adapter_value, disabled)
        self.assertNotIn("--debug-flags=CausalTrace", disabled)
        enabled = build_command(reference, Path("/new/output"), True,
                                Path("/new/gem5.opt"), Path("/new/adapter.py"),
                                "cpu0.data", 0x1000, 0x2000)
        self.assertIn("--debug-flags=CausalTrace", enabled)
        self.assertIn("--causal-trace", enabled)
        self.assertLess(enabled.index(adapter_value), enabled.index("--causal-trace"))

    def test_reads_monitored_range_from_top_level_metadata(self) -> None:
        metadata = {
            "probe_vaddr_base": 0x12080,
            "probe_vaddr_size": 0x40000,
            "contention": {"start_cycle": 2_000_000},
        }
        self.assertEqual(monitored_range(metadata), (0x12080, 0x40000))

    def test_equivalence_rejects_probe_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in (("reference", b"a"), ("candidate", b"b")):
                case = root / name
                case.mkdir()
                (case / "probes.bin").write_bytes(data)
            with self.assertRaisesRegex(ValueError, "probe"):
                validate_equivalence(root / "reference", root / "candidate")

    def test_snapshot_detects_change_and_excludes_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "kept.txt").write_text("one")
            output = root / ENABLED_ROOT
            output.mkdir()
            (output / "trace.log").write_text("ignored")
            values = snapshot(root)
            self.assertEqual(list(values), ["kept.txt"])
            manifest = root / "snapshot.json"
            write_snapshot(manifest, root, values)
            (root / "kept.txt").write_text("two")
            with self.assertRaisesRegex(ValueError, "kept.txt"):
                check(manifest)


if __name__ == "__main__":
    unittest.main()
