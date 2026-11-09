"""Regression test validating Marinelli beaker calculation against MEFFTRAN laboratory reference dataset (Sample 2025-0051C on DET952)."""
import math
from pathlib import Path
import tempfile
import unittest

from effsuite.materials import create_material
from effsuite.suite import run_project


class MefftranValidationCaseDET952MarTests(unittest.TestCase):
    """End-to-end regression validation for sample 2025-0051C vs MEFFTRAN v1.6.1 in DET952_MAR."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_mefftran_validation_case_det952_mar_transfer_and_summing(self):
        # 1. Self-contained Cellulose material definition matching sample 2025-0051C bulk density (0.229 g/cm3)
        data_dir = self.root / "Data"
        data_dir.mkdir()
        (data_dir / "Composition").mkdir()
        (data_dir / "Material").mkdir()

        comp_def = {
            "schema_version": 1,
            "name": "cellulose_0229",
            "density_g_cm3": 0.229,
            "components": [{"formula": "C6H10O5", "weight": 1.0}],
        }
        create_material(comp_def, library=data_dir)

        # 2. Reference calibration points from DET952 / MAR_1000.CAL
        cal_points = [
            {"energy_keV": 59.54, "efficiency": 0.01632278, "u_rel_percent": 3.86},
            {"energy_keV": 88.03, "efficiency": 0.03555380, "u_rel_percent": 3.57},
            {"energy_keV": 122.06, "efficiency": 0.04179295, "u_rel_percent": 2.22},
            {"energy_keV": 136.47, "efficiency": 0.03888335, "u_rel_percent": 11.60},
            {"energy_keV": 165.86, "efficiency": 0.04249605, "u_rel_percent": 2.57},
            {"energy_keV": 320.08, "efficiency": 0.02639890, "u_rel_percent": 3.00},
            {"energy_keV": 391.70, "efficiency": 0.02138803, "u_rel_percent": 2.22},
            {"energy_keV": 514.01, "efficiency": 0.02083085, "u_rel_percent": 2.65},
            {"energy_keV": 661.66, "efficiency": 0.01367983, "u_rel_percent": 2.50},
            {"energy_keV": 834.85, "efficiency": 0.01139698, "u_rel_percent": 2.52},
            {"energy_keV": 898.04, "efficiency": 0.01086442, "u_rel_percent": 2.45},
            {"energy_keV": 1115.54, "efficiency": 0.00880999, "u_rel_percent": 2.53},
            {"energy_keV": 1173.23, "efficiency": 0.00870983, "u_rel_percent": 2.50},
            {"energy_keV": 1332.49, "efficiency": 0.00776762, "u_rel_percent": 2.50},
            {"energy_keV": 1836.07, "efficiency": 0.00609458, "u_rel_percent": 2.67},
        ]

        # 3. Expected transfer factors (F = sample_eff / std_eff) from 9525160_1767696415.CAL
        expected_transfer_factors = {
            59.54: 1.2084,
            88.03: 1.1831,
            122.06: 1.1659,
            136.47: 1.1603,
            165.86: 1.1506,
            320.08: 1.1188,
            391.70: 1.1097,
            514.01: 1.0977,
            661.66: 1.0873,
            834.85: 1.0785,
            898.04: 1.0751,
            1115.54: 1.0677,
            1173.23: 1.0660,
            1332.49: 1.0618,
            1836.07: 1.0520,
        }

        # 4. Expected TCS correction factors from 9525160_1767696415.RPT
        expected_summing_factors = {
            ("CO-60", 1173): 1.0690,
            ("CO-60", 1332): 1.0711,
            ("CS-134", 563): 1.1690,
            ("CS-134", 605): 1.0989,
            ("CS-134", 796): 1.0979,
            ("CS-137", 662): 1.0000,
            ("NA-22", 1275): 1.1641,
            ("EU-152", 122): 1.1576,
            ("EU-152", 344): 1.0601,
            ("EU-152", 779): 1.0860,
            ("EU-152", 1408): 1.1301,
            ("BI-214", 609): 1.0783,
            ("BI-214", 1120): 1.0856,
            ("BI-214", 1764): 0.9976,
            ("K-40", 1461): 1.0000,
            ("BE-7", 478): 1.0000,
        }

        project = {
            "schema_version": 1,
            "geometry": "marinelli",
            "task": "both",
            "detector": [
                82.00, 1.00, 56.10, 74.40, 0.00, 0.00, 0.50, 4.00,
                10.00, 50.00, 1.00, 1.00, "Ge", "beryllium", "aluminium", "aluminium"
            ],
            "sample": [
                143.10, 87.00, 99.74, 77.00, 2.30, "cellulose_0229", "polypropylene"
            ],
            "standard": [
                143.10, 87.00, 99.60, 77.00, 2.30, "water", "polypropylene"
            ],
            "calibration": cal_points,
            "nuclides": ["CO-60", "CS-134", "CS-137", "NA-22", "EU-152", "BI-214", "K-40", "BE-7"],
            "workers": 1,
            "data_directory": str(data_dir),
        }

        result = run_project(project, self.root / "output")

        # Verify efficiency transfer factors (within 0.1% of MEFFTRAN v1.6.1)
        for row in result["efficiency"]:
            energy = row["energy_keV"]
            self.assertIn(energy, expected_transfer_factors)
            expected_f = expected_transfer_factors[energy]
            actual_f = row["transfer_factor"]
            self.assertAlmostEqual(actual_f, expected_f, delta=0.002,
                                   msg=f"Transfer factor mismatch at {energy} keV: got {actual_f}, expected {expected_f}")

        # Verify TCS factors (within 0.002 of MEFFTRAN v1.6.1)
        for row in result["summing"]:
            key = (row["nuclide"], int(row["energy_keV"]))
            if key in expected_summing_factors:
                expected_c = expected_summing_factors[key]
                actual_c = row["activity_multiplier"]
                self.assertIsNotNone(actual_c)
                self.assertAlmostEqual(actual_c, expected_c, delta=0.002,
                                       msg=f"TCS factor mismatch for {key}: got {actual_c}, expected {expected_c}")


if __name__ == "__main__":
    unittest.main()
