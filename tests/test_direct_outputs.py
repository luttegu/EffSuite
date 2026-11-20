"""--output-cal / --output-nlb / --output-ctf copy the verified exports of a run."""
import tempfile
import unittest
from pathlib import Path

from effsuite.app_cli import _copy_direct_outputs
from effsuite.parallel_coincidence import CoincidenceError


class DirectOutputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        run_folder = self.root / "result"
        run_folder.mkdir()
        (run_folder / "x_corrected.LIB").write_bytes(b"abc")
        self.result = {"output_directory": str(run_folder), "warnings": [],
                       "genie_exports": {"nlb": {"file": "x_corrected.LIB"}}}

    def tearDown(self):
        self.temporary.cleanup()

    def test_output_options_copy_exported_files(self):
        target = self.root / "sub" / "mine.LIB"
        _copy_direct_outputs(self.result, output_nlb=target)
        self.assertEqual(target.read_bytes(), b"abc")
        self.assertEqual(self.result["direct_outputs"], {"nlb_output": str(target.resolve())})

    def test_requested_output_that_was_not_produced_is_an_error(self):
        self.result["warnings"].append("Genie auto-export of CAL skipped: template has 5 points")
        with self.assertRaisesRegex(CoincidenceError, "not produced.*5 points"):
            _copy_direct_outputs(self.result, output_cal=self.root / "none.EFT")
        self.assertFalse((self.root / "none.EFT").exists())

    def test_existing_output_file_is_never_overwritten(self):
        target = self.root / "mine.LIB"
        target.write_bytes(b"keep me")
        with self.assertRaisesRegex(CoincidenceError, "already exists"):
            _copy_direct_outputs(self.result, output_nlb=target)
        self.assertEqual(target.read_bytes(), b"keep me")


if __name__ == "__main__":
    unittest.main()
