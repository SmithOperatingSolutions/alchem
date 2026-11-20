#!/usr/bin/env python3
"""Both translations of x86-64 to ARM64 against the machine they translate
for: random sequences of instructions run natively and, translated, under
QEMU, from the same registers and memory; the registers, the memory and what
each conditional jump decided must be the same afterwards.

scripts/x86-to-arm64.py translates the runtimes (spec/*-x86_64.s) and is
given every kind of sequence. The compiler's own translation of each
function (native-x86arm.alc, xa_function) is given the sequences made of
what the compiler emits: a program built from the compiler's source with
that function as its entry turns the x86-64 bytes of a sequence into ARM64
bytes, which run between a start and an end translated by the first."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location
from run import ROOT

sys.path.insert(0, str(ROOT / 'scripts'))
import arm64_runtime  # noqa: E402

TOOLS = ROOT / 'build/arm64-tools/bin'
# Registers the sequences use: not RSP, RBP (frame), R14 (the program's)
# or R11 (RCX and R11 are what syscall takes; kept simple).
REGS = ['rax', 'rcx', 'rdx', 'rbx', 'rsi', 'rdi', 'r8', 'r9', 'r10', 'r12', 'r13', 'r15']
R32 = {'rax': 'eax', 'rcx': 'ecx', 'rdx': 'edx', 'rbx': 'ebx', 'rsi': 'esi', 'rdi': 'edi', 'r8': 'r8d', 'r9': 'r9d',
       'r10': 'r10d', 'r12': 'r12d', 'r13': 'r13d', 'r15': 'r15d'}
R8 = {'rax': 'al', 'rcx': 'cl', 'rdx': 'dl', 'rbx': 'bl', 'rsi': 'sil', 'rdi': 'dil', 'r8': 'r8b', 'r9': 'r9b',
      'r10': 'r10b', 'r12': 'r12b', 'r13': 'r13b', 'r15': 'r15b'}
CONDS = ['e', 'ne', 'b', 'ae', 'be', 'a', 'l', 'ge', 'le', 'g', 's', 'ns', 'o', 'no', 'c', 'nc']


def imm(rng):
    return rng.choice([0, 1, -1, 7, 255, 4095, -4096, 65536, 0x7fffffff, -0x80000000, rng.randrange(-1000, 1000)])


def instruction(rng, n, kinds=range(43)):
    """One random instruction (and, for flag readers, what it needs) of one of kinds."""
    return instruction_of(rng, n, rng.choice(kinds))


def instruction_of(rng, n, kind):
    a, b = rng.choice(REGS), rng.choice(REGS)
    mem = f'qword ptr [rbp-{8 * rng.randrange(1, 9)}]'
    if kind == 42:
        # Flags carried by an unconditional jump to where they are read.
        c = rng.choice(CONDS)
        return [rng.choice([f'cmp {a},{b}', f'add {a},{b}', f'sub {b},{a}', f'test {a},{b}']), 'jmp 1f', 'inc r15', '1:',
                rng.choice([f'set{c} {R8[a]}', f'adc {a},{b}', f'dec {R8[b]}', f'inc {b}']), f'set{c} {R8[b]}']
    if kind == 41:
        # loop (RCX counted down, the flags kept) and jrcxz.
        a = rng.choice([r for r in REGS if r != 'rcx'])
        return rng.choice([['and rcx,7', 'or rcx,1', '1:', f'add {a},rcx', 'loop 1b'],
                           ['and rcx,1', 'jrcxz 1f', 'add r15,9', '1:'],
                           [f'cmp {a},{b}', 'and ecx,3', 'jrcxz 1f', f'set{rng.choice(CONDS)} {R8[a]}', '1:']])
    if kind == 40:
        # A routine that leaves its caller flags (bn_cmp of the float
        # runtime): from a comparison, or from a test on another way out.
        c = rng.choice(CONDS)
        body = rng.choice([[f'cmp {a},{b}'], [f'test {a},{b}'], [f'add {a},{b}'], [f'cmp {a},{b}', 'jne 6f', f'test {b},{b}', '6:'],
                           [f'sub {a},{b}', 'jb 6f', f'and {b},{a}', '6:'], [f'cmp {a},{imm(rng)}', f'mov {b},{a}']])
        return ['call 7f', f'j{c} 8f', 'add r15,5', '8:', 'jmp 9f', '7:', *body, 'ret', '9:']
    if kind == 39:
        # An address of 32-bit registers: computed in 32 bits.
        return [f'lea {rng.choice([a, R32[a]])},[{R32[b]}+{rng.choice(["ecx*8", "edx*2", "esi"])}-{rng.randrange(0, 300)}]'.replace('+-', '-')]
    if kind in (37, 38):
        # A carry chain in a loop, entered after logic, a comparison or an
        # addition, ended by inc, dec or lea and a jump back.
        a, b = rng.choice([r for r in REGS if r != 'r9']), rng.choice([r for r in REGS if r != 'r9'])
        first = rng.choice(['xor r9d,r9d', 'clc', 'stc', f'cmp {a},{b}', f'add {a},{b}', f'sub {b},{a}', f'test {a},{b}'])
        step = rng.choice([f'adc {a},{b}', f'sbb {a},{b}', f'adc {a},[rbp-8]', f'sbb {b},[rbp-16]'])
        return [first, f'mov r9d,{rng.randrange(1, 5)}' if 'r9' not in first else 'lea r9,[r9+3]', '1:', step,
                rng.choice(['dec r9', 'dec r9d']), 'jnz 1b', rng.choice([f'sbb {b},{b}', f'adc {b},0', f'setc {R8[b]}', f'ja 1f', f'jbe 1f']), 'inc r15', '1:'] if rng.random() < .5 else \
            [first, 'mov r9d,0', '1:', step, 'inc r9', 'cmp r9,3', 'jb 1b', f'sbb {b},{b}']
    if kind == 33:
        # inc and dec keep the carry an adc, sbb or setc reads after them.
        first = rng.choice([f'cmp {a},{b}', f'add {a},{b}', f'sub {b},{a}', 'stc', 'clc'])
        step = rng.choice([f'inc {b}', f'dec {b}', f'inc {R8[b]}', f'dec {R8[b]}', f'dec {R32[b]}'])
        return [first, step, rng.choice([f'adc {a},{b}', f'sbb {a},{b}', f'setc {R8[a]}', f'sete {R8[a]}'])]
    if kind == 34:
        # Through the carry: rcr and rcl by 1, then the carry they leave.
        first = rng.choice([f'cmp {a},{b}', f'shr {b},1', f'add {a},{b}', 'stc', 'clc'])
        return [first, f'{rng.choice(["rcr", "rcl"])} {a},1', f'sbb {b},{b}']
    if kind in (35, 36):
        return vector(rng, a, b)
    if kind == 31:
        # Floating-point comparisons, NaN among the operands now and then.
        c = rng.choice(['e', 'ne', 'b', 'ae', 'be', 'a', 'p', 'np'])
        return [f'movq xmm0,{a}', f'movq xmm1,{b}', 'ucomisd xmm0,xmm1', f'j{c} 1f', 'lea r15,[r15+3]', '1:', f'set{c} {R8[b]}']
    if kind == 32:
        # Arithmetic on doubles made from integers, a divisor never 0: NaN's
        # sign is x86-64's or ARM64's own (spec/arm64.md), so none is made.
        op = rng.choice(['addsd', 'subsd', 'mulsd', 'divsd'])
        return [f'cvtsi2sd xmm2,{R32[a]}', f'or {R32[b]},1', f'cvtsi2sd xmm3,{R32[b]}', f'{op} xmm2,xmm3', f'movq {a},xmm2']
    if kind == 28:
        # Byte and word comparisons and tests: their flags are those of the size.
        c = rng.choice(CONDS)
        first = rng.choice([f'cmp {R8[a]},{R8[b]}', f'test {R8[a]},{R8[b]}', f'cmp {R8[a]},{rng.randrange(-128, 128)}', f'cmp byte ptr [rbp-{8 * rng.randrange(1, 9)}],{rng.randrange(0, 256) - 128}',
                            f'add {R8[a]},{R8[b]}', f'sub {R8[a]},{R8[b]}', f'inc {R8[a]}', f'dec {R8[a]}', f'neg {R8[a]}'])
        if first.startswith(('inc', 'dec')):
            # inc and dec leave the carry before them, which may be one x86
            # leaves undefined (after div, imul, bt): no reader of it here.
            c = rng.choice(['e', 'ne', 's', 'ns', 'o', 'no', 'l', 'ge', 'le', 'g'])
        return [first, f'set{c} {R8[b]}']
    if kind == 29:
        c = rng.choice(CONDS)
        return [f'cmp {R32[a]},{R32[b]}', f'j{c} 1f', 'inc r15', '1:']
    if kind == 30:
        c = rng.choice(CONDS)
        return [rng.choice([f'test {R8[a]},{R8[a]}', f'cmp {R8[a]},13', f'and {R8[a]},{R8[b]}', f'or {R8[a]},{R8[b]}', f'xor {R8[a]},{R8[b]}']), f'j{c} 1f', 'add r15,7', '1:']
    if kind == 22:
        # mul and div: RDX:RAX; RDX made smaller than the divisor first.
        return [f'mul {a}'] if rng.random() < .5 else ['mov rdx,0' if rng.random() < .7 else 'and rdx,3', 'or r9,4', 'div r9']
    if kind == 23:
        # A bit string in the frame: RCX is 0..63 at the start (an offset that
        # stays inside the 64 bytes below RBP when it is masked).
        return ['and rcx,63', 'lea r9,[rbp-64]', f'{rng.choice(["bt", "bts", "btr"])} qword ptr [r9],rcx', f'setc {R8[b]}']
    if kind == 24:
        return ['and rcx,7', 'lea rdi,[rbp-64]', 'mov rax,rdx', 'cld', 'rep stosq']
    if kind == 25:
        return ['and rcx,31', 'lea rsi,[rbp-64]', 'lea rdi,[rbp-32]', 'cld', 'rep movsb']
    if kind == 26:
        return ['and rcx,63', f'{rng.choice(["shl", "shr", "sar"])} {a if a != "rcx" else "rax"},cl']
    if kind == 27:
        return [f'or {b},1', f'bsr {a},{b}', f'bsf {b},{a if a != b else "rdx"}']
    if kind == 0:
        return [f'mov {a},{b}']
    if kind == 1:
        return [f'mov {a},{imm(rng)}']
    if kind == 2:
        return [f'mov {a},{mem}'] if rng.random() < .5 else [f'mov {mem},{a}']
    if kind == 3:
        op = rng.choice(['add', 'sub', 'and', 'or', 'xor'])
        return [f'{op} {a},{b}'] if rng.random() < .6 else [f'{op} {a},{imm(rng)}']
    if kind == 4:
        op = rng.choice(['add', 'sub', 'and', 'or', 'xor', 'cmp'])
        return [f'{op} {a},{mem}'] if rng.random() < .5 else [f'{op} {mem},{a}']
    if kind == 5:
        return [f'cmp {a},{b}'] if rng.random() < .5 else [f'cmp {a},{imm(rng)}']
    if kind == 6:
        return [f'test {a},{b}']
    if kind == 7:
        return [f'{rng.choice(["inc", "dec", "neg", "not"])} {a}']
    if kind == 8:
        return [f'{rng.choice(["shl", "shr", "sar"])} {a},{rng.randrange(1, 64)}']
    if kind == 9:
        return [f'imul {a},{b}']
    if kind == 10:
        return [f'lea {a},[{b}+{rng.choice(["rcx*8", "rdx*2", "rsi"])}-{rng.randrange(0, 300)}]'.replace('+-', '-')]
    if kind == 11:
        return [f'movzx {R32[a]},{R8[b]}'] if rng.random() < .5 else [f'movsx {a},{R8[b]}']
    if kind == 12:
        return [f'mov {R32[a]},{R32[b]}']
    # A flag reader follows what sets the flags it reads (x86 leaves some
    # undefined after bt, imul, shifts).
    setter = rng.choice([f'cmp {a},{b}', f'cmp {b},{imm(rng)}', f'sub {b},{a}', f'add {b},{a}', f'test {a},{b}',
                         f'and {b},{a}', f'or {b},{a}', f'xor {b},{a}', f'neg {b}', f'cmp {mem},{a}'])
    if kind == 13:
        c = rng.choice(CONDS)
        return [setter, f'set{c} {R8[a]}']
    if kind == 14:
        # Two cmovs on one comparison: the second reads the flags the first left.
        c, d = rng.choice(CONDS), rng.choice(CONDS)
        return [setter, f'cmov{c} {a},{b}', f'cmov{d} {b},{a}']
    if kind == 15:
        c = rng.choice(CONDS)
        return [setter, f'j{c} 1f', f'add r15,{rng.randrange(1, 100)}', '1:']
    if kind == 16:
        return [f'bsr {a},{b}'] if rng.random() < .5 else [f'bsf {a},{b}']
    if kind == 17:
        return [f'bt {a},{rng.randrange(64)}', f'setc {R8[b]}']
    if kind == 18:
        first = rng.choice([f'cmp {a},{b}', f'add {a},{b}', f'sub {b},{a}', f'bt {a},{rng.randrange(64)}'])
        return [first, f'adc {a},{b}'] if rng.random() < .5 else [first, f'sbb {a},{b}']
    if kind == 19:
        return [f'xchg {a},{b}']
    if kind == 20:
        return [f'push {a}', f'pop {b}']
    first = rng.choice([f'add {a},{b}', f'sub {a},{b}', f'imul {a},{b}', f'shl {a},{rng.randrange(1, 64)}', f'shr {a},{rng.randrange(1, 64)}'])
    reads = ['o', 'no', 'c', 'nc'] if first.startswith('imul') else (['c', 'nc'] if first.startswith('sh') else ['o', 'no', 'c', 'nc', 's', 'e'])
    return [first, f'j{rng.choice(reads)} 1f', 'inc r15', '1:']


def vector(rng, a, b):
    """128-bit SSE and AES-NI (the TLS runtime): two vectors from the frame,
    one operation, the result written back to it."""
    x, y = rng.sample(range(8), 2)
    load = [f'movdqu xmm{x},[rbp-{16 * rng.randrange(1, 5)}]', f'movdqu xmm{y},[rbp-{16 * rng.randrange(1, 5)}]']
    op = rng.choice(['pand', 'por', 'pxor', 'pandn', 'pcmpgtb', 'pcmpeqb', 'paddb', 'paddd', 'paddq', 'psubb', 'psubd',
                     'pshufb', 'aesenc', 'aesenclast', 'aesdec', 'aesdeclast', 'aesimc', 'shift', 'bytes', 'pshufd',
                     'pclmulqdq', 'movd', 'memory'])
    if op == 'shift':
        body = [f'{rng.choice(["pslld", "psrld", "psllq", "psrlq"])} xmm{x},{rng.randrange(0, 70)}']
    elif op == 'bytes':
        body = [f'{rng.choice(["pslldq", "psrldq"])} xmm{x},{rng.randrange(0, 18)}']
    elif op == 'pshufd':
        body = [f'pshufd xmm{x},xmm{rng.choice([x, y])},{rng.randrange(256)}']
    elif op == 'pclmulqdq':
        body = [f'pclmulqdq xmm{x},xmm{y},{rng.choice([0, 1, 0x10, 0x11])}']
    elif op == 'movd':
        body = rng.choice([[f'movd xmm{x},{R32[a]}'], [f'movq xmm{x},{a}'], [f'movd {R32[a]},xmm{y}'], [f'movq {a},xmm{y}']])
    elif op == 'memory':
        body = [f'{rng.choice(["pxor", "pand", "por", "paddd"])} xmm{x},[rbp-{16 * rng.randrange(1, 5)}]']
    else:
        body = [f'{op} xmm{x},xmm{y}']
    return [*load, *body, f'movdqu [rbp-{16 * rng.randrange(1, 5)}],xmm{x}']


def program(lines, registers, memory):
    """Assembly that sets the registers and 64 bytes of frame, runs lines, and
    writes the registers and the frame to standard output."""
    setup = [f' mov {r},{v}' for r, v in zip(REGS, registers)]
    frame = [f' mov qword ptr [rbp-{8 * (i + 1)}],{v}' if -2**31 <= v < 2**31 else f' mov r11,{v}\n mov qword ptr [rbp-{8 * (i + 1)}],r11'
             for i, v in enumerate(memory)]
    out = [f' mov [rbp+{8 * i}],{r}' for i, r in enumerate(REGS)]
    return '\n'.join(['.intel_syntax noprefix', '.text', '.global _start', '_start:',
                      ' lea rbp,[rip+frame+512]', ' mov rsp,rbp', ' sub rsp,256',
                      *setup, *frame, ' fuzz_body:', ' xor r11d,r11d', *(' ' + l if not l.endswith(':') else l for l in lines), ' fuzz_end:', *out,
                      ' mov edi,1', ' lea rsi,[rbp-64]', f' mov edx,{64 + 8 * len(REGS)}', ' mov eax,1', ' syscall',
                      ' mov edi,0', ' mov eax,60', ' syscall',
                      '.data', 'frame: .zero 1024']) + '\n'


def build_x86(root, source):
    (root / 'x.s').write_text(source)
    subprocess.run(['as', '--64', '-o', str(root / 'x.o'), str(root / 'x.s')], check=True)
    subprocess.run(['ld', '-Tdata=0x480000', '-o', str(root / 'x'), str(root / 'x.o')], check=True)
    return root / 'x'


def build_arm(root, source):
    translator = arm64_runtime.translator()
    # The data section is the frame: kept as data by the translator, which
    # copies directives; .data is put back for the linker.
    text = translator.translate(source).replace('.zero 1024', '.data\n.zero 1024')
    (root / 'a.s').write_text(text)
    subprocess.run([str(TOOLS / 'aarch64-linux-gnu-as'), '-march=armv8-a+crypto', '-o', str(root / 'a.o'), str(root / 'a.s')], check=True)
    subprocess.run([str(TOOLS / 'aarch64-linux-gnu-ld'), '-e', '_start', '-Tdata=0x480000', '-o', str(root / 'a'), str(root / 'a.o')], check=True)
    return root / 'a'


def translator(root, compiler):
    """The compiler's translation as a program: the compiler's source for
    ARM64 with xa_function as the entry, built by compiler."""
    spec = spec_from_file_location('alchem_bootstrap', ROOT / 'scripts/bootstrap-alchem-compiler.py')
    bootstrap = module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    text = bootstrap.source_text('functions', False)
    entry = '  def native_compile(source: bytes): bytes do nc_compile(source) end\n'
    switch = '  def nc_arm(): integer do 0 end\n'
    assert text.count(entry) == 1 and text.count(switch) == 1, 'the compiler source has no single entry or nc_arm()'
    text = text.replace(entry, '  def native_compile(source: bytes): bytes do xa_function(source) end\n')
    text = text.replace(switch, '  def nc_arm(): integer do 1 end\n')
    text = bootstrap.compact_identifiers(bootstrap.compact_source(text))
    made = subprocess.run([str(compiler)], input=text.encode(), capture_output=True, env={'PATH': ''}, timeout=600)
    assert (made.returncode, made.stderr) == (0, b''), ('translator program', made.returncode, made.stderr[:300])
    path = root / 'xa'
    path.write_bytes(made.stdout)
    path.chmod(0o700)
    return path


# What the compiler's code is made of: the kinds of instruction() the
# compiler's translation is given (no SSE vectors, AES, rcl/rcr, stc/clc,
# addresses of 32-bit registers or flags a routine leaves its caller, which
# only the runtimes use).
COMPILER_KINDS = [k for k in range(43) if k not in (33, 34, 35, 36, 39, 40)]


def build_compiled(root, source, xa):
    """The program with its body (between fuzz_body and fuzz_end) translated
    by the compiler's translation, the rest by scripts/x86-to-arm64.py."""
    head, rest = source.split(' fuzz_body:\n')
    body, tail = rest.split(' fuzz_end:\n')
    (root / 'b.s').write_text('.intel_syntax noprefix\n.text\n' + body + ' mov r11,r11\n')
    subprocess.run(['as', '--64', '-o', str(root / 'b.o'), str(root / 'b.s')], check=True)
    subprocess.run(['objcopy', '-O', 'binary', '-j', '.text', str(root / 'b.o'), str(root / 'b.bin')], check=True)
    made = subprocess.run([str(xa)], input=(root / 'b.bin').read_bytes(), capture_output=True, timeout=60)
    assert made.returncode == 0 and len(made.stdout) % 4 == 0, ('compiler translation', made.returncode, made.stderr[:200])
    words = [int.from_bytes(made.stdout[i:i + 4], 'little') for i in range(0, len(made.stdout), 4)]
    text = arm64_runtime.translator().translate(head + 'fuzz_body:\n' + tail).replace('.zero 1024', '.data\n.zero 1024')
    text = text.replace('fuzz_body:\n', 'fuzz_body:\n' + ''.join(f' .inst {w:#x}\n' for w in words), 1)
    (root / 'c.s').write_text(text)
    subprocess.run([str(TOOLS / 'aarch64-linux-gnu-as'), '-march=armv8-a+crypto', '-o', str(root / 'c.o'), str(root / 'c.s')], check=True)
    subprocess.run([str(TOOLS / 'aarch64-linux-gnu-ld'), '-e', '_start', '-Tdata=0x480000', '-o', str(root / 'c'), str(root / 'c.o')], check=True)
    return root / 'c'


