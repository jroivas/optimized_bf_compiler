import os
from backends.backend import Backend

class RPythonBackend(Backend):
    __call_prefix = '__func_call_'

    def __init__(self, name, flags):
        self.code = None
        self.binary_name = None
        self.src_name = None
        self.name = name
        self.flags = flags
        ws = self.flags['word_size']
        if ws == '2':
            self.__mem_type = 'unsigned short'
        elif ws == '4' or ws == '3':
            self.__mem_type = 'unsigned int'
        elif ws == '8':
            self.__mem_type = 'unsigned long long'
        else:
            self.__mem_type = 'unsigned char'

    def translate(self, data, blocks):
        res = []
        methods = ''
        inc = ''

        inc += 'import os\n'
        inc += 'import sys\n'
        inc += """
try:
    from pypy.rlib.jit import JitDriver, purefunction
except ImportError:
    class JitDriver(object):
        def __init__(self,**kw): pass
        def jit_merge_point(self,**kw): pass
        def can_enter_jit(self,**kw): pass
    def purefunction(f): return f

jitdriver = JitDriver(greens=['ptr'], reds=['mem'])

"""

        prefix = '  '
        for b in blocks:
            res.append('def %s%s(mem, ptr):' % (self.__call_prefix, b))
            res += self.translace_c_block(blocks[b], prefix)
            res.append(prefix + 'return ptr')
        res = '\n'.join(res) + '\n'
        res += 'def run():\n'
        res += prefix + 'mem = [0] * 1000\n'
        res += prefix + 'ptr = 100\n'
        res += '\n'.join(self.translace_c_block(data, prefix)) + '\n'

        res += """
def entry_point(argv):
  run()
  return 0

def target(*args):
  return entry_point, None

if __name__ == '__main__':
  run()  
"""

        self.code = inc + methods + res

    def translace_c_block(self, data, prefix='  '):
        closed = 0
        lines = []
        orig_prefix = prefix
        got_jit = False
        for (d, c) in data:
            if d == '>':
                if c == 0:
                    pass
                else:
                    lines.append(prefix + 'ptr += %s' % (c))
            elif d == '+':
                if c == 0:
                    pass
                else:
                    lines.append(prefix + 'while ptr + 100 > len(mem):')
                    lines.append(prefix + prefix + 'mem.append(0)')
                    lines.append(prefix + 'mem[ptr] += %s' % (c))
            elif d == '+p':
                if c[0] != 0:
                    lines.append(prefix + 'mem[ptr + %s] += %s' % c)
            elif d == '+*':
                lines.append(prefix + 'mem[ptr + %s] += mem[ptr + %s] * %s' % c)
            elif d == '=':
                lines.append(prefix + 'mem[ptr + %s] = %s' % c)
            elif d == '.':
                lines.append(prefix + 'os.write(1, chr(mem[ptr]))')
            elif d == ',':
                lines.append(prefix + 'mem[ptr] = ord(os.read(0, 1)[0])')
            elif d == '[':
                lines.append(prefix + 'while mem[ptr] != 0:')
                prefix += orig_prefix
                if not got_jit:
                    lines.append(prefix + 'jitdriver.jit_merge_point(ptr=ptr, mem=mem) ')
                    got_jit = True
                closed += 1
            elif d == '[if':
                lines.append(prefix + 'if mem[ptr] != 0:')
                prefix += orig_prefix
                closed += 1
            elif d == ']':
                prefix = prefix[:-len(orig_prefix)]
                closed -= 1
            elif d[0] == 'b':
                lines.append(prefix + 'ptr = %s%s(mem, ptr);' % (self.__call_prefix, d[1:]))
        while closed > 0:
            closed -= 1
        return lines

    def compile(self):
        self.binary_name = self.src_name

    def write(self):
        onamec = self.name + '.py'
        fd = open(onamec, 'w')
        fd.write(self.code)
        fd.close()
        self.src_name = onamec
