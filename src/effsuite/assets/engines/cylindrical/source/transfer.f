
        program transfer

        implicit none

        double precision e,eps,u,u1,u2,t1,t2,x

C       Columns of standard-efficiency.txt / sample-efficiency.txt
C       (total.exe): energy, total efficiency, second moment, relative
C       Monte Carlo uncertainty (fraction). As in EFFTRAN 4.9 the latter
C       enters the transfer uncertainty in percent.

        open(7,file='reference.txt',status='old')
        open(8,file='standard-efficiency.txt',status='old')
        open(9,file='sample-efficiency.txt',status='old')
        open(10,file='efficiency.txt',status='unknown')

1       continue
        read(7,*,end=2) e,eps,u
        read(8,*) e,t1,x,u1
        u1=100.d0*u1
        read(9,*) e,t2,x,u2
        u2=100.d0*u2
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
