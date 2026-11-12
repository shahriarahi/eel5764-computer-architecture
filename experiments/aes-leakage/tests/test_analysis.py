"""analysis/aes_leak_analysis.py: run-dir reader, models, ground truth, synth.

Synthetic run directories have known answers, so every claim the analysis
makes can be checked end to end without gem5.  The synthetic generator is a
rehearsal tool, NOT a model of gem5: nothing here is a leakage result.
"""
import json
import subprocess
import sys
import unittest

import numpy as np

from tests import _helpers as h

KEY = "f1e2d3c4b5a69788796a5b4c3d2e1f10"
SEED = 0x5764A5E5
PREFIX = "system.llc.partitioning_manager."


def make_run(analysis, tmp, **kwargs):
    params = dict(key_hex=KEY, seed=SEED, n=1500, rounds1=True, leak="key",
                  delta=40.0, noise=6.0, visibility=1.0, rng_seed=1)
    params.update(kwargs)
    run_dir = h.Path(tmp) / "run"
    info = analysis.synth_run(run_dir, **params)
    return run_dir, info


class StatsParsing(unittest.TestCase):
    TEXT = """---------- Begin Simulation Statistics ----------
simSeconds                                   0.010000                       # x
system.llc.partitioning_manager.probeSetRotation           5       # rot
system.llc.partitioning_manager.victimTableLineSetPlusOne::0     11  # v
system.llc.partitioning_manager.victimTableLineSetPlusOne::1     12  # v
system.llc.partitioning_manager.victimTableLineSetPlusOne::total 23  # v
system.llc.partitioning_manager.victimTableSetMismatches    0  # m

---------- End Simulation Statistics   ----------

---------- Begin Simulation Statistics ----------
system.llc.partitioning_manager.probeSetRotation           99       # second
---------- End Simulation Statistics   ----------
"""

    def test_only_the_first_block_is_read(self):
        scalars, vectors = h.load_analysis().parse_first_stats_block(self.TEXT)
        self.assertEqual(scalars[PREFIX + "probeSetRotation"], 5)
        self.assertEqual(scalars[PREFIX + "victimTableSetMismatches"], 0)

    def test_vector_entries_are_indexed_and_total_is_dropped(self):
        _, vectors = h.load_analysis().parse_first_stats_block(self.TEXT)
        self.assertEqual(vectors[PREFIX + "victimTableLineSetPlusOne"],
                         {0: 11, 1: 12})


class WayIsolation(unittest.TestCase):
    """The proposal's isolation metric: valid LLC blocks outside the assigned
    ways must be zero in every partitioned run."""
    TEXT = "\n".join([
        "---------- Begin Simulation Statistics ----------",
        PREFIX + "wayOccupancy::p0::way0   12   # v",
        PREFIX + "wayOccupancy::p0::way1   0   # v",
        PREFIX + "wayOccupancy::p0::way2   %d   # v",
        PREFIX + "wayOccupancy::p0::total  12   # v",
        PREFIX + "wayOccupancy::p1::way0   %d   # v",
        PREFIX + "wayOccupancy::p1::way2   30   # v",
        PREFIX + "wayOccupancy::other::way0   %d   # v",
        "---------- End Simulation Statistics   ----------"])

    def occupancy(self, p0_way2, p1_way0, other_way0):
        a = h.load_analysis()
        return a, a.parse_way_occupancy(self.TEXT % (p0_way2, p1_way0, other_way0))

    def test_parse_reads_partition_rows_and_ways_and_skips_totals(self):
        _, occ = self.occupancy(0, 0, 0)
        self.assertEqual(occ[(0, 0)], 12)
        self.assertEqual(occ[(1, 2)], 30)
        self.assertNotIn("total", " ".join(map(str, occ)))

    def test_no_violation_when_each_partition_stays_in_its_ways(self):
        a, occ = self.occupancy(0, 0, 0)
        self.assertEqual(a.isolation_violations(occ, "2-14"), 0)

    def test_blocks_outside_the_assigned_ways_are_counted(self):
        a, occ = self.occupancy(5, 3, 2)     # p0 in way 2, p1 in way 0, 'other'
        self.assertEqual(a.isolation_violations(occ, "2-14"), 5 + 3 + 2)

    def test_split_off_has_nothing_to_check(self):
        a, occ = self.occupancy(5, 3, 2)
        self.assertIsNone(a.isolation_violations(occ, "off"))


