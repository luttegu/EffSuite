import shutil, tempfile, unittest
from pathlib import Path
from effsuite import gammavision

LIB = Path(r"C:\PGM\EFFTRAN\EFFTRAN_4.9\EFFTRAN.Lib")


@unittest.skipUnless(LIB.is_file(), "EFFTRAN.Lib sample not available")
class GammaVisionTests(unittest.TestCase):
    def test_read_and_export_roundtrip(self):
        rows = gammavision.read_library(LIB)
        self.assertIn("K-40", {r["nuclide"] for r in rows})
        target = rows[0]
        result = {"summing": [{"nuclide": target["nuclide"], "energy_keV": target["energy"],
                               "activity_multiplier": 1.25, "status": "candidate"}]}
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "corrected.LIB"
            report = gammavision.export_copy(LIB, out, result, "nlb")
            self.assertTrue(report["roundtrip_verified"])
            new = gammavision.read_library(out)
            self.assertAlmostEqual(new[0]["abundance"], target["abundance"] / 1.25, places=3)
            self.assertAlmostEqual(new[1]["abundance"], rows[1]["abundance"], places=3)

    def test_eft_roundtrip(self):
        eft = LIB.with_name("EFFTRAN.EFT")
        if not eft.is_file():self.skipTest("EFFTRAN.EFT not available")
        pts = gammavision.read_cal(eft)
        rows = [{"energy_keV": p["energy_keV"], "sample_efficiency": p["efficiency"] * 0.5,
                 "sample_relative_uncertainty_percent_legacy": 4.0} for p in pts]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "sample.EFT"
            self.assertTrue(gammavision.export_copy(eft, out, {"efficiency": rows}, "cal")["roundtrip_verified"])
            back = gammavision.read_cal(out)
            self.assertEqual(len(back), len(pts))
            self.assertAlmostEqual(back[3]["efficiency"] / pts[3]["efficiency"], 0.5, places=2)
            self.assertAlmostEqual(back[0]["u_rel_percent"], 4.0)
            self.assertIn("FitType", out.read_text())


if __name__ == "__main__":
    unittest.main()
