"""Finite-cylinder ray intersections for the developing well-detector engine.

This module calculates geometric lengths only. It is not an efficiency or
coincidence-summing model. Cylinder and origin coordinates must share one unit.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Cylinder:
    radius: float
    z_bottom: float
    z_top: float

    def __post_init__(self):
        if not all(math.isfinite(v) for v in (self.radius, self.z_bottom, self.z_top)):
            raise ValueError("Cylinder dimensions must be finite")
        if self.radius <= 0 or self.z_top <= self.z_bottom:
            raise ValueError("Cylinder radius and height must be positive")


def cylinder_ray_length(cylinder: Cylinder, origin: tuple[float, float, float],
                        direction: tuple[float, float, float]) -> float:
    """Physical length of the forward ray inside a closed finite cylinder.

    An emitter may be above or below the cylinder. The sample itself is never
    clipped: only the ray's intersection with each material volume is clipped.
    Directions are normalized so the result has the same unit as the geometry.
    """
    if len(origin) != 3 or len(direction) != 3:
        raise ValueError("Expected three-dimensional origin and direction")
    if not all(math.isfinite(v) for v in (*origin, *direction)):
        raise ValueError("Ray coordinates must be finite")
    norm = math.hypot(*direction)
    if norm == 0:
        raise ValueError("Ray direction cannot be zero")
    ux, uy, uz = (v / norm for v in direction)
    x, y, z = origin
    a = ux * ux + uy * uy
    b = 2 * (x * ux + y * uy)
    c = x * x + y * y - cylinder.radius * cylinder.radius
    radial_enter, radial_exit = -math.inf, math.inf
    if a == 0:
        if c > 0:
            return 0.0
    else:
        discriminant = b * b - 4 * a * c
        if discriminant <= 0:
            return 0.0
        q = -0.5 * (b + math.copysign(math.sqrt(discriminant), b))
        first, second = q / a, c / q
        radial_enter, radial_exit = min(first, second), max(first, second)
    slab_enter, slab_exit = -math.inf, math.inf
    if uz == 0:
        if z < cylinder.z_bottom or z > cylinder.z_top:
            return 0.0
    else:
        first, second = (cylinder.z_bottom - z) / uz, (cylinder.z_top - z) / uz
        slab_enter, slab_exit = min(first, second), max(first, second)
    enter = max(0.0, radial_enter, slab_enter)
    leave = min(radial_exit, slab_exit)
    return max(0.0, leave - enter)
