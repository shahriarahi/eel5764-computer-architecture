#!/usr/bin/env python3
"""Write build_manifest.json next to the binaries produced by build.sh.

The manifest records, for every binary, its sha256 and size, and from `nm -S`
the address and size of te0..te3, sbox (victims) and probe_lines (monitor).
It also derives the victim-table line layout that run_leakage.py hands to the
gem5 tracing extension.  Standard library only.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leak_params  # noqa: E402

VICTIMS = ["victim_leak_r1_scrub", "victim_leak_r1_noscrub",
           "victim_leak_full_scrub", "victim_leak_full_noscrub",
           "victim_leak_tvla"]
MONITOR = "monitor_leak"
TABLES = ("sbox", "te0", "te1", "te2", "te3")
LINE_BYTES = 64


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_nm(text):
    """Defined symbols of `nm -S --defined-only`: name -> {addr, size}."""
    symbols = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 4:
            try:
                symbols[fields[3]] = {"addr": int(fields[0], 16),
                                      "size": int(fields[1], 16)}
            except ValueError:
                continue
    return symbols


def nm_symbols(nm, binary, names):
    text = subprocess.check_output([nm, "-S", "--defined-only", str(binary)],
                                   text=True)
    table = parse_nm(text)
    missing = [n for n in names if n not in table]
    if missing:
        raise SystemExit("%s: symbols not found: %s" % (binary, missing))
    return {n: table[n] for n in names}


def table_layout(symbols):
    """Line layout of the five tables inside their min..max address range."""
    base = min(symbols[t]["addr"] for t in TABLES)
    end = max(symbols[t]["addr"] + symbols[t]["size"] for t in TABLES)
    table_lines = sum(symbols[t]["size"] // LINE_BYTES for t in TABLES)
    return {
        "trace_base": base,
        "trace_size": end - base,
        "trace_lines": (end - base) // LINE_BYTES,
        "table_lines": table_lines,
        "contiguous": (end - base) // LINE_BYTES == table_lines,
        "tables": {t: {"addr": symbols[t]["addr"], "size": symbols[t]["size"],
                       "lines": symbols[t]["size"] // LINE_BYTES,
                       "line_offset": (symbols[t]["addr"] - base) // LINE_BYTES}
                   for t in TABLES},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--n-win", required=True, type=int)
    parser.add_argument("--cc", default="riscv64-linux-gnu-gcc")
    parser.add_argument("defines", nargs="*",
                        help="extra -D flags passed to the compiler")
    args = parser.parse_args()

    nm = os.environ.get("NM") or args.cc.replace("gcc", "nm")
    defines = [d for d in args.defines if d != "--"]
    overrides = leak_params.parse_define_flags(defines)
    overrides["N_WIN"] = args.n_win
    compiler = subprocess.check_output([args.cc, "--version"],
                                       text=True).splitlines()[0]

    binaries, symbols, layouts = {}, {}, {}
    for name in VICTIMS + [MONITOR]:
        path = args.out_dir / name
        binaries[name] = {"sha256": sha256_of(path),
                          "bytes": path.stat().st_size}
    for name in VICTIMS:
        symbols[name] = nm_symbols(nm, args.out_dir / name, TABLES)
        layouts[name] = table_layout(symbols[name])
    symbols[MONITOR] = nm_symbols(nm, args.out_dir / MONITOR, ["probe_lines"])

    schedule = leak_params.constants(overrides)
    manifest = {
        "format": "aes-leakage-build-manifest-v1",
        "n_win": args.n_win,
        "defines": defines,
        "compiler": compiler,
        "schedule": {k: v for k, v in schedule.items()
                     if not k.endswith("_HEX")},
        "key_hex": schedule["KEY_HEX"],
        "tvla_fixed_pt_hex": schedule["TVLA_FIXED_PT_HEX"],
        "binaries": binaries,
        "symbols": symbols,
        "table_layout": layouts,
    }
    target = args.out_dir / "build_manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("wrote %s (%d binaries)" % (target, len(binaries)))


if __name__ == "__main__":
    main()
