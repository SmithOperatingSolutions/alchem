#!/usr/bin/env python3
"""HTML templates: ~h, ~H and Markup: every program runs as the pinned compiler runs it."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_bundle',ROOT/'scripts/bundle-alchem.py')
bundler=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundler)

# (files, status, standard output, standard error) as the pinned compiler runs
# main.alc; @ stands for the directory the files are in.
RUNS=[({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    name = "<ada> & \'x\' \\"q\\""\n'
               '    IO.puts(Markup.to_string(~h"<p>#{name}</p>"))\n'
               '    IO.puts(inspect(~h"<p>#{name}</p>"))\n'
               '    IO.puts(inspect(Markup.parts(~h"<p>#{name}</p>")))\n'
               '    IO.puts(inspect(Markup.parts(~h"")))\n'
               '    IO.puts(inspect(Markup.parts(~h"#{name}#{1}")))\n'
               '    IO.puts(inspect(Markup.parts(~H"<p>#{name}</p>")))\n'
               '    IO.puts(inspect(Markup.parts(~h(a "q" \\) b\\\\ #{1.5} #{:atm} #{[~h"<i>", '
               'Markup.raw("&")]} #{~h"x#{2}"}))))\n'
               '    IO.puts(inspect(Markup.parts(~h[x\\]y])))\n'
               '    IO.puts(inspect(Markup.parts(~h<a\\>b>)))\n'
               '    IO.puts(inspect(Markup.parts(~h/a\\/b\\n\\t/)))\n'
               '    IO.puts(inspect(Markup.parts(~h|a\\|b|)))\n'
               '    IO.puts(inspect(Markup.parts(~h{a\\}b #{3}})))\n'
               "    IO.puts(inspect(Markup.parts(~h'a\\'b')))\n"
               '  end\n'
               'end\n'},
  0,
  b'<p>&lt;ada&gt; &amp; &#39;x&#39; &#34;q&#34;</p>\n%Markup{html: "<p>&lt;ada&gt; &amp; &#39;x&#39; &#34;q&'
  b'#34;</p>"}\n%Markup.Parts{template: "386b76e6f2a676b0", fixed: ["<p>", "</p>"], values: [Markup.Value.tex'
  b't("&lt;ada&gt; &amp; &#39;x&#39; &#34;q&#34;")]}\n%Markup.Parts{template: "af63bd4c8601b7df", fixed: [""]'
  b', values: []}\n%Markup.Parts{template: "d94d12186c0f2fb7", fixed: ["", "", ""], values: [Markup.Value.tex'
  b't("&lt;ada&gt; &amp; &#39;x&#39; &#34;q&#34;"), Markup.Value.text("1")]}\n%Markup.Parts{template: "b62fc4'
  b'b2b4c87f48", fixed: ["<p>#{name}</p>"], values: []}\n%Markup.Parts{template: "6eacf61851c8a7f0", fixed: ['
  b'"a \\"q\\" ) b\\\\\\\\ ", " ", " ", " ", ""], values: [Markup.Value.text("1.5"), Markup.Value.text("at'
  b'm"), Markup.Value.list([%Markup{html: "<i>"}, %Markup{html: "&"}]), Markup.Value.markup(%Markup{html: "x'
  b'2"})]}\n%Markup.Parts{template: "19c64f540fcbb22f", fixed: ["x]y"], values: []}\n%Markup.Parts{templat'
  b'e: "f45b8182c7a4c134", fixed: ["a>b"], values: []}\n%Markup.Parts{template: "2ca91427be96e849", fixed: ["'
  b'a/b\\\\n\\\\t"], values: []}\n%Markup.Parts{template: "0e4e6383f898c582", fixed: ["a|b"], values: []}'
  b'\n%Markup.Parts{template: "625549f8aef47dd1", fixed: ["a}b ", ""], values: [Markup.Value.text("3")]}\n'
  b'%Markup.Parts{template: "ba533c82a782b5eb", fixed: ["a\'b"], values: []}\n',
  b''),
 ({'main.alc': 'defmodule T do\n  def main() do\n    IO.puts(inspect(~h"a#{"s"}b#{[]}"))\n  end\nend\n'},
  0,
  b'%Markup{html: "asb"}\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    IO.puts(inspect(Markup.parts(~h"a#{[Markup.raw("x")]}b#{Markup.join([])}")))\n'
               '    IO.puts(inspect(~h"x" == Markup.raw("x")))\n'
               '    IO.puts(inspect(Markup.parts(Markup.of(~h"t#{1}"))))\n'
               '    IO.puts(inspect(Markup.parts(Markup.of([~h"t"]))))\n'
               '    IO.puts(inspect(Markup.parts(Markup.of(3))))\n'
               '  end\n'
               'end\n'},
  0,
  b'%Markup.Parts{template: "3faea7fc849a4882", fixed: ["a", "b", ""], values: [Markup.Value.list([%Markup{h'
  b'tml: "x"}]), Markup.Value.list([])]}\ntrue\n%Markup.Parts{template: "566e361943eef51b", fixed: ["t", "'
  b'"], values: [Markup.Value.text("1")]}\n%Markup.Parts{template: "", fixed: ["", ""], values: [Markup.Value'
  b'.list([%Markup{html: "t"}])]}\n%Markup.Parts{template: "", fixed: ["", ""], values: [Markup.Value.text("3'
  b'")]}\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    IO.puts(inspect(Enum.map(["a"], fn x -> ~h"<b>#{x}</b>" end)))\n'
               '    m = %Markup{html: "<raw>"}\n'
               '    IO.puts(inspect(Markup.parts(m)))\n'
               '    case m do\n'
               '      %Markup{html: h} -> IO.puts(h)\n'
               '    end\n'
               '  end\n'
               'end\n'},
  0,
  b'[%Markup{html: "<b>a</b>"}]\n%Markup.Parts{template: "", fixed: ["", ""], values: [Markup.Value.text("<ra'
  b'w>")]}\n<raw>\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    IO.puts(inspect(Markup.parts(~h"é#{1}\\"ü")))\n'
               '    IO.puts(inspect(Markup.parts(~h"a   #{ 1 + 2 }  ")))\n'
               '  end\n'
               'end\n'},
  0,
  b'%Markup.Parts{template: "12f50df340b686bc", fixed: ["\xc3\xa9", "\\"\xc3\xbc"], values: [Markup.Value.tex'
  b't("1")]}\n%Markup.Parts{template: "fac984a22c7dcf64", fixed: ["a   ", "  "], values: [Markup.Value.text("'
  b'3")]}\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    IO.puts(inspect(~s"a\\#{1+1}"))\n'
               '    IO.puts(inspect(Markup.parts(~h"a\\#{1+1}")))\n'
               '  end\n'
               'end\n'},
  0,
  b'"a\\\\2"\n%Markup.Parts{template: "f984f7835bef8ef0", fixed: ["a\\\\", ""], values: [Markup.Value.text("2'
  b'")]}\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def item(name: string): Markup do\n'
               '    ~h"<li>#{name}</li>"\n'
               '  end\n'
               '  def main() do\n'
               '    names = ["ada", "<script>"]\n'
               '    p = ~h"""\n'
               '      <h1>#{length(names)} names</h1>\n'
               '        <ul>#{Enum.map(names, &item/1)}</ul>\n'
               '      "quoted" \\\\ #{1}\n'
               '      """\n'
               '    IO.puts(Markup.to_string(p))\n'
               '    IO.puts(inspect(Markup.parts(p)))\n'
               '    q = ~H"""\n'
               '        <b>#{x}</b>\n'
               '      tail\\n\n'
               '        """\n'
               '    IO.puts(inspect(Markup.parts(q)))\n'
               '  end\n'
               'end\n'},
  0,
  b'<h1>2 names</h1>\n  <ul><li>ada</li><li>&lt;script&gt;</li></ul>\n"quoted" \\\\ 1\n\n%Markup.Parts{tem'
  b'plate: "1c9a395c1496f74b", fixed: ["<h1>", " names</h1>\\n  <ul>", "</ul>\\n\\"quoted\\" \\\\\\\\ ", "\\n'
  b'"], values: [Markup.Value.text("2"), Markup.Value.list([%Markup{html: "<li>ada</li>"}, %Markup{html: "<l'
  b'i>&lt;script&gt;</li>"}]), Markup.Value.text("1")]}\n%Markup.Parts{template: "70ce162ebb55b51d", fixed: ['
  b'"<b>#{x}</b>\\n      tail\\\\n\\n"], values: []}\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    x = 0\n'
               '    IO.puts(inspect(~h"a#{10 / x}b"))\n'
               '  end\n'
               'end\n'},
  2,
  b'',
  b'@/main.alc:4:28: division by zero\n  at T.main (@/main.alc:4)\n'),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    x = 0\n'
               '    m = ~h"""\n'
               '      a\n'
               '      #{1}\n'
               '      b #{hd(tl([x]))}\n'
               '      """\n'
               '    IO.puts(inspect(m))\n'
               '  end\n'
               'end\n'},
  2,
  b'',
  b'@/main.alc:4:23: the list is empty\n  at T.main (@/main.alc:4)\n'),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    a = ~h"b#{1}"\n'
               '    b = Markup.raw("b1")\n'
               '    IO.inspect(Enum.uniq([a, b]))\n'
               '  end\n'
               'end\n'},
  0,
  b'[%Markup{html: "b1"}]\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    a = ~h"b#{1}"\n'
               '    b = Markup.raw("b1")\n'
               '    IO.inspect(a in [b])\n'
               '    IO.inspect(Enum.member?([a], b))\n'
               '  end\n'
               'end\n'},
  0,
  b'true\ntrue\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    a = ~h"b#{1}"\n'
               '    b = Markup.raw("b1")\n'
               '    IO.inspect(Enum.dedup([a, b]))\n'
               '  end\n'
               'end\n'},
  0,
  b'[%Markup{html: "b1"}]\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    a = ~h"b#{1}"\n'
               '    b = Markup.raw("b1")\n'
               '    IO.inspect({a, 1} == {b, 1})\n'
               '    IO.inspect([a] == [b])\n'
               '    IO.inspect(some(a) != some(b))\n'
               '  end\n'
               'end\n'},
  0,
  b'true\ntrue\nfalse\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    a = ~h"b#{1}"\n'
               '    b = Markup.raw("b1")\n'
               '    IO.inspect(Enum.uniq_by([{1, a}, {2, b}], fn x -> elem(x, 1) end))\n'
               '    IO.inspect(List.delete([a, a], b))\n'
               '    IO.inspect(Enum.find_index([a], fn x -> x == b end))\n'
               '  end\n'
               'end\n'},
  0,
  b'[{1, %Markup{html: "b1"}}]\n[%Markup{html: "b1"}]\nsome(0)\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    a = ~h"b#{1}"\n'
               '    b = Markup.raw("b1")\n'
               '    case a do\n'
               '      %Markup{html: "b1"} -> IO.puts("m")\n'
               '      _ -> IO.puts("n")\n'
               '    end\n'
               '    IO.inspect(a == %Markup{html: "b1"})\n'
               '    IO.inspect(Enum.count([a, b], fn x -> x == a end))\n'
               '  end\n'
               'end\n'},
  0,
  b'm\ntrue\n2\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    IO.puts(inspect(Markup.raw("<br>")))\n'
               '    IO.puts(inspect(Markup.raw("<br>") == Markup.join([Markup.raw("<br>")])))\n'
               '    IO.puts(inspect(Markup.parts(Markup.raw("<br>"))))\n'
               '    IO.puts(inspect(Markup.parts(Markup.join([Markup.raw("<br>")]))))\n'
               '    IO.puts(inspect(Markup.parts(Markup.template("greeting", ["<p>", "</p>"], '
               '[Markup.of("hi")]))))\n'
               '  end\n'
               'end\n'},
  0,
  b'%Markup{html: "<br>"}\ntrue\n%Markup.Parts{template: "", fixed: ["", ""], values: [Markup.Value.text("'
  b'<br>")]}\n%Markup.Parts{template: "", fixed: ["", ""], values: [Markup.Value.list([%Markup{html: "<br>"}]'
  b')]}\n%Markup.Parts{template: "greeting", fixed: ["<p>", "</p>"], values: [Markup.Value.text("hi")]}\n',
  b'')]

