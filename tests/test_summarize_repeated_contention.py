import unittest

from analysis.summarize_repeated_contention import (
    fisher_combined_p,
    holm_adjust,
    percent_cost,
    stable_collapse_point,
)


class RepeatedStatisticsTests(unittest.TestCase):
    def test_fisher_combines_three_independent_p_values(self) -> None:
        self.assertAlmostEqual(
            fisher_combined_p([0.01, 0.02, 0.03]),
            0.000511854277,
            places=10,
        )

    def test_fisher_rejects_invalid_p_values(self) -> None:
        for values in ([], [0.0], [1.1]):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    fisher_combined_p(values)

    def test_holm_adjustment_is_monotone_in_sorted_order(self) -> None:
        adjusted = holm_adjust({"a": 0.001, "b": 0.01, "c": 0.04})

        self.assertAlmostEqual(adjusted["a"], 0.003)
        self.assertAlmostEqual(adjusted["b"], 0.02)
        self.assertAlmostEqual(adjusted["c"], 0.04)

    def test_stable_collapse_requires_all_larger_allocations_suppressed(self) -> None:
        rows = [
            {"split": "1-15", "control_valid": True, "distinguishable": False},
            {"split": "2-14", "control_valid": True, "distinguishable": False},
            {"split": "3-13", "control_valid": True, "distinguishable": True},
        ]
        self.assertIsNone(stable_collapse_point(rows))

        rows[2]["distinguishable"] = False
        self.assertEqual(stable_collapse_point(rows), "1-15")

    def test_invalid_control_prevents_a_collapse_claim(self) -> None:
        rows = [
            {"split": "1-15", "control_valid": True, "distinguishable": False},
            {"split": "2-14", "control_valid": False, "distinguishable": False},
        ]
        self.assertIsNone(stable_collapse_point(rows))

    def test_cost_direction_depends_on_whether_higher_is_better(self) -> None:
        self.assertAlmostEqual(percent_cost(10.0, 9.0, higher_is_better=True), 10.0)
        self.assertAlmostEqual(percent_cost(10.0, 11.0, higher_is_better=False), 10.0)


if __name__ == "__main__":
    unittest.main()
