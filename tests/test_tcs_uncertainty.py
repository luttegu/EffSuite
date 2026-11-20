"""TCS (summing factor) uncertainty: settings, propagation formula and engine runs."""
import csv
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from effsuite import tcs_uncertainty as tcs
from effsuite.app_cli import example_path
from effsuite.parallel_coincidence import CoincidenceError, SharedInputs
from effsuite.spatial_summing import LocalEfficiencies
from effsuite.suite import _match_library_lines, run_project, validate_project

CURVE = b"100 0.1 0.12\n1000 0.02 0.03\n"
TOTAL = b"100 0.2 0.25\n1000 0.05 0.06\n"


class SettingsTests(unittest.TestCase):
    def test_defaults_and_overrides(self):
        self.assertEqual(tcs.validate_settings(None), tcs.DEFAULTS)
        settings = tcs.validate_settings({"total_efficiency_percent": 7})
        self.assertEqual(settings["total_efficiency_percent"], 7.0)
        self.assertEqual(settings["peak_efficiency_percent"], tcs.DEFAULTS["peak_efficiency_percent"])

    def test_invalid_settings_are_refused(self):
        for bad in ({"unknown": 1}, {"peak_efficiency_percent": -1}, {"peak_total_correlation": 1.5},
                    {"total_efficiency_percent": True}, {"enabled": "yes"}, {"step_percent": 0}, [1]):
            with self.subTest(bad=bad), self.assertRaises(CoincidenceError):
                tcs.validate_settings(bad)

    def test_project_validation_adds_settings_only_for_summing(self):
        project = json.loads(example_path("cylinder").read_text())
        self.assertIn("tcs_uncertainty", validate_project({**project, "task": "summing"}))
        self.assertNotIn("tcs_uncertainty", validate_project({**project, "task": "transfer"}))


