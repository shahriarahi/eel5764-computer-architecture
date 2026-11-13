"""leak_followup.py: differential test, raw-cycle effect size, collision-count
test.  Synthetic run directories give known answers; three tests read the
stored real runs (P0 attempt 2 and its repeat, and P1) without changing them.
"""
import json
import shutil
import unittest

import numpy as np

from tests import _helpers as h

RUNS = h.EXP / "runs"
P0B, P0C, P1 = (RUNS / "p0b-r1-scrub-n20", RUNS / "p0c-r1-scrub-n20",
                RUNS / "p1-r1-scrub-n2000")


def followup():
    return h.load_module("leak_followup_under_test",
                         h.EXP / "analysis" / "leak_followup.py")


def complete(run_dir, a, seed, probe_dir_name="run-x"):
    """synth_run() writes no binaries block and no config.json; add both."""
    cfg_path = run_dir / "leak_config.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["binaries"] = {"victim": {"name": "v", "sha256": "aa"},
                       "monitor": {"name": "m", "sha256": "bb"}}
    cfg["build_dir"] = "build/n-test"
    cfg_path.write_text(json.dumps(cfg))
    (run_dir / "config.json").write_text(json.dumps(
        {"cmd": ["monitor_leak", "16", "/x/%s/probes.bin" % probe_dir_name]}))


def synth(tmp, name, seed, n=300, rounds1=True, **kw):
    a = h.load_analysis()
    run_dir = h.Path(tmp) / name
    a.synth_run(run_dir, seed=seed, n=n, rounds1=rounds1, **kw)
    complete(run_dir, a, seed)
    return run_dir


class Diff(unittest.TestCase):
    def test_identical_logs_for_two_seeds_are_reported_identical(self):
        f = followup()
        with h.tmpdir() as tmp:
            a = synth(tmp, "a", 0x5764A5E5, delta=0.0, noise=0.0)
            b = synth(tmp, "b", 0x5764A5E6, delta=0.0, noise=0.0)
            res = f.diff_runs(a, b)
            self.assertTrue(res["preconditions_ok"], res["problems"])
            self.assertTrue(res["victim_inputs_differ"])
            self.assertEqual(res["verdict"], "IDENTICAL")
            self.assertEqual(res["latency_records_differing"], 0)

    def test_data_dependent_logs_are_reported_different(self):
        f = followup()
        with h.tmpdir() as tmp:
            a = synth(tmp, "a", 0x5764A5E5, delta=40.0, noise=0.0)
            b = synth(tmp, "b", 0x5764A5E6, delta=40.0, noise=0.0)
            res = f.diff_runs(a, b)
            self.assertEqual(res["verdict"], "DIFFERENT")
            self.assertGreater(res["latency_records_differing"], 0)
            self.assertEqual(res["max_abs_latency_difference"], 40)

    def test_same_seed_is_refused_unless_it_is_a_guard(self):
        f = followup()
        with h.tmpdir() as tmp:
            a = synth(tmp, "a", 7, delta=0.0, noise=0.0)
            b = synth(tmp, "b", 7, delta=0.0, noise=0.0)
            self.assertEqual(f.diff_runs(a, b)["verdict"], "INVALID")
            self.assertEqual(f.diff_runs(a, b, allow_same_seed=True)["verdict"],
                             "IDENTICAL")

    def test_mismatched_arms_and_path_lengths_are_refused(self):
        f = followup()
        with h.tmpdir() as tmp:
            a = synth(tmp, "a", 0x5764A5E5, delta=0.0, noise=0.0)
            b = synth(tmp, "b", 0x5764A5E6, delta=0.0, noise=0.0, split="8-8",
                      ways=8)
            res = f.diff_runs(a, b)
            self.assertEqual(res["verdict"], "INVALID")
            self.assertTrue(any("split differs" in p for p in res["problems"]))
            c = synth(tmp, "c", 0x5764A5E6, delta=0.0, noise=0.0)
            (c / "config.json").write_text(json.dumps(
                {"cmd": ["m", "16", "/x/a-longer-name/probes.bin"]}))
            res = f.diff_runs(a, c)
            self.assertTrue(any("probe path lengths" in p
                                for p in res["problems"]))

    def test_cli_exit_status_and_verdict_line(self):
        f = followup()
        with h.tmpdir() as tmp:
            a = synth(tmp, "a", 0x5764A5E5, delta=0.0, noise=0.0)
            b = synth(tmp, "b", 0x5764A5E6, delta=0.0, noise=0.0)
            out = h.Path(tmp) / "d.json"
            proc = h.run(["python3", "-B", h.EXP / "analysis" / "leak_followup.py",
                          "diff", "--a", a, "--b", b, "--out-json", out])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("DIFF VERDICT: IDENTICAL", proc.stdout)
            self.assertEqual(json.loads(out.read_text())["verdict"], "IDENTICAL")
            proc = h.run(["python3", "-B", h.EXP / "analysis" / "leak_followup.py",
                          "diff", "--a", a, "--b", a])
            self.assertEqual(proc.returncode, 2)

    @unittest.skipUnless(P0B.is_dir() and P0C.is_dir(), "stored P0 runs absent")
    def test_stored_p0_repeat_is_byte_identical(self):
        res = followup().diff_runs(P0B, P0C, allow_same_seed=True)
        self.assertTrue(res["preconditions_ok"], res["problems"])
        self.assertEqual(res["verdict"], "IDENTICAL")


