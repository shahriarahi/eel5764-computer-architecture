"""Per-domain LLC response queues (and optionally the quiet victim) around the TDMA adapter."""

import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys

sys.dont_write_bytecode = True

# Domain index = core index, matching the request-TDMA port-domain mapping.
RESPONSE_DOMAIN_PREFIXES = ["cpu0.", "cpu1."]
TDMA_ADAPTER = Path(__file__).resolve().parent.parent / "tdma/run_contention_tdma.py"


def parse_arguments(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--respq", action="store_true",
                        help="split the LLC CPU-side response queue by domain")
    parser.add_argument("--quiet-binary", type=Path, default=None,
                        help="replace the victim executable (argv[0] is kept)")
    return parser.parse_known_args(argv)


def main() -> None:
    import m5
    from m5.objects.Root import Root

    args, remaining = parse_arguments(sys.argv[1:])
    if args.quiet_binary is not None and not args.quiet_binary.is_file():
        raise FileNotFoundError(args.quiet_binary)
    original = m5.instantiate

    def instantiate(*positional: object, **keywords: object) -> object:
        system = Root.getInstance().system
        metadata = {"respq": args.respq, "quiet_binary": None}
        if args.respq:
            system.llc.response_domain_prefixes = RESPONSE_DOMAIN_PREFIXES
            metadata["response_domain_prefixes"] = RESPONSE_DOMAIN_PREFIXES
        if args.quiet_binary is not None:
            victim = system.cpu[1].workload[0]
            metadata.update({
                "quiet_binary": str(args.quiet_binary),
                "original_executable": str(victim.executable),
                "argv": list(victim.cmd),
                "argv0_intentionally_preserved": True,
                "quiet_sha256": hashlib.sha256(args.quiet_binary.read_bytes()).hexdigest(),
            })
            victim.executable = str(args.quiet_binary)
        with (Path(m5.options.outdir) / "respq_config.json").open("x") as stream:
            json.dump(metadata, stream, indent=2)
        return original(*positional, **keywords)

    m5.instantiate = instantiate
    sys.argv = [str(TDMA_ADAPTER), *remaining]
    try:
        runpy.run_path(str(TDMA_ADAPTER), run_name="__m5_main__")
    finally:
        m5.instantiate = original


if __name__ in ("__main__", "__m5_main__"):
    main()
