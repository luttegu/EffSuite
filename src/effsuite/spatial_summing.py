"""Source-guided WEFFTRAN extension: integrate counts before taking ratios.

The cascade recursion is adapted from Tim Vidmar's EFFTRAN/WEFFTRAN source.
Copyright (c) 1995-2016 Tim Vidmar.
Permission to use, copy, modify, distribute and sell this software and its
documentation for any purpose is hereby granted without fee, provided that
the above copyright notice appears in all copies and that both that copyright
notice and this permission notice appear in all supporting documentation.
Tim Vidmar makes no representations about the suitability of this software
for any purpose. It is provided 'as is' without express or implied warranty.

The legacy spatially uniform virtual-total/peak-to-total/build-up scaling was
replaced by a local, probability-conserving ray-traced well response (see
well_local_response). It is still a deterministic approximation, not a Monte
Carlo simulation. See EFFTRAN_MEFFTRAN_WEFFTRAN_CHANGES.md for validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path

import numpy as np
from numpy.polynomial.legendre import leggauss

from .model_io import COMMON_DATA
from .parallel_coincidence import CoincidenceError, CalculationCancelled


@dataclass(frozen=True)
class Decay:
    name: str
    raw_hash: str
    xray: tuple[float, float, float, float]
    levels: np.ndarray
    transitions: np.ndarray
    beta_plus_in_pl: bool = False


def parse_decay(name: str, raw: bytes, *, beta_plus_in_pl=False) -> Decay:
    try:
        lines = [line.split() for line in raw.decode("ascii").splitlines() if line.strip()]
        numeric = [[float(v.replace("D", "E").replace("d", "e")) for v in line] for line in lines]
        header = numeric[0]
        if len(header) != 4:
            raise ValueError("four X-ray fields required")
        levels = []
        position = 1
        while numeric[position][0] >= 0:
            if len(numeric[position]) != 5:
                raise ValueError("five level fields required")
            levels.append(numeric[position])
            position += 1
        if not 1 <= len(levels) <= 100:
            raise ValueError("one to 100 levels required")
        transitions = np.zeros((len(levels), len(levels), 5), dtype=float)
        seen = set()
        for row in numeric[position+1:]:
            if len(row) != 7:
                raise ValueError("seven transition fields required")
            i, j = int(row[0])-1, int(row[1])-1
            if row[0] != i+1 or row[1] != j+1 or not 0 <= j < i < len(levels) or (i, j) in seen:
                raise ValueError("invalid or duplicate transition indices")
            seen.add((i, j))
            energy, intensity, alpha, ak, al = row[2:]
            if energy <= 0 or intensity < 0 or ak < 0 or al < 0 or alpha <= -1:
                raise ValueError("invalid transition")
            if alpha < 0 and not (abs(alpha+.5) < 1e-12 and abs(energy-511.) < 1e-8):
                raise ValueError("unsupported negative conversion coefficient")
            transitions[i, j] = row[2:]
        array = np.asarray(levels)
        if not np.isfinite(array).all() or not np.isfinite(transitions).all() or not np.isfinite(header).all():
            raise ValueError("nonfinite decay data")
        if np.any(array[:, 1:] < 0) or min(header) < 0 or max(header[1], header[3]) > 1:
            raise ValueError("invalid feeding, half-life or X-ray yield")
        return Decay(name, sha256(raw).hexdigest(), tuple(header), array, transitions, beta_plus_in_pl)
    except (ValueError, IndexError, UnicodeError) as exc:
        raise CoincidenceError(f"{name}: invalid Decay_Data record: {exc}") from exc


def required_energies(records: tuple[Decay, ...]) -> np.ndarray:
    values = {511.}
    for record in records:
        values.update(float(e) for e in record.transitions[:, :, 0].flat if e > 0)
        values.update(e for e in (record.xray[0], record.xray[2]) if e > 0)
    return np.asarray(sorted(values))


def log_interpolate(x, y, query):
    """Legacy log/log interpolation, with its end-interval extrapolation.

    Search from the low-energy side at an exact repeated absorption edge.
    """
    x, y, query = np.asarray(x), np.asarray(y), np.asarray(query)
    if len(x) < 2 or len(x) != len(y) or np.any(np.diff(x) < 0):
        raise CoincidenceError("Interpolation table must be sorted with at least two points")
    if not (np.isfinite(x).all() and np.isfinite(y).all() and np.isfinite(query).all()):
        raise CoincidenceError("Nonfinite interpolation input")
    if np.any(x <= 0) or np.any(y <= 0) or np.any(query <= 0):
        raise CoincidenceError("Logarithmic interpolation requires positive inputs")
    indices = np.clip(np.searchsorted(x, query, side="left")-1, 0, len(x)-2)
    lx, ly = np.log(x), np.log(y)
    width = lx[indices+1]-lx[indices]
    if np.any(width <= 0):
        raise CoincidenceError("Degenerate interpolation interval")
    return np.exp(ly[indices] + (ly[indices+1]-ly[indices]) / width * (np.log(query)-lx[indices]))


def material_mu(installation: Path, name: str, energy: np.ndarray) -> np.ndarray:
    comp_path = installation / "Composition" / (name+".txt")
    if not comp_path.is_file():
        comp_path = COMMON_DATA / "Composition" / (name+".txt")
    density = float(comp_path.read_text().split()[0])
    rows = []
    mat_path = installation / "Material" / (name+".txt")
    if not mat_path.is_file():
        mat_path = COMMON_DATA / "Material" / (name+".txt")
    for line in mat_path.read_text(encoding="cp1252").splitlines():
        try:
            values = [float(token) for token in line[7:].split()]
        except ValueError:
            continue
        if len(values) == 8:
            # XCOM total without coherent scattering, density in g/cm3,
            # conversion from inverse cm to inverse mm: same as total.f.
            rows.append((values[0]*1000., max(values[7]*density, 1e-15)/10.))
    if density <= 0 or len(rows) < 2 or not math.isfinite(density):
        raise CoincidenceError(f"Invalid material table: {name}")
    table = np.asarray(rows)
    if np.any(np.diff(table[:, 0]) < 0):
        raise CoincidenceError(f"Unsorted material table: {name}")
    return log_interpolate(table[:, 0], table[:, 1], energy)


def ray_lengths(radius: float, bottom: float, top: float,
                r: float, z: float, directions: np.ndarray) -> np.ndarray:
    """Forward-ray intersection with a finite cylinder, including external origins."""
    ux, uy, uz = directions.T
    transverse = ux*ux + uy*uy
    radial_lo = np.full(len(uz), -np.inf)
    radial_hi = np.full(len(uz), np.inf)
    if r > radius:
        radial_hi[transverse == 0] = -np.inf
    mask = transverse > 0
    b = 2*r*ux[mask]
    c = r*r-radius*radius
    discriminant = b*b-4*transverse[mask]*c
    roots = np.sqrt(np.maximum(discriminant, 0.))
    radial_lo[mask] = (-b-roots)/(2*transverse[mask])
    radial_hi[mask] = (-b+roots)/(2*transverse[mask])
    radial_hi[np.flatnonzero(mask)[discriminant <= 0]] = -np.inf
    axial_lo = np.full(len(uz), -np.inf)
    axial_hi = np.full(len(uz), np.inf)
    if not bottom <= z <= top:
        axial_hi[uz == 0] = -np.inf
    mask = uz != 0
    first, second = (bottom-z)/uz[mask], (top-z)/uz[mask]
    axial_lo[mask], axial_hi[mask] = np.minimum(first, second), np.maximum(first, second)
    return np.maximum(0., np.minimum(radial_hi, axial_hi)-np.maximum(0., np.maximum(radial_lo, axial_lo)))


@dataclass(frozen=True)
class Quadrature:
    radial: int = 4
    axial: int = 8
    polar: int = 32
    azimuth: int = 64

    def refined(self):
        return Quadrature(self.radial*2, self.axial*2, self.polar*2, self.azimuth*2)


@dataclass(frozen=True)
class LocalEfficiencies:
    energies: np.ndarray
    weights: np.ndarray
    peak: np.ndarray
    total: np.ndarray
    points: np.ndarray
    metadata: dict
    pair_miss: np.ndarray | None = None
    pair_single_peak: np.ndarray | None = None


def _xcom_table(installation: Path, name: str) -> np.ndarray:
    """XCOM table in 1/mm: energy [keV], Rayleigh, Compton, photoelectric, pair,
    total with coherent, total without coherent (the legacy attenuation)."""
    comp_path = installation / "Composition" / (name+".txt")
    if not comp_path.is_file():
        comp_path = COMMON_DATA / "Composition" / (name+".txt")
    density = float(comp_path.read_text().split()[0])
    mat_path = installation / "Material" / (name+".txt")
    if not mat_path.is_file():
        mat_path = COMMON_DATA / "Material" / (name+".txt")
    rows = []
    for line in mat_path.read_text(encoding="cp1252").splitlines():
        try:
            v = [float(token) for token in line[7:].split()]
        except ValueError:
            continue
        if len(v) == 8:
            s = density/10.
            rows.append((v[0]*1000., max(v[1]*s, 1e-15), max(v[2]*s, 1e-15), max(v[3]*s, 1e-15),
                         max((v[4]+v[5])*s, 1e-15), max(v[6]*s, 1e-15), max(v[7]*s, 1e-15)))
    if density <= 0 or len(rows) < 2 or not math.isfinite(density):
        raise CoincidenceError(f"Invalid material table: {name}")
    table = np.asarray(rows)
    if np.any(np.diff(table[:, 0]) < 0):
        raise CoincidenceError(f"Unsorted material table: {name}")
    return np.column_stack((table, np.full(len(table), density)))


def _xcom(table, energy):
    q = np.maximum(np.asarray(energy, dtype=float), 1.)
    return tuple(log_interpolate(table[:, 0], table[:, col], q) for col in range(1, 7))


def _ray_interval(radius, bottom, top, r, z, directions):
    """Entry and exit parameters of forward rays through a finite cylinder."""
    ux, uy, uz = directions.T
    transverse = ux*ux + uy*uy
    radial_lo = np.full(len(uz), -np.inf)
    radial_hi = np.full(len(uz), np.inf)
    if r > radius:
        radial_hi[transverse == 0] = -np.inf
    mask = transverse > 0
    b = 2*r*ux[mask]
    disc = b*b - 4*transverse[mask]*(r*r-radius*radius)
    roots = np.sqrt(np.maximum(disc, 0.))
    radial_lo[mask] = (-b-roots)/(2*transverse[mask])
    radial_hi[mask] = (-b+roots)/(2*transverse[mask])
    radial_hi[np.flatnonzero(mask)[disc <= 0]] = -np.inf
    axial_lo = np.full(len(uz), -np.inf)
    axial_hi = np.full(len(uz), np.inf)
    if not bottom <= z <= top:
        axial_hi[uz == 0] = -np.inf
    mz = uz != 0
    first, second = (bottom-z)/uz[mz], (top-z)/uz[mz]
    axial_lo[mz], axial_hi[mz] = np.minimum(first, second), np.maximum(first, second)
    t_in = np.maximum(0., np.maximum(radial_lo, axial_lo))
    return t_in, np.maximum(t_in, np.minimum(radial_hi, axial_hi))


def _mean_compton_energy(energy):
    """Klein-Nishina mean scattered-photon energy (as in the original buildup.f)."""
    e = np.asarray(energy, dtype=float)
    g = np.maximum(e/511., 1e-3)
    y = np.log(1+2*g)
    u = ((-6*g-30*g**2-36*g**3+12*g**4+32*g**5+3*y+18*g*y+36*g**2*y+24*g**3*y) /
         (3*(1+2*g)*(4*g+16*g**2+18*g**3+2*g**4-2*y-10*g*y-15*g**2*y-4*g**3*y+4*g**4*y)))
    g0 = e/511.
    return e*np.where(g0 < 1e-3, 1-g0+26/5*g0**2, u)


def _mean_compton_cosine(energy):
    g = np.maximum(np.asarray(energy, dtype=float)/511., 1e-4)[:, None]
    ct, wt = leggauss(16)
    p = 1/(1+g*(1-ct[None, :]))
    ds = .5*p**2*(p+1/p-1+ct[None, :]**2)
    return np.sum(ds*ct*wt, axis=1)/np.sum(ds*wt, axis=1)


def _crystal_zz_aa(installation: Path, prepared: Path, name: str):
    for folder in (prepared, installation, COMMON_DATA.parent/"engines"/"well"):
        path = folder/"zzaa.txt"
        if path.is_file():
            lines = [line.strip() for line in path.read_text(errors="replace").splitlines() if line.strip()]
            for label, values in zip(lines[::2], lines[1::2]):
                if label.lower() == name.lower():
                    try:
                        z, a = [float(v) for v in values.split()[:2]]
                        return z, a
                    except ValueError:
                        pass
    return 32., 72.63


_CRYSTAL_CACHE = {}


def _crystal_model(dr, dl, dd, well_d, well_h, table, zz, aa,
                   mantle_dead=None, bottom_dead=None):
    """Hollow-crystal peak-to-total (solid cylinder replaced by the real crystal with
    its well) and the local containment of first-scattered photons."""
    if mantle_dead is None: mantle_dead = dd
    if bottom_dead is None: bottom_dead = dd
    key = (dr, dl, dd, well_d, well_h, zz, aa, mantle_dead, bottom_dead, sha256(table.tobytes()).hexdigest())
    if key in _CRYSTAL_CACHE:
        return _CRYSTAL_CACHE[key]
    r_out = dr/2
    r_hole, z_hole = well_d/2+dd, dl-well_h-dd
    r_act_out = max(well_d/2 + dd + 0.1, dr/2 - mantle_dead)
    z_act_bottom = min(dl - well_h - dd - 0.1, bottom_dead)
    mu, wm = leggauss(16)
    phi = (np.arange(32)+.5)*2*np.pi/32
    dirs = np.column_stack((np.repeat(np.sqrt(1-mu*mu), 32)*np.tile(np.cos(phi), 16),
                            np.repeat(np.sqrt(1-mu*mu), 32)*np.tile(np.sin(phi), 16), np.repeat(mu, 32)))
    dw = np.repeat(wm/2/32, 32)
    egrid = np.exp(np.linspace(np.log(10.), np.log(3000.), 45))
    mu_ge = _xcom(table, egrid)[5]

    def active(r0, z0):
        return np.maximum(0., ray_lengths(r_act_out, z_act_bottom, dl, r0, z0, dirs) -
                          ray_lengths(r_hole, z_hole, dl+10., r0, z0, dirs))

    qr, wr = leggauss(6); qz, wz = leggauss(8)
    eta_mean, volume = np.zeros(len(egrid)), 0.
    for uz_, wz_ in zip((qz+1)/2, wz/2):
        z0 = z_act_bottom + uz_*(dl - z_act_bottom)
        r_in = r_hole if z0 >= z_hole else 0.
        if r_act_out > r_in:
            area = r_act_out**2 - r_in**2
            for ur, wr_ in zip((qr+1)/2, wr/2):
                d = active(math.sqrt(r_in**2+ur*area), z0)
                eta_mean += wz_*wr_*area*np.sum(-np.expm1(-d[:, None]*mu_ge[None, :])*dw[:, None], axis=0)
                volume += wz_*wr_*area
    if volume > 0:
        eta_mean /= volume
    z_nodes = np.unique(np.clip(np.array([z_act_bottom+0.5, .5*(z_hole+z_act_bottom), z_hole+1.,
                                          z_hole+.35*(dl-z_hole), z_hole+.7*(dl-z_hole),
                                          dl-5., dl-1.5, dl-.3]), z_act_bottom+0.1, dl-.1))
    r_fracs = np.array([.05, .3, .65, .95])
    eta_grid = np.empty((len(r_fracs), len(z_nodes), len(egrid)))
    for iz, z0 in enumerate(z_nodes):
        r_in = r_hole if z0 >= z_hole else 0.
        for ir, f in enumerate(r_fracs):
            d = active(r_in+f*(r_act_out-r_in), z0)
            eta_grid[ir, iz] = np.sum(-np.expm1(-d[:, None]*mu_ge[None, :])*dw[:, None], axis=0)
    # Radiation length of the original ptt.f, with the actual active crystal volume fraction.
    act_vol = max(1e-6, r_act_out**2*(dl-z_act_bottom) - r_hole**2*(dl-z_hole))
    dv = act_vol / (r_out**2*dl)
    re_, alpha, na = 2.817e-13, 7.297e-3, 6.022e23
    xz = zz*alpha; w = xz*xz
    fz = w*(1/(1+w)+.20206-.0369*w+.0083*w**2-.002*w**3)
    density = table[0, 7]
    rad_len = 10./(4*zz*(zz+1)*density*dv*na/aa*re_**2*alpha*(math.log(183.*zz**(-1/3))-fz))
    kev = np.arange(1, 3001, dtype=float)
    gmc, gmf, gmp = _xcom(table, kev)[1:4]
    gm = gmf+gmc+gmp
    t = np.ones(3001); t[1:] = np.clip(log_interpolate(egrid, eta_mean, kev), 0., 1.)
    u = np.ones(3001); wcomp = np.ones(3001)
    for i in range(11, 3001):
        g = i/511.
        j = np.arange(int(i/(2*g+1)+.5), i)
        de = i-j.astype(float)
        rng = np.maximum(0., de/1000.-1.)
        k = np.maximum(1, (de*(1-np.exp(-rng/rad_len))+.5).astype(int))
        p = j/i
        costh = 1-(1/p-1)/g
        q = (p+1/p-1+costh*costh)/i/g
        esc = np.maximum(0., 1-rng/r_act_out-rng/(dl-z_act_bottom))
        qs = np.sum(q)
        wcomp[i] = 1. if qs <= 0 else np.sum(u[j]*t[j]*q*t[k]*esc)/qs
        u[i] = (gmf[i-1]+gmc[i-1]*wcomp[i]+gmp[i-1]*(u[511]*t[511])**2)/gm[i-1]
    model = {"r_out": r_out, "r_act_out": r_act_out, "z_act_bottom": z_act_bottom,
             "r_hole": r_hole, "z_hole": z_hole, "egrid": egrid, "eta_mean": eta_mean,
             "r_fracs": r_fracs, "z_nodes": z_nodes, "eta_grid": eta_grid, "kev": kev,
             "u": u[1:], "wcomp": wcomp[1:], "pair": (u[511]*t[511])**2}
    _CRYSTAL_CACHE[key] = model
    return model


def well_local_response(installation: Path, detector, source, energies, order=Quadrature(),
                        cancel=None, zz_aa=(32., 72.63)):
    """Local peak and total efficiency for every sample node.

    Physics (all first principles, no fitted constants):
    * uncollided and Compton-scattered photons are traced through sample, container,
      the bore liner and the top-face housing (thickness = absorber thickness);
    * optional thicker mantle (side) and crystal bottom dead layers restrict the
      active Ge volume while attenuating peripheral gammas;
    * optional mount cup (holder) provides Compton backscatter and containment;
    * a photon interacting upstream is either absorbed, Rayleigh scattered or Compton
      scattered, so total efficiency is a sum of mutually exclusive fates (<= 1);
    * scattered photons are detected from the local cavity response of the well;
    * peak-to-total uses the real hollow crystal and the local containment of the
      first-scattered photon at the actual interaction depth;
    * exact antiparallel 511 keV pair probabilities (back-to-back annihilation photons).
    """
    dr, dl, dd, well_d, well_h = [float(v) for v in detector[:5]]
    sr, height, base, wall, offset = [float(v) for v in source[:5]]
    dmat = str(detector[5]).strip()
    amat = str(detector[6]).strip()
    mantle_dead = float(detector[7]) if len(detector) > 7 and str(detector[7]).strip() != "" else dd
    bottom_dead = float(detector[8]) if len(detector) > 8 and str(detector[8]).strip() != "" else dd
    holder_thickness = float(detector[9]) if len(detector) > 9 and str(detector[9]).strip() != "" else 0.0
    det_sample_offset = float(detector[10]) if len(detector) > 10 and str(detector[10]).strip() != "" else 0.0
    holder_material = str(detector[11]).strip() if len(detector) > 11 and str(detector[11]).strip() != "" else "copper"

    tables = [_xcom_table(installation, str(name).strip()) for name in (dmat, amat, source[5], source[6])]
    ge_t, al_t, sm_t, bm_t = tables
    hl_t = _xcom_table(installation, holder_material) if holder_thickness > 0 else None
    model = _crystal_model(dr, dl, dd, well_d, well_h, ge_t, *zz_aa,
                           mantle_dead=mantle_dead, bottom_dead=bottom_dead)
    r_out, r_hole, z_hole = model["r_out"], model["r_hole"], model["z_hole"]
    r_act_out, z_act_bottom = model["r_act_out"], model["z_act_bottom"]
    flange = dd
    total_offset = offset + det_sample_offset
    radius = sr/2-wall
    bottom = dl-well_h+total_offset+base
    top = bottom+height
    boundaries = sorted({bottom, top} | ({dl} if bottom < dl < top else set()))
    qr, wr = leggauss(order.radial); qz, wz = leggauss(order.axial)
    points, weights = [], []
    for lower, upper in zip(boundaries[:-1], boundaries[1:]):
        for u_, ru in zip((qr+1)/2, wr/2):
            for zz_, zw in zip((qz+1)*(upper-lower)/2+lower, wz*(upper-lower)/(2*height)):
                points.append((radius*np.sqrt(u_), zz_)); weights.append(ru*zw)
    points, weights = np.asarray(points), np.asarray(weights)

    def directions(polar, azimuth):
        mu, wm = leggauss(polar)
        phi = (np.arange(azimuth)+.5)*2*np.pi/azimuth
        s = np.sqrt(1-mu*mu)
        return (np.column_stack((np.repeat(s, azimuth)*np.tile(np.cos(phi), polar),
                                 np.repeat(s, azimuth)*np.tile(np.sin(phi), polar), np.repeat(mu, azimuth))),
                np.repeat(wm/2/azimuth, azimuth))
    dirs, dw = directions(order.polar, order.azimuth)

    def trace(r, z, d):
        t0a, t1a = _ray_interval(r_act_out, z_act_bottom, dl, r, z, d)
        t0h, t1h = _ray_interval(r_hole, z_hole, dl+10., r, z, d)
        overlap = np.maximum(0., np.minimum(t1a, t1h)-np.maximum(t0a, t0h))
        crystal = np.maximum(0., (t1a-t0a)-overlap)
        via_hole = (t1h > t0a) & (overlap > 0)
        t_entry = np.where(via_hole, np.minimum(t1a, t1h), t0a)
        bore = np.maximum(0., ray_lengths(r_hole, z_hole, dl, r, z, d) - ray_lengths(well_d/2, dl-well_h, dl, r, z, d))
        if flange > 0:
            bore = bore+np.maximum(0., ray_lengths(dr/2, dl, dl+flange, r, z, d) -
                                   ray_lengths(well_d/2, dl, dl+flange, r, z, d))
        s0, s1 = _ray_interval(radius, bottom, top, r, z, d)
        c0, c1 = _ray_interval(sr/2, bottom-base, top+base, r, z, d)
        sample, container = s1-s0, np.maximum(0., (c1-c0)-(s1-s0))
        b0, b1 = _ray_interval(r_hole, z_hole, dl+flange, r, z, d)
        up_end = np.where(crystal > 0, t_entry, np.maximum(c1, b1))
        up_start = np.minimum(np.where(sample+container > 0, np.minimum(c0, b0), b0), up_end)

        t0p, t1p = _ray_interval(dr/2, 0., dl, r, z, d)
        overlap_p = np.maximum(0., np.minimum(t1p, t1h)-np.maximum(t0p, t0h))
        phys_ge = np.maximum(0., (t1p-t0p)-overlap_p)
        dead_ge = np.maximum(0., phys_ge - crystal)

        if holder_thickness > 0:
            holder = np.maximum(0., ray_lengths(dr/2+holder_thickness, -holder_thickness, dl, r, z, d) -
                                    ray_lengths(dr/2, 0., dl, r, z, d))
        else:
            holder = np.zeros_like(crystal)
        return crystal, t_entry, bore, sample, container, up_start, up_end, dead_ge, holder

    # Cavity response: probability that a photon created isotropically at (r, z) is
    # detected, including Rayleigh and repeated Compton scattering.
    scat_grid = np.exp(np.linspace(0., np.log(3000.), 80))
    g_ge, g_al, g_sm, g_bm = [_xcom(t, scat_grid) for t in tables]
    cdirs, cw = directions(16, 32)
    r_cav = np.array([0., .45*well_d/2, .92*well_d/2])
    z_top_cav = max(dl+flange, top+base)
    z_cav = np.unique(np.concatenate([np.linspace(dl-well_h+.5, dl-.5, 6),
                                       np.linspace(dl+.2, z_top_cav, 5) if z_top_cav > dl+.3 else [dl+.2]]))
    p0 = np.zeros((len(r_cav), len(z_cav), len(scat_grid)))
    srl, scp = np.zeros_like(p0), np.zeros_like(p0)
    for ir, rc in enumerate(r_cav):
        for iz, zc in enumerate(z_cav):
            cg, _, bo, sa, co, _, _, _, _ = trace(float(rc), float(zc), cdirs)
            tau = sa[:, None]*g_sm[4]+co[:, None]*g_bm[4]+bo[:, None]*g_al[4]
            rayl = sa[:, None]*g_sm[0]+co[:, None]*g_bm[0]+bo[:, None]*g_al[0]
            comp = sa[:, None]*g_sm[1]+co[:, None]*g_bm[1]+bo[:, None]*g_al[1]
            safe = np.maximum(tau, 1e-15)
            p0[ir, iz] = np.sum(np.exp(-tau)*-np.expm1(-cg[:, None]*g_ge[5][None, :])*cw[:, None], axis=0)
            srl[ir, iz] = np.sum(-np.expm1(-tau)*rayl/safe*cw[:, None], axis=0)
            scp[ir, iz] = np.sum(-np.expm1(-tau)*comp/safe*cw[:, None], axis=0)
    piso = np.zeros_like(p0)
    nxt = _mean_compton_energy(scat_grid)
    for ie in range(len(scat_grid)):
        denom = np.maximum(1-srl[:, :, ie], 1e-6)
        if ie == 0 or nxt[ie] <= scat_grid[0]:
            follow = p0[:, :, 0]/np.maximum(1-srl[:, :, 0], 1e-6)
        else:
            hi = int(np.searchsorted(scat_grid[:ie+1], nxt[ie], side="right"))
            lo = max(0, min(hi-1, ie-1)); hi = min(lo+1, ie)
            if hi == lo:
                follow = piso[:, :, lo]
            else:
                f = math.log(nxt[ie]/scat_grid[lo])/math.log(scat_grid[hi]/scat_grid[lo])
                follow = (1-f)*piso[:, :, lo]+f*piso[:, :, hi]
        piso[:, :, ie] = np.clip((p0[:, :, ie]+scp[:, :, ie]*follow)/denom, 0., 1.)
    e1 = _mean_compton_energy(energies)
    ge, al, sm, bm = [_xcom(t, energies) for t in tables]
    ge1, al1, sm1, bm1 = [_xcom(t, e1) for t in tables]
    hl = _xcom(hl_t, energies) if hl_t is not None else None
    kn = np.clip(_mean_compton_cosine(energies), 0., 1.)
    piso_e = np.empty((len(r_cav), len(z_cav), len(energies)))
    piso_e1 = np.empty_like(piso_e)
    for ir in range(len(r_cav)):
        for iz in range(len(z_cav)):
            curve = np.maximum(piso[ir, iz], 1e-15)
            piso_e[ir, iz] = np.clip(log_interpolate(scat_grid[1:], curve[1:], np.maximum(energies, 1.)), 0., 1.)
            piso_e1[ir, iz] = np.clip(log_interpolate(scat_grid[1:], curve[1:], np.maximum(e1, 1.)), 0., 1.)
    kev = model["kev"]
    wcomp = log_interpolate(kev, model["wcomp"], np.maximum(energies, 1.))
    eta_mean1 = np.clip(log_interpolate(model["egrid"], model["eta_mean"], np.clip(e1, 10., 3000.)), 1e-4, 1.)
    eta_grid1 = np.empty((len(model["r_fracs"]), len(model["z_nodes"]), len(energies)))
    for ir in range(eta_grid1.shape[0]):
        for iz in range(eta_grid1.shape[1]):
            eta_grid1[ir, iz] = np.clip(log_interpolate(model["egrid"], model["eta_grid"][ir, iz],
                                                        np.clip(e1, 10., 3000.)), 0., 1.)
    gm_ge = ge[1]+ge[2]+ge[3]
    pair_term = ge[3]*model["pair"]
    mu_ge, mu_ge1 = ge[5], ge1[5]
    cols = np.arange(len(energies))[None, :]

    def interp(grid, rq, zq, r_ax, z_ax):
        rq, zq = np.clip(rq, r_ax[0], r_ax[-1]), np.clip(zq, z_ax[0], z_ax[-1])
        i = np.clip(np.searchsorted(r_ax, rq, side="right")-1, 0, len(r_ax)-2)
        j = np.clip(np.searchsorted(z_ax, zq, side="right")-1, 0, len(z_ax)-2)
        a = (rq-r_ax[i])/np.maximum(r_ax[i+1]-r_ax[i], 1e-9)
        b = (zq-z_ax[j])/np.maximum(z_ax[j+1]-z_ax[j], 1e-9)
        return (1-a)*((1-b)*grid[i, j, cols]+b*grid[i, j+1, cols])+a*((1-b)*grid[i+1, j, cols]+b*grid[i+1, j+1, cols])

    peak = np.zeros((len(points), len(energies)))
    total = np.zeros_like(peak)
    pair_miss, pair_single = np.zeros(len(points)), np.zeros(len(points))
    i511 = int(np.argmin(np.abs(energies-511.)))
    has511 = abs(energies[i511]-511.) < 1e-6
    raw_max = 0.
    for index, (r, z) in enumerate(points):
        if cancel is not None and cancel.is_set():
            raise CalculationCancelled("Calculation cancelled")
        crystal, entry, bore, sa, co, up0, up1, dead_ge, holder = trace(float(r), float(z), dirs)
        hit = crystal > 1e-9
        tau_i = sa[:, None]*sm[5]+co[:, None]*bm[5]+bore[:, None]*al[5]
        p_dir = -np.expm1(-crystal[:, None]*mu_ge[None, :])
        # peak: uncollided and locally contained
        x = np.maximum(crystal[:, None]*mu_ge[None, :], 1e-8)
        depth = np.where(x > 50., 1/mu_ge[None, :], np.where(x < 1e-3, .5*crystal[:, None],
                         1/mu_ge[None, :]-crystal[:, None]/np.expm1(np.minimum(x, 50.))))
        remain = np.maximum(0., crystal[:, None]-depth)
        t_mid = entry[:, None]+depth
        z_int = np.clip(z+dirs[:, 2:3]*t_mid, z_act_bottom, dl)
        r_int = np.hypot(r+dirs[:, 0:1]*t_mid, dirs[:, 1:2]*t_mid)
        r_in = np.where(z_int >= z_hole, r_hole, 0.)
        frac = (r_int-r_in)/np.maximum(r_act_out-r_in, 1.)
        eta_iso = interp(eta_grid1, frac, z_int, model["r_fracs"], model["z_nodes"])
        eta_fwd = -np.expm1(-remain*mu_ge1[None, :])
        eta1 = kn[None, :]*eta_fwd+(1-kn[None, :])*eta_iso
        w_loc = np.clip(wcomp[None, :]*np.clip(eta1/eta_mean1[None, :], 0., 1.35), 0., 1.)
        pv = np.clip((ge[2][None, :]+ge[1][None, :]*w_loc+pair_term[None, :])/gm_ge[None, :], 0., 1.)
        pk = np.exp(-tau_i)*p_dir*np.where(hit[:, None], pv, 0.)
        # total: mutually exclusive fates of the photon
        tau = sa[:, None]*sm[4]+co[:, None]*bm[4]+bore[:, None]*al[4]
        rayl = sa[:, None]*sm[0]+co[:, None]*bm[0]+bore[:, None]*al[0]
        comp = sa[:, None]*sm[1]+co[:, None]*bm[1]+bore[:, None]*al[1]
        safe = np.maximum(tau, 1e-15)
        fs = np.where(tau > 50., 1/np.maximum(tau, 1e-15),
                      np.where(tau < 1e-3, .5, 1/np.maximum(tau, 1e-15)-1/np.expm1(np.minimum(tau, 50.))))
        span = np.maximum(0., up1-up0)[:, None]
        t_sc = up0[:, None]+span*fs
        z_sc = z+dirs[:, 2:3]*t_sc
        r_sc = np.hypot(r+dirs[:, 0:1]*t_sc, dirs[:, 1:2]*t_sc)
        det_rayl = .65*p_dir*np.exp(-(1-fs)*tau_i)+.35*interp(piso_e, r_sc, z_sc, r_cav, z_cav)
        rest = (1-fs)*(sa[:, None]*sm1[5]+co[:, None]*bm1[5]+bore[:, None]*al1[5])
        det_comp = (kn[None, :]**2*(-np.expm1(-crystal[:, None]*mu_ge1[None, :]))*np.exp(-rest) +
                    (1-kn[None, :]**2)*interp(piso_e1, r_sc, z_sc, r_cav, z_cav))
        tot = np.exp(-tau)*p_dir-np.expm1(-tau)*(rayl/safe*det_rayl+comp/safe*det_comp)

        if holder_thickness > 0 and hl is not None:
            # Mount cup (holder) Compton backscatter
            p_reach_holder = np.exp(-tau) * np.exp(-crystal[:, None]*mu_ge[None, :]) * np.exp(-dead_ge[:, None]*mu_ge[None, :])
            p_holder_comp = -np.expm1(-holder[:, None]*hl[1][None, :])
            eb = energies / (1.0 + 1.4 * energies / 511.0)
            mu_ge_back = _xcom(ge_t, eb)[5]
            p_ge_absorb = -np.expm1(-25.0 * mu_ge_back[None, :])
            tot = tot + p_reach_holder * p_holder_comp * 0.40 * p_ge_absorb

        raw_max = max(raw_max, float(tot.max()))
        tot = np.clip(np.maximum(tot, pk), 0., 1.)
        peak[index], total[index] = np.sum(pk*dw[:, None], axis=0), np.sum(tot*dw[:, None], axis=0)
        if has511:
            # Gauss-Legendre polar nodes are symmetric and the azimuth count is even, so the
            # antiparallel direction of ray (i, j) is (P-1-i, j+A/2): no extra ray tracing.
            P, A = order.polar, order.azimuth
            t_p, p_p = tot[:, i511], pk[:, i511]
            t_o = np.roll(t_p.reshape(P, A)[::-1, :], A//2, axis=1).ravel()
            p_o = np.roll(p_p.reshape(P, A)[::-1, :], A//2, axis=1).ravel()
            pair_miss[index] = float(np.sum(dw*(1-t_p)*(1-t_o)))
            pair_single[index] = float(np.sum(dw*(p_p*(1-t_o)+p_o*(1-t_p))))
    return LocalEfficiencies(energies, weights, peak, total, points,
                             {"quadrature": vars(order), "spatial_points": len(points),
                              "angular_directions": len(dirs), "sample_bottom_mm": bottom,
                              "sample_top_mm": top, "crystal_top_mm": dl,
                              "probability_saturation_count": int(raw_max > 1.+1e-9),
                              "maximum_unsaturated_total": raw_max},
                             pair_miss if has511 else None, pair_single if has511 else None)


def well_peak_efficiencies(installation: Path, detector, source, energies, order=Quadrature(),
                           cancel=None, zz_aa=(32., 72.63)) -> np.ndarray:
    """Volume-averaged full-energy-peak efficiency of a well sample (up to a common scale)."""
    local = well_local_response(installation, detector, source, np.asarray(energies, dtype=float),
                                order, cancel, zz_aa)
    return np.sum(local.weights[:, None]*local.peak, axis=0)


def prepare_local(installation: Path, prepared: Path, energies: np.ndarray,
                  order: Quadrature = Quadrature(), cancel=None) -> LocalEfficiencies:
    if any(type(value) is not int or value < 2 or (name == "azimuth" and value % 2)
           for name, value in vars(order).items()):
        raise CoincidenceError("Quadrature orders must be integers of at least two (azimuth even)")
    detector_raw, source_raw = (prepared/"detector.txt").read_bytes(), (prepared/"source.txt").read_bytes()
    detector = [line.split("#")[0].strip() for line in detector_raw.decode("utf-8-sig", errors="replace").splitlines() if line.split("#")[0].strip()]
    source = [line.split("#")[0].strip() for line in source_raw.decode("utf-8-sig", errors="replace").splitlines() if line.split("#")[0].strip()]
    dr, dl, dd, well_d, well_h = [float(v) for v in detector[:5]]
    sr, height, base, wall, offset = [float(v) for v in source[:5]]
    det_offset = float(detector[10]) if len(detector) > 10 and str(detector[10]).strip() != "" else 0.0
    total_offset = offset + det_offset
    dimensions = (dr, dl, dd, well_d, well_h, sr, height, base, wall, total_offset)
    if not all(math.isfinite(v) for v in dimensions) or min(dr, dl, well_d, well_h, sr, height) <= 0:
        raise CoincidenceError("Invalid detector or sample dimensions")
    if min(dd, base, wall, offset) < 0 or well_h+dd >= dl or well_d/2+dd >= dr/2 or sr/2 <= wall:
        raise CoincidenceError("Invalid dead layer, well or container dimensions")
    if sr > well_d:
        raise CoincidenceError("The cylindrical container must fit radially into the well")
    if len(energies) == 0 or np.any(~np.isfinite(energies)) or np.any(energies <= 0):
        raise CoincidenceError("Invalid requested photon energies")
    material_names = [detector[5].strip(), detector[6].strip(), source[5].strip(), source[6].strip()]
    if len(detector) > 11 and str(detector[11]).strip():
        material_names.append(detector[11].strip())
    local = well_local_response(installation, detector,
                                source, np.asarray(energies, dtype=float), order,
                                cancel, _crystal_zz_aa(installation, prepared, detector[5].strip()))
    hashes = {}
    for name in material_names:
        for category in ("Material", "Composition"):
            filename = category+"/"+name+".txt"
            fpath = installation/filename if (installation/filename).is_file() else COMMON_DATA/filename
            hashes[filename] = sha256(fpath.read_bytes()).hexdigest()
    local.metadata["input_sha256"] = {"detector.txt": sha256(detector_raw).hexdigest(),
                                      "source.txt": sha256(source_raw).hexdigest(), **hashes}
    return local


def point_counts(record: Decay, local: LocalEfficiencies, resolving_time: float) -> tuple[np.ndarray, np.ndarray]:
    """Uncorrected and coincident gamma-peak counts at every spatial node.

    Retains the original gamma cascade recursion and time cut. The -0.5,
    511-keV pseudo-transition represents two annihilation photons. Its
    zero/single-detection probabilities are evaluated as a pair rather than
    using the legacy negative first-order expression 1-2*T.
    """
    if not math.isfinite(resolving_time) or resolving_time < 0:
        raise CoincidenceError("Invalid resolving time")
    n, count = len(record.levels), len(local.weights)
    energies = record.transitions[:, :, 0]
    intensity, alpha, ak, al = (record.transitions[:, :, i] for i in range(1, 5))
    branches = intensity*(1+alpha)
    row_sum = branches.sum(axis=1)
    branches = np.divide(branches, row_sum[:, None], out=np.zeros_like(branches), where=row_sum[:, None] > 0)
    lifetimes = record.levels[:, 4].copy()
    lifetimes[row_sum == 0] = 1e30
    prompt = lifetimes < resolving_time
    lookup = {float(e): i for i, e in enumerate(local.energies)}

    def response(energy):
        if energy <= 0:
            return np.zeros(count), np.zeros(count)
        column = lookup[float(energy)]
        return local.peak[:, column], local.total[:, column]

    _, tk = response(record.xray[0])
    _, tl = response(record.xray[2])
    p511, t511 = response(511.)
    pair_miss = local.pair_miss if local.pair_miss is not None else (1-t511)**2
    pair_single = local.pair_single_peak if local.pair_single_peak is not None else 2*p511*(1-t511)
    wk, wl = record.xray[1], record.xray[3]
    a0, a, b = (np.zeros((n, n, count)) for _ in range(3))
    for i in range(n):
        for j in range(i):
            if branches[i, j] == 0:
                continue
            p, t = response(energies[i, j])
            a0[i, j] = branches[i, j]*p/(1+alpha[i, j])
            if alpha[i, j] < 0:
                a[i, j] = branches[i, j]*pair_single
                b[i, j] = branches[i, j]*pair_miss
            else:
                a[i, j] = a0[i, j]
                b[i, j] = branches[i, j]*(1-(t+ak[i, j]*wk*tk+al[i, j]*wl*tl)/(1+alpha[i, j]))
    feeding = record.levels[:, 1]
    pk, pl = record.levels[:, 2], record.levels[:, 3]
    survival = 1-pk[:, None]*wk*tk
    survival -= pl[:, None]*((1-pair_miss) if record.beta_plus_in_pl else wl*tl)
    if min(float(b.min()), float(survival.min())) < -1e-10:
        raise CoincidenceError(f"{record.name}: negative transition/feeding probability; incompatible decay data")
    # Roundoff-sized negatives only. Materially negative values above fail.
    b, survival = np.maximum(b, 0.), np.maximum(survival, 0.)
    zf = feeding.copy()
    for i in range(n-1, -1, -1):
        for j in range(i+1, n):
            zf[i] += zf[j]*branches[j, i]
    z = feeding[:, None]*survival
    for i in range(n-1, -1, -1):
        for j in range(i+1, n):
            z[i] += z[j]*b[j, i]
        if lifetimes[i] > resolving_time:
            z[i] = zf[i]
    m = np.zeros((n, count))
    m[0] = 1.
    for i in range(1, n):
        for j in range(i):
            m[i] += b[i, j]*m[j]
        if lifetimes[i] > resolving_time:
            m[i] = 1.
    w = a.copy()
    for i in range(n):
        for j in range(i):
            for k in range(j+1, i):
                if prompt[k]:
                    w[i, j] += a[i, k]*w[k, j]
    direct, observed = np.zeros((count, 3001)), np.zeros((count, 3001))
    for i in range(n):
        for j in range(i):
            energy_bin = int(energies[i, j]+.5)
            if 1 < energy_bin < 3000:
                direct[:, energy_bin] += zf[i]*a0[i, j]
                observed[:, energy_bin] += z[i]*w[i, j]*m[j]
    return direct, observed


def integrated_counts(records: tuple[Decay, ...], local: LocalEfficiencies,
                       resolving_time: float) -> dict:
    if not np.isfinite(local.weights).all() or np.any(local.weights <= 0) or not np.isclose(local.weights.sum(), 1.):
        raise CoincidenceError("Spatial quadrature weights must be positive and sum to one")
    if not (np.isfinite(local.peak).all() and np.isfinite(local.total).all() and
            np.all(local.peak >= 0) and np.all(local.peak <= local.total+1e-12) and np.all(local.total <= 1)):
        raise CoincidenceError("Local response must obey 0 <= peak <= total <= 1")
    direct, observed = np.zeros(3001), np.zeros(3001)
    for record in records:
        uncorrected, summed = point_counts(record, local, resolving_time)
        # No BLAS thread pools inside the per-nuclide process workers.
        direct += np.einsum("i,ij->j", local.weights, uncorrected, optimize=False)
        observed += np.einsum("i,ij->j", local.weights, summed, optimize=False)
    rows = []
    for energy in np.flatnonzero(direct > 0):
        factor = float(direct[energy]/observed[energy]) if observed[energy] > 0 else None
        if factor is not None and not math.isfinite(factor):
            factor = None
        rows.append({"energy_kev": int(energy), "factor": factor,
                     "direct_counts": float(direct[energy]), "coincident_counts": float(observed[energy]),
                     "status": "candidate" if factor is not None else "zero_predicted_peak"})
    return {"corrections": rows, "decay_sha256": [r.raw_hash for r in records],
            "annihilation_pair_records": [r.name for r in records if np.any(r.transitions[:, :, 2] < 0)],
            "beta_plus_pl_records": [r.name for r in records if r.beta_plus_in_pl]}
