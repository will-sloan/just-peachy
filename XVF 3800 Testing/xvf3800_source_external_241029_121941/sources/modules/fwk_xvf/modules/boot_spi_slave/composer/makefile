all:
	gcc -I ../loader composer.c -o composer
	gcc -I ../loader ../loader/packing_report.c -o packing_report
	./packing_report > packing_report.txt
	diff packing_report.txt ../loader
