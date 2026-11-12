"""leak_schedule.h: constants, splitmix64 and the plaintext stream.

The C header is the single source of the schedule; leak_params.py parses it
for Python, and a host-compiled dump program proves the C and Python
plaintext streams agree.
"""
import re
import unittest

from tests import _helpers as h

SEED_PLAINTEXTS = {
    0x5764A5E5: [
        "f6ed4a34b9791097c4913c9a13836d05",
        "c0bf76b584bd288872038fba14d23fa0",
        "c798222a46fd16059a4932beb89488b5",
    ],
}


class HeaderConstants(unittest.TestCase):
    def test_constants_match_the_task_specification(self):
        params = h.load_params().constants()
        self.assertEqual(params["T0"], 2_000_000)
        self.assertEqual(params["W"], 1_048_576)
        self.assertEqual(params["OFF_PRIME"], 65_536)
        self.assertEqual(params["OFF_ENC"], 524_288)
        self.assertEqual(params["OFF_ENC_END"], 524_288 + 65_536)
        self.assertEqual(params["OFF_PROBE"], 524_288 + 65_536 + 4_096)
        self.assertEqual(params["N_WIN"], 2000)
        self.assertEqual(params["KEY_HEX"], "f1e2d3c4b5a69788796a5b4c3d2e1f10")

    def test_command_line_override_changes_n_win_and_offsets(self):
        params = h.load_params().constants(
            overrides={"N_WIN": 20, "LEAK_OFF_ENC": 600_000})
        self.assertEqual(params["N_WIN"], 20)
        self.assertEqual(params["OFF_ENC"], 600_000)
        # derived values follow the override
        self.assertEqual(params["OFF_ENC_END"], 600_000 + 65_536)

    def test_key_has_no_zero_upper_nibble(self):
        key = bytes.fromhex(h.load_params().constants()["KEY_HEX"])
        self.assertEqual(len(key), 16)
        self.assertTrue(all(b >> 4 != 0 for b in key),
                        "a zero upper nibble makes (p^k)>>4 equal p>>4")

    def test_window_schedule_fits_inside_one_window(self):
        p = h.load_params().constants()
        self.assertLess(p["OFF_PRIME"], p["OFF_ENC"])
        self.assertLess(p["OFF_ENC_END"], p["OFF_PROBE"])
        self.assertLess(p["OFF_PROBE"], p["W"])


class PythonReference(unittest.TestCase):
    def test_splitmix_seed_zero_words(self):
        gen = h.load_analysis().splitmix64_stream(0)
        self.assertEqual([next(gen), next(gen)],
                         [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4])

    def test_plaintexts_for_the_default_seed(self):
        pts = h.load_analysis().plaintexts(0x5764A5E5, 3)
        self.assertEqual([bytes(p).hex() for p in pts],
                         SEED_PLAINTEXTS[0x5764A5E5])

    def test_tvla_even_windows_are_fixed_and_stream_stays_aligned(self):
        a = h.load_analysis()
        fixed = bytes.fromhex("da39a3ee5e6b4b0d3255bfef95601890")
        import numpy as np
        plain = a.plaintexts(7, 8)
        tvla = a.plaintexts(7, 8, tvla_fixed=np.frombuffer(fixed, np.uint8))
        for j in range(8):
            if j % 2 == 0:
                self.assertEqual(bytes(tvla[j]), fixed)
            else:
                self.assertEqual(bytes(tvla[j]), bytes(plain[j]))


@h.skip_unless_tool(h.HOST_CC)
class CMatchesPython(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = h.tmpdir()
        cls.exe = h.Path(cls._tmp.name) / "schedule_dump"
        proc = h.host_build([h.C_DIR / "schedule_dump.c"], cls.exe,
                            defines=["LEAK_FAKE_CLOCK"])
        if proc.returncode != 0:
            raise AssertionError("host build failed:\n" + proc.stderr)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def dump(self, seed, windows, tvla):
        proc = h.run([self.exe, seed, windows, tvla])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.splitlines()

    def test_constants_agree(self):
        lines = self.dump(1, 1, 0)
        c = dict(re.findall(r"(\w+)=(\d+)", lines[0]))
        p = h.load_params().constants()
        for name in ("T0", "W", "OFF_PRIME", "OFF_ENC", "OFF_ENC_END",
                     "OFF_PROBE", "N_WIN"):
            self.assertEqual(int(c[name]), p[name], name)
        self.assertEqual(lines[1], "key=" + p["KEY_HEX"])

    def test_splitmix_vector_from_c(self):
        lines = self.dump(1, 1, 0)
        self.assertEqual(lines[2],
                         "splitmix_seed0=e220a8397b1dcdaf,6e789e6aa1b965f4")

    def test_plaintext_streams_agree_for_several_seeds(self):
        a = h.load_analysis()
        import numpy as np
        fixed = np.frombuffer(
            bytes.fromhex("da39a3ee5e6b4b0d3255bfef95601890"), np.uint8)
        for seed in (0, 1, 0x5764A5E5, 0xFFFFFFFFFFFFFFFF):
            for tvla in (0, 1):
                lines = self.dump(seed, 40, tvla)
                got = [l.split()[2] for l in lines if l.startswith("pt ")]
                want = [bytes(p).hex() for p in a.plaintexts(
                    seed, 40, tvla_fixed=fixed if tvla else None)]
                self.assertEqual(got, want, (seed, tvla))

    def test_plaintext_vectors_from_c(self):
        lines = self.dump(0x5764A5E5, 3, 0)
        got = [l.split()[2] for l in lines if l.startswith("pt ")]
        self.assertEqual(got, SEED_PLAINTEXTS[0x5764A5E5])


if __name__ == "__main__":
    unittest.main()
