
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
      peak=max(1.d-15,tot*x)
      peak2=max(1.d-15,tot2*x)
      write(9,77) e,peak,peak2
77    format(3e15.5)
      goto 33
44    continue
      close(7)
      close(9)

      end
 
