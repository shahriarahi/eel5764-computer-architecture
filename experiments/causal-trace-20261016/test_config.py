import unittest
from pathlib import Path

import prepare_gem5
from prepare_gem5 import STAGES, TARGETS
from run_contention_causal import (
    domain_for_peer, llc_response_queue_name, validate_trace_config,
)


class TraceConfigTests(unittest.TestCase):
    def test_queue_name_matches_gem5_resp_packet_queue(self) -> None:
        # RespPacketQueue::name() is cpuSidePort.name() + "-" + label, and
        # BaseCache names its port "<cache>.cpu_side_port" with "CpuSidePort".
        self.assertEqual(llc_response_queue_name("system.llc"),
                         "system.llc.cpu_side_port-CpuSidePort")


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

    def test_hooks_emit_version_two_scheduled_ticks(self) -> None:
        source = Path(prepare_gem5.__file__).read_text()
        self.assertIn("CAUSAL_TRACE version=2 tick=%llu sched=%llu", prepare_gem5.HEADER)
        for hook in (
            'CAUSAL_TRACE_EVENT("llc_response_ready", name(), pkt, request_time, "hit")',
            'CAUSAL_TRACE_EVENT("llc_response_ready", name(), tgt_pkt, completion_time, "fill")',
            'CAUSAL_TRACE_EVENT("response_enqueue", name(), pkt, when, "queued")',
            'CAUSAL_TRACE_EVENT("xbar_response_forward", name(), pkt, curTick() + latency, "accepted")',
        ):
            self.assertIn(hook, source)


if __name__ == "__main__":
    unittest.main()
