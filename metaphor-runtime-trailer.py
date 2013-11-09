
# The following code corresponds to the grammar definition:
#  <*whitespace*> ::= REPEAT (ANY_OF ' \t\n\r\u000b\u000c');
# (Note that the labels all start with 'X' so no clash with generated labels.)

whitespace_code = [\
    '*whitespace*',
    (CHECKPOINT,),
    'X126',
    (BRA,),
    (CHECKPOINT,),
    (ANY_OF, ' \t\n\r\u000b\u000c'),
    (YIELD,),
    (BF, 'X127'),
    (COMMIT,),
    (YIELD,),
    (B, 'X128'),
    'X127',
    (ROLLBACK,),
    'X128',
    'X129',
    (KET,),
    (YIELD,),
    (BT, 'X126'),
    (SET,),
    (BF, 'X124'),
    (COMMIT,),
    (YIELD,),
    (B, 'X125'),
    'X124',
    (ROLLBACK,),
    'X125',
    'X130',
    (R,),]

# If the grammar doesn't itself define <*whitespace*>, we need
# to bolt this code onto the end of the program

if "*whitespace*" not in PROGRAM:
    PROGRAM.extend(whitespace_code)

#-------------------------------------------------------
# Helper to lookup labels

LABELS = {}
def lookup(s):
    if s in LABELS:
        return LABELS[s]
    else:
        for i, item in enumerate(PROGRAM):
            if isinstance(item, str) and item == s:
                LABELS[s] = i
                return i
        error("+++ No such label:", s)

# All that's left is to run it ...        
instruction = PROGRAM[0]
while True:
    fun, args = instruction[0], instruction[1:]
    fun(*args)
    if PC == None:
        break
    instruction = PROGRAM[PC]
    PC += 1
    # skip over labels
    while isinstance(instruction, str):
        instruction = PROGRAM[PC]
        PC += 1

# If the parse failed, show the high water mark
if not SWITCH:
    text = INPUT[max(0, HWM_position - 60):HWM_position] + "\n" + \
            "***ERROR: Syntax error\n***HERE:\n" + \
               INPUT[HWM_position:HWM_position + 60] + " ...\n"
    HWM_rules.reverse()
    for rule in HWM_rules[:-1]:
        text += "in <" + rule + "> "
    error(text)

# Tidy up the output
def flatten(xs):
    for x in xs:
        if isinstance(x, list):
            for y in flatten(x):
                yield y
        else:
            yield x

margin = 0
line_start = True
for item in flatten(RETVAL):
    if isinstance(item, int):
        if item == 0:
            # Newline marker
            sys.stdout.write("\n")
            line_start = True
        else:
            margin = max(0, margin + item)
    elif isinstance(item, str):
        if len(item) > 0:
            if line_start:
                sys.stdout.write(" " * margin)
            line_start = False
            sys.stdout.write(item)
    else:
        error("+++ Internal problem:", item)


    
