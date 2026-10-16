import argparse
import copy
import runpy
import unittest
from pathlib import Path

from configs.run_contention import (
    CONFIG,
    apply_experiment_profile,
    interval_ticks,
    mechanism_options,
    parse_l2bus_header_latency,
    parse_l2bus_width,
    parse_nm_symbol,
    parse_monitor_ways,
    parse_workload_seed,
    parse_l1d_size,
    parse_split,
    validate_monitor_ways,
)


class ContentionConfigTests(unittest.TestCase):
    def test_gem5_module_name_enters_main(self) -> None:
        config_path = Path(__file__).parents[1] / "configs" / "run_contention.py"
        with self.assertRaisesRegex(ModuleNotFoundError, "m5"):
            runpy.run_path(str(config_path), run_name="__m5_main__")

    def test_split_parser_accepts_control_and_valid_partitions(self) -> None:
        self.assertIsNone(parse_split("off"))
        self.assertIsNone(parse_split("UNPARTITIONED"))
        self.assertEqual(parse_split("8/8"), (8, 8))
        self.assertEqual(parse_split("1-15"), (1, 15))

    def test_split_parser_rejects_malformed_or_non_partitioning_values(self) -> None:
        for value in ("abc", "0-16", "9-9", "1-14"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_split(value)

    def test_monitor_way_parser_accepts_only_llc_depths(self) -> None:
        self.assertEqual(parse_monitor_ways("1"), 1)
        self.assertEqual(parse_monitor_ways("16"), 16)
        for value in ("0", "17", "bad", "1.5"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_monitor_ways(value)

    def test_workload_seed_parser_accepts_public_u64_values(self) -> None:
        self.assertEqual(parse_workload_seed("1466213861"), 1466213861)
        self.assertEqual(parse_workload_seed("0x5764a5e5"), 1466213861)
        self.assertEqual(parse_workload_seed("18446744073709551615"), 2**64 - 1)
        for value in ("0", "-1", "18446744073709551616", "bad"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_workload_seed(value)

    def test_partitioned_monitor_depth_must_match_allocation(self) -> None:
        validate_monitor_ways(None, 1)
        validate_monitor_ways(None, 16)
        validate_monitor_ways((4, 12), 4)
        with self.assertRaisesRegex(ValueError, "must equal"):
            validate_monitor_ways((4, 12), 16)

    def test_nm_parser_finds_probe_array_address_and_size(self) -> None:
        nm_output = (
            "0000000000010000 0000000000000040 t helper\n"
            "0000000000024000 0000000000040000 b probe_lines\n"
        )

        self.assertEqual(
            parse_nm_symbol(nm_output, "probe_lines"),
            (0x24000, 0x40000),
        )

    def test_monitor_and_victim_are_assigned_in_core_order(self) -> None:
        self.assertEqual(CONFIG["workloads"], ["workloads/monitor", "workloads/victim"])

    def test_timing_matches_shared_workload_contract(self) -> None:
        self.assertEqual(CONFIG["cpu_clock"], "2GHz")
        self.assertEqual(CONFIG["warmup_ticks"], 1_000_000_000)
        self.assertEqual(CONFIG["measure_ticks"], 32_000_000_000)
        self.assertEqual(CONFIG["contention"]["start_cycle"], 2_000_000)
        self.assertEqual(CONFIG["contention"]["epoch_cycles"], 1_000_000)
        self.assertEqual(CONFIG["contention"]["interval_count"], 64)
        self.assertEqual(len(CONFIG["contention"]["activity_labels"]), 64)
        self.assertEqual(sum(CONFIG["contention"]["activity_labels"]), 32)

    def test_l1d_size_parser_accepts_only_predeclared_methods(self) -> None:
        self.assertEqual(parse_l1d_size("16KiB"), "16KiB")
        self.assertEqual(parse_l1d_size("4KiB"), "4KiB")
        for value in ("2KiB", "8KiB", "4096", "bad"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_l1d_size(value)

    def test_l1d4k_profile_keeps_guest_and_gem5_timing_aligned(self) -> None:
        config = copy.deepcopy(CONFIG)
        apply_experiment_profile(config, "4KiB")

        self.assertEqual(config["l1d"]["size"], "4KiB")
        self.assertEqual(
            config["workloads"],
            ["workloads/monitor_l1d4k", "workloads/victim_l1d4k"],
        )
        self.assertEqual(config["contention"]["epoch_cycles"], 2_000_000)
        self.assertEqual(config["measure_ticks"], 64_000_000_000)

    def test_baseline_profile_preserves_original_timing_and_binaries(self) -> None:
        config = copy.deepcopy(CONFIG)
        apply_experiment_profile(config, "16KiB")

        self.assertEqual(config["l1d"]["size"], "16KiB")
        self.assertEqual(
            config["workloads"],
            ["workloads/monitor", "workloads/victim"],
        )
        self.assertEqual(config["contention"]["epoch_cycles"], 1_000_000)
        self.assertEqual(config["measure_ticks"], 32_000_000_000)


class MechanismOptionTests(unittest.TestCase):
    """Opt-in crossbar knobs for the mechanism study (2026-10-14)."""

    @staticmethod
    def namespace(**overrides) -> argparse.Namespace:
        values = {"l2bus_width": None, "l2bus_header_latency": None,
                  "l2bus_clock": "system", "stats_per_interval": False}
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_defaults_produce_no_mechanism_settings(self) -> None:
        # An ordinary run must not touch any SimObject parameter or metadata key.
        self.assertEqual(mechanism_options(self.namespace()), {})

    def test_non_default_settings_are_all_recorded(self) -> None:
        self.assertEqual(
            mechanism_options(self.namespace(
                l2bus_width=512, l2bus_header_latency=0, l2bus_clock="cpu",
                stats_per_interval=True)),
            {"l2bus_width": 512, "l2bus_header_latency": 0,
             "l2bus_clock": "cpu", "stats_per_interval": True},
        )

    def test_width_parser_accepts_only_listed_widths(self) -> None:
        self.assertEqual(parse_l2bus_width("128"), 128)
        self.assertEqual(parse_l2bus_width("512"), 512)
        for value in ("0", "48", "1024", "bad", "1e2"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_l2bus_width(value)

    def test_header_latency_parser_accepts_zero_or_one(self) -> None:
        self.assertEqual(parse_l2bus_header_latency("0"), 0)
        self.assertEqual(parse_l2bus_header_latency("1"), 1)
        for value in ("2", "-1", "bad"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_l2bus_header_latency(value)

    def test_per_interval_stats_align_with_labelled_intervals(self) -> None:
        config = copy.deepcopy(CONFIG)
        apply_experiment_profile(config, "4KiB")
        # 2,000,000 CPU cycles at 500 ticks per cycle; 64 of them fill the window.
        self.assertEqual(interval_ticks(config), 1_000_000_000)
        config["measure_ticks"] += 1
        with self.assertRaisesRegex(ValueError, "whole number of intervals"):
            interval_ticks(config)


if __name__ == "__main__":
    unittest.main()
