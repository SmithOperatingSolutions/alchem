#!/usr/bin/env python3
"""Translate a runtime routine's x86-64 assembly (GNU as, Intel syntax, as
spec/*-x86_64.s are written) into ARM64 assembly for GNU as, under the
machine model of spec/arm64.md: every x86-64 register has an ARM64 one, the
stack is X28, a call leaves its return address on that stack, and flags are
set only where an instruction after reads them.

    x86-to-arm64.py spec/memory-x86_64.s > memory.arm64.s

The x86-64 source stays the one source of a routine; this is how its ARM64
version is made (scripts/generate-*-runtime.py --arm64). Assembly marks what
is code and what is data, so a routine's data is copied and its code
translated instruction by instruction; an instruction the translator does not
know stops it with the line, rather than making something that might run.

Scratch registers: X16 and X17 for addresses and operands, X19 to X27 for
values inside one instruction; X30 is the link register.
"""
import re
import sys

REG64 = ['rax', 'rcx', 'rdx', 'rbx', 'rsp', 'rbp', 'rsi', 'rdi'] + [f'r{i}' for i in range(8, 16)]
REG32 = ['eax', 'ecx', 'edx', 'ebx', 'esp', 'ebp', 'esi', 'edi'] + [f'r{i}d' for i in range(8, 16)]
REG16 = ['ax', 'cx', 'dx', 'bx', 'sp', 'bp', 'si', 'di'] + [f'r{i}w' for i in range(8, 16)]
REG8 = ['al', 'cl', 'dl', 'bl', 'spl', 'bpl', 'sil', 'dil'] + [f'r{i}b' for i in range(8, 16)]
ARM = [0, 1, 2, 3, 28, 29, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15]
SIZES = {'byte': 1, 'word': 2, 'dword': 4, 'qword': 8, 'xmmword': 16, 'oword': 16}
# Condition codes by x86 suffix: (ARM condition after a subtraction or
# comparison, after an addition or logic, which differ for the carry).
CONDS = {
    'e': ('eq', 'eq'), 'z': ('eq', 'eq'), 'ne': ('ne', 'ne'), 'nz': ('ne', 'ne'),
    's': ('mi', 'mi'), 'ns': ('pl', 'pl'), 'o': ('vs', 'vs'), 'no': ('vc', 'vc'),
    'l': ('lt', 'lt'), 'nge': ('lt', 'lt'), 'ge': ('ge', 'ge'), 'nl': ('ge', 'ge'),
    'le': ('le', 'le'), 'ng': ('le', 'le'), 'g': ('gt', 'gt'), 'nle': ('gt', 'gt'),
    'b': ('lo', 'hs'), 'c': ('lo', 'hs'), 'nae': ('lo', 'hs'),
    'ae': ('hs', 'lo'), 'nc': ('hs', 'lo'), 'nb': ('hs', 'lo'),
    'be': ('ls', None), 'na': ('ls', None), 'a': ('hi', None), 'nbe': ('hi', None),
    'p': ('vs', 'vs'), 'pe': ('vs', 'vs'), 'np': ('vc', 'vc'), 'po': ('vc', 'vc'),
}
INVERT = {'eq': 'ne', 'ne': 'eq', 'hs': 'lo', 'lo': 'hs', 'mi': 'pl', 'pl': 'mi', 'vs': 'vc', 'vc': 'vs',
          'hi': 'ls', 'ls': 'hi', 'ge': 'lt', 'lt': 'ge', 'gt': 'le', 'le': 'gt'}
JCC = {'j' + s for s in CONDS} | {'jrcxz', 'jecxz'}
SETCC = {'set' + s for s in CONDS}
CMOVCC = {'cmov' + s for s in CONDS}
# Instructions that read the flags, and those that set them all (x86's
# inc and dec keep the carry; they are counted as setting them).
# ret counts as reading them all: a routine may leave its caller flags
# (bn_cmp), which leave it in a subtraction's sense.
READS = JCC | SETCC | CMOVCC | {'adc', 'sbb', 'rcl', 'rcr', 'ret'}
WRITES = {'add', 'sub', 'cmp', 'test', 'and', 'or', 'xor', 'neg', 'inc', 'dec', 'shl', 'sal', 'shr', 'sar',
          'imul', 'mul', 'bt', 'bts', 'btr', 'btc', 'bsr', 'bsf', 'ucomisd', 'comisd', 'adc', 'sbb', 'cmpsb',
          'ror', 'rol', 'shrd', 'shld', 'div', 'idiv', 'popcnt', 'lzcnt', 'tzcnt', 'rcl', 'rcr'}


# Every reader of the carry, those of C and Z with it (ja, jbe...).
CARRY_USERS = None
CARRY_READERS = {'jc', 'jnc', 'jb', 'jae', 'jnb', 'jnae', 'adc', 'sbb', 'setc', 'setnc', 'setb', 'setae', 'cmovc',
                 'cmovnc', 'cmovb', 'cmovae', 'rcl', 'rcr'}
CARRY_USERS = CARRY_READERS | {p + c for p in ('j', 'set', 'cmov') for c in ('a', 'be', 'na', 'nbe', 'nb', 'nae')} | {'ret'}


# 128-bit SSE (the TLS runtime) on NEON's V registers.
VECTOR = {'movdqa', 'movdqu', 'pand', 'por', 'pandn', 'pslld', 'psrld', 'psllq', 'psrlq', 'pslldq', 'psrldq',
          'pshufd', 'pshufb', 'pcmpgtb', 'pcmpeqb', 'paddb', 'paddd', 'paddq', 'psubb', 'psubd', 'aesenc', 'aesenclast',
          'aesdec', 'aesdeclast', 'aesimc', 'pclmulqdq'}


# The entry's words (from 0x400420) and the table of functions (from
# 0x400480, at most 65541 slots).
BLOCK = 0x400420
BLOCK_END = 0x400480 + 65541 * 8


class Untranslated(Exception):
    pass


# A list to collect what does not translate in, instead of stopping (for
# surveying a runtime); None normally.
MISSING = None


class Operand:
    def __init__(self, kind, **fields):
        self.kind = kind
        self.__dict__.update(fields)

    def __repr__(self):
        return f'{self.kind}{self.__dict__}'


