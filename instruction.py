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
    setting   = False
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

class SettingBasicInstruction(BasicInstruction):
    setting = True

class SettingNonBasicInstruction(NonBasicInstruction):
    setting = True
        
class SetInstruction(SettingBasicInstruction):
    opcode    = 1
    pneumonic = 'set'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b_array[b_index] = a_array[a_index]
        dcpu.cycles += 1

class AddInstruction(SettingBasicInstruction):
    opcode    = 2
    pneumonic = 'add'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] + a
        if result > 0xffff:
            dcpu.overflow[0] = 1
        b_array[b_index] = (result&0xffff)
        dcpu.cycles += 2

class SubInstruction(SettingBasicInstruction):
    opcode    = 3
    pneumonic = 'sub'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] - a
        if result < 0:
            result += 0x10000
            dcpu.overflow[0] = 0xffff
        b_array[b_index] = result
        dcpu.cycles += 2

class MulInstruction(SettingBasicInstruction):
    opcode    = 4
    pneumonic = 'mul'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] * a
        dcpu.overflow[0] = (result>>16)&0xffff
        b_array[b_index] = result&0xffff
        dcpu.cycles += 2

class MliInstruction(SettingBasicInstruction):
    opcode    = 5
    pneumonic = 'mli'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b = b_array[b_index]
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        b = (b&0x7fff) - (b&0x8000)
        result = b*a
        dcpu.overflow[0] = (result>>16)&0xffff
        b_array[b_index] = result&0xffff
        dcpu.cycles += 2

class DivInstruction(SettingBasicInstruction):
    opcode    = 6
    pneumonic = 'div'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        if a == 0:
            result = dcpu.overflow[0] = 0
        else:
            b = b_array[b_index]
            result = (b / a)&0xffff
            dcpu.overflow[0] = ((b<<16)/a)&0xffff
        b_array[b_index] = result
        dcpu.cycles += 3

class DviInstruction(SettingBasicInstruction):
    opcode    = 7
    pneumonic = 'dvi'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        if a == 0:
            result = dcpu.overflow[0] = 0
        else:
            b = b_array[b_index]
            b = (b&0x7fff) - (b&0x8000)
            result = (b / a)&0xffff
            dcpu.overflow[0] = ((b<<16)/a)&0xffff
        b_array[b_index] = result
        dcpu.cycles += 3

class ModInstruction(SettingBasicInstruction):
    opcode    = 8
    pneumonic = 'mod'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        if a == 0:
            result = 0
        else:
            result = b_array[b_index]%a
        b_array[b_index] = result
        dcpu.cycles += 3

class MdiInstruction(SettingBasicInstruction):
    opcode    = 9
    pneumonic = 'mdi'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        if a == 0:
            result = 0
        else:
            b = b_array[b_index]
            b = (b&0x7fff) - (b&0x8000)
            result = b_array[b_index]%a
        b_array[b_index] = result
        dcpu.cycles += 3

class AndInstruction(SettingBasicInstruction):
    opcode    = 10
    pneumonic = 'and'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b_array[b_index] = b_array[b_index] & a_array[a_index]
        dcpu.cycles += 1

class BorInstruction(SettingBasicInstruction):
    opcode    = 11
    pneumonic = 'bor'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b_array[b_index] = b_array[b_index] | a_array[a_index]
        dcpu.cycles += 1

class XorInstruction(SettingBasicInstruction):
    opcode    = 12
    pneumonic = 'xor'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b_array[b_index] = b_array[b_index] ^ a_array[a_index]
        dcpu.cycles += 1

class ShrInstruction(SettingBasicInstruction):
    opcode    = 13
    pneumonic = 'shr'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        b = b_array[b_index]
        result = b >> a
        dcpu.overflow[0] = (result >> 16)&0xffff
        b_array[b_index] = result&0xffff
        dcpu.cycles += 1

class AsrInstruction(SettingBasicInstruction):
    opcode    = 14
    pneumonic = 'asr'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        b = b_array[b_index]
        b = (b&0x7fff) - (b&0x8000)
        result = b >> a
        dcpu.overflow[0] = (result >> 16)&0xffff
        b_array[b_index] = result&0xffff
        dcpu.cycles += 1

class ShlInstruction(SettingBasicInstruction):
    opcode    = 15
    pneumonic = 'shl'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        b = b_array[b_index]
        result = (b << a)
        dcpu.overflow[0] = (result >> 16)&0xffff
        b_array[b_index] = result&0xffff
        dcpu.cycles += 1

