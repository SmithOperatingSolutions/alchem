#!/usr/bin/env python3
"""String and collection literals as the pinned compiler takes them: #{...}
in strings, heredocs, strings and list or map literals past the former 128,
and an exit status outside 0..255."""
from pathlib import Path
import subprocess
import sys
import tempfile

F='  def f(n: integer): integer do n * 2 end\n'
LONG='yz'*2500
# (main body, standard output, standard error, status)
ACCEPTED=[
    ('IO.puts("a#{1 + 2}b" <> "#{true}#{1 == 2}" <> "#{"in" <> "ner"}!")\nIO.puts("#{1}#{2} \\#{no} # not #1 {x}")\nIO.puts("#{f(2)} and #{String.length("ab")}; a#{"b#{1}c"}d; m#{Map.get(%{"k" => 7}, "k", 0)}!")\n'
     'IO.puts("#{if 1 == 1 do "y" else "n" end}é#{1}ü")',b'a3btruefalseinner!\n12 #{no} # not #1 {x}\n4 and 2; ab1cd; m7!\ny\xc3\xa91\xc3\xbc\n',b'',0),
    ('IO.puts("""\n    a\n      b "q" \\t.\n    """)\ntext = """\n  one\n    two\n    """\nIO.puts(text <> "|")\nIO.puts(Integer.to_string(String.length(text)))\nIO.puts("""\n    """ <> "x")\n'
     'IO.puts(String.upcase("""\n    abc\n    """) <> "z")',b'a\n  b "q" \t.\n\n  one\ntwo\n|\n10\nx\nABC\nz\n',b'',0),
    ('n = 3\ns = "x"\nIO.puts("""\n    #{n}#{s} and #{n + 1}!\n      second #{true}\n\n    last\n    """ <> "|")',b'3x and 4!\n  second true\n\nlast\n|\n',b'',0),
    ('IO.puts("'+'x'*300+'")\ns = "'+LONG+'"\nIO.puts(Integer.to_string(String.length(s)))',b'x'*300+b'\n5000\n',b'',0),
    ('l = ['+','.join(map(str,range(3000)))+']\nIO.puts(Integer.to_string(Enum.sum(l) + Enum.at(l, 2999, 0)))\nm = %{'+', '.join(f'"k{i}" => {i}' for i in range(300))+'}\n'
     'IO.puts(Integer.to_string(Map.get(m, "k299", 0) + Enum.count(Map.keys(m))))\nw = ['+','.join(f'"s{i}"' for i in range(300))+']\nIO.puts(Enum.join(Enum.take(w, 3), ",") <> Enum.at(w, 299, ""))',
     b'4501499\n599\ns0,s1,s2s299\n',b'',0),
    ('IO.puts("a")\nSystem.halt(300)',b'a\n',b'<stdin>:5:1: exit status must be between 0 and 255\n  at M.main (<stdin>:5)\n',2),
    ('System.halt(255)',b'',b'',255),
    # Expressions nest and chain past the former 16.
    ('IO.puts(Integer.to_string('+'('*100+'1'+')'*100+' + '+' + '.join(['1']*60)+'))\nIO.puts('+' <> '.join(f'"p{i}"' for i in range(40))+')\nx = '+' and '.join(['1 == 1']*30)+' or false\n'
     'IO.puts("#{x}")\nIO.puts(Integer.to_string('+'f('*25+'1'+')'*25+'))',b'61\n'+''.join(f'p{i}' for i in range(40)).encode()+b'\ntrue\n33554432\n',b'',0),
]
REJECTED=[('IO.puts("#{[1, 2]}")','a list in a string'),('IO.puts("#{some(1)}")','an option in a string'),('IO.puts("#{}")','an empty expression in a string'),('IO.puts("#{1")','an unclosed expression'),
          ('IO.puts(""" a\n    """)','a heredoc that does not end its opening line'),('IO.puts("""\n    #{[1]}\n    """)','a list in a heredoc'),('IO.puts("bad\\q")','an unknown escape')]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-literals-') as d:
        root=Path(d)
        def compiled(body):
            return subprocess.run([str(compiler)],input=('defmodule M do\n'+F+'  def main() do\n'+body+'\n  end\nend\n').encode(),capture_output=True,env={'PATH':''},timeout=120)
        for body,stdout,stderr,status in ACCEPTED:
            result=compiled(body)
            assert (result.returncode,result.stderr)==(0,b''),(body[:100],result.returncode,result.stderr)
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(body[:100],run.returncode,run.stdout[:200],run.stderr)
        for body,label in REJECTED:
            result=compiled(body)
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
    print(f'PASS literals: {len(ACCEPTED)} programs with #{{...}} in strings, heredocs, a 5000-byte string, 3000 list and 300 map elements, exit statuses, and expressions nested 100 deep; {len(REJECTED)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