class Effect(unittest.TestCase):
    def test_effect_is_in_cycles_and_scales_with_the_leak(self):
        f = followup()
        with h.tmpdir() as tmp:
            small = f.effect_run(synth(tmp, "s", 1, delta=1.0, noise=0.0),
                                 nperm=2000)
            big = f.effect_run(synth(tmp, "b", 1, delta=100.0, noise=0.0),
                               nperm=2000)
            es = small["hypotheses"]["p_xor_k"]["mean_effect_cycles_per_set_walk"]
            eb = big["hypotheses"]["p_xor_k"]["mean_effect_cycles_per_set_walk"]
            self.assertAlmostEqual(eb / es, 100.0, delta=1.0)
            self.assertGreater(es, 0.5)
            self.assertLess(es, 1.0)
            self.assertTrue(big["decision"]["round1_plaintext_plus_key"])
            self.assertFalse(big["decision"]["round1_plaintext_only"])
            self.assertEqual(big["hypotheses"]["shuffled"]["bytes_significant"], 0)

    def test_an_immaterial_effect_is_significant_but_not_supported(self):
        # 16 probed lines per walk and a 0.2-cycle rise: 0.0125 cycles per
        # probed line, below the 0.02 margin.  The registered z would call it.
        f = followup()
        with h.tmpdir() as tmp:
            run_dir = synth(tmp, "tiny", 1, n=600, delta=1.0, noise=0.0,
                            visibility=0.24)
            res = f.effect_run(run_dir, nperm=2000)
            v = res["hypotheses"]["p_xor_k"]
            self.assertLess(v["mean_effect_cycles_per_probed_line"], 0.02)
            self.assertGreater(v["bytes_significant"], 0)
            self.assertEqual(v["bytes_significant_and_material"], 0)
            self.assertFalse(res["decision"]["round1_plaintext_plus_key"])

    def test_no_data_dependence_supports_nothing(self):
        f = followup()
        with h.tmpdir() as tmp:
            res = f.effect_run(synth(tmp, "none", 3, leak="none", delta=40.0,
                                     noise=6.0), nperm=2000)
            self.assertFalse(any(res["decision"].values()))

    def test_confusion_table_of_a_noise_free_leak_is_exact(self):
        f = followup()
        with h.tmpdir() as tmp:
            res = f.effect_run(synth(tmp, "exact", 1, delta=2642.0, noise=0.0),
                               nperm=2000)
            c = res["confusion"]
            self.assertTrue(c["exact_indicator"])
            self.assertEqual(c["touched_fast"] + c["untouched_slow"], 0)

    def test_retained_fraction_against_a_reference_run(self):
        f = followup()
        with h.tmpdir() as tmp:
            ref = synth(tmp, "ref", 1, delta=100.0, noise=0.0)
            half = synth(tmp, "half", 1, delta=50.0, noise=0.0)
            res = f.effect_run(half, nperm=2000, reference=ref)
            frac = res["retained"]["values"]["p_xor_k"]["fraction_retained"]
            self.assertAlmostEqual(frac, 0.5, delta=0.01)

    def test_too_few_shuffles_for_the_holm_family_is_refused(self):
        # 200 shuffles give p >= 1/201; times 96 tests that can never be < 0.05
        f = followup()
        with h.tmpdir() as tmp:
            run_dir = synth(tmp, "few", 1, delta=40.0, noise=0.0)
            with self.assertRaisesRegex(f.FollowupError, "too small"):
                f.effect_run(run_dir, nperm=200)
            with self.assertRaisesRegex(f.FollowupError, "too small"):
                f.count_run(run_dir, nperm=100)

    @unittest.skipUnless(P1.is_dir(), "stored P1 run absent")
    def test_stored_p1_effect_and_exact_indicator(self):
        res = followup().effect_run(P1, nperm=2000)
        v = res["hypotheses"]["p_xor_k"]
        self.assertAlmostEqual(v["mean_effect_cycles_per_set_walk"], 2176.7,
                               delta=1.0)
        self.assertEqual(v["bytes_significant"], 16)
        self.assertEqual(res["hypotheses"]["p_only"]["bytes_significant"], 0)
        self.assertTrue(res["confusion"]["exact_indicator"])
        self.assertEqual(res["confusion"]["cells"], 136000)
        self.assertTrue(res["decision"]["round1_plaintext_plus_key"])