class IfbInstruction(BasicInstruction):
    opcode    = 16
    pneumonic = 'ifb'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = ((b_array[b_index]&a_array[a_index]) != 0)
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfcInstruction(BasicInstruction):
    opcode    = 17
    pneumonic = 'ifc'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = ((b_array[b_index]&a_array[a_index]) == 0)
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfeInstruction(BasicInstruction):
    opcode    = 18
    pneumonic = 'ife'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = (b_array[b_index] == a_array[a_index])
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfnInstruction(BasicInstruction):
    opcode    = 19
    pneumonic = 'ifn'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = (b_array[b_index] != a_array[a_index])
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfgInstruction(BasicInstruction):
    opcode    = 20
    pneumonic = 'ifg'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = (b_array[b_index] > a_array[a_index])
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfaInstruction(BasicInstruction):
    opcode    = 21
    pneumonic = 'ifa'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b = b_array[b_index]
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        b = (b&0x7fff) - (b&0x8000)
        dcpu.condition = (b > a)
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IflInstruction(BasicInstruction):
    opcode    = 22
    pneumonic = 'ifl'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = (b_array[b_index] < a_array[a_index])
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfuInstruction(BasicInstruction):
    opcode    = 23
    pneumonic = 'ifu'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b = b_array[b_index]
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        b = (b&0x7fff) - (b&0x8000)
        dcpu.condition = (b < a)
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class AdxInstruction(SettingBasicInstruction):
    opcode    = 26
    pneumonic = 'adx'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] + a + dcpu.overflow
        if result > 0xffff:
            dcpu.overflow[0] = 1
        b_array[b_index] = (result&0xffff)
        dcpu.cycles += 3

class SbxInstruction(SettingBasicInstruction):
    opcode    = 27
    pneumonic = 'sbx'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] - a - dcpu.overflow
        if result < 0:
            result += 0x10000
            dcpu.overflow[0] = 0xffff
        b_array[b_index] = result
        dcpu.cycles += 3

class StiInstruction(SettingBasicInstruction):
    opcode    = 30
    pneumonic = 'sti'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.Set(*args)
        for i in (6,7):
            dcpu.registers[i] = (dcpu.registers[i] + 1) & 0xffff
        dcpu.cycles += 2

class StdInstruction(SettingBasicInstruction):
    opcode    = 31
    pneumonic = 'std'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.Set(*args)
        for i in (6,7):
            dcpu.registers[i] = (dcpu.registers[i] + 0xffff) & 0xffff
        dcpu.cycles += 2


class JsrInstruction(NonBasicInstruction):
    opcode    = 1
    pneumonic = 'jsr'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        a = a_array[a_index]
        dcpu.sp[0] = (dcpu.sp[0] + 0xffff)&0xffff
        dcpu.memory[dcpu.sp[0]] = dcpu.pc[0]
        dcpu.pc[0] = a
        dcpu.cycles += 3

class IntInstruction(NonBasicInstruction):
    opcode    = 8
    pneumonic = 'int'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        dcpu.cycles += 4
        value = a_array[a_index]
        dcpu.Interrupt(value)

class IagInstruction(SettingNonBasicInstruction):
    opcode    = 9
    pneumonic = 'iag'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        a_array[a_index] = dcpu.interrupt_address
        dcpu.cycles += 1

class IasInstruction(NonBasicInstruction):
    opcode    = 10
    pneumonic = 'ias'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        dcpu.interrupt_address = a_array[a_index]
        dcpu.cycles += 1

class RfiInstruction(NonBasicInstruction):
    opcode    = 11
    pneumonic = 'rfi'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        dcpu.cycles += 3
        dcpu.interrupt_queing = False
        dcpu.registers[0] = dcpu.Pop()
        dcpu.pc[0] = dcpu.Pop()

class IaqInstruction(NonBasicInstruction):
    opcode    = 12
    pneumonic = 'iaq'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        dcpu.cycles += 2
        value = a_array[a_index]
        if value != 0:
            dcpu.interrupt_queing = True
        else:
            dcpu.interrupt_queing = False

class HwnInstruction(SettingNonBasicInstruction):
    opcode    = 16
    pneumonic = 'hwn'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        a_array[a_index] = len(dcpu.hardware)&0xffff
        dcpu.cycles += 2

class HwqInstruction(NonBasicInstruction):
    opcode    = 17
    pneumonic = 'hwq'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        i = a_array[a_index]
        dcpu.cycles += 4
        try:
            hw = dcpu.hardware[i]
        except IndexError:
            return
        dcpu.registers[0] = hw.id&0xffff
        dcpu.registers[1] = (hw.id>>16)&0xffff
        dcpu.registers[2] = hw.version&0xffff
        dcpu.registers[3] = hw.manufacturer&0xffff
        dcpu.registers[4] = (hw.manufacturer>>16)&0xffff

class HwiInstruction(NonBasicInstruction):
    opcode    = 18
    pneumonic = 'hwi'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        i = a_array[a_index]
        dcpu.cycles += 4
        try:
            hw = dcpu.hardware[i]
        except IndexError:
            return
        dcpu.cycles += hw.Interrupt()

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


instructions = {}
import inspect

for (name,cls) in globals().items():
    if inspect.isclass(cls) and issubclass(cls,Instruction) and hasattr(cls,'pneumonic'):
        if cls.pneumonic == None:
            continue
        instructions[cls.pneumonic] = cls

basic_by_opcode = {instruction.opcode:instruction for instruction in instructions.itervalues() if issubclass(instruction,BasicInstruction)}

nonbasic_by_opcode = {instruction.opcode:instruction for instruction in instructions.itervalues() if issubclass(instruction,NonBasicInstruction)}
