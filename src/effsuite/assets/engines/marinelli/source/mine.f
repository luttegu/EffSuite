
      program mine
      
      implicit none

      real e(1000)

      common /material/ gee(1000),gemu(1000),
     +                  ce(1000),cmu(1000),
     +                  we(1000),wmu(1000),
     +                  he(1000),hmu(1000),
     +                  se(1000),smu(1000),
     +                  pe(1000),pmu(1000),
     +                  ne,nge,nc,nw,nh,ns,np

      real gee,gemu
      real ce,cmu
      real we,wmu
      real he,hmu
      real se,smu
      real pe,pmu

      integer ne,nge,nc,nw,nh,ns,np

      common/detector/ cr,ct,dl,dr,ddt,dds,wt,bul,
     +                  wd,crl,crr,hol,dist,bt,tt,ar,at
      common /sample/ t,pt

      real cr,ct,dl,dr,ddt,dds,wt,bul
      real wd,crl,crr,hol,dist,bt,tt
      real ar,at

      real sr,st,sx,sh,pt,t
      real e1,e2,emin,acc

      character*70 dmat,wmat,cmat,hmat,smat,bmat,airmat,amat

      real rtbis
      external rtbis

      open(7,file='detector.txt',status='old')
      read(7,*) cr
      read(7,*) ct
      read(7,*) dr
      read(7,*) dl
      read(7,*) ddt
      read(7,*) dds
      read(7,*) wt
      read(7,*) wd
      read(7,*) crr
      read(7,*) crl
      read(7,*) hol
      read(7,*) bul
      read(7,77) dmat
      read(7,77) wmat
      read(7,77) cmat
      read(7,77) hmat
      close(7)
77    format(a)

      cr=cr/2.
      dr=dr/2.
      crr=crr/2.
      ar=ar/2.

      open(7,file='source.txt',status='old')
      read(7,*) sr
      read(7,*) sx
      read(7,*) st
      read(7,*) sh
      read(7,*) pt
      read(7,77) smat
      read(7,77) bmat
      close(7)

      sr=sr/2.
      sx=sx/2.
      t=sr-sx

      call readin(dmat,nge,gee,gemu)
      call readin(cmat,nc,ce,cmu)
      call readin(wmat,nw,we,wmu)
      call readin(hmat,nh,he,hmu)
      call readin(smat,ns,se,smu)
      call readin(bmat,np,pe,pmu)

      e1=0.1
      e2=3000.
      acc=1.0E-05

      emin=rtbis(e1,e2,acc)
c      if (emin.lt.10.) emin=10.

      open(7,file='mine.txt',status='unknown')
      write(7,'(f12.1)') emin
      close(7)

      end


      function func(e)

      implicit none

      real func
      real e

      common /material/ gee(1000),gemu(1000),
     +                  ce(1000),cmu(1000),
     +                  we(1000),wmu(1000),
     +                  he(1000),hmu(1000),
     +                  se(1000),smu(1000),
     +                  pe(1000),pmu(1000),
     +                  ne,nge,nc,nw,nh,ns,np

      real gee,gemu
      real ce,cmu
      real we,wmu
      real he,hmu
      real se,smu
      real pe,pmu

      integer ne,nge,nc,nw,nh,ns,np

      common/detector/ cr,ct,dl,dr,ddt,dds,wt,bul,
     +                 wd,crl,crr,hol,dist,bt,tt,ar,at

      common /sample/ t,pt

      real cr,ct,dl,dr,ddt,dds,wt,bul
      real wd,crl,crr,hol,dist,bt,tt
      real ar,at

      real t,pt

      real x1,x2,x
      real muge,muw,mus,muc,mup,muh

      call inter(nge,gee,gemu,e,muge)
      call inter(nw,we,wmu,e,muw)
      call inter(nc,ce,cmu,e,muc)
      call inter(nh,he,hmu,e,muh)
      call inter(ns,se,smu,e,mus)
      call inter(np,pe,pmu,e,mup)

      x1=exp(-muge*dds)
      x1=x1*exp(-muc*ct)
      x1=x1*exp(-muh*hol)
      x1=x1*exp(-mup*pt)

      x2=exp(-muge*ddt)
      x2=x2*exp(-muw*wt)
      x2=x2*exp(-mup*pt)

      x=(x1+x2)/2.
      x=x*(1.-exp(-mus*t))/(mus*t)

      func=x-0.05

      return
      end

      subroutine readin(fname,n,e,mu)

      implicit none

      character*(70) fname
      character*(132) line

      integer n
      integer left,right
      integer l,r
      integer kode

      real e(1000),mu(1000)
      real ene,rayl,comp,phot,pair,pair1,tot,tot1
      real den

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


      integer function left(s)
      implicit none
      integer n,l
      character blank
      character*(*) s
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
      character*(*) s
      blank=' '
      n=len(s)
      do while (s(n:n).eq.blank.and.n.gt.1)
        n=n-1
      enddo
      right=n
      return
      end


      subroutine inter(n,e,mu,z,xmu)
      implicit none
      integer n,j
      real e(1000),mu(1000),z,xe,xmu
      xe=log(z)
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


      FUNCTION rtbis(x1,x2,xacc)
      INTEGER JMAX
      real x1,x2
      REAL xacc
      PARAMETER (JMAX=40)
      INTEGER j
      REAL dx,f,fmid,xmid
      fmid=func(x2)
      f=func(x1)
      if(f*fmid.ge.0.) pause 'root must be bracketed in rtbis'
      if(f.lt.0.)then
        rtbis=x1
        dx=x2-x1
      else
        rtbis=x2
        dx=x1-x2
      endif
      do 11 j=1,JMAX
        dx=dx*.5
        xmid=rtbis+dx
        fmid=func(xmid)
        if(fmid.le.0.)rtbis=xmid
        if(abs(dx).lt.xacc .or. fmid.eq.0.) return
11    continue
      pause 'too many bisections in rtbis'
      END
C  (C) Copr. 1986-92 Numerical Recipes Software ,)+>.
