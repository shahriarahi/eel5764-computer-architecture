import re
import sys
import unittest
from pathlib import Path

from run_contention_respq import RESPONSE_DOMAIN_PREFIXES, parse_arguments

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "causal-trace-20261016"))
from run_contention_causal import domain_for_peer  # noqa: E402  (TDMA's port mapping)
sys.path.pop(0)


class AdapterConfigTests(unittest.TestCase):
    def test_prefix_domains_match_tdma_port_domains(self) -> None:
        for peer in ("system.cpu0.dcache.mem_side", "system.cpu0.icache.mem_side",
                     "system.cpu0.mmu.dtb.walker.port", "system.cpu1.dcache.mem_side",
                     "system.cpu1.mmu.itb.walker.port"):
            core = re.search(r"cpu(\d)", peer).group(1)
            prefix_domain = RESPONSE_DOMAIN_PREFIXES.index(f"cpu{core}.")
            self.assertEqual(prefix_domain, domain_for_peer(peer), peer)

    def test_disabled_by_default_and_forwards_baseline_arguments(self) -> None:
        args, remaining = parse_arguments(["--baseline-root", "/p", "--split", "1-15"])
        self.assertFalse(args.respq)
        self.assertIsNone(args.quiet_binary)
        self.assertEqual(remaining, ["--baseline-root", "/p", "--split", "1-15"])

    def test_enables_split_and_quiet_victim(self) -> None:
        args, remaining = parse_arguments(["--respq", "--quiet-binary", "/q", "--split", "8-8"])
        self.assertTrue(args.respq)
        self.assertEqual(args.quiet_binary, Path("/q"))
        self.assertEqual(remaining, ["--split", "8-8"])


if __name__ == "__main__":
    unittest.main()
