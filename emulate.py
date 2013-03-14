import sys
import struct
import pygame
import time
import array
import random
import disassemble
from pygame.locals import *
from optparse import OptionParser

import hardware
import instruction

pygame.init()

def NumToRGB(colour):
    h,r,g,b = (((colour>>i)&1) for i in (3,2,1,0))
    h = 0x55*h
    return (r*0xaa+h,g*0xaa+h,b*0xaa+h,255)

class StdOutWrapper:
    text = []
    def write(self,txt):
        self.text.append(txt)
        if len(self.text) > 500:
            self.text = self.text[:500]
    def get_text(self):
        return ''.join(self.text)


class Debugger(object):
    def __init__(self,cpu):
        self.cpu              = cpu
        self.breakpoints      = set([0])
        self.selected         = 0
        self.stdscr           = cpu.stdscr

        self.h,self.w   = self.stdscr.getmaxyx()
        self.left_window  = curses.newwin(self.h,self.w/2,0,0)
        self.right_window = curses.newwin(self.h,self.w/2,0,self.w/2)
        self.left_window.keypad(1)
        self.right_window.keypad(1)
        self.pane_w       = self.w/2
        self.stopped      = False
        with open('/usr/share/dict/words','rb') as f:
            self.words = [w.strip() for w in f.readlines()]

    def centre_view(self,pos):
        #Set our pos such that the given pos is as close to the centre as possible
        for i in xrange(3):
            correct = None
            self.disassembly = []
            start = max(pos-self.h*3,0) + i
            end = min(pos + self.h*3,len(self.cpu.memory)) + i
            for index,data in enumerate(disassemble.Disassemble(self.cpu.memory,start,end)):
                if data[0] == pos:
                    correct = index
                self.disassembly.append( data )
            if correct != None:
                break
        else:
            #Shouldn't be possible
            raise MonkeyError
        start = max(correct-self.h/2,0)
        self.disassembly = [(p,'%3s%s%04x : %9s : %s %s' % ('==>' if p == self.cpu.pc[0] else '','*' if p in self.breakpoints else ' ',p,b,ins,args)) for (p,b,ins,args) in self.disassembly[start:start+self.h]]

    def PrintState(self):
        for i,(regname,value) in enumerate( (('A',self.cpu.registers[0]),
                                             ('B',self.cpu.registers[1]),
                                             ('C',self.cpu.registers[2]),
                                             ('X',self.cpu.registers[3]),
                                             ('Y',self.cpu.registers[4]),
                                             ('Z',self.cpu.registers[5]),
                                             ('I',self.cpu.registers[6]),
                                             ('J',self.cpu.registers[7]),
                                             ('SP',self.cpu.sp[0]),
                                             ('PC',self.cpu.pc[0]),
                                             ('EX',self.cpu.overflow[0])) ):
            self.right_window.addstr(i,0,'%2s : %04x' % (regname,value))

    def Executing(self,pc):
        if not self.stopped:
            if pc in self.breakpoints:
                self.stopped = True
                self.centre_view(pc)
                self.selected = pc
            else:
                return
        else:
            self.centre_view(self.selected)

        #We're stopped, so display and wait for a keypress
        while True:
            #disassembly = disassemble.Disassemble(cpu.memory)
            self.left_window.clear()
            selected_pos = None
            for i,(pos,line) in enumerate(self.disassembly):
                if pos == self.selected:
                    selected_pos = i
                    self.left_window.addstr(i,0,line,curses.A_REVERSE)
                else:
                    print i
                    self.left_window.addstr(i,0,line)
            self.left_window.refresh()
            self.right_window.clear()
            self.PrintState()
            self.right_window.refresh()
            ch = self.left_window.getch()
            print ch,curses.KEY_DOWN
            if ch == curses.KEY_DOWN:
                try:
                    self.selected = self.disassembly[selected_pos+1][0]
                    self.centre_view(self.selected)
                except IndexError:
                    pass
            elif ch == curses.KEY_UP:
                if selected_pos > 0:
                    self.selected = self.disassembly[selected_pos-1][0]
                    self.centre_view(self.selected)
            elif ch == ord(' '):
                if self.selected in self.breakpoints:
                    self.breakpoints.remove(self.selected)
                else:
                    self.breakpoints.add(self.selected)
                self.centre_view(self.selected)
            elif ch == ord('c'):
                self.stopped = False
                break
            elif ch == ord('s'):
                break
        

