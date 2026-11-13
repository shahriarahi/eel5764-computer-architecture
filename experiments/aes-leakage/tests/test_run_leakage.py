"""run_leakage.py: the gem5 configuration adapter (tested without gem5).

The adapter loads the frozen configs/run_contention.py WITHOUT running its
main, overrides its tables, wraps m5.instantiate to set the tracing parameters
and write leak_config.json.  Here m5 is replaced by a small fake; the real
baseline module is loaded and inspected, never executed.
"""
import contextlib
import copy
import hashlib
import io
import json
import shutil
import sys
import types
import unittest

from tests import _helpers as h

BUILD = h.EXP / "build" / "n20"          # committed real (non-fake-clock) build


def adapter():
    return h.load_module("run_leakage_under_test", h.EXP / "run_leakage.py")


@h.skip_unless_tool("riscv64-linux-gnu-nm")
class Variants(unittest.TestCase):
    def test_variants_map_to_the_built_binaries_and_flags(self):
        rl = adapter()
        manifest = json.loads((BUILD / "build_manifest.json").read_text())
        self.assertEqual(sorted(rl.VARIANTS),
                         ["full-noscrub", "full-scrub", "r1-scrub", "tvla"])
        for name, v in rl.VARIANTS.items():
            self.assertIn(v["binary"], manifest["binaries"], name)
        self.assertEqual(rl.VARIANTS["r1-scrub"]["rounds1"], 1)
        self.assertEqual(rl.VARIANTS["full-noscrub"]["scrub"], 0)
        self.assertEqual(rl.VARIANTS["tvla"]["tvla"], 1)