class HypothesisScore(unittest.TestCase):
    def setUp(self):
        self.a = h.load_analysis()

    def test_true_lines_score_high_and_wrong_lines_score_low(self):
        rng = np.random.default_rng(3)
        n, lines = 3000, 16
        truth = rng.integers(0, lines, n)
        X = rng.normal(0, 1, (n, lines))
        X[np.arange(n), truth] += 2.0            # the true line's set is slower
        X = (X - X.mean(0)) / X.std(0)
        score_t, z_t = self.a.hypothesis_score(truth, X)
        score_w, z_w = self.a.hypothesis_score(rng.integers(0, lines, n), X)
        self.assertGreater(z_t, 10)
        self.assertLess(abs(z_w), 4)
        self.assertGreater(score_t, score_w)

    def test_works_for_four_line_tables(self):
        rng = np.random.default_rng(4)
        n = 2000
        truth = rng.integers(0, 4, n)
        X = rng.normal(0, 1, (n, 4))
        X[np.arange(n), truth] += 1.0
        X = (X - X.mean(0)) / X.std(0)
        self.assertGreater(self.a.hypothesis_score(truth, X)[1], 8)


class ByteClassification(unittest.TestCase):
    def test_labels(self):
        a = h.load_analysis()
        z_key = np.array([9.0, 1.0, 9.0, 9.0])
        z_plain = np.array([1.0, 9.0, 9.5, 1.0])
        z_shuf = np.array([0.5, 0.5, 0.5, 0.5])
        p_key = np.array([0.001, 0.9, 0.001, 0.001])
        p_plain = np.array([0.9, 0.001, 0.001, 0.9])
        labels = a.classify_bytes(z_key, z_plain, z_shuf, p_key, p_plain, 0.05)
        self.assertEqual(labels, ["plaintext_plus_key", "plaintext_only",
                                  "ambiguous", "plaintext_plus_key"])

    def test_nothing_significant_is_none(self):
        a = h.load_analysis()
        one = np.array([1.0])
        self.assertEqual(
            a.classify_bytes(one, one, one, np.array([0.5]), np.array([0.5]),
                             0.05), ["none"])


class TraceAndGroundTruth(unittest.TestCase):
    def setUp(self):
        self.a = h.load_analysis()
        self.cfg = {"T0": 2_000_000, "W": 1_048_576, "N_WIN": 4,
                    "OFF_ENC": 524_288, "OFF_ENC_END": 589_824}

    def line(self, window, offset, line):
        tick = (2_000_000 + window * 1_048_576 + offset) * 500
        return ("%d: system.llc.partitioning_manager: victim_fill line=%d "
                "set=34 vaddr=0x14200 paddr=0x2a200" % (tick, line))

    def test_window_and_offset_are_derived_from_the_tick(self):
        text = "\n".join([self.line(2, 524_288 + 40, 7),
                          "garbage line", self.line(0, 1000, 3)])
        events = self.a.parse_trace(text, self.cfg)
        self.assertEqual(events, [(2, 524_328, 7), (0, 1000, 3)])

    def test_warmup_fills_have_negative_windows(self):
        # window = floor((cycle - T0) / W): just before T0 is -1, and a fill at
        # cycle 100 is about 1.9 windows before T0, i.e. -2.
        text = "\n".join(
            "%d: x: victim_fill line=1 set=2 vaddr=0x1 paddr=0x2" % (cycle * 500)
            for cycle in (self.cfg["T0"] - 500, 100))
        events = self.a.parse_trace(text, self.cfg)
        self.assertEqual([e[0] for e in events], [-1, -2])

    def test_recall_precision_and_phase_accounting(self):
        touched = np.zeros((4, 68), dtype=bool)
        touched[0, [1, 2]] = True
        touched[1, [5]] = True
        events = [(0, 524_300, 1), (0, 524_301, 2),      # both touched lines
                  (1, 524_300, 5), (1, 524_302, 9),      # one hit, one extra
                  (2, 10, 4),                            # outside the AES phase
                  (-1, 100, 0)]                          # warm-up
        gt = self.a.ground_truth(events, touched, self.cfg)
        self.assertEqual(gt["touched_total"], 3)
        self.assertAlmostEqual(gt["recall"], 1.0)
        self.assertAlmostEqual(gt["precision"], 3 / 4)
        self.assertEqual(gt["fills_outside_aes_phase"], 1)
        self.assertEqual(gt["fills_before_measurement"], 1)
        self.assertAlmostEqual(gt["mean_fills_per_window"], 5 / 4)


