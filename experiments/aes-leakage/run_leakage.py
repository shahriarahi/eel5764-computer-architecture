"""gem5 configuration adapter for the AES leakage-attribution experiment.

SIMULATOR ONLY (gem5 v25.1.0.1, RISC-V SE mode, public test key).

Follows experiments/tdma/run_contention_tdma.py: the frozen
configs/run_contention.py is loaded with importlib WITHOUT running its main,
a few of its tables are overridden, and m5.instantiate is wrapped so that
parameters can be set once the original config has built the system.  The
original file is never edited.

What the adapter changes
  * EXPERIMENT_PROFILES["4KiB"]: workloads -> absolute paths of monitor_leak
    and the chosen AES build; epoch_cycles = W
  * CONFIG["contention"]["interval_count"] = N_WIN (from build_manifest.json)
  * MONITOR_VARIANT_BINARIES["v3"] (and the "file" sink entry) -> monitor_leak
  * before instantiate: system.llc.partitioning_manager gets victim_requestor_name,
    victim_vaddr_base/size, victim_set_count (from nm of the AES binary), and
    leak_config.json is written to the output directory
  It refuses to run on a gem5 binary that lacks the victim_* parameters, on a
  build made with -DLEAK_FAKE_CLOCK, and on a binary whose sha256 differs from
  build_manifest.json.

Recommended invocation (see README.md for the phases):
  gem5.opt --debug-flags=VictimTable --debug-file=victim_table.trace -d <out> \\
      experiments/aes-leakage/run_leakage.py --victim-variant r1-scrub \\
      --build-dir experiments/aes-leakage/build/n20 \\
      --split off --monitor-ways 16
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import write_manifest  # noqa: E402  (table_layout / nm helpers)

VICTIM_REQUESTOR = "cpu1.data"          # core 1 runs the AES workload
MONITOR_BINARY = "monitor_leak"
VARIANTS = {
    "r1-scrub": {"binary": "victim_leak_r1_scrub",
                 "rounds1": 1, "scrub": 1, "tvla": 0},
    "full-scrub": {"binary": "victim_leak_full_scrub",
                   "rounds1": 0, "scrub": 1, "tvla": 0},
    "full-noscrub": {"binary": "victim_leak_full_noscrub",
                     "rounds1": 0, "scrub": 0, "tvla": 0},
    "tvla": {"binary": "victim_leak_tvla",
             "rounds1": 0, "scrub": 1, "tvla": 1},
}
FORCED = {"--l1d-size": "4KiB", "--monitor-sink": "file",
          "--monitor-variant": "v3"}


class AdapterError(Exception):
    """The run must not start (wrong build, wrong gem5, conflicting flags)."""


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(build_dir):
    """build_manifest.json of a build.sh output directory, validated."""
    build_dir = Path(build_dir)
    path = build_dir / "build_manifest.json"
    if not path.is_file():
        raise AdapterError("%s has no build_manifest.json (run build.sh)" %
                           build_dir)
    manifest = json.loads(path.read_text())
    if "-DLEAK_FAKE_CLOCK" in manifest.get("defines", []):
        raise AdapterError(
            "%s was built with -DLEAK_FAKE_CLOCK (qemu-user tests only); "
            "rebuild with build.sh and no EXTRA_DEFS" % build_dir)
    for name, info in manifest["binaries"].items():
        binary = build_dir / name
        if not binary.is_file():
            raise AdapterError("%s is missing from %s" % (name, build_dir))
        if _sha256(binary) != info["sha256"]:
            raise AdapterError(
                "%s: sha256 differs from build_manifest.json (the binary was "
                "rebuilt or modified after the manifest was written)" % name)
    return manifest


def victim_layout(victim_path):
    """Line layout of te0..te3 and sbox in the AES binary, from nm."""
    nm = os.environ.get("NM", "riscv64-linux-gnu-nm")
    symbols = write_manifest.nm_symbols(nm, victim_path, write_manifest.TABLES)
    return write_manifest.table_layout(symbols)


def build_leak_config(manifest, variant, layout, workload_seed, split,
                      monitor_ways, build_dir):
    """Everything the analysis needs to know about a run, as plain JSON."""
    v = VARIANTS[variant]
    s = manifest["schedule"]
    binaries = manifest["binaries"]
    return {
        "format": "aes-leakage-config-v1",
        "key_hex": manifest["key_hex"],
        "workload_seed": workload_seed,
        "N_WIN": manifest["n_win"],
        "T0": s["T0"], "W": s["W"],
        "OFF_PRIME": s["OFF_PRIME"], "OFF_ENC": s["OFF_ENC"],
        "OFF_ENC_END": s["OFF_ENC_END"], "OFF_PROBE": s["OFF_PROBE"],
        "victim_variant": variant,
        "rounds1": v["rounds1"], "scrub": v["scrub"], "tvla": v["tvla"],
        "tvla_fixed_pt_hex": manifest["tvla_fixed_pt_hex"],
        "split": split, "monitor_ways": monitor_ways,
        "ticks_per_cycle": 500,
        "trace_range": {"base": layout["trace_base"],
                        "size": layout["trace_size"],
                        "n_lines": layout["trace_lines"]},
        "table_layout_contiguous": layout["contiguous"],
        "tables": layout["tables"],
        "binaries": {
            "victim": {"name": v["binary"],
                       "sha256": binaries[v["binary"]]["sha256"]},
            "monitor": {"name": MONITOR_BINARY,
                        "sha256": binaries[MONITOR_BINARY]["sha256"]}},
        "build_dir": str(build_dir),
        "defines": manifest["defines"],
        "synthetic": False,
    }


def load_baseline(root):
    """configs/run_contention.py as a module; its main() is NOT run (the
    module name differs from __main__ / __m5_main__)."""
    path = Path(root) / "configs" / "run_contention.py"
    if not path.is_file():
        raise AdapterError("baseline config missing: %s" % path)
    spec = importlib.util.spec_from_file_location("run_contention_baseline",
                                                  str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_overrides(baseline, manifest, victim_path, monitor_path):
    profile = baseline.EXPERIMENT_PROFILES["4KiB"]
    profile["workloads"] = [str(monitor_path), str(victim_path)]
    profile["epoch_cycles"] = manifest["schedule"]["W"]
    baseline.CONFIG["contention"]["interval_count"] = manifest["n_win"]
    baseline.MONITOR_VARIANT_BINARIES["v3"] = str(monitor_path)
    baseline.MONITOR_SINK_BINARIES["file"] = str(monitor_path)


def forwarded_args(remaining, default_seed):
    """Arguments handed on to the baseline's own parser.  The flags this
    experiment needs (4 KiB L1D, file sink, v3 monitor) are injected when
    absent and refused when they conflict."""
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--split")
    parser.add_argument("--monitor-ways")
    parser.add_argument("--workload-seed")
    for flag in FORCED:
        parser.add_argument(flag)
    known, rest = parser.parse_known_args(remaining)
    if known.split is None or known.monitor_ways is None:
        raise AdapterError("--split and --monitor-ways are required")
    for flag, value in FORCED.items():
        given = getattr(known, flag[2:].replace("-", "_"))
        if given is not None and given != value:
            raise AdapterError("%s must be %s for this experiment (got %s)" %
                               (flag, value, given))
    try:
        ways = int(known.monitor_ways)
        seed = default_seed if known.workload_seed is None else \
            int(known.workload_seed, 0)
    except ValueError as exc:
        raise AdapterError("bad --monitor-ways / --workload-seed: %s" % exc)
    if not 1 <= seed <= 2 ** 64 - 1:
        raise AdapterError("--workload-seed must be in 1..2^64-1")
    argv = ["--split", known.split, "--monitor-ways", str(ways),
            "--workload-seed", str(seed)]
    for flag, value in FORCED.items():
        argv += [flag, value]
    return argv + rest, {"split": known.split, "monitor_ways": ways,
                         "workload_seed": seed}


def set_tracing_params(manager, layout, requestor_name=VICTIM_REQUESTOR,
                       set_count=256):
    """Enable the victim-table tracing of the extended gem5_ext.  A gem5 binary
    built without experiments/aes-leakage/gem5_ext has no such parameters and
    raises AttributeError, which becomes a refusal to run."""
    try:
        manager.victim_requestor_name = requestor_name
        manager.victim_vaddr_base = layout["trace_base"]
        manager.victim_vaddr_size = layout["trace_size"]
        manager.victim_set_count = set_count
    except AttributeError as exc:
        raise AdapterError(
            "this gem5 binary lacks the victim_* parameters (%s); build it "
            "with EXTRAS=<repo>/experiments/aes-leakage/gem5_ext (see "
            "gem5_build.md)" % exc) from exc


def main(argv=None, m5_module=None, baseline=None, root=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(
        description=__doc__, allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--victim-variant", required=True,
                        choices=sorted(VARIANTS))
    parser.add_argument("--build-dir", type=Path,
                        default=HERE / "build" / "n2000",
                        help="build.sh output directory (default: build/n2000)")
    parser.add_argument("--baseline-root", type=Path, default=REPO,
                        help="repository whose configs/run_contention.py is used")
    args, remaining = parser.parse_known_args(argv)

    try:
        manifest = load_manifest(args.build_dir)
        baseline = baseline or load_baseline(args.baseline_root)
        variant = VARIANTS[args.victim_variant]
        victim = args.build_dir / variant["binary"]
        monitor = args.build_dir / MONITOR_BINARY
        layout = victim_layout(victim)
        forwarded, info = forwarded_args(
            remaining, getattr(baseline, "DEFAULT_WORKLOAD_SEED", 0x5764A5E5))
        config = build_leak_config(
            manifest, args.victim_variant, layout, info["workload_seed"],
            info["split"], info["monitor_ways"], args.build_dir)
        apply_overrides(baseline, manifest, victim, monitor)
    except AdapterError as exc:
        sys.exit("error: %s" % exc)

    if m5_module is None:
        import m5 as m5_module
    if root is None:
        from m5.objects.Root import Root as root
    original_instantiate = m5_module.instantiate

    def instantiate(*positional, **keywords):
        manager = root.getInstance().system.llc.partitioning_manager
        try:
            set_tracing_params(manager, layout)
        except AdapterError as exc:
            sys.exit("error: %s" % exc)
        with (Path(m5_module.options.outdir) / "leak_config.json").open("x") \
                as stream:
            json.dump(config, stream, indent=2)
            stream.write("\n")
        return original_instantiate(*positional, **keywords)

    # Temporary replacement: parameters can only be set after the original
    # config has built the system; the original file is never edited.
    m5_module.instantiate = instantiate
    saved_argv = sys.argv
    sys.argv = ["configs/run_contention.py"] + forwarded
    try:
        baseline.main()
    finally:
        m5_module.instantiate = original_instantiate
        sys.argv = saved_argv


if __name__ in ("__main__", "__m5_main__"):
    main()
