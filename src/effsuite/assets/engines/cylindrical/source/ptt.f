
      program ptt

      implicit none

      common /ge/ ege(1000),ge(1000),gef(1000),gec(1000),gep(1000),nge
      common /total/ et(100),tt(100),nt

      real ege,ge,gef,gec,gep
      real rhoge,aa,zz,ll
      real de,erad
      real range,rr
      real et,tt
      real dr,dl,crr,crl,ddt,dds,bul
      real dv,vv
      real s,z,g,emin,w,sum,q,p,costh

      real l,f,dsde,gemu,gemuf,gemuc,gemup,tot
      external l,f,gemu,gemuf,gemuc,gemup,tot
      
      integer nge,nt
      integer jmin,i,j,k

      real gmc(3000),gmf(3000),gmp(3000),gm(3000),t(3000)
      real u(3000)

      character*70 dmat,mat
      integer l1,r1,l2,r2

      integer left,right
      external left,right

      open(7,file='detector.txt',status='old')
      read(7,*) 
      read(7,*) 
      read(7,*) dr
      read(7,*) dl
      read(7,*) ddt
      read(7,*) dds
      read(7,*) 
      read(7,*) 
      read(7,*) crr
      read(7,*) crl
      read(7,*) 
      read(7,*) bul
      read(7,*) 
      read(7,*) 
      read(7,55) dmat 
      read(7,*) 
      read(7,*) 
      read(7,*) 
      read(7,*)
      close(7)
55    format(a)

      l1=left(dmat)
      r1=right(dmat)

      dr=dr/2.
      crr=crr/2.

      dr=dr-dds
      dl=dl-ddt

      vv=dr*dr*dl
      dv=crr*crr*crl+dr*bul*bul
      dv=(vv-dv)/vv

      call readin(dmat,nge,ege,gef,gec,gep,ge,rhoge,dv)

      aa=0.
      zz=0.

      open(7,file='zzaa.txt',status='old')
33    continue
      read(7,55,end=44) mat
      l2=left(mat)
      r2=right(mat)
      read(7,*) zz,aa
      if (mat(l1:r1).ne.dmat(l2:r2)) goto 33
44    continue
      close(7)

      ll=l(aa,zz,rhoge)

      nt=1
      open(7,file='eta.txt',status='old')
11    continue
      read(7,*,end=12) et(nt),tt(nt)
      et(nt)=log(et(nt))
      tt(nt)=log(tt(nt))
      nt=nt+1
      goto 11
12    continue
      close(7)
      nt=nt-1      

      do i=1,3000
        z=i
        gm(i)=gemu(z)
        gmc(i)=gemuc(z)
        gmf(i)=gemuf(z)
        gmp(i)=gemup(z)
	t(i)=tot(z)
      enddo

      do i=1,10
        u(i)=1.
      enddo

      do i=11,3000
        s=0.
        sum=0.
	z=i
        g=z/511.
        emin=z/(2.*g+1.)
	jmin=emin+0.5
        do j=jmin,i-1
          zz=j
          de=z-j
          range=de/1000.-1.
          if (range.lt.0.) range=0.
          erad=de*(1.-exp(-range/ll))
          k=erad+0.5
          if (k.lt.1) k=1
          p=zz/z
          w=1./p
          costh=1.-(w-1.)/g
          q=(p+w-1.+costh*costh)/z/g
          s=s+u(j)*t(j)*q*t(k)*(1.-range/dr-range/dl) 
          sum=sum+q
        enddo
        if (sum.le.0.) then
          w=1.
        else
          w=s/sum
        endif
        u(i)=gmf(i)+gmc(i)*w+gmp(i)*u(511)*t(511)*u(511)*t(511)
        u(i)=u(i)/gm(i)
      enddo
  
      open(7,file='ptt.txt',status='unknown')
      do i=1,3000
	write(7,77) i,u(i)
      enddo