def verify(count=300, seed=1, compiler=None):
    rng = random.Random(seed)
    checked = compiled = 0
    with tempfile.TemporaryDirectory(prefix='alchem-x86-to-arm64-') as d:
        root = Path(d)
        xa = translator(root, compiler) if compiler else None
        for case in range(count):
            # Every other sequence, when the compiler is given, is one for its translation too.
            both = xa is not None and case % 2 == 0
            lines = [l for _ in range(rng.randrange(3, 12)) for l in instruction(rng, case, COMPILER_KINDS if both else range(43))]
            # Numeric labels must be distinct for 1f to mean the next one.
            fixed, n = [], 0
            for l in lines:
                if l == '1:':
                    n += 1
                    fixed.append(f'{100 + n}:')
                else:
                    fixed.append(l.replace('1f', f'{101 + n}f').replace('1b', f'{100 + n}b'))
            registers = [rng.choice([0, 1, -1, 2**63 - 1, -2**63, rng.randrange(-2**63, 2**63), rng.randrange(256)]) for _ in REGS]
            registers[1] = rng.randrange(0, 64)    # RCX: shift counts, indexes
            registers[2] = rng.randrange(0, 64)
            registers[4] = rng.randrange(0, 64)
            memory = [rng.randrange(-2**63, 2**63) for _ in range(8)]
            source = program(fixed, registers, memory)
            x86 = subprocess.run([str(build_x86(root, source))], capture_output=True, timeout=10)
            words = lambda b: [int.from_bytes(b[i:i + 8], 'little', signed=True) for i in range(0, len(b), 8)]
            arm = subprocess.run([str(TOOLS / 'qemu-aarch64-static'), str(build_arm(root, source))], capture_output=True, timeout=10)
            if (x86.returncode, x86.stdout) != (arm.returncode, arm.stdout):
                raise AssertionError(('translated sequence differs', fixed, registers, words(x86.stdout), words(arm.stdout), arm.stderr[:200]))
            checked += 1
            if both:
                arm = subprocess.run([str(TOOLS / 'qemu-aarch64-static'), str(build_compiled(root, source, xa))], capture_output=True, timeout=10)
                if (x86.returncode, x86.stdout) != (arm.returncode, arm.stdout):
                    raise AssertionError(('compiler translation differs', fixed, registers, words(x86.stdout), words(arm.stdout), arm.stderr[:200]))
                compiled += 1
    print(f'PASS x86_to_arm64: {checked} random instruction sequences give the same registers, frame and branches natively and translated under QEMU'
          + (f', {compiled} of them translated by the compiler as well' if xa else ''))


if __name__ == '__main__':
    verify(int(sys.argv[1]) if len(sys.argv) > 1 else 150, compiler=Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None)
