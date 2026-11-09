
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

	program initialize

	implicit none

	double precision s(3000)
	integer i

	do i=1,3000
          s(i)=0.
        enddo

        open(7,file='peak.txt',status='unknown')
        do i=1,3000
          write(7,77) i,s(i)
        enddo
	close(7)

        open(7,file='emissions.txt',status='unknown')
        do i=1,3000
          write(7,77) i,s(i)
        enddo
	close(7)

        open(7,file='emissions2.txt',status='unknown')
        do i=1,3000
          write(7,77) i,s(i)
        enddo
	close(7)

77	format(i10,e15.5)

	end
