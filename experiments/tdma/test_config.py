import unittest
from run_contention_tdma import slot_cycles, domain_for_peer


class ConfigTests(unittest.TestCase):
    def test_disabled_and_valid_slot(self) -> None:
        self.assertEqual(slot_cycles("0"), 0)
        self.assertEqual(slot_cycles("4"), 4)

    def test_reject_short_or_invalid_slots(self) -> None:
        for value in ("-1", "1", "2", "3", "garbage"):
            with self.assertRaises(ValueError):
                slot_cycles(value)

    def test_maps_real_cache_peer_names(self) -> None:
        self.assertEqual(domain_for_peer("system.cpu0.dcache.mem_side"), 0)
        self.assertEqual(domain_for_peer("system.cpu1.icache.mem_side"), 1)
        self.assertEqual(domain_for_peer("system.cpu0.mmu.itb.walker.port"), 0)
        self.assertEqual(domain_for_peer("system.cpu1.mmu.dtb.walker.port"), 1)
        with self.assertRaises(ValueError):
            domain_for_peer("system.other.mem_side")


if __name__ == "__main__":
    unittest.main()
