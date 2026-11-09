
      program total

      implicit none

      real costh,sinth,fi
      real tx,ty,tz
      real x0,z0
      real x(6)
      real e(1000)

      real gee(1000),gemu(1000),muge(1000)
      real ce(1000),cmu(1000),muc(1000)
      real we(1000),wmu(1000),muw(1000)
      real he(1000),hmu(1000),muh(1000)
      real ae(1000),amu(1000),mua(1000)
      real se(1000),smu(1000),mus(1000)
      real ze(1000),zmu(1000),muz(1000)
      real pe(1000),pmu(1000),mup(1000)
      integer ne,nge,nc,nw,nh,na,ns,nz,np

      real rc,zlc,zuc,dc,rc2
      real rd,zld,zud,dd,rd2
      real rw,zlw,zuw,dw,rw2
      real ra,zla,zua,da,ra2
      real rcr,zlcr,zucr,dcr,rcr2
      real rddt,zlddt,zuddt,dddt,rddt2
      real rdds,zldds,zudds,ddds,rdds2
      real rv,zlv,zuv,dv,rv2
      real rh,zlh,zuh,dh,rh2
      real rhv,zlhv,zuhv,dhv,rhv2
      real rs,zls,zus,ds,rs2
      real rp,zlp,zup,dp,rp2
      real rb1,zlb1,zub1,db1,rb12
      real rb2,zlb2,zub2,db2,rb22
      real rb3,zlb3,zub3,db3,rb32
      real rt1,zlt1,zut1,dt1,rt12
      real rt2,zlt2,zut2,dt2,rt22
      real rt3,zlt3,zut3,dt3,rt32
      real rbul(10),rbul2(10)
      real zlbul(10),zubul(10)

      real cr,ct,dl,dr,ddt,dds,wt,bul
      real wd,crl,crr,hol,dist,bt,tt
      real ar,at
      real sr,st,pbt,pst,sdist

      real u1(1000),u2(1000)
      real t(1000),t2(1000),sig(1000),s(1000)
      real smax,unc

      real pi,u
      real sbul,dbul,dbul1
      real dead

      real ee,emin,emax,de

      character*70 dmat,wmat,cmat,hmat,smat,bmat,airmat,amat

      integer nbul
      integer i,j,n,l,r

      external left,right
      integer left,right

      pi=3.1415926

      ne=1
      open(7,file='reference.txt',status='old')
11    continue
      read(7,*,end=22) e(ne)
      e(ne)=log(e(ne))
      ne=ne+1
      goto 11
22    continue
      close(7)
      ne=ne-1
      close(7)

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
      read(7,*) ar
      read(7,*) at
      read(7,77) dmat
      read(7,77) wmat
      read(7,77) cmat
      read(7,77) hmat
      read(7,77) amat
      close(7)
