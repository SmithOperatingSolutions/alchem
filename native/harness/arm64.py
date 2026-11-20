#!/usr/bin/env python3
"""The linux/arm64 port (spec/arm64.md): the ARM64 instruction encoders
(native-arm64.alc) give the words GNU as gives for the same instructions, and
the compiler built for ARM64 makes AArch64 executables. Needs the tools of
scripts/fetch-arm64-tools.sh."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from run import ROOT

TOOLS=ROOT/'build/arm64-tools/bin'
# (encoder call, the instructions GNU as reads for it)
CASES=[('a_movz(0,42,0)','movz x0,#42'),('a_mov_imm(3,305419896)','movz x3,#0x5678\nmovk x3,#0x1234,lsl #16'),('a_mov_imm(1,-2)','movn x1,#1'),
       ('a_mov_imm(2,-305419897)','movn x2,#0x5678\nmovk x2,#0xedcb,lsl #16'),('a_mov_imm(5,9223372036854775807)','movz x5,#0xffff\nmovk x5,#0xffff,lsl #16\nmovk x5,#0xffff,lsl #32\nmovk x5,#0x7fff,lsl #48'),
       ('a_mov_imm(6,-9223372036854775807-1)','movn x6,#0xffff\nmovk x6,#0,lsl #16\nmovk x6,#0,lsl #32\nmovk x6,#0x8000,lsl #48'),('a_mov_imm(7,0)','movz x7,#0'),('a_mov_imm(7,65536)','movz x7,#0\nmovk x7,#1,lsl #16'),
       ('a_mov(28,4)','mov x28,x4'),('a_add_imm(1,2,4095,0)','add x1,x2,#4095'),('a_sub_imm(29,28,160,0)','sub x29,x28,#160'),('a_add_imm(3,4,7,1)','adds x3,x4,#7'),('a_add_imm(14,31,0,0)','mov x14,sp'),
       ('a_sub(0,1,2,1)','subs x0,x1,x2'),('a_add(0,1,2,0)','add x0,x1,x2'),('a_and(0,1,2,1)','ands x0,x1,x2'),('a_and(0,1,2,0)','and x0,x1,x2'),('a_orr(3,4,5)','orr x3,x4,x5'),('a_eor(3,4,5)','eor x3,x4,x5'),
       ('a_mul(0,1,2)','mul x0,x1,x2'),('a_smulh(16,1,2)','smulh x16,x1,x2'),('a_sdiv(0,1,2)','sdiv x0,x1,x2'),('a_lsl(0,1,2)','lsl x0,x1,x2'),('a_lsr(0,1,2)','lsr x0,x1,x2'),('a_asr(0,1,2)','asr x0,x1,x2'),
       ('a_cmp(28,14)','cmp x28,x14'),('a_tst(0,0)','tst x0,x0'),('a_cmp_value(0,255)','cmp x0,#255'),('a_cmp_value(0,-1)','cmn x0,#1'),('a_cmp_value(13,4194304)','movz x16,#0\nmovk x16,#0x40,lsl #16\ncmp x13,x16'),('a_cmp_value(13,0)','cmp x13,#0'),('a_cmp_value(13,-5000)','movn x16,#4999\ncmp x13,x16'),
       ('a_cset(0,0)','cset x0,eq'),('a_cset(1,11)','cset x1,lt'),('a_csel(0,1,2,3)','csel x0,x1,x2,lo'),
       ('a_ldr(0,29,8)','ldr x0,[x29,#8]'),('a_ldr(0,29,-136)','ldur x0,[x29,#-136]'),('a_ldr(0,29,-4096)','mov x17,#-4096\nldr x0,[x29,x17]'),('a_ldr(0,29,12)','ldur x0,[x29,#12]'),
       ('a_str(1,29,-8)','stur x1,[x29,#-8]'),('a_str(1,29,32760)','str x1,[x29,#32760]'),('a_str(1,29,40000)','mov x17,#40000\nstr x1,[x29,x17]'),
       ('a_ldrb(0,1,5)','ldrb w0,[x1,#5]'),('a_strb(0,1,5)','strb w0,[x1,#5]'),('a_push(29)','str x29,[x28,#-8]!'),('a_pop(29)','ldr x29,[x28],#8'),
       ('a_b(8)','b .+8'),('a_b(-8)','b .-8'),('a_bl(-1048576)','bl .-1048576'),('a_bcond(9,12)','b.ls .+12'),('a_bcond(7,-16)','b.vc .-16'),('a_br(16)','br x16'),
       ('a_adr(30,12)','adr x30,.+12'),('a_adr(1,-20)','adr x1,.-20'),('a_svc()','svc #0'),('a_add_value(0,1,5000,0)','mov x16,#5000\nadd x0,x1,x16'),('a_add_value(0,1,-8,0)','sub x0,x1,#8'),
       ('a_call(100)','adr x30,.+12\nstr x30,[x28,#-8]!\nb .+92'),('a_ret()','ldr x30,[x28],#8\nbr x30'),
       ('a_alu(2332033024,0,1,2,4)','add w0,w1,w2'),('a_alu(3942645760,31,1,2,4)','cmp w1,w2'),('a_alu(3942645760,31,1,2,8)','cmp x1,x2'),('a_alu(3120562176,0,1,2,8)','adcs x0,x1,x2'),
       ('a_alu(4194304000,0,1,2,8)','sbcs x0,x1,x2'),('a_alu(2317352960,0,1,2,8)','bic x0,x1,x2'),('a_alu(2854223872,0,31,2,4)','mvn w0,w2'),
       ('a_add_shift(16,3,1,3)','add x16,x3,x1,lsl #3'),('a_movw(0,1)','mov w0,w1'),('a_lsl_n(0,1,3,8)','lsl x0,x1,#3'),('a_lsl_n(0,1,3,4)','lsl w0,w1,#3'),
       ('a_lsr_n(0,1,5,8)','lsr x0,x1,#5'),('a_asr_n(0,1,63,8)','asr x0,x1,#63'),('a_lsr_n(0,1,5,4)','lsr w0,w1,#5'),('a_asr_n(0,1,31,4)','asr w0,w1,#31'),
       ('a_uxt(0,1,1)','uxtb w0,w1'),('a_uxt(0,1,2)','uxth w0,w1'),('a_uxt(0,1,4)','mov w0,w1'),('a_sxt(0,1,1)','sxtb x0,w1'),('a_sxt(0,1,2)','sxth x0,w1'),('a_sxt(0,1,4)','sxtw x0,w1'),
       ('a_bfxil(0,1,8)','bfxil x0,x1,#0,#8'),('a_bfxil(0,1,16)','bfxil x0,x1,#0,#16'),('a_bfi(0,1,8,8)','bfi x0,x1,#8,#8'),
       ('a_shiftv(0,0,1,2,8)','lsl x0,x1,x2'),('a_shiftv(1,0,1,2,4)','lsr w0,w1,w2'),('a_shiftv(2,0,1,2,8)','asr x0,x1,x2'),('a_shiftv(3,0,1,2,8)','ror x0,x1,x2'),
       ('a_ror_n(0,1,8,8)','ror x0,x1,#8'),('a_ror_n(0,1,8,4)','ror w0,w1,#8'),('a_clz(0,1,8)','clz x0,x1'),('a_clz(0,1,4)','clz w0,w1'),('a_rbit(0,1,8)','rbit x0,x1'),
       ('a_umulh(0,1,2)','umulh x0,x1,x2'),('a_smull(0,1,2)','smull x0,w1,w2'),('a_mul_s(0,1,2,8)','mul x0,x1,x2'),('a_mul_s(0,1,2,4)','mul w0,w1,w2'),
       ('a_udiv(0,1,2,8)','udiv x0,x1,x2'),('a_sdiv_s(0,1,2,4)','sdiv w0,w1,w2'),('a_msub(2,19,20,0,8)','msub x2,x19,x20,x0'),
       ('a_csel_s(0,1,2,11,8)','csel x0,x1,x2,lt'),('a_csel_s(0,1,2,0,4)','csel w0,w1,w2,eq'),('a_csetm(0,3)','csetm x0,lo'),
       ('a_cbz(1,8,8)','cbz x1,.+8'),('a_cbnz(1,-8,4)','cbnz w1,.-8'),
       ('a_ldur(0,1,-8,8,0)','ldur x0,[x1,#-8]'),('a_ldur(0,1,4,4,0)','ldur w0,[x1,#4]'),('a_ldur(0,1,4,4,1)','ldursw x0,[x1,#4]'),('a_ldur(0,1,2,2,0)','ldurh w0,[x1,#2]'),
       ('a_ldur(0,1,2,2,1)','ldursh x0,[x1,#2]'),('a_ldur(0,1,1,1,0)','ldurb w0,[x1,#1]'),('a_ldur(0,1,1,1,1)','ldursb x0,[x1,#1]'),
       ('a_stur(0,1,-8,8)','stur x0,[x1,#-8]'),('a_stur(0,1,4,4)','stur w0,[x1,#4]'),('a_stur(0,1,2,2)','sturh w0,[x1,#2]'),('a_stur(0,1,1,1)','sturb w0,[x1,#1]'),
       ('a_ldr_post(19,4,1,1)','ldrb w19,[x4],#1'),('a_ldr_post(19,4,-8,8)','ldr x19,[x4],#-8'),('a_str_post(0,5,8,8)','str x0,[x5],#8'),('a_str_post(0,5,4,4)','str w0,[x5],#4'),
       ('a_str_post(19,5,-1,1)','strb w19,[x5],#-1'),('a_udf()','udf #0'),
       ('a_fmov_dx(0,1)','fmov d0,x1'),('a_fmov_xd(1,0)','fmov x1,d0'),('a_fmov_dd(0,1)','fmov d0,d1'),('a_fcmp(0,1)','fcmp d0,d1'),
       ('a_farith(0,0,1,2)','fmul d0,d1,d2'),('a_farith(1,0,1,2)','fdiv d0,d1,d2'),('a_farith(2,0,1,2)','fadd d0,d1,d2'),('a_farith(3,0,1,2)','fsub d0,d1,d2'),
       ('a_fsqrt(0,1)','fsqrt d0,d1'),('a_scvtf(0,1,8)','scvtf d0,x1'),('a_fcvtzs(1,0,8)','fcvtzs x1,d0'),('a_ldr_d(0,16,-8)','ldur d0,[x16,#-8]'),('a_str_d(0,16,8)','stur d0,[x16,#8]')]


# Programs the ARM64 port runs so far: each must end under QEMU as the
# x86-64 build of it ends.
RUNS=['defmodule M do\n  def main() do\n    System.halt(42)\n  end\nend\n',
      'defmodule M do\n  def main() do\n    IO.puts("hello")\n  end\nend\n',
      'defmodule M do\n  def main() do\n    System.halt(0)\n  end\nend\n',
      'defmodule M do\n  def main() do\n    System.halt(255)\n  end\nend\n',
      # The zero a receive leaves for a regex is read at address 0: the
      # handler of SIGSEGV (zf_guard, native ARM64 code) makes that Go's panic.
      'defmodule M do\n  struct Holder do\n    re: regex\n    n: integer\n  end\n  def main() do\n    me: pid[Holder] = Process.self(8)\n'
      '    {got, h} = Process.receive(me, 10)\n    IO.inspect(h.n)\n    IO.inspect(Regex.match?(h.re, "x"))\n    IO.puts("after")\n  end\nend\n']


def encoders(root,compiler):
    """A compiler entry that returns the encoders' bytes for CASES, made from
    native-arm64.alc and the byte helpers it uses."""
    body=(ROOT/'implementations/alchem/native-arm64.alc').read_text().split('\n',1)[1].split('  # Native smoke test;')[0]
    compiler_text=(ROOT/'implementations/alchem/native-compiler.alc').read_text()
    helpers=''.join(re.search(r'  def '+name+r'\(.*?\n  end\n',compiler_text,re.S).group(0) for name in ['nc_hi','nc_upper','nc_quot256','nc_quot_high','nc_quot_low','nc_u16','nc_u32','nc_join','nc_zeros','nc_half'])
    # The entry calls the translation; the encoders alone are tested here.
    helpers+='  def xa_function(code: bytes): bytes do code end\n'
    def joined(calls):
        if len(calls)==1:return calls[0]
        middle=len(calls)//2
        return f'Enum.concat({joined(calls[:middle])},{joined(calls[middle:])})'
    expression=joined([call for call,_ in CASES])
    source=f'defmodule ArmEncoders do\n{helpers}{body}  def native_compile(source: bytes): bytes do {expression} end\n  def main() do System.halt(0) end\nend\n'
    built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=300)
    assert (built.returncode,built.stderr)==(0,b''),('encoder program',built.returncode,built.stderr)
    program=root/'encoders';program.write_bytes(built.stdout);program.chmod(0o700)
    got=subprocess.run([str(program)],input=b'',capture_output=True,timeout=60)
    assert got.returncode==0,('encoder run',got)
    (root/'want.s').write_text('\n'.join(text for _,text in CASES)+'\n')
    subprocess.run([str(TOOLS/'aarch64-linux-gnu-as'),str(root/'want.s'),'-o',str(root/'want.o')],check=True)
    subprocess.run([str(TOOLS/'aarch64-linux-gnu-objcopy'),'-O','binary','-j','.text',str(root/'want.o'),str(root/'want.bin')],check=True)
    want=(root/'want.bin').read_bytes()
    for index in range(0,max(len(want),len(got.stdout)),4):
        assert got.stdout[index:index+4]==want[index:index+4],('encoder word',index//4,got.stdout[index:index+4].hex(),want[index:index+4].hex())
    return len(want)//4


# A compiler entry (native_compile: its input and output, the collector on):
# the bytes it is given, reversed and followed by 7, for these inputs.
ENTRY=('defmodule E do\n  def back(s: bytes, at: integer, acc: bytes): bytes do\n'
       '    if at < 0 do acc else back(s, at-1, Enum.concat(acc, b[Enum.at(s, at, 0)])) end\n  end\n'
       '  def native_compile(source: bytes): bytes do Enum.concat(back(source, Enum.count(source)-1, b[]), b[7]) end\n'
       '  def main() do System.halt(0) end\nend\n')
INPUTS=[b'',b'abc',bytes(range(256))*300]


def compiler_entry(root,compiler,arm):
    """ENTRY built for ARM64 answers as its x86-64 build does."""
    built=[]
    for name,which in (('x86',compiler),('arm',arm)):
        made=subprocess.run([str(which)],input=ENTRY.encode(),capture_output=True,env={'PATH':''},timeout=120)
        assert made.returncode==0,('compiler entry build',name,made.returncode,made.stderr)
        path=root/f'entry-{name}';path.write_bytes(made.stdout);path.chmod(0o700);built.append(path)
    for given in INPUTS:
        want=subprocess.run([str(built[0])],input=given,capture_output=True,timeout=120)
        got=subprocess.run([str(TOOLS/'qemu-aarch64-static'),str(built[1])],input=given,capture_output=True,timeout=120)
        assert (got.returncode,got.stdout,got.stderr)==(want.returncode,want.stdout,want.stderr)==(0,given[::-1]+b'\x07',b''),('compiler entry',len(given),got.returncode,got.stderr[:200])
    return len(INPUTS)


def self_hosted(root,compiler,arm):
    """The compiler built for ARM64 compiles its own source under QEMU to
    what the x86-64 compiler is."""
    spec=spec_from_file_location('alchem_bootstrap',ROOT/'scripts/bootstrap-alchem-compiler.py');bootstrap=module_from_spec(spec);spec.loader.exec_module(bootstrap)
    source=bootstrap.source_text('functions').encode()
    made=subprocess.run([str(arm)],input=source,capture_output=True,env={'PATH':''},timeout=600)
    assert made.returncode==0 and made.stdout[18:20]==b'\xb7\x00',('the compiler built for ARM64',made.returncode,made.stderr[:200])
    hosted=root/'compiler-arm64-hosted';hosted.write_bytes(made.stdout);hosted.chmod(0o700)
    again=subprocess.run([str(TOOLS/'qemu-aarch64-static'),str(hosted)],input=source,capture_output=True,timeout=1200)
    reference=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=600)
    assert (again.returncode,again.stderr)==(0,b'') and again.stdout==reference.stdout,('the compiler under QEMU',again.returncode,again.stderr[:200],len(again.stdout),len(reference.stdout))
    return len(source)


def verify(compiler):
    assert (TOOLS/'aarch64-linux-gnu-as').exists(),'run scripts/fetch-arm64-tools.sh first'
    spec=spec_from_file_location('build_arm64',ROOT/'scripts/build-arm64.py');build=module_from_spec(spec);spec.loader.exec_module(build)
    with tempfile.TemporaryDirectory(prefix='alchem-arm64-') as d:
        root=Path(d)
        words=encoders(root,compiler)
        arm=root/'alchem-compiler-arm64';build.build(compiler,arm)
        ran=0
        for source in RUNS:
            native=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            reference=root/'reference';reference.write_bytes(native.stdout);reference.chmod(0o700)
            done=subprocess.run([str(reference)],capture_output=True,env={'PATH':''},timeout=120)
            expected=(done.returncode,done.stdout,done.stderr)
            made=subprocess.run([str(arm)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert made.returncode==0 and made.stdout[:4]==b'\x7fELF' and made.stdout[18:20]==b'\xb7\x00',('ARM64 compiler output',source,made.returncode,made.stdout[:20])
            program=root/'program';program.write_bytes(made.stdout);program.chmod(0o700)
            run=subprocess.run([str(TOOLS/'qemu-aarch64-static'),str(program)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==expected,('ARM64 run',source,run.returncode,run.stdout,run.stderr[:300])
            ran+=1
        entries=compiler_entry(root,compiler,arm)
        size=self_hosted(root,compiler,arm)
    print(f'PASS arm64: {words} encoded instructions as GNU as encodes them; {ran} programs compiled for ARM64 run under QEMU;'
          f' a compiler entry answers {entries} inputs as its x86-64 build; the compiler built for ARM64 compiles its {size:,} bytes of source under QEMU to the x86-64 compiler, byte for byte')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
