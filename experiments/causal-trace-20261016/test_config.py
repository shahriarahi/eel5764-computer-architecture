import unittest

from prepare_gem5 import STAGES, TARGETS
from run_contention_causal import domain_for_peer, validate_trace_config


class TraceConfigTests(unittest.TestCase):
    def test_disabled_accepts_empty_filter(self) -> None:
        validate_trace_config(False, "", 0, 0, "", "")

    def test_enabled_accepts_complete_filter(self) -> None:
        validate_trace_config(True, "cpu0.data", 0x1000, 0x2000,
                              "system.llc", "system.llc.cpu_side")

    def test_enabled_rejects_zero_size(self) -> None:
        with self.assertRaisesRegex(ValueError, "size"):
            validate_trace_config(True, "cpu0.data", 0x1000, 0,
                                  "system.llc", "system.llc.cpu_side")

    def test_enabled_rejects_missing_names(self) -> None:
        for values in (("", "system.llc", "system.llc.cpu_side"),
                       ("cpu0.data", "", "system.llc.cpu_side"),
                       ("cpu0.data", "system.llc", "")):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, "name"):
                validate_trace_config(True, values[0], 0x1000, 0x1000,
                                      values[1], values[2])

    def test_rejects_address_overflow(self) -> None:
        with self.assertRaisesRegex(ValueError, "overflow"):
            validate_trace_config(True, "cpu0.data", (1 << 64) - 8, 16,
                                  "system.llc", "system.llc.cpu_side")

    def test_preserves_tdma_domain_mapping(self) -> None:
        self.assertEqual(domain_for_peer("system.cpu0.dcache.mem_side"), 0)
        self.assertEqual(domain_for_peer("system.cpu1.mmu.dtb.walker.port"), 1)

    def test_preparation_covers_declared_stages_and_sources(self) -> None:
        self.assertEqual(STAGES, {
            "request_admit", "llc_response_ready", "response_enqueue",
            "response_send_attempt", "response_retry", "response_dequeue",
            "xbar_response_forward", "cpu_delivery",
        })
        self.assertEqual(TARGETS, {
            "src/mem/SConscript", "src/mem/XBar.py",
            "src/mem/coherent_xbar.hh", "src/mem/coherent_xbar.cc",
            "src/mem/cache/base.cc", "src/mem/cache/cache.cc",
            "src/mem/packet_queue.cc", "src/cpu/simple/timing.cc",
        })


if __name__ == "__main__":
    unittest.main()
