#!/usr/bin/env python

import sys
import os
import argparse
import importlib

from backends.vmops import VmOps

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
        if d in VmOps.CMDS:
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
        if d == VmOps.LOOP_START:
            starts.append(i)
        elif d == VmOps.LOOP_END:
            if not starts:
                raise ValueError('Block end without a start! @%s' % (i))
            start = starts.pop()
            end = i
            block = data[start:end+1]
            tmp = is_block(block, blocks)
            if block == [VmOps.LOOP_START, VmOps.DEC_VAL, VmOps.LOOP_END]:
                middle = ['%s0' % (VmOps.SET_VAL)]
            elif tmp is None:
                blocks[bid] = block
                middle = ['%s%s' % (VmOps.BLOCK, bid)]
                bid += 1
            else:
                middle = ['%s%s' % (VmOps.BLOCK, tmp)]
            newdata = data[:start] + middle + data[end+1:]
            data = newdata
            starts = []
            i = -1
        i += 1
        if i >= len(data):
            break

    return (data, blocks)

def optimize_adds(data, i, dlen):
    d = data[i]
    val = 0
    while d == VmOps.INC_VAL or d == VmOps.DEC_VAL:
        if d == VmOps.INC_VAL:
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
    while d == VmOps.INC_PTR or d == VmOps.DEC_PTR:
        if d == VmOps.INC_PTR:
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
    values = {}
    for (d, c) in data:
        prev = d
        if d == VmOps.INC_VAL:
            val += c
        elif d == VmOps.INC_PTR:
            if val != 0:
                if offs != 0:
                    newcode.append((VmOps.ADD_PTR, (offs, val)))
                else:
                    newcode.append((VmOps.INC_VAL, val))
                    orig_change = True
                values[origoff + offs] = values.get(origoff + offs, 0) + val
            offs += c
            val = 0
        elif d == '=':
            if val != 0:
                if offs != 0:
                    newcode.append((VmOps.ADD_PTR, (offs, val)))
                else:
                    newcode.append((VmOps.INC_VAL, val))
                    orig_change = True
            val = 0

            values = {}
            newcode.append((d, (c[0]+offs, c[1])))
        elif d == VmOps.LOOP_START:
            pass
        elif d == VmOps.LOOP_END:
            if offs != 0:
                newcode.append((VmOps.INC_PTR, offs))
                orig_change = True
                origoff += offs
                offs = 0
        else:
            return data

    if val != 0:
        newcode.append((VmOps.INC_VAL, val))
        values[origoff + offs] = values.get(origoff + offs, 0) + val
        if offs == 0:
            orig_change = True

    if values and offs == 0 and values.get(0,0) == -1:
        values.pop(0)
        if values:
            newcode = []
            for off in values:
                newcode.append( (VmOps.PLUS_MUL, (off, 0, values[off])))
            newcode.append((VmOps.SET_VAL, (0, 0)))
            return newcode

    if data[0][0] == VmOps.LOOP_START:
        if not orig_change:
            newcode.insert(0, (VmOps.LOOP_IF,''))
            newcode.append((VmOps.LOOP_END,''))
        else:
            newcode.insert(0, (VmOps.LOOP_START,''))
            newcode.append((VmOps.LOOP_END,''))

    return newcode

def optimize_loops_1(data):
    if data == [(VmOps.LOOP_START, ''), (VmOps.INC_VAL, -1), (VmOps.LOOP_END, '')]:
        return [(VmOps.SET_VAL, (0, 0))]
    if data == [(VmOps.LOOP_IF, ''), (VmOps.LOOP_END, '')]:
        return []
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
        if d == VmOps.INC_VAL or d == VmOps.DEC_VAL:
            (val, i) = optimize_adds(data, i, dlen)
            imm.append((VmOps.INC_VAL, val))
        elif d == VmOps.INC_PTR or d == VmOps.DEC_PTR:
            (val, i) = optimize_ptrs(data, i, dlen)
            imm.append((VmOps.INC_PTR, val))
        elif d == VmOps.OUT_VAL:
            imm.append((VmOps.OUT_VAL, ''))
            i += 1
        elif d == VmOps.INP_VAL:
            imm.append((VmOps.INP_VAL, ''))
            i += 1
        elif d == VmOps.LOOP_START:
            imm.append((VmOps.LOOP_START, ''))
            i += 1
        elif d == VmOps.LOOP_END:
            imm.append((VmOps.LOOP_END, ''))
            i += 1
        elif d[0] == VmOps.BLOCK:
            imm.append((d, ''))
            i += 1
        elif d == '%s0' % (VmOps.SET_VAL):
            imm.append((VmOps.SET_VAL, (0, 0)))
            i += 1

        if i >= dlen:
            break

    imm = optimize_simple_adds(imm)
    return imm

def merge_small_block(block, small_ones):
    tmp = []
    for (d, c) in block:
        ok = False
        if d[0] == VmOps.BLOCK:
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
        if d[0] == VmOps.BLOCK:
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

def get_backend(oname, flags):
    name = flags['backend']
    fdir = os.path.dirname(__file__)
    backend_dir = os.path.join(fdir, 'backends')
    files = os.listdir(backend_dir)
    for f in files:
        if f.endswith('.py') and f != '__init__.py' and f != 'backend.py':
            fname = f.replace('.py', '')
            if fname == name:
                mod = importlib.import_module('backends')
                findname = name + 'backend'
                for item in dir(mod):
                    if findname == item.lower():
                        constr = getattr(mod, item)
                        return constr(oname, flags)

    return None


def main():
    parser = argparse.ArgumentParser(description='Optimizing BrainFuck compiler')
    parser.add_argument('-w', '--word-size', action='store', default='1', help='Define word size in bytes, default 1')
    parser.add_argument('--backend', action='store', default='c', help='Define backend, default "c"')
    parser.add_argument('-o', '--output', action='store', default=None, help='Output file name')
    parser.add_argument('file', action='store', default=None, help='BrainFuck source file')

    if len(sys.argv) <= 1:
        parser.print_help()

    args = parser.parse_args()
    flags = vars(args)

    fname = flags['file']
    data = read(fname)
    if data is None:
        print ('\nERROR: File not found: %s\n' % (fname))
        sys.exit(1)
    parsed = parse(data)
    (data, blocks) = detect_loops(parsed)
    (idata, iblocks) = immediate(data, blocks)
    (idata, iblocks) = optimize_loops(idata, iblocks)
    (idata, iblocks) = merge_small_blocks(idata, iblocks)

    if flags['output'] is None:
        oname = os.path.basename(fname)
        oname = oname.lower().replace('.bf', '')
        oname = oname.lower().replace('.b', '')
    else:
        oname = flags['output']
    #backend = CBackend(oname, flags)
    backend = get_backend(oname, flags)
    if backend == None:
        print ('Backend not found: %s' % (flags['backend']))
        sys.exit(1)

    backend.translate(idata, iblocks)
    backend.write()
    backend.compile()
    res = backend.binaryName()
    print (res)

if __name__ == '__main__':
    main()
