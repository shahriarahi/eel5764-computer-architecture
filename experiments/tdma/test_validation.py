import unittest
from validate import scheduler_counters


class ValidationTests(unittest.TestCase):
    def test_missing_enabled_counter_cannot_look_like_zero(self) -> None:
        with self.assertRaises(ValueError):
            scheduler_counters([{"system.l2bus.tdmaGrants0": 1}], True)

    def test_disabled_original_binary_needs_no_new_counters(self) -> None:
        self.assertEqual(scheduler_counters([{}], False)["tdmaGrants0"], 0)


if __name__ == "__main__":
    unittest.main()
