import time

class Clock(object):
    id           = 0x12d0b402
    manufacturer = 0x41414141
    version      = 1
    def __init__(self,dcpu):
        self.dcpu  = dcpu
        self.ticks = 0
        self.tick_duration  = 0
        self.interrupt_message = 0
        self.last  = 0

    def Interrupt(self):
        value = self.dcpu.registers[0]
        if value == 0:
            self.tick_duration = self.dcpu.registers[1]/60.0
            self.ticks = 0

        elif value == 1:
            self.dcpu.registers[2] = self.ticks

        elif value == 2:
            self.interrupt_message = self.dcpu.registers[1]
        return 0

    def Update(self):
        t = time.time()
        if self.last == 0:
            self.last = t
            return
        elapsed = t - self.last
        
        if self.tick_duration:
            ticks_passed = int(elapsed/self.tick_duration)
            if ticks_passed >= 1:
                self.ticks += ticks_passed
                self.last += ticks_passed * self.tick_duration
                if self.interrupt_message != 0:
                    self.dcpu.Interrupt(self.interrupt_message)
                
        else:
            self.last = t
