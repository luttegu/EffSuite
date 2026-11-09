
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

        program emissions

        implicit none

        double precision p(100,100),t(100,100)
        double precision alpha(100,100),alphak(100,100),alphal(100,100)
        double precision f(100),t12(100),pk(100),pl(100),eg(100)
        double precision zf(100)
        double precision e(100,100),x(100,100),a(100,100)
        double precision exk,omegak,exl,omegal,epsxk,totxk,epsxl,totxl

 	integer n

        double precision en,xx,aa,ak,al,ff,ppk,ppl,tau
	double precision totx,sum,d1,d2

        double precision ee(100),pp(100),tt(100)
        double precision s(3000)

        integer i,j,k,ne

        ne=1
        open(7,file='efficiency.txt',status='old')
        open(8,file='buildup.txt',status='old')
66      continue
        read(7,*,end=88) ee(ne),d1,pp(ne)
        read(8,*) ee(ne),d2,tt(ne)
        ee(ne)=log(ee(ne))
        pp(ne)=log(pp(ne))
        tt(ne)=log(tt(ne))
        ne=ne+1
        goto 66
88      continue
        close(7)
        close(8)
	close(9)
        ne=ne-1

	do i=1,100
          eg(i)=0.
	  f(i)=0.
	  pk(i)=0.
	  pl(i)=0.
	  t12(i)=0.
          zf(i)=0.
	enddo

	do i=1,100
	do j=1,100
	  e(i,j)=0.
	  x(i,j)=0.
	  alpha(i,j)=0.	  
          alphak(i,j)=0.
	  alphal(i,j)=0.
          a(i,j)=0.
          p(i,j)=0.
          t(i,j)=0.
	enddo
	enddo

        open(7,file='coin.txt',status='old')

 	read(7,*) exk,omegak,exl,omegal

        n=1

11      continue

	read(7,*) en,ff,ppk,ppl,tau

        if (en.lt.0.) goto 22

        eg(n)=en
	f(n)=ff
	pk(n)=ppk
	pl(n)=ppl
	t12(n)=tau
	n=n+1

	goto 11

22	continue
        n=n-1

33	continue
 
	read(7,*,end=55) i,j,en,xx,aa,ak,al

        e(i,j)=en
	x(i,j)=xx
	alpha(i,j)=aa
	alphak(i,j)=ak
	alphal(i,j)=al

	goto 33

55	continue
	close(7)

        open(7,file='emissions2.txt',status='old')
        do i=1,3000
          read(7,*) j,s(i)
        enddo
        close(7)

	do i=1,n
	  sum=0.
	  do j=1,i-1
	    sum=sum+x(i,j)*(1.+alpha(i,j))
	  enddo
	  if (sum.gt.0.) then
	    do j=1,i-1
	      x(i,j)=x(i,j)*(1.+alpha(i,j))/sum
	    enddo
          else
            t12(i)=1.e30
	  endif
	enddo

        do i=1,n
        do j=1,i-1
          if (e(i,j).gt.0.) then
            call inter(ne,ee,pp,log(e(i,j)),p(i,j))
            call inter(ne,ee,tt,log(e(i,j)),t(i,j))
            p(i,j)=exp(p(i,j))
            t(i,j)=exp(t(i,j))
	    if (p(i,j).gt.1.) p(i,j)=1.
	    if (t(i,j).gt.1.) t(i,j)=1.
	    if (p(i,j).lt.0.) p(i,j)=0.
	    if (t(i,j).lt.0.) t(i,j)=0.
          endif
        enddo
        enddo

        call inter(ne,ee,pp,log(exk),epsxk)
        call inter(ne,ee,tt,log(exk),totxk)
        epsxk=exp(epsxk)
        totxk=exp(totxk)
        if (epsxk.lt.0.) epsxk=0.
        if (totxk.lt.0.) totxk=0.
        if (epsxk.gt.1.) epsxk=1.
        if (totxk.gt.1.) totxk=1.

        call inter(ne,ee,pp,log(exl),epsxl)
        call inter(ne,ee,tt,log(exl),totxl)
        epsxl=exp(epsxl)
        totxl=exp(totxl)
        if (epsxl.lt.0.) epsxl=0.
        if (totxl.lt.0.) totxl=0.
        if (epsxl.gt.1.) epsxl=1.
        if (totxl.gt.1.) totxl=1.
        
        do i=1,n
	do j=1,i-1
           a(i,j)=x(i,j)*p(i,j)/(1.+alpha(i,j))
        enddo
        enddo

        do i=n,1,-1
          zf(i)=f(i)
          do j=i+1,n
            zf(i)=zf(i)+zf(j)*x(j,i)
          enddo
        enddo

        do i=1,n
        do j=1,i-1
          k=e(i,j)+0.5
          if (k.gt.1.and.k.lt.3000) s(k)=s(k)+zf(i)*a(i,j)
        enddo
        enddo

        open(7,file='emissions2.txt',status='unknown')
        do i=1,3000
          write(7,77) i,s(i) 
        enddo
        close(7)
77      format(i10,e15.5)

        end

        subroutine inter(n,x,y,xx,yy)
        implicit none
        double precision x(100),y(100)
        double precision xx,yy
        integer n,j
        j=1
        do while(x(j).lt.xx.and.j.lt.n)
          j=j+1
        enddo
        j=j-1
        if (j.eq.0) j=1
        yy=(y(j+1)-y(j))/(x(j+1)-x(j))*(xx-x(j))+y(j)
        return
        end

