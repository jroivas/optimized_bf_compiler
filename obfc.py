#!/usr/bin/env python

import sys
import os

__cmds = ['<', '>', '+', '-', '.', ',', '[', ']']
__call_prefix = '__func_call_'
__mem_type = 'unsigned int'

def read(fname):
    try:
        fd = open(fname, 'r')
        res = fd.read()
        fd.close()
    except:
        res = None
    return res

def parse(data):
    cmds = []
    for d in data:
        if d in __cmds:
            cmds.append(d)
    return cmds

def is_block(data, blocks):
    for b in blocks:
        if data == blocks[b]:
            return b
    return None

def detect_loops(data):
    blocks = {}
    i = 0
    starts = []
    #for d in data:
    bid = 0
    while True:
        d = data[i]
        if d == '[':
            starts.append(i)
        elif d == ']':
            if not starts:
                raise ValueError('Block end without a start! @%s' % (i))
            start = starts.pop()
            end = i
            block = data[start:end+1]
            tmp = is_block(block, blocks)
            if tmp is None:
                blocks[bid] = block
                middle = ['b%s' % (bid)]
                bid += 1
            else:
                middle = ['b%s' % (tmp)]
                #print tmp
                #bid = tmp
            newdata = data[:start] + middle + data[end+1:]
            data = newdata
            #print block
            #print newdata
            starts = []
            i = -1
        i += 1
        if i >= len(data):
            break

    return (data, blocks)

def optimize_adds(data, i, dlen):
    d = data[i]
    val = 0
    while d == '+' or d == '-':
        if d == '+':
            val += 1
        else:
            val -= 1
        i += 1
        if i >= dlen:
            break
        d = data[i]
    return (val, i)

def optimize_ptrs(data, i, dlen):
    d = data[i]
    val = 0
    while d == '>' or d == '<':
        if d == '>':
            val += 1
        else:
            val -= 1
        i += 1
        if i >= dlen:
            break
        d = data[i]
    return (val, i)

def bf_compile(data):
    imm = []
    i = 0
    dlen = len(data)
    while True:
        d = data[i]
        if d == '+' or d == '-':
            (val, i) = optimize_adds(data, i, dlen)
            if val < 0:
                imm.append(('-', -1 * val))
            else:
                imm.append(('+', val))
        elif d == '>' or d == '<':
            (val, i) = optimize_ptrs(data, i, dlen)
            if val < 0:
                imm.append(('<', -1 * val))
            else:
                imm.append(('>', val))
        elif d == '.':
            imm.append(('.', ''))
            i += 1
        elif d == ',':
            imm.append((',', ''))
            i += 1
        elif d == '[':
            imm.append(('[', ''))
            i += 1
        elif d == ']':
            imm.append((']', ''))
            i += 1
        elif d[0] == 'b':
            imm.append((d, ''))
            i += 1

        if i >= dlen:
            break
    return imm

def immediate(data, blocks):
    imm_blocks = {}
    for b in blocks:
        imm_blocks[b] = bf_compile(blocks[b])
    data = bf_compile(data)
    return (data, imm_blocks)

def compile_c_block(data, prefix='  '):
    closed = 0
    res = ''
    for d, c in data:
        if d == '>':
            if c == 1:
                res += prefix + '++ptr;\n'
                # Guards help to resize memory in case of owerflow
                #res += prefix + 'ptr = guard_mem(ptr);\n'
            else:
                res += prefix + 'ptr += %s;\n' % (c)
                # Guards help to resize memory in case of owerflow
                #res += prefix + 'ptr = guard_mem(ptr);\n'
        elif d == '<':
            if c == 1:
                res += prefix + '--ptr;\n'
            else:
                res += prefix + 'ptr -= %s;\n' % (c)
        elif d == '+':
            if c == 1:
                res += prefix + '++(*ptr);\n'
            else:
                res += prefix + '(*ptr) += %s;\n' % (c)
        elif d == '-':
            if c == 1:
                res += prefix + '--(*ptr);\n'
            else:
                res += prefix + '(*ptr) -= %s;\n' % (c)
        elif d == '.':
            res += prefix + 'putchar(*ptr);\n'
            res += prefix + 'fflush(stdout);\n'
            #res += prefix + 'printf("%d\\n", *ptr);\n'
        elif d == ',':
            res += prefix + '*ptr = getchar();\n'
        elif d == '[':
            res += prefix + 'while (*ptr) {\n'
            prefix = prefix + prefix
            closed += 1
        elif d == ']':
            prefix = prefix[:-1]
            res += prefix + '}\n'
            closed -= 1
        elif d[0] == 'b':
            res += prefix + 'ptr = %s%s(ptr);\n' % (__call_prefix, d[1:])
    while closed > 0:
        res += prefix + '}\n'
        closed -= 1
    return res

def compile_c(data, blocks):
    res = ''
    methods = ''
    inc = ''
    inc += '#include <stdio.h>\n'
    inc += '#include <stdlib.h>\n'
    inc += '/* Use some initial memory size */\n'
    inc += 'unsigned int mem_size = 10000;\n'
    inc += '%s *mem = 0;\n' % (__mem_type)
    inc += '/* Check if we need to increment memory size */\n'
    inc += 'static %s *guard_mem(%s *ptr) {\n' % (__mem_type, __mem_type)
    inc += '\tunsigned int diff = ptr-mem;\n'
    inc += '\tif (diff>mem_size) {\n'
    inc += '\t\tmem_size = diff + 1000;\n'
    inc += '\t\tmem = realloc(mem, mem_size);\n'
    inc += '\t\treturn mem + diff;\n'
    inc += '\t}\n'
    inc += '\treturn ptr;\n'
    inc += '}\n'
    prefix = '\t'
    for b in blocks:
        methods += '%s *%s%s(%s *ptr);\n' % (__mem_type, __call_prefix, b, __mem_type)
        res += '%s *%s%s(%s *ptr) {\n' % (__mem_type, __call_prefix, b, __mem_type)
        res += compile_c_block(blocks[b], prefix)
        res += prefix + 'return ptr;\n'
        res += '}\n'
    
    res += 'int main(unsigned int argc, char **argv) {\n'
    res += prefix + 'mem = (%s*)calloc(1, mem_size);\n' % (__mem_type)
    res += prefix + '%s *ptr = mem;\n' % (__mem_type)
    res += compile_c_block(data, prefix)
    res += prefix + 'free(mem);\n'
    res += prefix + 'return 0;\n'
    res += '}\n'

    return inc + methods + res

def write_c(oname, cdata):
    onamec = oname + '_compiled.c'
    fd = open(onamec, 'w')
    fd.write(cdata)
    fd.close()
    return onamec

def compile_bin(oname):
    oname_bin = oname.replace('.c', '')
    oname_bin += '.bin'
    os.system('gcc -O3 %s -o %s' % (oname, oname_bin))
    return oname_bin

def main():
    if len(sys.argv) <= 1:
        print ('Usage: %s source.b' % (sys.argv[0]))
        sys.exit(1)

    fname = sys.argv[1]
    data = read(fname)
    if data is None:
        print ('\nERROR: File not found: %s\n' % (fname))
        sys.exit(1)
    parsed = parse(data)
    (data, blocks) = detect_loops(parsed)
    (idata, iblocks) = immediate(data, blocks)
    cdata = compile_c(idata, iblocks)
    oname = os.path.basename(fname)
    oname = oname.lower().replace('.bf', '')
    oname = oname.lower().replace('.b', '')
    oname_bin = write_c(oname, cdata)
    res = compile_bin(oname_bin)
    print ('Output: %s' % (res))

if __name__ == '__main__':
    main()
