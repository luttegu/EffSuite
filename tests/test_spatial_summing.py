"""Independent analytic and event-enumeration checks for the spatial extension."""
from dataclasses import replace
import itertools
from pathlib import Path
import unittest

try:
    import numpy as np
    from effsuite.spatial_summing import (LocalEfficiencies, integrated_counts,
        log_interpolate, parse_decay, point_counts, ray_lengths, required_energies)
except ImportError:
    np = None

from effsuite.parallel_coincidence import CoincidenceError


@unittest.skipIf(np is None, "optional spatial NumPy dependency is not installed")
class SpatialTests(unittest.TestCase):
    def record(self, levels, transitions, header="10 0 1 0", name="TEST", **kwargs):
        raw = (header+"\n"+"\n".join(" ".join(map(str, row)) for row in levels)+
               "\n-1 0 0 0 0\n"+"\n".join(" ".join(map(str, row)) for row in transitions)+"\n").encode()
        return parse_decay(name, raw, **kwargs)

    def local(self, record, peak=.1, total=.2, weights=(1.,)):
        energies = required_energies((record,))
        def response(value):
            if isinstance(value, dict):
                return np.asarray([[value.get(float(e), .1) for e in energies] for _ in weights])
            return np.full((len(weights), len(energies)), value)
        return LocalEfficiencies(energies, np.asarray(weights), response(peak), response(total),
                                  np.zeros((len(weights), 2)), {})

    def chain(self):
        return self.record([[0,0,0,0,0],[100,0,0,0,0],[300,1,0,0,0]],
                           [[2,1,100,1,0,0,0],[3,2,200,1,0,0,0]])

    def test_two_gamma_summing_out_matches_analytic_probability(self):
        record = self.chain()
        result = integrated_counts((record,), self.local(record, .1, .2), 10.)
        for row in result["corrections"]:
            self.assertAlmostEqual(row["factor"], 1/.8)

    def test_counts_are_integrated_before_ratio_not_average_of_factors(self):
        record = self.chain()
        local = self.local(record, weights=(.3,.7))
        local.peak[0] = .1; local.peak[1] = .3
        local.total[0] = .2; local.total[1] = .8
        expected = (.3*.1+.7*.3)/(.3*.1*.8+.7*.3*.2)
        result = integrated_counts((record,), local, 10.)
        self.assertAlmostEqual(result["corrections"][0]["factor"], expected)
        self.assertNotAlmostEqual(expected, .3/.8+.7/.2)

    def test_parent_and_continuation_counts_are_combined_before_ratio(self):
        first = self.chain()
        second = self.record([[0,0,0,0,0],[100,.5,0,0,0]], [[2,1,100,1,0,0,0]])
        local = self.local(first, .1, .2)
        rows = integrated_counts((first, second), local, 10.)["corrections"]
        self.assertAlmostEqual(rows[0]["factor"], .15/.13)

    def test_long_lived_intermediate_splits_coincident_cascade(self):
        record = self.chain()
        levels = record.levels.copy(); levels[1,4] = 100
        record = replace(record, levels=levels)
        rows = integrated_counts((record,), self.local(record), 10.)["corrections"]
        self.assertTrue(all(abs(row["factor"]-1) < 1e-14 for row in rows))

    def test_real_summing_in_factor_below_one_is_preserved(self):
        record = self.record([[0,0,0,0,0],[100,0,0,0,0],[300,1,0,0,0]],
                             [[2,1,100,1,0,0,0],[3,2,200,.9,0,0,0],[3,1,300,.1,0,0,0]])
        rows = integrated_counts((record,), self.local(record, .2, .3), 10.)["corrections"]
        row = next(row for row in rows if row["energy_kev"] == 300)
        self.assertAlmostEqual(row["factor"], .02/(.02+.9*.2*.2))

    def test_gamma_recursion_matches_exhaustive_event_enumeration(self):
        record = self.record([[0,0,0,0,0],[100,0,0,0,0],[300,0,0,0,0],[600,1,0,0,0]],
                             [[2,1,100,1,0,0,0],[3,2,200,.7,0,0,0],[3,1,300,.3,0,0,0],
                              [4,3,300,.5,0,0,0],[4,2,500,.3,0,0,0],[4,1,600,.2,0,0,0]])
        local = self.local(record, .17, .42)
        _, observed = point_counts(record, local, 10.)
        expected = {}
        def visit(level, probability, photons):
            if level == 0:
                # Each photon is missed, fully absorbed, or deposits a partial
                # energy (which does not contribute to a discrete gamma peak).
                for outcomes in itertools.product((0,1,2), repeat=len(photons)):
                    chance = probability
                    energy = 0
                    for photon, outcome in zip(photons,outcomes):
                        chance *= (.58,.17,.25)[outcome]
                        if outcome == 1: energy += photon
                    if 2 not in outcomes:
                        expected[energy] = expected.get(energy,0)+chance
                return
            transitions = record.transitions[level]
            scale = sum(row[1] for row in transitions)
            for target,row in enumerate(transitions):
                if row[1]:visit(target,probability*row[1]/scale,photons+[int(row[0])])
        visit(3,1.,[])
        for energy in (100,200,300,500,600):
            self.assertAlmostEqual(observed[0,energy],expected.get(energy,0),places=14)

    def test_annihilation_pair_survival_is_positive_at_high_efficiency(self):
        record = self.record([[0,0,0,0,0],[511,1,0,0,0]], [[2,1,511,1,-.5,0,0]])
        local = self.local(record, .4, .8)
        row = integrated_counts((record,), local, 10.)["corrections"][0]
        self.assertAlmostEqual(row["direct_counts"], .8)
        self.assertAlmostEqual(row["coincident_counts"], 2*.4*.2)
        self.assertAlmostEqual(row["factor"], 5.)

    def test_beta_plus_pl_encoding_is_explicit_not_probability_heuristic(self):
        levels = [[0,0,0,0,0],[100,1,0,.9,0]]
        transitions = [[2,1,100,1,0,0,0]]
        capture = self.record(levels, transitions, header="10 0 1 0")
        beta = replace(capture, beta_plus_in_pl=True)
        local = self.local(beta, .1, .2)
        self.assertAlmostEqual(integrated_counts((capture,),local,10.)["corrections"][0]["factor"],1.)
        self.assertAlmostEqual(integrated_counts((beta,),local,10.)["corrections"][0]["factor"],1/(1-.9*.36))

    def test_invalid_response_probabilities_are_rejected(self):
        record = self.chain(); local = self.local(record, .5, .2)
        with self.assertRaisesRegex(CoincidenceError,"peak <= total"):
            integrated_counts((record,),local,10.)

    def test_zero_observed_peak_is_not_replaced_with_one(self):
        record = self.chain()
        rows = integrated_counts((record,),self.local(record,.1,1.),10.)["corrections"]
        self.assertTrue(all(row["factor"] is None for row in rows))

    def test_three_photon_spatial_average_avoids_negative_moment_denominator(self):
        record = self.record([[0,0,0,0,0],[100,0,0,0,0],[300,0,0,0,0],[700,1,0,0,0]],
                             [[2,1,100,1,0,0,0],[3,2,200,1,0,0,0],[4,3,400,1,0,0,0]])
        local = self.local(record, weights=(.5,.5))
        local.peak[0] = local.total[0] = .001
        local.peak[1] = local.total[1] = .9
        mean = (.001+.9)/2
        rms = np.sqrt((.001**2+.9**2)/2)
        legacy_denominator = rms*(1-rms)**2-rms+mean
        self.assertLess(legacy_denominator,0)
        expected = mean/(.5*.001*(1-.001)**2+.5*.9*(1-.9)**2)
        rows = integrated_counts((record,),local,10.)["corrections"]
        self.assertTrue(all(abs(row["factor"]-expected)<1e-12 for row in rows))
        self.assertGreater(expected, 50.)  # Legitimate large factors are not clipped.

    def test_inconsistent_conversion_coefficients_are_rejected(self):
        record = self.record([[0,0,0,0,0],[100,1,0,0,0]],
                             [[2,1,100,1,0,118,0]],header="10 1 1 0")
        with self.assertRaisesRegex(CoincidenceError,"negative transition"):
            integrated_counts((record,),self.local(record),10.)

    def test_exact_absorption_edge_uses_low_side_then_high_side(self):
        values = log_interpolate([1,2,2,3],[1,2,20,30],np.asarray([2.,2.00001]))
        self.assertAlmostEqual(values[0],2.)
        self.assertGreater(values[1],20.)

    def test_axial_and_horizontal_rays_from_above_crystal(self):
        directions = np.asarray([[0,0,-1.],[0,0,1.],[1.,0,0]])
        self.assertTrue(np.array_equal(ray_lengths(36,0,69,0,80,directions), [69.,0.,0.]))

    def test_library_indices_cannot_wrap_negative_python_indices(self):
        with self.assertRaises(CoincidenceError):
            self.record([[0,0,0,0,0],[100,1,0,0,0]], [[2,0,100,1,0,0,0]])
