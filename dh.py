import math
import sys 

m = 0xFFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A63A3620FFFFFFFFFFFFFFFF

def MontyMul(x,y,rinv,m):
    a = 0
    for i in xrange(768):
        u = (a + ((x>>i)&y))&1
        adder = 0
        if (x>>i)&1:
            adder += y
        if u:
            adder += m
        a = (a + adder)>>1
    if a > m:
        a -= m
    return a

def euclid_inv(a,b):
    lasty = x = 0
    lastx = y = 1
    m = b
    while b != 0:
        q = a / b
        (a, b) = (b, a % b)
        (x, lastx) = (lastx - q*x, x)
        (y, lasty) = (lasty - q*y, y)       
    if lastx < 0:
        lastx += m
    return lastx

R = 2**768
Rinv = euclid_inv(R,m)
a    = R % m
xbar = (a<<1)
if xbar > m:
    xbar -= m

print hex(Rinv)
print hex(a)
print hex(xbar)
print '--'
e = int(sys.argv[1])

for j in xrange(767,-1,-1):
    if (e>>j)&1:
        break

for i in xrange(j,-1,-1):
    a = MontyMul(a,a,Rinv,m)
    print i,hex(a)
    if (e>>i)&1:
        a = MontyMul(a,xbar,Rinv,m)
        print i,'*',hex(a)
a = MontyMul(a,1,Rinv,m)

print hex(a)
print hex(pow(2,e,m))
#print math.log(a,2)
#print hex(2**e)

