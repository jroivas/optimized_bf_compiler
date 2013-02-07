import os

class CBackend:
    __call_prefix = '__func_call_'
    __mem_type = 'unsigned int'

    def __init__(self, name):
        self.code = None
        self.binary_name = None
        self.src_name = None
        self.name = name

    def translate(self, data, blocks):
        res = ''
        methods = ''
        inc = ''
        inc += '#include <stdio.h>\n'
        inc += '#include <stdlib.h>\n'
        inc += '/* Use some initial memory size */\n'
        inc += 'unsigned int mem_size = 10000;\n'
        inc += '%s *mem = 0;\n' % (self.__mem_type)
        inc += '/* Check if we need to increment memory size */\n'
        inc += 'static %s *guard_mem(%s *ptr) {\n' % (self.__mem_type, self.__mem_type)
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
            methods += '%s *%s%s(%s *ptr);\n' % (self.__mem_type, self.__call_prefix, b, self.__mem_type)
            res += '%s *%s%s(%s *ptr) {\n' % (self.__mem_type, self.__call_prefix, b, self.__mem_type)
            res += self.translace_c_block(blocks[b], prefix)
            res += prefix + 'return ptr;\n'
            res += '}\n'
        
        res += 'int main(unsigned int argc, char **argv) {\n'
        res += prefix + 'mem = (%s*)calloc(1, mem_size);\n' % (self.__mem_type)
        res += prefix + '%s *ptr = mem;\n' % (self.__mem_type)
        res += self.translace_c_block(data, prefix)
        res += prefix + 'free(mem);\n'
        res += prefix + 'return 0;\n'
        res += '}\n'

        self.code = inc + methods + res

    def translace_c_block(self, data, prefix='  '):
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
                res += prefix + 'ptr = %s%s(ptr);\n' % (self.__call_prefix, d[1:])
        while closed > 0:
            res += prefix + '}\n'
            closed -= 1
        return res


    def compile(self):
        oname_bin = self.src_name.replace('.c', '')
        oname_bin += '.bin'
        os.system('gcc -O3 %s -o %s' % (self.src_name, oname_bin))
        self.binary_name = oname_bin

    def binaryName(self):
        return self.binary_name

    def write(self):
        onamec = self.name + '_compiled.c'
        fd = open(onamec, 'w')
        fd.write(self.code)
        fd.close()
        self.src_name = onamec
