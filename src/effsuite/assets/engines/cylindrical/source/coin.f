
	program coin

C	 input: detector.txt, source.txt
C	 output: coin.txt

	call system('del /Q /F total.txt')
	call system('del /Q /F scatter.txt')
	call system('del /Q /F buildup.txt')
	call system('del /Q /F eta.txt')
	call system('del /Q /F ptt.txt')
	call system('del /Q /F efficiency.txt')
	call system('del /Q /F mine.txt')
	call system('del /Q /F reference.txt')
	call system('mine.exe')
	call system('energy.exe')
	call system('total.exe')
	call system('scatter.exe')
	call system('buildup.exe')
	call system('eta.exe')
	call system('ptt.exe')
	call system('efficiency.exe')
	call system('coincidence.exe')

	end
