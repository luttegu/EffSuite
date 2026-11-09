from dataclasses import replace
import unittest

from effsuite.correction_diagnostics import audit_corrections, plan_nlb_updates
from effsuite.parallel_coincidence import CoincidenceError


def spectrum(values):
    return b"".join(f"{i} {values.get(i, 0):.12g}\n".encode() for i in range(1, 3001))


def audit(x=.2, peak=.1, second=.21, factor=2.2222):
    return audit_corrections(spectrum({100: x}), spectrum({100: peak}),
                             spectrum({100: second}),
                             b"" if factor is None else f"100 {factor:.12g}\n".encode())[0]


class CorrectionTests(unittest.TestCase):
    def test_positive_candidate_retains_legacy_printed_factor(self):
        row = audit()
        self.assertEqual(row.status, "candidate")
        self.assertEqual(row.factor, 2.2222)
        self.assertAlmostEqual(row.denominator, .09)

    def test_negative_denominator_blocks_export(self):
        row = audit(peak=.01, second=.22, factor=-20.)
        self.assertEqual(row.status, "invalid")
        self.assertIsNone(row.factor)
        self.assertEqual(row.legacy_factor, -20.)
        with self.assertRaisesRegex(CoincidenceError, "invalid"):
            plan_nlb_updates((("EU-152", 100., .2),), {"EU-152": (row,)})

    def test_zero_denominator_is_invalid(self):
        self.assertEqual(audit(peak=.05, second=.25, factor=None).status, "invalid")

    def test_near_cancellation_requires_review(self):
        row = audit(x=1.6267e-5, peak=1.0876e-6, second=1.7352e-5, factor=6256.5)
        self.assertEqual(row.status, "review_cancellation")
        self.assertIsNone(row.factor)
        self.assertAlmostEqual(row.denominator, 2.6e-9)

    def test_positive_summing_in_below_one_is_supported(self):
        row = audit(peak=.4, second=.2, factor=.5)
        plan = plan_nlb_updates((("CS-134", 100.2, .1),), {"CS-134": (row,)})
        self.assertEqual(plan[0]["corrected_abundance"], .2)

    def test_missing_does_not_become_one(self):
        row = audit(factor=None)
        self.assertEqual(row.status, "missing")
        with self.assertRaisesRegex(CoincidenceError, "missing"):
            plan_nlb_updates((("CO-60", 100., .99),), {"CO-60": (row,)})

    def test_valid_neighbor_does_not_hide_invalid_nearest_line(self):
        bad = audit(peak=.01, second=.22, factor=-20.)
        other = replace(audit(), energy_kev=101)
        with self.assertRaisesRegex(CoincidenceError, "invalid"):
            plan_nlb_updates((("EU-152", 100.1, .2),), {"EU-152": (bad, other)})

    def test_identity_is_distinct_from_missing(self):
        row = audit(peak=.2, second=.2, factor=1.)
        self.assertEqual(row.status, "candidate")
        self.assertEqual(plan_nlb_updates((("CO-60", 100., .99),),
                                         {"CO-60": (row,)})[0]["corrected_abundance"], .99)

    def test_incomplete_intermediate_is_rejected(self):
        with self.assertRaisesRegex(CoincidenceError, "3000"):
            audit_corrections(b"100 .2\n", b"100 .1\n", b"100 .2\n", b"100 2\n")

    def test_tied_nearest_energy_is_ambiguous(self):
        rows = (audit(), replace(audit(), energy_kev=101))
        with self.assertRaisesRegex(CoincidenceError, "ambiguous"):
            plan_nlb_updates((("EU-152", 100.5, .2),), {"EU-152": rows})