77    format(i10,e12.4)
      close(7)

      end


      real function gemu(x)

      implicit none

      real x

      common /ge/ ege(1000),ge(1000),gef(1000),gec(1000),gep(1000),nge
      real ege,ge,gef,gec,gep
      integer nge

      real y,z
      integer j

      y=log(x)
      j=1.
      do while(ege(j).lt.y.and.j.lt.nge) 
         j=j+1
      enddo
      j=j-1
      if (j.eq.0) j=1
      z=(ge(j+1)-ge(j))/(ege(j+1)-ege(j))*(y-ege(j))+ge(j)
      gemu=exp(z)

      return
      end


      real function gemuc(x)

      implicit none

      real x

      common /ge/ ege(1000),ge(1000),gef(1000),gec(1000),gep(1000),nge
      real ege,ge,gef,gec,gep
      integer nge

      real y,z
      integer j

      y=log(x)
      j=1.
      do while(ege(j).lt.y.and.j.lt.nge) 
         j=j+1
      enddo
      j=j-1
      if (j.eq.0) j=1
      z=(gec(j+1)-gec(j))/(ege(j+1)-ege(j))*(y-ege(j))+gec(j)
      gemuc=exp(z)

      return
      end


      real function gemuf(x)

      implicit none

      real x

      common /ge/ ege(1000),ge(1000),gef(1000),gec(1000),gep(1000),nge
      real ege,ge,gef,gec,gep
      integer nge

      real y,z
      integer j

      y=log(x)
      j=1.
      do while(ege(j).lt.y.and.j.lt.nge) 
         j=j+1
      enddo
      j=j-1
      if (j.eq.0) j=1
      z=(gef(j+1)-gef(j))/(ege(j+1)-ege(j))*(y-ege(j))+gef(j)
      gemuf=exp(z)

      return
      end


      real function gemup(x)

      implicit none

      real x

      common /ge/ ege(1000),ge(1000),gef(1000),gec(1000),gep(1000),nge
      real ege,ge,gef,gec,gep
      integer nge

      real y,z
      integer j

      y=log(x)
      j=1.
      do while(ege(j).lt.y.and.j.lt.nge) 
         j=j+1
      enddo
      j=j-1
      if (j.eq.0) j=1
      z=(gep(j+1)-gep(j))/(ege(j+1)-ege(j))*(y-ege(j))+gep(j)
      gemup=exp(z)

      return
      end


      real function tot(x)

      implicit none

      real x

      common /total/ et(100),tt(100),nt
      real et,tt
      integer nt

      real y,z
      integer j

      y=log(x)
      j=1.
      do while(et(j).lt.y.and.j.lt.nt) 
         j=j+1
      enddo
      j=j-1
      if (j.eq.0) j=1
      z=(tt(j+1)-tt(j))/(et(j+1)-et(j))*(y-et(j))+tt(j)
      z=exp(z)

      if (z.lt.0.) z=0.
      if (z.gt.1.) z=1.

      tot=z

      return
      end


      subroutine readin(fname,n,e,muf,muc,mup,mu,den,dlt)

      implicit none

      character*(*) fname
      character*(132) line

      integer n
      integer left,right
      integer l,r
      integer kode

      real e(1000),muf(1000),muc(1000),mup(1000),mu(1000)
      real ene,rayl,comp,phot,pair,pair1,tot,tot1
      real den,dlt

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

        muf(n)=phot
        muc(n)=comp
        mup(n)=pair
        mu(n)=phot+comp+pair

        muf(n)=muf(n)/10.
        muc(n)=muc(n)/10.
        mup(n)=mup(n)/10.
        mu(n)=mu(n)/10.

        e(n)=log(e(n))
        muf(n)=log(muf(n))
        muc(n)=log(muc(n))
        mup(n)=log(mup(n))
        mu(n)=log(mu(n))
     
        n=n+1
      
      endif
   
      goto 1

2     continue

      close(7)
      n=n-1

      return
      end

      real function l(a,z,rho)

      implicit none

      real f

      real a,z,rho
      real re,alpha,na

      real x

      data re,alpha,na /2.817E-13,7.297E-3,6.022E23/

      x=4.*z*(z+1)*rho*na/a*re**2*alpha*(log(183.*z**(-1./3.))-f(z))
      l=10./x
  
      return
      end


      real function f(z)

      implicit none

      real z
      real alpha
      real k1,k2,k3,k4
      real x,w

      data alpha /7.297E-3/
      data k1,k2,k3,k4 /0.20206,-0.0369,0.0083,-0.002/

      x=z*alpha
      w=x*x

      f=w*(1./(1.+w)+k1+k2*w+k3*w*w+k4*w*w*w)

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