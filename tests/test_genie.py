"""Genie CAM adapter tests with a fake PowerShell bridge (real CAM needs Windows + Genie)."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from effsuite import genie
from effsuite.genie import export_copy, match_factor
from effsuite.parallel_coincidence import CoincidenceError
from effsuite.software import copy_verified_export

CO60_LINE = {"nuclide": "CO-60", "energy": 1173.2, "abundance": .99, "record": 1, "line": 1}
CS137_LINE = {"nuclide": "CS-137", "energy": 661.66, "abundance": .85, "record": 2, "line": 1}


class FakeBridge:
    """Stands in for genie._call. Records every call.

    Reading returns ``rows``. Writing returns the rows "read back" after saving,
    which by default are the rows with the requested values stored, or
    ``saved_rows`` when a test wants to simulate a bad save.
    """
    def __init__(self, rows, saved_rows=None):
        self.rows, self.saved_rows, self.calls = rows, saved_rows, []

    def __call__(self, action, path, updates=None):
        self.calls.append((action, Path(path), updates))
        if action.startswith("read_"):
            return {"ok": True, "rows": copy.deepcopy(self.rows)}
        if self.saved_rows is not None:
            return {"ok": True, "rows": copy.deepcopy(self.saved_rows)}
        saved = copy.deepcopy(self.rows)
        for row, update in zip(saved, updates):
            row["abundance"] = update["value"]
        return {"ok": True, "rows": saved}


class GenieTests(unittest.TestCase):
    def setUp(self):
        genie._rows_cache.clear()   # every test starts without remembered files
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "original.NLB"
        self.source.write_bytes(b"original")
        self.result = {"summing": [{"nuclide": "CO-60", "energy_keV": 1173, "activity_multiplier": 1.25,
                                    "status": "candidate"}], "efficiency": []}

    def tearDown(self):
        self.temporary.cleanup()

    def export(self, bridge, name="corrected.NLB"):
        with patch("effsuite.genie._call", side_effect=bridge):
            return export_copy(self.source, self.root / name, self.result, "nlb")

    # --- match_factor ---------------------------------------------------------
    def test_missing_factor_never_becomes_one(self):
        with self.assertRaises(CoincidenceError):
            match_factor(self.result, "CS-137", 661.66)

    def test_invalid_nearest_factor_is_not_replaced_with_a_valid_neighbor(self):
        self.result["summing"].append({"nuclide": "CO-60", "energy_keV": 1174, "activity_multiplier": None, "status": "invalid"})
        with self.assertRaises(CoincidenceError):
            match_factor(self.result, "CO-60", 1173.9)

    def test_library_spelling_does_not_matter(self):
        # A library may write "Co60" or "co-60"; the calculation writes "CO-60".
        self.assertEqual(match_factor(self.result, "Co60", 1173.2), 1.25)
        self.assertEqual(match_factor(self.result, "co-60", 1173.2), 1.25)

    # --- export ---------------------------------------------------------------
    def test_roundtrip_source_preservation_and_abundance_division(self):
        bridge = FakeBridge([CO60_LINE])
        report = self.export(bridge)
        action, path, updates = bridge.calls[-1]
        self.assertEqual(action, "write_nlb")
        self.assertNotEqual(path, self.source)               # Genie only sees a private copy
        self.assertAlmostEqual(updates[0]["value"], .99 / 1.25)
        self.assertTrue(report["roundtrip_verified"])
        self.assertEqual(report["corrected_lines"], 1)
        self.assertEqual(self.source.read_bytes(), b"original")

    def test_export_starts_powershell_once_when_file_was_already_read(self):
        bridge = FakeBridge([CO60_LINE])
        with patch("effsuite.genie._call", side_effect=bridge):
            genie.read_library(self.source)                  # e.g. the GUI import
            genie.read_library(self.source)                  # same content: taken from memory
            export_copy(self.source, self.root / "out.NLB", self.result, "nlb")
        self.assertEqual([call[0] for call in bridge.calls], ["read_nlb", "write_nlb"])

    def test_changed_file_is_read_again(self):
        bridge = FakeBridge([CO60_LINE])
        with patch("effsuite.genie._call", side_effect=bridge):
            genie.read_library(self.source)
            self.source.write_bytes(b"changed")
            genie.read_library(self.source)
        self.assertEqual(len(bridge.calls), 2)

    def test_failed_roundtrip_does_not_publish_output(self):
        bridge = FakeBridge([CO60_LINE], saved_rows=[CO60_LINE])   # value was not saved
        with self.assertRaises(CoincidenceError):
            self.export(bridge, "bad.NLB")
        self.assertFalse((self.root / "bad.NLB").exists())
        self.assertEqual(self.source.read_bytes(), b"original")

    def test_tiny_coefficient_underflow_is_rejected(self):
        self.result["summing"][0]["activity_multiplier"] = 2.
        tiny = dict(CO60_LINE, abundance=1e-30)
        bridge = FakeBridge([tiny], saved_rows=[dict(tiny, abundance=0.)])
        with self.assertRaises(CoincidenceError):
            self.export(bridge, "underflow.NLB")
        self.assertFalse((self.root / "underflow.NLB").exists())

    def test_uncomputed_line_abundance_remains_unchanged_in_export(self):
        bridge = FakeBridge([CO60_LINE, CS137_LINE])
        report = self.export(bridge, "mixed.NLB")
        updates = bridge.calls[-1][2]
        self.assertAlmostEqual(updates[0]["value"], .99 / 1.25)
        self.assertAlmostEqual(updates[1]["value"], .85)    # no factor: unchanged
        self.assertTrue(report["roundtrip_verified"])
        self.assertEqual(report["corrected_lines"], 1)

    def test_failed_well_model_blocks_export(self):
        self.result["well_spatial_diagnostics"] = {"convergence": {"passed": False},
                                                   "transport": {"probability_saturation_count": 0}, "nuclides": []}
        bridge = FakeBridge([CO60_LINE])
        with self.assertRaisesRegex(CoincidenceError, "blocked"):
            self.export(bridge, "blocked.NLB")
        self.assertEqual(bridge.calls, [])                  # PowerShell never started
        self.assertFalse((self.root / "blocked.NLB").exists())

    def test_ambiguous_factor_blocks_export(self):
        self.result["summing"] = [{"nuclide": "CO-60", "energy_keV": 1172.7, "activity_multiplier": 1.1, "status": "candidate"},
                                  {"nuclide": "CO-60", "energy_keV": 1173.7, "activity_multiplier": 1.3, "status": "candidate"}]
        with self.assertRaisesRegex(CoincidenceError, "Ambiguous"):
            self.export(FakeBridge([CO60_LINE]), "ambiguous.NLB")
        self.assertFalse((self.root / "ambiguous.NLB").exists())

    # --- copying an export that a run already verified ------------------------
    def test_copy_verified_export(self):
        run_folder = self.root / "run"
        run_folder.mkdir()
        (run_folder / "original_corrected.NLB").write_bytes(b"verified")
        result = {"output_directory": str(run_folder), "genie_exports": {"nlb": {"file": "original_corrected.NLB"}}}
        target = copy_verified_export(result, "nlb", self.root / "copy.NLB")
        self.assertEqual(target.read_bytes(), b"verified")
        with self.assertRaises(CoincidenceError):           # never overwrite
            copy_verified_export(result, "nlb", self.root / "copy.NLB")
        with self.assertRaises(CoincidenceError):           # wrong format
            copy_verified_export(result, "nlb", self.root / "copy.LIB")
        with self.assertRaises(CoincidenceError):           # nothing exported for this kind
            copy_verified_export(result, "ctf", self.root / "copy.CTF")


if __name__ == "__main__":
    unittest.main()
