import sys,struct
import instruction

labels = {}
pos = 0
line_number = 0
out = []


instructions = {'set':instruction.SetInstruction,
                'add':instruction.AddInstruction,
                'sub':instruction.SubInstruction,
                'mul':instruction.MulInstruction,
                'div':instruction.DivInstruction,
                'mod':instruction.ModInstruction,
                'shl':instruction.ShlInstruction,
                'shr':instruction.ShrInstruction,
                'and':instruction.AndInstruction,
                'bor':instruction.BorInstruction,
                'xor':instruction.XorInstruction,
                'ife':instruction.IfeInstruction,
                'ifn':instruction.IfnInstruction,
                'ifg':instruction.IfgInstruction,
                'ifb':instruction.IfbInstruction,
                'jsr':instruction.JsrInstruction,
                'dat':instruction.Data}

for line_number,line in enumerate(sys.stdin):
    line = line.strip().split(';')[0].strip()
    if line and line[0] == ':': #it's a label
        label_parts = line[1:].split(None,1)
        labels[label_parts[0]] = pos
        if len(label_parts) == 1:
            continue
        else:
            line = label_parts[1]
        print 'label',label_parts[0],hex(pos)
    if not line:
        continue
    try:
        instruction,line = line.split(None,1)
    except ValueError:
        raise Monkeys
    #I'm not sure if there's a nice simpy way to parse this with regular expressions or python string manipulation
    #functions, but I'll just go with a long hand approach to be clear. This whole thing should really be done with 
    #flex / bison / whatever the fuck. even regexes maybe
    #to be clear, we want to split on commas, but not if they're inside quotes.
    line_pos = 0
    parts = []
    inside = 0
    word = []
    while line_pos < len(line):
        letter = line[line_pos]
        if not inside:
            letter = letter.lower()
        word.append(letter)
        if letter == '"':
            inside ^= 1
        elif letter == '\\':
            #escape the next character
            line_pos += 1
            letter = line[line_pos]
            if not inside:
                letter = letter.lower()
        elif letter == ',' and not inside:
            parts.append(''.join(word[:-1]).strip())
            word = []
        line_pos += 1
    parts.append(''.join(word).strip())
            
    #parts = line.split()
    instruction = instruction.lower()
    args = parts
    
    print instruction,args
    instruction = instruction.strip(',')
    try:
        instruction = instructions[instruction]
    except KeyError:
        print 'Unknown instruction at line %d:%s' % (line_number+1,instruction)
        raise SystemExit
    try:
        instruction = instruction(args)
    except:
        print 'Unspecified Error during parsing of line %d:%s' % (line_number+1,line)
        raise
    out.append(instruction)
    pos += len(out[-1])

#Now the first pass has completed we have encountered all the labels, so go through filling them in...
try:
    for i,instruction in enumerate(out):
        instruction.FillLabels(labels)
except instruction.UnknownLabel as e:
    print 'unknown label %s in instruction %d'  % (e.label,i)
    raise SystemExit

out = [i.Emit() for i in out]
    
with open(sys.argv[1],'wb') as f:
    f.write(''.join(out))
