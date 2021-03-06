import curses
import disassemble
import time

class Labels(object):
    def __init__(self,fname):
        self.addr_to_label = {}
        self.label_to_addr = {}
        if fname == None:
            return
        try:
            with open(fname,'rb') as f:
                for line in f:
                    addr,label = line.split()
                    addr = int(addr,16)
                    self.addr_to_label[addr]  = label
                    self.label_to_addr[label] = addr
        except IOError:
            pass

class WindowControl:
    SAME    = 1
    RESUME  = 2
    NEXT    = 3
    RESTART = 4


class View(object):
    def __init__(self,h,w,y,x):
        self.width  = w
        self.height = h
        self.startx = x
        self.starty = y
        self.window = curses.newwin(self.height,self.width,self.starty,self.startx)
        self.window.keypad(1)

    def Centre(self,pos):
        pass

    def Select(self,pos):
        pass

    def TakeInput(self):
        return WindowControl.SAME

class Debug(View):
    label_width = 14
    def __init__(self,debugger,h,w,y,x):
        super(Debug,self).__init__(h,w,y,x)
        self.selected = 0
        self.debugger = debugger

    def Centre(self,pos = None):
        if pos == None:
            pos = self.selected
        #Set our pos such that the given pos is as close to the centre as possible
        for i in xrange(3):
            correct = None
            self.disassembly = []
            start = max(pos-self.height*3,0) + i
            end = min(pos + self.height*3,len(self.debugger.cpu.memory)) + i
            for index,data in enumerate(disassemble.Disassemble(self.debugger.cpu.memory,start,end)):
                if data[0] == pos:
                    correct = index
                self.disassembly.append( data )
            if correct != None:
                break
        else:
            #Shouldn't be possible
            raise MonkeyError
        start = max(correct-self.height/2,0)
        dis = []
        for (p,b,ins,args) in self.disassembly[start:start+self.height-2]:
            try:
                label = self.debugger.labels.addr_to_label[p]
            except KeyError:
                label = ''
            arrow = '==>' if p == self.debugger.cpu.pc[0] else ''
            bpt   = '*' if p in self.debugger.breakpoints else ' '
            if len(label) > self.label_width:
                label = label[:self.label_width]
                #dis.append( (p,'%3s%s%04x %10s' % (arrow,bpt,p,label)))
                #dis.append( (p,'%3s%s%04x %10s : %9s : %s %s' % (arrow,bpt,p,b,' '*self.label_width,ins,args)))
            #else:
            dis.append( (p,'%3s%s%04x %9s : %14s : %s %s' % (arrow,bpt,p,b,label,ins,args)))
                
        self.disassembly = dis

    def Select(self,pos):
        self.selected = pos

    def TakeInput(self):
        ch = self.window.getch()
        #print ch,curses.KEY_DOWN
        if ch == curses.KEY_DOWN:
            try:
                self.selected = self.disassembly[self.selected_pos+1][0]
                self.Centre(self.selected)
            except IndexError:
                pass
        elif ch == curses.KEY_UP:
            if self.selected_pos > 0:
                self.selected = self.disassembly[self.selected_pos-1][0]
                self.Centre(self.selected)
        elif ch == curses.KEY_NPAGE:
            #We can't jump to any arbitrary point because we don't know the instruction boundaries
            #instead jump to the end of the screen twice, which should push us down by a whole page
            for i in xrange(2):
                p = self.disassembly[-1][0]
                self.Centre(p)

            self.Select(p)
        elif ch == curses.KEY_PPAGE:
            for i in xrange(2):
                p = self.disassembly[0][0]
                self.Centre(p)

            self.Select(p)
        elif ch == ord('\t'):
            return WindowControl.NEXT
        elif ch == ord(' '):
            if self.selected in self.debugger.breakpoints:
                self.debugger.breakpoints.remove(self.selected)
            else:
                self.debugger.breakpoints.add(self.selected)
            self.Centre(self.selected)
        elif ch == ord('c'):
            self.debugger.Continue()
            return WindowControl.RESUME
        elif ch == ord('s'):
            return WindowControl.RESUME
        elif ch == ord('r'):
            self.debugger.cpu.Reset()
            return WindowControl.RESTART
        return WindowControl.SAME


    def Draw(self,draw_border = False):
        self.window.clear()
        if draw_border:
            self.window.border()
        self.selected_pos = None
        for i,(pos,line) in enumerate(self.disassembly):
            if pos == self.selected:
                self.selected_pos = i
                self.window.addstr(i+1,1,line,curses.A_REVERSE)
            else:
                #print i,line
                self.window.addstr(i+1,1,line)
        self.window.refresh()

