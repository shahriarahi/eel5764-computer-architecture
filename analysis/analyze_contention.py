#!/usr/bin/env python3
"""Analyze the simulated monitor/AES contention experiment.

The monitor contributes one latency for each LLC set in each labelled
interval.  Set latencies are averaged within an interval before active and
idle intervals are compared, so the statistical sample is an interval rather
than a set access.

SNR = abs(mean(active) - mean(idle)) / pooled sample standard deviation.
The null distribution comes from balanced interval-label shuffles.  No AES
key material or secret-dependent classification is involved.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
import struct
from pathlib import Path


BEGIN_STATS = "---------- Begin Simulation Statistics ----------"

# Record-free monitor (probe_bin_v2): one little-endian record per set per
# interval, interval-major: u64 timestamp, u32 latency, u16 interval, u16 set.
PROBE_BIN_RECORD = struct.Struct("<QIHH")

# Predeclared co-primary statistic (PREREGISTRATION_V2_20261011.md): a probe
# walk counts as all-hit when it is at most this many cycles above the run's
# 1st-percentile walk time.  One LLC miss adds roughly 120 cycles.
HIT_BAND_CYCLES = 20
HIT_FLOOR_PERCENTILE = 1.0


class AnalysisError(RuntimeError):
    """Raised when an input cannot support the declared analysis."""


def snr(active: list[float], idle: list[float]) -> float:
    """Return absolute mean separation divided by pooled sample deviation."""
    if len(active) < 2 or len(idle) < 2:
        raise AnalysisError("SNR needs at least two active and two idle samples")
    active_var = statistics.variance(active)
    idle_var = statistics.variance(idle)
    degrees = len(active) + len(idle) - 2
    pooled_var = (
        (len(active) - 1) * active_var + (len(idle) - 1) * idle_var
    ) / degrees
    if pooled_var == 0.0:
        raise AnalysisError("pooled standard deviation is zero; SNR is undefined")
    return abs(statistics.mean(active) - statistics.mean(idle)) / math.sqrt(
        pooled_var
    )


def permutation_test(
    samples: list[float],
    labels: list[int],
    permutations: int = 10_000,
    seed: int = 5_764,
) -> dict[str, float | int | bool]:
    """Compare observed SNR with fixed-seed balanced label shuffles."""
    if len(samples) != len(labels):
        raise AnalysisError("sample and label counts differ")
    if set(labels) != {0, 1}:
        raise AnalysisError("labels must contain both 0 and 1 only")
    if permutations <= 0:
        raise AnalysisError("permutations must be positive")

    def grouped(values: list[int]) -> tuple[list[float], list[float]]:
        active = [value for value, label in zip(samples, values) if label == 1]
        idle = [value for value, label in zip(samples, values) if label == 0]
        return active, idle

    observed_active, observed_idle = grouped(labels)
    observed = snr(observed_active, observed_idle)
    rng = random.Random(seed)
    null_values: list[float] = []
    for _ in range(permutations):
        shuffled = labels.copy()
        rng.shuffle(shuffled)
        active, idle = grouped(shuffled)
        null_values.append(snr(active, idle))
    null_values.sort()
    percentile_index = math.ceil(0.95 * permutations) - 1
    threshold = null_values[percentile_index]
    empirical_p = (1 + sum(value >= observed for value in null_values)) / (
        permutations + 1
    )
    return {
        "observed_snr": observed,
        "null_snr_95th": threshold,
        "empirical_p": empirical_p,
        "permutations": permutations,
        "seed": seed,
        "passes_null": observed > threshold and empirical_p < 0.05,
    }


def parse_probe_matrix(
    path: Path,
    *,
    expected_labels: list[int],
    start_cycle: int,
    epoch_cycles: int,
    interval_count: int,
    set_count: int,
) -> tuple[list[list[float]], list[int]]:
    """Validate probe CSV records and return interval-by-set latencies."""
    if len(expected_labels) != interval_count:
        raise AnalysisError("expected label count does not match interval count")
    records: dict[tuple[int, int], float] = {}
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise AnalysisError(f"cannot read {path}: {exc}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.startswith("probe,"):
            continue
        parts = line.split(",")
        if len(parts) != 6:
            raise AnalysisError(f"{path}:{line_number}: malformed probe record")
        try:
            timestamp, interval, label, cache_set, latency = (
                int(value) for value in parts[1:]
            )
        except ValueError as exc:
            raise AnalysisError(
                f"{path}:{line_number}: malformed probe record"
            ) from exc
        if not 0 <= interval < interval_count:
            raise AnalysisError(f"{path}:{line_number}: interval out of range")
        if not 0 <= cache_set < set_count:
            raise AnalysisError(f"{path}:{line_number}: LLC set out of range")
        if label != expected_labels[interval]:
            raise AnalysisError(
                f"{path}:{line_number}: label mismatch for interval {interval}"
            )
        interval_start = start_cycle + interval * epoch_cycles
        if not interval_start <= timestamp < interval_start + epoch_cycles:
            raise AnalysisError(
                f"{path}:{line_number}: timestamp outside interval {interval}"
            )
        if latency < 0:
            raise AnalysisError(f"{path}:{line_number}: negative latency")
        key = (interval, cache_set)
        if key in records:
            raise AnalysisError(
                f"{path}:{line_number}: duplicate probe record for {key}"
            )
        records[key] = float(latency)

    expected_count = interval_count * set_count
    if len(records) != expected_count:
        missing = expected_count - len(records)
        raise AnalysisError(
            f"{path}: missing probe records: expected {expected_count}, "
            f"found {len(records)} (difference {missing})"
        )
    matrix = [
        [records[(interval, cache_set)] for cache_set in range(set_count)]
        for interval in range(interval_count)
    ]
    return matrix, expected_labels.copy()


def parse_probe_binary(
    path: Path,
    *,
    expected_labels: list[int],
    start_cycle: int,
    epoch_cycles: int,
    interval_count: int,
    set_count: int,
) -> tuple[list[list[float]], list[int]]:
    """Validate a probe_bin_v2 file and return interval-by-set latencies."""
    if len(expected_labels) != interval_count:
        raise AnalysisError("expected label count does not match interval count")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise AnalysisError(f"cannot read {path}: {exc}") from exc
    expected_bytes = interval_count * set_count * PROBE_BIN_RECORD.size
    if len(data) != expected_bytes:
        raise AnalysisError(
            f"{path}: expected {expected_bytes} bytes, found {len(data)}"
        )
    matrix: list[list[float]] = []
    offset = 0
    for interval in range(interval_count):
        interval_start = start_cycle + interval * epoch_cycles
        row: list[float] = []
        for cache_set in range(set_count):
            timestamp, latency, record_interval, record_set = (
                PROBE_BIN_RECORD.unpack_from(data, offset)
            )
            offset += PROBE_BIN_RECORD.size
            if record_interval != interval or record_set != cache_set:
                raise AnalysisError(
                    f"{path}: record {interval * set_count + cache_set} is "
                    f"interval {record_interval} set {record_set}, expected "
                    f"interval {interval} set {cache_set}"
                )
            if not interval_start <= timestamp < interval_start + epoch_cycles:
                raise AnalysisError(
                    f"{path}: timestamp outside interval {interval} "
                    f"for set {cache_set}"
                )
            row.append(float(latency))
        matrix.append(row)
    return matrix, expected_labels.copy()


def percentile(values: list[float], percent: float) -> float:
    """Linear-interpolation percentile (numpy's default method)."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100.0
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def hit_only_test(
    matrix: list[list[float]],
    labels: list[int],
    monitor_ways: int,
    permutations: int = 10_000,
    seed: int = 5_764,
) -> dict[str, object]:
    """Co-primary test on per-interval means of all-hit probe walks only."""
    floor = percentile(
        [value for row in matrix for value in row], HIT_FLOOR_PERCENTILE
    )
    limit = floor + HIT_BAND_CYCLES
    interval_means: list[float] = []
    hit_records = 0
    for interval, row in enumerate(matrix):
        hits = [value for value in row if value <= limit]
        if not hits:
            raise AnalysisError(f"interval {interval} has no all-hit probe walks")
        hit_records += len(hits)
        interval_means.append(statistics.mean(hits))
    test = permutation_test(interval_means, labels, permutations, seed)
    active = [v for v, label in zip(interval_means, labels) if label == 1]
    idle = [v for v, label in zip(interval_means, labels) if label == 0]
    total = sum(len(row) for row in matrix)
    return {
        "hit_only_walk_floor_cycles": floor,
        "hit_only_band_cycles": HIT_BAND_CYCLES,
        "all_hit_record_fraction": hit_records / total,
        "hit_only_snr": test["observed_snr"],
        "hit_only_p": test["empirical_p"],
        "hit_only_delta_per_line": (
            (statistics.mean(active) - statistics.mean(idle)) / monitor_ways
        ),
        "hit_only_distinguishable": bool(test["passes_null"]),
        "hit_only_interval_means": interval_means,
    }


def parse_probe_log(
    path: Path,
    *,
    expected_labels: list[int],
    start_cycle: int,
    epoch_cycles: int,
    interval_count: int,
    set_count: int,
) -> tuple[list[float], list[int]]:
    """Validate probe CSV records and return one mean per interval."""
    matrix, labels = parse_probe_matrix(
        path,
        expected_labels=expected_labels,
        start_cycle=start_cycle,
        epoch_cycles=epoch_cycles,
        interval_count=interval_count,
        set_count=set_count,
    )
    return [statistics.mean(row) for row in matrix], labels


def max_set_permutation_test(
    matrix: list[list[float]],
    labels: list[int],
    permutations: int = 10_000,
    seed: int = 5_764,
) -> dict[str, float | int | bool]:
    """Test the maximum per-set SNR against maxima from label shuffles."""
    if len(matrix) != len(labels) or not matrix:
        raise AnalysisError("probe matrix and label counts differ or are empty")
    if set(labels) != {0, 1}:
        raise AnalysisError("labels must contain both 0 and 1 only")
    if permutations <= 0:
        raise AnalysisError("permutations must be positive")
    set_count = len(matrix[0])
    if set_count == 0 or any(len(row) != set_count for row in matrix):
        raise AnalysisError("probe matrix rows have inconsistent set counts")

    columns = [
        [matrix[interval][cache_set] for interval in range(len(matrix))]
        for cache_set in range(set_count)
    ]
    eligible: list[tuple[int, list[float], float, float]] = []
    for cache_set, column in enumerate(columns):
        total = sum(column)
        total_squares = sum(value * value for value in column)
        if total_squares - total * total / len(column) > 0.0:
            eligible.append((cache_set, column, total, total_squares))
    if not eligible:
        raise AnalysisError("all LLC-set latency series are constant")

    active_count = labels.count(1)
    idle_count = labels.count(0)
    if active_count < 2 or idle_count < 2:
        raise AnalysisError("max-set SNR needs at least two intervals per label")

    def score(
        column: list[float],
        total: float,
        total_squares: float,
        active_indices: list[int],
    ) -> float:
        active_sum = sum(column[index] for index in active_indices)
        active_squares = sum(column[index] ** 2 for index in active_indices)
        idle_sum = total - active_sum
        idle_squares = total_squares - active_squares
        active_mean = active_sum / active_count
        idle_mean = idle_sum / idle_count
        active_var = max(
            0.0,
            (active_squares - active_sum * active_sum / active_count)
            / (active_count - 1),
        )
        idle_var = max(
            0.0,
            (idle_squares - idle_sum * idle_sum / idle_count)
            / (idle_count - 1),
        )
        pooled_var = (
            (active_count - 1) * active_var + (idle_count - 1) * idle_var
        ) / (active_count + idle_count - 2)
        difference = abs(active_mean - idle_mean)
        if pooled_var == 0.0:
            return 0.0 if difference == 0.0 else math.inf
        return difference / math.sqrt(pooled_var)

    observed_indices = [index for index, label in enumerate(labels) if label == 1]
    observed_scores = [
        (score(column, total, total_squares, observed_indices), cache_set)
        for cache_set, column, total, total_squares in eligible
    ]
    observed, observed_set = max(observed_scores)
    observed_column = columns[observed_set]
    observed_active = [
        value for value, label in zip(observed_column, labels) if label == 1
    ]
    observed_idle = [
        value for value, label in zip(observed_column, labels) if label == 0
    ]

    rng = random.Random(seed)
    null_values: list[float] = []
    shuffled = labels.copy()
    for _ in range(permutations):
        rng.shuffle(shuffled)
        active_indices = [
            index for index, label in enumerate(shuffled) if label == 1
        ]
        null_values.append(max(
            score(column, total, total_squares, active_indices)
            for _, column, total, total_squares in eligible
        ))
    null_values.sort()
    threshold = null_values[math.ceil(0.95 * permutations) - 1]
    empirical_p = (1 + sum(value >= observed for value in null_values)) / (
        permutations + 1
    )
    return {
        "observed_max_snr": observed,
        "observed_max_set": observed_set,
        "max_set_mean_active_cycles": statistics.mean(observed_active),
        "max_set_mean_idle_cycles": statistics.mean(observed_idle),
        "eligible_nonconstant_sets": len(eligible),
        "null_max_snr_95th": threshold,
        "empirical_p": empirical_p,
        "permutations": permutations,
        "seed": seed,
        "passes_null": observed > threshold and empirical_p < 0.05,
    }


def validate_schedule_headers(path: Path, expected_labels: list[int]) -> None:
    """Require victim, monitor, and metadata to declare one identical schedule."""
    expected = "".join(str(label) for label in expected_labels)
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise AnalysisError(f"cannot read {path}: {exc}") from exc
    for workload in ("victim", "monitor"):
        headers = [
            line for line in lines
            if line.startswith(f"{workload} ") and "labels=" in line
        ]
        if len(headers) != 1:
            raise AnalysisError(
                f"{path}: expected one {workload} label schedule header"
            )
        declared = headers[0].split("labels=", 1)[1].split()[0]
        if declared != expected:
            raise AnalysisError(f"{path}: {workload} label schedule mismatch")


def parse_workload_metadata(
    path: Path, *, expected_monitor_ways: int, expected_workload_seed: int,
    active_cycles: int
) -> dict[str, int | float]:
    """Extract monitor depth and AES useful-work throughput from simout."""
    try:
        text = path.read_text()
    except OSError as exc:
        raise AnalysisError(f"cannot read {path}: {exc}") from exc
    monitor = re.findall(
        r"^monitor format=probe_(?:csv_v1|bin_v2) .*\bways=(\d+)\b",
        text,
        re.MULTILINE,
    )
    if len(monitor) != 1 or int(monitor[0]) != expected_monitor_ways:
        raise AnalysisError(
            f"{path}: monitor depth does not match {expected_monitor_ways}"
        )
    seeds = re.findall(
        r"^victim aes_self_test=PASS .*\bplaintext_seed=(\d+)\b",
        text,
        re.MULTILINE,
    )
    if len(seeds) != 1 or int(seeds[0]) != expected_workload_seed:
        raise AnalysisError(
            f"{path}: victim seed does not match {expected_workload_seed}"
        )
    completions = re.findall(
        r"^victim measurement_complete encryptions=(\d+)\b",
        text,
        re.MULTILINE,
    )
    if len(completions) != 1:
        raise AnalysisError(f"{path}: expected one victim completion record")
    encryptions = int(completions[0])
    if encryptions <= 0:
        raise AnalysisError(f"{path}: AES completed no encryptions")
    return {
        "workload_seed": expected_workload_seed,
        "aes_encryptions": encryptions,
        "aes_cycles_per_encryption": active_cycles / encryptions,
    }


def read_measurement_stats(path: Path) -> tuple[dict[str, float], int]:
    """Return the first measurement-only stats block and total block count."""
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        raise AnalysisError(f"cannot read {path}: {exc}") from exc
    block_count = sum(line.startswith(BEGIN_STATS) for line in lines)
    if block_count not in (1, 2):
        raise AnalysisError(
            f"{path}: expected one measurement block and at most one automatic "
            f"final block, found {block_count}"
        )
    stats: dict[str, float] = {}
    inside = False
    for line in lines:
        if line.startswith(BEGIN_STATS):
            inside = True
            continue
        if inside and line.startswith("---------- End Simulation Statistics"):
            break
        if not inside:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            stats[parts[0]] = float(parts[1])
        except ValueError:
            continue

    return stats, block_count


def partition_evidence(
    stats: dict[str, float], ways: dict[str, list[int]]
) -> dict[str, int | str]:
    """Validate measured tag occupancy against the configured way allocation."""
    prefix = "system.llc.partitioning_manager."
    if not any(
        f"{prefix}wayOccupancy_p{partition}::way{way}" in stats
        for partition in (0, 1)
        for way in range(16)
    ):
        raise AnalysisError("partitioned result has no way-occupancy statistics")

    allowed = (
        set(ways["partition0_monitor"]),
        set(ways["partition1_aes"]),
    )
    occupancy = {
        partition: [
            int(stats.get(f"{prefix}wayOccupancy_p{partition}::way{way}", 0.0))
            for way in range(16)
        ]
        for partition in (0, 1)
    }
    other = [
        int(stats.get(f"{prefix}wayOccupancy_other::way{way}", 0.0))
        for way in range(16)
    ]
    violations = sum(
        count
        for partition in (0, 1)
        for way, count in enumerate(occupancy[partition])
        if way not in allowed[partition]
    ) + sum(other)
    unmapped = int(stats.get(f"{prefix}unmappedLookups", 0.0))
    conflicts = int(stats.get(f"{prefix}addrPartitionConflicts", 0.0))
    blocks = (sum(occupancy[0]), sum(occupancy[1]))
    passed = (
        violations == 0
        and unmapped == 0
        and conflicts == 0
        and blocks[0] > 0
        and blocks[1] > 0
    )
    return {
        "isolation_validation": "PASS disjoint" if passed else "FAIL",
        "isolation_violations": violations,
        "unmapped_lookups": unmapped,
        "addr_partition_conflicts": conflicts,
        "llc_blocks_partition0_monitor": blocks[0],
        "llc_blocks_partition1_aes": blocks[1],
    }


def mapping_evidence(stats: dict[str, float]) -> dict[str, int | str]:
    """Validate that each logical monitor set maps to one physical LLC set."""
    prefix = "system.llc.partitioning_manager."
    required = (
        "probeAddressLookups",
        "probeMissingVaddr",
        "probeSetMappingMismatches",
        "probeSetRotation",
    )
    missing = [name for name in required if f"{prefix}{name}" not in stats]
    if missing:
        raise AnalysisError(
            "result has no probe-address mapping statistics: "
            + ", ".join(missing)
        )
    lookups = int(stats[f"{prefix}probeAddressLookups"])
    missing_vaddr = int(stats[f"{prefix}probeMissingVaddr"])
    mismatches = int(stats[f"{prefix}probeSetMappingMismatches"])
    rotation = int(stats[f"{prefix}probeSetRotation"])
    passed = lookups > 0 and missing_vaddr == 0 and mismatches == 0
    return {
        "probe_mapping_validation": "PASS congruent" if passed else "FAIL",
        "probe_address_lookups": lookups,
        "probe_missing_vaddr": missing_vaddr,
        "probe_set_mapping_mismatches": mismatches,
        "probe_set_rotation": rotation,
    }
def parse_gem5_stats(path: Path) -> dict[str, float]:
    """Read metrics from the first, measurement-only statistics block."""
    stats, block_count = read_measurement_stats(path)

    def required(name: str) -> float:
        try:
            return stats[name]
        except KeyError as exc:
            raise AnalysisError(f"{path}: required statistic '{name}' missing") from exc

    required("system.llc.demandAccesses::total")
    metrics: dict[str, float] = {"stats_blocks": block_count}
    for core in (0, 1):
        metrics[f"ipc_core{core}"] = required(f"system.cpu{core}.ipc")
        accesses = sum(
            stats.get(f"system.llc.demandAccesses::cpu{core}.{port}", 0.0)
            for port in ("inst", "data")
        )
        misses = sum(
            stats.get(f"system.llc.demandMisses::cpu{core}.{port}", 0.0)
            for port in ("inst", "data")
        )
        metrics[f"llc_miss_rate_core{core}"] = (
            misses / accesses if accesses > 0 else math.nan
        )
        metrics[f"llc_accesses_core{core}"] = int(accesses)
        metrics[f"llc_misses_core{core}"] = int(misses)
    return metrics


def analyze(results: Path, statistic: str = "interval-mean") -> dict[str, object]:
    """Validate one contention result directory and write its derived result."""
    meta_path = results / "run_meta.json"
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise AnalysisError(f"cannot read valid {meta_path}: {exc}") from exc
    try:
        contention = meta["contention"]
        labels = [int(value) for value in contention["activity_labels"]]
        start_cycle = int(contention["start_cycle"])
        epoch_cycles = int(contention["epoch_cycles"])
        interval_count = int(contention["interval_count"])
        set_count = int(contention["llc_sets"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AnalysisError(f"{meta_path}: malformed contention metadata") from exc
    if labels.count(0) != labels.count(1) or labels.count(0) * 2 != len(labels):
        raise AnalysisError(f"{meta_path}: activity labels are not balanced")

    simout = results / "simout.txt"
    validate_schedule_headers(simout, labels)
    sink = meta.get("monitor_sink", "memory")
    if sink not in ("memory", "file"):
        raise AnalysisError(f"{meta_path}: unknown monitor_sink {sink!r}")
    probe_source = (
        results / str(meta.get("probe_file")) if sink == "file" else simout
    )
    parse = parse_probe_binary if sink == "file" else parse_probe_matrix
    matrix, parsed_labels = parse(
        probe_source,
        expected_labels=labels,
        start_cycle=start_cycle,
        epoch_cycles=epoch_cycles,
        interval_count=interval_count,
        set_count=set_count,
    )
    samples = [statistics.mean(row) for row in matrix]
    active = [value for value, label in zip(samples, parsed_labels) if label == 1]
    idle = [value for value, label in zip(samples, parsed_labels) if label == 0]
    if statistic == "interval-mean":
        test = permutation_test(samples, parsed_labels)
        aggregation = "mean latency across 256 LLC sets per interval"
    elif statistic == "max-set":
        test = max_set_permutation_test(matrix, parsed_labels)
        aggregation = (
            "maximum per-set SNR; shuffled null recomputes the maximum "
            "across all nonconstant sets"
        )
    else:
        raise AnalysisError(f"unknown statistic: {statistic}")
    stats_path = results / "stats.txt"
    result: dict[str, object] = {
        "split": meta.get("split"),
        "monitor_ways": meta.get("monitor_ways"),
        "l1d_size": meta.get("config", {}).get("l1d", {}).get("size"),
        "statistic": statistic,
        "snr_formula": (
            "abs(mean(active)-mean(idle))/pooled_sample_standard_deviation"
        ),
        "aggregation": aggregation,
        "filtering": "none; all post-warm-up intervals are used",
        "active_intervals": len(active),
        "idle_intervals": len(idle),
        "mean_active_cycles": statistics.mean(active),
        "mean_idle_cycles": statistics.mean(idle),
        **test,
        **parse_gem5_stats(stats_path),
    }
    monitor_ways = meta.get("monitor_ways")
    if not isinstance(monitor_ways, int):
        raise AnalysisError(f"{meta_path}: missing integer monitor_ways")
    workload_seed = meta.get("workload_seed")
    if not isinstance(workload_seed, int):
        raise AnalysisError(f"{meta_path}: missing integer workload_seed")
    result.update(parse_workload_metadata(
        simout,
        expected_monitor_ways=monitor_ways,
        expected_workload_seed=workload_seed,
        active_cycles=labels.count(1) * epoch_cycles,
    ))
    measurement_stats, _ = read_measurement_stats(stats_path)
    result.update(mapping_evidence(measurement_stats))
    ways = meta.get("ways")
    if ways is not None:
        result.update(partition_evidence(measurement_stats, ways))
    if sink == "file":
        # Record-free runs carry the predeclared co-primary statistic.
        result["monitor_sink"] = sink
        try:
            result.update(hit_only_test(matrix, parsed_labels, monitor_ways))
            result["hit_only_error"] = None
        except AnalysisError as exc:
            # e.g. an A=16 diagnostic with no all-hit walk in some interval;
            # the v2 summarizer refuses matched runs that lack the statistic.
            result["hit_only_error"] = str(exc)
    result["distinguishable"] = bool(test["passes_null"])
    result["decision"] = "PASS" if test["passes_null"] else "FAIL"
    output_path = results / "analysis.json"
    output_path.write_text(json.dumps(result, indent=2, allow_nan=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument(
        "--statistic", choices=("interval-mean", "max-set"),
        default="interval-mean",
    )
    args = parser.parse_args()
    result = analyze(args.results, statistic=args.statistic)
    if args.statistic == "max-set":
        print(
            f"{result['decision']} split={result['split']} "
            f"max_set={result['observed_max_set']} "
            f"max_snr={result['observed_max_snr']:.6f} "
            f"null_max95={result['null_max_snr_95th']:.6f} "
            f"p={result['empirical_p']:.6f} "
            f"n_active={result['active_intervals']} "
            f"n_idle={result['idle_intervals']}"
        )
    else:
        print(
            f"{result['decision']} split={result['split']} "
            f"snr={result['observed_snr']:.6f} "
            f"null95={result['null_snr_95th']:.6f} "
            f"p={result['empirical_p']:.6f} "
            f"n_active={result['active_intervals']} "
            f"n_idle={result['idle_intervals']}"
        )
    print(
        f"ipc0={result['ipc_core0']:.6f} ipc1={result['ipc_core1']:.6f} "
        f"mr0={result['llc_miss_rate_core0']:.6f} "
        f"mr1={result['llc_miss_rate_core1']:.6f}"
    )
    print(f"wrote {args.results / 'analysis.json'}")


if __name__ == "__main__":
    try:
        main()
    except AnalysisError as exc:
        raise SystemExit(f"error: {exc}") from exc
