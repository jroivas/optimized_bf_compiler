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

def optimize_simple_adds(data):
    offs = 0
    val = 0
    newcode = []
    prev = ''
    origoff = 0
    orig_change = False
    for (d, c) in data:
        prev = d
        if d == '+':
            val += c
        elif d == '>':
            if val != 0:
                if offs != 0:
                    newcode.append(('+p', (offs, val)))
                else:
                    newcode.append(('+', val))
                    orig_change = True
            offs += c
            val = 0
        elif d == '[':
            pass
        elif d == ']':
            if offs != 0:
                newcode.append(('>', offs))
                orig_change = True
                origoff -= offs
                offs = 0
        else:
            return data

    if val != 0:
        newcode.append(('+', val))
        if offs == 0:
            orig_change = True

    if data[0][0] == '[':
        if not orig_change:
            newcode.insert(0, ('[if',''))
            newcode.append((']',''))
        else:
            newcode.insert(0, ('[',''))
            newcode.append((']',''))

    return newcode

def optimize_loops_1(data):
    if data == [('[', ''), ('+', -1), (']', '')]:
        return [('=', '0')]
    return data

def optimize_loops(data, blocks):
    for b in blocks:
        blocks[b] = optimize_loops_1(blocks[b])
    return (data, blocks)

def bf_compile(data):
    imm = []
    i = 0
    dlen = len(data)
    while True:
        d = data[i]
        if d == '+' or d == '-':
            (val, i) = optimize_adds(data, i, dlen)
            imm.append(('+', val))
        elif d == '>' or d == '<':
            (val, i) = optimize_ptrs(data, i, dlen)
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

    imm = optimize_simple_adds(imm)
    return imm

def merge_small_block(block, small_ones):
    tmp = []
    for (d, c) in block:
        ok = False
        if d[0] == 'b':
            num = int(d[1:])
            if num in small_ones:
                tmp += small_ones[num]
                ok = True
        if not ok:
            tmp.append((d, c))

    return tmp

def sub_block_cnt(data):
    cnt = 0
    for (d, c) in data:
        if d[0] == 'b':
            cnt += 1

    return cnt

def merge_small_blocks(data, blocks):
    small_ones = {}
    big_ones = {}
    for b in blocks:
        if len(blocks[b]) <= 4 and sub_block_cnt(blocks[b]) == 0:
            small_ones[b] = blocks[b]
        else:
            big_ones[b] = blocks[b]

    newblocks = {}
    for b in big_ones:
        newblocks[b] = merge_small_block(big_ones[b], small_ones)
    newdata = merge_small_block(data, small_ones)

    return (newdata, newblocks)
                    
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
    (idata, iblocks) = optimize_loops(idata, iblocks)
    (idata, iblocks) = merge_small_blocks(idata, iblocks)

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
