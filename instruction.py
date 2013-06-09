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
    mneumonic = None
    setting   = False
    def ProcessArg(self,arg,is_a):
        allow_literals = is_a
        if not arg:
            raise InvalidArg
        arg = arg.strip()
        registers = 'abcxyzij'
        try:
            reg = registers.index(arg.lower())
            return reg
        except ValueError:
            pass
        try:
            reg = ['[%s]' % r for r in registers].index(arg.lower())
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
            if (literal < 0x1f or literal == 0xffff) and allow_literals:
                return (0x21 + literal)&0xffff
            else:
                self.words.append(literal)
                return 0x1e if deref else 0x1f
                
        except ValueError:
            #self.words.append(arg)
            pass

        #not a literal, maybe a sum
        argl = arg.lower()
        if argl == 'pop' or argl == '[sp++]':
            if is_a:
                return 0x18
            raise InvalidJimnie
        if argl == 'peek' or argl == '[sp]':
            return 0x19
        if argl.startswith('pick'):
            #the other syntax is caught below
            literal = int(argl.split('pick')[1].strip(),0)
            self.words.append(literal)
            return 0x1a
        if argl == 'push' or argl == '[--sp]':
            if not is_a:
                return 0x18
            raise InvalidJimnie
        if argl == 'sp':
            return 0x1b
        if argl == 'pc':
            return 0x1c
        if argl == 'o':
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
                if a == 'sp':
                    literal = int(b,0)
                elif b == 'sp':
                    literal = int(a,0)
                else:
                    raise InvalidArg
                self.words.append(literal)
                return 0x1a
                

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
        self.a = self.ProcessArg(a,is_a = True)&0x3f
        self.b = self.ProcessArg(b,is_a = False)&0x1f
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
        self.a = self.ProcessArg(a,is_a = True)

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
    mneumonic = 'set'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b_array[b_index] = a_array[a_index]
        dcpu.cycles += 1

class AddInstruction(SettingBasicInstruction):
    opcode    = 2
    mneumonic = 'add'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] + a
        if result > 0xffff:
            dcpu.overflow[0] = 1
        else:
            dcpu.overflow[0] = 0
        b_array[b_index] = (result&0xffff)
        dcpu.cycles += 2

class SubInstruction(SettingBasicInstruction):
    opcode    = 3
    mneumonic = 'sub'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] - a
        if result < 0:
            result += 0x10000
            dcpu.overflow[0] = 0xffff
        else:
            dcpu.overflow[0] = 0
        b_array[b_index] = result
        dcpu.cycles += 2

class MulInstruction(SettingBasicInstruction):
    opcode    = 4
    mneumonic = 'mul'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] * a
        dcpu.overflow[0] = (result>>16)&0xffff
        b_array[b_index] = result&0xffff
        dcpu.cycles += 2

class MliInstruction(SettingBasicInstruction):
    opcode    = 5
    mneumonic = 'mli'
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
    mneumonic = 'div'
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
    mneumonic = 'dvi'
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
    mneumonic = 'mod'
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
    mneumonic = 'mdi'
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
    mneumonic = 'and'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b_array[b_index] = b_array[b_index] & a_array[a_index]
        dcpu.cycles += 1

class BorInstruction(SettingBasicInstruction):
    opcode    = 11
    mneumonic = 'bor'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b_array[b_index] = b_array[b_index] | a_array[a_index]
        dcpu.cycles += 1

class XorInstruction(SettingBasicInstruction):
    opcode    = 12
    mneumonic = 'xor'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        b_array[b_index] = b_array[b_index] ^ a_array[a_index]
        dcpu.cycles += 1

class ShrInstruction(SettingBasicInstruction):
    opcode    = 13
    mneumonic = 'shr'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        b = b_array[b_index]
        result = b >> a
        dcpu.overflow[0] = ((b << 16)>>a)&0xffff
        b_array[b_index] = result&0xffff
        dcpu.cycles += 1

class AsrInstruction(SettingBasicInstruction):
    opcode    = 14
    mneumonic = 'asr'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        b = b_array[b_index]
        b = (b&0x7fff) - (b&0x8000)
        result = b >> a
        dcpu.overflow[0] = ((b << 16)>>a)&0xffff
        b_array[b_index] = result&0xffff
        dcpu.cycles += 1

class ShlInstruction(SettingBasicInstruction):
    opcode    = 15
    mneumonic = 'shl'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        b = b_array[b_index]
        result = (b << a)
        dcpu.overflow[0] = ((b << a)>>16)&0xffff
        b_array[b_index] = result&0xffff
        dcpu.cycles += 1

