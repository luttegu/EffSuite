
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