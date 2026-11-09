
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

      program efficiency

      implicit none

      double precision e,x,peak,peak2,tot,tot2
      double precision ptt(3000)
      integer n

      open(7,file='ptt.txt',status='old')
      do n=1,3000
        read(7,*) e,ptt(n)
      enddo
      close(7)

      open(7,file='total.txt',status='old')
      open(9,file='efficiency.txt',status='unknown')
33    continue
      read(7,*,end=44) e,tot,tot2
      n=e+0.5
      x=ptt(n)
      peak=tot*x
      peak2=tot2*x
      write(9,77) e,peak,peak2
77    format(3e15.5)
      goto 33
44    continue
      close(7)
      close(9)

      end
 
