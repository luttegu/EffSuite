
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

        program corrections

        implicit none

        double precision x(3000),x1(3000),x2(3000)
        integer i,j

        open(7,file='emissions.txt',status='old')
        do i=1,3000
          read(7,*) j,x(i)
        enddo
        close(7)

        open(7,file='peak.txt',status='old')
        do i=1,3000
          read(7,*) j,x1(i)
        enddo
        close(7)

        open(7,file='emissions2.txt',status='old')
        do i=1,3000
          read(7,*) j,x2(i)
        enddo
        close(7)

        open(7,file='correct.txt',status='unknown')
        do i=2,3000
          if (x(i).gt.0..and.x1(i).gt.0..and.x2(i).gt.0.)
     +    write(7,77) i,x(i)/(x1(i)-x2(i)+x(i))
        enddo
        close(7)
77      format(i10,e15.5)

        end
