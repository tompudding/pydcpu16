import curses
import disassemble

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
        return self

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
        for (p,b,ins,args) in self.disassembly[start:start+self.height]:
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
        elif ch == ord(' '):
            if self.selected in self.debugger.breakpoints:
                self.debugger.breakpoints.remove(self.selected)
            else:
                self.debugger.breakpoints.add(self.selected)
            self.Centre(self.selected)
        elif ch == ord('c'):
            self.debugger.Continue()
            return None
        elif ch == ord('s'):
            return None
        return self


    def Draw(self):
        self.window.clear()
        self.selected_pos = None
        for i,(pos,line) in enumerate(self.disassembly):
            if pos == self.selected:
                self.selected_pos = i
                self.window.addstr(i,0,line,curses.A_REVERSE)
            else:
                #print i,line
                self.window.addstr(i,0,line)
        self.window.refresh()

class State(View):
    def __init__(self,debugger,h,w,y,x):
        super(State,self).__init__(h,w,y,x)
        self.debugger = debugger

    def Draw(self):
        self.window.clear()
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
            self.window.addstr(i,0,'%2s : %04x' % (regname,value))
        self.window.refresh()

class Help(View):
    def Draw(self):
        self.window.clear()
        for i,(key,action) in enumerate( (('c','continue'),
                                          ('g','goto'),
                                          ('s','step'),
                                          ('space','set breakpoint'),
                                          ('tab','switch window')) ):
            self.window.addstr(i,0,'%5s - %s' % (key,action))
        self.window.refresh()

class Memdump(View):
    def __init__(self,debugger,h,w,y,x):
        super(Memdump,self).__init__(h,w,y,x)
        self.debugger = debugger
        self.pos = 0

    def Draw(self):
        for i in xrange(self.height):
            addr = self.pos + i*16
            data = self.debugger.cpu.memory[addr:addr+16]
            if len(data) < 16:
                data.extend([0]*(16-len(data)))
            data_string = ' '.join('%04x' % d for d in data)
            self.window.addstr(i,0,'%04x : %s' % (addr,data_string))
        self.window.refresh()
    

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
                self.current_view.Select(pc)
                self.current_view.Centre(pc)
            else:
                return
        else:
            self.current_view.Centre()

        #We're stopped, so display and wait for a keypress
        while True:
            #disassembly = disassemble.Disassemble(cpu.memory)
            
            self.state_window.Draw()
            self.memdump_window.Draw()
            self.code_window.Draw()
            self.current_view = self.current_view.TakeInput()
            if self.current_view == None:
                break
            