77    format(a)

      cr=cr/2.
      dr=dr/2.
      crr=crr/2.
      ar=ar/2.
      nbul=10

      airmat='air'

      open(7,file='source.txt',status='old')
      read(7,*) sr
      read(7,*) st
      read(7,*) pbt
      read(7,*) pst
      read(7,*) sdist
      read(7,77) smat
      read(7,77) bmat
      close(7)

      sr=sr/2.

      call readin(dmat,nge,gee,gemu)
      call readin(cmat,nc,ce,cmu)
      call readin(wmat,nw,we,wmu)
      call readin(hmat,nh,he,hmu)
      call readin(amat,na,ae,amu)
      call readin(airmat,nz,ze,zmu)
      call readin(smat,ns,se,smu)
      call readin(bmat,np,pe,pmu)

      do j=1,ne
        call inter(nge,gee,gemu,e(j),muge(j))
        call inter(nw,we,wmu,e(j),muw(j))
        call inter(nc,ce,cmu,e(j),muc(j))
        call inter(nh,he,hmu,e(j),muh(j))
        call inter(na,ae,amu,e(j),mua(j))
        call inter(nz,ze,zmu,e(j),muz(j))
        call inter(ns,se,smu,e(j),mus(j))
        call inter(np,pe,pmu,e(j),mup(j))
      enddo

      l=left(smat)
      r=right(smat)

      bt=0.001
      tt=bt

      zld=0.
      zud=dl-ddt
      rd=dr-dds
      rd2=rd*rd

      zlddt=zud
      zuddt=zlddt+ddt
      rddt=rd+dds
      rddt2=rddt*rddt

      zldds=zld
      zudds=zud
      rdds=rd+dds
      rdds2=rdds*rdds
      
      zlh=0.
      zuh=zud+ddt
      rh=rdds+hol
      rh2=rh*rh

      zlhv=zlh
      zuhv=zuh
      rhv=rh-hol
      rhv2=rhv*rhv

      zlcr=zld
      zucr=zlcr+crl
      rcr=crr
      rcr2=rcr*rcr

      zlc=zld
      zuc=zud+ddt+wd
      rc=cr
      rc2=rc*rc

      zlv=zlc
      zuv=zuc
      rv=rc-ct
      rv2=rv*rv

      zlw=zuc
      zuw=zlw+wt
      rw=rc
      rw2=rw*rw

      zla=zuw
      zua=zla+at
      ra=ar
      ra2=ra*ra

      zls=zuw+at+sdist+pbt
      zus=zls+st
      rs=sr-pst
      rs2=rs*rs

      zlp=zls-pbt
      zup=zus
      rp=sr
      rp2=rp*rp

      zub1=zld
      zlb1=zub1-bt
      rb1=rd
      rb12=rb1*rb1

      zub2=zld
      zlb2=zub2-bt
      rb2=rv
      rb22=rb2*rb2
      
      zub3=zlhv
      zlb3=zub3-bt
      rb3=rhv
      rb32=rb3*rb3
      
      zlt1=zud
      zut1=zlt1+tt
      rt1=rd
      rt12=rt1*rt1

      zlt2=zuv
      zut2=zlt2+tt
      rt2=rv
      rt22=rt2*rt2

      zlt3=zuhv
      zut3=zlt3+tt
      rt3=rhv
      rt32=rt3*rt3

      zud=zud-bul

      sbul=bul/nbul

      zlbul(1)=zud
      zubul(1)=zlbul(1)+sbul

      do i=2,nbul
        zlbul(i)=zubul(i-1)
        zubul(i)=zlbul(i)+sbul
      enddo

      rbul(1)=rd-sbul
      do i=2,nbul
        rbul(i)=rbul(i-1)-sbul
        rbul2(i)=rbul(i)*rbul(i)
      enddo

      pi=3.141592653

      do i=1,ne
        t(i)=0.
        sig(i)=0.
      enddo

      do i=1,ne
      do j=1,ne
        t2(i)=0.
      enddo
      enddo

      unc=0.01

      call sobseq(-6,x)

      n=0
    
