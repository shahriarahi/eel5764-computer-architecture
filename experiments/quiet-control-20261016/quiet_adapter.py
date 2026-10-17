"""Replace only the victim executable before the original adapter instantiates."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys

sys.dont_write_bytecode = True


def main() -> None:
    import m5
    from m5.objects.Root import Root
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--quiet-binary", required=True, type=Path)
    args, remaining = parser.parse_known_args()
    if not args.quiet_binary.is_file():
        raise FileNotFoundError(args.quiet_binary)
    original = m5.instantiate

    def instantiate(*positional: object, **keywords: object) -> object:
        victim = Root.getInstance().system.cpu[1].workload[0]
        argv = list(victim.cmd)
        original_binary = str(victim.executable)
        victim.executable = str(args.quiet_binary)
        # Keep argv[0] unchanged to retain its stack-layout contribution.
        metadata = {"original_executable": original_binary, "actual_executable": str(args.quiet_binary),
                    "argv": argv, "argv0_intentionally_preserved": True,
                    "quiet_sha256": hashlib.sha256(args.quiet_binary.read_bytes()).hexdigest()}
        with (Path(m5.options.outdir) / "quiet_config.json").open("x") as stream:
            json.dump(metadata, stream, indent=2)
        return original(*positional, **keywords)

    m5.instantiate = instantiate
    adapter = Path(__file__).resolve().parent.parent / "tdma/run_contention_tdma.py"
    sys.argv = [str(adapter), *remaining]
    try:
        runpy.run_path(str(adapter), run_name="__m5_main__")
    finally:
        m5.instantiate = original


if __name__ in ("__main__", "__m5_main__"):
    main()
