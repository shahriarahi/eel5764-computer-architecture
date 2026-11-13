"""analysis/power_synth.py: synthetic power / false-positive tables.

These tables come from the synthetic generator, not from gem5.  They size N for
the preregistration and check that the decision rule stays quiet on data with
no data dependence.
"""
import unittest

from tests import _helpers as h


class PowerSynth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = h.load_module("power_synth_under_test",
                              h.EXP / "analysis" / "power_synth.py")

    def test_power_grid_rows_have_the_documented_columns(self):
        rows = self.p.power_grid(modes=("round1",), deltas=(40.0,), sizes=(300,),
                                 reps=2, noise=6.0)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for key in ("mode", "delta", "n", "reps", "mean_bytes_p_xor_k",
                    "mean_bytes_lastround", "frac_round1_supported",
                    "frac_lastround_supported"):
            self.assertIn(key, row)
        self.assertGreater(row["mean_bytes_p_xor_k"], 8)

    def test_false_positive_rate_on_data_without_dependence(self):
        row = self.p.false_positive_rate(rounds1=True, n=400, reps=4)
        self.assertEqual(row["reps"], 4)
        self.assertLessEqual(row["any_decision_true"], 1)

    def test_markdown_tables_render(self):
        rows = self.p.power_grid(modes=("round1",), deltas=(40.0,), sizes=(300,),
                                 reps=1, noise=6.0)
        text = self.p.render_markdown(rows, [self.p.false_positive_rate(
            rounds1=True, n=300, reps=2)])
        self.assertIn("| mode |", text)
        self.assertIn("synthetic", text.lower())


if __name__ == "__main__":
    unittest.main()
