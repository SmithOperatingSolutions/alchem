#!/usr/bin/env python3
"""Exercise real main/0 programs through the installed Rust source command."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from run import ROOT, TARGET


def verify(frontend, rust, go):
    # Exercise sibling frontend discovery, spaces in paths, and an empty PATH:
    # source compilation must use prebuilt tools rather than a host toolchain.
    environment = dict(os.environ, PATH="")
    with tempfile.TemporaryDirectory(prefix="alchem-main-") as directory:
        root = Path(directory)
        tools = root / "native tools"
        tools.mkdir()
        driver = tools / "alchem-native"
        shutil.copy2(rust, driver)
        shutil.copy2(frontend, tools / "alchem-source-probe")
        invoice = (ROOT / "examples/invoice.alc").read_text()
        cases = [((ROOT / "examples/recursive-sum.alc").read_text(), 42), ((ROOT / "examples/invoice-conditional.alc").read_text(), 42), (invoice, 42), ((ROOT / "examples/invoice-functions.alc").read_text(), 42)]
        cases.extend([
            ("defmodule Calls do def add(a: integer, b: integer): integer do a + b end def twice(x: integer): integer do add(x, x) end def main() do result = add(twice(10), twice(11))\n System.halt(result) end end", 42),
            ("defmodule Calls do def mix(a: integer, b: integer, c: integer, d: integer, e: integer, f: integer): integer do a - b*c + d*e - f end def main() do System.halt(mix(90, 2, 3, 4, 5, 62)) end end", 42),
            ("defmodule Calls do defp negate(x: integer): integer do -x end def main() do System.halt(negate(-42)) end end", 42),
        ])
        for body, expected in [
            ("x = 42\ny = x\nSystem.halt(y)", 42),
            ("x = 42", 0),
            ("x = 1 - 7\nSystem.halt(x * -7)", 42),
            ("System.halt(0)", 0),
            ("System.halt(255)", 255),
        ]:
            cases.append((f"defmodule Program do def main() do\n{body}\nend end", expected))
        for condition, expected in [("1 < 2",42),("2 < 1",7),("-9223372036854775808 < 9223372036854775807",42),("7 == 7",42),("7 != 7",7),("7 <= 7",42),("7 > 8",7),("8 >= 8",42)]:
            cases.append((f"defmodule Branch do def main() do amount = if {condition} do 42 else 7 end\n System.halt(amount) end end", expected))
        cases.extend([
            ("defmodule Branch do def choose(a: integer, b: integer): integer do if a < b do 42 else 7 end end def main() do System.halt(choose(2,1)) end end",7),
            ("defmodule Branch do def main() do flag = if 1 < 2 do true else false end\n if not flag do System.halt(7) else System.halt(42) end end end",42),
            ("defmodule Branch do def main() do value = if true do local = 40\n local + 2 else local = 7\n local end\n System.halt(value) end end",42),
            ("defmodule Branch do def choose(x: integer): integer do if x < 0 do 7 else if x == 0 do 42 else 9 end end end def main() do System.halt(choose(0)) end end",42),
        ])
        cases.append(("defmodule Mutual do def even(n: integer): integer do if n == 0 do 1 else odd(n-1) end end def odd(n: integer): integer do if n == 0 do 0 else even(n-1) end end def main() do System.halt(even(12)+41) end end",42))
        cases.append(((ROOT / "examples/byte-cursor.alc").read_text(),42))
        for expression,expected in [
            ("Enum.at([0, 42, 255], -2, 7)",42),
            ("Enum.at([0, 42, 255], -1, 7)",255),
            ("Enum.at([0, 42, 255], -4, 7)",7),
            ("Enum.at([0, 42, 255], 3, 7)",7),
            ("Enum.at([42], -9223372036854775808, 7)",7),
            ("Enum.at([42], 9223372036854775807, 7)",7),
            ("Enum.count([0, 42, 255])",3),
            ("Enum.at(if true do [0,42] else [7] end, -1, 9)",42),
            ("Enum.at(if false do [0,42] else [7] end, -1, 9)",7),
        ]:
            cases.append((f"defmodule Bytes do def main() do System.halt({expression}) end end",expected))
        cases.append(("defmodule Bytes do def read(values: list[integer]): integer do Enum.at(values, 0, 42) end def main() do System.halt(read([])) end end",42))
        classifier = (ROOT / "implementations/alchem/lexer.alc").read_text()
        cases.append((classifier, 0))
        prefix = classifier.split("  # Native smoke test;", 1)[0]
        punctuation = {43:4, 45:5, 42:6, 40:7, 41:8}
        checks = []
        for code in [-2, -1] + list(range(128)) + [128, 255, 9223372036854775807]:
            expected = (9 if code == -1 else 1 if code in (9,10,13,32) else 2 if 65 <= code <= 90 or 97 <= code <= 122 or code == 95 else 3 if 48 <= code <= 57 else punctuation.get(code, 0))
            checks.append(f"match_kind(classify_ascii({code}), {expected})")
        exhaustive = prefix + "  def main() do\n    checks = " + " * ".join(checks) + "\n    if checks == 1 do System.halt(0) else System.halt(1) end\n  end\nend\n"
        cases.append((exhaustive, 0))
        ascii_values = ", ".join(map(str,range(128)))
        cursor_cases = [
            (f"count_buffer_digits([{ascii_values}], 0)",10),
            ("skip_spaces([32,9,10,13,65], 0)",4),
            ("skip_spaces([32,9,10,13], 0)",4),
            ("scan_digits([48,57,49,255], 0)",3),
            ("scan_digits([48,57,49], 0)",3),
            ("byte_at([0,255], 0)",0),
            ("byte_at([0,255], 1)",255),
            ("match_kind(byte_at([0,255], 2), -1)",1),
            ("match_kind(byte_at([0,255], -1), -1)",1),
        ]
        for expression,expected in cursor_cases:
            cases.append((prefix+f"  def main() do System.halt({expression}) end\nend\n",expected))
        cases.append(("defmodule Wide do def wide(): integer do -9223372036854775808 end def main() do if wide() == -9223372036854775808 do System.halt(42) else System.halt(7) end end end",42))
        cases.append(("defmodule Status do def main() do System.halt(70) end end",70))
        cases.append(("defmodule Status do def main() do if false do System.halt(256) else System.halt(42) end end end",42))
        nested='('*16+'6*7'+')'*16
        literal=','.join(map(str,nested.encode()))
        cases.append((prefix+f"  def main() do System.halt(expression_or([{literal}], 7)) end\nend\n",42))
        helpers=' '.join(f'def f{i}(x: integer): integer do f{i+1}(x) + f{i+1}(x) end' for i in range(19))
        cases.append((f"defmodule Budget do {helpers} def f19(x: integer): integer do x end def main() do System.halt(f0(0)) end end",0))
        cases.extend([
            ('defmodule Join do def join(a: list[integer], b: list[integer]): list[integer] do Enum.concat(a,b) end def main() do values=join([20],[22])\n System.halt(Enum.at(values,0,0)+Enum.at(values,1,0)) end end',42),
            ('defmodule Join do def join(a: list[integer], b: list[integer]): list[integer] do Enum.concat(a,b) end def main() do System.halt(Enum.count(join([],[]))) end end',0),
            ('defmodule Join do def data(): list[integer] do [42] end def main() do System.halt(Enum.at(data(),0,7)) end end',42),
            ('defmodule Join do def choose(n: integer): list[integer] do if n == 0 do [42] else [7] end end def main() do System.halt(Enum.at(choose(0),0,0)) end end',42),
            ('defmodule Join do def build(n: integer): list[integer] do if n <= 0 do [40] else Enum.concat(build(n-1),[1]) end end def main() do result=build(2)\n System.halt(Enum.at(result,0,0)+Enum.count(result)-1) end end',42),
            ('defmodule Join do def main() do original=[20,22]\n joined=Enum.concat(original,[9])\n System.halt(Enum.at(original,0,0)+Enum.at(original,1,0)) end end',42),
            ('defmodule Join do def join(a: list[integer], b: list[integer]): list[integer] do IO.puts("built")\n Enum.concat(a,b) end def main() do values=join([20],[22])\n System.halt(Enum.at(values,0,0)+Enum.at(values,1,0)) end end',42),
        ])
        cases.extend([
            ('defmodule Pack do def main() do x=42\n System.halt(Enum.at([x],0,0)) end end',42),
            ('defmodule Pack do def main() do System.halt(Enum.at([40+2],0,0)) end end',42),
            ('defmodule Pack do def data(x: integer): list[integer] do [x,22] end def main() do values=data(20)\n System.halt(Enum.at(values,0,0)+Enum.at(values,1,0)) end end',42),
            ('defmodule Pack do def main() do values=if false do [-1] else [42] end\n System.halt(Enum.at(values,0,0)) end end',42),
            ((ROOT/'implementations/alchem/encoder.alc').read_text(),0),
        ])
        output_cases=[
            ('defmodule Hello do def main() do IO.puts("hello") end end',0,b'hello\n'),
            ('defmodule Hello do def main() do IO.puts("") end end',0,b'\n'),
            ('defmodule Hello do def main() do IO.puts("héλ🙂") end end',0,'héλ🙂\n'.encode()),
            ('defmodule Hello do def main() do IO.puts("line\\n") end end',0,b'line\n\n'),
            ('defmodule Hello do def main() do IO.puts("first")\n IO.puts("last")\n System.halt(42) end end',42,b'first\nlast\n'),
            ('defmodule Hello do def emit(x: integer): integer do IO.puts("helper")\n x+1 end def main() do System.halt(emit(41)) end end',42,b'helper\n'),
            ('defmodule Hello do def main() do if true do IO.puts("yes") else IO.puts("no") end end end',0,b'yes\n'),
            ('defmodule Hello do def main() do if false do IO.puts("yes") else IO.puts("no") end end end',0,b'no\n'),
        ]
        built_index=next(i for i,(source,_) in enumerate(cases) if 'IO.puts("built")' in source)
        built_case=cases.pop(built_index)
        output_cases.append((built_case[0],built_case[1],b'built\n'))
        output_cases += [
            ('defmodule Pack do def emit(x: integer): integer do IO.puts("eval")\n x end def main() do values=[emit(20),emit(22)]\n System.halt(Enum.at(values,0,0)+Enum.at(values,1,0)) end end',42,b'eval\neval\n'),
        ]
        valid_count=len(cases)+len(output_cases)
        cases=[(source,expected,b"",b"") for source,expected in cases]+[(source,expected,stdout,b"") for source,expected,stdout in output_cases]
        status_error=b"E_HALT_STATUS: expected status 0..255\n"
        for value in [-1,256,-9223372036854775808,9223372036854775807]:
            cases.append((f"defmodule Status do def main() do System.halt({value}) end end",70,b"",status_error))
        cases.append(("defmodule Calls do def identity(x: integer): integer do x end def main() do System.halt(identity(256)) end end",70,b"",status_error))
        cases.append(("defmodule Calls do def loop(x: integer): integer do loop(x) end def main() do System.halt(loop(0)) end end",70,b"",b"E_RUNTIME_LIMIT: native call/stack budget exceeded\n"))
        for value in [-1,256,-9223372036854775808,9223372036854775807]:
            cases.append((f'defmodule Pack do def main() do x={value}\n values=[x]\n System.halt(Enum.count(values)) end end',72,b'',b'E_RUNTIME_BYTE: expected byte value 0..255\n'))
        for value in [-1,256]:
            cases.append((f'defmodule Pack do def main() do values=[{value}]\n System.halt(Enum.count(values)) end end',72,b'',b'E_RUNTIME_BYTE: expected byte value 0..255\n'))
        cases.append(('defmodule Pack do def emit_bad(): integer do IO.puts("first")\n 256 end def emit_good(): integer do IO.puts("second")\n 42 end def main() do values=[emit_bad(),emit_good()]\n System.halt(Enum.count(values)) end end',72,b'first\nsecond\n',b'E_RUNTIME_BYTE: expected byte value 0..255\n'))
        for index, (source, expected, expected_stdout, expected_stderr) in enumerate(cases):
            path = root / "source file.alc"
            path.write_text(source)
            output = root / "native output"
            command = [str(driver), "--source", str(path), "--output", str(output)]
            compiled = subprocess.run(command, env=environment, capture_output=True, timeout=120)
            assert compiled.returncode == 0, compiled.stderr
            assert output.stat().st_mode & 0o777 == 0o700
            first = output.read_bytes()
            repeat = root / "repeat output"
            repeated = subprocess.run(command[:-1] + [str(repeat)], env=environment, capture_output=True, timeout=120)
            assert repeated.returncode == 0 and first == repeat.read_bytes(), "source build is not deterministic"
            executed = subprocess.run([str(output)], capture_output=True, timeout=120)
            assert (executed.returncode, executed.stdout, executed.stderr) == (expected, expected_stdout, expected_stderr), (index, executed)
            ir_result = subprocess.run([str(frontend), "--input", str(path), "--program"], capture_output=True, timeout=120)
            assert ir_result.returncode == 0, ir_result.stderr
            ir = root / "reference.json"
            ir.write_bytes(ir_result.stdout)
            reference = root / "reference output"
            result = subprocess.run([str(go), "--target", TARGET, "--input", str(ir), "--output", str(reference)], capture_output=True, timeout=120)
            assert result.returncode == 0 and first == reference.read_bytes(), "source Rust/Go output differs"
        path.write_text(invoice)
        before = path.read_bytes()
        rejected = subprocess.run([str(driver), "--source", str(path), "--output", str(path)], env=environment, capture_output=True, timeout=120)
        assert rejected.returncode != 0 and b"E_INVALID_ARGUMENT" in rejected.stderr, "source overwrite must be rejected"
        assert path.read_bytes() == before, "compiler overwrote its source"
        for body in ["System.halt(0)\nx = 42", "IO.puts(\"value #{42}\")", "System.halt(missing)"]:
            path.write_text(f"defmodule Program do def main() do\n{body}\nend end")
            output.write_bytes(b"existing output")
            rejected = subprocess.run(command, env=environment, capture_output=True, timeout=120)
            assert rejected.returncode != 0 and b"E_SOURCE" in rejected.stderr, rejected
            assert output.read_bytes() == b"existing output", "failed source compilation replaced output"
        rejected_sources = [
            "defmodule Calls do def identity(x: integer): integer do x end def main() do System.halt(identity()) end end",
            "defmodule Bytes do def main() do System.halt(Enum.at([1 | [42]], 1, 0)) end end",
        ]
        for source in rejected_sources:
            path.write_text(source)
            output.write_bytes(b"existing output")
            rejected = subprocess.run(command, env=environment, capture_output=True, timeout=120)
            assert rejected.returncode != 0 and b"E_SOURCE" in rejected.stderr
            assert output.read_bytes() == b"existing output"
        print(f"PASS {valid_count} executable-main programs, {len(cases)-valid_count} runtime-error cases and {3+len(rejected_sources)} source rejections; native helper calls verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frontend", type=Path)
    parser.add_argument("rust", type=Path)
    parser.add_argument("go", type=Path)
    args = parser.parse_args()
    verify(args.frontend.resolve(), args.rust.resolve(), args.go.resolve())