class Translator:
    def __init__(self):
        self.symbols = {}
        self.out = []
        self.carry = 'sub'      # what the flags came from: 'sub' (carry is a borrow) or 'add'
        self.direction = 1      # x86's DF: 1 forward, -1 back (cld, std)
        self.count = 0

    # ---- operands ----
    def value(self, text):
        """The number an expression of numbers and .set symbols is, or None."""
        expr = text.strip()
        if not expr:
            return None
        def name(m):
            word = m.group(0)
            if word in self.symbols:
                return str(self.symbols[word])
            raise KeyError(word)
        try:
            python = re.sub(r'\b0x[0-9a-fA-F]+\b|\b[A-Za-z_.][A-Za-z_0-9.]*\b',
                            lambda m: m.group(0) if m.group(0).startswith('0x') else name(m), expr)
            if re.search(r'[^0-9xa-fA-F+\-*/()<>|&~ ]', python):
                return None
            python = python.replace('/', '//')
            return int(eval(python, {'__builtins__': {}}))
        except (KeyError, SyntaxError, NameError, ValueError, TypeError):
            return None

    def operand(self, text):
        text = text.strip()
        size = None
        m = re.match(r'(byte|word|dword|qword|xmmword|oword)\s+ptr\s+(.*)$', text)
        if m:
            size = SIZES[m.group(1)]
            text = m.group(2).strip()
        if text.startswith('['):
            return self.memory(text[1:-1], size)
        low = text.lower()
        for table, bits in ((REG64, 8), (REG32, 4), (REG16, 2), (REG8, 1)):
            if low in table:
                return Operand('reg', r=ARM[table.index(low)], size=bits, x86=table.index(low))
        if re.fullmatch(r'xmm\d+', low):
            return Operand('xmm', r=int(low[3:]), size=16)
        number = self.value(text)
        if number is not None:
            return Operand('imm', v=number, size=size)
        return Operand('label', name=text, size=size)

    def memory(self, inner, size):
        base = index = None
        scale = 1
        disp_terms = []
        label = None
        addr32 = False      # an address of 32-bit registers (lea r8d,[eax+edx])
        for sign, term in re.findall(r'([+-]?)\s*([^+-]+)', inner.replace(' ', '')):
            low = term.lower()
            if low == 'rip':
                base = 'rip'
                continue
            m = re.fullmatch(r'([a-z0-9]+)\*(\d+)', low)
            for table in (REG64, REG32):
                if m and m.group(1) in table:
                    index, scale = ARM[table.index(m.group(1))], int(m.group(2))
                    addr32 |= table is REG32
                    break
                if low in table:
                    if base is None:
                        base = ARM[table.index(low)]
                    else:
                        index = ARM[table.index(low)]
                    addr32 |= table is REG32
                    break
            else:
                table = None
            if table is not None:
                if sign == '-':
                    raise Untranslated(f'memory operand [{inner}]')
                continue
            v = self.value(term)
            if v is None:
                if sign == '-':
                    raise Untranslated(f'memory operand [{inner}]')
                label = term
                continue
            disp_terms.append(-v if sign == '-' else v)
        if label is not None and base != 'rip':
            raise Untranslated(f'memory operand [{inner}]')
        return Operand('mem', base=base, index=index, scale=scale, disp=sum(disp_terms), label=label, size=size,
                       addr32=addr32)

    # ---- emission ----
    def emit(self, *lines):
        self.out.extend(' ' + line for line in lines)

    def label(self):
        self.count += 1
        return f'.Lx{self.count}'

    def mov_imm(self, reg, value, width=64):
        """reg = value with movz/movn/movk."""
        mask = (1 << width) - 1
        v = value & mask
        name = f'{"x" if width == 64 else "w"}{reg}'
        chunks = [(v >> (16 * i)) & 0xffff for i in range(width // 16)]
        ones = sum(1 for c in chunks if c == 0xffff)
        zeros = sum(1 for c in chunks if c == 0)
        if ones > zeros:
            first = next((i for i, c in enumerate(chunks) if c != 0xffff), 0)
            self.emit(f'movn {name},#{(~chunks[first]) & 0xffff},lsl #{16 * first}')
            for i, c in enumerate(chunks):
                if i != first and c != 0xffff:
                    self.emit(f'movk {name},#{c},lsl #{16 * i}')
        else:
            first = next((i for i, c in enumerate(chunks) if c != 0), 0)
            self.emit(f'movz {name},#{chunks[first]},lsl #{16 * first}')
            for i, c in enumerate(chunks):
                if i != first and c != 0:
                    self.emit(f'movk {name},#{c},lsl #{16 * i}')

    def in_block(self, value):
        """An address among the entry's words and the table, which a
        position-independent program (PIC defined) reads from their copy at
        X26 (spec/arm64.md)."""
        return 'PIC' in self.symbols and value is not None and BLOCK <= value < BLOCK_END

    def block_address(self, reg, value):
        self.mov_imm(reg, value - BLOCK)
        self.emit(f'add x{reg},x{reg},x26')

    def address(self, op, size):
        """An ARM address for a memory operand: '[xN, #d]' or '[x16]'."""
        if op.base == 'rip':
            target = op.label + (f'+{op.disp}' if op.disp else '')
            self.emit(f'adr x16,{target}')
            return '[x16]'
        if op.label is not None or op.addr32:
            raise Untranslated('memory operand with a label or a 32-bit address')
        base = op.base
        disp = op.disp
        if op.index is not None:
            shift = {1: 0, 2: 1, 4: 2, 8: 3}[op.scale]
            if base is None:
                self.emit(f'lsl x16,x{op.index},#{shift}')
            else:
                self.emit(f'add x16,x{base},x{op.index},lsl #{shift}')
            base = 16
        elif base is None:
            if self.in_block(disp):
                self.block_address(16, disp)
                return '[x16]'
            self.mov_imm(16, disp)
            return '[x16]'
        if base == 16 and self.in_block(disp):
            # An index into the table: X16 holds the index scaled.
            self.mov_imm(17, disp - BLOCK)
            self.emit('add x16,x16,x17', 'add x16,x16,x26')
            return '[x16]'
        if -256 <= disp <= 255 or (0 <= disp <= 4095 * size and disp % size == 0):
            return f'[x{base},#{disp}]'
        self.mov_imm(17, disp)
        self.emit(f'add x16,x{base},x17')
        return '[x16]'

    def load(self, dst, op, size, signed=False):
        """Register dst (an ARM number) = the operand, zero- or sign-extended to 64 bits."""
        if op.kind == 'reg':
            self.copy_reg(dst, op.r, op.size, signed)
            return
        if op.kind == 'imm':
            self.mov_imm(dst, op.v)
            return
        if op.kind == 'mem':
            where = self.address(op, size)
            if size == 8:
                self.emit(f'ldr x{dst},{where}')
            elif size == 4:
                self.emit(f'ldrsw x{dst},{where}' if signed else f'ldr w{dst},{where}')
            elif size == 2:
                self.emit(f'ldrsh x{dst},{where}' if signed else f'ldrh w{dst},{where}')
            elif size == 1:
                self.emit(f'ldrsb x{dst},{where}' if signed else f'ldrb w{dst},{where}')
            else:
                raise Untranslated(f'load of {size} bytes')
            return
        if op.kind == 'label':
            self.emit(f'adr x{dst},{op.name}')
            return
        raise Untranslated(f'operand {op}')

    def copy_reg(self, dst, src, size, signed=False):
        if size == 8:
            if dst != src:
                self.emit(f'mov x{dst},x{src}')
        elif size == 4:
            self.emit(f'sxtw x{dst},w{src}' if signed else f'mov w{dst},w{src}')
        elif size == 2:
            self.emit(f'sxth x{dst},w{src}' if signed else f'uxth w{dst},w{src}')
        else:
            self.emit(f'sxtb x{dst},w{src}' if signed else f'uxtb w{dst},w{src}')

    def store(self, op, src, size):
        """The operand = register src (its low size bytes)."""
        if op.kind == 'reg':
            if op.size == 8:
                if op.r != src:
                    self.emit(f'mov x{op.r},x{src}')
            elif op.size == 4:
                self.emit(f'mov w{op.r},w{src}')
            else:
                self.emit(f'bfxil x{op.r},x{src},#0,#{op.size * 8}')
            return
        if op.kind == 'mem':
            where = self.address(op, size)
            letter = {8: 'str x', 4: 'str w', 2: 'strh w', 1: 'strb w'}[size]
            self.emit(f'{letter}{src},{where}')
            return
        raise Untranslated(f'store to {op}')

    def size_of(self, ops):
        for op in ops:
            if op.kind in ('reg', 'xmm') and op.kind == 'reg':
                return op.size
        for op in ops:
            if getattr(op, 'size', None):
                return op.size
        return 8

    def condition(self, suffix):
        """ARM conditions for x86 condition suffix after the current flags:
        a list, any of which holds (two for ja/jbe after an addition)."""
        if self.carry == 'fp':
            # After ucomisd: x86's CF is less or unordered, ZF equal or
            # unordered, PF unordered; ARM's fcmp gives lt (N!=V) for less or
            # unordered, vs for unordered.
            fp = {'a': ['gt'], 'nbe': ['gt'], 'ae': ['ge'], 'nb': ['ge'], 'nc': ['ge'], 'b': ['lt'], 'c': ['lt'],
                  'nae': ['lt'], 'be': ['le'], 'na': ['le'], 'e': ['eq', 'vs'], 'z': ['eq', 'vs'], 'p': ['vs'],
                  'pe': ['vs'], 'np': ['vc'], 'po': ['vc'], 'ne': [('vc', 'ne')], 'nz': [('vc', 'ne')]}
            if suffix not in fp:
                raise Untranslated(f'condition {suffix} after a floating-point comparison')
            return fp[suffix]
        sub, add = CONDS[suffix]
        if self.carry == 'sub':
            return [sub]
        if add is not None:
            return [add]
        # After an addition or logic the carry is ARM's own: ja is C clear and
        # Z clear, jbe is C set or Z set.
        return ['hs', 'eq'] if suffix in ('be', 'na') else [('lo', 'ne')]

    # ---- instructions ----
    def instruction(self, mnemonic, ops, flags_needed):
        m = mnemonic
        size = self.size_of(ops)
        if m in ('nop',):
            return
        if m == 'mov':
            dst, src = ops
            if dst.kind == 'xmm' or src.kind == 'xmm':
                return self.sse(m, ops)
            if dst.kind == 'reg':
                if src.kind == 'reg' and dst.size == 8:
                    self.copy_reg(dst.r, src.r, 8)
                elif src.kind == 'imm' and dst.size >= 4:
                    self.mov_imm(dst.r, src.v, 64 if dst.size == 8 else 32)
                else:
                    self.load(19, src, dst.size)
                    self.store(dst, 19, dst.size)
                return
            size = dst.size or (src.size if src.kind == 'reg' else 8)
            if src.kind == 'reg':
                self.store(dst, src.r, size)
            else:
                self.load(19, src, size)
                self.store(dst, 19, size)
            return
        if m in ('movabs',):
            return self.instruction('mov', ops, flags_needed)
        if m in ('movzx', 'movsx', 'movsxd'):
            dst, src = ops
            src_size = src.size if src.kind == 'reg' else (src.size or (4 if m == 'movsxd' else 1))
            self.load(19, src, src_size, signed=(m != 'movzx'))
            self.store(dst, 19, dst.size)
            return
        if m == 'lea':
            dst, src = ops
            if src.base == 'rip':
                self.emit(f'adr x19,{src.label}' + (f'+{src.disp}' if src.disp else ''))
            else:
                self.lea(19, src)
                if src.addr32:
                    # The address is computed in 32 bits.
                    self.emit('mov w19,w19')
            self.store(dst, 19, dst.size)
            return
        if m in ('add', 'sub', 'and', 'or', 'xor', 'adc', 'sbb'):
            return self.arith(m, ops, flags_needed)
        if m == 'cmp':
            a, b = ops
            self.load(19, a, size)
            self.operand_reg(20, b, size)
            self.narrow(size, 19, 20)
            self.emit(f'cmp {self.r(19, size)},{self.r(20, size)}')
            self.carry = 'sub'
            return
        if m == 'test':
            a, b = ops
            self.load(19, a, size)
            self.operand_reg(20, b, size)
            self.narrow(size, 19, 20)
            self.emit(f'tst {self.r(19, size)},{self.r(20, size)}')
            self.carry = 'add'
            return
        if m in ('inc', 'dec'):
            (a,) = ops
            self.load(19, a, size)
            op = 'adds' if m == 'inc' else 'subs'
            if not flags_needed:
                self.emit(f'{op[:3]} {self.r(19, size)},{self.r(19, size)},#1')
                self.store(a, 19, size)
                return
            # x86's inc and dec keep the carry: ARM's C is put back into the
            # flags they set and keeps its sense (where the flags came from),
            # so that a path that skips one reads it the same. After a
            # floating-point comparison it is made an addition's.
            fp = self.carry == 'fp'
            self.emit('cset x22,lt' if fp else 'mrs x22,nzcv')
            if size < 4:
                self.emit(f'mov w20,#{1 << (32 - 8 * size)}')
                self.narrow(size, 19)
                self.emit(f'{op} w19,w19,w20', f'lsr w19,w19,#{32 - 8 * size}')
            else:
                self.emit(f'{op} {self.r(19, size)},{self.r(19, size)},#1')
            if not fp:
                self.emit('lsr x22,x22,#29')
            self.emit('mrs x23,nzcv', 'bfi x23,x22,#29,#1', 'msr nzcv,x23')
            self.store(a, 19, size)
            if fp:
                self.carry = 'add'
            return
        if m == 'neg':
            (a,) = ops
            self.load(19, a, size)
            if flags_needed and size < 4:
                self.narrow(size, 19)
                self.emit('negs w19,w19', f'lsr w19,w19,#{32 - 8 * size}')
            else:
                self.emit(f'negs {self.r(19, size)},{self.r(19, size)}')
            self.store(a, 19, size)
            self.carry = 'sub'
            return
        if m == 'not':
            (a,) = ops
            self.load(19, a, size)
            self.emit(f'mvn {self.r(19, size)},{self.r(19, size)}')
            self.store(a, 19, size)
            return
        if m in ('shl', 'sal', 'shr', 'sar', 'ror', 'rol'):
            return self.shift(m, ops, size, flags_needed)
        if m in ('shrd', 'shld'):
            return self.double_shift(m, ops)
        if m == 'imul':
            return self.imul(ops, size, flags_needed)
        if m == 'mul':
            (src,) = ops
            self.operand_reg(20, src, size)
            if size != 8:
                raise Untranslated('mul of 32 bits')
            self.emit('umulh x19,x0,x20', 'mul x0,x0,x20', 'mov x2,x19')
            if flags_needed:
                self.emit('cmp x2,#0', 'cset x21,ne')
                self.overflow_from('x21')
            return
        if m in ('div', 'idiv'):
            return self.divide(m, ops, size)
        if m == 'push':
            (a,) = ops
            if a.kind == 'reg':
                self.emit(f'str x{a.r},[x28,#-8]!')
            else:
                self.load(19, a, 8)
                self.emit('str x19,[x28,#-8]!')
            return
        if m == 'pop':
            (a,) = ops
            if a.kind == 'reg':
                self.emit(f'ldr x{a.r},[x28],#8')
            else:
                self.emit('ldr x19,[x28],#8')
                self.store(a, 19, 8)
            return
        if m == 'call':
            (a,) = ops
            back = self.label()
            if a.kind == 'label':
                self.emit(f'adr x30,{back}', 'str x30,[x28,#-8]!', f'b {a.name}')
            else:
                self.load(17, a, 8)
                self.emit(f'adr x30,{back}', 'str x30,[x28,#-8]!', 'br x17')
            self.out.append(f'{back}:')
            # The flags a routine leaves are in a subtraction's sense.
            self.carry = 'sub'
            return
        if m == 'ret':
            if self.carry == 'add':
                self.emit('mrs x22,nzcv', 'eor x22,x22,#0x20000000', 'msr nzcv,x22')
                self.carry = 'sub'
            if ops:
                self.emit('ldr x30,[x28],#8', f'add x28,x28,#{ops[0].v}', 'br x30')
            else:
                self.emit('ldr x30,[x28],#8', 'br x30')
            return
        if m == 'leave':
            self.emit('mov x28,x29', 'ldr x29,[x28],#8')
            return
        if m == 'jmp':
            (a,) = ops
            if a.kind == 'label':
                self.emit(f'b {a.name}')
            else:
                self.load(17, a, 8)
                self.emit('br x17')
            return
        if m in ('loop', 'loope', 'loopne'):
            # RCX counted down without the flags; loope and loopne also by Z.
            (a,) = ops
            self.emit('sub x1,x1,#1')
            if m == 'loop':
                self.emit(f'cbnz x1,{a.name}')
            else:
                skip = self.label()
                self.emit(f'cbz x1,{skip}', f'b.{"eq" if m == "loope" else "ne"} {a.name}')
                self.out.append(f'{skip}:')
            return
        if m in JCC:
            (a,) = ops
            if m in ('jrcxz', 'jecxz'):
                self.emit(f'cbz {"x1" if m == "jrcxz" else "w1"},{a.name}')
                return
            for c in self.condition(m[1:]):
                if isinstance(c, tuple):
                    skip = self.label()
                    self.emit(f'b.{INVERT[c[0]]} {skip}', f'b.{c[1]} {a.name}')
                    self.out.append(f'{skip}:')
                else:
                    self.emit(f'b.{c} {a.name}')
            return
        if m in SETCC:
            (a,) = ops
            self.flag_value(19, m[3:])
            self.store(a, 19, 1 if a.kind == 'mem' else a.size)
            return
        if m in CMOVCC:
            # By csel alone, so the flags stay for what reads them after.
            dst, src = ops
            self.load(19, src, dst.size)
            r = lambda n: self.r(n, dst.size)
            conds = self.condition(m[4:])
            c = conds[0]
            if isinstance(c, tuple):
                self.emit(f'csel {r(24)},{r(19)},{r(dst.r)},{c[1]}', f'csel {r(dst.r)},{r(24)},{r(dst.r)},{c[0]}')
            elif len(conds) == 2:
                self.emit(f'csel {r(24)},{r(19)},{r(dst.r)},{conds[1]}', f'csel {r(dst.r)},{r(19)},{r(24)},{conds[0]}')
            else:
                self.emit(f'csel {r(dst.r)},{r(19)},{r(dst.r)},{c}')
            return
        if m == 'xchg':
            a, b = ops
            self.load(19, a, size)
            self.load(20, b, size)
            self.store(a, 20, size)
            self.store(b, 19, size)
            return
        if m in ('bt', 'bts', 'btr', 'btc'):
            return self.bit_test(m, ops, size)
        if m in ('bsr', 'bsf'):
            dst, src = ops
            self.load(20, src, size)
            if m == 'bsr':
                self.emit(f'clz {self.r(19, size)},{self.r(20, size)}', f'mov x21,#{size * 8 - 1}', 'sub x19,x21,x19')
            else:
                self.emit(f'rbit {self.r(19, size)},{self.r(20, size)}', f'clz {self.r(19, size)},{self.r(19, size)}')
            skip = self.label()
            self.emit(f'cbz {self.r(20, size)},{skip}')
            self.store(dst, 19, dst.size)
            self.out.append(f'{skip}:')
            self.emit(f'cmp {self.r(20, size)},#0')
            self.carry = 'sub'
            return
        if m == 'cld':
            self.direction = 1
            return
        if m == 'std':
            self.direction = -1
            return
        if m.startswith('rep') or m in ('movsb', 'movsq', 'movsd_string', 'stosb', 'stosq', 'stosd', 'cmpsb'):
            return self.string(m, ops)
        if m == 'syscall':
            back = self.label()
            self.emit(f'adr x30,{back}', 'b x86_syscall')
            self.out.append(f'{back}:')
            return
        if m == 'ud2':
            self.emit('udf #0')
            return
        if m == 'int3':
            self.emit('brk #0')
            return
        if m in ('movq', 'movd', 'movsd', 'ucomisd', 'comisd', 'addsd', 'subsd', 'mulsd', 'divsd', 'sqrtsd',
                 'cvtsi2sd', 'cvttsd2si', 'cvtsd2si', 'xorpd', 'andpd', 'orpd', 'xorps', 'movapd', 'movaps', 'movups',
                 'pxor', 'vaddsd', 'vfmadd213sd', 'vfmadd231sd', 'vfmadd132sd', 'vfnmadd231sd', 'vfnmadd213sd', 'vfmsub231sd', 'vfmsub213sd', 'vfmsub132sd', 'vfnmsub231sd',
                 'cmpnltsd', 'cmpltsd', 'cmplesd', 'cmpnlesd', 'cmpeqsd'):
            return self.sse(m, ops)
        if m in VECTOR:
            return self.vector(m, ops)
        if m == 'clc':
            # CF = 0: an addition of nothing leaves C clear.
            self.emit('adds xzr,xzr,xzr')
            self.carry = 'add'
            return
        if m == 'stc':
            self.emit('subs xzr,xzr,xzr')
            self.carry = 'add'
            return
        if m == 'rcl':
            # Through the carry, by 1: (x << 1) | CF, CF = the bit out: adcs x, x, x.
            dst, count = ops
            if count.kind != 'imm' or count.v != 1:
                raise Untranslated('rcl by other than 1')
            if self.carry == 'sub':
                self.emit('cset x21,lo', 'cmp x21,#1')
            self.load(19, dst, size)
            self.emit(f'adcs {self.r(19, size)},{self.r(19, size)},{self.r(19, size)}')
            self.store(dst, 19, size)
            self.carry = 'add'
            return
        if m == 'rcr':
            # Through the carry, by 1: (x >> 1) | CF << top, CF = bit 0.
            dst, count = ops
            if count.kind != 'imm' or count.v != 1:
                raise Untranslated('rcr by other than 1')
            self.emit(f'cset x21,{"lo" if self.carry == "sub" else "hs"}')
            self.load(19, dst, size)
            a = self.r(19, size)
            self.emit(f'and x22,x19,#1', f'lsr {a},{a},#1', f'orr {a},{a},{self.r(21, size)},lsl #{size * 8 - 1}')
            self.store(dst, 19, size)
            self.emit('cmp x22,#1')
            self.carry = 'add'
            return
        if m == 'bswap':
            (a,) = ops
            self.emit(f'rev {self.r(a.r, a.size)},{self.r(a.r, a.size)}')
            return
        if m == 'cpuid':
            # The features asked of leaf 1 that ARM64 has an equivalent of: FMA
            # (bit 12 of ECX), OSXSAVE (27), AVX (28) always; AES (25), PCLMULQDQ
            # (1) and SSSE3 (9) where the processor has AES and PMULL (field
            # AES of ID_AA64ISAR0_EL1 at 2, which Linux lets a program read).
            # The flags are left alone, as cpuid leaves them. macOS lets no
            # program read the register, and every Mac on ARM64 has both.
            read = 'mov x16,#0x20' if 'DARWIN' in self.symbols else 'mrs x16,ID_AA64ISAR0_EL1'
            self.emit(read, 'ubfx x16,x16,#5,#1', 'neg x16,x16',
                      'movz w17,#0x0202', 'movk w17,#0x0200,lsl #16', 'and w17,w17,w16',
                      'movz w1,#0x1000', 'movk w1,#0x1800,lsl #16', 'orr w1,w1,w17',
                      'mov x0,#0', 'mov x2,#0', 'mov x3,#0')
            return
        if m == 'xgetbv':
            # XCR0 with the XMM and YMM state on (bits 1 and 2).
            self.emit('mov x0,#6', 'mov x2,#0')
            return
        if m == 'lock':
            return
        raise Untranslated(f'instruction {m}')

    def r(self, reg, size):
        return f'{"w" if size <= 4 else "x"}{reg}'

    def narrow(self, size, *regs):
        """A byte or a word moved to the top of its W register, so that the
        flags an operation on it sets are those of its size."""
        if size < 4:
            for reg in regs:
                self.emit(f'lsl w{reg},w{reg},#{32 - 8 * size}')

    def operand_reg(self, reg, op, size):
        """reg holds the operand (an immediate in a register too)."""
        self.load(reg, op, size)

    def lea(self, dst, op):
        base = op.base
        if op.index is not None:
            shift = {1: 0, 2: 1, 4: 2, 8: 3}[op.scale]
            if base is None:
                self.emit(f'lsl x{dst},x{op.index},#{shift}')
            else:
                self.emit(f'add x{dst},x{base},x{op.index},lsl #{shift}')
            base = dst
        if base is None:
            if self.in_block(op.disp):
                self.block_address(dst, op.disp)
                return
            self.mov_imm(dst, op.disp)
            return
        if op.index is not None and self.in_block(op.disp):
            self.mov_imm(17, op.disp - BLOCK)
            self.emit(f'add x{dst},x{dst},x17', f'add x{dst},x{dst},x26')
            return
        if op.disp == 0:
            if base != dst:
                self.emit(f'mov x{dst},x{base}')
        elif 0 < op.disp < 4096:
            self.emit(f'add x{dst},x{base},#{op.disp}')
        elif -4096 < op.disp < 0:
            self.emit(f'sub x{dst},x{base},#{-op.disp}')
        else:
            self.mov_imm(17, op.disp)
            self.emit(f'add x{dst},x{base},x17')

    def arith(self, m, ops, flags_needed):
        dst, src = ops
        size = dst.size if dst.kind == 'reg' else (dst.size or (src.size if src.kind == 'reg' else 8))
        a, b = self.r(19, size), self.r(20, size)
        self.load(19, dst, size)
        if m == 'xor' and src.kind == 'reg' and dst.kind == 'reg' and src.r == dst.r:
            self.emit(f'mov {a},#0')
            if flags_needed:
                self.emit(f'tst {a},{a}')
                self.carry = 'add'
            self.store(dst, 19, size)
            return
        self.load(20, src, size)
        narrowed = bool(flags_needed) and size < 4 and m != 'adc' and m != 'sbb'
        if narrowed:
            self.narrow(size, 19, 20)
        if m == 'add':
            self.emit(f'adds {a},{a},{b}' if flags_needed else f'add {a},{a},{b}')
            self.carry = 'add'
        elif m == 'sub':
            self.emit(f'subs {a},{a},{b}' if flags_needed else f'sub {a},{a},{b}')
            self.carry = 'sub'
        elif m == 'and':
            self.emit(f'ands {a},{a},{b}' if flags_needed else f'and {a},{a},{b}')
            self.carry = 'add'
        elif m in ('or', 'xor'):
            self.emit(f'{"orr" if m == "or" else "eor"} {a},{a},{b}')
            if flags_needed:
                self.emit(f'tst {a},{a}')
                self.carry = 'add'
        elif m in ('adc', 'sbb'):
            # Bring x86's carry into ARM's C as each instruction reads it.
            if m == 'adc':
                if self.carry == 'sub':
                    self.emit('cset x21,lo', 'cmp x21,#1')      # C = the borrow
                self.emit(f'adcs {a},{a},{b}')
                self.carry = 'add'
            else:
                if self.carry == 'add':
                    self.emit('cset x21,lo', 'cmp x21,#1')      # C = not the carry
                self.emit(f'sbcs {a},{a},{b}')
                self.carry = 'sub'
        if narrowed:
            self.emit(f'lsr w19,w19,#{32 - 8 * size}')
        self.store(dst, 19, size)

    def flag_value(self, reg, suffix):
        """reg = 1 when condition suffix holds, else 0."""
        conds = self.condition(suffix)
        c = conds[0]
        if isinstance(c, tuple):
            self.emit(f'cset x{reg},{c[0]}', f'cset x21,{c[1]}', f'and x{reg},x{reg},x21')
        elif len(conds) == 2:
            self.emit(f'cset x{reg},{conds[0]}', f'cset x21,{conds[1]}', f'orr x{reg},x{reg},x21')
        else:
            self.emit(f'cset x{reg},{c}')

    def shift(self, m, ops, size, flags_needed):
        dst, count = ops
        a = self.r(19, size)
        self.load(19, dst, size)
        op = {'shl': 'lsl', 'sal': 'lsl', 'shr': 'lsr', 'sar': 'asr', 'ror': 'ror'}.get(m)
        if count.kind == 'imm':
            n = count.v & (63 if size == 8 else 31)
            if m == 'rol':
                op, n = 'ror', (size * 8 - n) % (size * 8)
            if n == 0:
                return
            if flags_needed:
                # x86's carry: the last bit shifted out.
                if m in ('shl', 'sal'):
                    self.emit(f'lsr {a.replace("19", "21")},{a},#{size * 8 - n}')
                else:
                    self.emit(f'lsr {a.replace("19", "21")},{a},#{n - 1}')
                self.emit('and x21,x21,#1')
            self.emit(f'{op} {a},{a},#{n}')
        else:
            if count.kind != 'reg' or count.x86 != 1:
                raise Untranslated('shift by other than CL')
            if flags_needed and m in ('shl', 'sal', 'shr', 'sar'):
                # The carry is the last bit out; a count of 0 (CL masked)
                # leaves the flags as they were.
                bits = size * 8
                w = 'x' if size == 8 else 'w'
                self.emit(f'and x24,x1,#{bits - 1}')
                if m in ('shl', 'sal'):
                    self.emit(f'mov x23,#{bits}', 'sub x23,x23,x24')
                else:
                    self.emit('sub x23,x24,#1')
                self.emit(f'lsr {w}21,{a},{w}23', 'and x21,x21,#1', f'{op} {a},{a},{self.r(1, size)}')
                if size < 4:
                    raise Untranslated('shift of a byte or word')
                self.store(dst, 19, size)
                skip = self.label()
                if self.carry == 'fp':
                    self.carry = 'add'
                if self.carry == 'sub':
                    self.emit('eor x21,x21,#1')
                self.emit(f'cbz x24,{skip}', f'tst {a},{a}', 'mrs x23,nzcv', 'bfi x23,x21,#29,#1', 'msr nzcv,x23')
                self.out.append(f'{skip}:')
                return
            if m == 'rol':
                self.emit(f'neg w20,w1', f'ror {a},{a},{self.r(20, size)}')
            else:
                self.emit(f'{op} {a},{a},{self.r(1, size)}')
            if flags_needed:
                raise Untranslated(f'flags of {m} by CL')
        if size < 4:
            raise Untranslated('shift of a byte or word')
        self.store(dst, 19, size)
        if flags_needed:
            # x86 sets the carry (the last bit out) and Z, S from the result:
            # Z and N by tst, C put in after.
            self.emit(f'tst {a},{a}')
            if flags_needed in CARRY_USERS:
                self.emit('mrs x23,nzcv', 'bfi x23,x21,#29,#1', 'msr nzcv,x23')
            self.carry = 'add'

    def double_shift(self, m, ops):
        dst, src, count = ops
        if count.kind != 'reg' or count.x86 != 1 or dst.kind != 'reg' or dst.size != 8:
            raise Untranslated(f'{m} form')
        skip = self.label()
        self.emit('and x21,x1,#63', f'cbz x21,{skip}', 'mov x22,#64', 'sub x22,x22,x21')
        if m == 'shrd':
            self.emit(f'lsr x{dst.r},x{dst.r},x21', f'lsl x23,x{src.r},x22', f'orr x{dst.r},x{dst.r},x23')
        else:
            self.emit(f'lsl x{dst.r},x{dst.r},x21', f'lsr x23,x{src.r},x22', f'orr x{dst.r},x{dst.r},x23')
        self.out.append(f'{skip}:')

    def imul(self, ops, size, flags_needed):
        if len(ops) == 1:
            raise Untranslated('one-operand imul')
        dst = ops[0]
        a, b = (ops[0], ops[1]) if len(ops) == 2 else (ops[1], ops[2])
        self.load(19, a, size)
        self.load(20, b, size)
        if size == 8:
            if flags_needed:
                self.emit('smulh x21,x19,x20')
            self.emit('mul x19,x19,x20')
            if flags_needed:
                # Overflow when the high half is not the sign of the low.
                self.emit('cmp x21,x19,asr #63', 'cset x21,ne')
                self.overflow_from('x21')
        else:
            self.emit('smull x19,w19,w20')
            if flags_needed:
                self.emit('cmp x19,w19,sxtw', 'cset x21,ne')
                self.overflow_from('x21')
        self.store(dst, 19, size)

    def overflow_from(self, reg):
        """Flags with V and C set when reg is 1 (imul's overflow), as x86 sets OF and CF."""
        # (b << 63) + (b << 63) overflows, signed and unsigned, exactly when b is 1.
        self.emit(f'lsl x22,{reg},#63', 'adds xzr,x22,x22')
        self.carry = 'add'

    def divide(self, m, ops, size):
        (src,) = ops
        self.load(20, src, size, signed=(m == 'idiv'))
        if size == 8:
            if m == 'div':
                # RDX:RAX / src, RDX below src as x86 requires; RDX = 0 is the
                # common case, else a long division by bits.
                # The remainder shifted left may pass 64 bits (a divisor past
                # 2**63): then it is above the divisor and is reduced at once.
                long, done, top, take, next_ = (self.label() for _ in range(5))
                self.emit(f'cbnz x2,{long}', 'udiv x19,x0,x20', 'msub x2,x19,x20,x0', 'mov x0,x19', f'b {done}')
                self.out.append(f'{long}:')
                self.emit('mov x21,#64')
                self.out.append(f'{top}:')
                self.emit('lsr x22,x0,#63', 'adds x2,x2,x2', 'cset x23,hs', 'orr x2,x2,x22', 'lsl x0,x0,#1',
                          f'cbnz x23,{take}', 'cmp x2,x20', f'b.lo {next_}')
                self.out.append(f'{take}:')
                self.emit('sub x2,x2,x20', 'orr x0,x0,#1')
                self.out.append(f'{next_}:')
                self.emit('subs x21,x21,#1', f'b.ne {top}')
                self.out.append(f'{done}:')
            else:
                self.emit('sdiv x19,x0,x20', 'msub x2,x19,x20,x0', 'mov x0,x19')
        else:
            if m == 'div':
                self.emit('orr x21,x0,x2,lsl #32', 'mov w0,w0', 'udiv x19,x21,x20', 'msub x2,x19,x20,x21',
                          'mov w0,w19', 'mov w2,w2')
            else:
                raise Untranslated('idiv of 32 bits')

    def bit_test(self, m, ops, size):
        base, bit = ops
        if base.kind == 'reg':
            self.load(20, bit, 8)
            self.emit(f'and x20,x20,#{size * 8 - 1}', 'mov x21,#1', 'lsl x21,x21,x20', f'tst x{base.r},x21',
                      'cset x22,ne')
            if m == 'bts':
                self.emit(f'orr x{base.r},x{base.r},x21')
            elif m == 'btr':
                self.emit(f'bic x{base.r},x{base.r},x21')
            elif m == 'btc':
                self.emit(f'eor x{base.r},x{base.r},x21')
        else:
            if bit.kind == 'imm':
                where_disp = (bit.v >> 6) * 8
                self.lea(23, base)
                if where_disp:
                    self.emit(f'add x23,x23,#{where_disp}')
                self.mov_imm(20, bit.v & 63)
            else:
                # A register bit offset reaches past the operand: the word is
                # base + (bit >> 6) * 8, signed.
                self.lea(23, base)
                self.load(20, bit, 8)
                self.emit('asr x22,x20,#6', 'add x23,x23,x22,lsl #3', 'and x20,x20,#63')
            self.emit('ldr x24,[x23]', 'mov x21,#1', 'lsl x21,x21,x20', 'tst x24,x21', 'cset x22,ne')
            if m != 'bt':
                op = {'bts': 'orr', 'btr': 'bic', 'btc': 'eor'}[m]
                self.emit(f'{op} x24,x24,x21', 'str x24,[x23]')
        # C = the bit (cmp x22,#1 sets C when x22 >= 1), so jc is b.hs as
        # after an addition.
        self.emit('cmp x22,#1')
        self.carry = 'add'

    def string(self, m, ops):
        rep = m.startswith('rep')
        op = m.split()[-1] if ' ' in m else m
        if m in ('rep', 'repe', 'repz', 'repne'):
            raise Untranslated('rep without its instruction')
        if self.direction < 0 and op not in ('movsb', 'movsq'):
            raise Untranslated(f'{op} backwards')
        step = {'movsb': 1, 'movsq': 8, 'stosb': 1, 'stosq': 8, 'stosd': 4, 'cmpsb': 1, 'movsd': 4}[op]
        letter = {1: ('ldrb w', 'strb w'), 4: ('ldr w', 'str w'), 8: ('ldr x', 'str x')}[step]
        d = step * self.direction
        top, done = self.label(), self.label()
        if op.startswith('movs'):
            body = [f'{letter[0]}19,[x4],#{d}', f'{letter[1]}19,[x5],#{d}']
        elif op.startswith('stos'):
            body = [f'{letter[1]}0,[x5],#{d}']
        elif op == 'cmpsb':
            if m not in ('repe cmpsb', 'repz cmpsb'):
                raise Untranslated(m)
            # Compare until a difference or RCX runs out; flags of the last pair.
            self.emit(f'cbz x1,{done}')
            self.out.append(f'{top}:')
            self.emit('ldrb w19,[x4],#1', 'ldrb w20,[x5],#1', 'sub x1,x1,#1', 'cmp w19,w20', f'b.ne {done}',
                      f'cbnz x1,{top}')
            self.out.append(f'{done}:')
            self.carry = 'sub'
            return
        if not rep:
            self.emit(*body)
            return
        self.emit(f'cbz x1,{done}')
        self.out.append(f'{top}:')
        self.emit(*body, 'sub x1,x1,#1', f'cbnz x1,{top}')
        self.out.append(f'{done}:')

    def vsrc(self, op):
        """A vector operand as a V register: V31 for memory."""
        if op.kind == 'xmm':
            return op.r
        self.emit(f'ldr q31,{self.address(op, 16)}')
        return 31

    def vector(self, m, ops):
        if m in ('movdqa', 'movdqu'):
            return self.sse('movapd', ops)
        d = ops[0].r
        if m in ('pand', 'por', 'pandn'):
            s = self.vsrc(ops[1])
            op = {'pand': 'and', 'por': 'orr'}.get(m)
            if m == 'pandn':
                self.emit(f'bic v{d}.16b,v{s}.16b,v{d}.16b')
            else:
                self.emit(f'{op} v{d}.16b,v{d}.16b,v{s}.16b')
            return
        if m in ('pslld', 'psrld', 'psllq', 'psrlq'):
            n = ops[1].v
            lane = '4s' if m[-1] == 'd' else '2d'
            bits = 32 if lane == '4s' else 64
            if n >= bits:
                self.emit(f'movi v{d}.2d,#0')
            elif n:
                self.emit(f'{"shl" if m.startswith("psl") else "ushr"} v{d}.{lane},v{d}.{lane},#{n}')
            return
        if m in ('pslldq', 'psrldq'):
            n = ops[1].v
            self.emit('movi v30.2d,#0')
            if n >= 16:
                self.emit(f'movi v{d}.2d,#0')
            elif n and m == 'psrldq':
                self.emit(f'ext v{d}.16b,v{d}.16b,v30.16b,#{n}')
            elif n:
                self.emit(f'ext v{d}.16b,v30.16b,v{d}.16b,#{16 - n}')
            return
        if m == 'pshufd':
            s = self.vsrc(ops[1])
            k = ops[2].v
            self.emit(f'mov v29.16b,v{s}.16b')
            for i in range(4):
                self.emit(f'mov v{d}.s[{i}],v29.s[{(k >> (2 * i)) & 3}]')
            return
        if m == 'pshufb':
            # x86 takes the low four bits of an index below 128, and 0 from 128
            # up; tbl gives 0 from 16 up: so each index & 0x8F.
            s = self.vsrc(ops[1])
            self.emit('movi v30.16b,#0x8f', f'and v30.16b,v{s}.16b,v30.16b', f'tbl v{d}.16b,{{v{d}.16b}},v30.16b')
            return
        if m in ('pcmpgtb', 'pcmpeqb'):
            s = self.vsrc(ops[1])
            self.emit(f'{"cmgt" if m == "pcmpgtb" else "cmeq"} v{d}.16b,v{d}.16b,v{s}.16b')
            return
        if m in ('paddb', 'paddd', 'paddq', 'psubb', 'psubd'):
            s = self.vsrc(ops[1])
            lane = {'b': '16b', 'd': '4s', 'q': '2d'}[m[-1]]
            self.emit(f'{"add" if m.startswith("padd") else "sub"} v{d}.{lane},v{d}.{lane},v{s}.{lane}')
            return
        if m.startswith('aes'):
            # x86 adds the round key last, ARM first: a round against zero, then the key.
            s = self.vsrc(ops[1])
            if m == 'aesimc':
                self.emit(f'aesimc v{d}.16b,v{s}.16b')
                return
            self.emit(f'mov v29.16b,v{s}.16b', 'movi v30.2d,#0')
            if m.startswith('aesenc'):
                self.emit(f'aese v{d}.16b,v30.16b')
                if m == 'aesenc':
                    self.emit(f'aesmc v{d}.16b,v{d}.16b')
            else:
                self.emit(f'aesd v{d}.16b,v30.16b')
                if m == 'aesdec':
                    self.emit(f'aesimc v{d}.16b,v{d}.16b')
            self.emit(f'eor v{d}.16b,v{d}.16b,v29.16b')
            return
        if m == 'pclmulqdq':
            s = self.vsrc(ops[1])
            k = ops[2].v
            self.emit(f'dup d29,v{d}.d[{k & 1}]', f'dup d30,v{s}.d[{(k >> 4) & 1}]', f'pmull v{d}.1q,v29.1d,v30.1d')
            return
        raise Untranslated(f'vector {m}')

    def sse(self, m, ops):
        def d(op):
            return f'd{op.r}'
        if m in ('movq', 'movd'):
            dst, src = ops
            if dst.kind == 'xmm' and src.kind == 'reg':
                self.emit(f'fmov s{dst.r},w{src.r}' if src.size == 4 else f'fmov d{dst.r},x{src.r}')
            elif dst.kind == 'reg' and src.kind == 'xmm':
                self.emit(f'fmov w{dst.r},s{src.r}' if dst.size == 4 else f'fmov x{dst.r},d{src.r}')
            elif dst.kind == 'xmm' and src.kind == 'xmm':
                self.emit(f'fmov d{dst.r},d{src.r}')
            elif dst.kind == 'xmm' and src.kind == 'mem':
                self.emit(f'ldr d{dst.r},{self.address(src, 8)}')
            elif dst.kind == 'mem' and src.kind == 'xmm':
                self.emit(f'str d{src.r},{self.address(dst, 8)}')
            else:
                raise Untranslated(f'{m} {ops}')
            return
        if m == 'movsd':
            return self.sse('movq', ops)
        if m in ('movapd', 'movaps', 'movups'):
            dst, src = ops
            if dst.kind == 'xmm' and src.kind == 'xmm':
                self.emit(f'mov v{dst.r}.16b,v{src.r}.16b')
            elif dst.kind == 'xmm':
                self.emit(f'ldr q{dst.r},{self.address(src, 16)}')
            else:
                self.emit(f'str q{src.r},{self.address(dst, 16)}')
            return
        def fsrc(op):
            # The second operand as a D register: D31 for memory.
            if op.kind == 'xmm':
                return f'd{op.r}'
            self.emit(f'ldr d31,{self.address(op, 8)}')
            return 'd31'
        arith = {'addsd': 'fadd', 'subsd': 'fsub', 'mulsd': 'fmul', 'divsd': 'fdiv'}
        if m in arith:
            dst, src = ops
            self.emit(f'{arith[m]} d{dst.r},d{dst.r},{fsrc(src)}')
            return
        if m == 'vaddsd':
            dst, a, b = ops
            self.emit(f'fadd d{dst.r},d{a.r},{fsrc(b)}')
            return
        if m == 'sqrtsd':
            dst, src = ops
            self.emit(f'fsqrt d{dst.r},{fsrc(src)}')
            return
        if m.startswith('vf'):
            # FMA3: 132 a = a*c + b, 213 a = b*a + c, 231 a = b*c + a; the
            # negated forms subtract the product, the sub forms the addend.
            # ARM fmadd d = a + n*m, fmsub d = a - n*m, fnmsub d = n*m - a,
            # fnmadd d = -(n*m) - a.
            a, b, c = ops
            cs = fsrc(c)
            op = {'vfmadd': 'fmadd', 'vfnmadd': 'fmsub', 'vfmsub': 'fnmsub', 'vfnmsub': 'fnmadd'}[m[:-5]]
            order = m[-5:-2]
            if order == '213':
                self.emit(f'{op} d{a.r},d{b.r},d{a.r},{cs}')
            elif order == '231':
                self.emit(f'{op} d{a.r},d{b.r},{cs},d{a.r}')
            else:
                self.emit(f'{op} d{a.r},d{a.r},{cs},d{b.r}')
            return
        if m == 'cvtsi2sd':
            dst, src = ops
            self.load(19, src, src.size if src.kind == 'reg' else (src.size or 8), signed=True)
            self.emit(f'scvtf d{dst.r},x19')
            return
        if m in ('cvttsd2si', 'cvtsd2si'):
            # x86 gives the integer indefinite (the lowest integer) for NaN and
            # values out of range, where ARM saturates; cvtsd2si rounds to even.
            dst, src = ops
            s = fsrc(src)
            w = dst.size
            name = self.r(19, w)
            conv = 'fcvtzs' if m == 'cvttsd2si' else 'fcvtns'
            ok, bad = self.label(), self.label()
            self.emit(f'{conv} {name},{s}', f'fcmp {s},{s}', f'b.vs {bad}')
            self.mov_imm(20, (1 << (8 * w - 1)) - 1, 64 if w == 8 else 32)
            self.emit(f'cmp {name},{self.r(20, w)}', f'b.eq {bad}')
            self.mov_imm(20, -(1 << (8 * w - 1)), 64 if w == 8 else 32)
            self.emit(f'cmp {name},{self.r(20, w)}', f'b.ne {ok}')
            self.out.append(f'{bad}:')
            self.mov_imm(19, -(1 << (8 * w - 1)), 64 if w == 8 else 32)
            self.out.append(f'{ok}:')
            self.store(dst, 19, w)
            return
        if m in ('xorpd', 'xorps', 'pxor', 'andpd', 'orpd'):
            dst, src = ops
            if src.kind == 'xmm' and dst.kind == 'xmm':
                if src.r == dst.r and m in ('xorpd', 'xorps', 'pxor'):
                    self.emit(f'movi v{dst.r}.2d,#0')
                    return
                op = {'xorpd': 'eor', 'xorps': 'eor', 'pxor': 'eor', 'andpd': 'and', 'orpd': 'orr'}[m]
                self.emit(f'{op} v{dst.r}.16b,v{dst.r}.16b,v{src.r}.16b')
            else:
                op = {'xorpd': 'eor', 'xorps': 'eor', 'pxor': 'eor', 'andpd': 'and', 'orpd': 'orr'}[m]
                self.emit(f'ldr q31,{self.address(src, 16)}', f'{op} v{dst.r}.16b,v{dst.r}.16b,v31.16b')
            return
        if m.startswith('cmp') and m.endswith('sd'):
            # A mask of all ones where the comparison holds: nlt is not less
            # (or unordered), lt less, le less or equal, nle not that, eq equal.
            dst, src = ops
            s = fsrc(src)
            cond = {'cmpltsd': 'mi', 'cmplesd': 'ls', 'cmpeqsd': 'eq', 'cmpnltsd': 'pl', 'cmpnlesd': 'hi'}[m]
            self.emit(f'fcmp d{dst.r},{s}', f'csetm x19,{cond}')
            if m in ('cmpnltsd', 'cmpnlesd'):
                self.emit(f'csinv x19,x19,xzr,vc')
            self.emit(f'fmov d{dst.r},x19')
            return
        if m in ('ucomisd', 'comisd'):
            a, b = ops
            if b.kind == 'mem':
                self.emit(f'ldr d31,{self.address(b, 8)}')
                self.emit(f'fcmp {d(a)},d31')
            else:
                self.emit(f'fcmp {d(a)},{d(b)}')
            # x86: CF = less or unordered, ZF = equal or unordered, PF =
            # unordered. ARM after fcmp: lt N!=V, unordered C=1 V=1. The
            # conditions jb/jae/ja/jbe map through 'fp'.
            self.carry = 'fp'
            return
        raise Untranslated(f'SSE {m}')


def split_operands(text):
    parts, depth, current = [], 0, ''
    for ch in text:
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(current)
            current = ''
        else:
            current += ch
    if current.strip():
        parts.append(current)
    return [p.strip() for p in parts]


def strip_comment(line):
    out, quoted = '', False
    for ch in line:
        if ch == '"':
            quoted = not quoted
        if ch == '#' and not quoted:
            break
        out += ch
    return out.rstrip()


# Macros whose x86-64 body is machine code written as data: their meaning.
# jump5 is a 5-byte jump in a table of entry points (4 bytes on ARM64).
OVERRIDES = {'jump5': (['target'], [' jmp \\target'])}


def expand_macros(lines, macros=None):
    macros = {} if macros is None else macros
    out, i = [], 0
    def block(i, opener):
        """The lines up to the end that matches the opener at i, and the index after it."""
        body, depth = [], 1
        i += 1
        while True:
            word = (strip_comment(lines[i]).strip().split() or [''])[0]
            if word in opener:
                depth += 1
            elif word == ('.endm' if '.macro' in opener else '.endr'):
                depth -= 1
                if depth == 0:
                    return body, i + 1
            body.append(lines[i])
            i += 1
    while i < len(lines):
        line = strip_comment(lines[i]).strip()
        m = re.match(r'\.macro\s+(\w+)\s*(.*)$', line)
        if m:
            body, i = block(i, ('.macro',))
            params = [p.strip().split('=')[0] for p in m.group(2).replace(',', ' ').split() if p.strip()]
            macros[m.group(1)] = OVERRIDES.get(m.group(1), (params, body))
            continue
        m = re.match(r'\.(irp|rept)\s*(.*)$', line)
        if m:
            body, i = block(i, ('.irp', '.rept', '.irpc'))
            if m.group(1) == 'rept':
                times = int(Translator().value(m.group(2)))
                for _ in range(times):
                    out.extend(expand_macros(body, macros))
            else:
                name, _, values = m.group(2).partition(',')
                for v in split_operands(values):
                    out.extend(expand_macros([b.replace('\\' + name.strip(), v) for b in body], macros))
            continue
        word = line.split()[0] if line.split() else ''
        if word in macros:
            params, body = macros[word]
            args = split_operands(line[len(word):])
            lines_in = []
            for b in body:
                for p, a in zip(params, args):
                    b = b.replace('\\' + p, a)
                lines_in.append(b)
            out.extend(expand_macros(lines_in, macros))
            i += 1
            continue
        out.append(lines[i])
        i += 1
    return out


def reader_after(items, index):
    """The first instruction after items[index] that reads the flags it
    leaves, or False: none before they are set again. An unconditional jump
    is followed to its label (a few times at most: past that the flags
    count as read)."""
    carry_only = False      # past an inc or dec, which keep the carry
    i = index + 1
    jumps = 0
    while i < len(items):
        later = items[i]
        if later[0] != 'ins':
            if later[0] == 'label':
                i += 1
                continue
            break
        name = later[1].split()[-1] if later[1].startswith('rep') else later[1]
        if name in READS or later[1] in READS:
            return name if not carry_only or name in CARRY_USERS else False
        if name in ('inc', 'dec'):
            carry_only = True
            i += 1
            continue
        if name in ('shl', 'sal', 'shr', 'sar', 'rol', 'ror') and later[2].replace(' ', '').lower().endswith(',cl'):
            # By CL, which may be 0: then the flags are kept.
            i += 1
            continue
        if name == 'jmp':
            to = target(items, i, later[2].strip())
            if to is None:
                break
            jumps += 1
            if jumps > 8:
                return 'jmp'
            i = to + 1
            continue
        if name in WRITES or name in ('ret', 'call', 'syscall'):
            break
        i += 1
    return False


def target(items, index, name):
    """The index of the label a jump at items[index] goes to (1b, 1f or a name), or None."""
    m = re.fullmatch(r'(\d+)([bf])', name)
    if m:
        order = range(index - 1, -1, -1) if m.group(2) == 'b' else range(index + 1, len(items))
        return next((i for i in order if items[i] == ('label', m.group(1))), None)
    return next((i for i, item in enumerate(items) if item == ('label', name)), None)


def translate(text, defines=()):
    t = Translator()
    for name in defines:
        t.symbols[name] = 1
    lines = expand_macros(text.split('\n'))
    # Conditional assembly is resolved here, as the symbols are known.
    kept, stack = [], []
    for raw in lines:
        line = strip_comment(raw).strip()
        if line.startswith('.ifdef'):
            stack.append(line.split()[1] in t.symbols)
            continue
        if line.startswith('.ifndef'):
            stack.append(line.split()[1] not in t.symbols)
            continue
        if line.startswith(('.ifc ', '.ifnc ')):
            left, _, right = line.split(None, 1)[1].partition(',')
            same = left.strip() == right.strip()
            stack.append(same if line.startswith('.ifc ') else not same)
            continue
        if line.startswith(('.ifb', '.ifnb')):
            empty = len(line.split(None, 1)) < 2
            stack.append(empty if line.startswith('.ifb') else not empty)
            continue
        if line.startswith('.if '):
            v = t.value(line[4:])
            if v is None:
                raise Untranslated(f'condition {line}')
            stack.append(v != 0)
            continue
        if line.startswith('.else'):
            stack[-1] = not stack[-1]
            continue
        if line.startswith('.endif'):
            stack.pop()
            continue
        if all(stack):
            kept.append(line)
            m = re.match(r'\.(?:set|equ)\s+(\w+)\s*,\s*(.+)$', line)
            if m:
                v = t.value(m.group(2))
                if v is not None:
                    t.symbols[m.group(1)] = v
    # Instructions: (mnemonic, operand texts) and which read flags.
    items = []
    for line in kept:
        if not line:
            continue
        while True:
            m = re.match(r'^([A-Za-z_.$][\w.$]*|\d+):\s*(.*)$', line)
            if not m:
                break
            items.append(('label', m.group(1)))
            line = m.group(2).strip()
        if not line:
            continue
        if line.startswith('.'):
            items.append(('directive', line))
            continue
        word, _, rest = line.partition(' ')
        word = word.lower()
        if word in ('rep', 'repe', 'repz', 'repne', 'repnz', 'lock'):
            inner, _, rest2 = rest.strip().partition(' ')
            if word == 'lock':
                word, rest = inner.lower(), rest2
            else:
                word = f'{word} {inner.lower()}'
                rest = rest2
        items.append(('ins', word, rest.strip()))
    out = ['.text']
    in_data = False
    pending = []
    # A label where the carry is read before it is set again: every path
    # that comes to it brings the carry in one sense, a subtraction's (a
    # loop entered after logic, whose body ends with sbb, reads it so at
    # its head both ways).
    carried = {i for i, item in enumerate(items) if item[0] == 'label' and reader_after(items, i) in CARRY_USERS}
    flip = [' mrs x22,nzcv', ' eor x22,x22,#0x20000000', ' msr nzcv,x22']
    for index, item in enumerate(items):
        if item[0] == 'label':
            if index in carried:
                if t.carry == 'add':
                    out.extend(flip)
                if t.carry != 'fp':
                    t.carry = 'sub'
            pending.append(item[1])
            continue
        if item[0] == 'directive':
            d = item[1]
            if d.startswith(('.global', '.globl')):
                out.append(d)
                continue
            if d.startswith(('.intel_syntax', '.att_syntax', '.text', '.section', '.type', '.size')):
                continue
            if d.startswith('.set') or d.startswith('.equ'):
                out.append(d)
                continue
            if not in_data:
                in_data = True
            out.extend(f'{p}:' for p in pending)
            pending = []
            # x86-64's .word is 2 bytes, AArch64's 4.
            out.append(re.sub(r'^\.word\b', '.hword', d))
            continue
        _, word, rest = item
        if in_data:
            out.append('.balign 4')
            in_data = False
        out.extend(f'{p}:' for p in pending)
        pending = []
        # Whether a later instruction reads the flags this one leaves.
        needed = reader_after(items, index)
        if (word == 'jmp' or word in JCC) and target(items, index, rest.strip()) in carried and t.carry == 'add':
            out.extend(flip)
            t.carry = 'sub'
        try:
            ops = [t.operand(o) for o in split_operands(rest)] if rest else []
            t.out = []
            t.instruction(word, ops, needed)
            out.extend(t.out)
        except (Untranslated, ValueError, KeyError) as error:
            if MISSING is None:
                raise Untranslated(f'{word} {rest}: {error}') from None
            MISSING.append(f'{word} {rest}: {error}')
            out.append(' udf #0')
    # The system call routine goes before labels that end the routine: a
    # label at the end names what the compiler appends (tr_data, the trace
    # runtime's tables).
    out.append('.text')
    out.append('.balign 4')
    out.extend(((darwin_syscall() if 'DARWIN_ROUTINE' in t.symbols else DARWIN_STUB) if 'DARWIN' in t.symbols else SYSCALL).split('\n'))
    out.extend(f'{p}:' for p in pending)
    return '\n'.join(out) + '\n'


# x86-64's syscall, entered with X30 the way back: the number in RAX (X0), the
# arguments in RDI, RSI, RDX, R10, R8, R9 (X5, X4, X2, X10, X8, X9); every
# register but RCX and R11 (X1, X11) kept, the result in RAX.

# On macOS (DARWIN defined, spec/darwin-arm64.md) x86-64's system calls are
# calls of libSystem's functions, through the words dyld binds before the
# copy of the entry's words: word i of DARWIN_IMPORTS is at X26 less
# darwin_head() plus 8 i. The collector holds the routine (DARWIN_ROUTINE
# defined); every other runtime goes to it through the word at 0x400420, as
# translated functions do.
DARWIN_IMPORTS = ['_exit', '_mmap', '_write', '_read', '_close', '_munmap', '_mprotect', '___error',
                  '_openat', '_fstat', '_fstatat', '_lseek', '_pread', '_pwrite', '_dup', '_dup2', '_nanosleep',
                  '_fork', '_execve', '_wait4', '_kill', '_fcntl', '_fsync', '_ftruncate', '_getcwd', '_chdir',
                  '_readlink', '_rename', '_mkdir', '_rmdir', '_unlink', '_link', '_symlink', '_chmod', '_access',
                  '_pipe', '___getdirentries64', '_clock_gettime', '_getentropy', '_poll', '_sigaction', '_mkstemp',
                  '_getpid', '_socket', '_connect', '_bind', '_listen', '_accept', '_sendto', '_recvfrom',
                  '_shutdown', '_setsockopt', '_getsockopt', '_getsockname', '_getpeername', '_mkdirat',
                  '_unlinkat', '_readlinkat', '_fchmodat', '_utimensat', '_faccessat']


def darwin_head():
    """How far before X26 the first bound word is: the words, then the count
    of the copy and a word kept free."""
    return 16 + 8 * len(DARWIN_IMPORTS)


# What each x86-64 system call is on macOS: (number, function, how its
# arguments and result convert: one of DARWIN_KINDS). Any other is -ENOSYS.
DARWIN_CALLS = [
    (0, '_read', 'plain'), (1, '_write', 'plain'), (2, '_openat', 'open'), (3, '_close', 'plain'),
    (4, '_fstatat', 'stat'), (5, '_fstat', 'fstat'), (6, '_fstatat', 'lstat'), (7, '_poll', 'plain'),
    (8, '_lseek', 'plain'), (9, '_mmap', 'mmap'), (10, '_mprotect', 'plain'), (11, '_munmap', 'plain'),
    (13, '_sigaction', 'sigaction'), (17, '_pread', 'plain'), (18, '_pwrite', 'plain'), (21, '_access', 'plain'),
    (22, '_pipe', 'plain'), (25, '_mmap', 'mremap'), (32, '_dup', 'plain'), (33, '_dup2', 'plain'),
    (35, '_nanosleep', 'plain'), (39, '_getpid', 'plain'), (41, '_socket', 'socket'), (42, '_connect', 'sain'),
    (43, '_accept', 'accept'), (44, '_sendto', 'sendto'), (45, '_recvfrom', 'recvfrom'), (48, '_shutdown', 'plain'),
    (49, '_bind', 'sain'), (50, '_listen', 'plain'), (51, '_getsockname', 'saout'), (52, '_getpeername', 'saout'),
    (54, '_setsockopt', 'sockopt'), (55, '_getsockopt', 'getsockopt'), (57, '_fork', 'plain'), (59, '_execve', 'plain'),
    (60, '_exit', 'plain'), (61, '_wait4', 'wait4'), (62, '_kill', 'kill'), (72, '_fcntl', 'fcntl'),
    (74, '_fcntl', 'fullsync'), (75, '_fsync', 'plain'), (77, '_ftruncate', 'plain'), (79, '_getcwd', 'getcwd'), (80, '_chdir', 'plain'),
    (82, '_rename', 'plain'), (83, '_mkdir', 'plain'), (84, '_rmdir', 'plain'), (86, '_link', 'plain'),
    (87, '_unlink', 'plain'), (88, '_symlink', 'plain'), (89, '_readlink', 'plain'), (90, '_chmod', 'plain'),
    (217, '___getdirentries64', 'dents'), (228, '_clock_gettime', 'clock'), (231, '_exit', 'plain'),
    (257, '_openat', 'openat'), (258, '_mkdirat', 'atfd'), (262, '_fstatat', 'fstatat'), (263, '_unlinkat', 'unlinkat'),
    (267, '_readlinkat', 'atfd'), (268, '_fchmodat', 'atflags'), (271, '_poll', 'ppoll'),
    (280, '_utimensat', 'utimensat'), (288, '_accept', 'accept4'), (293, '_pipe', 'pipe2'),
    (318, '_getentropy', 'random'), (319, '_mkstemp', 'memfd'), (439, '_faccessat', 'atflags'),
]
DARWIN_KINDS = ['plain', 'mmap', 'open', 'openat', 'stat', 'lstat', 'fstat', 'fstatat', 'fcntl', 'getcwd', 'dents',
                'clock', 'random', 'ppoll', 'pipe2', 'mremap', 'sigaction', 'memfd', 'kill', 'wait4', 'atfd',
                'atflags', 'unlinkat', 'utimensat', 'socket', 'sain', 'saout', 'accept', 'accept4', 'sendto',
                'recvfrom', 'sockopt', 'getsockopt', 'fullsync']
# What is done with a call's result once it is no -1 (X19 holds the index).
DARWIN_POSTS = ['back', 'stat', 'getfl', 'getcwd', 'dents', 'wait4', 'sockfl', 'saout', 'accept4', 'sigact', 'pipe2',
                'soerror']
# macOS's errno as Linux's, 0 to 106.
DARWIN_ERRNOS = list(range(11)) + [35] + list(range(12, 35)) + [
    11, 115, 114, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109,
    110, 111, 40, 36, 112, 113, 39, 11, 87, 122, 116, 66, 71, 71, 71, 71, 71, 37, 38, 22, 13, 13, 19, 5, 75, 8, 8, 8,
    8, 125, 43, 42, 84, 61, 74, 72, 61, 67, 63, 60, 71, 62, 95, 1, 131, 130, 105]
# Linux's signals as macOS's, and back, 0 to 31.
DARWIN_SIGNALS = [0, 1, 2, 3, 4, 5, 6, 10, 8, 9, 30, 11, 31, 13, 14, 15, 0, 20, 19, 17, 18, 21, 22, 16, 24, 25, 26, 27,
                  28, 23, 0, 12]
DARWIN_SIGNALS_BACK = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 7, 11, 31, 13, 14, 15, 23, 19, 20, 18, 17, 21, 22, 29, 24, 25, 26,
                       27, 28, 29, 10, 12]


def darwin_call(name):
    """A call of libSystem function name; X0 to X18 lost."""
    return f' sub x16,x26,#{darwin_head()}\n ldr x16,[x16,#{8 * DARWIN_IMPORTS.index(name)}]\n blr x16'


def darwin_syscall():
    """The routine, from DARWIN_ROUTINE with the calls, tables and kinds put in."""
    assert len(DARWIN_ERRNOS) == 107 and len(DARWIN_SIGNALS) == 32 == len(DARWIN_SIGNALS_BACK)
    text = DARWIN_ROUTINE
    for name in DARWIN_IMPORTS:
        text = text.replace(f'@call {name}\n', darwin_call(name) + '\n')
    for index, post in enumerate(DARWIN_POSTS):
        text = text.replace(f'#@{post}\n', f'#{index}\n')
    table = ', '.join(str(number | DARWIN_IMPORTS.index(name) << 16 | DARWIN_KINDS.index(kind) << 24)
                      for number, name, kind in DARWIN_CALLS)
    return (text.replace('@head', str(darwin_head()))
            .replace('@kinds', '\n'.join(f' b xd_k_{kind}' for kind in DARWIN_KINDS))
            .replace('@posts', '\n'.join(f' b xd_p_{post}' for post in DARWIN_POSTS))
            .replace('@errnos', ', '.join(map(str, DARWIN_ERRNOS)))
            .replace('@signals_back', ', '.join(map(str, DARWIN_SIGNALS_BACK)))
            .replace('@signals', ', '.join(map(str, DARWIN_SIGNALS)))
            .replace('@table', table))


# The frame: the outgoing word of a variadic argument at 0, X2 to X17 and
# X30 at 16, Q0 to Q15 at 144, X19 to X22 at 400, a link at 432, a word at
# 440, and 256 bytes at 448 for what is converted. X19 says what is done
# with the result (DARWIN_POSTS), X20 and X21 keep what that needs, X22 is
# the function's word.
DARWIN_ROUTINE = '''x86_syscall:
 sub sp,sp,#704
 stp x2,x3,[sp,#16]
 stp x4,x5,[sp,#32]
 stp x6,x7,[sp,#48]
 stp x8,x9,[sp,#64]
 stp x10,x12,[sp,#80]
 stp x13,x14,[sp,#96]
 stp x15,x16,[sp,#112]
 stp x17,x30,[sp,#128]
 stp q0,q1,[sp,#144]
 stp q2,q3,[sp,#176]
 stp q4,q5,[sp,#208]
 stp q6,q7,[sp,#240]
 stp q8,q9,[sp,#272]
 stp q10,q11,[sp,#304]
 stp q12,q13,[sp,#336]
 stp q14,q15,[sp,#368]
 stp x19,x20,[sp,#400]
 stp x21,x22,[sp,#416]
 mov x17,x0
 mov x0,x5
 mov x1,x4
 mov x3,x10
 mov x4,x8
 mov x5,x9
 mov x19,#0
 adr x16,xd_table
xd_find:
 ldr w6,[x16],#4
 cbz w6,xd_nosys
 and w7,w6,#0xffff
 cmp x7,x17
 b.ne xd_find
 ubfx x22,x6,#16,#8
 lsr w6,w6,#24
 adr x7,xd_kinds
 add x7,x7,x6,lsl #2
 br x7
xd_nosys:
 mov x0,#-38
 b xd_back
xd_kinds:
@kinds
xd_call:
 sub x16,x26,#@head
 ldr x16,[x16,x22,lsl #3]
 blr x16
 cmn x0,#1
 b.eq xd_errno
 adr x7,xd_posts
 add x7,x7,x19,lsl #2
 br x7
xd_posts:
@posts
xd_errno:
@call ___error
 ldrsw x0,[x0]
 cmp x0,#106
 b.hi xd_errno_1
 adr x1,xd_errnos
 ldrb w0,[x1,x0]
xd_errno_1:
 neg x0,x0
xd_p_back:
xd_back:
 ldp x2,x3,[sp,#16]
 ldp x4,x5,[sp,#32]
 ldp x6,x7,[sp,#48]
 ldp x8,x9,[sp,#64]
 ldp x10,x12,[sp,#80]
 ldp x13,x14,[sp,#96]
 ldp x15,x16,[sp,#112]
 ldp q0,q1,[sp,#144]
 ldp q2,q3,[sp,#176]
 ldp q4,q5,[sp,#208]
 ldp q6,q7,[sp,#240]
 ldp q8,q9,[sp,#272]
 ldp q10,q11,[sp,#304]
 ldp q12,q13,[sp,#336]
 ldp q14,q15,[sp,#368]
 ldp x19,x20,[sp,#400]
 ldp x21,x22,[sp,#416]
 ldp x17,x30,[sp,#128]
 add sp,sp,#704
 br x30
// Linux's MAP_SHARED, MAP_PRIVATE and MAP_FIXED are macOS's; MAP_ANONYMOUS
// 0x20 is 0x1000; MAP_NORESERVE has no meaning there.
xd_k_mmap:
 mov x7,#0x13
 and x6,x3,x7
 tst x3,#0x20
 b.eq xd_k_mmap_1
 orr x6,x6,#0x1000
xd_k_mmap_1:
 mov x3,x6
xd_k_plain:
 b xd_call
// open(path, flags, mode) is openat(AT_FDCWD, ...); the mode is variadic,
// so on the stack.
xd_k_open:
 mov x3,x2
 mov x2,x1
 mov x1,x0
 mov x0,#-100
xd_k_openat:
 bl xd_fd
 bl xd_oflags
 str x3,[sp]
 b xd_call
xd_k_stat:
 mov x3,#0
 b xd_k_stat_1
xd_k_lstat:
 mov x3,#0x20
xd_k_stat_1:
 mov x20,x1
 mov x2,x1
 mov x1,x0
 mov x0,#-2
 mov x19,#@stat
 b xd_call
xd_k_fstat:
 mov x20,x1
 mov x19,#@stat
 b xd_call
xd_k_fstatat:
 bl xd_fd
 bl xd_atflags
 mov x20,x2
 mov x19,#@stat
 b xd_call
// F_DUPFD_CLOEXEC is 67; F_SETFL's and F_GETFL's flags convert.
xd_k_fcntl:
 cmp x1,#1030
 b.ne xd_k_fcntl_1
 mov x1,#67
xd_k_fcntl_1:
 cmp x1,#4
 b.ne xd_k_fcntl_2
 bl xd_oflags
xd_k_fcntl_2:
 cmp x1,#3
 b.ne xd_k_fcntl_3
 mov x19,#@getfl
xd_k_fcntl_3:
 str x2,[sp]
 b xd_call
// fsync writes all the disk holds: fcntl(fd, F_FULLFSYNC), as Go's File.Sync
// is; a plain fsync of macOS stops at the disk's own memory.
xd_k_fullsync:
 mov x1,#51
 str xzr,[sp]
 b xd_call
xd_k_getcwd:
 mov x20,x0
 mov x19,#@getcwd
 b xd_call
// getdents64 is __getdirentries64, whose fourth argument is where it keeps
// the position.
xd_k_dents:
 mov x20,x1
 add x3,sp,#448
 mov x19,#@dents
 b xd_call
xd_k_clock:
 cmp x0,#7
 b.hi xd_call
 adr x6,xd_clocks
 ldrb w0,[x6,x0]
 b xd_call
// getrandom is getentropy, 256 bytes at a time.
xd_k_random:
 mov x20,x0
 mov x21,x1
xd_k_random_1:
 cbz x21,xd_k_random_2
 mov x1,#256
 cmp x21,x1
 csel x1,x21,x1,lo
 mov x0,x20
 add x20,x20,x1
 sub x21,x21,x1
@call _getentropy
 cmn x0,#1
 b.eq xd_errno
 b xd_k_random_1
xd_k_random_2:
 ldr x0,[sp,#32]
 b xd_back
// ppoll's timespec is poll's milliseconds, rounded up; none is -1.
xd_k_ppoll:
 mov x6,x2
 mov x2,#-1
 cbz x6,xd_call
 ldp x6,x7,[x6]
 mov x8,#1000
 mul x6,x6,x8
 movz x8,#0x4240
 movk x8,#0xf,lsl #16
 add x7,x7,x8
 sub x7,x7,#1
 udiv x7,x7,x8
 add x2,x6,x7
 b xd_call
xd_k_pipe2:
 mov x20,x0
 mov x21,x1
 mov x19,#@pipe2
 b xd_call
// mremap(MREMAP_MAYMOVE): a new mapping, the old one's bytes copied to it.
xd_k_mremap:
 cmp x2,x1
 b.ls xd_back
 mov x20,x0
 mov x21,x1
 mov x0,#0
 mov x1,x2
 mov x2,#3
 mov x3,#0x1002
 mov x4,#-1
 mov x5,#0
@call _mmap
 cmn x0,#1
 b.eq xd_errno
 mov x6,#0
xd_k_mremap_1:
 cmp x6,x21
 b.hs xd_k_mremap_2
 ldr x7,[x20,x6]
 str x7,[x0,x6]
 add x6,x6,#8
 b xd_k_mremap_1
xd_k_mremap_2:
 str x0,[sp,#440]
 mov x0,x20
 mov x1,x21
@call _munmap
 ldr x0,[sp,#440]
 b xd_back
// rt_sigaction's handler and flags as macOS's struct sigaction.
xd_k_sigaction:
 mov x6,x0
 bl xd_sig
 mov x0,x6
 mov x20,x2
 cbz x1,xd_k_sigaction_3
 ldp x6,x7,[x1]
 add x1,sp,#448
 str x6,[x1]
 mov x8,#0
 tbz x7,#28,xd_k_sigaction_1
 orr x8,x8,#2
xd_k_sigaction_1:
 tbz x7,#2,xd_k_sigaction_2
 orr x8,x8,#0x40
xd_k_sigaction_2:
 str wzr,[x1,#8]
 str w8,[x1,#12]
xd_k_sigaction_3:
 cbz x2,xd_k_sigaction_4
 add x2,sp,#464
xd_k_sigaction_4:
 mov x19,#@sigact
 b xd_call
// memfd_create: a file made by mkstemp and unlinked at once.
xd_k_memfd:
 add x0,sp,#448
 adr x6,xd_template
 ldp x7,x8,[x6]
 stp x7,x8,[x0]
 ldp x7,x8,[x6,#16]
 stp x7,x8,[x0,#16]
@call _mkstemp
 cmn x0,#1
 b.eq xd_errno
 str x0,[sp,#440]
 add x0,sp,#448
@call _unlink
 ldr x0,[sp,#440]
 mov x21,#0x80000
 bl xd_fdflags
 b xd_back
xd_k_kill:
 mov x6,x1
 bl xd_sig
 mov x1,x6
 b xd_call
xd_k_wait4:
 mov x20,x1
 mov x19,#@wait4
 b xd_call
xd_k_atfd:
 bl xd_fd
 b xd_call
xd_k_atflags:
 bl xd_fd
 bl xd_atflags
 b xd_call
// AT_REMOVEDIR 0x200 is 0x80.
xd_k_unlinkat:
 bl xd_fd
 and x6,x2,#0x200
 lsr x2,x6,#2
 b xd_call
// UTIME_NOW and UTIME_OMIT are -1 and -2.
xd_k_utimensat:
 bl xd_fd
 bl xd_atflags
 cbz x2,xd_call
 ldp x7,x8,[x2]
 ldp x9,x10,[x2,#16]
 mov x11,#0x3fffffff
 sub x12,x11,#1
 mov x13,#-2
 cmp x8,x11
 csinv x8,x8,xzr,ne
 cmp x8,x12
 csel x8,x13,x8,eq
 cmp x10,x11
 csinv x10,x10,xzr,ne
 cmp x10,x12
 csel x10,x13,x10,eq
 add x2,sp,#448
 stp x7,x8,[x2]
 stp x9,x10,[x2,#16]
 b xd_call
// AF_INET6 is 30; SOCK_NONBLOCK and SOCK_CLOEXEC are set after.
xd_k_socket:
 cmp x0,#10
 b.ne xd_k_socket_1
 mov x0,#30
xd_k_socket_1:
 movz x6,#0x800
 movk x6,#0x8,lsl #16
 and x21,x1,x6
 and x1,x1,#0xf
 mov x19,#@sockfl
 b xd_call
xd_k_sain:
 mov x8,x1
 mov x9,x2
 bl xd_sain
 mov x1,x8
 mov x2,x9
 b xd_call
xd_k_saout:
 mov x20,x1
 mov x19,#@saout
 b xd_call
xd_k_accept:
 mov x3,#0
xd_k_accept4:
 mov x20,x1
 mov x21,x3
 mov x19,#@accept4
 b xd_call
xd_k_sendto:
 bl xd_msgflags
 mov x8,x4
 mov x9,x5
 bl xd_sain
 mov x4,x8
 mov x5,x9
 b xd_call
xd_k_recvfrom:
 bl xd_msgflags
 mov x20,x4
 mov x19,#@saout
 b xd_call
// SO_ERROR's value is an errno.
xd_k_getsockopt:
 mov x20,#0
 cmp x1,#1
 b.ne xd_k_sockopt
 cmp x2,#4
 b.ne xd_k_sockopt
 mov x20,x3
 mov x19,#@soerror
// SOL_SOCKET is 0xffff, and its options and TCP's and IPV6_V6ONLY convert.
xd_k_sockopt:
 adr x6,xd_sockopts
 cmp x1,#1
 b.ne xd_k_sockopt_1
 mov x1,#0xffff
 b xd_k_sockopt_3
xd_k_sockopt_1:
 adr x6,xd_tcpopts
 cmp x1,#6
 b.eq xd_k_sockopt_3
 cmp x1,#41
 b.ne xd_call
 cmp x2,#26
 b.ne xd_call
 mov x2,#27
 b xd_call
xd_k_sockopt_3:
 ldp w7,w8,[x6],#8
 cbz w7,xd_call
 cmp x2,x7
 b.ne xd_k_sockopt_3
 mov x2,x8
 b xd_call
// A stat record of macOS's in place of x86-64 Linux's.
xd_p_stat:
 ldr w8,[x20]
 ldrh w9,[x20,#4]
 ldrh w10,[x20,#6]
 ldr x11,[x20,#8]
 ldp w12,w13,[x20,#16]
 ldr w14,[x20,#24]
 ldp x15,x17,[x20,#32]
 ldp x6,x7,[x20,#48]
 ldp x1,x2,[x20,#64]
 ldp x3,x4,[x20,#96]
 ldr w5,[x20,#112]
 str x8,[x20]
 str x11,[x20,#8]
 str x10,[x20,#16]
 str w9,[x20,#24]
 stp w12,w13,[x20,#28]
 str wzr,[x20,#36]
 str x14,[x20,#40]
 str x3,[x20,#48]
 str x5,[x20,#56]
 str x4,[x20,#64]
 stp x15,x17,[x20,#72]
 stp x6,x7,[x20,#88]
 stp x1,x2,[x20,#104]
 stp xzr,xzr,[x20,#120]
 str xzr,[x20,#136]
 mov x0,#0
 b xd_back
xd_p_getfl:
 bl xd_oback
 b xd_back
xd_p_getcwd:
 cbz x0,xd_errno
 mov x6,x20
xd_p_getcwd_1:
 ldrb w7,[x6],#1
 cbnz w7,xd_p_getcwd_1
 sub x0,x6,x20
 b xd_back
// Each record of macOS's (its length at 16, type at 20, name at 21) as
// Linux's (type at 18, name at 19).
xd_p_dents:
 mov x8,x20
 add x9,x20,x0
xd_p_dents_1:
 cmp x8,x9
 b.hs xd_back
 ldrh w10,[x8,#16]
 ldrb w11,[x8,#20]
 strb w11,[x8,#18]
 add x12,x8,#21
 add x13,x8,#19
xd_p_dents_2:
 ldrb w11,[x12],#1
 strb w11,[x13],#1
 cbnz w11,xd_p_dents_2
 add x8,x8,x10
 b xd_p_dents_1
// The signal of a status that has one, as Linux numbers it.
xd_p_wait4:
 cbz x20,xd_back
 cbz x0,xd_back
 ldr w8,[x20]
 and w6,w8,#0x7f
 cbz w6,xd_back
 cmp w6,#0x7f
 b.eq xd_p_wait4_1
 bl xd_sigback
 and w8,w8,#0xffffff80
 orr w8,w8,w6
 str w8,[x20]
 b xd_back
xd_p_wait4_1:
 ubfx x6,x8,#8,#8
 bl xd_sigback
 and w8,w8,#0xffff00ff
 orr w8,w8,w6,lsl #8
 str w8,[x20]
 b xd_back
xd_p_accept4:
 bl xd_saout
// A socket: SO_NOSIGPIPE, as Linux's sends with MSG_NOSIGNAL, and the
// flags X21 holds.
xd_p_sockfl:
 bl xd_fdflags
 str x0,[sp,#696]
 mov x1,#1
 str w1,[sp,#688]
 mov x1,#0xffff
 mov x2,#0x1022
 add x3,sp,#688
 mov x4,#4
@call _setsockopt
 ldr x0,[sp,#696]
 b xd_back
xd_p_saout:
 bl xd_saout
 b xd_back
xd_p_sigact:
 cbz x20,xd_back
 ldr x6,[sp,#464]
 str x6,[x20]
 stp xzr,xzr,[x20,#8]
 str xzr,[x20,#24]
 b xd_back
xd_p_soerror:
 ldr w6,[x20]
 cmp w6,#106
 b.hi xd_back
 adr x7,xd_errnos
 ldrb w6,[x7,x6]
 str w6,[x20]
 b xd_back
xd_p_pipe2:
 ldr w0,[x20]
 bl xd_fdflags
 ldr w0,[x20,#4]
 bl xd_fdflags
 mov x0,#0
 b xd_back
// AT_FDCWD (X0) is -2.
xd_fd:
 cmn x0,#100
 b.ne xd_fd_1
 mov x0,#-2
xd_fd_1:
 ret
// AT_SYMLINK_NOFOLLOW, AT_EACCESS and AT_SYMLINK_FOLLOW (X3).
xd_atflags:
 mov x6,#0
 tbz x3,#8,xd_atflags_1
 orr x6,x6,#0x20
xd_atflags_1:
 tbz x3,#9,xd_atflags_2
 orr x6,x6,#0x10
xd_atflags_2:
 tbz x3,#10,xd_atflags_3
 orr x6,x6,#0x40
xd_atflags_3:
 mov x3,x6
 ret
// open's flags (X2), and back (X0).
xd_oflags:
 and x6,x2,#3
 adr x7,xd_open_flags
xd_oflags_1:
 ldp w8,w9,[x7],#8
 cbz w8,xd_oflags_2
 tst x2,x8
 b.eq xd_oflags_1
 orr x6,x6,x9
 b xd_oflags_1
xd_oflags_2:
 mov x2,x6
 ret
xd_oback:
 and x6,x0,#3
 adr x7,xd_open_flags
xd_oback_1:
 ldp w8,w9,[x7],#8
 cbz w8,xd_oback_2
 tst x0,x9
 b.eq xd_oback_1
 orr x6,x6,x8
 b xd_oback_1
xd_oback_2:
 mov x0,x6
 ret
// The flags of send and recv (X3): MSG_DONTWAIT and MSG_WAITALL move;
// MSG_NOSIGNAL is the socket's SO_NOSIGPIPE.
xd_msgflags:
 and x6,x3,#7
 tbz x3,#6,xd_msgflags_1
 orr x6,x6,#0x80
xd_msgflags_1:
 tbz x3,#8,xd_msgflags_2
 orr x6,x6,#0x40
xd_msgflags_2:
 mov x3,x6
 ret
// A signal (X6) as macOS numbers it, and back.
xd_sig:
 cmp x6,#31
 b.hi xd_sig_1
 adr x7,xd_signals
 ldrb w6,[x7,x6]
xd_sig_1:
 ret
xd_sigback:
 cmp x6,#31
 b.hi xd_sigback_1
 adr x7,xd_signals_back
 ldrb w6,[x7,x6]
xd_sigback_1:
 ret
// The address X8 of X9 bytes as macOS's, at 448: its length in its first
// byte, the family in the second (AF_INET6 30); a path of at most 104.
xd_sain:
 cbz x8,xd_sain_4
 cmp x9,#128
 b.ls xd_sain_1
 mov x9,#128
xd_sain_1:
 add x10,sp,#448
 mov x11,#0
xd_sain_2:
 cmp x11,x9
 b.hs xd_sain_3
 ldrb w12,[x8,x11]
 strb w12,[x10,x11]
 add x11,x11,#1
 b xd_sain_2
xd_sain_3:
 ldrh w12,[x8]
 cmp w12,#10
 b.ne xd_sain_5
 mov w12,#30
xd_sain_5:
 cmp w12,#1
 b.ne xd_sain_6
 cmp x9,#106
 b.ls xd_sain_6
 mov x9,#106
xd_sain_6:
 strb w9,[x10]
 strb w12,[x10,#1]
 mov x8,x10
xd_sain_4:
 ret
// The address at X20 as Linux's: the family a 16-bit word.
xd_saout:
 cbz x20,xd_saout_1
 ldrb w6,[x20,#1]
 cmp w6,#30
 b.ne xd_saout_2
 mov w6,#10
xd_saout_2:
 strh w6,[x20]
xd_saout_1:
 ret
// FD_CLOEXEC and O_NONBLOCK on the descriptor X0 as Linux's flags X21 ask;
// X0 kept.
xd_fdflags:
 str x30,[sp,#432]
 str x0,[sp,#440]
 tbz x21,#19,xd_fdflags_1
 mov x1,#2
 mov x2,#1
 str x2,[sp]
@call _fcntl
xd_fdflags_1:
 tbz x21,#11,xd_fdflags_2
 ldr x0,[sp,#440]
 mov x1,#4
 mov x2,#4
 str x2,[sp]
@call _fcntl
xd_fdflags_2:
 ldr x0,[sp,#440]
 ldr x30,[sp,#432]
 ret
xd_errnos:
 .byte @errnos
xd_signals:
 .byte @signals
xd_signals_back:
 .byte @signals_back
xd_clocks:
 .byte 0, 6, 12, 16, 4, 0, 6, 6
 .balign 8
xd_template:
 .ascii "/tmp/alchem.XXXXXX"
 .space 14
// Linux's open flags and macOS's: O_CREAT, O_EXCL, O_NOCTTY, O_TRUNC,
// O_APPEND, O_NONBLOCK, O_DIRECTORY, O_NOFOLLOW, O_CLOEXEC, O_DSYNC, O_SYNC.
xd_open_flags:
 .word 0x40, 0x200, 0x80, 0x800, 0x100, 0x20000, 0x200, 0x400, 0x400, 0x8, 0x800, 0x4
 .word 0x10000, 0x100000, 0x20000, 0x100, 0x80000, 0x1000000, 0x1000, 0x400000, 0x100000, 0x80, 0, 0
// SO_REUSEADDR, SO_TYPE, SO_ERROR, SO_BROADCAST, SO_SNDBUF, SO_RCVBUF,
// SO_KEEPALIVE, SO_LINGER, SO_REUSEPORT, SO_RCVTIMEO, SO_SNDTIMEO.
xd_sockopts:
 .word 2, 4, 3, 0x1008, 4, 0x1007, 6, 0x20, 7, 0x1001, 8, 0x1002, 9, 8, 13, 0x1080, 15, 0x200
 .word 20, 0x1006, 21, 0x1005, 0, 0
// TCP_NODELAY, TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT.
xd_tcpopts:
 .word 1, 1, 4, 0x10, 5, 0x101, 6, 0x102, 0, 0
xd_table:
 .word @table, 0
 .balign 4'''
# Every runtime but the collector goes to the collector's routine.
DARWIN_STUB = '''x86_syscall:
 ldr x16,[x26]
 br x16'''
SYSCALL = '''x86_syscall:
 stp x1,x2,[sp,#-112]!
 stp x3,x4,[sp,#16]
 stp x5,x8,[sp,#32]
 stp x9,x10,[sp,#48]
 stp x30,x19,[sp,#64]
 stp x20,x21,[sp,#80]
 mov x17,x0
 mov x0,x5
 mov x1,x4
 mov x3,x10
 ldr x4,[sp,#40]
 mov x5,x9
 mov x20,#0
 adr x16,x86_sysno
 mov x8,#-1
1:
 ldp w6,w7,[x16],#8
 cmp w6,#-1
 b.eq 2f
 cmp x6,x17
 b.ne 1b
 mov x8,x7
2:
 // Calls ARM64 Linux has only in a form with other arguments.
 cmp x17,#2
 b.eq x86_open
 cmp x17,#257
 b.eq x86_openat
 cmp x17,#4
 b.eq x86_stat
 cmp x17,#6
 b.eq x86_lstat
 cmp x17,#5
 b.eq x86_fstat
 cmp x17,#262
 b.eq x86_fstatat
 cmp x17,#21
 b.eq x86_access
 cmp x17,#22
 b.eq x86_pipe
 cmp x17,#33
 b.eq x86_dup2
 cmp x17,#57
 b.eq x86_fork
 cmp x17,#82
 b.eq x86_rename
 cmp x17,#83
 b.eq x86_mkdir
 cmp x17,#84
 b.eq x86_rmdir
 cmp x17,#87
 b.eq x86_unlink
 cmp x17,#89
 b.eq x86_readlink
 cmp x17,#90
 b.eq x86_chmod
 cmp x17,#213
 b.eq x86_epoll_create
 cmp x17,#232
 b.eq x86_epoll_wait
 cmp x17,#7
 b.eq x86_poll
 cmp x17,#86
 b.eq x86_link
 cmp x17,#88
 b.eq x86_symlink
x86_call:
 cmn x8,#1
 b.eq 3f
 svc #0
 b 4f
3:
 mov x0,#-38
4:
 // A stat buffer (X20) in x86-64's layout: nlink and mode trade places and
 // sizes, rdev and blksize move.
 cbz x20,5f
 cbnz x0,5f
 ldr w6,[x20,#16]
 ldr w7,[x20,#20]
 ldp w9,w10,[x20,#24]
 ldr x16,[x20,#32]
 ldrsw x17,[x20,#56]
 str x7,[x20,#16]
 str w6,[x20,#24]
 stp w9,w10,[x20,#28]
 str wzr,[x20,#36]
 str x16,[x20,#40]
 str x17,[x20,#56]
5:
 ldp x1,x2,[sp]
 ldp x3,x4,[sp,#16]
 ldp x5,x8,[sp,#32]
 ldp x9,x10,[sp,#48]
 ldp x30,x19,[sp,#64]
 ldp x20,x21,[sp,#80]
 add sp,sp,#112
 br x30
// x86-64's open flags where ARM64's differ: O_DIRECT 0x4000 and
// O_DIRECTORY 0x10000, O_LARGEFILE 0x8000 and O_NOFOLLOW 0x20000 trade.
x86_flags:
 and x6,x2,#0xfffffffffffc3fff
 tbz x2,#14,6f
 orr x6,x6,#0x10000
6:
 tbz x2,#16,6f
 orr x6,x6,#0x4000
6:
 tbz x2,#15,6f
 orr x6,x6,#0x20000
6:
 tbz x2,#17,6f
 orr x6,x6,#0x8000
6:
 mov x2,x6
 ret
x86_open:
 mov x3,x2
 mov x2,x1
 mov x1,x0
 mov x0,#-100
 mov x8,#56
 bl x86_flags
 b x86_call
x86_openat:
 bl x86_flags
 b x86_call
x86_stat:
 mov x3,#0
 b 7f
x86_lstat:
 mov x3,#0x100
7:
 mov x2,x1
 mov x1,x0
 mov x0,#-100
 mov x8,#79
 mov x20,x2
 b x86_call
x86_fstat:
 mov x20,x1
 b x86_call
x86_fstatat:
 mov x20,x2
 b x86_call
x86_access:
 mov x3,#0
 mov x2,x1
 mov x1,x0
 mov x0,#-100
 mov x8,#48
 b x86_call
x86_pipe:
 mov x1,#0
 mov x8,#59
 b x86_call
x86_dup2:
 cmp x0,x1
 b.ne 8f
 // dup2 of a descriptor onto itself: it, when it is open.
 mov x21,x0
 mov x1,#1
 mov x8,#25
 svc #0
 tbnz x0,#63,5b
 mov x0,x21
 b 5b
8:
 mov x2,#0
 mov x8,#24
 b x86_call
x86_fork:
 mov x0,#17
 mov x1,#0
 mov x2,#0
 mov x3,#0
 mov x4,#0
 mov x8,#220
 b x86_call
x86_rename:
 mov x3,x1
 mov x2,#-100
 mov x1,x0
 mov x0,#-100
 mov x8,#38
 b x86_call
x86_mkdir:
 mov x2,x1
 mov x1,x0
 mov x0,#-100
 mov x8,#34
 b x86_call
x86_rmdir:
 mov x2,#0x200
 b 9f
x86_unlink:
 mov x2,#0
9:
 mov x1,x0
 mov x0,#-100
 mov x8,#35
 b x86_call
x86_readlink:
 mov x3,x2
 mov x2,x1
 mov x1,x0
 mov x0,#-100
 mov x8,#78
 b x86_call
x86_chmod:
 mov x2,x1
 mov x1,x0
 mov x0,#-100
 mov x8,#53
 b x86_call
x86_link:
 // link(old, new) is linkat(AT_FDCWD, old, AT_FDCWD, new, 0).
 mov x3,x1
 mov x2,#-100
 mov x1,x0
 mov x0,#-100
 mov x4,#0
 mov x8,#37
 b x86_call
x86_symlink:
 // symlink(target, link) is symlinkat(target, AT_FDCWD, link).
 mov x2,x1
 mov x1,#-100
 mov x8,#36
 b x86_call
x86_epoll_create:
 mov x0,#0
 mov x8,#20
 b x86_call
x86_epoll_wait:
 mov x4,#0
 mov x5,#8
 mov x8,#22
 b x86_call
x86_poll:
 // poll(fds, n, ms) is ppoll(fds, n, a timespec of ms or none, no mask).
 mov x8,#73
 mov x3,#0
 tbnz x2,#63,10f
 mov x6,#1000
 udiv x7,x2,x6
 msub x6,x7,x6,x2
 mov x16,#16960
 movk x16,#15,lsl #16
 mul x6,x6,x16
 stp x7,x6,[sp,#96]
 add x2,sp,#96
 b x86_call
10:
 mov x2,#0
 b x86_call
x86_sysno:
 .word 0,63, 1,64, 3,57, 5,80, 8,62, 9,222, 10,226, 11,215, 12,214, 13,134, 14,135, 15,139
 .word 16,29, 17,67, 18,68, 19,65, 20,66, 24,124, 25,216, 28,233, 32,23, 35,101, 39,172, 40,71
 .word 41,198, 42,203, 43,202, 44,206, 45,207, 46,211, 47,212, 48,210, 49,200, 50,201, 51,204, 52,205
 .word 54,208, 55,209, 56,220, 59,221, 60,93, 61,260, 62,129, 63,160, 72,25, 73,32, 74,82, 75,83
 .word 76,45, 77,46, 79,17, 80,49, 81,50, 91,52, 93,55, 95,166, 96,169, 97,163, 98,165, 99,179
 .word 102,174, 104,176, 105,146, 106,144, 107,175, 108,177, 109,154, 110,173, 112,157, 121,155, 131,132, 157,167
 .word 186,178, 202,98, 217,61, 218,96, 228,113, 229,114, 230,115, 231,94, 233,21, 234,131, 257,56, 258,34
 .word 260,54, 262,79, 263,35, 264,38, 265,37, 266,36, 267,78, 268,53, 269,48, 270,72, 271,73, 280,88
 .word 281,22, 288,242, 290,19, 291,20, 292,24, 293,59, 302,261, 316,276, 318,278, 319,279, 332,291
 .word 326,285, 439,439, 435,435, 424,424, 425,425, 426,426, 427,427
 .word -1,-1'''


def main():
    defines = [a.split('=')[0] for a in sys.argv[2:] if a.startswith('STRESS')]
    try:
        sys.stdout.write(translate(open(sys.argv[1]).read(), defines))
    except Untranslated as error:
        sys.stderr.write(f'x86-to-arm64: {error}\n')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
