import sys,struct,pygame,time,array
from pygame.locals import *
from optparse import OptionParser

import instruction

registers = 'ABCXYZIJ'

def ToString(x,pos,memory,in_a):
    if x < 8:
        return registers[x],pos
    elif x < 0x10:
        return '[' + registers[x-8] + ']',pos
    elif x < 0x18:
        value = memory[pos]
        pos += 1
        return '[%s + 0x%x]' % (registers[x-0x10],value),pos
    elif x == 0x18:
        if in_a:
            return 'POP',pos
        else:
            return 'PUSH',pos
    elif x == 0x19:
        return 'PEEK',pos
    elif x == 0x1a:
        value = memory[pos]
        pos += 1
        return 'PICK %d' % value,pos
    elif x == 0x1b:
        return 'SP',pos
    elif x == 0x1c:
        return 'PC',pos
    elif x == 0x1d:
        return 'EX',pos
    elif x == 0x1e:
        value = memory[pos]
        pos += 1
        return ('[0x%x]' % value),pos
    elif x == 0x1f:
        value = memory[pos]
        pos += 1
        return ('0x%x' % value),pos
    elif x <= 0x3f:
        value = (x - 0x21 + 0x10000)&0xffff
        return ('0x%x' % value),pos


def Disassemble(memory,start,end):
    pos = start

    while pos < end:
        try:
            startbytes = pos
            ins = memory[pos]
            pos += 1
            opcode = ins&0x1f
            if opcode == 0:
                #non-basic instruction
                opcode = (ins>>5)&0x1f
                a = (ins>>10)&0x3f
                try:
                    ins = instruction.nonbasic_by_opcode[opcode]
                except KeyError:
                    #reserved instruction
                    ins = instruction.Reserved

                args,pos = ToString(a,pos,memory,in_a = True)

            else:
                b,a = (ins>>5)&0x1f,(ins>>10)&0x3f
                string_a,pos = ToString(a,pos,memory,in_a = True)
                string_b,pos = ToString(b,pos,memory,in_a = False)
                args = string_b + ' ' + string_a

                try:
                    ins = instruction.basic_by_opcode[opcode]
                except KeyError:
                    ins = instruction.Reserved
        except IndexError:
            return

        bytes = ' '.join('%04x' % memory[i] for i in xrange(startbytes,pos))
        yield (startbytes,bytes,ins.mneumonic,args)
    

if __name__ == '__main__':
    memory = array.array('H',[0 for i in xrange(0x10000)])
    pos = 0
    done = False
    with open(sys.argv[1],'rb') as f:
        while not done:
            datum = f.read(2)
            if len(datum) == 0:
                done = True
            if len(datum) != 2:
                datum = datum + '\x00'*(2-len(datum))
            memory[pos] = struct.unpack('>H',datum)[0]
            pos += 1
            if pos >= len(memory):
                done = True

    total = pos
    for startbytes,bytes,mneumonic,args in Disassemble(memory[:pos]):
        print '%04x : %9s : %s %s' % (startbytes,bytes,mneumonic,args)
