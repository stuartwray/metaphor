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
