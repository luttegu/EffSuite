! raytrace.f90 - local peak and total efficiency of a well detector, ray by ray.
!
! This is the compiled version of the inner loop of well_local_response() in
! spatial_summing.py (the function _eval_block). Python prepares every input
! (sample points, directions, attenuation coefficients, interpolation grids)
! and writes them to one binary file; this program does the slow part: for
! each sample point and each direction it traces the ray through the detector
! and, for every gamma energy, adds up the probability that the photon is
! detected in the full-energy peak ("peak") or at all ("total").
!
! The formulas are exactly those of the Python code, in the same order, so the
! results agree to rounding level (about 1e-15). Lengths are in mm,
! attenuation coefficients in 1/mm. z = 0 is the bottom of the crystal and r is
! the distance from the detector axis.
!
! Usage:  raytrace  input.bin  output.bin  first_point  number_of_points
!   Several copies can run at the same time on different points.
!
! Output (binary, 8-byte reals): for each point
!   peak(1:ne), total(1:ne), pair_miss, pair_single, largest_raw_total
!
! Build: see tools/build_raytrace.py (gfortran, double precision, no fast-math).

module raytrace_data
  use, intrinsic :: iso_fortran_env, only: int32, real64
  use, intrinsic :: iso_c_binding, only: c_double
  use, intrinsic :: ieee_arithmetic, only: ieee_value, ieee_positive_inf, ieee_negative_inf
  implicit none
  integer, parameter :: dp = real64
  integer, parameter :: FORMAT_VERSION = 1

  ! Sizes
  integer :: n_points, n_dirs, n_energies, n_polar, n_azimuth
  integer :: n_rfrac, n_znode, n_rcav, n_zcav
  logical :: has511, has_holder
  integer :: i511                       ! position of 511 keV in the energy list

  ! Geometry (see the glossary in spatial_summing.well_local_response)
  real(dp) :: dl, r_act_out, z_act_bottom, r_hole, z_hole, well_d, well_h, dr, flange
  real(dp) :: radius, bottom, top, sr, base, holder_thickness

  real(dp), allocatable :: points(:, :)       ! (2, n_points): r, z of each sample point
  real(dp), allocatable :: dirs(:, :)         ! (3, n_dirs): unit vector of each direction
  real(dp), allocatable :: dw(:)              ! (n_dirs): solid-angle weight of each direction
  real(dp), allocatable :: coef(:, :)         ! (n_energies, N_COEF): per-energy coefficients
  real(dp), allocatable :: r_fracs(:), z_nodes(:), eta_grid1(:, :, :)   ! peak-to-total grid
  real(dp), allocatable :: r_cav(:), z_cav(:), piso_e(:, :, :), piso_e1(:, :, :)   ! cavity grid

  ! Columns of "coef", in the order Python writes them.
  integer, parameter :: SM0 = 1, SM1 = 2, SM4 = 3, SM5 = 4     ! sample matrix: Rayleigh, Compton, total+coh, total
  integer, parameter :: BM0 = 5, BM1 = 6, BM4 = 7, BM5 = 8     ! container ("bottle")
  integer, parameter :: AL0 = 9, AL1 = 10, AL4 = 11, AL5 = 12  ! well absorber
  integer, parameter :: SM1_5 = 13, BM1_5 = 14, AL1_5 = 15     ! total, at the energy after one Compton scattering
  integer, parameter :: MU_GE = 16, MU_GE1 = 17                ! germanium total attenuation (E and E')
  integer, parameter :: KN = 18, WCOMP = 19, ETA_MEAN1 = 20
  integer, parameter :: GE_COMPTON = 21, GE_PHOTO = 22, PAIR_TERM = 23, GM_GE = 24
  integer, parameter :: HL_COMPTON = 25, P_GE_ABSORB = 26
  integer, parameter :: N_COEF = 26

  real(dp) :: plus_inf, minus_inf

  interface
    ! expm1(x) = exp(x) - 1, accurate for small x (from the C library, like NumPy).
    pure function expm1(x) bind(c, name="expm1") result(y)
      import :: c_double
      real(c_double), value :: x
      real(c_double) :: y
    end function expm1
  end interface

contains

  subroutine read_input(path)
    character(len=*), intent(in) :: path
    integer :: unit, version, sizes(13)
    real(dp) :: scalars(15)
    open(newunit=unit, file=path, access="stream", form="unformatted", status="old", action="read")
    read(unit) version
    if (version /= FORMAT_VERSION) error stop "raytrace: unsupported input file version"
    read(unit) sizes
    n_points = sizes(1); n_dirs = sizes(2); n_energies = sizes(3); n_polar = sizes(4); n_azimuth = sizes(5)
    n_rfrac = sizes(6); n_znode = sizes(7); n_rcav = sizes(8); n_zcav = sizes(9)
    has511 = sizes(10) == 1; i511 = sizes(11); has_holder = sizes(12) == 1
    if (sizes(13) /= N_COEF) error stop "raytrace: wrong number of coefficient arrays"
    read(unit) scalars
    dl = scalars(1); r_act_out = scalars(2); z_act_bottom = scalars(3); r_hole = scalars(4)
    z_hole = scalars(5); well_d = scalars(6); well_h = scalars(7); dr = scalars(8); flange = scalars(9)
    radius = scalars(10); bottom = scalars(11); top = scalars(12); sr = scalars(13); base = scalars(14)
    holder_thickness = scalars(15)
    allocate(points(2, n_points), dirs(3, n_dirs), dw(n_dirs), coef(n_energies, N_COEF))
    allocate(r_fracs(n_rfrac), z_nodes(n_znode), eta_grid1(n_energies, n_znode, n_rfrac))
    allocate(r_cav(n_rcav), z_cav(n_zcav), piso_e(n_energies, n_zcav, n_rcav), piso_e1(n_energies, n_zcav, n_rcav))
    read(unit) points, dirs, dw, coef, r_fracs, z_nodes, eta_grid1, r_cav, z_cav, piso_e, piso_e1
    close(unit)
    plus_inf = ieee_value(1.0_dp, ieee_positive_inf)
    minus_inf = ieee_value(1.0_dp, ieee_negative_inf)
  end subroutine read_input

  ! Entry and exit distances of a ray starting at (r, 0, z) with direction u
  ! through a finite cylinder (radius, bottom, top). Same as _ray_interval.
  subroutine ray_interval(cyl_radius, cyl_bottom, cyl_top, r, z, u, t_in, t_out)
    real(dp), intent(in) :: cyl_radius, cyl_bottom, cyl_top, r, z, u(3)
    real(dp), intent(out) :: t_in, t_out
    real(dp) :: transverse, b, disc, roots, radial_lo, radial_hi, axial_lo, axial_hi, first, second
    transverse = u(1)*u(1) + u(2)*u(2)
    radial_lo = minus_inf
    radial_hi = plus_inf
    if (r > cyl_radius .and. transverse == 0) radial_hi = minus_inf
    if (transverse > 0) then
      b = 2*r*u(1)
      disc = b*b - 4*transverse*(r*r - cyl_radius*cyl_radius)
      roots = sqrt(max(disc, 0.0_dp))
      radial_lo = (-b - roots)/(2*transverse)
      radial_hi = (-b + roots)/(2*transverse)
      if (disc <= 0) radial_hi = minus_inf
    end if
    axial_lo = minus_inf
    axial_hi = plus_inf
    if (.not. (cyl_bottom <= z .and. z <= cyl_top) .and. u(3) == 0) axial_hi = minus_inf
    if (u(3) /= 0) then
      first = (cyl_bottom - z)/u(3)
      second = (cyl_top - z)/u(3)
      axial_lo = min(first, second)
      axial_hi = max(first, second)
    end if
    t_in = max(0.0_dp, max(radial_lo, axial_lo))
    t_out = max(t_in, min(radial_hi, axial_hi))
  end subroutine ray_interval

  ! Length of the ray inside a finite cylinder. Same as ray_lengths.
  real(dp) function ray_length(cyl_radius, cyl_bottom, cyl_top, r, z, u)
    real(dp), intent(in) :: cyl_radius, cyl_bottom, cyl_top, r, z, u(3)
    real(dp) :: t_in, t_out
    call ray_interval(cyl_radius, cyl_bottom, cyl_top, r, z, u, t_in, t_out)
    ray_length = t_out - t_in
  end function ray_length

  ! Bilinear interpolation in a grid(energy, z, r) at (rq, zq) for energy ie,
  ! clamped to the grid edges. Same as interp() in the Python code.
  real(dp) function interp(grid, ie, rq_in, zq_in, r_ax, z_ax)
    real(dp), intent(in) :: grid(:, :, :), rq_in, zq_in, r_ax(:), z_ax(:)
    integer, intent(in) :: ie
    real(dp) :: rq, zq, a, b
    integer :: i, j
    rq = min(max(rq_in, r_ax(1)), r_ax(size(r_ax)))
    zq = min(max(zq_in, z_ax(1)), z_ax(size(z_ax)))
    i = min(max(count(r_ax <= rq), 1), size(r_ax) - 1)    ! cell i..i+1 containing rq
    j = min(max(count(z_ax <= zq), 1), size(z_ax) - 1)
    a = (rq - r_ax(i))/max(r_ax(i+1) - r_ax(i), 1e-9_dp)
    b = (zq - z_ax(j))/max(z_ax(j+1) - z_ax(j), 1e-9_dp)
    interp = (1-a)*((1-b)*grid(ie, j, i) + b*grid(ie, j+1, i)) + a*((1-b)*grid(ie, j, i+1) + b*grid(ie, j+1, i+1))
  end function interp

  ! Path lengths of one ray through every part of the detector and source.
  ! Same as trace() in the Python code.
  subroutine trace(r, z, u, crystal, t_entry, bore, sample, container, up_start, up_end, dead_ge, holder)
    real(dp), intent(in) :: r, z, u(3)
    real(dp), intent(out) :: crystal, t_entry, bore, sample, container, up_start, up_end, dead_ge, holder
    real(dp) :: t0a, t1a, t0h, t1h, overlap, s0, s1, c0, c1, b0, b1, t0p, t1p, overlap_p, phys_ge
    logical :: via_hole
    ! Active germanium, minus the part that is the well hole.
    call ray_interval(r_act_out, z_act_bottom, dl, r, z, u, t0a, t1a)
    call ray_interval(r_hole, z_hole, dl + 10., r, z, u, t0h, t1h)
    overlap = max(0.0_dp, min(t1a, t1h) - max(t0a, t0h))
    crystal = max(0.0_dp, (t1a - t0a) - overlap)
    via_hole = (t1h > t0a) .and. (overlap > 0)
    if (via_hole) then
      t_entry = min(t1a, t1h)
    else
      t_entry = t0a
    end if
    ! Well absorber (bore liner) and top-face housing.
    bore = max(0.0_dp, ray_length(r_hole, z_hole, dl, r, z, u) - ray_length(well_d/2, dl - well_h, dl, r, z, u))
    if (flange > 0) then
      bore = bore + max(0.0_dp, ray_length(dr/2, dl, dl + flange, r, z, u) - ray_length(well_d/2, dl, dl + flange, r, z, u))
    end if
    ! Sample and container.
    call ray_interval(radius, bottom, top, r, z, u, s0, s1)
    call ray_interval(sr/2, bottom - base, top + base, r, z, u, c0, c1)
    sample = s1 - s0
    container = max(0.0_dp, (c1 - c0) - (s1 - s0))
    ! Part of the path before the crystal ("upstream"), where scattering can happen.
    call ray_interval(r_hole, z_hole, dl + flange, r, z, u, b0, b1)
    if (crystal > 0) then
      up_end = t_entry
    else
      up_end = max(c1, b1)
    end if
    if (sample + container > 0) then
      up_start = min(min(c0, b0), up_end)
    else
      up_start = min(b0, up_end)
    end if
    ! Dead germanium (physical crystal minus active crystal).
    call ray_interval(dr/2, 0.0_dp, dl, r, z, u, t0p, t1p)
    overlap_p = max(0.0_dp, min(t1p, t1h) - max(t0p, t0h))
    phys_ge = max(0.0_dp, (t1p - t0p) - overlap_p)
    dead_ge = max(0.0_dp, phys_ge - crystal)
    ! Mount cup (holder) around the crystal.
    if (holder_thickness > 0) then
      holder = max(0.0_dp, ray_length(dr/2 + holder_thickness, -holder_thickness, dl, r, z, u) &
                           - ray_length(dr/2, 0.0_dp, dl, r, z, u))
    else
      holder = 0
    end if
  end subroutine trace

  ! Peak and total efficiency of one sample point (sum over all directions),
  ! and the 511-keV pair probabilities. Same as _eval_block + _eval_point.
  subroutine evaluate_point(r, z, peak, total, pair_miss, pair_single, raw_max)
    real(dp), intent(in) :: r, z
    real(dp), intent(out) :: peak(n_energies), total(n_energies), pair_miss, pair_single, raw_max
    real(dp) :: crystal, t_entry, bore, sa, co, up0, up1, dead_ge, holder
    real(dp) :: tau_i, p_dir, x, depth, remain, t_mid, z_int, r_int, r_in, frac, eta_iso, eta_fwd, eta1
    real(dp) :: w_loc, pv, pk, tau, rayl, comp, safe, fs, span, t_sc, z_sc, r_sc
    real(dp) :: det_rayl, rest, det_comp, tot, mu, mu1, knc
    real(dp), allocatable :: t_p(:), p_p(:)
    integer :: k, ie, ip, ia, opposite
    logical :: hit
    allocate(t_p(n_dirs), p_p(n_dirs))
    peak = 0
    total = 0
    raw_max = 0
    t_p = 0
    p_p = 0
    do k = 1, n_dirs
      call trace(r, z, dirs(:, k), crystal, t_entry, bore, sa, co, up0, up1, dead_ge, holder)
      hit = crystal > 1e-9_dp
      do ie = 1, n_energies
        mu = coef(ie, MU_GE)
        mu1 = coef(ie, MU_GE1)
        knc = coef(ie, KN)
        ! --- peak: photon reaches the crystal unscattered and is fully absorbed there
        tau_i = sa*coef(ie, SM5) + co*coef(ie, BM5) + bore*coef(ie, AL5)
        p_dir = -expm1(-crystal*mu)
        x = max(crystal*mu, 1e-8_dp)
        if (x > 50.) then                   ! mean interaction depth in the crystal
          depth = 1/mu
        else if (x < 1e-3_dp) then
          depth = .5*crystal
        else
          depth = 1/mu - crystal/expm1(min(x, 50.0_dp))
        end if
        remain = max(0.0_dp, crystal - depth)
        t_mid = t_entry + depth
        z_int = min(max(z + dirs(3, k)*t_mid, z_act_bottom), dl)
        r_int = hypot(r + dirs(1, k)*t_mid, dirs(2, k)*t_mid)
        if (z_int >= z_hole) then
          r_in = r_hole
        else
          r_in = 0
        end if
        frac = (r_int - r_in)/max(r_act_out - r_in, 1.0_dp)
        eta_iso = interp(eta_grid1, ie, frac, z_int, r_fracs, z_nodes)
        eta_fwd = -expm1(-remain*mu1)
        eta1 = knc*eta_fwd + (1 - knc)*eta_iso
        w_loc = min(max(coef(ie, WCOMP)*min(max(eta1/coef(ie, ETA_MEAN1), 0.0_dp), 1.35_dp), 0.0_dp), 1.0_dp)
        pv = min(max((coef(ie, GE_PHOTO) + coef(ie, GE_COMPTON)*w_loc + coef(ie, PAIR_TERM))/coef(ie, GM_GE), 0.0_dp), 1.0_dp)
        if (hit) then
          pk = exp(-tau_i)*p_dir*pv
        else
          pk = exp(-tau_i)*p_dir*0.0_dp
        end if
        ! --- total: the photon is detected at all (mutually exclusive fates)
        tau = sa*coef(ie, SM4) + co*coef(ie, BM4) + bore*coef(ie, AL4)
        rayl = sa*coef(ie, SM0) + co*coef(ie, BM0) + bore*coef(ie, AL0)
        comp = sa*coef(ie, SM1) + co*coef(ie, BM1) + bore*coef(ie, AL1)
        safe = max(tau, 1e-15_dp)
        if (tau > 50.) then                  ! mean fraction of the path before the first interaction
          fs = 1/max(tau, 1e-15_dp)
        else if (tau < 1e-3_dp) then
          fs = .5
        else
          fs = 1/max(tau, 1e-15_dp) - 1/expm1(min(tau, 50.0_dp))
        end if
        span = max(0.0_dp, up1 - up0)
        t_sc = up0 + span*fs
        z_sc = z + dirs(3, k)*t_sc
        r_sc = hypot(r + dirs(1, k)*t_sc, dirs(2, k)*t_sc)
        det_rayl = .65_dp*p_dir*exp(-(1 - fs)*tau_i) + .35_dp*interp(piso_e, ie, r_sc, z_sc, r_cav, z_cav)
        rest = (1 - fs)*(sa*coef(ie, SM1_5) + co*coef(ie, BM1_5) + bore*coef(ie, AL1_5))
        det_comp = knc**2*(-expm1(-crystal*mu1))*exp(-rest) + (1 - knc**2)*interp(piso_e1, ie, r_sc, z_sc, r_cav, z_cav)
        tot = exp(-tau)*p_dir - expm1(-tau)*(rayl/safe*det_rayl + comp/safe*det_comp)
        if (has_holder) then                 ! Compton backscatter from the mount cup
          tot = tot + exp(-tau)*exp(-crystal*mu)*exp(-dead_ge*mu)*(-expm1(-holder*coef(ie, HL_COMPTON))) &
                      *0.40_dp*coef(ie, P_GE_ABSORB)
        end if
        raw_max = max(raw_max, tot)
        tot = min(max(max(tot, pk), 0.0_dp), 1.0_dp)
        peak(ie) = peak(ie) + pk*dw(k)
        total(ie) = total(ie) + tot*dw(k)
        if (has511 .and. ie == i511) then
          t_p(k) = tot
          p_p(k) = pk
        end if
      end do
    end do
    ! 511-keV pairs: direction k = (polar ip, azimuth ia) has its opposite at
    ! (n_polar+1-ip, ia + n_azimuth/2), because the polar nodes are symmetric.
    pair_miss = 0
    pair_single = 0
    if (has511) then
      do k = 1, n_dirs
        ip = (k - 1)/n_azimuth + 1
        ia = mod(k - 1, n_azimuth)
        opposite = (n_polar - ip)*n_azimuth + mod(ia + n_azimuth/2, n_azimuth) + 1
        pair_miss = pair_miss + dw(k)*(1 - t_p(k))*(1 - t_p(opposite))
        pair_single = pair_single + dw(k)*(p_p(k)*(1 - t_p(opposite)) + p_p(opposite)*(1 - t_p(k)))
      end do
    end if
  end subroutine evaluate_point

end module raytrace_data


program raytrace
  use raytrace_data
  implicit none
  character(len=4096) :: input_path, output_path, text
  integer :: first, count_points, p, unit
  real(dp), allocatable :: peak(:), total(:)
  real(dp) :: pair_miss, pair_single, raw_max
  if (command_argument_count() /= 4) error stop "usage: raytrace input.bin output.bin first_point number_of_points"
  call get_command_argument(1, input_path)
  call get_command_argument(2, output_path)
  call get_command_argument(3, text)
  read(text, *) first
  call get_command_argument(4, text)
  read(text, *) count_points
  call read_input(trim(input_path))
  if (first < 1 .or. count_points < 0 .or. first + count_points - 1 > n_points) error stop "raytrace: bad point range"
  allocate(peak(n_energies), total(n_energies))
  open(newunit=unit, file=trim(output_path), access="stream", form="unformatted", status="replace", action="write")
  do p = first, first + count_points - 1
    call evaluate_point(points(1, p), points(2, p), peak, total, pair_miss, pair_single, raw_max)
    write(unit) peak, total, pair_miss, pair_single, raw_max
  end do
  close(unit)
end program raytrace
