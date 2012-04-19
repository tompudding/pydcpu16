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
    def ProcessArg(self,arg):
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
            if literal > 0x1f:
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
    def __init__(self,opcode,args):
        a,b = args
        self.opcode = opcode
        self.words = [self.opcode]
        self.a = self.ProcessArg(a)
        self.b = self.ProcessArg(b)
        print 'args',self.a,self.b,self.words

    def Emit(self):
        self.words[0] |= ((self.a<<4) | (self.b<<10))
        return ''.join((struct.pack('>H',w) for w in self.words))

    def FillLabels(self,labels):
        super(BasicInstruction,self).FillLabels(labels)
        self.a = CheckLabel(self.a,labels)
        self.b = CheckLabel(self.b,labels)


class NonBasicInstruction(Instruction):
    def __init__(self,opcode,args):
        a = args[0]
        self.opcode = opcode
        self.words = [self.opcode << 4]
        self.a = self.ProcessArg(a)

    def Emit(self):
        self.words[0] |= (self.a<<10)
        return ''.join((struct.pack('>H',w) for w in self.words))

    def FillLabels(self,labels):
        super(NonBasicInstruction,self).FillLabels(labels)
        self.a = CheckLabel(self.a,labels)

        
class SetInstruction(BasicInstruction):
    def __init__(self,args):
        super(SetInstruction,self).__init__(1,args)
class AddInstruction(BasicInstruction):
    def __init__(self,args):
        super(AddInstruction,self).__init__(2,args)
class SubInstruction(BasicInstruction):
    def __init__(self,args):
        super(SubInstruction,self).__init__(3,args)
class MulInstruction(BasicInstruction):
    def __init__(self,args):
        super(MulInstruction,self).__init__(4,args)
class DivInstruction(BasicInstruction):
    def __init__(self,args):
        super(DivInstruction,self).__init__(5,args)
class ModInstruction(BasicInstruction):
    def __init__(self,args):
        super(ModInstruction,self).__init__(6,args)
class ShlInstruction(BasicInstruction):
    def __init__(self,args):
        super(ShlInstruction,self).__init__(7,args)
class ShrInstruction(BasicInstruction):
    def __init__(self,args):
        super(ShrInstruction,self).__init__(8,args)
class AndInstruction(BasicInstruction):
    def __init__(self,args):
        super(AndInstruction,self).__init__(9,args)
class BorInstruction(BasicInstruction):
    def __init__(self,args):
        super(BorInstruction,self).__init__(10,args)
class XorInstruction(BasicInstruction):
    def __init__(self,args):
        super(XorInstruction,self).__init__(11,args)
class IfeInstruction(BasicInstruction):
    def __init__(self,args):
        super(IfeInstruction,self).__init__(12,args)
class IfnInstruction(BasicInstruction):
    def __init__(self,args):
        super(IfnInstruction,self).__init__(13,args)
class IfgInstruction(BasicInstruction):
    def __init__(self,args):
        super(IfgInstruction,self).__init__(14,args)
class IfbInstruction(BasicInstruction):
    def __init__(self,args):
        super(IfbInstruction,self).__init__(15,args)

class JsrInstruction(NonBasicInstruction):
    def __init__(self,args):
        super(JsrInstruction,self).__init__(1,args)

class Data(Instruction):
    def __init__(self,args):
        self.words = []
        for arg in args:
            if arg[0] == '"' and arg[-1] == '"':
                self.words.extend([ord(c) for c in arg[1:-1]])
            else:
                self.words.append(int(arg,0))
    def Emit(self):
        return ''.join((struct.pack('>H',w) for w in self.words))