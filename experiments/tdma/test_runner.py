import tempfile
import unittest
from pathlib import Path
from run_pilot import build_plan, case_path, reserve_output


class RunnerTests(unittest.TestCase):
    def test_pilot_and_full_plan(self) -> None:
        self.assertEqual(len(build_plan((0x5764A5E5,))), 6)
        self.assertEqual(len(build_plan()), 18)
        self.assertEqual(len(set(build_plan())), 18)

    def test_root_and_case_path_lengths(self) -> None:
        for arm, seed, ways in build_plan():
            path = case_path(arm, seed, ways)
            self.assertEqual(len(path.parts[2]), len("sweep-v3"))
            self.assertEqual(path.name, f"UNPARTITIONED-A{ways}" if arm == "off" else f"{ways}-{16-ways}")

    def test_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "output"
            reserve_output(path)
            with self.assertRaises(FileExistsError):
                reserve_output(path)


if __name__ == "__main__":
    unittest.main()
