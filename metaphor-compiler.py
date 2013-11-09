#!/usr/bin/python3

import sys
import string
import re
import os

# Meta-compiler runtime. This was originally based on a tutorial/website by
# James M. Neighbors: "Tutorial: Metacompilers Part 1" (2008). That was
# in turn based on a paper by D. V. Schorre: "META II: A Syntax-Oriented
# Compiler Writing Language" (1964).

#--------------------------------------------------------

def error(*args):
    print(*args, file=sys.stderr)
    sys.exit(1)

#--------------------------------------------------------
# Parse command-line arguments, get filenames straight

myname = os.path.basename(sys.argv[0])
if len(sys.argv) == 1:
    error("Usage: %s <input-file>" % myname)
INPUT_name = sys.argv[1]

#--------------------------------------------------------
# Global variables holding input file contents

with open(INPUT_name) as fin:
    INPUT = fin.read()
 
# Other global variables

INPUT_position = 0
GENINT_counter = 1

HWM_position = 0
HWM_rules = []

CALL_STACK = [] # return addr, rule-name, vars dict
EXPR_STACK = [] # input position, output list 
SWITCH = False
RETVAL = ""

# These get saved on a function (rule) call
PC = None
RULE = None
VARS_dict = {}
OUTPUT_list = []
        
#--------------------------------------------------------
# Parsing machine instructions

# XXX trying to write this using checkpoint/rollback/commit, so as
# to see how this will go when implement <ID>, <NUM> etc using
# grammar rules (it's a bit contorted ...)

def have_char():
    return INPUT_position < len(INPUT)

def get_char():
    global INPUT_position
    result = INPUT[INPUT_position]
    INPUT_position += 1
    return result

def success():
    global SWITCH, HWM_position, HWM_rules
    SWITCH = True
    # Remember, if this is the furthest so far ...
    if INPUT_position > HWM_position:
         HWM_position = INPUT_position
         HWM_rules = [rule for _, rule, _ in CALL_STACK]

def failure():
    global SWITCH
    SWITCH = False

def CHECKPOINT():
    global OUTPUT_list
    EXPR_STACK.append((INPUT_position, OUTPUT_list))
    OUTPUT_list = []

def ROLLBACK():
    global INPUT_position
    global OUTPUT_list
    RETVAL = ""
    INPUT_position, OUTPUT_list = EXPR_STACK.pop()
    failure()

def consolidate_OUTPUT_list_to_RETVAL():
    global RETVAL
    # try consolidate what's in the OUTPUT_list into one string if we can
    if all(isinstance(x, str) for x in OUTPUT_list):
        RETVAL = "".join(OUTPUT_list)
    else:
        RETVAL = OUTPUT_list

def COMMIT():
    global OUTPUT_list
    consolidate_OUTPUT_list_to_RETVAL()
    _, OUTPUT_list = EXPR_STACK.pop() # DON'T restore INPUT_position
    success()

def match_char_in(candidates):
    CHECKPOINT()
    if have_char():
        got = get_char()
        if got in candidates:
            OUTPUT_list.append(got)
            COMMIT()
        else:
            ROLLBACK()
    else:
        ROLLBACK()
    return SWITCH

def match_char_not_in(candidates):
    CHECKPOINT()
    if have_char():
        got = get_char()
        if got not in candidates:
            OUTPUT_list.append(got)
            COMMIT()
        else:
            ROLLBACK()
    else:
        ROLLBACK()
    return SWITCH

# Now ANY_OF, ANY_BUT and LITERAL, which we will use to build
# token recognisers in the grammar, rather than built-in to the
# runtime

def ANY_OF(x):
    if isinstance(x, str):
        match_char_in(x)
    else:
        error("Wrong argument " + x + " to ANY_OF")

def ANY_BUT(x):
    if isinstance(x, str):
        match_char_not_in(x)
    else:
        error("Wrong argument " + x + " to ANY_BUT")

def LITERAL(x):
    CHECKPOINT()
    for ch in x:
        if match_char_in(ch):
            OUTPUT_list.append(RETVAL)
        else:
            ROLLBACK()
            return
    COMMIT()
   
#------------------------------------------------------------
# Be a packrat: 
# When we use a rule at a particular place in the input, first check 
# if we've done this before, and if so, return the cached result.
RULE_USE_CACHE = {}

def CALL(rule):
    global PC, RULE, OUTPUT_list, VARS_dict
    global INPUT_position, RETVAL, SWITCH
    if (INPUT_position, rule) in RULE_USE_CACHE:
        INPUT_position, RETVAL, SWITCH =  RULE_USE_CACHE[INPUT_position, rule]
    else:
        CALL_STACK.append([PC, RULE, VARS_dict])
        EXPR_STACK.append((INPUT_position, OUTPUT_list))
        PC = lookup(rule)
        RULE = rule
        OUTPUT_list = []
        VARS_dict = {}

