"""run_leakage_defense.py: the full-defense wrapper (tested without gem5).

A fake m5, a fake baseline and a fake system stand in for gem5, as in
test_run_leakage.py.
"""
import contextlib
import io
import json
import sys
import types
import unittest

from tests import _helpers as h

BUILD = h.EXP / "build" / "n20"
PEERS = ["system.cpu0.icache.mem_side", "system.cpu0.dcache.mem_side",
         "system.cpu0.mmu.itb.walker.port", "system.cpu0.mmu.dtb.walker.port",
         "system.cpu1.icache.mem_side", "system.cpu1.dcache.mem_side",
         "system.cpu1.mmu.itb.walker.port", "system.cpu1.mmu.dtb.walker.port"]


def wrapper():
    return h.load_module("run_leakage_defense_under_test",
                         h.EXP / "run_leakage_defense.py")


def fake_system(peers=PEERS, bus=None, llc=None, manager=None):
    ports = [types.SimpleNamespace(peer=p) for p in peers]
    bus = bus or types.SimpleNamespace()
    bus.cpu_side_ports = types.SimpleNamespace(elements=ports)
    llc = llc or types.SimpleNamespace()
    llc.partitioning_manager = manager or types.SimpleNamespace()
    return types.SimpleNamespace(l2bus=bus, llc=llc)


class NoDefenseParams(object):
    """A bus of a gem5 binary without the time-slot patch."""
    def __setattr__(self, name, value):
        if name.startswith("tdma_"):
            raise AttributeError("no parameter %s" % name)
        object.__setattr__(self, name, value)


class Peers(unittest.TestCase):
    def test_maps_every_real_peer_name_to_its_core(self):
        w = wrapper()
        self.assertEqual([w.domain_for_peer(p) for p in PEERS],
                         [0, 0, 0, 0, 1, 1, 1, 1])

    def test_refuses_an_unknown_peer(self):
        w = wrapper()
        with self.assertRaises(w.run_leakage.AdapterError):
            w.domain_for_peer("system.cpu2.dcache.mem_side")

    def test_slot_cycles_validation(self):
        w = wrapper()
        self.assertEqual(w.slot_cycles("0"), 0)
        self.assertEqual(w.slot_cycles("4"), 4)
        with self.assertRaises(Exception):
            w.slot_cycles("3")


class ApplyDefense(unittest.TestCase):
    def test_sets_time_slots_and_response_domains(self):
        w = wrapper()
        system = fake_system()
        meta = w.apply_defense(system, 4, True)
        self.assertEqual(system.l2bus.tdma_slot_cycles, 4)
        self.assertEqual(system.l2bus.tdma_port_domains, [0, 0, 0, 0, 1, 1, 1, 1])
        self.assertEqual(system.llc.response_domain_prefixes, ["cpu0.", "cpu1."])
        self.assertEqual(meta["tdma_slot_cycles"], 4)
        self.assertTrue(meta["respq"])

    def test_without_respq_the_llc_is_left_alone(self):
        w = wrapper()
        system = fake_system()
        meta = w.apply_defense(system, 4, False)
        self.assertFalse(hasattr(system.llc, "response_domain_prefixes"))
        self.assertIsNone(meta["response_domain_prefixes"])

    def test_refuses_a_binary_without_the_defense_parameters(self):
        w = wrapper()
        with self.assertRaisesRegex(w.run_leakage.AdapterError, "defense"):
            w.apply_defense(fake_system(bus=NoDefenseParams()), 4, True)

    def test_refuses_a_system_with_one_domain_only(self):
        w = wrapper()
        with self.assertRaises(w.run_leakage.AdapterError):
            w.apply_defense(fake_system(peers=PEERS[:4]), 4, True)


