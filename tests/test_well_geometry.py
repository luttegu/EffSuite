import math
import unittest

from effsuite.well_geometry import Cylinder, cylinder_ray_length


class WellGeometryTests(unittest.TestCase):
    def setUp(self):
        self.cylinder = Cylinder(1, 0, 2)

    def path(self, origin, direction):
        return cylinder_ray_length(self.cylinder, origin, direction)

    def test_emitter_above_detector_downward_counts_only_material(self):
        self.assertEqual(self.path((0, 0, 3), (0, 0, -1)), 2)

    def test_emitter_above_detector_pointing_away_has_no_material_path(self):
        self.assertEqual(self.path((0, 0, 3), (0, 0, 1)), 0)

    def test_diagonal_ray_can_miss_even_when_pointing_down(self):
        self.assertEqual(self.path((.5, 0, 3), (1, 0, -1)), 0)

    def test_diagonal_ray_crosses_both_caps(self):
        self.assertAlmostEqual(self.path((0, 0, 3), (.2, 0, -1)), 2 * math.sqrt(1.04))

    def test_axial_ray_inside_detector(self):
        self.assertEqual(self.path((0, 0, 1), (0, 0, 1)), 1)

    def test_horizontal_ray_inside_detector(self):
        self.assertEqual(self.path((.5, 0, 1), (1, 0, 0)), .5)

    def test_horizontal_ray_above_crystal_does_not_intersect(self):
        self.assertEqual(self.path((0, 0, 3), (1, 0, 0)), 0)

    def test_ray_starting_outside_radius_counts_entry_and_exit(self):
        self.assertEqual(self.path((3, 0, 1), (-1, 0, 0)), 2)

    def test_ray_outside_radius_pointing_away(self):
        self.assertEqual(self.path((3, 0, 1), (1, 0, 0)), 0)

    def test_tangent_ray_has_zero_path(self):
        self.assertEqual(self.path((1, 0, 1), (0, 1, 0)), 0)

    def test_ray_from_below_detector(self):
        self.assertEqual(self.path((0, 0, -1), (0, 0, 1)), 2)

    def test_crystal_top_boundary_is_continuous(self):
        below = self.path((0, 0, 2 - 1e-8), (0, 0, -1))
        equal = self.path((0, 0, 2), (0, 0, -1))
        above = self.path((0, 0, 2 + 1e-8), (0, 0, -1))
        self.assertAlmostEqual(equal, above, delta=1e-14)
        self.assertAlmostEqual(equal - below, 1e-8, delta=1e-14)

    def test_real_well_axial_path_does_not_include_space_above_crystal(self):
        outer = Cylinder(36, 0, 69)
        cavity = Cylinder(12.75, 26, 69)
        # DET07: 43 mm well in a 69 mm crystal. A source above its top,
        # directed down the axis, encounters 26 mm of bottom crystal.
        active = (cylinder_ray_length(outer, (0, 0, 80), (0, 0, -1))
                  - cylinder_ray_length(cavity, (0, 0, 80), (0, 0, -1)))
        self.assertEqual(active, 26)

    def test_rotation_around_axis_preserves_length(self):
        a = self.path((.5, 0, 1), (.3, .4, .5))
        b = self.path((0, .5, 1), (-.4, .3, .5))
        self.assertAlmostEqual(a, b, delta=1e-14)

    def test_direction_magnitude_does_not_change_physical_length(self):
        self.assertEqual(self.path((0, 0, 3), (0, 0, -100)), 2)

    def test_invalid_direction_is_rejected(self):
        with self.assertRaises(ValueError):
            self.path((0, 0, 1), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
