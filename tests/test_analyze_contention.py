import json
import math
import tempfile
import unittest
from pathlib import Path

from analysis.analyze_contention import (
    AnalysisError,
    max_set_permutation_test,
    mapping_evidence,
    partition_evidence,
    parse_gem5_stats,
    parse_probe_matrix,
    parse_probe_log,
    parse_workload_metadata,
    permutation_test,
    snr,
    validate_schedule_headers,
)


class SnrTests(unittest.TestCase):
    def test_snr_uses_pooled_sample_standard_deviation(self) -> None:
        self.assertEqual(snr([1.0, 2.0, 3.0], [3.0, 4.0, 5.0]), 2.0)

    def test_snr_rejects_zero_pooled_variance(self) -> None:
        with self.assertRaisesRegex(AnalysisError, "pooled standard deviation is zero"):
            snr([1.0, 1.0], [2.0, 2.0])

    def test_permutation_test_is_reproducible_and_seeded(self) -> None:
        samples = [9.0, 10.0, 11.0, 0.0, 1.0, 2.0, 8.0, 3.0]
        labels = [1, 1, 1, 0, 0, 0, 1, 0]
        first = permutation_test(samples, labels, permutations=200, seed=5764)
        again = permutation_test(samples, labels, permutations=200, seed=5764)
        other_seed = permutation_test(samples, labels, permutations=200, seed=5765)
        self.assertEqual(first, again)
        self.assertNotEqual(first["empirical_p"], other_seed["empirical_p"])
        self.assertAlmostEqual(
            first["observed_snr"], 8.0 / math.sqrt(5.0 / 3.0)
        )
        self.assertEqual(first["permutations"], 200)
        self.assertEqual(first["seed"], 5764)
        self.assertGreater(first["empirical_p"], 0.0)