def R():
    global PC, RULE, VARS_dict, OUTPUT_list
    consolidate_OUTPUT_list_to_RETVAL()
    # DON'T restore old INPUT_position ...
    old_posn, OUTPUT_list = EXPR_STACK.pop()  
    # ... but use it to cache our result
    RULE_USE_CACHE[old_posn, RULE] = (INPUT_position, RETVAL, SWITCH)
    PC, RULE, VARS_dict = CALL_STACK.pop()
    
def SET():
    global RETVAL
    RETVAL = ""
    success()

def ADR(label):
    CALL(label)

def B(label):
    global PC
    PC = lookup(label)

def BT(label):
    global PC
    if SWITCH:
        PC = lookup(label)
   
def BF(label):
    global PC
    if not SWITCH:
        PC = lookup(label)
        
def CL(literal):
    OUTPUT_list.append(literal)

def CI():
    OUTPUT_list.append(RETVAL)

def END():
    PC = None # halt interpreter

def GEN():
    global GENINT_counter
    global RETVAL
    RETVAL = str(GENINT_counter)
    GENINT_counter += 1
    success()

#-------------------------------------------------
# Extra new instructions for better indentation

def TB():
    OUTPUT_list.append(4 * " ") 

def LMI():
    OUTPUT_list.append(4) 

def LMD():
    OUTPUT_list.append(-4) 

def NL():
    OUTPUT_list.append(0) 

#-------------------------------------------------
# Further instructions for showing/capturing results

def BRA():
    # LIKE CHECKPOINT()
    global OUTPUT_list
    EXPR_STACK.append(OUTPUT_list)
    OUTPUT_list = []

def KET():
    # LIKE COMMIT(), but preserves SWITCH and INPUT_position
    global OUTPUT_list
    consolidate_OUTPUT_list_to_RETVAL()
    OUTPUT_list = EXPR_STACK.pop()

def YIELD():
    OUTPUT_list.append(RETVAL)

def STORE(name):
    VARS_dict[name] = RETVAL

def show_place_of_error(message):   
    # This shows where we are NOW
    text = "... " + \
           INPUT[max(0, INPUT_position - 60):INPUT_position] + "\n" + \
           "***ERROR: "+ message + "\n***HERE:\n" + \
               INPUT[INPUT_position:INPUT_position + 60] + " ...\n"
    # ignore last stackframe
    while len(CALL_STACK) > 1:
        _, rule, _ = CALL_STACK.pop()
        text += "in <" + rule + "> "
    error(text)

def LOAD(name):
    global RETVAL
    if name in VARS_dict:
        RETVAL = VARS_dict[name]
    else:
        show_place_of_error("INTERNAL ERROR: No such variable: " + name)

# DEBUGGING
def NOP(what):
    pass