100   continue

      n=n+1

      do j=1,ne
        u1(j)=0.
      enddo

      call sobseq(6,x)
      x0=x(1)
      x0=rs*sqrt(x0)

      dist=x(2)
      dist=dist*st
      z0=zls+dist

      fi=x(3)
      fi=2.*pi*fi

      costh=x(4)
      sinth=sqrt(1.-costh*costh)

      tx=sinth*cos(fi)
      ty=sinth*sin(fi)
      tz=costh
      if (tz.eq.0.) tz=1.E-06

      call path(zlc,zuc,rc2,x0,z0,tx,ty,tz,dc)
      if (dc.le.0.) goto 111

      call path(zld,zud,rd2,x0,z0,tx,ty,tz,dd)
      call path(zlcr,zucr,rcr2,x0,z0,tx,ty,tz,dcr)
      call path(zlw,zuw,rw2,x0,z0,tx,ty,tz,dw)
      call path(zla,zua,ra2,x0,z0,tx,ty,tz,da)
      call path(zlv,zuv,rv2,x0,z0,tx,ty,tz,dv)
      call path(zlh,zuh,rh2,x0,z0,tx,ty,tz,dh)
      call path(zlhv,zuhv,rhv2,x0,z0,tx,ty,tz,dhv)
      call path(zlddt,zuddt,rddt2,x0,z0,tx,ty,tz,dddt)
      call path(zldds,zudds,rdds2,x0,z0,tx,ty,tz,ddds)
      call path(zls,zus,rs2,x0,z0,tx,ty,tz,ds)
      call path(zlp,zup,rp2,x0,z0,tx,ty,tz,dp)
      call path(zlb1,zub1,rb12,x0,z0,tx,ty,tz,db1)
      call path(zlb2,zub2,rb22,x0,z0,tx,ty,tz,db2)
      call path(zlb3,zub3,rb32,x0,z0,tx,ty,tz,db3)
      call path(zlt1,zut1,rt12,x0,z0,tx,ty,tz,dt1)
      call path(zlt2,zut2,rt22,x0,z0,tx,ty,tz,dt2)
      call path(zlt3,zut3,rt32,x0,z0,tx,ty,tz,dt3)
      dbul=0.
      do i=1,nbul
        call path(zlbul(i),zubul(i),rbul2(i),x0,z0,tx,ty,tz,dbul1)
         dbul=dbul+dbul1
      enddo

      dc=dc-dv
      dh=dh-dhv
      ddds=ddds-dd
      dd=dd-dcr
      dd=dd+dbul
      if (dd.lt.0.) dd=0.
      dp=dp-ds
      if (dt1.gt.0.) ddds=0.
      if (dt2.gt.0.) dc=0.
      if (dt3.gt.0.) dh=0.
      if (db1.eq.0.) ddds=ddds/2.
      if (db2.eq.0.) dc=dc/2.
      if (db3.eq.0.) dh=dh/2.
      dead=dddt+ddds

      do j=1,ne
        u=(1.-exp(-muge(j)*dd))
        u=u*exp(-muw(j)*dw)*exp(-muc(j)*dc)
        u=u*exp(-muge(j)*dead)
        u=u*exp(-muh(j)*dh)
        u=u*exp(-mua(j)*da)
        u=u*exp(-muz(j)*sdist/tz)
        u=u*exp(-mus(j)*ds)*exp(-mup(j)*dp)
        u=u/2.
        u1(j)=u
      enddo