class ProbeLogTests(unittest.TestCase):
    LABELS = [0, 1, 1, 0]

    def write_log(self, lines: list[str]) -> Path:
        temp = tempfile.NamedTemporaryFile("w", delete=False, newline="")
        with temp:
            temp.write("monitor format=probe_csv_v1\n")
            temp.writelines(lines)
        self.addCleanup(Path(temp.name).unlink, missing_ok=True)
        return Path(temp.name)

    def complete_lines(self) -> list[str]:
        lines = []
        for interval, label in enumerate(self.LABELS):
            for cache_set in range(3):
                timestamp = 1_000 + interval * 100 + cache_set
                latency = 10 * (interval + 1) + cache_set
                lines.append(
                    f"probe,{timestamp},{interval},{label},{cache_set},{latency}\n"
                )
        return lines

    def parse(self, path: Path) -> tuple[list[float], list[int]]:
        return parse_probe_log(
            path,
            expected_labels=self.LABELS,
            start_cycle=1_000,
            epoch_cycles=100,
            interval_count=4,
            set_count=3,
        )

    def test_complete_log_returns_interval_means(self) -> None:
        samples, labels = self.parse(self.write_log(self.complete_lines()))
        self.assertEqual(samples, [11.0, 21.0, 31.0, 41.0])
        self.assertEqual(labels, self.LABELS)

    def test_complete_log_returns_interval_by_set_matrix(self) -> None:
        matrix, labels = parse_probe_matrix(
            self.write_log(self.complete_lines()),
            expected_labels=self.LABELS,
            start_cycle=1_000,
            epoch_cycles=100,
            interval_count=4,
            set_count=3,
        )
        self.assertEqual(matrix[0], [10.0, 11.0, 12.0])
        self.assertEqual(matrix[3], [40.0, 41.0, 42.0])
        self.assertEqual(labels, self.LABELS)

    def test_duplicate_interval_set_pair_is_rejected(self) -> None:
        lines = self.complete_lines()
        lines.append(lines[0])
        with self.assertRaisesRegex(AnalysisError, "duplicate probe record"):
            self.parse(self.write_log(lines))

    def test_missing_interval_set_pair_is_rejected(self) -> None:
        with self.assertRaisesRegex(AnalysisError, "missing probe records"):
            self.parse(self.write_log(self.complete_lines()[:-1]))

    def test_mismatched_public_label_is_rejected(self) -> None:
        lines = self.complete_lines()
        lines[0] = lines[0].replace(
            "probe,1000,0,0,0,10", "probe,1000,0,1,0,10"
        )
        with self.assertRaisesRegex(AnalysisError, "label mismatch"):
            self.parse(self.write_log(lines))

    def test_timestamp_outside_declared_interval_is_rejected(self) -> None:
        lines = self.complete_lines()
        lines[0] = lines[0].replace("probe,1000", "probe,1100")
        with self.assertRaisesRegex(AnalysisError, "outside interval"):
            self.parse(self.write_log(lines))

    def test_non_numeric_record_is_rejected(self) -> None:
        lines = self.complete_lines()
        lines[0] = lines[0].replace(",10\n", ",not-a-number\n")
        with self.assertRaisesRegex(AnalysisError, "malformed probe record"):
            self.parse(self.write_log(lines))

    def test_victim_monitor_and_metadata_schedules_must_match(self) -> None:
        path = self.write_log([
            "victim aes_self_test=PASS labels=0110\n",
            "monitor format=probe_csv_v1 labels=0110\n",
        ])
        validate_schedule_headers(path, self.LABELS)

        mismatch = self.write_log([
            "victim aes_self_test=PASS labels=0100\n",
            "monitor format=probe_csv_v1 labels=0110\n",
        ])
        with self.assertRaisesRegex(AnalysisError, "victim label schedule mismatch"):
            validate_schedule_headers(mismatch, self.LABELS)

    def test_workload_metadata_extracts_depth_and_aes_throughput(self) -> None:
        path = self.write_log([
            "monitor format=probe_csv_v1 intervals=64 sets=256 ways=4 labels=0110\n",
            "victim aes_self_test=PASS key=public plaintext_seed=1466213861 labels=0110\n",
            "victim measurement_complete encryptions=25000 sink=7\n",
        ])

        metadata = parse_workload_metadata(
            path, expected_monitor_ways=4,
            expected_workload_seed=1466213861, active_cycles=64_000_000
        )

        self.assertEqual(metadata["workload_seed"], 1466213861)
        self.assertEqual(metadata["aes_encryptions"], 25000)
        self.assertEqual(metadata["aes_cycles_per_encryption"], 2560.0)

    def test_workload_metadata_rejects_wrong_monitor_depth(self) -> None:
        path = self.write_log([
            "monitor format=probe_csv_v1 intervals=64 sets=256 ways=16 labels=0110\n",
            "victim aes_self_test=PASS key=public plaintext_seed=1466213861 labels=0110\n",
            "victim measurement_complete encryptions=25000 sink=7\n",
        ])

        with self.assertRaisesRegex(AnalysisError, "monitor depth"):
            parse_workload_metadata(
                path, expected_monitor_ways=4,
                expected_workload_seed=1466213861, active_cycles=64_000_000
            )

    def test_workload_metadata_rejects_wrong_victim_seed(self) -> None:
        path = self.write_log([
            "monitor format=probe_csv_v1 intervals=64 sets=256 ways=4 labels=0110\n",
            "victim aes_self_test=PASS key=public plaintext_seed=1466213862 labels=0110\n",
            "victim measurement_complete encryptions=25000 sink=7\n",
        ])

        with self.assertRaisesRegex(AnalysisError, "victim seed"):
            parse_workload_metadata(
                path, expected_monitor_ways=4,
                expected_workload_seed=1466213861, active_cycles=64_000_000
            )


class Gem5StatsTests(unittest.TestCase):
    def test_single_measurement_block_returns_ipc_and_miss_rates(self) -> None:
        text = """---------- Begin Simulation Statistics ----------
system.cpu0.ipc 0.5
system.cpu1.ipc 0.25
system.llc.demandAccesses::total 100
system.llc.demandAccesses::cpu0.inst 10
system.llc.demandAccesses::cpu0.data 30
system.llc.demandMisses::cpu0.data 8
system.llc.demandAccesses::cpu1.inst 20
system.llc.demandAccesses::cpu1.data 40
system.llc.demandMisses::cpu1.inst 2
system.llc.demandMisses::cpu1.data 10
---------- End Simulation Statistics   ----------
"""
        with tempfile.NamedTemporaryFile("w", delete=False) as temp:
            temp.write(text)
        path = Path(temp.name)
        self.addCleanup(path.unlink, missing_ok=True)
        metrics = parse_gem5_stats(path)
        self.assertEqual(metrics["ipc_core0"], 0.5)
        self.assertEqual(metrics["ipc_core1"], 0.25)
        self.assertEqual(metrics["llc_miss_rate_core0"], 0.2)
        self.assertEqual(metrics["llc_miss_rate_core1"], 0.2)

    def test_first_of_two_stats_blocks_is_the_measurement_window(self) -> None:
        block = """---------- Begin Simulation Statistics ----------
system.cpu0.ipc {ipc0}
system.cpu1.ipc {ipc1}
system.llc.demandAccesses::total 10
system.llc.demandAccesses::cpu0.data 5
system.llc.demandMisses::cpu0.data 1
system.llc.demandAccesses::cpu1.data 5
system.llc.demandMisses::cpu1.data 2
---------- End Simulation Statistics   ----------
"""
        text = block.format(ipc0="0.5", ipc1="0.25") + block.format(
            ipc0="0.9", ipc1="0.8"
        )
        with tempfile.NamedTemporaryFile("w", delete=False) as temp:
            temp.write(text)
        path = Path(temp.name)
        self.addCleanup(path.unlink, missing_ok=True)
        metrics = parse_gem5_stats(path)
        self.assertEqual(metrics["ipc_core0"], 0.5)
        self.assertEqual(metrics["ipc_core1"], 0.25)


