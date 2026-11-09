"""Regression test validating calculation against EFFTRAN reference dataset (Sample 207724)."""
import json
from pathlib import Path
import tempfile
import unittest

from effsuite.materials import create_material
from effsuite.suite import run_project


class EfftranValidationCase207724Tests(unittest.TestCase):
    """End-to-end regression validation for sample 207724 vs EFFTRAN v4.7.3."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_efftran_validation_case_207724_transfer_and_summing(self):
        # 1. Self-contained Glucose material definition matching sample 207724 bulk density (1.346 g/cm3)
        data_dir = self.root / "Data"
        data_dir.mkdir()
        (data_dir / "Composition").mkdir()
        (data_dir / "Material").mkdir()

        comp_def = {
            "schema_version": 1,
            "name": "Glucose",
            "density_g_cm3": 1.346,
            "components": [{"formula": "C6H12O6", "weight": 1.0}],
        }
        create_material(comp_def, library=data_dir)

        # 2. Calibration points from DET002 / TF400_268_2025.CAL
        cal_points = [
            {"energy_keV": 46.539, "efficiency": 0.00122617, "u_rel_percent": 4.04},
            {"energy_keV": 59.541, "efficiency": 0.00706926, "u_rel_percent": 3.01},
            {"energy_keV": 88.034, "efficiency": 0.02608664, "u_rel_percent": 3.00},
            {"energy_keV": 122.061, "efficiency": 0.03365479, "u_rel_percent": 3.10},
            {"energy_keV": 158.970, "efficiency": 0.03284783, "u_rel_percent": 3.04},
            {"energy_keV": 391.698, "efficiency": 0.01907763, "u_rel_percent": 3.02},
            {"energy_keV": 661.657, "efficiency": 0.01278776, "u_rel_percent": 3.00},
            {"energy_keV": 898.042, "efficiency": 0.01004292, "u_rel_percent": 3.02},
            {"energy_keV": 1173.230, "efficiency": 0.00839791, "u_rel_percent": 3.00},
            {"energy_keV": 1332.490, "efficiency": 0.00761853, "u_rel_percent": 3.00},
            {"energy_keV": 1836.070, "efficiency": 0.00575819, "u_rel_percent": 3.02},
        ]

        # 3. Project configuration for sample 207724
        project = {
            "schema_version": 1,
            "geometry": "cylindrical",
            "task": "both",
            "detector": [
                64.0, 1.0, 58.9, 59.4, 0.7, 0.7, 1.27, 3.0, 10.0, 35.0, 1.0, 1.0, 0.0, 0.0,
                "Ge", "aluminium", "aluminium", "aluminium", "air",
            ],
            "standard": [
                82.3, 50.43, 1.5, 1.5, 0.0,
                "water", "polystyrene",
            ],
            "sample": [
                82.3, 55.0, 1.5, 1.5, 0.0,
                "Glucose", "polystyrene",
            ],
            "nuclides": [
                "CO-60", "NA-22", "Y-88", "CS-134", "BA-133", "EU-152", "CO-58", "MN-54", "ZN-65",
            ],
            "workers": 2,
            "calibration": cal_points,
            "data_directory": str(data_dir),
        }

        output_dir = self.root / "output"
        result = run_project(project, output_dir)

        # 4. Verify Efficiency Transfer Factors T(E) = eff_sample / eff_standard
        # Reference values from EFFTRAN transfer routine
        expected_transfer = {
            46.54: 0.8416,
            59.54: 0.8429,
            88.03: 0.8486,
            122.06: 0.8551,
            158.97: 0.8605,
            391.70: 0.8808,
            661.66: 0.8930,
            898.04: 0.8997,
            1173.23: 0.9054,
            1332.49: 0.9080,
            1836.07: 0.9142,
        }

        for row in result["efficiency"]:
            e = row["energy_keV"]
            match_key = min(expected_transfer.keys(), key=lambda k: abs(k - e))
            self.assertAlmostEqual(
                row["transfer_factor"],
                expected_transfer[match_key],
                places=3,
                msg=f"Transfer factor mismatch at {e} keV",
            )

        # 5. Verify True Coincidence Summing Correction Factors (C)
        # Reference factors from EFFTRAN v4.7.3 report 207724_1775741868.RPT
        expected_summing = {
            ("CO-60", 1173): 1.0827,
            ("CO-60", 1332): 1.0854,
            ("NA-22", 1275): 1.2105,
            ("Y-88", 898): 1.0758,
            ("Y-88", 1836): 1.0865,
            ("BA-133", 356): 1.0312,
            ("CS-134", 605): 1.1256,
            ("EU-152", 122): 1.1266,
            ("CO-58", 811): 1.0313,
            ("MN-54", 835): 1.0000,
            ("ZN-65", 1116): 1.0000,
        }

        summing_map = {
            (r["nuclide"], r["energy_keV"]): r["activity_multiplier"]
            for r in result["summing"]
        }

        for (nuclide, energy), ref_factor in expected_summing.items():
            self.assertIn((nuclide, energy), summing_map, f"Missing {nuclide} at {energy} keV in results")
            calc_factor = summing_map[(nuclide, energy)]
            self.assertAlmostEqual(
                calc_factor,
                ref_factor,
                delta=0.0005,
                msg=f"Coincidence factor mismatch for {nuclide} at {energy} keV: got {calc_factor}, expected {ref_factor}",
            )


if __name__ == "__main__":
    unittest.main()