@h.skip_unless_tool("riscv64-linux-gnu-nm")
class MainWithFakeM5(unittest.TestCase):
    def make_fakes(self, outdir, system):
        calls = []
        baseline = types.ModuleType("fake_baseline")
        baseline.EXPERIMENT_PROFILES = {"4KiB": {"workloads": ["x", "y"],
                                                 "epoch_cycles": 2_000_000}}
        baseline.CONFIG = {"contention": {"interval_count": 64}}
        baseline.MONITOR_VARIANT_BINARIES = {"v3": "m"}
        baseline.MONITOR_SINK_BINARIES = {"file": "m"}
        baseline.DEFAULT_WORKLOAD_SEED = 0x5764A5E5

        def baseline_main():
            calls.append(("baseline_main", list(sys.argv)))
            m5.instantiate()
        baseline.main = baseline_main

        def original_instantiate(*a, **k):
            calls.append(("instantiate",
                          dict(vars(system.llc.partitioning_manager)),
                          getattr(system.l2bus, "tdma_slot_cycles", None),
                          getattr(system.llc, "response_domain_prefixes", None)))
        m5 = types.SimpleNamespace(
            instantiate=original_instantiate,
            options=types.SimpleNamespace(outdir=str(outdir)))
        root = types.SimpleNamespace(
            getInstance=lambda: types.SimpleNamespace(system=system))
        return m5, baseline, root, calls, original_instantiate

    ARGS = ["--victim-variant", "full-scrub", "--build-dir", str(BUILD),
            "--split", "8-8", "--monitor-ways", "8"]

    def test_tracing_then_defense_then_the_real_instantiate(self):
        w = wrapper()
        with h.tmpdir() as tmp:
            system = fake_system()
            m5, baseline, root, calls, original = self.make_fakes(tmp, system)
            w.main(["--tdma-slot-cycles", "4", "--respq"] + self.ARGS,
                   m5_module=m5, baseline=baseline, root=root)
            self.assertIs(m5.instantiate, original, "m5.instantiate restored")
            self.assertEqual([c[0] for c in calls],
                             ["baseline_main", "instantiate"])
            argv = calls[0][1]
            self.assertNotIn("--tdma-slot-cycles", argv)
            self.assertNotIn("--respq", argv)
            self.assertEqual(argv[argv.index("--split") + 1], "8-8")
            _, tracing, slots, prefixes = calls[1]
            self.assertEqual(tracing["victim_requestor_name"], "cpu1.data")
            self.assertEqual(slots, 4)
            self.assertEqual(prefixes, ["cpu0.", "cpu1."])
            leak = json.loads((h.Path(tmp) / "leak_config.json").read_text())
            self.assertEqual((leak["split"], leak["monitor_ways"]), ("8-8", 8))
            meta = json.loads((h.Path(tmp) / "defense_config.json").read_text())
            self.assertEqual(meta["tdma_slot_cycles"], 4)
            self.assertEqual(meta["port_domains"], [0, 0, 0, 0, 1, 1, 1, 1])
            self.assertTrue(meta["respq"])

    def test_slot_cycles_are_required(self):
        w = wrapper()
        with h.tmpdir() as tmp:
            m5, baseline, root, calls, _ = self.make_fakes(tmp, fake_system())
            with self.assertRaises(SystemExit), \
                    contextlib.redirect_stderr(io.StringIO()):
                w.main(self.ARGS, m5_module=m5, baseline=baseline, root=root)
            self.assertEqual(calls, [])

    def test_a_binary_without_the_defense_stops_before_instantiate(self):
        w = wrapper()
        with h.tmpdir() as tmp:
            system = fake_system(bus=NoDefenseParams())
            m5, baseline, root, calls, original = self.make_fakes(tmp, system)
            with self.assertRaises(SystemExit), \
                    contextlib.redirect_stderr(io.StringIO()):
                w.main(["--tdma-slot-cycles", "4", "--respq"] + self.ARGS,
                       m5_module=m5, baseline=baseline, root=root)
            self.assertEqual([c[0] for c in calls], ["baseline_main"])
            self.assertIs(m5.instantiate, original)
            self.assertFalse((h.Path(tmp) / "defense_config.json").exists())


if __name__ == "__main__":
    unittest.main()