class Count(unittest.TestCase):
    def contention_run(self, tmp, name, p_hit, rounds1, follow_count=True,
                       n=1500):
        """A synthetic overlap arm: flat 257-cycle walks; each distinct table
        line of the encryption delays one walk by 4 cycles with probability
        p_hit, on a set that does NOT depend on the line's address."""
        f = followup()
        a = h.load_analysis()
        run_dir = synth(tmp, name, 0x5764A5E5, n=n, rounds1=rounds1, delta=0.0,
                        noise=0.0, schedule={"OFF_PROBE": 520192})
        run = f.load_run(run_dir, need_line_map=False)
        counts = f.distinct_line_counts(run)["lines_all_rounds"].astype(int)
        rng = np.random.default_rng(9)
        if not follow_count:
            counts = rng.permutation(counts)
        X = np.full((n, a.NSETS), 257, dtype="<u4")
        for w in range(n):
            hits = rng.random(counts[w]) < p_hit
            sets = rng.integers(0, a.NSETS, size=int(hits.sum()))
            np.add.at(X[w], sets, 4)
        rec = np.frombuffer((run_dir / "probes.bin").read_bytes(),
                            dtype=a.PROBE_DTYPE).copy()
        rec["latency"] = X.reshape(-1)
        rec.tofile(run_dir / "probes.bin")
        return run_dir

    def test_round1_victim_separates_key_dependent_from_key_free_count(self):
        f = followup()
        with h.tmpdir() as tmp:
            res = f.count_run(self.contention_run(tmp, "r1", 1.0, True),
                              nperm=1000)
            self.assertTrue(res["overlap_schedule"])
            self.assertTrue(res["round1_statements_registered"])
            self.assertTrue(res["decision"]["count_dependent"])
            self.assertTrue(res["decision"]["round1_count_plaintext_plus_key"])
            self.assertFalse(res["decision"]["round1_count_plaintext_only"])

    def test_round1_victim_with_a_30_percent_hit_rate_is_still_detected(self):
        f = followup()
        with h.tmpdir() as tmp:
            res = f.count_run(self.contention_run(tmp, "p30", 0.3, True, n=2000),
                              nperm=2000)
            self.assertTrue(res["decision"]["count_dependent"])
            self.assertTrue(res["decision"]["round1_count_plaintext_plus_key"])

    def test_full_aes_count_dependence_is_detected(self):
        f = followup()
        with h.tmpdir() as tmp:
            res = f.count_run(self.contention_run(tmp, "full", 1.0, False),
                              nperm=1000)
            self.assertTrue(res["decision"]["count_dependent"])
            self.assertFalse(res["round1_statements_registered"])
            self.assertIn("low-power", f.render_count(res))

    def test_count_independent_delay_is_not_attributed(self):
        f = followup()
        with h.tmpdir() as tmp:
            res = f.count_run(self.contention_run(tmp, "i", 1.0, True,
                                                  follow_count=False),
                              nperm=1000)
            self.assertFalse(res["decision"]["count_dependent"])
            self.assertFalse(res["decision"]["round1_count_plaintext_plus_key"])

    def test_the_registered_location_aware_rule_misses_this_channel(self):
        # Why the count test exists: the same data give 0/16 with the
        # registered attribution, because the delay is not at the line's set.
        a = h.load_analysis()
        with h.tmpdir() as tmp:
            run_dir = self.contention_run(tmp, "blind", 1.0, True)
            res = a.analyze_run_dir(run_dir)
            self.assertEqual(res["attribution"]["p_xor_k"]["bytes_significant"], 0)
            self.assertFalse(res["decision"]["round1_plaintext_plus_key"])

    def test_a_flat_log_gives_no_statement_and_does_not_crash(self):
        f = followup()
        with h.tmpdir() as tmp:
            res = f.count_run(synth(tmp, "flat", 1, rounds1=False, delta=0.0,
                                    noise=0.0), nperm=200)
            self.assertFalse(any(res["decision"].values()))
            self.assertFalse(res["overlap_schedule"])


if __name__ == "__main__":
    unittest.main()