class OracleLines(unittest.TestCase):
    def test_round1_touches_at_most_sixteen_lines_and_full_touches_more(self):
        a = h.load_analysis()
        key = a.hex16(KEY)
        pts = a.plaintexts(SEED, 200)
        ct, lookups, _ = a.aes_encrypt_trace(pts, a.key_expansion(key))
        offsets = a.DEFAULT_LINE_OFFSETS
        r1 = a.touched_lines(lookups, True, offsets)
        full = a.touched_lines(lookups, False, offsets)
        self.assertEqual(r1.shape, (200, 68))
        self.assertTrue((r1.sum(1) <= 16).all())
        self.assertTrue((full.sum(1) > r1.sum(1)).all())
        self.assertTrue(full[:, offsets["sbox"]:offsets["sbox"] + 4].any())
        self.assertFalse(r1[:, offsets["sbox"]:offsets["sbox"] + 4].any())
        self.assertTrue((full >= r1).all(), "round 1 is part of the full encryption")


class SynthRoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = h.load_analysis()

    def analyze(self, **kwargs):
        with h.tmpdir() as tmp:
            run_dir, info = make_run(self.a, tmp, **kwargs)
            return self.a.analyze_run_dir(run_dir), info

    def test_round1_key_leak_is_attributed_to_plaintext_plus_key(self):
        res, _ = self.analyze()
        at = res["attribution"]
        self.assertEqual(at["p_xor_k"]["bytes_significant"], 16)
        self.assertEqual(at["p_only"]["bytes_significant"], 0)
        self.assertEqual(at["shuffled"]["bytes_significant"], 0)
        self.assertEqual(res["byte_classification"]["round1"],
                         ["plaintext_plus_key"] * 16)
        self.assertTrue(res["decision"]["round1_plaintext_plus_key"])
        self.assertFalse(res["decision"]["round1_plaintext_only"])
        self.assertFalse(res["decision"]["lastround_c_xor_k10"])

    def test_plaintext_only_leak_is_not_mistaken_for_key_dependence(self):
        res, _ = self.analyze(leak="plaintext")
        self.assertEqual(res["byte_classification"]["round1"],
                         ["plaintext_only"] * 16)
        self.assertTrue(res["decision"]["round1_plaintext_only"])
        self.assertFalse(res["decision"]["round1_plaintext_plus_key"])

    def test_no_data_dependence_is_not_detected(self):
        res, _ = self.analyze(leak="none")
        for hyp in ("p_xor_k", "p_only", "shuffled", "lr_c_xor_k10", "c_only",
                    "lr_shuffled"):
            self.assertEqual(res["attribution"][hyp]["bytes_significant"], 0, hyp)
        self.assertFalse(any(res["decision"][k] for k in (
            "round1_plaintext_plus_key", "round1_plaintext_only",
            "lastround_c_xor_k10", "lastround_ciphertext_only")))

    def test_detection_is_flagged_unreliable_when_classes_outnumber_windows(self):
        # The P0 smoke run (20 windows, 16 classes) showed the SHUFFLED control
        # significant on 16/16 bytes: with about one window per class the ANOVA
        # is degenerate.  The table must say so instead of looking like a result.
        res, _ = self.analyze(n=100)
        det = res["detection"]
        self.assertFalse(det["first_round"]["reliable"])     # 16 classes need 160
        self.assertFalse(det["shuffled"]["reliable"])
        self.assertTrue(det["last_round"]["reliable"])       # 4 classes need 40
        self.assertTrue(det["c_line"]["reliable"])

    def test_detection_is_reliable_with_enough_windows(self):
        res, _ = self.analyze(n=300)
        self.assertTrue(all(v["reliable"] for v in res["detection"].values()))

    def test_markdown_warns_about_unreliable_detection(self):
        res, _ = self.analyze(n=100)
        text = self.a.render_markdown(res)
        self.assertIn("unreliable", text)
        res, _ = self.analyze(n=300)
        self.assertNotIn("unreliable", self.a.render_markdown(res))

    def test_no_data_dependence_in_full_aes_mode_is_not_detected(self):
        # 'none' must randomise EVERY round's lookups: rounds 2-10 of a real
        # encryption genuinely depend on the data, so leaving them in place
        # would make a correct last-round detection look like a false positive.
        res, _ = self.analyze(leak="none", rounds1=False, n=2000)
        for hyp in ("p_xor_k", "p_only", "shuffled", "lr_c_xor_k10", "c_only",
                    "lr_shuffled"):
            self.assertEqual(res["attribution"][hyp]["bytes_significant"], 0, hyp)
        self.assertFalse(any(res["decision"][k] for k in (
            "round1_plaintext_plus_key", "round1_plaintext_only",
            "lastround_c_xor_k10", "lastround_ciphertext_only")))

    def test_detection_is_location_free_and_cannot_separate_p_from_pxk(self):
        res, _ = self.analyze()
        det = res["detection"]
        self.assertEqual(det["first_round"]["bytes_significant"], 16)
        self.assertEqual(det["shuffled"]["bytes_significant"], 0)

    def test_ground_truth_matches_the_oracle_for_the_synthetic_trace(self):
        res, _ = self.analyze()
        gt = res["ground_truth"]
        self.assertAlmostEqual(gt["recall"], 1.0)
        self.assertAlmostEqual(gt["precision"], 1.0)
        self.assertEqual(gt["fills_outside_aes_phase"], 0)
        self.assertGreater(gt["fills_before_measurement"], 0)

    def test_run_checks_pass_and_mapping_is_complete(self):
        res, _ = self.analyze()
        self.assertTrue(res["run_checks"]["all_passed"],
                        res["run_checks"]["checks"])
        self.assertEqual(len(res["line_map"]["line_logical_set"]), 68)
        self.assertEqual(len(set(res["line_map"]["line_logical_set"])), 68)

    def test_full_aes_round1_attribution_still_works_with_all_rounds_present(self):
        res, _ = self.analyze(rounds1=False, n=3000)
        at = res["attribution"]
        self.assertEqual(at["p_xor_k"]["bytes_significant"], 16)
        self.assertEqual(at["p_only"]["bytes_significant"], 0)
        self.assertEqual(at["shuffled"]["bytes_significant"], 0)
        # last round uses the 4-line sbox; it must be attributed to the key
        # at least as well as to ciphertext-only
        self.assertGreater(np.mean(at["lr_c_xor_k10"]["z_per_byte"]),
                           np.mean(at["c_only"]["z_per_byte"]))

    def test_arbitrary_set_map_and_rotation_are_handled(self):
        for rng_seed in (2, 9):
            res, info = self.analyze(rng_seed=rng_seed)
            self.assertEqual(res["line_map"]["line_logical_set"],
                             info["line_logical_set"])
            self.assertEqual(res["attribution"]["p_xor_k"]["bytes_significant"], 16)

    def test_partitioned_run_checks_way_isolation(self):
        res, _ = self.analyze(split="8-8", n=300)
        checks = {c["name"]: c for c in res["run_checks"]["checks"]}
        self.assertTrue(checks["way_isolation"]["ok"], checks["way_isolation"])
        self.assertTrue(res["run_checks"]["all_passed"])

    def test_isolation_violation_fails_the_run_checks(self):
        res, _ = self.analyze(split="8-8", n=300, isolation_violation=True)
        checks = {c["name"]: c for c in res["run_checks"]["checks"]}
        self.assertFalse(checks["way_isolation"]["ok"])
        self.assertFalse(res["run_checks"]["all_passed"])

    def test_unpartitioned_run_has_no_isolation_check(self):
        res, _ = self.analyze(n=300)
        self.assertNotIn("way_isolation",
                         [c["name"] for c in res["run_checks"]["checks"]])

    def test_markdown_summary_is_a_table(self):
        res, _ = self.analyze()
        text = self.a.render_markdown(res)
        self.assertIn("| hypothesis |", text)
        self.assertIn("p_xor_k", text)
        self.assertIn("Run checks", text)
        self.assertIn("simulated", text.lower())


class RunDirValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = h.load_analysis()

    def with_run(self, mutate):
        with h.tmpdir() as tmp:
            run_dir, _ = make_run(self.a, tmp, n=200)
            mutate(run_dir)
            return self.a.analyze_run_dir(run_dir)

    def test_unmapped_table_line_is_an_error(self):
        def mutate(run_dir):
            path = run_dir / "stats.txt"
            wanted = PREFIX + "victimTableLineSetPlusOne::10 "
            lines = [PREFIX + "victimTableLineSetPlusOne::10   0   # unmapped"
                     if l.startswith(wanted) else l
                     for l in path.read_text().splitlines()]
            path.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(self.a.AnalysisError, "unmapped"):
            self.with_run(mutate)

    def test_set_mismatch_counter_is_an_error(self):
        def mutate(run_dir):
            path = run_dir / "stats.txt"
            path.write_text(path.read_text().replace(
                PREFIX + "victimTableSetMismatches  0",
                PREFIX + "victimTableSetMismatches  3", 1))
        with self.assertRaisesRegex(self.a.AnalysisError, "mismatch"):
            self.with_run(mutate)

    def test_truncated_probe_file_is_an_error(self):
        def mutate(run_dir):
            path = run_dir / "probes.bin"
            path.write_bytes(path.read_bytes()[:-16])
        with self.assertRaisesRegex(self.a.AnalysisError, "probes.bin"):
            self.with_run(mutate)

    def test_wrong_interval_field_is_an_error(self):
        def mutate(run_dir):
            path = run_dir / "probes.bin"
            raw = bytearray(path.read_bytes())
            raw[12] ^= 0x01                      # interval field of record 0
            path.write_bytes(bytes(raw))
        with self.assertRaisesRegex(self.a.AnalysisError, "interval"):
            self.with_run(mutate)

    def test_two_table_lines_in_one_set_is_an_error(self):
        def mutate(run_dir):
            path = run_dir / "stats.txt"
            lines = path.read_text().splitlines()
            wanted = PREFIX + "victimTableLineSetPlusOne::1 "
            first = next(l for l in lines
                         if l.startswith(PREFIX + "victimTableLineSetPlusOne::0 "))
            value = first.split()[1]
            lines = [l if not l.startswith(wanted) else
                     PREFIX + "victimTableLineSetPlusOne::1   %s   # clash" % value
                     for l in lines]
            path.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(self.a.AnalysisError, "share"):
            self.with_run(mutate)

    def test_checksum_mismatch_is_reported_not_hidden(self):
        def mutate(run_dir):
            path = run_dir / "simout.txt"
            text = path.read_text()
            start = text.index("pt_checksum=") + len("pt_checksum=")
            flip = "0" if text[start] != "0" else "1"
            path.write_text(text[:start] + flip + text[start + 1:])
        res = self.with_run(mutate)
        self.assertFalse(res["run_checks"]["all_passed"])
        names = [c["name"] for c in res["run_checks"]["checks"] if not c["ok"]]
        self.assertIn("checksum_matches", names)

    def test_missing_selftest_pass_is_reported(self):
        def mutate(run_dir):
            path = run_dir / "simout.txt"
            path.write_text(path.read_text().replace(
                "victim aes_self_test=PASS\n", ""))
        res = self.with_run(mutate)
        names = [c["name"] for c in res["run_checks"]["checks"] if not c["ok"]]
        self.assertIn("aes_self_test_pass", names)