class PropagationTests(unittest.TestCase):
    settings = {**tcs.DEFAULTS, "peak_efficiency_percent": 4.0, "total_efficiency_percent": 3.0}

    def test_uncorrelated_quadrature_sum(self):
        out = tcs.line_uncertainty(.5, 2., self.settings, None)
        self.assertAlmostEqual(out["tcs_u_peak_percent"], 2.)
        self.assertAlmostEqual(out["tcs_u_total_percent"], 6.)
        self.assertAlmostEqual(out["tcs_u_rel_percent"], math.hypot(2, 6))
        self.assertIsNone(out["tcs_u_numerical_percent"])

    def test_full_correlation_adds_signed_components_linearly(self):
        plus = tcs.line_uncertainty(-.5, 2., {**self.settings, "peak_total_correlation": 1.}, None)
        minus = tcs.line_uncertainty(-.5, 2., {**self.settings, "peak_total_correlation": -1.}, None)
        self.assertAlmostEqual(plus["tcs_u_rel_percent"], abs(-2 + 6))
        self.assertAlmostEqual(minus["tcs_u_rel_percent"], abs(-2 - 6))

    def test_numerical_term_in_quadrature(self):
        out = tcs.line_uncertainty(0., 1., {**self.settings, "total_efficiency_percent": 3.}, .04)
        self.assertAlmostEqual(out["tcs_u_rel_percent"], 5.)
        self.assertAlmostEqual(out["tcs_u_numerical_percent"], 4.)

    def test_missing_sensitivity_gives_no_uncertainty(self):
        self.assertEqual(tcs.line_uncertainty(None, 1., self.settings, None), tcs.empty_fields())

    def test_central_difference_is_exact_for_a_power_law(self):
        """C = eps_P^a * eps_T^b has S_P = a and S_T = b exactly."""
        def run(inputs):
            peak = tcs._rows(inputs.efficiency)[0][1] / .1
            total = tcs._rows(inputs.buildup)[0][1] / .2
            return f"{'CO-60':10s}{1173:10d}{1.1 * peak**-.3 * total**.08:23.15e}\n".encode()
        found = tcs.cascade_sensitivities(SharedInputs(CURVE, TOTAL, b""), run, .02)
        s_peak, s_total = found[("CO-60", 1173)]
        self.assertAlmostEqual(s_peak, -.3, places=5)
        self.assertAlmostEqual(s_total, .08, places=5)

    def test_scaled_inputs_cap_physical_limits(self):
        scaled = tcs.scaled_inputs(SharedInputs(b"100 0.19 0.2\n1000 0.02 0.03\n", b"100 0.2 0.21\n1000 0.95 0.96\n", b""),
                                   1.2, 1.1)
        peak, total = tcs._rows(scaled.efficiency), tcs._rows(scaled.buildup)
        self.assertEqual(total[1][1:], [1., 1.])            # total efficiency at most 1
        self.assertAlmostEqual(peak[0][1], .22)             # peak at most total (0.19*1.2 > 0.2*1.1)
        self.assertAlmostEqual(peak[1][1], .024)
        scaled.validate()                                   # energy grids still match

    def test_scaled_local_respects_peak_le_total_le_one(self):
        local = LocalEfficiencies(np.array([100., 511.]), np.array([.5, .5]), np.array([[.3, .2], [.1, .05]]),
                                  np.array([[.35, .95], [.2, .1]]), np.zeros((2, 2)), {},
                                  pair_miss=np.array([.1, .8]), pair_single_peak=np.array([.2, .05]))
        scaled = tcs.scaled_local(local, 1.2, 1.1)
        self.assertTrue(np.all(scaled.peak <= scaled.total) and np.all(scaled.total <= 1))
        np.testing.assert_allclose(scaled.pair_miss, [.01, .78])   # 1 - 1.1 * (1 - miss)
        np.testing.assert_allclose(scaled.pair_single_peak, [.24, .06])

    def test_library_matching_carries_uncertainty(self):
        calculated = [{"nuclide": "CO-60", "energy_keV": 1173, "activity_multiplier": 1.07, "status": "candidate",
                       **tcs.line_uncertainty(0., .07, tcs.DEFAULTS, None)}]
        library = [{"nuclide": "Co60", "energy_keV": 1173.2}, {"nuclide": "CO-60", "energy_keV": 1500.},
                   {"nuclide": "CS-137", "energy_keV": 661.7}]
        rows = _match_library_lines(library, calculated, set())
        self.assertAlmostEqual(rows[0]["tcs_u_rel_percent"], .7)
        self.assertIsNone(rows[1]["tcs_u_rel_percent"])      # uncorrected line: no uncertainty
        self.assertEqual(rows[2]["tcs_u_rel_percent"], 0.)   # no coincidence at all: C = 1 exactly
        self.assertIsNone(_match_library_lines(library[2:], calculated, set(), False)[0]["tcs_u_rel_percent"])


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def summing(self, name, nuclides, **settings):
        project = json.loads(example_path(name).read_text())
        project.update(task="summing", nuclides=nuclides, workers=1, tcs_uncertainty=settings)
        return run_project(project, self.root / f"{name}-{len(list(self.root.iterdir()))}")

    def line(self, result, nuclide, energy):
        return next(r for r in result["summing"] if r["nuclide"] == nuclide and r["energy_keV"] == energy)

    def check_co60(self, result, tolerance):
        # Co-60 1173 keV loses counts when the 1332 keV photon is detected:
        # C = 1/(1 - eps_T(1332)), so S_T = eps_T C = C - 1 and S_P = 0.
        line = self.line(result, "CO-60", 1173)
        self.assertAlmostEqual(line["tcs_sensitivity_total"], line["activity_multiplier"] - 1, delta=tolerance)
        self.assertAlmostEqual(line["tcs_sensitivity_peak"], 0., delta=1e-3)
        # The 2506 keV sum peak only exists by summing: C is proportional to 1/eps_P.
        self.assertAlmostEqual(self.line(result, "CO-60", 2506)["tcs_sensitivity_peak"], -1., delta=2e-3)
        # Summing-in to 2159 keV: C decreases when the peak efficiency increases.
        self.assertLess(self.line(result, "CO-60", 2159)["tcs_sensitivity_peak"], 0)

    def test_cylinder_and_marinelli(self):
        for name in ("cylinder", "marinelli"):
            with self.subTest(name=name):
                result = self.summing(name, ["CO-60", "CS-134"])
                self.check_co60(result, 2e-3)
                self.assertTrue(result["tcs_uncertainty"]["enabled"])
                monte_carlo = result["tcs_uncertainty"]["monte_carlo_relative_uncertainty_percent"]
                self.assertTrue(0 < monte_carlo <= 1.0001)    # total.f stops at 1 % relative
                for row in result["summing"]:
                    expected = tcs.line_uncertainty(row["tcs_sensitivity_peak"], row["tcs_sensitivity_total"],
                                                    tcs.DEFAULTS, abs(row["tcs_sensitivity_peak"] + row["tcs_sensitivity_total"]) * monte_carlo / 100)
                    self.assertAlmostEqual(row["tcs_u_rel_percent"], expected["tcs_u_rel_percent"])
                folder = Path(result["output_directory"])
                with (folder / "summing.csv").open(newline="", encoding="utf-8") as file:
                    header = next(csv.reader(file))
                self.assertEqual(header[4:], list(tcs.FIELDS))
                self.assertIn("u(C)", (folder / "report.html").read_text(encoding="utf-8"))

    def test_sensitivity_runs_do_not_change_the_factors(self):
        on = self.summing("cylinder", ["CO-60"])
        off = self.summing("cylinder", ["CO-60"], enabled=False)
        self.assertEqual([r["activity_multiplier"] for r in on["summing"]], [r["activity_multiplier"] for r in off["summing"]])
        self.assertTrue(all(r["tcs_u_rel_percent"] is None for r in off["summing"]))
        self.assertFalse(off["tcs_uncertainty"]["enabled"])

    def test_recompute_reproduces_a_new_calculation(self):
        """u(C) recalculated from stored sensitivities equals a fresh engine run with those settings."""
        settings = {**tcs.DEFAULTS, "peak_efficiency_percent": 3., "total_efficiency_percent": 7., "peak_total_correlation": .5}
        default = self.summing("cylinder", ["CO-60"])
        fresh = self.summing("cylinder", ["CO-60"], peak_efficiency_percent=3., total_efficiency_percent=7.,
                             peak_total_correlation=.5)
        for old, new in zip(default["summing"], fresh["summing"]):
            self.assertAlmostEqual(tcs.recompute(old, settings), new["tcs_u_rel_percent"], places=9)
        self.assertIsNone(tcs.recompute(default["summing"][0], {**settings, "enabled": False}))

    def test_uncertainty_scales_with_the_input_uncertainty(self):
        small = self.line(self.summing("cylinder", ["CO-60"], total_efficiency_percent=5., peak_efficiency_percent=0.), "CO-60", 1173)
        large = self.line(self.summing("cylinder", ["CO-60"], total_efficiency_percent=10., peak_efficiency_percent=0.), "CO-60", 1173)
        self.assertAlmostEqual(large["tcs_u_total_percent"], 2 * small["tcs_u_total_percent"])

    def test_well(self):
        result = self.summing("well", ["CO-60"])
        self.check_co60(result, .02 * (self.line(result, "CO-60", 1173)["activity_multiplier"] - 1))
        line = self.line(result, "CO-60", 1173)
        self.assertAlmostEqual(line["tcs_u_numerical_percent"], 100 * next(
            r["refinement_relative_change"] for r in result["well_spatial_diagnostics"]["nuclides"][0]["corrections"]
            if r["energy_kev"] == 1173))


if __name__ == "__main__":
    unittest.main()
