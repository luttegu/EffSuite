
CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
C                                                                       C
C  EFFTRAN (version 4.4.4 2016)                                         C
C  Copyright (c) 1995-2016                                             C
C  Tim Vidmar                                                           C
C                                                                       C
C  Permission to use, copy, modify, distribute and sell this software   C
C  and its documentation for any purpose is hereby granted without      C
C  fee, provided that the above copyright notice appears in all         C
C  copies and that both that copyright notice and this permission       C
C  notice appear in all supporting documentation. Tim Vidmar makes      C
C  no representations about the suitability of this software for any    C
C  purpose. It is provided 'as is' without express or implied warranty. C
C                                                                       C
CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC

      program scatter

      implicit none

      double precision costh,sinth,fi
      double precision tx,ty,tz
      double precision x0,z0
      double precision x(4)
      double precision e(1000)

      double precision se(1000),smu(1000),smuc(1000)
      double precision mus,musc
      integer ne,ns

      double precision rs,zls,zus,ds,rs2
      double precision sr,st,sden
      double precision cb,cs
      double precision dist,u,pi
      double precision t(1000),sig(1000),rat,ratmax,unc

      character*60 smat

      integer i,j,n

      ne=1
      open(7,file='total.txt',status='old')
11    continue
      read(7,*,end=22) e(ne)
      e(ne)=log(e(ne))
      ne=ne+1
      goto 11
22    continue
      close(7)
      ne=ne-1
      close(7)

      open(7,file='source.txt',status='old')
      read(7,*) sr
      read(7,*) st
      read(7,*) cb
      read(7,*) cs
      read(7,*) 
      read(7,55) smat
      close(7)
55    format(a)

      sr=sr/2.
      st=st+cb+cb

      unc=0.01

      call readin(smat,ns,se,smu,smuc)

      zls=0.
      zus=zls+st
      rs=sr
      rs2=rs*rs

      pi=3.141592653

      do i=1,ne
        t(i)=0.
        sig(i)=0.
      enddo

      call sobseq(-4,x)

      n=0
    
100   continue

      n=n+1

      call sobseq(4,x)
      x0=x(1)
      x0=rs*sqrt(x0)

      dist=x(2)
      dist=dist*st
      z0=zls+dist

      fi=x(3)
      fi=2.*pi*fi
      costh=x(4)
      costh=1.-2.*costh
      sinth=sqrt(1.-costh*costh)
      tx=sinth*cos(fi)
      ty=sinth*sin(fi)
      tz=costh
      if (tz.eq.0.) tz=1.e-15

      call path(zls,zus,rs2,x0,z0,tx,ty,tz,ds)
      ds=abs(ds)

      ratmax=0.      
      do j=1,ne
        call inter(ns,se,smuc,e(j),musc)
        call inter(ns,se,smu,e(j),mus)
        u=1.-exp(-musc*ds)
        t(j)=(n-1)*t(j)+u
        t(j)=t(j)/n
        sig(j)=(n-1)*sig(j)+u*u
        sig(j)=sig(j)/n
        rat=0.
        if (t(j).gt.0.) rat=sqrt((sig(j)-t(j)*t(j))/n)/t(j)
        if (rat.gt.ratmax) ratmax=rat
      enddo
      
      if (ratmax.gt.unc.or.n.lt.1000) goto 100

      open(7,file='scatter.txt',status='unknown')
      do i=1,ne
        write(7,77) exp(e(i)),t(i)
      enddo
      close(7)
