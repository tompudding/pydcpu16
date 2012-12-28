import sys,struct,pygame,time,array
from pygame.locals import *
from optparse import OptionParser

pygame.init()
scale_factor = 8

dirty_rects = []
font_surface = pygame.Surface((4,8),depth=8)
font_surface.set_palette(((0, 0, 0, 255),)*256)
font_surface.set_palette(((0,0,0,255),(255, 255, 255, 255)))
font_surfaces = {}

pixels = pygame.PixelArray(font_surface)

def NumToRGB(colour):
    h,r,g,b = (((colour>>i)&1) for i in (3,2,1,0))
    h = 0x55*h
    return (r*0xaa+h,g*0xaa+h,b*0xaa+h,255)

class CPU(object):
    def __init__(self,memory):
        self.registers         = [0 for i in xrange(8)]
        self.sp                = [0]
        self.pc                = [0]
        self.memory            = memory 
        self.cycles            = 0
        self.overflow          = [0]
        self.interrupt_address = [0]
        self.Instructions      = {0x01 : (self.Set,True),
                                  0x02 : (self.Add,True),
                                  0x03 : (self.Sub,True),
                                  0x04 : (self.Mul,True),
                                  0x05 : (self.Mli,True),
                                  0x06 : (self.Div,True),
                                  0x07 : (self.Dvi,True),
                                  0x08 : (self.Mod,True),
                                  0x09 : (self.Mdi,True),
                                  0x0a : (self.And,True),
                                  0x0b : (self.Bor,True),
                                  0x0c : (self.Xor,True),
                                  0x0d : (self.Shr,True),
                                  0x0e : (self.Asr,True),
                                  0x0f : (self.Shl,True),
                                  0x10 : (self.Ifb,False),
                                  0x11 : (self.Ifc,False),
                                  0x12 : (self.Ife,False),
                                  0x13 : (self.Ifn,False),
                                  0x14 : (self.Ifg,False),
                                  0x15 : (self.Ifa,False),
                                  0x16 : (self.Ifl,False),
                                  0x17 : (self.Ifu,False),
                                  0x1a : (self.Adx,True),
                                  0x1b : (self.Sbx,True),
                                  0x1e : (self.Sti,True),
                                  0x1f : (self.Std,True)}
        self.NonBasic    = {0x1 : (self.Jsr,False),}
        self.condition   = True
        self.keypointer  = 0
        self.dirty_rects = {}

    def step(self):
        instruction = self.memory[self.pc[0]]
        #self.Print()
        self.pc[0] = (self.pc[0] + 1)&0xffff
        opcode = instruction&0xf
        if opcode == 0:
            #non-basic instruction
            opcode = (instruction>>4)&0x3f
            a_array,a_index = self.process_arg((instruction>>10)&0x3f)
            try:
                instruction,sets = self.NonBasic[opcode]
            except KeyError:
                #reserved instruction
                return
            if self.condition:
                instruction(a_array,a_index)
                if a_array is self.memory and sets:
                    self.dirty(a_index)
            else:
                self.condition = True
        else:
            b,a = (instruction>>4)&0x3f,(instruction>>10)&0x3f
            a_array,a_index = self.process_arg(a)
            b_array,b_index = self.process_arg(b)
            if self.condition:
                instruction,sets = self.Instructions[opcode]
                instruction(b_array,b_index,a_array,a_index)
                if b_array is self.memory and sets:
                    self.dirty(b_index)
            else:
                #we're skipping due to an unsatisfied if
                self.condition = True

    def key_press(self,key):
        pointer_pos = 0x9010
        
        buffer_pos = 0x9000+self.keypointer
        if self.memory[buffer_pos] != 0:
            return
        self.memory[buffer_pos] = key
        self.memory[pointer_pos] = 0x9000+self.keypointer
        self.keypointer = (self.keypointer+1)&0xf
        #print [hex(c) for c in self.memory[0x9000:0x9011]]

    def dirty(self,index):
        if index >= 0x8000 and index < 0x8180:
            pos = index - 0x8000
            x = (pos&0x1f)*4
            y = (pos/32)*8
            dirty = (x*scale_factor,y*scale_factor,(x+4)*scale_factor,(y+8)*scale_factor)
            letter = self.memory[index]
            text_colour = (letter>>12)&0xf
            back_colour = (letter>>8)&0xf
            text_colour,back_colour = (NumToRGB(c) for c in (text_colour,back_colour))
            letter = letter&0x7f

            tile = font_surfaces[letter&0x7f]
            tile.set_palette((back_colour,text_colour))
            screen.blit(tile,(x*scale_factor,y*scale_factor))
            self.dirty_rects[dirty] = True
        elif index >= 0x8180 and index < 0x8280:
            #it's an update to the font
            SetPixels(pixels,self.memory[(index&0xfffe):(index&0xfffe)+2])
            font_surfaces[(index-0x8180)/2] = pygame.transform.scale(font_surface,(4*scale_factor,8*scale_factor))
            

    def Print(self):
        print ':'.join('%.4x' % c for c in self.registers)
        print 'sp:%.4x' % self.sp[0]
        print 'pc:%.4x' % self.pc[0]
        print 'EX:%.4x' % self.overflow[0]
        print 'Next instruction : %.4x' % self.memory[self.pc[0]],self.condition
        instruction = self.memory[self.pc[0]]
        opcode = instruction&0xf
        if opcode != 0:
            a,b = (instruction>>4)&0x3f,(instruction>>10)&0x3f
            print opcode,hex(a),hex(b),self.Instructions[opcode][0].__name__,self.condition
                
    def Jsr(self,a_array,a_index):
        a = a_array[a_index]
        self.sp[0] = (self.sp[0] + 0xffff)&0xffff
        self.memory[self.sp[0]] = self.pc[0]
        self.pc[0] = a
        self.cycles += 3
                
    def Set(self,b_array,b_index,a_array,a_index):
        b_array[b_index] = a_array[a_index]
        self.cycles += 1

    def Add(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] + a
        if result > 0xffff:
            self.overflow[0] = 1
        b_array[b_index] = (result&0xffff)
        self.cycles += 2

    def Sub(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] - a
        if result < 0:
            result += 0x10000
            self.overflow[0] = 0xffff
        b_array[b_index] = result
        self.cycles += 2

    def Mul(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] * a
        self.overflow[0] = (result>>16)&0xffff
        b_array[b_index] = result&0xffff
        self.cycles += 2

    def Mli(self,b_array,b_index,a_array,a_index):
        b = b_array[b_index]
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        b = (b&0x7fff) - (b&0x8000)
        result = b*a
        self.overflow[0] = (result>>16)&0xffff
        b_array[b_index] = result0xffff
        self.cycles += 2

    def Div(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        if a == 0:
            result = self.overflow[0] = 0
        else:
            b = b_array[b_index]
            result = (b / a)&0xffff
            self.overflow[0] = ((b<<16)/a)&0xffff
        b_array[b_index] = result
        self.cycles += 3

    def Dvi(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        if a == 0:
            result = self.overflow[0] = 0
        else:
            b = b_array[b_index]
            b = (b&0x7fff) - (b&0x8000)
            result = (b / a)&0xffff
            self.overflow[0] = ((b<<16)/a)&0xffff
        b_array[b_index] = result
        self.cycles += 3

    def Mod(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        if a == 0:
            result = 0
        else:
            result = b_array[b_index]%a
        b_array[b_index] = result
        self.cycles += 3

    def Mdi(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        if a == 0:
            result = 0
        else:
            b = b_array[b_index]
            b = (b&0x7fff) - (b&0x8000)
            result = b_array[b_index]%a
        b_array[b_index] = result
        self.cycles += 3

    def Shl(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        b = b_array[b_index]
        result = (b << a)
        self.overflow[0] = (result >> 16)&0xffff
        b_array[b_index] = result&0xffff
        self.cycles += 1

    def Shr(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        b = b_array[b_index]
        result = b >> a
        self.overflow[0] = (result >> 16)&0xffff
        b_array[b_index] = result&0xffff
        self.cycles += 1

    def Asr(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        b = b_array[b_index]
        b = (b&0x7fff) - (b&0x8000)
        result = b >> a
        self.overflow[0] = (result >> 16)&0xffff
        b_array[b_index] = result&0xffff
        self.cycles += 1

    def And(self,b_array,b_index,a_array,a_index):
        b_array[b_index] = b_array[b_index] & a_array[a_index]
        self.cycles += 1

    def Bor(self,b_array,b_index,a_array,a_index):
        b_array[b_index] = b_array[b_index] | a_array[a_index]
        self.cycles += 1

    def Xor(self,b_array,b_index,a_array,a_index):
        b_array[b_index] = b_array[b_index] ^ a_array[a_index]
        self.cycles += 1

    def Adx(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] + a + self.overflow
        if result > 0xffff:
            self.overflow[0] = 1
        b_array[b_index] = (result&0xffff)
        self.cycles += 3

    def Sbx(self,b_array,b_index,a_array,a_index):
        a = a_array[a_index]
        result = b_array[b_index] - a - self.overflow
        if result < 0:
            result += 0x10000
            self.overflow[0] = 0xffff
        b_array[b_index] = result
        self.cycles += 3

    def Sti(self,*args):
        self.Set(*args):
        for i in (6,7):
            self.registers[i] = (self.registers[i] + 1) & 0xffff
        self.cycles += 2
        
    def Std(self,*args):
        self.Set(*args):
        for i in (6,7):
            self.registers[i] = (self.registers[i] + 0xffff) & 0xffff
        self.cycles += 2

    def Ifb(self,b_array,b_index,a_array,a_index):
        self.condition = ((b_array[b_index]&a_array[a_index]) != 0)
        self.cycles += (2 + 1 if not self.condition else 0)

    def Ifc(self,b_array,b_index,a_array,a_index):
        self.condition = ((b_array[b_index]&a_array[a_index]) == 0)
        self.cycles += (2 + 1 if not self.condition else 0)

    def Ife(self,b_array,b_index,a_array,a_index):
        self.condition = (b_array[b_index] == a_array[a_index])
        self.cycles += (2 + 1 if not self.condition else 0)

    def Ifn(self,b_array,b_index,a_array,a_index):
        self.condition = (b_array[b_index] != a_array[a_index])
        self.cycles += (2 + 1 if not self.condition else 0)

    def Ifg(self,b_array,b_index,a_array,a_index):
        self.condition = (b_array[b_index] > a_array[a_index])
        self.cycles += (2 + 1 if not self.condition else 0)

    def Ifa(self,b_array,b_index,a_array,a_index):
        b = b_array[b_index]
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        b = (b&0x7fff) - (b&0x8000)
        self.condition = (b > a)
        self.cycles += (2 + 1 if not self.condition else 0)

    def Ifl(self,b_array,b_index,a_array,a_index):
        self.condition = (b_array[b_index] < a_array[a_index])
        self.cycles += (2 + 1 if not self.condition else 0)

    def Ifu(self,b_array,b_index,a_array,a_index):
        b = b_array[b_index]
        a = a_array[a_index]
        a = (a&0x7fff) - (a&0x8000)
        b = (b&0x7fff) - (b&0x8000)
        self.condition = (b < a)
        self.cycles += (2 + 1 if not self.condition else 0)

    def process_arg(self,x):
        if x < 8:
            return self.registers,x
        elif x < 0x10:
            return self.memory,self.registers[x-8]
        elif x < 0x18:
            word = self.memory[self.pc[0]]
            self.pc[0] = (self.pc[0] + 1)&0xffff
            self.cycles += 1
            return self.memory,word + self.registers[x-0x10]
        elif x == 0x18:
            out = self.memory,self.sp[0]
            if self.condition:
                self.sp[0] = (self.sp[0] + 1)&0xffff
            return out
        elif x == 0x19:
            return self.memory,self.sp[0]
        elif x == 0x1a:
            if self.condition:
                self.sp[0] = (self.sp[0] + 0xffff)&0xffff
            return self.memory,self.sp[0]
        elif x == 0x1b:
            return self.sp,0
        elif x == 0x1c:
            return self.pc,0
        elif x == 0x1d:
            return self.overflow,0
        elif x == 0x1e:
            word = self.memory[self.pc[0]]
            self.pc[0] = (self.pc[0] + 1)&0xffff
            self.cycles += 1
            return self.memory,word
        elif x == 0x1f:
            word = self.memory[self.pc[0]]
            self.pc[0] = (self.pc[0] + 1)&0xffff
            self.cycles += 1
            return [word],0
        else:
            return [x-0x20],0

def SetPixels(pixels,words):
    for i,word in enumerate(words):
        for j in xrange(16):
            #the next line is so obvious it doesn't need a comment
            pixels[i*2+1-(j/8)][j%8] = ((word>>j)&1)
    

def main():
    global scale_factor,screen
    parser = OptionParser(usage="usage: %prog [options] filename",
                          version="%prog 1.0")
    parser.add_option("-s", "--scale_factor",
                      action="store",
                      dest="scale_factor",
                      default=4,
                      help="scale the native size of 128x96 by this amount")
    parser.add_option("-t", "--target_frequency",
                      action="store",
                      dest="target_frequency",
                      default=100000,
                      help="Attempt to run the emulator at this frequency (default = 100000)")
    parser.add_option("-r", "--hardware_rate",
                      action="store",
                      dest="hardware_rate",
                      default=2000,
                      help="How many CPU cycles between hardware updates? Increasing this will increase maximum simulation speed at the expense of a less frequently updated video window and keyboard buffer (default = 2000)")
    parser.add_option("-f", "--show_frequency",
                      action="store_true",
                      dest="show_freq",
                      default=False,
                      help="Periodically print the actually frequency to the console (default = Off)")
    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.error("wrong number of arguments")
    
    scale_factor = int(options.scale_factor)
    screen = pygame.display.set_mode((128*scale_factor, 96*scale_factor))

    memory = array.array('H',[0 for i in xrange(0x10000)])
    pos = 0
    done = False
    with open(args[0],'rb') as f:
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

    cpu = CPU(memory)

    pygame.display.set_caption('DCPU-16 pygame emulator')
    pygame.mouse.set_visible(0)

    background = pygame.Surface(screen.get_size())
    background = background.convert()
    background.fill((0, 0, 0))
    screen.blit(background, (0, 0))

    font_data = {i:[0,0] for i in xrange(128)}

    with open('default_font.txt','rb') as f:
        for line in f:
            i,dummy,word1,word2 = line.strip().split()
            i,word1,word2 = [int(v,16) for v in i,word1,word2]
            font_data[i] = [word1,word2]
            SetPixels(pixels,font_data[i])
            font_surfaces[i] = pygame.transform.scale(font_surface,(4*scale_factor,8*scale_factor))

    clock = pygame.time.Clock()
    done = False
    count = 0
    target = int(options.target_frequency)
    poll_clock = int(options.hardware_rate)
    tick_amount = target/poll_clock

    while not done:
        cpu.step()

        if cpu.cycles > poll_clock:
            #keep to 100kHz
            clock.tick(tick_amount)
            if count > 50 and options.show_freq:
                print 'CPU frequency : %.2f kHz' % ((clock.get_fps()*poll_clock)/1000)
                count = 0
            count += 1
            for event in pygame.event.get():
                if event.type == pygame.locals.QUIT:
                    done = True
                    break

                if (event.type == KEYDOWN):
                    if event.key == K_ESCAPE:
                        done = True
                        break
                    elif event.key == K_RETURN:
                        key = 0xa
                    elif event.key == K_LEFT:
                        key = 0x25
                    elif event.key == K_RIGHT:
                        key = 0x27
                    elif event.key == K_UP:
                        key = 0x26
                    elif event.key == K_DOWN:
                        key = 0x28
                    else:
                        key = event.key
                    cpu.key_press(key)
            cpu.cycles = 0
            if len(cpu.dirty_rects) != 0:
                pygame.display.update(cpu.dirty_rects.keys())
                cpu.dirty_rects = {}


if __name__ == '__main__':
    main()
