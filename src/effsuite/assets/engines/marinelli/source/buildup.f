
      program buildup

      implicit none

      double precision e(1000),eps(1000),eps2(1000)
      double precision sca(1000),epsn(1000),b(1000)
      double precision eps1,sca1,add,sc,esc
      integer ne
      character*30 fname
      integer i,j
      
      double precision ecbar
      external ecbar

      fname='total.txt'
      call readin(fname,ne,e,eps)
      fname='scatter.txt'
      call readin(fname,ne,e,sca)

      do i=1,ne

        epsn(i)=exp(eps(i))
        add=0.
        sc=1.
        esc=exp(e(i))

        do j=1,10

        call inter(ne,e,sca,log(esc),sca1)
        sc=sc*sca1
        esc=ecbar(esc)
        call inter(ne,e,eps,log(esc),eps1)
        add=add+sc*eps1

        enddo

        epsn(i)=epsn(i)+add

      enddo

      do i=1,ne
        b(i)=epsn(i)/exp(eps(i))
      enddo

      open(7,file='total.txt',status='unknown')
      open(9,file='buildup.txt',status='unknown')
      do i=1,ne
        read(7,*) e(i),eps(i),eps2(i)
        write(9,77) e(i),eps(i)*b(i),eps2(i)*b(i)
      enddo
      close(7)
      close(9)
77    format(3e15.5)

      end

      subroutine readin(fname,n,e,mu)
      implicit none
      character*(30) fname
      integer n
      double precision e(1000),mu(1000)
      integer left,right
      integer l,r
      n=1
      l=left(fname)
      r=right(fname)
      open(7,file=fname(l:r),status='old')
1     continue
      read(7,*,end=2) e(n),mu(n)
      if (mu(n).le.0.) mu(n)=1.e-15
      e(n)=log(e(n))
      mu(n)=log(mu(n))
      n=n+1
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

      double precision function ecbar(e)
      double precision e
      double precision u,g,y
      g=e/511.
      y=log(1.+2.*g)
      u=(-6.*g-30.*g**2-36.*g**3+12.*g**4+32.*g**5+
     +     3.*y+18.*g*y+36.*g**2*y+24.*g**3*y)/
     +   (3.*(1.+2.*g)*(4.*g+16.*g**2+18.*g**3+2.*g**4-
     +        2.*y-10.*g*y-15.*g**2*y-4.*g**3*y+4.*g**4*y))
      ecbar=u*e
      end

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