class MaxSetStatisticTests(unittest.TestCase):
    def test_max_set_statistic_finds_localized_signal(self) -> None:
        labels = [1, 1, 1, 1, 0, 0, 0, 0]
        matrix = [
            [9.0, 1.0],
            [10.0, 2.0],
            [11.0, 1.0],
            [8.0, 2.0],
            [0.0, 1.0],
            [1.0, 2.0],
            [2.0, 1.0],
            [3.0, 2.0],
        ]
        result = max_set_permutation_test(
            matrix, labels, permutations=200, seed=5764
        )
        self.assertEqual(result["observed_max_set"], 0)
        self.assertAlmostEqual(
            result["observed_max_snr"], 8.0 / math.sqrt(5.0 / 3.0)
        )
        self.assertEqual(result["permutations"], 200)
        self.assertEqual(result["seed"], 5764)
        self.assertGreater(result["null_max_snr_95th"], 0.0)


class PartitionEvidenceTests(unittest.TestCase):
    def test_disjoint_occupancy_passes_with_blocks_in_allowed_ways(self) -> None:
        stats = {
            "system.llc.partitioning_manager.wayOccupancy_p0::way0": 3.0,
            "system.llc.partitioning_manager.wayOccupancy_p1::way1": 5.0,
            "system.llc.partitioning_manager.unmappedLookups": 0.0,
            "system.llc.partitioning_manager.addrPartitionConflicts": 0.0,
        }
        ways = {
            "partition0_monitor": [0],
            "partition1_aes": list(range(1, 16)),
        }

        evidence = partition_evidence(stats, ways)

        self.assertEqual(evidence["isolation_validation"], "PASS disjoint")
        self.assertEqual(evidence["isolation_violations"], 0)
        self.assertEqual(evidence["llc_blocks_partition0_monitor"], 3)
        self.assertEqual(evidence["llc_blocks_partition1_aes"], 5)

    def test_block_in_forbidden_way_fails_with_exact_violation_count(self) -> None:
        stats = {
            "system.llc.partitioning_manager.wayOccupancy_p0::way0": 3.0,
            "system.llc.partitioning_manager.wayOccupancy_p0::way2": 2.0,
            "system.llc.partitioning_manager.wayOccupancy_p1::way1": 5.0,
            "system.llc.partitioning_manager.unmappedLookups": 0.0,
            "system.llc.partitioning_manager.addrPartitionConflicts": 0.0,
        }
        ways = {
            "partition0_monitor": [0],
            "partition1_aes": list(range(1, 16)),
        }

        evidence = partition_evidence(stats, ways)

        self.assertEqual(evidence["isolation_validation"], "FAIL")
        self.assertEqual(evidence["isolation_violations"], 2)


class ProbeMappingEvidenceTests(unittest.TestCase):
    def test_constant_virtual_to_physical_set_rotation_passes(self) -> None:
        stats = {
            "system.llc.partitioning_manager.probeAddressLookups": 4096.0,
            "system.llc.partitioning_manager.probeMissingVaddr": 0.0,
            "system.llc.partitioning_manager.probeSetMappingMismatches": 0.0,
            "system.llc.partitioning_manager.probeSetRotation": 64.0,
        }

        evidence = mapping_evidence(stats)

        self.assertEqual(evidence["probe_mapping_validation"], "PASS congruent")
        self.assertEqual(evidence["probe_set_rotation"], 64)

    def test_any_mapping_mismatch_fails(self) -> None:
        stats = {
            "system.llc.partitioning_manager.probeAddressLookups": 4096.0,
            "system.llc.partitioning_manager.probeMissingVaddr": 0.0,
            "system.llc.partitioning_manager.probeSetMappingMismatches": 1.0,
            "system.llc.partitioning_manager.probeSetRotation": 64.0,
        }

        evidence = mapping_evidence(stats)

        self.assertEqual(evidence["probe_mapping_validation"], "FAIL")


if __name__ == "__main__":
    unittest.main()
