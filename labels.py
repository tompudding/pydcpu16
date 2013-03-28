import sys
import os

#Parse the dump from das into straight labels

with open(sys.argv[1],'rb') as f:
    for line in f:
        if ';' in line:
            line = line.split(';')[0]
        if ':' not in line:
            continue
        addr = int(line.split()[0],16)
        label = line.split(':')[1].split()[0].strip()
        print '%04x %s' % (addr,label)
