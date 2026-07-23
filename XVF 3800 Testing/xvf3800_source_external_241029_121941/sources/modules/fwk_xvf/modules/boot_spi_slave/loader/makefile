all:
	xcc -target=XCORE-AI-EXPLORER -c -Os network_setup.c
	xcc -target=XCORE-AI-EXPLORER -c -Os remote_transfer.xc
	xcc -target=XCORE-AI-EXPLORER -c -Os ready_signal.xc
	xcc -target=XCORE-AI-EXPLORER -c spi_slave.S
	xmosar cru libloader.a network_setup.o remote_transfer.o spi_slave.o ready_signal.o
	-rm -f network_setup.o remote_transfer.o spi_slave.o ready_signal.o
	xcc -target=XCORE-AI-EXPLORER -c ${TEST} crt.S
	xcc -target=XCORE-AI-EXPLORER -c -Os main.c
	xcc -target=XCORE-AI-EXPLORER -L . -Os -nostartfiles -o loader.xe crt.o main.o -lloader
	-rm -f crt.o main.o
	xobjdump -D loader.xe > objdump
	xobjdump --size loader.xe
	xobjdump --strip --split loader.xe >/dev/null
	xcc -target=XCORE-AI-EXPLORER packing_report.c -o packing_report.xe
	xsim packing_report.xe > packing_report.txt
	cp image_n0c0_2.bin loader.bin
	-rm -f loader.xb image_*.bin platform_def.xn xscope.xscope program_info.txt
