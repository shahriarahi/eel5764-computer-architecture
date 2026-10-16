import gzip
from pathlib import Path
import tempfile
import unittest
from summarize import numeric_blocks, security_statistics


class SummaryTests(unittest.TestCase):
    def test_constant_latency_is_reported_without_inventing_p_values(self) -> None:
        project = Path(__file__).resolve().parents[4]
        result = security_statistics(project, [[10.0] * 256 for _ in range(64)], [0, 1] * 32, 1)
        self.assertIn("max_set_error", result)
        self.assertIn("hit_only_error", result)
        self.assertNotIn("max_set", result)
        self.assertNotIn("hit_only", result)

    def test_keeps_interval_blocks_separate_from_final_dump(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "stats.txt.gz"
            with gzip.open(path, "wt") as stream:
                for value in (10, 20, 999):
                    stream.write("---------- Begin Simulation Statistics ----------\n")
                    stream.write(f"system.cpu0.numCycles {value} # comment\n")
                    stream.write("---------- End Simulation Statistics ----------\n")
            blocks = numeric_blocks(path)
            self.assertEqual([block["system.cpu0.numCycles"] for block in blocks], [10, 20, 999])
            self.assertEqual(sum(b["system.cpu0.numCycles"] for b in blocks[:-1]), 30)


if __name__ == "__main__":
    unittest.main()