#-------------------------------------------------------
# The "assembler" instructions go here
PROGRAM = \
[
    (ADR, 'program'),
    'program',
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L3'),
    (LITERAL, 'BEGIN'),
    (BF, 'L3'),
    (COMMIT,),
    (B, 'L4'),
    'L3',
    (ROLLBACK,),
    'L4',
    (BF, 'L1'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L5'),
    (LITERAL, '<'),
    (BF, 'L5'),
    (COMMIT,),
    (B, 'L6'),
    'L5',
    (ROLLBACK,),
    'L6',
    (BF, 'L1'),
    (CALL, 'id'),
    (STORE, 'name'),
    (BF, 'L1'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L7'),
    (LITERAL, '>'),
    (BF, 'L7'),
    (COMMIT,),
    (B, 'L8'),
    'L7',
    (ROLLBACK,),
    'L8',
    (BF, 'L1'),
    (BRA,),
    (LMI,),
    (CL, '(ADR, \''),
    (LOAD, 'name'),
    (YIELD,),
    (CL, '\'),'),
    (NL,),
    (KET,),
    (YIELD,),
    'L9',
    (CALL, 'st'),
    (YIELD,),
    (BT, 'L9'),
    (SET,),
    (BF, 'L1'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L10'),
    (LITERAL, 'END'),
    (BF, 'L10'),
    (COMMIT,),
    (B, 'L11'),
    'L10',
    (ROLLBACK,),
    'L11',
    (BF, 'L1'),
    (BRA,),
    (CL, '(END,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L2'),
    'L1',
    (ROLLBACK,),
    'L2',
    'L12',
    (R,),
    'st',
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L15'),
    (LITERAL, '<'),
    (BF, 'L15'),
    (COMMIT,),
    (B, 'L16'),
    'L15',
    (ROLLBACK,),
    'L16',
    (BF, 'L13'),
    (CALL, 'ruleid'),
    (STORE, 'rule'),
    (BF, 'L13'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L17'),
    (LITERAL, '>'),
    (BF, 'L17'),
    (COMMIT,),
    (B, 'L18'),
    'L17',
    (ROLLBACK,),
    'L18',
    (BF, 'L13'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L19'),
    (LITERAL, '::='),
    (BF, 'L19'),
    (COMMIT,),
    (B, 'L20'),
    'L19',
    (ROLLBACK,),
    'L20',
    (BF, 'L13'),
    (CALL, 'ex1'),
    (STORE, 'body'),
    (BF, 'L13'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L21'),
    (LITERAL, ';'),
    (BF, 'L21'),
    (COMMIT,),
    (B, 'L22'),
    'L21',
    (ROLLBACK,),
    'L22',
    (BF, 'L13'),
    (BRA,),
    (CL, '\''),
    (LOAD, 'rule'),
    (YIELD,),
    (CL, '\','),
    (NL,),
    (LOAD, 'body'),
    (YIELD,),
    (CL, '(R,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L14'),
    'L13',
    (ROLLBACK,),
    'L14',
    'L23',
    (R,),
    'ex1',
    (CHECKPOINT,),
    (CALL, 'ex2'),
    (YIELD,),
    (BF, 'L24'),
    (BRA,),
    (CL, '\'L'),
    (GEN,),
    (YIELD,),
    (CL, '\''),
    (KET,),
    (STORE, 'label'),
    'L26',
    (BRA,),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L29'),
    (LITERAL, '|'),
    (BF, 'L29'),
    (COMMIT,),
    (B, 'L30'),
    'L29',
    (ROLLBACK,),
    'L30',
    (BF, 'L27'),
    (BRA,),
    (CL, '(BT, '),
    (LOAD, 'label'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (KET,),
    (YIELD,),
    (CALL, 'ex2'),
    (YIELD,),
    (BF, 'L27'),
    (COMMIT,),
    (YIELD,),
    (B, 'L28'),
    'L27',
    (ROLLBACK,),
    'L28',
    'L31',
    (KET,),
    (YIELD,),
    (BT, 'L26'),
    (SET,),
    (BF, 'L24'),
    (BRA,),
    (LOAD, 'label'),
    (YIELD,),
    (CL, ','),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L25'),
    'L24',
    (ROLLBACK,),
    'L25',
    'L32',
    (R,),
    'ex2',
    (CHECKPOINT,),
    (BRA,),
    (CL, '\'L'),
    (GEN,),
    (YIELD,),
    (CL, '\''),
    (KET,),
    (STORE, 'rollback'),
    (BRA,),
    (CL, '\'L'),
    (GEN,),
    (YIELD,),
    (CL, '\''),
    (KET,),
    (STORE, 'end'),
    (BRA,),
    (CL, '(CHECKPOINT,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (BRA,),
    (CHECKPOINT,),
    (CALL, 'ex3'),
    (YIELD,),
    (BF, 'L35'),
    (BRA,),
    (CL, '(BF, '),
    (LOAD, 'rollback'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L36'),
    'L35',
    (ROLLBACK,),
    'L36',
    (BT, 'L37'),
    (CHECKPOINT,),
    (CALL, 'output'),
    (YIELD,),
    (BF, 'L38'),
    (COMMIT,),
    (YIELD,),
    (B, 'L39'),
    'L38',
    (ROLLBACK,),
    'L39',
    'L37',
    (KET,),
    (YIELD,),
    (BF, 'L33'),
    'L40',
    (BRA,),
    (CHECKPOINT,),
    (CALL, 'ex3'),
    (YIELD,),
    (BF, 'L41'),
    (BRA,),
    (CL, '(BF, '),
    (LOAD, 'rollback'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L42'),
    'L41',
    (ROLLBACK,),
    'L42',
    (BT, 'L43'),
    (CHECKPOINT,),
    (CALL, 'output'),
    (YIELD,),
    (BF, 'L44'),
    (COMMIT,),
    (YIELD,),
    (B, 'L45'),
    'L44',
    (ROLLBACK,),
    'L45',
    'L43',
    (KET,),
    (YIELD,),
    (BT, 'L40'),
    (SET,),
    (BF, 'L33'),
    (BRA,),
    (CL, '(COMMIT,),'),
    (NL,),
    (CL, '(YIELD,),'),
    (NL,),
    (CL, '(B, '),
    (LOAD, 'end'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (LOAD, 'rollback'),
    (YIELD,),
    (CL, ','),
    (NL,),
    (CL, '(ROLLBACK,),'),
    (NL,),
    (LOAD, 'end'),
    (YIELD,),
    (CL, ','),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L34'),
    'L33',
    (ROLLBACK,),
    'L34',
    'L46',
    (R,),
    'ex3',
    (CHECKPOINT,),
    (CALL, 'quoted_symbol'),
    (YIELD,),
    (BF, 'L47'),
    (COMMIT,),
    (YIELD,),
    (B, 'L48'),
    'L47',
    (ROLLBACK,),
    'L48',
    (BT, 'L49'),
    (CHECKPOINT,),
    (CALL, 'ex3yield'),
    (YIELD,),
    (BF, 'L50'),
    (BRA,),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L54'),
    (LITERAL, ':'),
    (BF, 'L54'),
    (COMMIT,),
    (B, 'L55'),
    'L54',
    (ROLLBACK,),
    'L55',
    (BF, 'L52'),
    (CALL, 'id'),
    (STORE, 'id'),
    (BF, 'L52'),
    (BRA,),
    (CL, '(STORE, \''),
    (LOAD, 'id'),
    (YIELD,),
    (CL, '\'),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L53'),
    'L52',
    (ROLLBACK,),
    'L53',
    (BT, 'L56'),
    (CHECKPOINT,),
    (SET,),
    (YIELD,),
    (BF, 'L57'),
    (BRA,),
    (CL, '(YIELD,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L58'),
    'L57',
    (ROLLBACK,),
    'L58',
    'L56',
    (KET,),
    (YIELD,),
    (BF, 'L50'),
    (COMMIT,),
    (YIELD,),
    (B, 'L51'),
    'L50',
    (ROLLBACK,),
    'L51',
    (BT, 'L49'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L61'),
    (LITERAL, 'REPEAT'),
    (BF, 'L61'),
    (COMMIT,),
    (B, 'L62'),
    'L61',
    (ROLLBACK,),
    'L62',
    (BF, 'L59'),
    (BRA,),
    (CL, '\'L'),
    (GEN,),
    (YIELD,),
    (CL, '\''),
    (KET,),
    (STORE, 'label'),
    (BRA,),
    (LOAD, 'label'),
    (YIELD,),
    (CL, ','),
    (NL,),
    (KET,),
    (YIELD,),
    (CALL, 'ex3'),
    (YIELD,),
    (BF, 'L59'),
    (BRA,),
    (CL, '(BT, '),
    (LOAD, 'label'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (CL, '(SET,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L60'),
    'L59',
    (ROLLBACK,),
    'L60',
    'L49',
    (R,),
    'quoted_symbol',
    (CHECKPOINT,),
    (CALL, 'string'),
    (STORE, 's'),
    (BF, 'L63'),
    (BRA,),
    (CL, '\'L'),
    (GEN,),
    (YIELD,),
    (CL, '\''),
    (KET,),
    (STORE, 'rollback'),
    (BRA,),
    (CL, '\'L'),
    (GEN,),
    (YIELD,),
    (CL, '\''),
    (KET,),
    (STORE, 'end'),
    (BRA,),
    (CL, '(CHECKPOINT,),'),
    (NL,),
    (CL, '(CALL, \'*whitespace*\'),'),
    (NL,),
    (CL, '(BF, '),
    (LOAD, 'rollback'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (CL, '(LITERAL, '),
    (LOAD, 's'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (CL, '(BF, '),
    (LOAD, 'rollback'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (CL, '(COMMIT,),'),
    (NL,),
    (CL, '(B, '),
    (LOAD, 'end'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (LOAD, 'rollback'),
    (YIELD,),
    (CL, ','),
    (NL,),
    (CL, '(ROLLBACK,),'),
    (NL,),
    (LOAD, 'end'),
    (YIELD,),
    (CL, ','),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L64'),
    'L63',
    (ROLLBACK,),
    'L64',
    'L65',
    (R,),
    'ex3yield',
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L68'),
    (LITERAL, 'ANY_OF'),
    (BF, 'L68'),
    (COMMIT,),
    (B, 'L69'),
    'L68',
    (ROLLBACK,),
    'L69',
    (BF, 'L66'),
    (CALL, 'string'),
    (STORE, 's'),
    (BF, 'L66'),
    (BRA,),
    (CL, '(ANY_OF, '),
    (LOAD, 's'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L67'),
    'L66',
    (ROLLBACK,),
    'L67',
    (BT, 'L70'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L73'),
    (LITERAL, 'ANY_BUT'),
    (BF, 'L73'),
    (COMMIT,),
    (B, 'L74'),
    'L73',
    (ROLLBACK,),
    'L74',
    (BF, 'L71'),
    (CALL, 'string'),
    (STORE, 's'),
    (BF, 'L71'),
    (BRA,),
    (CL, '(ANY_BUT, '),
    (LOAD, 's'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L72'),
    'L71',
    (ROLLBACK,),
    'L72',
    (BT, 'L70'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L77'),
    (LITERAL, 'LITERAL'),
    (BF, 'L77'),
    (COMMIT,),
    (B, 'L78'),
    'L77',
    (ROLLBACK,),
    'L78',
    (BF, 'L75'),
    (CALL, 'string'),
    (STORE, 's'),
    (BF, 'L75'),
    (BRA,),
    (CL, '(LITERAL, '),
    (LOAD, 's'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L76'),
    'L75',
    (ROLLBACK,),
    'L76',
    (BT, 'L70'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L81'),
    (LITERAL, 'GEN'),
    (BF, 'L81'),
    (COMMIT,),
    (B, 'L82'),
    'L81',
    (ROLLBACK,),
    'L82',
    (BF, 'L79'),
    (BRA,),
    (CL, '(GEN,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L80'),
    'L79',
    (ROLLBACK,),
    'L80',
    (BT, 'L70'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L85'),
    (LITERAL, 'EMPTY'),
    (BF, 'L85'),
    (COMMIT,),
    (B, 'L86'),
    'L85',
    (ROLLBACK,),
    'L86',
    (BF, 'L83'),
    (BRA,),
    (CL, '(SET,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L84'),
    'L83',
    (ROLLBACK,),
    'L84',
    (BT, 'L70'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L89'),
    (LITERAL, '<'),
    (BF, 'L89'),
    (COMMIT,),
    (B, 'L90'),
    'L89',
    (ROLLBACK,),
    'L90',
    (BF, 'L87'),
    (CALL, 'ruleid'),
    (STORE, 'rule'),
    (BF, 'L87'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L91'),
    (LITERAL, '>'),
    (BF, 'L91'),
    (COMMIT,),
    (B, 'L92'),
    'L91',
    (ROLLBACK,),
    'L92',
    (BF, 'L87'),
    (BRA,),
    (CL, '(CALL, \''),
    (LOAD, 'rule'),
    (YIELD,),
    (CL, '\'),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L88'),
    'L87',
    (ROLLBACK,),
    'L88',
    (BT, 'L70'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L95'),
    (LITERAL, '('),
    (BF, 'L95'),
    (COMMIT,),
    (B, 'L96'),
    'L95',
    (ROLLBACK,),
    'L96',
    (BF, 'L93'),
    (CALL, 'ex1'),
    (STORE, 'e'),
    (BF, 'L93'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L97'),
    (LITERAL, ')'),
    (BF, 'L97'),
    (COMMIT,),
    (B, 'L98'),
    'L97',
    (ROLLBACK,),
    'L98',
    (BF, 'L93'),
    (BRA,),
    (CL, '(BRA,),'),
    (NL,),
    (LOAD, 'e'),
    (YIELD,),
    (CL, '(KET,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L94'),
    'L93',
    (ROLLBACK,),
    'L94',
    'L70',
    (R,),
    'output',
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L101'),
    (LITERAL, '{'),
    (BF, 'L101'),
    (COMMIT,),
    (B, 'L102'),
    'L101',
    (ROLLBACK,),
    'L102',
    (BF, 'L99'),
    (CALL, 'outlist'),
    (STORE, 'e'),
    (BF, 'L99'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L103'),
    (LITERAL, '}'),
    (BF, 'L103'),
    (COMMIT,),
    (B, 'L104'),
    'L103',
    (ROLLBACK,),
    'L104',
    (BF, 'L99'),
    (BRA,),
    (CL, '(BRA,),'),
    (NL,),
    (LOAD, 'e'),
    (YIELD,),
    (CL, '(KET,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (BRA,),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L107'),
    (LITERAL, ':'),
    (BF, 'L107'),
    (COMMIT,),
    (B, 'L108'),
    'L107',
    (ROLLBACK,),
    'L108',
    (BF, 'L105'),
    (CALL, 'id'),
    (STORE, 'id'),
    (BF, 'L105'),
    (BRA,),
    (CL, '(STORE, \''),
    (LOAD, 'id'),
    (YIELD,),
    (CL, '\'),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L106'),
    'L105',
    (ROLLBACK,),
    'L106',
    (BT, 'L109'),
    (CHECKPOINT,),
    (SET,),
    (YIELD,),
    (BF, 'L110'),
    (BRA,),
    (CL, '(YIELD,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L111'),
    'L110',
    (ROLLBACK,),
    'L111',
    'L109',
    (KET,),
    (YIELD,),
    (BF, 'L99'),
    (COMMIT,),
    (YIELD,),
    (B, 'L100'),
    'L99',
    (ROLLBACK,),
    'L100',
    'L112',
    (R,),
    'outlist',
    (CHECKPOINT,),
    'L115',
    (CALL, 'out1'),
    (YIELD,),
    (BT, 'L115'),
    (SET,),
    (BF, 'L113'),
    (COMMIT,),
    (YIELD,),
    (B, 'L114'),
    'L113',
    (ROLLBACK,),
    'L114',
    'L116',
    (R,),
    'out1',
    (CHECKPOINT,),
    (CALL, 'string'),
    (STORE, 's'),
    (BF, 'L117'),
    (BRA,),
    (CL, '(CL, '),
    (LOAD, 's'),
    (YIELD,),
    (CL, '),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L118'),
    'L117',
    (ROLLBACK,),
    'L118',
    (BT, 'L119'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L122'),
    (LITERAL, 'NL'),
    (BF, 'L122'),
    (COMMIT,),
    (B, 'L123'),
    'L122',
    (ROLLBACK,),
    'L123',
    (BF, 'L120'),
    (BRA,),
    (CL, '(NL,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L121'),
    'L120',
    (ROLLBACK,),
    'L121',
    (BT, 'L119'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L126'),
    (LITERAL, 'TAB'),
    (BF, 'L126'),
    (COMMIT,),
    (B, 'L127'),
    'L126',
    (ROLLBACK,),
    'L127',
    (BF, 'L124'),
    (BRA,),
    (CL, '(TB,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L125'),
    'L124',
    (ROLLBACK,),
    'L125',
    (BT, 'L119'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L130'),
    (LITERAL, 'INDENT'),
    (BF, 'L130'),
    (COMMIT,),
    (B, 'L131'),
    'L130',
    (ROLLBACK,),
    'L131',
    (BF, 'L128'),
    (BRA,),
    (CL, '(LMI,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L129'),
    'L128',
    (ROLLBACK,),
    'L129',
    (BT, 'L119'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L134'),
    (LITERAL, 'OUTDENT'),
    (BF, 'L134'),
    (COMMIT,),
    (B, 'L135'),
    'L134',
    (ROLLBACK,),
    'L135',
    (BF, 'L132'),
    (BRA,),
    (CL, '(LMD,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L133'),
    'L132',
    (ROLLBACK,),
    'L133',
    (BT, 'L119'),
    (CHECKPOINT,),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (BF, 'L138'),
    (LITERAL, 'GEN'),
    (BF, 'L138'),
    (COMMIT,),
    (B, 'L139'),
    'L138',
    (ROLLBACK,),
    'L139',
    (BF, 'L136'),
    (BRA,),
    (CL, '(GEN,),'),
    (NL,),
    (CL, '(YIELD,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L137'),
    'L136',
    (ROLLBACK,),
    'L137',
    (BT, 'L119'),
    (CHECKPOINT,),
    (CALL, 'id'),
    (STORE, 'id'),
    (BF, 'L140'),
    (BRA,),
    (CL, '(LOAD, \''),
    (LOAD, 'id'),
    (YIELD,),
    (CL, '\'),'),
    (NL,),
    (CL, '(YIELD,),'),
    (NL,),
    (KET,),
    (YIELD,),
    (COMMIT,),
    (YIELD,),
    (B, 'L141'),
    'L140',
    (ROLLBACK,),
    'L141',
    'L119',
    (R,),
    'ruleid',
    (CHECKPOINT,),
    (CALL, 'id'),
    (YIELD,),
    (BF, 'L142'),
    (COMMIT,),
    (YIELD,),
    (B, 'L143'),
    'L142',
    (ROLLBACK,),
    'L143',
    (BT, 'L144'),
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (YIELD,),
    (BF, 'L145'),
    (LITERAL, '*whitespace*'),
    (YIELD,),
    (BF, 'L145'),
    (COMMIT,),
    (YIELD,),
    (B, 'L146'),
    'L145',
    (ROLLBACK,),
    'L146',
    'L144',
    (R,),
    'lower',
    (CHECKPOINT,),
    (ANY_OF, 'abcdefghijklmnopqrstuvwxyz'),
    (YIELD,),
    (BF, 'L147'),
    (COMMIT,),
    (YIELD,),
    (B, 'L148'),
    'L147',
    (ROLLBACK,),
    'L148',
    'L149',
    (R,),
    'upper',
    (CHECKPOINT,),
    (ANY_OF, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
    (YIELD,),
    (BF, 'L150'),
    (COMMIT,),
    (YIELD,),
    (B, 'L151'),
    'L150',
    (ROLLBACK,),
    'L151',
    'L152',
    (R,),
    'digit',
    (CHECKPOINT,),
    (ANY_OF, '0123456789'),
    (YIELD,),
    (BF, 'L153'),
    (COMMIT,),
    (YIELD,),
    (B, 'L154'),
    'L153',
    (ROLLBACK,),
    'L154',
    'L155',
    (R,),
    'id',
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (YIELD,),
    (BF, 'L156'),
    (BRA,),
    (CHECKPOINT,),
    (CALL, 'lower'),
    (YIELD,),
    (BF, 'L158'),
    (COMMIT,),
    (YIELD,),
    (B, 'L159'),
    'L158',
    (ROLLBACK,),
    'L159',
    (BT, 'L160'),
    (CHECKPOINT,),
    (CALL, 'upper'),
    (YIELD,),
    (BF, 'L161'),
    (COMMIT,),
    (YIELD,),
    (B, 'L162'),
    'L161',
    (ROLLBACK,),
    'L162',
    (BT, 'L160'),
    (CHECKPOINT,),
    (LITERAL, '_'),
    (YIELD,),
    (BF, 'L163'),
    (COMMIT,),
    (YIELD,),
    (B, 'L164'),
    'L163',
    (ROLLBACK,),
    'L164',
    'L160',
    (KET,),
    (YIELD,),
    (BF, 'L156'),
    'L165',
    (BRA,),
    (CHECKPOINT,),
    (CALL, 'lower'),
    (YIELD,),
    (BF, 'L166'),
    (COMMIT,),
    (YIELD,),
    (B, 'L167'),
    'L166',
    (ROLLBACK,),
    'L167',
    (BT, 'L168'),
    (CHECKPOINT,),
    (CALL, 'upper'),
    (YIELD,),
    (BF, 'L169'),
    (COMMIT,),
    (YIELD,),
    (B, 'L170'),
    'L169',
    (ROLLBACK,),
    'L170',
    (BT, 'L168'),
    (CHECKPOINT,),
    (LITERAL, '_'),
    (YIELD,),
    (BF, 'L171'),
    (COMMIT,),
    (YIELD,),
    (B, 'L172'),
    'L171',
    (ROLLBACK,),
    'L172',
    (BT, 'L168'),
    (CHECKPOINT,),
    (CALL, 'digit'),
    (YIELD,),
    (BF, 'L173'),
    (COMMIT,),
    (YIELD,),
    (B, 'L174'),
    'L173',
    (ROLLBACK,),
    'L174',
    'L168',
    (KET,),
    (YIELD,),
    (BT, 'L165'),
    (SET,),
    (BF, 'L156'),
    (COMMIT,),
    (YIELD,),
    (B, 'L157'),
    'L156',
    (ROLLBACK,),
    'L157',
    'L175',
    (R,),
    'number',
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (YIELD,),
    (BF, 'L176'),
    (CALL, 'digit'),
    (YIELD,),
    (BF, 'L176'),
    'L178',
    (CALL, 'digit'),
    (YIELD,),
    (BT, 'L178'),
    (SET,),
    (BF, 'L176'),
    (COMMIT,),
    (YIELD,),
    (B, 'L177'),
    'L176',
    (ROLLBACK,),
    'L177',
    'L179',
    (R,),
    'hex_digit',
    (CHECKPOINT,),
    (CALL, 'digit'),
    (YIELD,),
    (BF, 'L180'),
    (COMMIT,),
    (YIELD,),
    (B, 'L181'),
    'L180',
    (ROLLBACK,),
    'L181',
    (BT, 'L182'),
    (CHECKPOINT,),
    (ANY_OF, 'abcdefABCDEF'),
    (YIELD,),
    (BF, 'L183'),
    (COMMIT,),
    (YIELD,),
    (B, 'L184'),
    'L183',
    (ROLLBACK,),
    'L184',
    'L182',
    (R,),
    'hex',
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (YIELD,),
    (BF, 'L185'),
    (CALL, 'hex_digit'),
    (YIELD,),
    (BF, 'L185'),
    'L187',
    (CALL, 'hex_digit'),
    (YIELD,),
    (BT, 'L187'),
    (SET,),
    (BF, 'L185'),
    (COMMIT,),
    (YIELD,),
    (B, 'L186'),
    'L185',
    (ROLLBACK,),
    'L186',
    'L188',
    (R,),
    'string_escape',
    (CHECKPOINT,),
    (LITERAL, '\\'),
    (YIELD,),
    (BF, 'L189'),
    (BRA,),
    (CHECKPOINT,),
    (ANY_OF, '\\\'\"abfnrtv0'),
    (YIELD,),
    (BF, 'L191'),
    (COMMIT,),
    (YIELD,),
    (B, 'L192'),
    'L191',
    (ROLLBACK,),
    'L192',
    (BT, 'L193'),
    (CHECKPOINT,),
    (LITERAL, 'u'),
    (YIELD,),
    (BF, 'L194'),
    (CALL, 'hex_digit'),
    (YIELD,),
    (BF, 'L194'),
    (CALL, 'hex_digit'),
    (YIELD,),
    (BF, 'L194'),
    (CALL, 'hex_digit'),
    (YIELD,),
    (BF, 'L194'),
    (CALL, 'hex_digit'),
    (YIELD,),
    (BF, 'L194'),
    (COMMIT,),
    (YIELD,),
    (B, 'L195'),
    'L194',
    (ROLLBACK,),
    'L195',
    'L193',
    (KET,),
    (YIELD,),
    (BF, 'L189'),
    (COMMIT,),
    (YIELD,),
    (B, 'L190'),
    'L189',
    (ROLLBACK,),
    'L190',
    'L196',
    (R,),
    'string',
    (CHECKPOINT,),
    (CALL, '*whitespace*'),
    (YIELD,),
    (BF, 'L197'),
    (LITERAL, '\''),
    (YIELD,),
    (BF, 'L197'),
    'L199',
    (BRA,),
    (CHECKPOINT,),
    (CALL, 'string_escape'),
    (YIELD,),
    (BF, 'L200'),
    (COMMIT,),
    (YIELD,),
    (B, 'L201'),
    'L200',
    (ROLLBACK,),
    'L201',
    (BT, 'L202'),
    (CHECKPOINT,),
    (ANY_BUT, '\''),
    (YIELD,),
    (BF, 'L203'),
    (COMMIT,),
    (YIELD,),
    (B, 'L204'),
    'L203',
    (ROLLBACK,),
    'L204',
    'L202',
    (KET,),
    (YIELD,),
    (BT, 'L199'),
    (SET,),
    (BF, 'L197'),
    (LITERAL, '\''),
    (YIELD,),
    (BF, 'L197'),
    (COMMIT,),
    (YIELD,),
    (B, 'L198'),
    'L197',
    (ROLLBACK,),
    'L198',
    'L205',
    (R,),
    '*whitespace*',
    (CHECKPOINT,),
    (BRA,),
    (CHECKPOINT,),
    'L210',
    (BRA,),
    (CHECKPOINT,),
    (ANY_OF, ' \t\n\r\u000b\u000c'),
    (YIELD,),
    (BF, 'L211'),
    (COMMIT,),
    (YIELD,),
    (B, 'L212'),
    'L211',
    (ROLLBACK,),
    'L212',
    (BT, 'L213'),
    (CHECKPOINT,),
    (CALL, 'comment'),
    (YIELD,),
    (BF, 'L214'),
    (COMMIT,),
    (YIELD,),
    (B, 'L215'),
    'L214',
    (ROLLBACK,),
    'L215',
    'L213',
    (KET,),
    (YIELD,),
    (BT, 'L210'),
    (SET,),
    (BF, 'L208'),
    (COMMIT,),
    (YIELD,),
    (B, 'L209'),
    'L208',
    (ROLLBACK,),
    'L209',
    'L216',
    (KET,),
    (STORE, 'ignore'),
    (BF, 'L206'),
    (COMMIT,),
    (YIELD,),
    (B, 'L207'),
    'L206',
    (ROLLBACK,),
    'L207',
    'L217',
    (R,),
    'comment',
    (CHECKPOINT,),
    (LITERAL, '#'),
    (YIELD,),
    (BF, 'L218'),
    'L220',
    (BRA,),
    (CHECKPOINT,),
    (ANY_BUT, '\n\r'),
    (YIELD,),
    (BF, 'L221'),
    (COMMIT,),
    (YIELD,),
    (B, 'L222'),
    'L221',
    (ROLLBACK,),
    'L222',
    'L223',
    (KET,),
    (YIELD,),
    (BT, 'L220'),
    (SET,),
    (BF, 'L218'),
    (COMMIT,),
    (YIELD,),
    (B, 'L219'),
    'L218',
    (ROLLBACK,),
    'L219',
    'L224',
    (R,),
    (END,),
]

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


    
