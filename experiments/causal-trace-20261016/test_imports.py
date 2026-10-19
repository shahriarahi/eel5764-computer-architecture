import sys
import unittest
from pathlib import Path

import validate_trace


HERE = Path(__file__).resolve().parent
TDMA = HERE.parent / "tdma"


class HelperImportTests(unittest.TestCase):
    def test_tdma_helpers_resolve_inside_tdma(self) -> None:
        # A site package named "validate" exists on some hosts (configobj).
        self.assertEqual(Path(sys.modules["validate"].__file__).resolve().parent, TDMA)

    def test_tdma_directory_does_not_stay_on_path(self) -> None:
        self.assertNotIn(str(TDMA), sys.path)

    def test_local_modules_are_not_shadowed(self) -> None:
        import run_structural
        self.assertEqual(Path(run_structural.__file__).resolve().parent, HERE)


if __name__ == "__main__":
    unittest.main()
