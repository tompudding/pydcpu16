CC=gcc
CFLAGS=-O3

ma.bin: ma.dasm
	das -o ma.bin ma.dasm --dumpfile ma.dump
	python labels.py ma.dump > ma.labels

dcpu16: dcpu16.c 
	${CC} ${CFLAGS} -o $@ dcpu16.c 

clean:
	rm -f ma.dump ma.labels ma.bin dcpu16