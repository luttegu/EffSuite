   
      program energies      

      implicit none

      real e(100),ee,emin,emax,de
      integer i,ne

      ne=25
	
      open(7,file='mine.txt',status='old')
      read(7,*) emin
      close(7)

      emax=3000.

      de=log(emax)-log(emin)
      de=de/ne

      ee=log(emin)
      
      do i=1,ne+1
        e(i)=ee
	ee=ee+de
      enddo

      ne=ne+1

      open(7,file='reference.txt',status='unknown')

      do i=1,ne
        write(7,77) exp(e(i))
      enddo
77    format(f12.2)

      close(7)

      end