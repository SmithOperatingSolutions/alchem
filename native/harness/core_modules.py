#!/usr/bin/env python3
"""Verify full compiler components through the actual self-hosted compiler."""
import ast
from pathlib import Path
from source_syntax import native_bytes
import sys
import tempfile
from run import ROOT
from lexer import cases as lexer_cases
from integers import cases as integer_cases,decimal,integer,MIN
from expressions import cases as expression_cases
from self_hosted_components import literal,product,verify_programs
from source_syntax import native_bytes


def prefix(name):return (ROOT/'implementations/alchem'/name).read_text().split('  # Native smoke test;',1)[0]


def verify(compiler):
    count={'lexer':0,'integers':0,'expressions':0,'encoder':0}
    base=prefix('lexer.alc')
    programs=[]
    if True:
        for name,old_literal,assertions in lexer_cases():
            # The existing oracle remains authoritative; its literal can exceed
            # the compiler's pack bound in intentional 129-byte rejection cases.
            data=ast.literal_eval(old_literal)
            values=literal(data)
            local=[item for item in assertions if 'token_count(' not in item and 'first_error(' not in item]
            summaries=[item for item in assertions if 'token_count(' in item or 'first_error(' in item]
            chunks=[local[i:i+24] for i in range(0,len(local),24)]+[[item] for item in summaries]
            for part,checks in enumerate(chunks):
                source=base+'  def verify(values: list[integer]): integer do '+product(checks)+' end\n  def main() do if verify('+values+') == 1 do System.halt(0) else System.halt(1) end end\nend\n'
                programs.append((source,('lexer',name,part),0));count['lexer']+=1
        for number,(mode,data,start,stop,negative,fallback) in enumerate(integer_cases()):
            if mode=='decimal':
                error,value=decimal(data,start,stop,negative,fallback);args=f'{literal(data)},{start},{stop},{negative}'
            else:
                error,value=integer(data,start,negative,fallback);args=f'{literal(data)},{start},{negative}'
            checks=[f'match_kind({mode}_error({args}),{error})',f'match_kind({mode}_or({args},{fallback}),{value})']
            source=base+'  def main() do if '+product(checks)+' == 1 do System.halt(0) else System.halt(1) end end\nend\n'
            programs.append((source,('integer',number),0));count['integers']+=1
        for number,(data,error,value) in enumerate(expression_cases()):
            for expression,expected in [(f'expression_error({literal(data)})',error),(f'expression_or({literal(data)},{MIN})',value)]:
                source=base+'  def main() do if '+expression+' == '+str(expected)+' do System.halt(0) else System.halt(1) end end\nend\n'
                programs.append((source,('expression',number),0));count['expressions']+=1
        base=prefix('encoder.alc')
        for value in list(range(256))+[-1,256,-(1<<63),(1<<63)-1]:
            source=base+f'  def main() do image=emit_elf_exit({value})\n System.halt(Enum.count(image)-140) end\nend\n'
            # A value that is no byte fails where the byte is made (spec/alchem-failures.md, "Bytes").
            programs.append((source,('encoder',value),0 if 0<=value<=255 else (2,b'byte must be between 0 and 255')));count['encoder']+=1
    # The fixtures are in the old byte spelling.
    verify_programs([(native_bytes(source),label,status) for source,label,status in programs],compiler)
    print('PASS self-hosted core component oracles:',count)


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