@h.skip_unless_tool("riscv64-linux-gnu-nm")
class Manifest(unittest.TestCase):
    def test_loads_the_committed_build(self):
        m = adapter().load_manifest(BUILD)
        self.assertEqual(m["n_win"], 20)

    def test_refuses_a_fake_clock_build(self):
        rl = adapter()
        with h.tmpdir() as tmp:
            target = h.Path(tmp) / "b"
            shutil.copytree(BUILD, target)
            manifest = json.loads((target / "build_manifest.json").read_text())
            manifest["defines"].append("-DLEAK_FAKE_CLOCK")
            (target / "build_manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(rl.AdapterError, "LEAK_FAKE_CLOCK"):
                rl.load_manifest(target)

    def test_refuses_a_binary_that_does_not_match_its_recorded_hash(self):
        rl = adapter()
        with h.tmpdir() as tmp:
            target = h.Path(tmp) / "b"
            shutil.copytree(BUILD, target)
            with open(target / "monitor_leak", "ab") as stream:
                stream.write(b"\0")
            with self.assertRaisesRegex(rl.AdapterError, "sha256"):
                rl.load_manifest(target)

    def test_refuses_a_missing_manifest(self):
        rl = adapter()
        with h.tmpdir() as tmp:
            with self.assertRaisesRegex(rl.AdapterError, "build_manifest.json"):
                rl.load_manifest(h.Path(tmp))


@h.skip_unless_tool("riscv64-linux-gnu-nm")
class LeakConfig(unittest.TestCase):
    def test_contents(self):
        rl = adapter()
        manifest = rl.load_manifest(BUILD)
        name = rl.VARIANTS["r1-scrub"]["binary"]
        layout = rl.victim_layout(BUILD / name)
        cfg = rl.build_leak_config(
            manifest, "r1-scrub", layout, workload_seed=0x5764A5E5,
            split="8-8", monitor_ways=8, build_dir=BUILD)
        self.assertEqual(cfg["key_hex"], "f1e2d3c4b5a69788796a5b4c3d2e1f10")
        self.assertEqual((cfg["N_WIN"], cfg["W"], cfg["T0"]),
                         (20, 1_048_576, 2_000_000))
        for key in ("OFF_PRIME", "OFF_ENC", "OFF_ENC_END", "OFF_PROBE"):
            self.assertIn(key, cfg)
        self.assertEqual((cfg["rounds1"], cfg["scrub"], cfg["tvla"]), (1, 1, 0))
        self.assertEqual(cfg["workload_seed"], 0x5764A5E5)
        self.assertEqual((cfg["split"], cfg["monitor_ways"]), ("8-8", 8))
        self.assertEqual(cfg["trace_range"]["n_lines"], 68)
        self.assertEqual(cfg["tables"]["te3"]["line_offset"], 52)
        self.assertEqual(cfg["tables"]["sbox"]["lines"], 4)
        victim = (BUILD / name).read_bytes()
        self.assertEqual(cfg["binaries"]["victim"]["sha256"],
                         hashlib.sha256(victim).hexdigest())
        self.assertEqual(cfg["binaries"]["monitor"]["name"], "monitor_leak")
        self.assertFalse(cfg["synthetic"])

    def test_config_is_what_the_analysis_expects(self):
        rl = adapter()
        a = h.load_analysis()
        manifest = rl.load_manifest(BUILD)
        layout = rl.victim_layout(BUILD / rl.VARIANTS["full-scrub"]["binary"])
        cfg = rl.build_leak_config(manifest, "full-scrub", layout, 1, "off", 16,
                                   BUILD)
        for table in a.TABLES:
            self.assertEqual(cfg["tables"][table]["line_offset"],
                             a.DEFAULT_LINE_OFFSETS[table], table)
            self.assertEqual(cfg["tables"][table]["lines"],
                             a.TABLE_LINES[table], table)
        for key, value in a.DEFAULT_SCHEDULE.items():
            self.assertEqual(cfg[key], value, key)


class ForwardedArguments(unittest.TestCase):
    def test_injects_the_required_baseline_flags(self):
        rl = adapter()
        argv, info = rl.forwarded_args(
            ["--split", "off", "--monitor-ways", "16"], default_seed=99)
        self.assertEqual(argv.count("--l1d-size"), 1)
        self.assertIn("4KiB", argv)
        self.assertEqual(argv[argv.index("--monitor-sink") + 1], "file")
        self.assertEqual(argv[argv.index("--monitor-variant") + 1], "v3")
        self.assertEqual(info, {"split": "off", "monitor_ways": 16,
                                "workload_seed": 99})

    def test_explicit_matching_flags_are_accepted_once(self):
        rl = adapter()
        argv, info = rl.forwarded_args(
            ["--split", "8-8", "--monitor-ways", "8", "--l1d-size", "4KiB",
             "--monitor-sink", "file", "--monitor-variant", "v3",
             "--workload-seed", "0x10"], default_seed=1)
        self.assertEqual(argv.count("--l1d-size"), 1)
        self.assertEqual(info["workload_seed"], 16)

    def test_conflicting_flags_are_refused(self):
        rl = adapter()
        for extra in (["--l1d-size", "16KiB"], ["--monitor-sink", "memory"],
                      ["--monitor-variant", "v2"]):
            with self.assertRaises(rl.AdapterError, msg=extra):
                rl.forwarded_args(["--split", "off", "--monitor-ways", "16"] +
                                  extra, default_seed=1)

    def test_split_and_monitor_ways_are_required(self):
        rl = adapter()
        with self.assertRaises(rl.AdapterError):
            rl.forwarded_args(["--split", "off"], default_seed=1)
        with self.assertRaises(rl.AdapterError):
            rl.forwarded_args(["--monitor-ways", "4"], default_seed=1)


@h.skip_unless_tool("riscv64-linux-gnu-nm")
class BaselineOverrides(unittest.TestCase):
    def test_baseline_is_loaded_without_running_main_and_overridden(self):
        rl = adapter()
        manifest = rl.load_manifest(BUILD)
        baseline = rl.load_baseline(h.REPO)
        self.assertTrue(hasattr(baseline, "main"))
        self.assertNotIn("m5", vars(baseline), "main() must not have run")
        victim = BUILD / rl.VARIANTS["full-scrub"]["binary"]
        monitor = BUILD / "monitor_leak"
        rl.apply_overrides(baseline, manifest, victim, monitor)
        cfg = copy.deepcopy(baseline.CONFIG)
        baseline.apply_experiment_profile(cfg, "4KiB")
        self.assertEqual(cfg["workloads"], [str(monitor), str(victim)])
        self.assertEqual(cfg["contention"]["epoch_cycles"], 1_048_576)
        self.assertEqual(cfg["contention"]["interval_count"], 20)
        self.assertEqual(cfg["measure_ticks"], 20 * 1_048_576 * 500)
        # the 'v3' monitor variant now resolves to monitor_leak, which the
        # baseline's main() picks for --monitor-sink file --monitor-variant v3
        self.assertEqual(baseline.MONITOR_VARIANT_BINARIES["v3"], str(monitor))
        self.assertEqual(baseline.MONITOR_SINK_BINARIES["file"], str(monitor))

    def test_baseline_file_on_disk_is_untouched(self):
        rl = adapter()
        before = (h.REPO / "configs" / "run_contention.py").read_bytes()
        rl.load_baseline(h.REPO)
        self.assertEqual(before,
                         (h.REPO / "configs" / "run_contention.py").read_bytes())


class TracingParameters(unittest.TestCase):
    LAYOUT = {"trace_base": 0x14080, "trace_size": 68 * 64, "trace_lines": 68}

    def test_sets_all_four_parameters(self):
        rl = adapter()
        manager = types.SimpleNamespace()
        rl.set_tracing_params(manager, self.LAYOUT)
        self.assertEqual(manager.victim_requestor_name, "cpu1.data")
        self.assertEqual(manager.victim_vaddr_base, 0x14080)
        self.assertEqual(manager.victim_vaddr_size, 68 * 64)
        self.assertEqual(manager.victim_set_count, 256)

    def test_refuses_a_gem5_binary_without_the_victim_parameters(self):
        rl = adapter()

        class Old(object):
            def __setattr__(self, name, value):
                if name.startswith("victim_"):
                    raise AttributeError("no parameter %s" % name)
                object.__setattr__(self, name, value)

        with self.assertRaisesRegex(rl.AdapterError, "victim_"):
            rl.set_tracing_params(Old(), self.LAYOUT)


@h.skip_unless_tool("riscv64-linux-gnu-nm")
class MainWithFakeM5(unittest.TestCase):
    """Drives main() end to end with a fake m5 and a fake baseline."""

    def make_fakes(self, outdir, manager):
        calls = []
        baseline = types.ModuleType("fake_baseline")
        baseline.EXPERIMENT_PROFILES = {"4KiB": {"workloads": ["x", "y"],
                                                 "epoch_cycles": 2_000_000}}
        baseline.CONFIG = {"contention": {"interval_count": 64}}
        baseline.MONITOR_VARIANT_BINARIES = {"v3": "workloads/monitor_v3_l1d4k"}
        baseline.MONITOR_SINK_BINARIES = {"file": "workloads/monitor_v2_l1d4k"}
        baseline.DEFAULT_WORKLOAD_SEED = 0x5764A5E5

        def baseline_main():
            calls.append(("baseline_main", list(sys.argv)))
            m5.instantiate()
        baseline.main = baseline_main

        def original_instantiate(*a, **k):
            calls.append(("instantiate", dict(vars(manager))))
        m5 = types.SimpleNamespace(
            instantiate=original_instantiate,
            options=types.SimpleNamespace(outdir=str(outdir)))
        root = types.SimpleNamespace(
            getInstance=lambda: types.SimpleNamespace(
                system=types.SimpleNamespace(
                    llc=types.SimpleNamespace(partitioning_manager=manager))))
        return m5, baseline, root, calls, original_instantiate

    def test_flow_sets_params_writes_config_then_runs_the_baseline(self):
        rl = adapter()
        with h.tmpdir() as tmp:
            manager = types.SimpleNamespace()
            m5, baseline, root, calls, original = self.make_fakes(tmp, manager)
            rl.main(["--victim-variant", "r1-scrub", "--build-dir", str(BUILD),
                     "--split", "off", "--monitor-ways", "16"],
                    m5_module=m5, baseline=baseline, root=root)
            self.assertIs(m5.instantiate, original, "m5.instantiate restored")
            self.assertEqual([c[0] for c in calls],
                             ["baseline_main", "instantiate"])
            argv = calls[0][1]
            self.assertEqual(argv[0], "configs/run_contention.py")
            self.assertIn("--monitor-variant", argv)
            params = calls[1][1]
            self.assertEqual(params["victim_requestor_name"], "cpu1.data")
            self.assertEqual(params["victim_vaddr_size"], 68 * 64)
            cfg = json.loads((h.Path(tmp) / "leak_config.json").read_text())
            self.assertEqual(cfg["victim_variant"], "r1-scrub")
            self.assertEqual(cfg["N_WIN"], 20)
            self.assertEqual(cfg["workload_seed"], 0x5764A5E5)

    def test_existing_leak_config_is_never_overwritten(self):
        rl = adapter()
        with h.tmpdir() as tmp:
            (h.Path(tmp) / "leak_config.json").write_text("{}")
            manager = types.SimpleNamespace()
            m5, baseline, root, calls, _ = self.make_fakes(tmp, manager)
            with self.assertRaises(FileExistsError):
                rl.main(["--victim-variant", "full-scrub", "--build-dir",
                         str(BUILD), "--split", "off", "--monitor-ways", "16"],
                        m5_module=m5, baseline=baseline, root=root)
            self.assertEqual((h.Path(tmp) / "leak_config.json").read_text(), "{}")

    def test_unknown_variant_is_refused_before_anything_runs(self):
        rl = adapter()
        with h.tmpdir() as tmp:
            m5, baseline, root, calls, _ = self.make_fakes(tmp, types.SimpleNamespace())
            with self.assertRaises(SystemExit), \
                    contextlib.redirect_stderr(io.StringIO()):
                rl.main(["--victim-variant", "nope", "--build-dir", str(BUILD),
                         "--split", "off", "--monitor-ways", "16"],
                        m5_module=m5, baseline=baseline, root=root)
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
