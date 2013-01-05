import pygame
import random

scale_factor = None

def SetPixels(pixels,words):
    for i,word in enumerate(words):
        for j in xrange(16):
            #the next line is so obvious it doesn't need a comment
            pixels[i*2+1-(j/8)][j%8] = ((word>>j)&1)

class MemType:
    SCREEN  = 0
    FONT    = 1
    PALETTE = 2

class Lem1802(object):
    id             = 0x7349f615
    manufacturer   = 0x1c6c8b36
    version        = 0x1802
    vram_size      = 384
    lookups = (('mem_screen' ,vram_size ,MemType.SCREEN),
               ('mem_font'   ,256       ,MemType.FONT),
               ('mem_palette',16        ,MemType.PALETTE))
    def __init__(self,dcpu):
        self.dcpu              = dcpu
        self.buffer            = []
        self.mem_screen        = 0
        self.mem_font          = 0
        self.mem_palette       = 0
        self.dirty_rects = {}
        self.screen = pygame.display.set_mode((128*scale_factor, 96*scale_factor))
        self.font_surface = pygame.Surface((4,8),depth=8)
        self.font_surface.set_palette(((0, 0, 0, 255),)*256)
        self.font_surface.set_palette(((0,0,0,255),(255, 255, 255, 255)))
        self.font_surfaces = {}
        self.last = None
        #Blinkers is a set of all those video positions currently blinking
        self.blinkers = {}
        #Letters is a lookup keyed on letter, values are a list of video positions with that letter.
        #It's to make updating the screen on font updates quicker
        self.letters  = {i:set() for i in xrange(0x80)}
        self.letters[0] = set(range(self.vram_size))
        self.vram_cache = [0 for i in xrange(self.vram_size)]
        self.default_palette = [ (0x00,0x00,0x00,0xff),
                                 (0x00,0x00,0xaa,0xff),
                                 (0x00,0xaa,0x00,0xff),
                                 (0x00,0xaa,0xaa,0xff),
                                 (0xaa,0x00,0x00,0xff),
                                 (0xaa,0x00,0xaa,0xff),
                                 (0xaa,0xaa,0x00,0xff),
                                 (0xaa,0xaa,0xaa,0xff),
                                 (0x55,0x55,0x55,0xff),
                                 (0x55,0x55,0xff,0xff),
                                 (0x55,0xff,0x55,0xff),
                                 (0x55,0xff,0xff,0xff),
                                 (0xff,0x55,0x55,0xff),
                                 (0xff,0x55,0xff,0xff),
                                 (0xff,0xff,0x55,0xff),
                                 (0xff,0xff,0xff,0xff) ]
        self.palette = [colour for colour in self.default_palette]

        self.pixels = pygame.PixelArray(self.font_surface)

        self.font_data = [[0,0] for i in xrange(128)]
        self.write_handlers = {MemType.SCREEN  : self.write_screen,
                               MemType.FONT    : self.write_font,
                               MemType.PALETTE : self.write_palette}
        
        with open('default_font.txt','rb') as f:
            for line in f:
                i,dummy,word1,word2 = line.strip().split()
                i,word1,word2 = [int(v,16) for v in i,word1,word2]
                self.font_data[i] = [word1,word2]
                SetPixels(self.pixels,self.font_data[i])
                self.font_surfaces[i] = pygame.transform.scale(self.font_surface,(4*scale_factor,8*scale_factor))

    def Interrupt(self):
        value = self.dcpu.registers[0]
        if value >= 0 and value <= 2:
            name,size,t = self.lookups[value]
            mmap = getattr(self,name)
            if mmap:
                self.dcpu.Munmap(mmap)
            mmap = self.dcpu.registers[1]
            setattr(self,name,mmap)
            self.dcpu.Mmap(self,mmap,size,t)
            update_func = self.write_handlers[t]
            #On initial mmap we need to read all of the buffer
            for i in xrange(size):
                update_func(i)
                
        elif value == 3:
            #set border colour
            pass
        elif value == 4:
            #dump default font
            pos = self.dcpu.registers[1]
            #start = pos
            #print 'Dumping font to %x' % pos
            for font_datum in self.font_data:
                for word in font_datum:
                    self.dcpu.memory[pos] = word
                    pos = (pos + 1)&0xffff
            #assert(pos == (start+256))
            #for i in xrange(start,pos):
            #    print '%04x' % self.dcpu.memory[i]
            #raise SystemExit
        elif value == 5:
            #dump default palette
            pos = self.dcpu.registers[1]
            for i in xrange(16):
                r,g,b,opacity = self.default_palette[i]
                r,g,b = (v>>4 for v in (r,g,b))
                self.dcpu.memory[(pos + i)&0xffff] = (r<<8) | (g<<4) | (b)
        return 0

    def mmap_write(self,offset,kind):
        self.write_handlers[kind](offset)

    def write_screen(self,pos):
        x = (pos&0x1f)*4
        y = (pos/32)*8
        dirty = (x*scale_factor,y*scale_factor,(x+4)*scale_factor,(y+8)*scale_factor)
        letter = self.dcpu.memory[(self.mem_screen + pos)&0xffff]
        #if (pos,letter) != self.last:
            #print pos,letter,' '.join('%04x' % c for c in self.dcpu.memory[self.mem_screen:self.mem_screen+16])
            #print 'write_screen',pos,x,y,letter,self.dcpu.registers[2]
        #self.last = (pos,letter)
        text_colour = (letter>>12)&0xf
        back_colour = (letter>>8)&0xf
        text_colour,back_colour = (self.palette[c] for c in (text_colour,back_colour))
        blink = True if letter&0x80 else False
        letter = letter&0x7f

        tile = self.font_surfaces[letter&0x7f]
        tile.set_palette((back_colour,text_colour))
        if blink:
            self.blinkers[pos] = (tile,text_colour,back_colour)
        elif pos in self.blinkers:
            del self.blinkers[pos]
        self.screen.blit(tile,(x*scale_factor,y*scale_factor))
        self.dirty_rects[dirty] = True
        old_letter = self.vram_cache[pos]
        self.letters[old_letter].remove(pos)
        self.letters[letter].add(pos)
        self.vram_cache[pos] = letter
    
    def write_font(self,pos):
        index = (self.mem_font + (pos&0xfffe))&0xffff
        SetPixels(self.pixels,self.dcpu.memory[index:index+2])
        self.font_surfaces[pos/2] = pygame.transform.scale(self.font_surface,(4*scale_factor,8*scale_factor))
        #if self.mem_screen:
        #    for video_pos in xrange(self.vram_size):
        #        letter = self.dcpu.memory[(self.mem_screen + video_pos)&0xffff]
        #        if letter == (pos/2):
        #            self.write_screen(video_pos)
 
    def write_palette(self,offset):
        value = self.dcpu.memory[(self.mem_palette + offset)&0xffff]
        r,g,b = ((value >> i)&0xf for i in (8,4,0))
        self.palette[offset] = (r*16,g*16,b*16,0xff)

    def Update(self):
        #print len(self.blinkers)
        for pos,(tile,fore,back) in self.blinkers.iteritems():
                x = (pos&0x1f)*4
                y = (pos/32)*8
                dirty = (x*scale_factor,y*scale_factor,(x+4)*scale_factor,(y+8)*scale_factor)
                if (self.dcpu.cycles/50000)&1:
                    tile.set_palette((back,fore))
                else:
                    tile.set_palette((back,back))
                self.screen.blit(tile,(x*scale_factor,y*scale_factor))
                self.dirty_rects[dirty] = True
        if self.dirty_rects:
            pygame.display.update(self.dirty_rects.keys())
            self.dirty_rects = {}