class CPU(object):
    def __init__(self,stdscr,memory,hw):
        self.registers         = [0 for i in xrange(8)]
        self.sp                = [0]
        self.pc                = [0]
        self.memory            = memory 
        self.cycles            = 0
        self.overflow          = [0]
        self.hardware          = []
        self.interrupt_address = [0]
        self.interrupt_queue   = []
        self.interrupt_queing  = False
        self.mmap_regions      = {}
        self.mmap_memory       = {}
        self.basic             = instruction.basic_by_opcode
        self.nonbasic          = instruction.nonbasic_by_opcode

        self.condition   = True
        self.keypointer  = 0
        self.dirty_rects = {}
        self.stdscr      = stdscr
        self.debug       = Debugger(self)
        for device in hw:
            new_device = device(self)
            if device is hardware.Lem1802:
                self.screen = new_device
            elif device is hardware.Keyboard:
                self.keyboard = new_device
            elif device is hardware.M35fd:
                self.floppy = new_device
            elif device is hardware.Clock:
                self.clock  = new_device
            self.hardware.append(new_device)

    def step(self):
        if self.interrupt_queue and not self.interrupt_queing:
            message = self.interrupt.queue.pop(0)
            self.Interrupt(message)
        instruction = self.memory[self.pc[0]]
        if self.debug:
            self.debug.Executing(self.pc[0])
        self.pc[0] = (self.pc[0] + 1)&0xffff
        opcode = instruction&0x1f
        if opcode == 0:
            #non-basic instruction
            opcode = (instruction>>5)&0x1f
            a_array,a_index = self.process_arg((instruction>>10)&0x3f,in_a = True)
            try:
                instruction = self.nonbasic[opcode]
            except KeyError:
                #reserved instruction
                return
            if self.condition:
                instruction.Execute(self,a_array,a_index)
                if a_array is self.memory and instruction.setting:
                    self.dirty(a_index)
            else:
                self.condition = True
        else:
            b,a = (instruction>>5)&0x1f,(instruction>>10)&0x3f
            a_array,a_index = self.process_arg(a,in_a = True)
            b_array,b_index = self.process_arg(b,in_a = False)
            #print opcode,hex(self.pc[0]),self.Instructions[opcode]
            #self.Print()
            instruction = self.basic[opcode]
            if self.condition:
                instruction.Execute(self,b_array,b_index,a_array,a_index)
                if b_array is self.memory and instruction.setting:
                    self.dirty(b_index)
            else:
                #we're skipping due to an unsatisfied if
                #continue skipping if the instruction we just skipped is conditional
                if opcode < 0x10 or opcode > 0x17:
                    self.condition = True

    def Mmap(self,hw,address,size,kind):
        self.mmap_regions[address] = (size,kind)
        for i in xrange(size):
            self.mmap_memory[(address + i)&0xffff] = (hw,i,kind)

    def Munmap(self,address):
        try:
            data = self.mmap_regions[address]
        except KeyError:
            return
        size = data[0]
        for i in xrange(size):
            del self.mmap_memory[address + i]

    def dirty(self,index):
        try:
            hw,offset,kind = self.mmap_memory[index]
        except KeyError:
            return
        hw.mmap_write(offset,kind)
           

    def Print(self):
        print ':'.join('%.4x' % c for c in self.registers)
        print 'sp:%.4x' % self.sp[0]
        print 'pc:%.4x' % self.pc[0]
        print 'EX:%.4x' % self.overflow[0]
        print 'Next instruction : %.4x' % self.memory[self.pc[0]],self.condition
        instruction = self.memory[self.pc[0]]
        opcode = instruction&0x1f
        if opcode != 0:
            b,a = (instruction>>5)&0x1f,(instruction>>10)&0x3f
            if opcode == 0:
                ins = self.nonbasic[opcode]
            else:
                ins = self.basic[opcode]
            print opcode,hex(b),hex(a),ins.pneumonic,self.condition

    def Interrupt(self,value):
        #I haven't tested this yet
        #while not self.condition:
        #    self.step()
            
        if self.interrupt_queing:
            self.interrupt_queue.append(value)
            if len(self.interrupt_queue) > 256:
                self.interrupt_queue.Ignite()
            return
        if self.interrupt_address == 0:
            return
        self.interrupt_queing = True
        self.Push(self.pc[0])
        self.Push(self.registers[0])
        self.registers[0] = value
        self.pc[0] = self.interrupt_address

    def Push(self,value):
        self.sp[0] = (self.sp[0] + 0xffff)&0xffff
        self.memory[self.sp[0]] = value

    def Pop(self):
        out = self.memory[self.sp[0]]
        self.sp[0] = (self.sp[0] + 1)&0xffff
        return out

    def process_arg(self,x,in_a):
        if x < 8:
            return self.registers,x
        elif x < 0x10:
            return self.memory,self.registers[x-8]
        elif x < 0x18:
            word = self.memory[self.pc[0]]
            self.pc[0] = (self.pc[0] + 1)&0xffff
            self.cycles += 1
            return self.memory,(word + self.registers[x-0x10])&0xffff
        elif x == 0x18:
            if not in_a:
                if self.condition:
                    self.sp[0] = (self.sp[0] + 0xffff)&0xffff
                return self.memory,self.sp[0]
            else:
                out = self.memory,self.sp[0]
                if self.condition:
                    self.sp[0] = (self.sp[0] + 1)&0xffff
                return out
        elif x == 0x19:
            return self.memory,self.sp[0]
        elif x == 0x1a:
            word = self.memory[self.pc[0]]
            self.pc[0] = (self.pc[0] + 1)&0xffff
            self.cycles += 1
            return self.memory,(self.sp[0] + word)&0xffff
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
            return [(x-0x21+0x10000)&0xffff],0

