#!/usr/bin/python3

import sys
import string
import re
import os

# runtime for the AEXP example 

#--------------------------------------------------------

def error(*args):
    print(*args)
    sys.exit(1)

#--------------------------------------------------------
# Supporting functions

PC = 0
ENV = {}
STACK = []

def STORE(var):
    n = STACK.pop()
    ENV[var] = n

def ADD():
    b = STACK.pop()
    a = STACK.pop()
    STACK.append(a + b)

def SUB():
    b = STACK.pop()
    a = STACK.pop()
    STACK.append(a - b)
    
def MUL():
    b = STACK.pop()
    a = STACK.pop()
    STACK.append(a * b)
    
def DIV():
    b = STACK.pop()
    a = STACK.pop()
    STACK.append(a / b)
    
def EXP():
    b = STACK.pop()
    a = STACK.pop()
    STACK.append(a ** b)

def NEG():
    a = STACK.pop()
    STACK.append(-a)
    
def LOAD(var):
    STACK.append(ENV[var])

def LITERAL(number):
    STACK.append(number)

#-------------------------------------------------------
# The program, using those functions, goes here:


