class Keyboard(object):
    max_buffer_len = 16
    id             = 0x30cf7406
    manufacturer   = 0x41414141
    version        = 1
    def __init__(self,dcpu):
        self.dcpu              = dcpu
        self.buffer            = []
        self.states            = [0 for i in xrange(0x92)]
        self.interrupt_message = 0

    def key_down(self,key):
        self.states[key] = 1
        if self.interrupt_message != 0:
            self.dcpu.Interrupt(self.interrupt_message)

    def key_up(self,key):
        self.states[key] = 0
        self.key_typed(key)
        #if self.interrupt_message != 0:
        #    self.dcpu.Interrupt(self.interrupt_message)
        
    def key_typed(self,key):
        if len(self.buffer) > self.max_buffer_len:
            return
        self.buffer.append(key)
        if self.interrupt_message != 0:
            self.dcpu.Interrupt(self.interrupt_message)

    def Interrupt(self):
        value = self.dcpu.registers[0]
        if value == 0:
            self.buffer = []
        elif value == 1:
            try:
                key = self.buffer.pop(0)
            except IndexError:
                key = 0
            self.dcpu.registers[2] = key
        elif value == 2:
            try:
                out = self.states[self.dcpu.registers[1]]
            except IndexError:
                out = 0
            self.dcpu.registers[2] = out
        elif value == 3:
            self.interrupt_message = self.dcpu.registers[1]
        return 0