77    format(2e15.5)

      end

      subroutine readin(fname,n,e,mu,muc)

      implicit none

      character*(70) fname
      character*(132) line

      integer n
      integer left,right
      integer l,r
      integer kode

      double precision e(1000),mu(1000),muc(1000)
      double precision ene,rayl,comp,phot,pair,pair1,tot,tot1
      double precision den

      l=left(fname)
      r=right(fname)

      open(7,file='.\\Composition\\'//fname(l:r)//'.txt',status='old')
      read(7,*) den
      close(7)

      n=1

      open(7,file='.\\Material\\'//fname(l:r)//'.txt',status='old')

1     continue

      read(7,'(a)',end=2) line

      line=line(8:len(line))

      read(line,*,err=1,iostat=kode) 
     +ene,rayl,comp,phot,pair,pair1,tot,tot1

      if (kode.eq.0) then

        ene=ene*1.e3
        rayl=rayl*den
        comp=comp*den
        phot=phot*den
        pair=pair*den
        tot=tot*den
        tot1=tot1*den

        if (rayl.le.0)  rayl=1.e-15
        if (comp.le.0)  comp=1.e-15
        if (phot.le.0)  phot=1.e-15
        if (pair.le.0)  pair=1.e-15
        if (pair1.le.0) pair1=1.e-15
        if (tot.le.0)   tot=1.e-15
        if (tot1.le.0)  tot1=1.e-15

        e(n)=ene

        mu(n)=tot1
        mu(n)=mu(n)/10.
        muc(n)=comp
        muc(n)=muc(n)/10.

        e(n)=log(e(n))
        mu(n)=log(mu(n))
        muc(n)=log(muc(n))

        n=n+1
      
      endif
   
      goto 1

2     continue

      close(7)
      n=n-1

      return
      end

      subroutine inter(n,e,mu,xe,xmu)
      implicit none
      integer n,j
      double precision e(1000),mu(1000),xe,xmu
      j=1.
      do while(e(j).lt.xe.and.j.lt.n)
         j=j+1
      enddo
      j=j-1
      if (j.eq.0) j=1
      xmu=(mu(j+1)-mu(j))/(e(j+1)-e(j))*(xe-e(j))+mu(j)
      xmu=exp(xmu)
      return
      end
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
      SUBROUTINE sobseq(n,x)
      INTEGER n,MAXBIT,MAXDIM
      double precision x(4)
      PARAMETER (MAXBIT=30,MAXDIM=6)
      INTEGER i,im,in,ipp,j,k,l,ip(MAXDIM),iu(MAXDIM,MAXBIT),iv(MAXBIT*
     *MAXDIM),ix(MAXDIM),mdeg(MAXDIM)
      double precision fac
      SAVE ip,mdeg,ix,iv,in,fac
      EQUIVALENCE (iv,iu)
      DATA ip /0,1,1,2,1,4/, mdeg /1,2,3,3,4,4/, ix /6*0/
      DATA iv /6*1,3,1,3,3,1,1,5,7,7,3,3,5,15,11,5,15,13,9,156*0/
      if (n.lt.0) then
        do 11 k=1,MAXDIM
          ix(k)=0
11      continue
        in=0
        if(iv(1).ne.1)return
        fac=1./2.**MAXBIT
        do 15 k=1,MAXDIM
          do 12 j=1,mdeg(k)
            iu(k,j)=iu(k,j)*2**(MAXBIT-j)
12        continue
          do 14 j=mdeg(k)+1,MAXBIT
            ipp=ip(k)
            i=iu(k,j-mdeg(k))
            i=ieor(i,i/2**mdeg(k))
            do 13 l=mdeg(k)-1,1,-1
              if(iand(ipp,1).ne.0)i=ieor(i,iu(k,j-l))
              ipp=ipp/2
13          continue
            iu(k,j)=i
14        continue
15      continue
      else
        im=in
        do 16 j=1,MAXBIT
          if(iand(im,1).eq.0)goto 1
          im=im/2
16      continue
1       im=(j-1)*MAXDIM
        do 17 k=1,min(n,MAXDIM)
          ix(k)=ieor(ix(k),iv(im+k))
          x(k)=ix(k)*fac
17      continue
        in=in+1
      endif
      return
      END
C  (C) Copr. 1986-92 Numerical Recipes Software ,)+>.

      integer function left(s)
      implicit none
      integer n,l
      character blank
      character*(30) s
      blank=' '
      l=len(s)
      n=1
      do while (s(n:n).eq.blank.and.n.lt.l)
        n=n+1
      enddo
      left=n
      return
      end

      integer function right(s)
      implicit none
      integer n
      character blank
      character*(30) s
      blank=' '
      n=len(s)
      do while (s(n:n).eq.blank.and.n.gt.1)
        n=n-1
      enddo
      right=n
      return
      end
