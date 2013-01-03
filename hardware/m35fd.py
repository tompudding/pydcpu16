class M35fd(object):
    id             = 0x4fd524c5
    manufacturer   = 0x1eb37e91
    version        = 0x000b
    def __init__(self,dcpu):
        self.dcpu = dcpu

    def Interrupt(self):
        return 0