class IfbInstruction(BasicInstruction):
    opcode    = 16
    mneumonic = 'ifb'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = ((b_array[b_index]&a_array[a_index]) != 0)
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfcInstruction(BasicInstruction):
    opcode    = 17
    mneumonic = 'ifc'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = ((b_array[b_index]&a_array[a_index]) == 0)
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfeInstruction(BasicInstruction):
    opcode    = 18
    mneumonic = 'ife'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = (b_array[b_index] == a_array[a_index])
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfnInstruction(BasicInstruction):
    opcode    = 19
    mneumonic = 'ifn'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = (b_array[b_index] != a_array[a_index])
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfgInstruction(BasicInstruction):
    opcode    = 20
    mneumonic = 'ifg'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = (b_array[b_index] > a_array[a_index])
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfaInstruction(BasicInstruction):
    opcode    = 21
    mneumonic = 'ifa'
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
    mneumonic = 'ifl'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        dcpu.condition = (b_array[b_index] < a_array[a_index])
        dcpu.cycles += (2 + 1 if not dcpu.condition else 0)

class IfuInstruction(BasicInstruction):
    opcode    = 23
    mneumonic = 'ifu'
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
    mneumonic = 'adx'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] + a + dcpu.overflow[0]
        if result > 0xffff:
            dcpu.overflow[0] = 1
        else:
            dcpu.overflow[0] = 0
        b_array[b_index] = (result&0xffff)
        dcpu.cycles += 3

class SbxInstruction(SettingBasicInstruction):
    opcode    = 27
    mneumonic = 'sbx'
    @staticmethod
    def Execute(dcpu,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] - a - dcpu.overflow
        if result < 0:
            result += 0x10000
            dcpu.overflow[0] = 0xffff
        else:
            dcpu.overflow[0] = 0
        b_array[b_index] = result
        dcpu.cycles += 3

class StiInstruction(SettingBasicInstruction):
    opcode    = 30
    mneumonic = 'sti'
    @staticmethod
    def Execute(dcpu,*args):
        SetInstruction.Execute(dcpu,*args)
        for i in (6,7):
            dcpu.registers[i] = (dcpu.registers[i] + 1) & 0xffff
        dcpu.cycles += 2

class StdInstruction(SettingBasicInstruction):
    opcode    = 31
    mneumonic = 'std'
    @staticmethod
    def Execute(dcpu,*args):
        SetInstruction.Execute(dcpu,*args)
        for i in (6,7):
            dcpu.registers[i] = (dcpu.registers[i] + 0xffff) & 0xffff
        dcpu.cycles += 2


class JsrInstruction(NonBasicInstruction):
    opcode    = 1
    mneumonic = 'jsr'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        a = a_array[a_index]
        dcpu.sp[0] = (dcpu.sp[0] + 0xffff)&0xffff
        dcpu.memory[dcpu.sp[0]] = dcpu.pc[0]
        dcpu.pc[0] = a
        dcpu.cycles += 3

class IntInstruction(NonBasicInstruction):
    opcode    = 8
    mneumonic = 'int'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        dcpu.cycles += 4
        value = a_array[a_index]
        dcpu.Interrupt(value)

class IagInstruction(SettingNonBasicInstruction):
    opcode    = 9
    mneumonic = 'iag'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        a_array[a_index] = dcpu.interrupt_address
        dcpu.cycles += 1

class IasInstruction(NonBasicInstruction):
    opcode    = 10
    mneumonic = 'ias'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        dcpu.interrupt_address = a_array[a_index]
        dcpu.cycles += 1

class RfiInstruction(NonBasicInstruction):
    opcode    = 11
    mneumonic = 'rfi'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        dcpu.cycles += 3
        dcpu.interrupt_queing = False
        dcpu.registers[0] = dcpu.Pop()
        dcpu.pc[0] = dcpu.Pop()

class IaqInstruction(NonBasicInstruction):
    opcode    = 12
    mneumonic = 'iaq'
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
    mneumonic = 'hwn'
    @staticmethod
    def Execute(dcpu,a_array,a_index):
        a_array[a_index] = len(dcpu.hardware)&0xffff
        dcpu.cycles += 2

class HwqInstruction(NonBasicInstruction):
    opcode    = 17
    mneumonic = 'hwq'
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
    mneumonic = 'hwi'
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
    mneumonic = 'dat'
    def __init__(self,args):
        self.words = []
        for arg in args:
            if arg[0] == '"' and arg[-1] == '"':
                self.words.extend([ord(c) for c in arg[1:-1]])
            else:
                self.words.append(int(arg,0))
    def Emit(self):
        return ''.join((struct.pack('>H',w) for w in self.words))

class Reserved(Instruction):
    mneumonic = 'reserved'

instructions = {}
import inspect

for (name,cls) in globals().items():
    if inspect.isclass(cls) and issubclass(cls,Instruction) and hasattr(cls,'mneumonic'):
        if cls.mneumonic == None:
            continue
        instructions[cls.mneumonic] = cls

basic_by_opcode = {instruction.opcode:instruction for instruction in instructions.itervalues() if issubclass(instruction,BasicInstruction)}

nonbasic_by_opcode = {instruction.opcode:instruction for instruction in instructions.itervalues() if issubclass(instruction,NonBasicInstruction)}
