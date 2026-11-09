
	program gammavision

        implicit none

	integer*2 libid,libid2,reclen,rectot,dum1,typrec,dum2,dum3
        integer*2 isomax,isolen,isostr,isoend,isofre,dum4,dum5
        integer*2 isobas,pkmax,pklen,pkstr,pkend,pkfre,dum6,dum7
        integer*2 pkbas,rsv1(8)
        integer*2 nucuse,pkuse,rsv2(11)
        character*19 datim

        integer*2 nnuc

	character*8 name(1000),rsv3(1000)
        real*4 haflif(1000),uncert(1000)
        integer*2 uni(1000),isonum(1000),isotyp(1000)
        integer*2 isoflg(1000),selfpt(1000),rsv4(1000)
        integer*2 firstpk(1000),backpt(1000),forept(1000)

	integer*2 npeak

	real*4 kev(1000),gamprd(1000)
	integer*2 pkflg(10000),rsv5(10000),rsv6(10000),pknum(10000)
        integer*2 nucpt(10000),dum8(10000),dum9(10000),dum10(10000)
        integer*2 backpt2(10000),forept2(10000)
        integer*2 bnucpt(10000),fnucpt(10000)

	character*12 nuc
	real*4 e,f,x
	integer*2 l1,r1

	real*4 de,demax,gamprdold,z

	integer*2 length,left,right
	external length,left,right

	integer*2 start,stop
	integer*2 i,j,k,m,n
	integer*2 r,l
	integer*2 c

	open(unit=7,file='MEFFTRAN.Lib',status='old',form='unformatted',
     +  access='direct',recl=128)

	read(unit=7,rec=1) 
     +  libid,libid2,reclen,rectot,dum1,typrec,dum2,dum3,
     +  isomax,isolen,isostr,isoend,isofre,dum4,dum5,
     +  isobas,pkmax,pklen,pkstr,pkend,pkfre,dum6,dum7,pkbas,
     +  rsv1,datim,nucuse,pkuse,rsv2

	n=1

	do k=isobas,pkbas-1

	read(unit=7,rec=k)
     +  name(n),haflif(n),uncert(n),uni(n),isonum(n),
     +  isotyp(n),isoflg(n),rsv3(n),selfpt(n),rsv4(n),
     +  firstpk(n),backpt(n),forept(n),
     +  name(n+1),haflif(n+1),uncert(n+1),uni(n+1),isonum(n+1),
     +  isotyp(n+1),isoflg(n+1),rsv3(n+1),selfpt(n+1),rsv4(n+1),
     +  firstpk(n+1),backpt(n+1),forept(n+1),
     +  name(n+2),haflif(n+2),uncert(n+2),uni(n+2),isonum(n+2),
     +  isotyp(n+2),isoflg(n+2),rsv3(n+2),selfpt(n+2),rsv4(n+2),
     +  firstpk(n+2),backpt(n+2),forept(n+2)

	n=n+3

	enddo

	nnuc=n

	n=1

	do k=pkbas,rectot

	read(unit=7,rec=k)
     +  kev(n),gamprd(n),
     +  pkflg(n),dum8(n),dum9(n),dum10(n),pknum(n),
     +  nucpt(n),rsv5(n),rsv6(n),
     +  backpt2(n),forept2(n),bnucpt(n),fnucpt(n),
     +  kev(n+1),gamprd(n+1),
     +  pkflg(n+1),dum8(n+1),dum9(n+1),dum10(n+1),pknum(n+1),
     +  nucpt(n+1),rsv5(n+1),rsv6(n+1),
     +  backpt2(n+1),forept2(n+1),bnucpt(n+1),fnucpt(n+1),
     +  kev(n+2),gamprd(n+2),
     +  pkflg(n+2),dum8(n+2),dum9(n+2),dum10(n+2),pknum(n+2),
     +  nucpt(n+2),rsv5(n+2),rsv6(n+2),
     +  backpt2(n+2),forept2(n+2),bnucpt(n+2),fnucpt(n+2),
     +  kev(n+3),gamprd(n+3),
     +  pkflg(n+3),dum8(n+3),dum9(n+3),dum10(n+3),pknum(n+3),
     +  nucpt(n+3),rsv5(n+3),rsv6(n+3),
     +  backpt2(n+3),forept2(n+3),bnucpt(n+3),fnucpt(n+3)

	n=n+4

	enddo

	npeak=n

	close(7)

	call system('coin.exe')

	open(11,file='gv.txt',status='unknown')

	do n=1,nnuc

	if (length(name(n)).eq.0) goto 99       
	
	l=left(name(n))
	r=right(name(n))

	do k=1,npeak

	if (nucpt(k).ne.selfpt(n)) goto 77

	gamprdold=gamprd(k)
	demax=1.e30
	c=0
	x=1.
	z=1.

	open(7,file='coin.txt',status='old')
15	continue
	read(7,*,end=16) nuc,e,f
	l1=left(nuc)
	r1=right(nuc)
	de=abs(e-kev(k))
	if ((name(n)(l:r).eq.nuc(l1:r1)).and.(de.lt.demax)) then
	  demax=de
	  x=f
        endif
	goto 15
16      continue
	close(7)

        if (demax.lt.1.0) then
	  gamprd(k)=gamprd(k)/x
	  c=1
	  z=x
	endif

	write(11,55) name(n)
	write(11,57) kev(k),gamprdold,gamprd(k),z,c
55	format(a)
57	format(f10.2,f10.2,f10.2,f10.3,i5,e12.2)

77	continue	

	enddo

99	continue

	enddo

	close(11)

	open(unit=7,file='MEFFTRAN.Lib',status='old',form='unformatted',
     +  access='direct',recl=128)

	n=1

	do k=pkbas,rectot

	write(unit=7,rec=k)
     +  kev(n),gamprd(n),
     +  pkflg(n),dum8(n),dum9(n),dum10(n),pknum(n),
     +  nucpt(n),rsv5(n),rsv6(n),
     +  backpt2(n),forept2(n),bnucpt(n),fnucpt(n),
     +  kev(n+1),gamprd(n+1),
     +  pkflg(n+1),dum8(n+1),dum9(n+1),dum10(n+1),pknum(n+1),
     +  nucpt(n+1),rsv5(n+1),rsv6(n+1),
     +  backpt2(n+1),forept2(n+1),bnucpt(n+1),fnucpt(n+1),
     +  kev(n+2),gamprd(n+2),
     +  pkflg(n+2),dum8(n+2),dum9(n+2),dum10(n+2),pknum(n+2),
     +  nucpt(n+2),rsv5(n+2),rsv6(n+2),
     +  backpt2(n+2),forept2(n+2),bnucpt(n+2),fnucpt(n+2),
     +  kev(n+3),gamprd(n+3),
     +  pkflg(n+3),dum8(n+3),dum9(n+3),dum10(n+3),pknum(n+3),
     +  nucpt(n+3),rsv5(n+3),rsv6(n+3),
     +  backpt2(n+3),forept2(n+3),bnucpt(n+3),fnucpt(n+3)

	n=n+4

	enddo

	close(7)

	end

	integer*2 function length(s)
	implicit none
	character*(*) s
	integer n
	n=len(s)
11	continue
	if (s(n:n).ne.' '.and.s(n:n).ne.char(0)) goto 33
	n=n-1
	if (n.eq.0) goto 33
	goto 11
33	continue
	length=n
	return
	end

      integer*2 function left(s)
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

      integer*2 function right(s)
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
	  