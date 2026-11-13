import gzip
import tempfile
import unittest
from pathlib import Path

from gates import tdma_counter_gate


def write_stats(case: Path, lines: list[str]) -> None:
    case.mkdir()
    with gzip.open(case / "stats.txt.gz", "wt") as stream:
        stream.write("simTicks 10\n" + "".join(line + "\n" for line in lines))


GOOD = [
    "system.l2bus.tdmaReadGrants 7 # grants",
    "system.l2bus.tdmaOverruns 0 # overruns",
    "system.l2bus.tdmaDownstreamRefusals 0 # refusals",
    "system.l2bus.tdmaExpressBypasses 0 # bypasses",
]


class CounterGateTests(unittest.TestCase):
    def check(self, reference: list[str], candidate: list[str]) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_stats(root / "reference", reference)
            write_stats(root / "candidate", candidate)
            return tdma_counter_gate(root / "reference", root / "candidate")

    def test_accepts_identical_zero_violation_counters(self) -> None:
        result = self.check(GOOD, GOOD)
        self.assertEqual(result["tdma_lines"], 4)

    def test_rejects_changed_counter(self) -> None:
        changed = GOOD[:]
        changed[0] = "system.l2bus.tdmaReadGrants 8 # grants"
        with self.assertRaisesRegex(ValueError, "differ"):
            self.check(GOOD, changed)

    def test_rejects_nonzero_violation_even_if_reference_matches(self) -> None:
        bad = GOOD[:]
        bad[1] = "system.l2bus.tdmaOverruns 1 # overruns"
        with self.assertRaisesRegex(ValueError, "tdmaOverruns"):
            self.check(bad, bad)

    def test_rejects_missing_counters(self) -> None:
        with self.assertRaisesRegex(ValueError, "no tdma"):
            self.check([], [])


if __name__ == "__main__":
    unittest.main()
