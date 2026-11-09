"""Export policy checks for the source-guided spatial backend."""
import copy
import unittest

try:
    from effsuite.well_spatial import legacy_text
except ImportError:
    legacy_text = None

from effsuite.parallel_coincidence import CoincidenceError


@unittest.skipIf(legacy_text is None, "optional spatial NumPy dependency is not installed")
class SpatialExportTests(unittest.TestCase):
    def setUp(self):
        self.report = {"convergence": {"passed": True},
                       "transport": {"probability_saturation_count": 0},
                       "nuclides": [{"nuclide": "TEST", "annihilation_pair_records": [],
                                      "corrections": [{"energy_kev":100,"factor":1.25,"status":"candidate"}]}]}

    def test_converged_legacy_output_contains_the_actual_factor(self):
        raw = legacy_text(self.report)
        self.assertEqual(raw.split(),[b"100", b"1.2500000E+00"])

    def test_unconverged_results_cannot_be_exported(self):
        self.report["convergence"]["passed"] = False
        with self.assertRaisesRegex(CoincidenceError,"refinement"):
            legacy_text(self.report)

    def test_saturation_of_local_probabilities_blocks_legacy_export(self):
        self.report["transport"]["probability_saturation_count"] = 1
        with self.assertRaisesRegex(CoincidenceError,"saturation"):
            legacy_text(self.report)

    def test_multiple_nuclides_cannot_be_mixed_in_unlabelled_legacy_file(self):
        self.report["nuclides"].append(copy.deepcopy(self.report["nuclides"][0]))
        with self.assertRaisesRegex(CoincidenceError,"one parent"):
            legacy_text(self.report)

    def test_missing_physical_peak_does_not_become_unit_correction(self):
        self.report["nuclides"][0]["corrections"][0]["factor"] = None
        with self.assertRaisesRegex(CoincidenceError,"complete"):
            legacy_text(self.report)

    def test_pair_sum_in_channel_is_not_claimed_supported(self):
        self.report["nuclides"][0]["annihilation_pair_records"] = ["TEST"]
        self.report["nuclides"][0]["corrections"][0]["energy_kev"] = 1022
        with self.assertRaisesRegex(CoincidenceError,"1022"):
            legacy_text(self.report)
