"""DET007 well-detector validation against a GenTran Monte Carlo (ETM hybrid) report,
and regression tests for the five WEFFTRAN/EffSuite bugs fixed together with it."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from effsuite.model_io import ASSETS, COMMON_DATA, read_model, validate_model
from effsuite.parallel_coincidence import CoincidenceError
from effsuite.spatial_summing import (LocalEfficiencies, Quadrature, integrated_counts, parse_decay,
                                      prepare_local, required_energies)
from effsuite.suite import run_project, validate_project

DET007 = [72.0, 69.0, 0.7, 25.5, 43.0, "Ge", "aluminium"]
STANDARD = [17.0, 20.75, 1.5, 1.5, 10.0, "water", "Plastic_vial_det07"]
SAMPLE = [17.0, 58.46, 1.5, 1.5, 10.0, "water", "Plastic_vial_det07"]

# nuclide, energy keV, MC summing correction, MC total (geometry) correction, MC reference efficiency
MC = [
    ("CO-60", 1173.228, 1.597013, 0.403971, 0.110757), ("CO-60", 1332.492, 1.632502, 0.397700, 0.0990798),
    ("CS-137", 661.657, 1.000000, 0.637635, 0.179895), ("AM-241", 59.5409, 1.005157, 0.613650, 0.711913),
    ("RA-226", 186.211, 1.000418, 0.627098, 0.563969), ("PB-214", 241.997, 1.097598, 0.580920, 0.448426),
    ("PB-214", 295.224, 0.983559, 0.641014, 0.372048), ("PB-214", 351.932, 1.005231, 0.628655, 0.315276),
    ("BI-214", 609.312, 1.717482, 0.366922, 0.192963), ("BI-214", 1120.287, 1.928857, 0.332302, 0.115265),
    ("BI-214", 1238.111, 1.912063, 0.338996, 0.105688), ("BI-214", 1764.494, 0.988374, 0.651203, 0.0769),
    ("PB-210", 46.539, 1.0, 0.610993, 0.644585), ("AC-228", 338.32, 1.106343, 0.572394, 0.327151),
    ("AC-228", 911.196, 1.244804, 0.510117, 0.137418), ("AC-228", 968.96, 1.207182, 0.527651, 0.130463),
    ("PB-212", 238.632, 1.001227, 0.626895, 0.45426), ("BI-212", 727.33, 1.175142, 0.548986, 0.166083),
    ("CS-134", 563.246, 3.325774, 0.192373, 0.206451), ("CS-134", 569.33, 3.220434, 0.196666, 0.204544),
    ("CS-134", 604.72, 2.017763, 0.316859, 0.194216), ("CS-134", 795.86, 2.082581, 0.306189, 0.153979),
    ("CS-134", 801.95, 2.835765, 0.232579, 0.152996), ("BA-133", 80.9979, 3.46942, 0.180883, 0.752701),
    ("BA-133", 276.3989, 5.30981, 0.118541, 0.395959), ("BA-133", 302.8508, 3.649467, 0.172532, 0.363178),
    ("BA-133", 356.0129, 2.838251, 0.223041, 0.311897), ("BA-133", 383.8485, 1.258416, 0.504186, 0.290828),
    ("BE-7", 477.6035, 1.000001, 0.634763, 0.238551), ("EU-152", 121.7817, 3.395726, 0.184931, 0.720878),
    ("EU-152", 244.6974, 5.675805, 0.110185, 0.443842), ("EU-152", 344.2785, 1.493875, 0.425674, 0.321834),
    ("EU-152", 778.9045, 2.21733, 0.288047, 0.156789), ("EU-152", 964.079, 4.006508, 0.156636, 0.131022),
    ("EU-152", 1085.837, 1.487838, 0.424222, 0.1184), ("EU-152", 1112.076, 3.44423, 0.183069, 0.115997),
    ("EU-152", 1408.013, 3.533309, 0.183174, 0.0943468), ("I-131", 284.305, 2.161375, 0.293892, 0.385549),
    ("I-131", 364.489, 0.978128, 0.647174, 0.305129), ("I-131", 636.989, 0.996463, 0.63157, 0.185791),
    ("NA-22", 1274.537, 3.171711, 0.202038, 0.103038),
]
CASCADES = ("CO-60", "BI-214", "CS-134", "BA-133", "EU-152", "I-131", "NA-22", "CS-137")


class Det007MonteCarloValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        calibration = [{"energy_keV": e, "efficiency": eff, "u_rel_percent": 1.0}
                       for e, eff in sorted({row[1]: row[4] for row in MC}.items())]
        project = {"schema_version": 1, "geometry": "well", "task": "both", "detector": DET007,
                   "standard": STANDARD, "sample": SAMPLE, "calibration": calibration,
                   "nuclides": list(CASCADES), "workers": 0}
        cls.result = run_project(project, Path(cls.tmp.name)/"det007")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_efficiency_transfer_matches_monte_carlo(self):
        factor = {round(r["energy_keV"], 3): r["transfer_factor"] for r in self.result["efficiency"]}
        errors = []
        for _, energy, tcs, total, _ in MC:
            errors.append(factor[round(energy, 3)]/(tcs*total)-1)
        errors = np.abs(errors)
        self.assertLess(errors.mean(), .025, errors)
        self.assertLess(errors.max(), .055, errors)

    def test_coincidence_summing_tracks_monte_carlo_without_overshoot(self):
        found = {(r["nuclide"], r["energy_keV"]): r["activity_multiplier"] for r in self.result["summing"]}
        ratios = {}
        for nuclide, energy, tcs, _, _ in MC:
            if nuclide not in CASCADES:
                continue
            key = (nuclide, min((k[1] for k in found if k[0] == nuclide), key=lambda e: abs(e-energy)))
            if abs(key[1]-energy) < 2:
                ratios[(nuclide, round(energy))] = found[key]/tcs
        self.assertGreater(len(ratios), 25)
        self.assertLess(max(ratios.values()), 1.05)
        self.assertGreater(min(ratios.values()), .70)
        for key in (("CO-60", 1173), ("CS-134", 605), ("BI-214", 1120), ("NA-22", 1275)):
            self.assertGreater(ratios[key], .88, key)
        self.assertTrue(self.result["all_reported_factors_valid"])


class WellBugRegressions(unittest.TestCase):
    def test_bug1_container_wider_than_well_is_rejected(self):
        base = json.loads((Path(__file__).parent.parent/"src/effsuite/assets/examples/well.effsuite.json").read_text())
        for task, kind in (("summing", "sample"), ("transfer", "standard"), ("both", "sample")):
            project = json.loads(json.dumps(base)); project["task"] = task
            project[kind][0] = 30.0
            with self.assertRaisesRegex(CoincidenceError, "fit"):
                validate_project(project)

    def test_bug1_bundled_well_models_are_valid_well_models(self):
        well = ASSETS/"well"
        for kind, folder in (("sample", "Sample"), ("standard", "Standard"), ("detector", "Detector")):
            for path in (well/folder).glob("*.txt"):
                values = read_model("well", kind, path)
                if kind != "detector":
                    self.assertLessEqual(values[0], 25.5, path.name)

    def local(self, source, order=Quadrature(3, 4, 8, 16)):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        folder = Path(self.tmp.name)
        (folder/"detector.txt").write_text("\n".join(map(str, DET007))+"\n")
        (folder/"source.txt").write_text("\n".join(map(str, source))+"\n")
        energies = np.asarray([30.4, 81., 100., 356., 511., 1173.2, 1274.5])
        return prepare_local(COMMON_DATA, folder, energies, order)

    def test_bug2_wide_vial_has_no_probability_saturation(self):
        local = self.local([24.0, 58.46, 1.5, 1.5, 10.0, "water", "Plastic_vial_det07"])
        self.assertEqual(local.metadata["probability_saturation_count"], 0)
        self.assertLessEqual(local.metadata["maximum_unsaturated_total"], 1.0)
        self.assertTrue(np.all(local.peak <= local.total+1e-12))
        self.assertTrue(np.all(local.total <= 1.))

    def test_bug3_annihilation_photons_are_antiparallel(self):
        local = self.local(SAMPLE)
        i = int(np.argmin(np.abs(local.energies-511.)))
        independent = (1-local.total[:, i])**2
        self.assertIsNotNone(local.pair_miss)
        self.assertGreater(np.max(np.abs(local.pair_miss-independent)), 1e-4)
        self.assertTrue(np.all((local.pair_miss >= 0) & (local.pair_miss <= 1)))
        raw = b"10 0 1 0\n0 0 0 0 0\n100 1 0 .9 0\n-1 0 0 0 0\n2 1 100 1 0 0 0\n"
        record = parse_decay("NA", raw, beta_plus_in_pl=True)
        energies = required_energies((record,))
        columns = [int(np.argmin(np.abs(local.energies-e))) for e in energies]
        peak, total = local.peak[:, columns], local.total[:, columns]
        collinear = LocalEfficiencies(energies, local.weights, peak, total, local.points, {},
                                      local.pair_miss, local.pair_single_peak)
        independent = LocalEfficiencies(energies, local.weights, peak, total, local.points, {})
        a = integrated_counts((record,), collinear, 10.)["corrections"][0]["factor"]
        b = integrated_counts((record,), independent, 10.)["corrections"][0]["factor"]
        self.assertTrue(np.isfinite(a) and a > 1.)
        self.assertNotAlmostEqual(a, b, places=4)



class WellExtendedDetectorTests(unittest.TestCase):
    def test_legacy_7_field_detector_defaults_optional_parameters(self):
        d = validate_model("well", "detector", DET007)
        self.assertEqual(len(d), 12)
        self.assertEqual(d[:7], DET007)
        self.assertEqual(d[7], DET007[2])
        self.assertEqual(d[8], DET007[2])
        self.assertEqual(d[9], 0.0)
        self.assertEqual(d[10], 0.0)
        self.assertEqual(d[11], "copper")

    def test_extended_12_field_detector_validation(self):
        ext = [72.0, 69.0, 0.7, 25.5, 43.0, "Ge", "aluminium", 1.9, 1.5, 2.45, 1.0, "copper"]
        d = validate_model("well", "detector", ext)
        self.assertEqual(d, ext)

    def test_detector_with_key_values_and_comments(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "det.txt"
            path.write_text("""# DET007 Model with Cu holder and real dead layers