# Programs the pinned compiler rejects.
REJECTS=[{'main.alc': 'defmodule T do\n  def main() do\n    IO.puts(inspect(~h"a#{some(1)}"))\n  end\nend\n'},
 {'main.alc': 'defmodule T do\n'
              '  def main() do\n'
              '    f = fn x -> ~h"<b>#{x}</b>" end\n'
              '    IO.puts(inspect(f("a")))\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n  def main() do\n    IO.puts(inspect(~h"a#{true}"))\n  end\nend\n'},
 {'main.alc': 'defmodule T do\n  def main() do\n    IO.puts(inspect(~h"a#{%{1 => 2}}"))\n  end\nend\n'},
 {'main.alc': 'defmodule T do\n  def main() do\n    IO.puts(inspect(~h"a"x))\n  end\nend\n'},
 {'main.alc': 'defmodule T do\n  def main() do\n    IO.puts(inspect(~H"a"i))\n  end\nend\n'},
 {'main.alc': 'defmodule T do\n'
              '  def main() do\n'
              '    a = ~h"b#{1}"\n'
              '    b = Markup.raw("b1")\n'
              '    IO.inspect(Enum.group_by([a, b], fn x -> x end))\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def main() do\n'
              '    a = ~h"b#{1}"\n'
              '    b = Markup.raw("b1")\n'
              '    IO.inspect(Enum.frequencies([a, b]))\n'
              '  end\n'
              'end\n'}]


