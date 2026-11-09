
	program trans

C 	input: detector.txt, sample.txt, standard.txt, reference.txt
C 	output: efficiency.txt

	call system('del /Q /F standard-efficiency.txt')
	call system('del /Q /F sample-efficiency.txt')
	call system('del /Q /F efficiency.txt')
	call system('del /Q /F total.txt')
	call system('copy sample.txt source.txt')
	call system('total.exe')
	call system('copy total.txt sample-efficiency.txt')
	call system('copy standard.txt source.txt')
	call system('del /Q /F total.txt')
	call system('total.exe')
	call system('copy total.txt standard-efficiency.txt')
	call system('transfer.exe')

	end
