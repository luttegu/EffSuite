
        program coincidence

        implicit none

        real p(100,100),t(100,100)
        real alpha(100,100),alphak(100,100),alphal(100,100)
        real f(100),t12(100),pk(100),pl(100),eg(100)
        real m(100),z(100),zf(100)
        real e(100,100),x(100,100)
        real a(100,100),b(100,100),w(100,100)
        real exk,omegak,exl,omegal,epsxk,totxk,epsxl,totxl

 	integer n

        real en,xx,aa,ak,al,ff,ppk,ppl,tau,t0
	real totx,sum

        real ee(100),pp(100),tt(100),pp1(100),tt1(100)
        real s(3000),s1(3000)

        integer i,j,k,ne

	character*10 nuc,oldnuc
	integer left,right,r
        
	ne=1
        open(7,file='efficiency.txt',status='old')
        open(8,file='buildup.txt',status='old')
66      continue
        read(7,*,end=88) ee(ne),pp(ne),pp1(ne)
        read(8,*) ee(ne),tt(ne),tt1(ne)
        ee(ne)=log(ee(ne))
        pp(ne)=log(pp(ne))
        tt(ne)=log(tt(ne))
        pp1(ne)=log(pp1(ne))
        tt1(ne)=log(tt1(ne))
        ne=ne+1
        goto 66
88      continue
        close(7)
        close(8)
        ne=ne-1

        t0=10.

        open(7,file='kordaten.txt',status='old')
        open(9,file='coin.txt',status='unknown')

	oldnuc=''

	do i=1,3000
	  s(i)=0.
	  s1(i)=0.
	enddo

123	continue
	
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
	  if (e(i,j).ne.0.) e(i,j)=0.
	  if (x(i,j).ne.0.) x(i,j)=0.
	  if (alpha(i,j).ne.0.) alpha(i,j)=0.	  
          if (alphak(i,j).ne.0.) alphak(i,j)=0.
	  if (alphal(i,j).ne.0.) alphal(i,j)=0.
          if (a(i,j).ne.0.) a(i,j)=0.
          if (p(i,j).ne.0.) p(i,j)=0.
          if (t(i,j).ne.0.0) t(i,j)=0.
	enddo
	enddo

	read(7,'(a)',end=99) nuc
	if (oldnuc.eq.'') oldnuc=nuc

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
 
	read(7,*) i,j,en,xx,aa,ak,al
	if (i.eq.-1) goto 55

        e(i,j)=en
	x(i,j)=xx
	alpha(i,j)=aa
	alphak(i,j)=ak
	alphal(i,j)=al

	goto 33

55	continue

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

	r=right(nuc)
        if (nuc(r:r).eq.'b') goto 25

	do i=2,3000
	  s1(i)=s1(i)+s(i)
          if (s(i).gt.0.) write(9,77) oldnuc,i,s(i)/s1(i)
        enddo
77      format(a10,i10,f15.3)

	oldnuc=nuc

	do i=1,3000
          if(s(i).ne.0.) s(i)=0.
          if (s1(i).ne.0.) s1(i)=0.
        enddo

25	continue

c emissions
	
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

c peak

        do i=1,n
        do j=1,i-1
          if (e(i,j).gt.0.) then
            call inter(ne,ee,pp1,log(e(i,j)),p(i,j))
            call inter(ne,ee,tt1,log(e(i,j)),t(i,j))
            p(i,j)=exp(p(i,j))
            t(i,j)=exp(t(i,j))
	    if (p(i,j).gt.1.) p(i,j)=1.
	    if (t(i,j).gt.1.) t(i,j)=1.
	    if (p(i,j).lt.0.) p(i,j)=0.
	    if (t(i,j).lt.0.) t(i,j)=0.
          endif
        enddo
        enddo

        call inter(ne,ee,pp1,log(exk),epsxk)
        call inter(ne,ee,tt1,log(exk),totxk)
        epsxk=exp(epsxk)
        totxk=exp(totxk)
        if (epsxk.lt.0.) epsxk=0.
        if (totxk.lt.0.) totxk=0.
        if (epsxk.gt.1.) epsxk=1.
        if (totxk.gt.1.) totxk=1.

        call inter(ne,ee,pp1,log(exl),epsxl)
        call inter(ne,ee,tt1,log(exl),totxl)
        epsxl=exp(epsxl)
        totxl=exp(totxl)
        if (epsxl.lt.0.) epsxl=0.
        if (totxl.lt.0.) totxl=0.
        if (epsxl.gt.1.) epsxl=1.
        if (totxl.gt.1.) totxl=1. 

        do i=1,n
	do j=1,i-1
           a(i,j)=x(i,j)*p(i,j)/(1.+alpha(i,j))
           totx=alphak(i,j)*omegak*totxk
	   totx=totx+alphal(i,j)*omegal*totxl
           b(i,j)=x(i,j)*(1.-(totx+t(i,j))/(1.+alpha(i,j)))
        enddo
        enddo

        do i=n,1,-1
          zf(i)=f(i)
          do j=i+1,n
            zf(i)=zf(i)+zf(j)*x(j,i)
          enddo
        enddo

        do i=n,1,-1
          totx=pk(i)*omegak*totxk
	  totx=totx+pl(i)*omegal*totxl
          z(i)=f(i)*(1.-totx)        
          do j=i+1,n
            z(i)=z(i)+z(j)*b(j,i)
          enddo
          if (t12(i).gt.t0) z(i)=zf(i)
        enddo

        m(1)=1.
        do i=2,n
          m(i)=0.
          do j=1,i-1
            m(i)=m(i)+b(i,j)*m(j)
          enddo
          if (t12(i).gt.t0) m(i)=1.
        enddo

        do i=1,n
        do j=1,i-1
          w(i,j)=a(i,j)
          do k=j+1,i-1
            if (t12(k).lt.t0.and.j.lt.i) w(i,j)=w(i,j)+a(i,k)*w(k,j)
          enddo
        enddo
        enddo

        do i=1,n
        do j=1,i-1
          k=e(i,j)+0.5
          if (k.gt.1.and.k.lt.3000) s1(k)=s1(k)+z(i)*w(i,j)*m(j)
        enddo
        enddo

c emissions 2

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
          if (k.gt.1.and.k.lt.3000) s1(k)=s1(k)-zf(i)*a(i,j)
        enddo
        enddo


	goto 123

99	continue
	
        do i=2,3000
	  s1(i)=s1(i)+s(i)
          if (s(i).gt.0.) write(9,77) oldnuc,i,s(i)/s1(i)
        enddo

	close(7)
	close(9)

        end

        subroutine inter(n,x,y,xx,yy)
        implicit none
        real x(100),y(100)
        real xx,yy
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
