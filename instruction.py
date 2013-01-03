import sys,struct

class NotImplemented(Exception):
    pass

class UnknownLabel(Exception):
    def __init__(self,label = None):
        self.label = label

def CheckLabel(x,labels):
    if isinstance(x,str):
        try:
            out = labels[x]
        except KeyError:
            raise UnknownLabel(x)
        return out
    else:
        return x

class Instruction(object):
    opcode    = None
    pneumonic = None
    def ProcessArg(self,arg,allow_literals):
        if not arg:
            raise InvalidArg
        arg = arg.strip()
        registers = 'abcxyzij'
        try:
            reg = registers.index(arg)
            return reg
        except ValueError:
            pass
        try:
            reg = ['[%s]' % r for r in registers].index(arg)
            return reg + 8
        except ValueError:
            pass
        #stuff here for the various expressions
        #...
        deref = False
        if arg[0] == '[' and arg[-1] == ']':
            deref = True
            arg = arg[1:-1].strip()
        else:
            deref = False
    
        try:
            literal = int(arg,0)
            if literal > 0x1f and allow_literals:
            #if 1:
                self.words.append(literal)
                return 0x1e if deref else 0x1f
            else:
                return 0x20 + literal
        except ValueError:
            #self.words.append(arg)
            pass

        #not a literal, maybe a sum
        if arg == 'pop' or arg == '[sp++]':
            return 0x18
        if arg == 'peek' or arg == '[sp]':
            return 0x19
        if arg == 'push' or arg == '[--sp]':
            return 0x1a
        if arg == 'sp':
            return 0x1b
        if arg == 'pc':
            return 0x1c
        if arg == 'o':
            return 0x1d
        if '+' in arg:
            try:
                a,b = [v.strip() for v in arg.split('+')]
            except ValueError:
                #not a well formed sum
                raise InvalidArg
            if a in registers:
                reg,literal = a,b
            elif b in registers:
                reg,literal = b,a
            else:
                raise InvalidArg

            reg = registers.index(reg)
            try:
                literal = int(literal,0)
            except ValueError:
                #probably a label, fill it in later
                pass

            self.words.append(literal)
            return 0x10 + reg

        #it must be a label
        #if arg in labels:
        #    return labels[arg]
        #We have to assume it's a reference to a label that's not defined yet
        self.words.append(arg)
        return 0x1e if deref else 0x1f

    def __len__(self):
        return len(self.words)

    def FillLabels(self,labels):
        self.words = [CheckLabel(w,labels) for w in self.words]


class BasicInstruction(Instruction):
    def __init__(self,args):
        b,a = args
        self.words = [self.opcode]
        self.b = self.ProcessArg(b,allow_literals = False)&0x1f
        self.a = self.ProcessArg(a,allow_literals = True)&0x3f
        print 'args',self.b,self.a,self.words

    def Emit(self):
        self.words[0] |= ((self.b<<5) | (self.a<<10))
        return ''.join((struct.pack('>H',w) for w in self.words))

    def FillLabels(self,labels):
        super(BasicInstruction,self).FillLabels(labels)
        self.b = CheckLabel(self.b,labels)
        self.a = CheckLabel(self.a,labels)


class NonBasicInstruction(Instruction):
    def __init__(self,args):
        a = args[0]
        self.words = [self.opcode << 5]
        self.a = self.ProcessArg(a,allow_literals = True)

    def Emit(self):
        self.words[0] |= (self.a<<10)
        return ''.join((struct.pack('>H',w) for w in self.words))

    def FillLabels(self,labels):
        super(NonBasicInstruction,self).FillLabels(labels)
        self.a = CheckLabel(self.a,labels)

        
class SetInstruction(BasicInstruction):
    opcode    = 1
    pneumonic = 'set'

class AddInstruction(BasicInstruction):
    opcode    = 2
    pneumonic = 'add'

class SubInstruction(BasicInstruction):
    opcode    = 3
    pneumonic = 'sub'

class MulInstruction(BasicInstruction):
    opcode    = 4
    pneumonic = 'mul'

class MliInstruction(BasicInstruction):
    opcode    = 5
    pneumonic = 'mli'

class DivInstruction(BasicInstruction):
    opcode    = 6
    pneumonic = 'div'

class DviInstruction(BasicInstruction):
    opcode    = 7
    pneumonic = 'dvi'

class ModInstruction(BasicInstruction):
    opcode    = 8
    pneumonic = 'mod'

class MdiInstruction(BasicInstruction):
    opcode    = 9
    pneumonic = 'mdi'

class AndInstruction(BasicInstruction):
    opcode    = 10
    pneumonic = 'and'

class BorInstruction(BasicInstruction):
    opcode    = 11
    pneumonic = 'bor'

class XorInstruction(BasicInstruction):
    opcode    = 12
    pneumonic = 'xor'

class ShrInstruction(BasicInstruction):
    opcode    = 13
    pneumonic = 'shr'

class AsrInstruction(BasicInstruction):
    opcode    = 14
    pneumonic = 'asr'

class ShlInstruction(BasicInstruction):
    opcode    = 15
    pneumonic = 'shl'

class IfbInstruction(BasicInstruction):
    opcode    = 16
    pneumonic = 'ifb'

class IfcInstruction(BasicInstruction):
    opcode    = 17
    pneumonic = 'ifc'

class IfeInstruction(BasicInstruction):
    opcode    = 18
    pneumonic = 'ife'

class IfnInstruction(BasicInstruction):
    opcode    = 19
    pneumonic = 'ifn'

class IfgInstruction(BasicInstruction):
    opcode    = 20
    pneumonic = 'ifg'

class IfaInstruction(BasicInstruction):
    opcode    = 21
    pneumonic = 'ifa'

class IflInstruction(BasicInstruction):
    opcode    = 22
    pneumonic = 'ifl'

class IfuInstruction(BasicInstruction):
    opcode    = 23
    pneumonic = 'ifu'

class AdxInstruction(BasicInstruction):
    opcode    = 26
    pneumonic = 'adx'

class SbxInstruction(BasicInstruction):
    opcode    = 27
    pneumonic = 'sbx'

class StiInstruction(BasicInstruction):
    opcode    = 30
    pneumonic = 'sti'

class StiInstruction(BasicInstruction):
    opcode    = 31
    pneumonic = 'sti'


class JsrInstruction(NonBasicInstruction):
    opcode    = 1
    pneumonic = 'jsr'

class IntInstruction(NonBasicInstruction):
    opcode    = 8
    pneumonic = 'int'

class IagInstruction(NonBasicInstruction):
    opcode    = 9
    pneumonic = 'iag'

class IasInstruction(NonBasicInstruction):
    opcode    = 10
    pneumonic = 'ias'

class RfiInstruction(NonBasicInstruction):
    opcode    = 11
    pneumonic = 'rfi'

class IaqInstruction(NonBasicInstruction):
    opcode    = 12
    pneumonic = 'iaq'

class HwnInstruction(NonBasicInstruction):
    opcode    = 16
    pneumonic = 'hwn'

class HwqInstruction(NonBasicInstruction):
    opcode    = 17
    pneumonic = 'hwq'

class HwiInstruction(NonBasicInstruction):
    opcode    = 18
    pneumonic = 'hwi'

class Data(Instruction):
    pneumonic = 'dat'
    def __init__(self,args):
        self.words = []
        for arg in args:
            if arg[0] == '"' and arg[-1] == '"':
                self.words.extend([ord(c) for c in arg[1:-1]])
            else:
                self.words.append(int(arg,0))
    def Emit(self):
        return ''.join((struct.pack('>H',w) for w in self.words))
