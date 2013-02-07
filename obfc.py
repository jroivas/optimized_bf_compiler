#!/usr/bin/env python

import sys
import os

__cmds = ['<', '>', '+', '-', '.', ',', '[', ']']

from backends.c import CBackend

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

    oname = os.path.basename(fname)
    oname = oname.lower().replace('.bf', '')
    oname = oname.lower().replace('.b', '')
    backend = CBackend(oname)

    backend.translate(idata, iblocks)
    backend.write()
    backend.compile()
    res = backend.binaryName()
    print res

if __name__ == '__main__':
    main()
