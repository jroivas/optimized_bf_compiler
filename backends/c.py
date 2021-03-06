import os
#from backend.backend import Backend
from backend import Backend
#from backend import vmops.VmOps
import vmops

class CBackend(Backend):
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
        inc += '#include <stdio.h>\n'
        inc += '#include <stdlib.h>\n'
        inc += '/* Use some initial memory size */\n'
        inc += 'unsigned int mem_size = 1000000;\n'
        inc += '%s *mem = 0;\n' % (self.__mem_type)
        inc += '/* Check if we need to increment memory size */\n'
        inc += 'static %s *guard_mem(%s *ptr) {\n' % (self.__mem_type, self.__mem_type)
        inc += '    unsigned int diff = ptr-mem;\n'
        inc += '    if (diff>mem_size) {\n'
        inc += '        mem_size = diff + 1000;\n'
        inc += '        mem = realloc(mem, mem_size);\n'
        inc += '        return mem + diff;\n'
        inc += '    }\n'
        inc += '    return ptr;\n'
        inc += '}\n'
        prefix = '    '
        for b in blocks:
            methods += '%s *%s%s(%s *ptr);\n' % (self.__mem_type, self.__call_prefix, b, self.__mem_type)
            res.append('%s *%s%s(%s *ptr) {' % (self.__mem_type, self.__call_prefix, b, self.__mem_type))
            res += self.translace_c_block(blocks[b], prefix)
            res.append(prefix + 'return ptr;')
            res.append('}')

        res = '\n'.join(res) + '\n'
        res += 'int main(int argc, char **argv) {\n'
        res += prefix + 'mem = (%s*)calloc(1, mem_size);\n' % (self.__mem_type)
        res += prefix + '%s *ptr = mem + 1000;\n' % (self.__mem_type)
        res += '\n'.join(self.translace_c_block(data, prefix)) + '\n'
        res += prefix + 'free(mem);\n'
        res += prefix + 'return 0;\n'
        res += '}\n'

        self.code = inc + methods + res

    def translace_c_block(self, data, prefix='  '):
        closed = 0
        #res = ''
        lines = []
        orig_prefix = prefix
        for (d, c) in data:
            if d == vmops.VmOps.INC_PTR:
                if c == 0:
                    pass
                elif c == 1:
                    lines.append(prefix + '++ptr;')
                    # Guards help to resize memory in case of owerflow
                    #res += prefix + 'ptr = guard_mem(ptr);\n'
                elif c == -1:
                    lines.append(prefix + '--ptr;')
                else:
                    lines.append(prefix + 'ptr += %s;' % (c))
                    # Guards help to resize memory in case of owerflow
                    #res += prefix + 'ptr = guard_mem(ptr);\n'
            elif d == vmops.VmOps.INC_VAL:
                if c == 0:
                    pass
                elif c == 1:
                    lines.append(prefix + '++(*ptr);')
                elif c == -1:
                    lines.append(prefix + '--(*ptr);')
                else:
                    lines.append(prefix + '(*ptr) += %s;' % (c))
            elif d == vmops.VmOps.ADD_PTR:
                if c[0] != 0:
                    if c[1] == 1:
                        lines.append(prefix + '++ptr[%s];' % (c[0]))
                    elif c[1] == -1:
                        lines.append(prefix + '--ptr[%s];' % (c[0]))
                    else:
                        lines.append(prefix + 'ptr[%s] += %s;' % (c[0], c[1]))
            elif d == vmops.VmOps.PLUS_MUL:
                lines.append(prefix + 'ptr[%s] += ptr[%s] * %s;' % c)
            elif d == vmops.VmOps.SET_VAL:
                lines.append(prefix + 'ptr[%s] = %s;' % c)
            elif d == vmops.VmOps.OUT_VAL:
                lines.append(prefix + 'putchar(*ptr);')
            elif d == vmops.VmOps.INP_VAL:
                lines.append(prefix + '*ptr = getchar();')
            elif d == vmops.VmOps.LOOP_START:
                lines.append(prefix + 'while (*ptr) {')
                prefix += orig_prefix
                closed += 1
            elif d == vmops.VmOps.LOOP_IF:
                lines.append(prefix + 'if (*ptr) {')
                prefix += orig_prefix
                closed += 1
            elif d == vmops.VmOps.LOOP_END:
                prefix = prefix[:-1]
                lines.append(prefix + '}')
                closed -= 1
            elif d[0] == vmops.VmOps.BLOCK:
                lines.append(prefix + 'ptr = %s%s(ptr);' % (self.__call_prefix, d[1:]))
        while closed > 0:
            lines.append(prefix + '}')
            closed -= 1
        return lines

    def compile(self):
        oname_bin = self.src_name.replace('.c', '')
        os.system('gcc -O3 %s -o %s' % (self.src_name, oname_bin))
        self.binary_name = oname_bin

    def write(self):
        onamec = self.name + '.c'
        fd = open(onamec, 'w')
        fd.write(self.code)
        fd.close()
        self.src_name = onamec