72.00
69.00
0.70
25.50
43.00
Ge
aluminium
# Extended fields:
mantle_dead_layer = 1.90
bottom_dead_layer = 1.50
holder_thickness = 2.45
sample_offset = 1.00
holder_material = copper
""")
            d = read_model("well", "detector", path)
            self.assertEqual(d[7], 1.9)
            self.assertEqual(d[8], 1.5)
            self.assertEqual(d[9], 2.45)
            self.assertEqual(d[10], 1.0)
            self.assertEqual(d[11], "copper")

    def test_mantle_dead_layer_too_thick_rejected(self):
        with self.assertRaisesRegex(CoincidenceError, "Mantle dead layer"):
            validate_model("well", "detector", [72.0, 69.0, 0.7, 25.5, 43.0, "Ge", "aluminium", 25.0, 1.5, 0.0, 0.0, "copper"])

    def test_bottom_dead_layer_too_thick_rejected(self):
        with self.assertRaisesRegex(CoincidenceError, "Bottom dead layer"):
            validate_model("well", "detector", [72.0, 69.0, 0.7, 25.5, 43.0, "Ge", "aluminium", 1.9, 30.0, 0.0, 0.0, "copper"])

    def test_holder_and_dead_layers_physics(self):
        with tempfile.TemporaryDirectory() as td:
            folder_no_h = Path(td) / "no_holder"
            folder_h = Path(td) / "with_holder"
            folder_no_h.mkdir(); folder_h.mkdir()

            (folder_no_h / "detector.txt").write_text("\n".join(map(str, DET007)) + "\n")
            (folder_no_h / "source.txt").write_text("\n".join(map(str, STANDARD)) + "\n")

            det_h = [72.0, 69.0, 0.7, 25.5, 43.0, "Ge", "aluminium", 1.9, 1.5, 2.45, 0.0, "copper"]
            (folder_h / "detector.txt").write_text("\n".join(map(str, det_h)) + "\n")
            (folder_h / "source.txt").write_text("\n".join(map(str, STANDARD)) + "\n")

            energies = np.array([122.06, 661.66, 1173.23, 1332.49])
            loc_no_h = prepare_local(COMMON_DATA, folder_no_h, energies, Quadrature(2, 2, 4, 8))
            loc_h = prepare_local(COMMON_DATA, folder_h, energies, Quadrature(2, 2, 4, 8))

            self.assertEqual(loc_h.metadata["probability_saturation_count"], 0)
            self.assertLessEqual(loc_h.metadata["maximum_unsaturated_total"], 1.0)
            self.assertTrue(np.all(loc_h.peak <= loc_h.total + 1e-12))
            self.assertTrue(np.all(loc_h.total <= 1.0))


if __name__ == "__main__":
    unittest.main()