class Cli(unittest.TestCase):
    SCRIPT = h.EXP / "analysis" / "aes_leak_analysis.py"

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(self.SCRIPT)] +
                              [str(a) for a in args],
                              capture_output=True, text=True, timeout=600)

    def test_selftest_passes(self):
        proc = self.run_cli("selftest")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("SELFTEST PASS", proc.stdout)

    def test_synth_then_analyze_round_trip_writes_json_and_markdown(self):
        with h.tmpdir() as tmp:
            run_dir = h.Path(tmp) / "fake"
            proc = self.run_cli("synth", "--run-dir", run_dir, "--n", 600)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            for name in ("probes.bin", "stats.txt", "simout.txt",
                         "leak_config.json", "victim_table.trace"):
                self.assertTrue((run_dir / name).is_file(), name)
            out_json, out_md = h.Path(tmp) / "r.json", h.Path(tmp) / "r.md"
            proc = self.run_cli("analyze", "--run-dir", run_dir,
                                "--out-json", out_json, "--out-md", out_md)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            data = json.loads(out_json.read_text())
            self.assertEqual(data["attribution"]["p_xor_k"]["bytes_significant"], 16)
            self.assertIn("| hypothesis |", out_md.read_text())

    def test_analyze_exits_1_when_a_run_check_fails(self):
        with h.tmpdir() as tmp:
            run_dir = h.Path(tmp) / "fake"
            self.run_cli("synth", "--run-dir", run_dir, "--n", 300)
            simout = run_dir / "simout.txt"
            simout.write_text(simout.read_text().replace(
                "victim aes_self_test=PASS\n", ""))
            proc = self.run_cli("analyze", "--run-dir", run_dir)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("FAIL", proc.stdout)


if __name__ == "__main__":
    unittest.main()