def bundled(files,directory):
    for name,text in files.items():(directory/name).write_text(text)
    return bundler.bundle(str(directory/'main.alc'))


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-templates-') as d:
        d=Path(d).resolve();out=d/'out'
        for index,(files,status,stdout,stderr) in enumerate(RUNS):
            directory=d/f'run{index}';directory.mkdir()
            # A program of one file is also compiled as it is, without a bundle.
            sources=[(bundled(files,directory),stderr.replace(b'@/',str(directory).encode()+b'/'))]
            if len(files)==1:sources.append((files['main.alc'].encode(),stderr.replace(b'@/main.alc',b'<stdin>')))
            for source,expected in sources:
                result=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
                assert (result.returncode,result.stderr)==(0,b''),(files['main.alc'],result.returncode,result.stderr)
                out.write_bytes(result.stdout);out.chmod(0o700)
                run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
                assert (run.returncode,run.stdout,run.stderr)==(status,stdout,expected),(files['main.alc'],run,expected)
        for index,files in enumerate(REJECTS):
            directory=d/f'reject{index}';directory.mkdir()
            sources=[bundled(files,directory)]+([files['main.alc'].encode()] if len(files)==1 else [])
            for source in sources:
                result=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
                assert (result.returncode,result.stdout)==(65,b''),(files['main.alc'],result.returncode)
    print(f'PASS templates: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; one-line and heredoc templates, every delimiter, the escaping of values by type, template names, Markup.parts, Markup in equality, ordering and keys, the places of failures in a value')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
