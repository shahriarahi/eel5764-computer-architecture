"""Read-only validation for new TDMA runs; never summarize old folders in place."""
import json
from pathlib import Path
import sys


def scheduler_counters(blocks: list[dict[str, float]], enabled: bool) -> dict[str, float]:
    keys = ("tdmaGrants0", "tdmaGrants1", "tdmaWithheld", "tdmaOverruns",
            "tdmaDownstreamRefusals", "tdmaExpressBypasses", "tdmaReadGrants", "tdmaWritebackGrants")
    if enabled:
        for block in blocks:
            missing = [key for key in keys if "system.l2bus." + key not in block]
            if missing:
                raise ValueError(f"missing enabled TDMA counters: {missing}")
    # Original executable intentionally has none of the new counter schema.
    return {key: sum(b.get("system.l2bus." + key, 0) for b in blocks) for key in keys}


def validate_case(project: Path, case: Path, ways: int, split: bool, slots: int) -> dict:
    sys.path.insert(0, str(project))
    from scripts.run_mechanism import check_outputs, MechItem
    from analysis.summarize_mechanism import read_stats_blocks, PM
    from analysis.analyze_contention import partition_evidence, parse_probe_binary, mapping_evidence

    item = MechItem("std", 0, ways, "treatment" if split else "control")
    problems = check_outputs(case, item)
    if problems:
        raise ValueError(f"{case}: {problems}")
    meta = json.loads((case / "run_meta.json").read_text())
    c = meta["contention"]
    parse_probe_binary(case / "probes.bin", expected_labels=c["activity_labels"],
                       start_cycle=c["start_cycle"], epoch_cycles=c["epoch_cycles"],
                       interval_count=c["interval_count"], set_count=c["llc_sets"])
    blocks = read_stats_blocks(case / "stats.txt.gz")[:64]
    for block in blocks:
        if mapping_evidence(block)["probe_mapping_validation"] != "PASS congruent":
            raise ValueError("mapping gate failed")
        if split and partition_evidence(block, meta["ways"])["isolation_validation"] != "PASS disjoint":
            raise ValueError("per-interval way-isolation gate failed")
    counters = scheduler_counters(blocks, bool(slots))
    if slots:
        config = json.loads((case / "tdma_config.json").read_text())
        if config["slot_cycles"] != slots or set(config["port_domains"]) != {0, 1}:
            raise ValueError("TDMA configuration gate failed")
        if not all(counters[key] > 0 for key in ("tdmaGrants0", "tdmaGrants1", "tdmaWithheld")):
            raise ValueError("missing positive TDMA admission counters")
        if any(counters[key] for key in ("tdmaOverruns", "tdmaDownstreamRefusals", "tdmaExpressBypasses")):
            raise ValueError("TDMA structural gate failed")
    return {"mapping": "PASS", "isolation": "PASS 64/64" if split else "n/a",
            "records": 16384, "tdma_counters": counters}
