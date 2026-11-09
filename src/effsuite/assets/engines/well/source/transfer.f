
CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC
C                                                                       C
C  EFFTRAN (version 4.4.5 2016)                                         C
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

        program transfer

        implicit none

        double precision e,eps,u,u1,u2,t1,t2

        open(7,file='reference.txt',status='old')
        open(8,file='standard-efficiency.txt',status='old')
        open(9,file='sample-efficiency.txt',status='old')
        open(10,file='efficiency.txt',status='unknown')

1       continue
        read(7,*,end=2) e,eps,u
        read(8,*) e,t1
        u1=0.5
        read(9,*) e,t2
        u2=0.5
	u=u*u+u1*u1+u2*u2
        u=sqrt(u)
        eps=eps*t2/t1
        write(10,77) e,eps,u
77      format(3e15.5)
        goto 1

2       continue

        close(7)
        close(8)
        close(9)
        close(10)

        end
