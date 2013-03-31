import sys
import random

NUMWORDS = 50
WORDSIZE = 16
WORDMASK = ((1<<WORDSIZE)-1)
MASK = (1<<(NUMWORDS*16))-1

#This is a prototype for an assembly implementation. It's not supposed to be pythonic

class BigNum(object):
    def __init__(self,num=0):
        self.words = [0 for i in xrange(NUMWORDS)]
        self.num_words = 0
        if isinstance(num,BigNum):
            self.words = num.words[::]
            self.num_words = num.num_words
            return
        self.Set(num)
        
    def Zero(self):
        for i in xrange(len(self.words)):
            self.words[i] = 0
        self.num_words = 0

    def Set(self,num):
        num &= MASK
        self.Zero()
        while num > 0:
            self.words[self.num_words] = num&WORDMASK
            self.num_words += 1
            num >>= 16

    def PrintDat(self):
        for word in [self.num_words] + self.words:
            print 'DAT 0x%04x' % word
        print

    def Print(self):
        print ''.join(['%04x' % c for c in self.words[:self.num_words]][::-1])


def Add(x,y):
    overflow = 0
    last_zero_words = 0
    for i in xrange(NUMWORDS):
        if i >= y.num_words and overflow == 0:
            break
        x.words[i] += (y.words[i] + overflow)
        if x.words[i] > WORDMASK:
            x.words[i] -= 0x10000
            overflow = 1
        else:
            overflow = 0
        if x.words[i] == 0:
            last_zero_words += 1
        else:
            last_zero_words = 0
    if i > x.num_words:
        x.num_words = i
    x.num_words -= last_zero_words

def Sub(x,y):
    overflow = 0
    last_zero_words = 0
    for i in xrange(NUMWORDS):
        if i >= y.num_words and overflow == 0:
            break
        x.words[i] -= (y.words[i] + overflow)
        if x.words[i] < 0:
            x.words[i] += 0x10000
            overflow = 1
        else:
            overflow = 0
        if x.words[i] == 0:
            last_zero_words += 1
        else:
            last_zero_words = 0
    if i > x.num_words:
        x.num_words = i
    x.num_words -= last_zero_words

def Rshift(x,y):
    word_shift = y/WORDSIZE
    sub_shift = y&(WORDSIZE-1)
    for i in xrange(x.num_words):
        if i+word_shift >= x.num_words:
            a = 0
        else:
            a = x.words[i+word_shift]>>sub_shift
        if i+word_shift+1 >= x.num_words:
            b = 0
        else:
            b = (x.words[i+word_shift+1]<<(WORDSIZE-sub_shift)&WORDMASK)
        x.words[i] = a | b
    x.num_words -= word_shift
    assert x.num_words >= 0
    if x.num_words > 0 and x.words[x.num_words-1] == 0:
        x.num_words -= 1

def Cmp(a,b):
    if a.num_words > b.num_words:
        return 1
    elif a.num_words < b.num_words:
        return -1
    #equal number of words
    for i in xrange(a.num_words):
        if a.words[i] < b.words[i]:
            return -1
        if a.words[i] > b.words[i]:
            return 1
    return 0
        

def MontyMul(a,x,y,rinv,m):
    a.Zero()
    for w in xrange(48):
        for i in xrange(WORDSIZE):
            xbit = ((x.words[w]>>i)&1)
            u = (a.words[0]&1) ^ ( (xbit & y.words[0])&1 )
            if xbit:
                Add(a,y)
            if u:
                Add(a,m)
            Rshift(a,1)
            a.Print()
            print i,w
    if Cmp(a,m) > 0:
        Sub(a,m)
    

m     = BigNum(0xffffffffffffffffc90fdaa22168c234c4c6628b80dc1cd129024e088a67cc74020bbea63b139b22514a08798e3404ddef9519b3cd3a431b302b0a6df25f14374fe1356d6d51c245e485b576625e7ec6f44c42e9a63a3620ffffffffffffffff)
Rinv  = BigNum(0xaedeec350492d9c8ab21edbde1bd016c6f7d95e2c428a0c6f580eabc8315617e900bf6073ac1af565d7131ff9fc0ba4d5661dd351e73fa0fd075b96625a07c6581d03f04faa0e4a7602a2c70180d9922042ac2acc98281d6e3d44cd8dea606ef)
Rmodm = BigNum(0x36f0255dde973dcb3b399d747f23e32ed6fdb1f77598338bfdf44159c4ec64ddaeb5f78671cbfb22106ae64c32c5bce4cfd4f5920da0ebc8b01eca9292ae3dba1b7a4a899da181390bb3bd1659c5c9df0000000000000001)
xbar  = BigNum(0x6de04abbbd2e7b9676733ae8fe47c65dadfb63eeeb306717fbe882b389d8c9bb5d6bef0ce397f64420d5cc98658b79c99fa9eb241b41d791603d9525255c7b7436f495133b43027217677a2cb38b93be0000000000000002)
#R     = BigNum(1<<768)
one   = BigNum(1)

def ModExp(t,x,e,m):
    t1 = BigNum(Rmodm)
    t2 = BigNum(0)
    assert e.words[e.num_words-1] != 0
    try:
        for i in xrange(WORDSIZE-1,-1,-1):
            if (e.words[e.num_words-1]>>i)&1:
                break
        else:
            raise CabbageError
    except IndexError:
        #Exponent is 0
        t.Set(1)
        return
    bitstart = i
    for w in xrange(e.num_words-1,-1,-1):
        print w
        for i in xrange(bitstart if w == e.num_words-1 else WORDSIZE-1,-1,-1):
            MontyMul(t2,t1,t1,Rinv,m)
            t1,t2 = t2,t1
            #print w*WORDSIZE+i,''.join(['%04x' % c for c in t1.words][::-1])
            if (e.words[w]>>i)&1:
                MontyMul(t2,t1,xbar,Rinv,m)
                t1,t2 = t2,t1
                #print w*WORDSIZE+i,'*',''.join(['%04x' % c for c in t1.words][::-1])
    MontyMul(t,t1,one,Rinv,m)

a = BigNum(0)
MontyMul(a,xbar,xbar,Rinv,m)

a.Print()
raise SystemExit
                                                          
a_n = int(sys.argv[1])

a = BigNum(a_n)
b = BigNum(2)
target = BigNum(0)

ModExp(target,b,a,m)

print ''.join(['%04x' % c for c in target.words[:target.num_words]][::-1])
print target.num_words
raise SystemExit

# for i in xrange(1000):
#     a_n = random.getrandbits(500)
#     y = random.randint(0,500)
#     a = BigNum(a_n)
#     b = BigNum(a_n>>y)
#     Rshift(a,y)
#     if a.words != b.words:
#         print hex(a_n)
#         print hex(a_n>>y)
#         print hex(y)
#         print ['%04x' % c for c in a.words]
#         print ['%04x' % c for c in b.words]
#         raise SystemExit

#for i in xrange(10000):
#    a_n = random.getrandbits(500)
#    b_n = random.getrandbits(500)
#    a = BigNum(a_n)
#    b = BigNum(b_n)
#    Add(a,b)
#    if BigNum(a_n+b_n).words != a.words:
#        print hex(a_n)
#        print hex(b_n)
#        raise SystemExit

print hex(a_n-b_n)
print BigNum(a_n-b_n).words
print a.words
print a.num_words

print a.words == BigNum(a_n-b_n).words

        