111   continue

      do j=1,ne
        u2(j)=0.
      enddo

      fi=x(5)
      fi=2.*pi*fi

      costh=x(6)
      sinth=sqrt(1.-costh*costh)

      tx=sinth*cos(fi)
      ty=sinth*sin(fi)
      tz=costh
      if (tz.eq.0.) tz=1.E-06

      call path(zlc,zuc,rc2,x0,z0,tx,ty,tz,dc)
      if (dc.le.0.) goto 333

      call path(zld,zud,rd2,x0,z0,tx,ty,tz,dd)
      call path(zlcr,zucr,rcr2,x0,z0,tx,ty,tz,dcr)
      call path(zlw,zuw,rw2,x0,z0,tx,ty,tz,dw)
      call path(zla,zua,ra2,x0,z0,tx,ty,tz,da)
      call path(zlv,zuv,rv2,x0,z0,tx,ty,tz,dv)
      call path(zlh,zuh,rh2,x0,z0,tx,ty,tz,dh)
      call path(zlhv,zuhv,rhv2,x0,z0,tx,ty,tz,dhv)
      call path(zlddt,zuddt,rddt2,x0,z0,tx,ty,tz,dddt)
      call path(zldds,zudds,rdds2,x0,z0,tx,ty,tz,ddds)
      call path(zls,zus,rs2,x0,z0,tx,ty,tz,ds)
      call path(zlp,zup,rp2,x0,z0,tx,ty,tz,dp)
      call path(zlb1,zub1,rb12,x0,z0,tx,ty,tz,db1)
      call path(zlb2,zub2,rb22,x0,z0,tx,ty,tz,db2)
      call path(zlb3,zub3,rb32,x0,z0,tx,ty,tz,db3)
      call path(zlt1,zut1,rt12,x0,z0,tx,ty,tz,dt1)
      call path(zlt2,zut2,rt22,x0,z0,tx,ty,tz,dt2)
      call path(zlt3,zut3,rt32,x0,z0,tx,ty,tz,dt3)
      dbul=0.
      do i=1,nbul
        call path(zlbul(i),zubul(i),rbul2(i),x0,z0,tx,ty,tz,dbul1)
        dbul=dbul+dbul1
      enddo

      dc=dc-dv
      dh=dh-dhv
      ddds=ddds-dd
      dd=dd-dcr
      dd=dd+dbul
      if (dd.lt.0.) dd=0.
      dp=dp-ds
      if (dt1.gt.0.) ddds=0.
      if (dt2.gt.0.) dc=0.
      if (dt3.gt.0.) dh=0.
      if (db1.eq.0.) ddds=ddds/2.
      if (db2.eq.0.) dc=dc/2.
      if (db3.eq.0.) dh=dh/2.
      dead=dddt+ddds

      do j=1,ne
        u=(1.-exp(-muge(j)*dd))
        u=u*exp(-muw(j)*dw)*exp(-muc(j)*dc)
        u=u*exp(-muge(j)*dead)
        u=u*exp(-muh(j)*dh)
        u=u*exp(-mua(j)*da)
        u=u*exp(-muz(j)*sdist/tz)
        u=u*exp(-mus(j)*ds)*exp(-mup(j)*dp)
        u=u/2.
        u2(j)=u
      enddo

333   continue

      smax=0.

      do j=1,ne
        u=u1(j)+u2(j)
	u=u/2.
        t(j)=(n-1)*t(j)+u
        t(j)=t(j)/n
        sig(j)=(n-1)*sig(j)+u*u
        sig(j)=sig(j)/n
        s(j)=sig(j)-t(j)*t(j)
	s(j)=abs(s(j))
        s(j)=sqrt(s(j)/n)
	if (t(j).gt.0.) then
          s(j)=s(j)/t(j)
          if (s(j).gt.smax) smax=s(j)
        endif
      enddo
      
      do i=1,ne
        u=u1(i)*u2(i)
        t2(i)=(n-1)*t2(i)+u
        t2(i)=t2(i)/n
      enddo
      
      if (smax.gt.unc.or.n.lt.10000) goto 100

      open(7,file='total.txt',status='unknown')
      do i=1,ne
        write(7,99) exp(e(i)),t(i),sqrt(t2(i))
      enddo
      close(7)
99    format(3e15.5)

      end

      subroutine readin(fname,n,e,mu)

      implicit none

      character*(*) fname
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

      subroutine inter(n,e,mu,xe,xmu)
      implicit none
      integer n,j
      real e(100),mu(100),xe,xmu
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
      real zlo,zup,r2,x0,z0,tx,ty,tz
      real k
      real za,zb
      real a,b,c,det,q,sgn
      real d
      d=0.
      if (zlo.ge.zup.or.r2.le.0.) return
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
      k=q/a
      za=z0+k*tz
      if (za.lt.zlo) za=zlo
      if (za.gt.zup) za=zup
      k=c/q
      zb=z0+k*tz
      if (zb.le.zlo) zb=zlo
      if (zb.gt.zup) zb=zup
      if (za.gt.z0) za=z0
      if (zb.gt.z0) zb=z0
      d=abs(za-zb)/tz
      return
      end

      SUBROUTINE sobseq(n,x)
      INTEGER n,MAXBIT,MAXDIM
      real x(6)
      PARAMETER (MAXBIT=30,MAXDIM=6)
      INTEGER i,im,in,ipp,j,k,l,ip(MAXDIM),iu(MAXDIM,MAXBIT),iv(MAXBIT*
     *MAXDIM),ix(MAXDIM),mdeg(MAXDIM)
      real fac
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
