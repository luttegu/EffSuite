
CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
C                                                                       C
C  EFFTRAN (version 4.4.4 2016)                                         C
C  Copyright (c) 1995-2016                                              C
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

      program eta

      implicit none

      double precision costh,sinth,fi
      double precision tx,ty,tz
      double precision x0,z0
      double precision x(4)
      double precision e(1000)

      double precision emin,emax,de,ene

      double precision se(1000),smu(1000)
      double precision mus
      integer ne,ns

      double precision rs,zls,zus,ds,rs2
      double precision sr,st,sden,crr,crl,dd,dv,vv,ddt,dds,bul
      double precision dist,u,pi
      double precision t(1000),sig(1000),rat,ratmax,unc

      character*60 smat

      integer i,j,n

      emin=10.
      emax=3000.

      ne=40

      de=log(emax)-log(emin)
      de=de/ne

      ne=ne+1

      ene=log(emin)
      e(1)=ene

      do n=2,ne
        ene=ene+de
        e(n)=ene
      enddo

      open(7,file='detector.txt',status='old')
      read(7,*) sr
      read(7,*) st
      read(7,*) dd
      read(7,*) crr
      read(7,*) crl
      read(7,55) smat
      close(7)
55    format(a)

      sr=sr/2.
      crr=crr/2.

      crr=crr+dd
      crl=crl+dd

      vv=sr*sr*st
      dv=crr*crr*crl
      dv=(vv-dv)/vv

      unc=0.01

      call readin(smat,ns,se,smu,dv)

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
      
      ratmax=0.      
      do j=1,ne
        call inter(ns,se,smu,e(j),mus)
        u=1.-exp(-mus*ds)
        t(j)=(n-1)*t(j)+u
        t(j)=t(j)/n
        sig(j)=(n-1)*sig(j)+u*u
        sig(j)=sig(j)/n
        rat=0.
        if (t(j).gt.0.) rat=sqrt((sig(j)-t(j)*t(j))/n)/t(j)
        if (rat.gt.ratmax) ratmax=rat
      enddo
      
      if (ratmax.gt.unc.or.n.lt.1000) goto 100

      open(7,file='eta.txt',status='unknown')
      do i=1,ne
        write(7,77) exp(e(i)),t(i)
      enddo
      close(7)
77    format(2e15.5)

      end

      subroutine readin(fname,n,e,mu,dlt)

      implicit none

      character*(70) fname
      character*(132) line

      integer n
      integer left,right
      integer l,r
      integer kode

      double precision e(1000),mu(1000)
      double precision ene,rayl,comp,phot,pair,pair1,tot,tot1
      double precision den,dlt

      l=left(fname)
      r=right(fname)

      open(7,file='.\\Composition\\'//fname(l:r)//'.txt',status='old')
      read(7,*) den
      close(7)
      den=den*dlt

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

        mu(n)=phot+comp+pair
        mu(n)=mu(n)/10.

        e(n)=log(e(n))
        mu(n)=log(mu(n))

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

      subroutine path(zlo,zup,r2,x0,z0,tx,ty,tz,d)
      implicit none
      double precision zlo,zup,r2,x0,z0,tx,ty,tz
      double precision k1,k2,k
      double precision za,zb
      double precision a,b,c,det,q,sgn
      double precision d
      d=0.
      a=tx*tx+ty*ty
      b=2.*x0*tx
      c=x0*x0-r2
      det=b*b-4.*a*c
      if (det.lt.0..or.a.le.0.) return
      if (b.ge.0.) then
         sgn=1.
      else
         sgn=-1.
      endif
      q=-(b+sgn*sqrt(det))/2.
      k1=q/a
      k2=c/q
      k=k1
      if (k2.gt.k) k=k2
      zb=z0+k*tz
      if (zb.le.zlo) zb=zlo
      if (zb.gt.zup) zb=zup
      za=z0
      d=(za-zb)/tz
      d=abs(d)
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
