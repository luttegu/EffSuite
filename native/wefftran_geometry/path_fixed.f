C  Finite-cylinder forward-ray intersection for WEFFTRAN.
C  Local modification 2026-10-30. Original caller assumes unit direction.
C  Preserve legacy arithmetic for strict interior starting points.
      subroutine path(zlo,zup,r2,x0,z0,tx,ty,tz,d)
      implicit none
      double precision zlo,zup,r2,x0,z0,tx,ty,tz,d
      double precision a,b,c,det,q,sgn,k1,k2,k,za,zb
      double precision rlo,rhi,zmin,zmax,tin,tout,inf
      d=0.d0
      if (r2.le.0.d0.or.zup.le.zlo) return
      a=tx*tx+ty*ty
      b=2.d0*x0*tx
      c=x0*x0-r2
C  This branch retains the original operation sequence on valid
C  interior rays. Corrected external and degenerate rays follow below.
      if (c.lt.0.d0.and.z0.ge.zlo.and.z0.le.zup.and.
     +    a.gt.0.d0.and.tz.ne.0.d0) then
        det=b*b-4.d0*a*c
        if (det.lt.0.d0) return
        if (b.ge.0.d0) then
          sgn=1.d0
        else
          sgn=-1.d0
        endif
        q=-(b+sgn*sqrt(det))/2.d0
        k1=q/a
        k2=c/q
        k=k1
        if (k2.gt.k) k=k2
        zb=z0+k*tz
        if (zb.le.zlo) zb=zlo
        if (zb.gt.zup) zb=zup
        za=z0
        d=abs((za-zb)/tz)
        return
      endif
C  Intersect the radial interval, axial slab and forward half-ray.
C  Outside air is excluded even when the emitter is above the crystal.
      inf=huge(1.d0)
      rlo=-inf
      rhi=inf
      if (a.eq.0.d0) then
        if (c.gt.0.d0) return
        if (tz.eq.0.d0) return
      else
        det=b*b-4.d0*a*c
        if (det.le.0.d0) return
        if (b.ge.0.d0) then
          sgn=1.d0
        else
          sgn=-1.d0
        endif
        q=-(b+sgn*sqrt(det))/2.d0
        k1=q/a
        k2=c/q
        rlo=min(k1,k2)
        rhi=max(k1,k2)
      endif
      zmin=-inf
      zmax=inf
      if (tz.eq.0.d0) then
        if (z0.lt.zlo.or.z0.gt.zup) return
      else
        k1=(zlo-z0)/tz
        k2=(zup-z0)/tz
        zmin=min(k1,k2)
        zmax=max(k1,k2)
      endif
      tin=max(0.d0,rlo,zmin)
      tout=min(rhi,zmax)
      if (tout.gt.tin) d=tout-tin
      return
      end