class State(View):
    def __init__(self,debugger,h,w,y,x):
        super(State,self).__init__(h,w,y,x)
        self.debugger = debugger

    def Draw(self,draw_border = False):
        self.window.clear()
        if draw_border:
            self.window.border()
        for i,(regname,value) in enumerate( (('A',self.debugger.cpu.registers[0]),
                                             ('B',self.debugger.cpu.registers[1]),
                                             ('C',self.debugger.cpu.registers[2]),
                                             ('X',self.debugger.cpu.registers[3]),
                                             ('Y',self.debugger.cpu.registers[4]),
                                             ('Z',self.debugger.cpu.registers[5]),
                                             ('I',self.debugger.cpu.registers[6]),
                                             ('J',self.debugger.cpu.registers[7]),
                                             ('SP',self.debugger.cpu.sp[0]),
                                             ('PC',self.debugger.cpu.pc[0]),
                                             ('EX',self.debugger.cpu.overflow[0])) ):
            self.window.addstr(i+1,1,'%2s : %04x' % (regname,value))
        self.window.refresh()

class Help(View):
    def Draw(self,draw_border = False):
        self.window.clear()
        if draw_border:
            self.window.border()
        for i,(key,action) in enumerate( (('c','continue'),
                                          ('g','goto'),
                                          ('s','step'),
                                          ('space','set breakpoint'),
                                          ('tab','switch window')) ):
            self.window.addstr(i+1,1,'%5s - %s' % (key,action))
        self.window.refresh()

class Memdump(View):
    display_width = 16
    key_time = 0.5
    masks  = (0x0000,0xf000,0xff00,0xfff0,0xffff)
    shifts = (12,8,4,0)
    def __init__(self,debugger,h,w,y,x):
        super(Memdump,self).__init__(h,w,y,x)
        self.debugger = debugger
        self.pos = 0
        self.selected = 0
        self.lastkey = 0
        self.keypos = 0

    def Draw(self,draw_border = False):
        self.window.clear()
        if draw_border:
            self.window.border()
        for i in xrange(self.height-2):
            addr = self.pos + i*self.display_width
            data = self.debugger.cpu.memory[addr:addr+self.display_width]
            if len(data) < self.display_width:
                data.extend([0]*(self.display_width-len(data)))
            data_string = ' '.join('%04x' % d for d in data)
            line = '%04x : %s' % (addr,data_string)
            if addr == self.selected:
                self.window.addstr(i+1,1,line,curses.A_REVERSE)
            else:
                self.window.addstr(i+1,1,line)
        self.window.refresh()

    def TakeInput(self):
        ch = self.window.getch()
        if ch == curses.KEY_DOWN:
            self.selected += self.display_width
            if self.selected >= 0x10000:
                self.selected = 0x10000
            if ((self.selected - self.pos)/self.display_width) >= (self.height - 2):
                self.pos = self.selected - (self.height-3)*self.display_width
        elif ch == curses.KEY_UP:
            self.selected -= self.display_width
            if self.selected < 0:
                self.selected = 0
            if self.selected < self.pos:
                self.pos = self.selected
        elif ch in [ord(c) for c in '0123456789abcdef']:
            newnum = int(chr(ch),16)
            now = time.time()
            if now - self.lastkey > self.key_time:
                self.keypos = 0
            self.pos &= self.masks[self.keypos]
            self.pos |= newnum << self.shifts[self.keypos]
            self.keypos += 1
            self.keypos &= 3
            self.lastkey = now
            self.selected = self.pos
            
        elif ch == ord('\t'):
            return WindowControl.NEXT
        return WindowControl.SAME
    

class Debugger(object):
    def __init__(self,cpu,labels):
        self.cpu              = cpu
        self.breakpoints      = set([0])
        self.selected         = 0
        self.stdscr           = cpu.stdscr
        self.labels           = Labels(labels)

        self.h,self.w       = self.stdscr.getmaxyx()
        self.code_window    = Debug(self,self.h,self.w/2,0,0)
        self.state_window   = State(self,self.h/2,self.w/4,0,self.w/2)
        self.help_window    = Help(self.h/2,self.w/4,0,3*(self.w/4))
        self.memdump_window = Memdump(self,self.h/2,self.w/2,self.h/2,self.w/2)
        self.window_choices = [self.code_window,self.memdump_window]
        self.current_view   = self.code_window
        self.stopped        = False
        self.help_window.Draw()

    def Continue(self):
        self.stopped = False
        
    def Executing(self,pc):
        self.current_view = self.code_window
        if not self.stopped:
            if pc in self.breakpoints:
                self.stopped = True
            else:
                return
        else:
            self.current_view.Centre()
        self.current_view.Select(pc)
        self.current_view.Centre(pc)

        #We're stopped, so display and wait for a keypress
        while True:
            #disassembly = disassemble.Disassemble(cpu.memory)
            
            for window in self.state_window,self.memdump_window,self.code_window:
                window.Draw(self.current_view is window)

            result = self.current_view.TakeInput()
            if result == WindowControl.RESUME:
                break
            elif result == WindowControl.RESTART:
                return False
            elif result == WindowControl.NEXT:
                pos = self.window_choices.index(self.current_view)
                pos = (pos + 1)%len(self.window_choices)
                self.current_view = self.window_choices[pos]
            
