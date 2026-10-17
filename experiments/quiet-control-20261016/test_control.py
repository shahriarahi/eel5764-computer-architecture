"""Validity gates for the separately scoped quiet-victim experiment."""
import unittest
from run_control import require_quiet


class QuietGateTests(unittest.TestCase):
    def blocks(self) -> list[dict[str, float]]:
        return [{"system.l2bus.tdmaGrants0": 1,
                 "system.l2bus.tdmaGrants1": 0,
                 "system.l2bus.tdmaOverruns": 0,
                 "system.l2bus.tdmaDownstreamRefusals": 0,
                 "system.l2bus.tdmaExpressBypasses": 0} for _ in range(64)]

    def test_accepts_quiet_intervals(self) -> None:
        require_quiet(self.blocks())

    def test_rejects_one_victim_grant(self) -> None:
        blocks = self.blocks()
        blocks[31]["system.l2bus.tdmaGrants1"] = 1
        with self.assertRaisesRegex(ValueError, "interval 31"):
            require_quiet(blocks)

    def test_rejects_incomplete_measurement(self) -> None:
        with self.assertRaisesRegex(ValueError, "64"):
            require_quiet(self.blocks()[:-1])

    def test_rejects_missing_counter(self) -> None:
        blocks = self.blocks()
        del blocks[0]["system.l2bus.tdmaGrants1"]
        with self.assertRaisesRegex(ValueError, "missing"):
            require_quiet(blocks)

    def test_rejects_violation(self) -> None:
        blocks = self.blocks()
        blocks[2]["system.l2bus.tdmaOverruns"] = 1
        with self.assertRaisesRegex(ValueError, "interval 2"):
            require_quiet(blocks)


if __name__ == "__main__":
    unittest.main()
