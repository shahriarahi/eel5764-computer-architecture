import json
import tempfile
import unittest
from pathlib import Path

from preserve import check, snapshot, write_snapshot
from run_cases import (
    DISABLED_ROOT, ENABLED_ROOT, build_command, require_new,
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

    def test_staging_name_preserves_case_path_length(self) -> None:
        for name in ("1-15", "8-8"):
            staging = temporary_case_name(name)
            self.assertEqual(len(staging), len(name))
            self.assertNotEqual(staging, name)

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
