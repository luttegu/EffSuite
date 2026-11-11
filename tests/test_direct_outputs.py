import tempfile, unittest
from pathlib import Path
from effsuite.app_cli import _copy_direct_outputs


class DirectOutputTests(unittest.TestCase):
    def test_output_options_copy_exported_files(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            out = d / "result"; out.mkdir()
            (out / "x_corrected.LIB").write_bytes(b"abc")
            result = {"output_directory": str(out), "genie_exports": {"nlb": {"file": "x_corrected.LIB"}}}
            target = d / "sub" / "mine.LIB"
            _copy_direct_outputs(result, output_nlb=target, output_cal=d / "none.EFT")
            self.assertEqual(target.read_bytes(), b"abc")
            self.assertEqual(result["direct_outputs"], {"nlb_output": str(target.resolve())})
            self.assertFalse((d / "none.EFT").exists())


if __name__ == "__main__":
    unittest.main()