keyMappings = { K_BACKSPACE : 0x10,
                K_RETURN    : 0x11,
                K_INSERT    : 0x12,
                K_DELETE    : 0x13,
                K_UP        : 0x80,
                K_DOWN      : 0x81,
                K_LEFT      : 0x82,
                K_RIGHT     : 0x83,
                K_LSHIFT    : 0x90,
                K_RSHIFT    : 0x90,
                K_LCTRL     : 0x91,
                K_RCTRL     : 0x91}

def main(stdscr):
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

    curses.use_default_colors()
    #curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)

    if len(args) != 1:
        parser.error("wrong number of arguments")
    
    hardware.lem1802.scale_factor = int(options.scale_factor)
    print hardware.lem1802.scale_factor

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

    pygame.display.set_caption('DCPU-16 pygame emulator')
    pygame.mouse.set_visible(0)

    cpu = CPU(stdscr,memory,(hardware.Keyboard,hardware.M35fd,hardware.Lem1802,hardware.Clock))

    background = pygame.Surface(cpu.screen.screen.get_size())
    background = background.convert()
    background.fill((0, 0, 0))
    cpu.screen.screen.blit(background, (0, 0))

    clock = pygame.time.Clock()
    done = False
    count = 0
    target = int(options.target_frequency)
    poll_clock = int(options.hardware_rate)
    tick_amount = target/poll_clock
    last_cycles = 0

    while not done:
        cpu.step()

        if (cpu.cycles - last_cycles) > poll_clock:
            #keep to 100kHz
            clock.tick(tick_amount)
            if count > 50 and options.show_freq:
                print 'CPU frequency : %.2f kHz' % ((clock.get_fps()*poll_clock)/1000)
                count = 0
            count += 1
            cpu.clock.Update()
            for event in pygame.event.get():
                if event.type == pygame.locals.QUIT:
                    done = True
                    break

                if (event.type in (KEYDOWN,KEYUP)):
                    if event.key == K_ESCAPE:
                        done = True
                        break
                    try:
                        key = keyMappings[event.key]
                        if event.type == KEYDOWN:
                            cpu.keyboard.key_down(key)
                        else:
                            cpu.keyboard.key_up(key)
                    except KeyError:
                        try:
                            k = ord(event.unicode)
                            if k >= 0x20 and k <= 0x7f:
                                cpu.keyboard.key_typed(k)
                        except:
                            pass

            
            last_cycles = cpu.cycles
            cpu.screen.Update()


if __name__ == '__main__':
    import curses
    mystdout = StdOutWrapper()
    sys.stdout = mystdout
    sys.stderr = mystdout
    try:
        curses.wrapper(main)
    finally:
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        sys.stdout.write(mystdout.get_text())
        
