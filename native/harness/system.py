#!/usr/bin/env python3
"""Files, directories, the environment and external programs (File, System,
Path, IO): every program runs as the pinned compiler runs it, in an empty
directory of its own with a fixed environment and umask."""
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import tempfile

# (program, standard input, 1 when root may run it too, status, standard output,
# standard error) as the pinned compiler runs it with HOME=/home/gate and no
# TMPDIR or PWD in the environment
RUNS=[('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(File.exists?(".")))\n'
  'IO.puts(inspect(File.read_binary("x")))\n'
  'File.write!("b", "a\\x00\\xff")\n'
  'IO.puts(inspect(File.read_binary("b")))\n'
  'IO.puts(inspect(byte_size(File.read_binary!("b"))))\n'
  'IO.puts(inspect(File.read_binary(".")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'true\nerror("open x: no such file or directory")\nok("a\\x00\\xff")\n3\nerror("read .: is a directory")\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(File.read_binary!("x")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not read x: open x: no such file or directory\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(File.mkdir_p("d/e/f")))\n'
  'IO.puts(inspect(File.mkdir_p("d/e/f")))\n'
  'IO.puts(inspect(File.mkdir_p("d//e/g/")))\n'
  'File.write!("d/x", "1")\n'
  'IO.puts(inspect(File.mkdir_p("d/x")))\n'
  'IO.puts(inspect(File.mkdir_p("d/x/y")))\n'
  'IO.puts(inspect(File.mkdir_p("")))\n'
  'IO.puts(inspect(File.mkdir_p("q/.")))\n'
  'IO.puts(inspect(File.mkdir_p("/")))\n'
  'IO.puts(inspect(File.ls("d")))\n'
  'IO.puts(inspect(File.ls("d/e")))\n'
  'IO.puts(inspect(File.ls!(".")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'ok({})\nok({})\nok({})\nerror("mkdir d/x: not a directory")\nerror("mkdir d/x: not a directory")\nerror("mkdir : no such file or directory")\n'
  b'ok({})\nok({})\nok(["e", "x"])\nok(["f", "g"])\n["d", "q"]\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'ok(here) = File.stat(".")\n'
  'IO.puts(inspect({here.type, here.access}))\n'
  'File.write!("a", "12345")\n'
  'ok(sa) = File.stat("a")\n'
  'IO.puts(inspect({sa.size, sa.type, sa.access, sa.mode, sa.mtime > 1700000000}))\n'
  'IO.puts(inspect(File.ln("a","b")))\n'
  'IO.puts(inspect(File.ln("a","b")))\n'
  'IO.puts(inspect(File.ln("zz","c")))\n'
  'IO.puts(inspect(File.ln_s("a","s")))\n'
  'IO.puts(inspect(File.ln_s("a","s")))\n'
  'IO.puts(inspect(File.ln_s("nowhere","t")))\n'
  'ok(ls) = File.lstat("s")\n'
  'IO.puts(inspect({ls.size, ls.type, ls.access, ls.mode}))\n'
  'ok(ss) = File.stat("s")\n'
  'IO.puts(inspect({ss.size, ss.type, ss.access, ss.mode}))\n'
  'ok(lt) = File.lstat("t")\n'
  'IO.puts(inspect({lt.size, lt.type, lt.access, lt.mode}))\n'
  'IO.puts(inspect(File.stat("t")))\n'
  'IO.puts(inspect(File.chmod("a",0o600)))\n'
  'ok(s6) = File.stat("a")\n'
  'IO.puts(inspect(s6.mode))\n'
  'IO.puts(inspect(File.chmod("a",0o4755)))\n'
  'ok(s7) = File.stat("a")\n'
  'IO.puts(inspect(s7.mode))\n'
  'IO.puts(inspect(File.chmod("a",0o444)))\n'
  'ok(s4) = File.stat("a")\n'
  'IO.puts(inspect({s4.mode, s4.access}))\n'
  'IO.puts(inspect(File.chmod("zz",0o600)))\n'
  'IO.puts(inspect(File.chmod("a/b",0o600)))\n'
  'ok(dn) = File.stat("/dev/null")\n'
  'IO.puts(inspect({dn.size, dn.type, dn.access}))\n'
  'ok(st) = File.stat("s")\n'
  'IO.puts(inspect(%File.Stat{st | mtime: 7}))\n'
  'IO.puts(inspect(File.ls(".")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'{:directory, :read_write}\n{5, :regular, :read_write, 420, true}\nok({})\nerror("eexist")\nerror("enoent")\nok({})\nerror("eexist")\nok({})\n{1,'
  b' :symlink, :read_write, 511}\n{5, :regular, :read_write, 420}\n{7, :symlink, :none, 511}\nerror("enoent")\nok({})\n384\nok({})\n493\nok({})\n{292'
  b', :read}\nerror("enoent")\nerror("chmod a/b: not a directory")\n{0, :other, :read_write}\n%File.Stat{size: 5, type: :regular, access: :read, mti'
  b'me: 7, mode: 292}\nok(["a", "b", "s", "t"])\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(File.touch("t")))\n'
  'IO.puts(inspect(File.touch("t")))\n'
  'IO.puts(inspect(File.touch("n/t")))\n'
  'IO.puts(inspect(File.touch(".")))\n'
  'IO.puts(inspect(File.read("t")))\n'
  'IO.puts(inspect(File.cwd() == ok(File.cwd!())))\n'
  'IO.puts(inspect(String.ends_with?(File.cwd!(), Path.basename(File.cwd!()))))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'ok({})\nok({})\nerror("open n/t: no such file or directory")\nok({})\nok("")\ntrue\ntrue\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.write!("a", "data")\n'
  'IO.puts(inspect(File.cp("a","b")))\n'
  'IO.puts(inspect(File.read("b")))\n'
  'IO.puts(inspect(File.cp("zz","c")))\n'
  'IO.puts(inspect(File.cp("a","n/c")))\n'
  'IO.puts(inspect(File.cp(".","c")))\n'
  'IO.puts(inspect(File.exists?("c")))\n'
  'IO.puts(inspect(File.cp("a",".")))\n'
  'IO.puts(inspect(File.cp("a","a")))\n'
  'IO.puts(inspect(File.read("a")))\n'
  'IO.puts(inspect(File.cp("/dev/null","e")))\n'
  'IO.puts(inspect(File.read("e")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'ok({})\nok("data")\nerror("open zz: no such file or directory")\nerror("open n/c: no such file or directory")\nerror("write c: copy_file_range: '
  b'is a directory")\ntrue\nerror("open .: is a directory")\nok({})\nok("")\nok({})\nok("")\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(File.rm_rf("zz")))\n'
  'IO.puts(inspect(File.mkdir_p("d/e/f")))\n'
  'File.write!("d/e/x", "1")\n'
  'File.write!("d/y", "1")\n'
  'IO.puts(inspect(File.ln_s("e", "d/l")))\n'
  'IO.puts(inspect(File.rm_rf("d")))\n'
  'IO.puts(inspect(File.exists?("d")))\n'
  'File.write!("f", "1")\n'
  'IO.puts(inspect(File.rm_rf("f/x")))\n'
  'IO.puts(inspect(File.rm_rf("f")))\n'
  'IO.puts(inspect(File.rm_rf(".")))\n'
  'IO.puts(inspect(File.rm_rf("a/.")))\n'
  'IO.puts(inspect(File.rm_rf("")))\n'
  'IO.puts(inspect(File.mkdir_p("g/h")))\n'
  'IO.puts(inspect(File.rm_rf("g//h/")))\n'
  'IO.puts(inspect(File.ls("g")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'ok({})\nok({})\nok({})\nok({})\nfalse\nerror("unlinkat f/x: not a directory")\nok({})\nerror("RemoveAll .: invalid argument")\nerror("RemoveAll '
  b'a/.: invalid argument")\nok({})\nok({})\nok({})\nok([])\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(File.cp_r("a","b")))\n'
  'IO.puts(inspect(File.mkdir_p("d/e/f")))\n'
  'File.write!("d/e/x", "1")\n'
  'File.write!("d/y", "22")\n'
  'IO.puts(inspect(File.ln_s("e", "d/l")))\n'
  'IO.puts(inspect(File.cp_r("d","c")))\n'
  'IO.puts(inspect(File.cp_r("d","c")))\n'
  'IO.puts(inspect(File.read("c/e/x")))\n'
  'ok(cl) = File.lstat("c/l")\n'
  'IO.puts(inspect(cl.type))\n'
  'IO.puts(inspect(File.cp_r("d/y","c/z/")))\n'
  'IO.puts(inspect(File.cp_r("d/y","c/y/k")))\n'
  'IO.puts(inspect(File.cp_r("d/y","d/y")))\n'
  'IO.puts(inspect(File.read("d/y")))\n'
  'IO.puts(inspect(File.cp_r("d","d/e/x")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'error("enoent")\nok({})\nok({})\nok(["c", "c/e", "c/e/f", "c/e/x", "c/l", "c/y"])\nok(["c", "c/e", "c/e/f", "c/e/x", "c/l", "c/y"])\nok("1")\n'
  b':symlink\nok(["c/z"])\nerror("open c/y/k: not a directory")\nok(["d/y"])\nok("22")\nerror("mkdir d/e/x: not a directory")\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(File.write("w","x",[:append])))\n'
  'IO.puts(inspect(File.write("w","y",[:append])))\n'
  'IO.puts(inspect(File.write("w","z",[:exclusive])))\n'
  'IO.puts(inspect(File.read("w")))\n'
  'IO.puts(inspect(File.write("w","z",[:write, :utf8, :binary])))\n'
  'IO.puts(inspect(File.read("w")))\n'
  'IO.puts(inspect(File.write("n/w","z",[:append])))\n'
  'IO.puts(inspect(File.write(".","z",[])))\n'
  'IO.puts(inspect(File.write("v","z",[:exclusive, :append])))\n'
  'IO.puts(inspect(File.write("w","z",[:read])))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  2,
  b'ok({})\nok({})\nerror("eexist")\nok("xy")\nok({})\nok("z")\nerror("enoent")\nerror("open .: is a directory")\nok({})\n',
  b'<stdin>:12:17: File.write takes the modes :append, :exclusive, :write, :utf8 and :binary\n  at T.main (<stdin>:12)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(File.open("w",[:write])))\n'
  'IO.puts(inspect(File.open("w",[:write], fn f -> File.close(f) end)))\n'
  'IO.puts(inspect(File.open("n/w",[:write])))\n'
  'IO.puts(inspect(File.open("zz",[:read])))\n'
  'IO.puts(inspect(File.open("zz",[])))\n'
  'IO.puts(inspect(File.open("w",[:exclusive])))\n'
  'IO.puts(inspect(File.open(".",[:write])))\n'
  'ok(f) = File.open("w", [:append, :read])\n'
  'IO.puts(inspect(f))\n'
  'IO.puts(inspect(File.close(f)))\n'
  'IO.puts(inspect(File.close(f)))\n'
  'IO.puts(inspect(File.open("w",[:bogus])))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  2,
  b'ok(#fileHandle<>)\nok(true)\nerror("enoent")\nerror("enoent")\nerror("enoent")\nerror("eexist")\nerror("open .: is a directory")\n#fileHandle<>'
  b'\ntrue\nfalse\n',
  b'<stdin>:14:17: File.open takes :read, :write, :append, :exclusive, :utf8 and :binary\n  at T.main (<stdin>:14)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.write!("w", "one\\ntwo\\nthree")\n'
  'IO.puts(inspect(File.stream!("w") |> Enum.to_list()))\n'
  'IO.puts(inspect(File.stream!("w", 4) |> Enum.to_list()))\n'
  'File.write!("w", "one\\n\\ntwo\\n")\n'
  'IO.puts(inspect(File.stream!("w") |> Enum.to_list()))\n'
  'IO.puts(inspect(File.stream!("w", 100) |> Enum.to_list()))\n'
  'File.write!("w", "")\n'
  'IO.puts(inspect(File.stream!("w") |> Enum.to_list()))\n'
  'IO.puts(inspect(File.stream!("w", 1) |> Enum.to_list()))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'["one\\n", "two\\n", "three"]\n["one\\n", "two\\n", "thre", "e"]\n["one\\n", "\\n", "two\\n"]\n["one\\n\\ntwo\\n"]\n[]\n[]\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(File.stream!("zz") |> Enum.to_list()))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not stream zz: no such file or directory\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(File.stream!("w", 0) |> Enum.to_list()))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: chunk size must be between 1 and 1073741824 bytes\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(System.cwd!() == File.cwd!()))\n'
  'IO.puts(inspect(System.env("ALCHEM_NO_SUCH_VARIABLE")))\n'
  'IO.puts(inspect(System.env("HOME") == System.get_env("HOME")))\n'
  'IO.puts(inspect(System.user_home() == System.get_env("HOME")))\n'
  'IO.puts(inspect(System.tmp_dir()))\n'
  'IO.puts(inspect(System.tmp_dir!()))\n'
  'System.put_env("TMPDIR", "/var/t")\n'
  'IO.puts(inspect(System.tmp_dir()))\n'
  'IO.puts(inspect(System.find_executable("alchem-no-such-program")))\n'
  'IO.puts(inspect(System.find_executable("sh") != none))\n'
  'IO.puts(inspect(System.find_executable("/bin/sh")))\n'
  'IO.puts(inspect(System.find_executable("/bin")))\n'
  'IO.puts(inspect(System.find_executable("")))\n'
  'IO.puts(inspect(System.find_executable(".")))\n'
  'IO.puts(inspect(System.find_executable("/etc/passwd")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'true\nnone\ntrue\ntrue\nsome("/tmp")\n"/tmp"\nsome("/var/t")\nnone\ntrue\nsome("/bin/sh")\nnone\nnone\nnone\nnone\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'System.put_env("ALCHEM_DOC_PUT", "on")\n'
  'IO.puts(inspect(System.get_env("ALCHEM_DOC_PUT", "")))\n'
  'IO.puts(inspect(System.get_env("ALCHEM_DOC_PUT")))\n'
  'System.put_env("ALCHEM_DOC_PUT", "off")\n'
  'System.put_env("B", "")\n'
  'IO.puts(inspect({System.get_env("ALCHEM_DOC_PUT"), System.get_env("B"), System.get_env("C")}))\n'
  'System.put_env("HOME", "/nowhere")\n'
  'IO.puts(inspect(System.user_home()))\n'
  'IO.puts(inspect(System.cmd("sh", ["-c", "echo $HOME $ALCHEM_DOC_PUT [$B]"])))\n'
  'System.put_env("PATH", "")\n'
  'IO.puts(inspect(System.find_executable("sh")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'"on"\nsome("on")\n{some("off"), some(""), none}\nsome("/nowhere")\n{"/nowhere off []\\n", 0}\nnone\n',
  b''),
 ('defmodule T do\n  def main() do\nSystem.put_env("", "x")\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:1: could not set : setenv: invalid argument\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nSystem.put_env("A=B", "x")\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:1: could not set A=B: setenv: invalid argument\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nSystem.put_env("A", "x\\x00y")\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:1: could not set A: setenv: invalid argument\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(System.monotonic_time(:millisecond) >= 0))\n'
  'IO.puts(inspect(System.monotonic_time() >= 0))\n'
  'IO.puts(inspect(System.os_time(:second) > 1700000000))\n'
  'IO.puts(inspect(System.system_time(:second) > 1700000000))\n'
  'IO.puts(inspect(System.system_time(:millisecond) > 1700000000000))\n'
  'IO.puts(inspect(System.system_time(:microsecond) > 1700000000000000))\n'
  'IO.puts(inspect(System.system_time(:native) == 0))\n'
  'IO.puts(inspect(System.convert_time_unit(2, :second, :millisecond)))\n'
  'IO.puts(inspect(System.convert_time_unit(1500, :millisecond, :second)))\n'
  'IO.puts(inspect(System.convert_time_unit(-1500, :millisecond, :second)))\n'
  'IO.puts(inspect(System.convert_time_unit(7, :native, :nanosecond)))\n'
  'IO.puts(inspect(System.convert_time_unit(7, :microsecond, :native)))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'true\ntrue\ntrue\ntrue\ntrue\ntrue\nfalse\n2000\n1\n-1\n7\n7000\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.system_time(:hour)))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: the time unit is :second, :millisecond, :microsecond, :nanosecond or :native, not :hour\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.convert_time_unit(7, :microsecond, :day)))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: the time units are :second, :millisecond, :microsecond, :nanosecond or :native\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'memory = System.memory()\n'
  'IO.puts(inspect(Map.fetch!(memory, :in_use) > 0 and Map.fetch!(memory, :held) >= Map.fetch!(memory, :idle)))\n'
  'IO.puts(inspect(Enum.sort(Map.keys(memory))))\n'
  'before = Map.fetch!(System.memory(), :collections)\n'
  'System.collect_garbage()\n'
  'IO.puts(inspect(Map.fetch!(System.memory(), :collections) > before))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'true\n[:collections, :held, :idle, :in_use, :stacks]\ntrue\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(System.cmd("echo", ["hello"])))\n'
  'IO.puts(inspect(System.cmd("sh", ["-c", "echo out; echo err >&2; exit 3"])))\n'
  'IO.puts(inspect(System.cmd("sh", ["-c", "echo out; echo err >&2; exit 3"], [stderr_to_stdout: "true"])))\n'
  'IO.puts(inspect(System.cmd("sh", ["-c", "kill -9 $$"])))\n'
  'IO.puts(inspect(System.cmd("pwd", [], [cd: "/"])))\n'
  'IO.puts(inspect(System.cmd("sh", ["-c", "echo $PWD"], [cd: "/usr/../etc"])))\n'
  'IO.puts(inspect(System.cmd("sh", ["-c", "echo $A $B $PWD"], [env: "A=1", env: "B=2", env: "A=3", cd: "/"])))\n'
  'IO.puts(inspect(System.cmd("/bin/echo", ["a b", ""])))\n'
  'IO.puts(inspect(System.cmd("cat", [])))\n'
  'IO.puts(inspect(System.cmd("head", ["-c", "200000", "/dev/zero"]) == {String.duplicate("\\x00", 200000), 0}))\n'
  'File.write!("x.sh", "#!/bin/sh\\necho ran $0 $1\\n")\n'
  'File.chmod("x.sh", 0o755)\n'
  'IO.puts(inspect(System.cmd("./x.sh", ["1"])))\n'
  'File.mkdir("sub")\n'
  'IO.puts(inspect(System.cmd("../x.sh", ["2"], [cd: "sub"])))\n'
  'IO.puts(inspect(System.cmd("env", [], [env: "ONLY=1"]) == System.cmd("env", [])))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'{"hello\\n", 0}\n{"out\\n", 3}\n{"out\\nerr\\n", 3}\n{"", -1}\n{"/\\n", 0}\n{"/etc\\n", 0}\n{"3 2 /\\n", 0}\n{"a b \\n", 0}\n{"", 0}\ntrue\n{"'
  b'ran ./x.sh 1\\n", 0}\n{"ran ../x.sh 2\\n", 0}\nfalse\n',
  b'err\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd("nope-cmd", ["hello"])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not run nope-cmd: exec: "nope-cmd": executable file not found in $PATH\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd("", ["hello"])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not run : exec: no command\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd("./nope", ["hello"])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not run ./nope: fork/exec ./nope: no such file or directory\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd("/etc/passwd", [])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not run /etc/passwd: fork/exec /etc/passwd: permission denied\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd("/etc", [])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not run /etc: fork/exec /etc: permission denied\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd("echo", [], [cd: "/nope"])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not run echo: chdir /nope: no such file or directory\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd("echo", [], [env: "NOEQ"])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: System.cmd: env: is "NAME=value"\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd("echo", [], [bogus: "x"])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: System.cmd: unknown option :bogus; the options are cd:, env: and stderr_to_stdout:\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.write!("x.sh", "#!/bin/sh\\n")\n'
  'File.chmod("x.sh", 0o755)\n'
  'IO.puts(inspect(System.cmd("./x.sh", ["a\\x00b"])))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:5:17: could not run ./x.sh: fork/exec ./x.sh: invalid argument\n  at T.main (<stdin>:5)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd("echo", [], [env: "A=\\x00"])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not run echo: exec: environment variable contains NUL\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.write!("x.sh", "#!/bin/sh\\necho ran\\n")\n'
  'File.chmod("x.sh", 0o755)\n'
  'System.put_env("PATH", ".")\n'
  'IO.puts(inspect(System.find_executable("x.sh")))\n'
  'IO.puts(inspect(System.cmd("x.sh", [])))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  2,
  b'none\n',
  b'<stdin>:7:17: could not run x.sh: exec: "x.sh": cannot run executable found relative to current directory\n  at T.main (<stdin>:7)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.write!("x.sh", "echo ran\\n")\n'
  'File.chmod("x.sh", 0o755)\n'
  'IO.puts(inspect(System.cmd("./x.sh", [])))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:5:17: could not run ./x.sh: fork/exec ./x.sh: exec format error\n  at T.main (<stdin>:5)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(System.cmd(".", [])))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: could not run .: exec: ".": executable file not found in $PATH\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(:stdio, "a")\nIO.puts(:stderr, "to standard error")\nx = :stderr\nIO.puts(x, "again")\n  end\nend\n',
  b'',
  1,
  0,
  b'a\n',
  b'to standard error\nagain\n'),
 ('defmodule T do\n  def main() do\nIO.puts(:other, "a")\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:1: IO.puts writes to :stdio or :stderr, not :other\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'ok(f) = File.open("x.txt", [:write])\n'
  'IO.puts(inspect(IO.puts(f, "line")))\n'
  'IO.puts(inspect(IO.write(f, "more")))\n'
  'IO.puts(inspect(IO.write(f, "")))\n'
  'IO.puts(inspect(File.close(f)))\n'
  'IO.puts(inspect(IO.puts(f, "line")))\n'
  'IO.puts(inspect(IO.write(f, "x")))\n'
  'IO.puts(inspect(File.read("x.txt")))\n'
  'IO.puts(inspect(File.open("x.txt", [:read], fn file -> IO.read(file, :line) end)))\n'
  'IO.puts(inspect(File.open("x.txt", [:read], fn file -> {IO.read(file, :line), IO.read(file, :line), IO.read(file, :line)} end)))\n'
  'IO.puts(inspect(File.open("x.txt", [:read], fn file -> {IO.read(file, 2), IO.read(file, :eof), IO.read(file, :eof), IO.read(file, 1), '
  'IO.read(file, 0)} end)))\n'
  'IO.puts(inspect(File.open("x.txt", [:read], fn file -> {IO.binread(file, 3), IO.binread(file, 100), IO.binread(file, 1), IO.binread(file, 0)} '
  'end)))\n'
  'IO.puts(inspect(File.open("x.txt", [:read], fn file -> {IO.read(file, :all), IO.read(file, :line)} end)))\n'
  'IO.puts(inspect(File.open("x.txt", [:read], fn file -> IO.write(file, "no") end)))\n'
  'IO.puts(inspect(File.open("x.txt", [:write], fn file -> IO.read(file, :line) end)))\n'
  'IO.puts(inspect(File.open("x.txt", [:append], fn file -> IO.puts(file, "tail") end)))\n'
  'IO.puts(inspect(File.read("x.txt")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'ok({})\nok({})\nok({})\ntrue\nerror("closed")\nerror("closed")\nok("line\\nmore")\nok(some("line\\n"))\nok({some("line\\n"), some("more"), none'
  b'})\nok({some("li"), some("ne\\nmore"), none, none, some("")})\nok({some("lin"), some("e\\nmore"), none, some("")})\nok({some("line\\nmore"), n'
  b'one})\nok({})\nok(none)\nok({})\nok("tail\\n")\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.write!("u.txt", "héllo wörld\\n€uro \\xff\\xe2\\x82 ok \\xf0\\x9f\\x98\\x80!")\n'
  'IO.puts(inspect(File.open("u.txt", [:read], fn f -> {IO.read(f, 3), IO.read(f, 9), IO.read(f, 6), IO.read(f, 3), IO.read(f, 100)} end)))\n'
  'IO.puts(inspect(File.open("u.txt", [:read], fn f -> {IO.binread(f, 2), IO.read(f, 2), IO.read(f, :line), IO.binread(f, 2), IO.read(f, 1)} end)))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'ok({some("h\xc3\xa9l"), some("lo w\xc3\xb6rld\\n"), some("\xe2\x82\xacuro \xef\xbf\xbd"), some("\xef\xbf\xbd\xef\xbf\xbd "), some("ok'
  b' \xf0\x9f\x98\x80!")})\nok({some("h\\xc3"), some("\xef\xbf\xbdl"), some("lo w\xc3\xb6rld\\n"), some("\\xe2\\x82"), some("\xef\xbf\xbd")})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.write!("big.txt", String.duplicate("0123456789", 1000) <> "\\nsecond\\n" <> String.duplicate("x", 5000))\n'
  'r = File.open("big.txt", [:read], fn f -> {IO.read(f, :line), IO.read(f, :line), IO.read(f, :line), IO.read(f, :line)} end)\n'
  'ok(t) = r\n'
  'some(a) = elem(t, 0)\n'
  'some(c) = elem(t, 2)\n'
  'IO.puts(inspect({byte_size(a), elem(t, 1), byte_size(c), elem(t, 3)}))\n'
  'ok(u) = File.open("big.txt", [:read], fn f -> {IO.binread(f, 5), IO.binread(f, 5000), IO.binread(f, 10), IO.read(f, 4500), IO.read(f, :line), '
  'IO.binread(f, 99999)} end)\n'
  'some(b) = elem(u, 1)\n'
  'some(d) = elem(u, 3)\n'
  'some(e) = elem(u, 5)\n'
  'IO.puts(inspect({elem(u, 0), byte_size(b), elem(u, 2), byte_size(d), elem(u, 4), byte_size(e)}))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'{10001, some("second\\n"), 5000, none}\n{some("01234"), 5000, some("5678901234"), 4500, some("567890123456789012345678901234567890123456789012'
  b'345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456'
  b'789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890'
  b'123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234'
  b'56789\\n"), 5007}\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.write!("rw.txt", "one\\ntwo\\nthree\\n")\n'
  'ok(f) = File.open("rw.txt", [:read, :write])\n'
  'IO.puts(inspect(IO.read(f, :line)))\n'
  'IO.puts(inspect(IO.write(f, "X")))\n'
  'IO.puts(inspect(IO.read(f, :line)))\n'
  'File.close(f)\n'
  'IO.puts(inspect(File.read("rw.txt")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'some("one\\n")\nok({})\nsome("two\\n")\nok("one\\ntwo\\nthree\\nX")\n',
  b''),
 ('defmodule T do\n  def main() do\nok(f) = File.open("x.txt", [:write])\nFile.close(f)\nIO.puts(inspect(IO.read(f, :line)))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:5:17: the file is closed\n  at T.main (<stdin>:5)\n'),
 ('defmodule T do\n  def main() do\nok(f) = File.open("x.txt", [:write])\nIO.puts(inspect(IO.read(f, -1)))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:4:17: the count must not be negative\n  at T.main (<stdin>:4)\n'),
 ('defmodule T do\n  def main() do\nok(f) = File.open("x.txt", [:write])\nIO.puts(inspect(IO.binread(f, -1)))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:4:17: the count must not be negative\n  at T.main (<stdin>:4)\n'),
 ('defmodule T do\n  def main() do\nok(f) = File.open("x.txt", [:write])\nIO.puts(inspect(IO.read(f, :bogus)))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:4:17: IO.read takes :line, :eof or a number\n  at T.main (<stdin>:4)\n'),
 ('defmodule T do\n  def main() do\nok(f) = File.open("x.txt", [:write])\nFile.close(f)\nIO.puts(inspect(IO.binread(f, 1)))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:5:17: the file is closed\n  at T.main (<stdin>:5)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect({IO.read(:line), IO.read(:stdio, :line), IO.read(:line), IO.read(:line)}))\n  end\nend\n',
  b'one\ntwo\r\nthree',
  1,
  0,
  b'{some("one\\n"), some("two\\r\\n"), some("three"), none}\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect({IO.read(2), IO.binread(3), IO.read(:eof), IO.read(:eof), IO.read(1), IO.binread(1), IO.read(0), IO.binread(0)}))\n'
  '  end\n'
  'end\n',
  b'one\ntwo\r\nthree',
  1,
  0,
  b'{some("on"), some("e\\nt"), some("wo\\r\\nthree"), none, none, none, some(""), some("")}\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect({IO.read(3), IO.read(4), IO.read(3), IO.read(5), IO.read(100)}))\n  end\nend\n',
  b'h\xc3\xa9llo \xe2\x82\xac \xff\xe2\x82 ok \xf0\x9f\x98\x80!\xe2',
  1,
  0,
  b'{some("h\xc3\xa9l"), some("lo \xe2\x82\xac"), some(" \xef\xbf\xbd\xef\xbf\xbd"), some("\xef\xbf\xbd ok "), some("\xf0\x9f\x98\x80!\xef\xbf\xbd"'
  b')}\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect({IO.read(:line), IO.read_line(), IO.read(:all)}))\n  end\nend\n',
  b'abc\ndef\n',
  1,
  0,
  b'{some("abc\\n"), some("def"), none}\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect({IO.gets("prompt> "), IO.read(:all)}))\n  end\nend\n',
  b'abc\ndef\n',
  1,
  0,
  b'prompt> {some("abc"), some("def\\n")}\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(IO.stream() |> Enum.to_list()))\n  end\nend\n',
  b'abc\r\ndef\n\nlast',
  1,
  0,
  b'["abc", "def", "", "last"]\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect({IO.stream() |> Enum.to_list(), IO.read(:line), IO.read(1), IO.binread(1), IO.gets("")}))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'{[], none, none, none, none}\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(IO.read(:bogus)))\n  end\nend\n',
  b'x',
  1,
  2,
  b'',
  b'<stdin>:3:17: IO.read takes :line, :eof or a number of characters\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(IO.read(:stderr, :line)))\n  end\nend\n',
  b'x',
  1,
  2,
  b'',
  b'<stdin>:3:17: IO.read reads :stdio, or a file opened with File.open\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(IO.read(-1)))\n  end\nend\n',
  b'x',
  1,
  2,
  b'',
  b'<stdin>:3:17: IO.read needs a nonnegative count\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(IO.binread(-1)))\n  end\nend\n',
  b'x',
  1,
  2,
  b'',
  b'<stdin>:3:17: IO.binread needs a nonnegative count\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.warn("careful")\n[1, 2] |> IO.inspect() |> length()\nIO.write("no newline")\n  end\nend\n',
  b'',
  1,
  0,
  b'[1, 2]\nno newline',
  b'careful\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect({IO.read(4), IO.read_line(), IO.read_all()}))\n  end\nend\n',
  b'abc\xe2A\nrest\n',
  1,
  0,
  b'{some("abc\xef\xbf\xbd"), some("A"), "rest\\n"}\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect({IO.read(4), IO.read(:line), IO.read_all()}))\n  end\nend\n',
  b'abc\xf0\x9f\x98Z\nrest\n',
  1,
  0,
  b'{some("abc\xef\xbf\xbd"), some("\\x9f\\x98Z\\n"), "rest\\n"}\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect({IO.read(4), IO.binread(2), IO.read(:all)}))\n  end\nend\n',
  b'abc\xf0\x9f\x98Z\nrest\n',
  1,
  0,
  b'{some("abc\xef\xbf\xbd"), some("\\x9f\\x98"), some("Z\\nrest\\n")}\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'IO.puts(inspect(Path.absname("a.txt") == Path.join(File.cwd!(), "a.txt")))\n'
  'IO.puts(inspect(String.ends_with?(Path.expand("a/b/../c"), "/a/c")))\n'
  'IO.puts(inspect(Path.type(Path.expand("docs"))))\n'
  'IO.puts(inspect(Path.type("docs")))\n'
  'IO.puts(inspect(Path.expand("/a/./b//../c/")))\n'
  'IO.puts(inspect(Path.expand("~") == System.get_env("HOME", "")))\n'
  'IO.puts(inspect(Path.expand("~/x/../y") == System.get_env("HOME", "") <> "/y"))\n'
  'IO.puts(inspect(Path.expand("~user") == System.get_env("HOME", "") <> "user"))\n'
  'IO.puts(inspect(Path.expand("") == File.cwd!()))\n'
  'IO.puts(inspect(Path.expand(".") == File.cwd!()))\n'
  'IO.puts(inspect(Path.expand("..") == Path.dirname(File.cwd!())))\n'
  'IO.puts(inspect(Path.absname("/")))\n'
  'System.put_env("HOME", "")\n'
  'IO.puts(inspect(Path.expand("~/q") == File.cwd!() <> "/~/q"))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'true\ntrue\n:absolute\n:relative\n"/a/c"\ntrue\ntrue\ntrue\ntrue\ntrue\ntrue\n"/"\ntrue\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.mkdir_p("doc_wildcard/sub/deep")\n'
  'File.write!("doc_wildcard/a.txt", "")\n'
  'File.write!("doc_wildcard/b.txt", "")\n'
  'File.write!("doc_wildcard/c.md", "")\n'
  'File.write!("doc_wildcard/sub/d.txt", "")\n'
  'File.write!("doc_wildcard/sub/deep/e.txt", "")\n'
  'File.write!("doc_wildcard/.hidden", "")\n'
  'File.write!("doc_wildcard/x[1].txt", "")\n'
  'File.write!("doc_wildcard/ü.txt", "")\n'
  'File.write!("doc_wildcard/a-b", "")\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/*.txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/*")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/?.txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/[ab].txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/[^ab].txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/[a-c].*")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/*/*.txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/*/*/*.txt")))\n'
  'IO.puts(inspect(Path.wildcard("*/a.txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/a.txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/nope")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/x\\\\[1\\\\].txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/x[[]1].txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/*b*")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/a*t")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/a*x")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/*.t?t")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/[ü].txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/[à-ÿ].txt")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/[a\\\\-]-b")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/sub/")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard//sub/*")))\n'
  'IO.puts(inspect(Path.wildcard("./doc_wildcard/s*")))\n'
  'IO.puts(inspect(Path.wildcard("*")))\n'
  'IO.puts(inspect(Path.wildcard("")))\n'
  'IO.puts(inspect(Path.wildcard("/de[v]/nul?")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/**")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/*/")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/a.txt/*")))\n'
  'IO.puts(inspect(Path.wildcard("doc_wildcard/*[")))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  2,
  b'["doc_wildcard/a.txt", "doc_wildcard/b.txt", "doc_wildcard/x[1].txt", "doc_wildcard/\xc3\xbc.txt"]\n["doc_wildcard/.hidden", "doc_wildcard/a-b"'
  b', "doc_wildcard/a.txt", "doc_wildcard/b.txt", "doc_wildcard/c.md", "doc_wildcard/sub", "doc_wildcard/x[1].txt", "doc_wildcard/\xc3\xbc.txt"]\n['
  b'"doc_wildcard/a.txt", "doc_wildcard/b.txt", "doc_wildcard/\xc3\xbc.txt"]\n["doc_wildcard/a.txt", "doc_wildcard/b.txt"]\n["doc_wildcard/\xc3'
  b'\xbc.txt"]\n["doc_wildcard/a.txt", "doc_wildcard/b.txt", "doc_wildcard/c.md"]\n["doc_wildcard/sub/d.txt"]\n["doc_wildcard/sub/deep/e.txt"]\n["d'
  b'oc_wildcard/a.txt"]\n["doc_wildcard/a.txt"]\n[]\n["doc_wildcard/x[1].txt"]\n["doc_wildcard/x[1].txt"]\n["doc_wildcard/a-b", "doc_wildcard/b.txt",'
  b' "doc_wildcard/sub"]\n["doc_wildcard/a.txt"]\n[]\n["doc_wildcard/a.txt", "doc_wildcard/b.txt", "doc_wildcard/x[1].txt", "doc_wildcard/\xc3\xbc.tx'
  b't"]\n["doc_wildcard/\xc3\xbc.txt"]\n["doc_wildcard/\xc3\xbc.txt"]\n["doc_wildcard/a-b"]\n["doc_wildcard/sub/"]\n["doc_wildcard/sub/d.txt", "doc_w'
  b'ildcard/sub/deep"]\n["doc_wildcard/sub"]\n["doc_wildcard"]\n[]\n["/dev/null"]\n["doc_wildcard/.hidden", "doc_wildcard/a-b", "doc_wildcard/a.txt",'
  b' "doc_wildcard/b.txt", "doc_wildcard/c.md", "doc_wildcard/sub", "doc_wildcard/x[1].txt", "doc_wildcard/\xc3\xbc.txt"]\n[]\n[]\n',
  b'<stdin>:42:17: malformed wildcard pattern\n  at T.main (<stdin>:42)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(Path.wildcard("[")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: malformed wildcard pattern\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(Path.wildcard("a[")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: malformed wildcard pattern\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(Path.wildcard("[]")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: malformed wildcard pattern\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(Path.wildcard("[a-]")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: malformed wildcard pattern\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nIO.puts(inspect(Path.wildcard("x\\\\")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:3:17: malformed wildcard pattern\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n  def main() do\nFile.write!("ab", "")\nIO.puts(inspect(Path.wildcard("a*[")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:4:17: malformed wildcard pattern\n  at T.main (<stdin>:4)\n'),
 ('defmodule T do\n  def main() do\nFile.write!("ab", "")\nIO.puts(inspect(Path.wildcard("*b[")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:4:17: malformed wildcard pattern\n  at T.main (<stdin>:4)\n'),
 ('defmodule T do\n  def main() do\nFile.write!("ab", "")\nIO.puts(inspect(Path.wildcard("[-]")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:4:17: malformed wildcard pattern\n  at T.main (<stdin>:4)\n'),
 ('defmodule T do\n  def main() do\nFile.write!("ab", "")\nIO.puts(inspect(Path.wildcard("a[\\xff]")))\n  end\nend\n',
  b'',
  1,
  2,
  b'',
  b'<stdin>:4:17: malformed wildcard pattern\n  at T.main (<stdin>:4)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'File.mkdir_p("d/e")\n'
  'File.write!("d/e/x", "1")\n'
  'File.write!("d/y", "2")\n'
  'File.write!("f", "3")\n'
  'File.chmod("f", 0o000)\n'
  'File.chmod("d/e", 0o555)\n'
  'IO.puts(inspect(File.read("f")))\n'
  'IO.puts(inspect(File.read_binary("f")))\n'
  'IO.puts(inspect(File.write("f", "x")))\n'
  'IO.puts(inspect(File.write("f", "x", [:append])))\n'
  'IO.puts(inspect(File.open("f", [:read])))\n'
  'IO.puts(inspect(File.cp("f", "g")))\n'
  'IO.puts(inspect(File.cp("d/y", "d/e/z")))\n'
  'IO.puts(inspect(File.touch("d/e/t")))\n'
  'IO.puts(inspect(File.mkdir("d/e/m")))\n'
  'IO.puts(inspect(File.mkdir_p("d/e/m/n")))\n'
  'IO.puts(inspect(File.rm("d/e/x")))\n'
  'IO.puts(inspect(File.rename("d/e/x", "d/x")))\n'
  'IO.puts(inspect(File.ln("d/y", "d/e/l")))\n'
  'IO.puts(inspect(File.ln_s("d/y", "d/e/l")))\n'
  'IO.puts(inspect(File.cp_r("d/y", "d/e/c")))\n'
  'IO.puts(inspect(File.cp_r("f", "h")))\n'
  'IO.puts(inspect(File.rm_rf("d")))\n'
  'IO.puts(inspect(File.ls("d")))\n'
  'ok(sf) = File.stat("f")\n'
  'IO.puts(inspect({sf.access, sf.mode}))\n'
  'File.chmod("d/e", 0o000)\n'
  'ok(se) = File.stat("d/e")\n'
  'IO.puts(inspect({se.type, se.access, se.mode}))\n'
  'IO.puts(inspect(File.ls("d/e")))\n'
  'IO.puts(inspect(File.exists?("d/e/x")))\n'
  'IO.puts(inspect(File.stat("d/e/x")))\n'
  'IO.puts(inspect(Path.wildcard("d/*/*")))\n'
  'IO.puts(inspect(File.rm_rf("d")))\n'
  'IO.puts(inspect(System.cmd("./f", [])))\n'
  '  end\n'
  'end\n',
  b'',
  0,
  2,
  b'error("open f: permission denied")\nerror("open f: permission denied")\nerror("open f: permission denied")\nerror("eacces")\nerror("eacces")\nerr'
  b'or("open f: permission denied")\nerror("open d/e/z: permission denied")\nerror("open d/e/t: permission denied")\nerror("mkdir d/e/m: permission'
  b' denied")\nerror("mkdir d/e/m: permission denied")\nerror("remove d/e/x: permission denied")\nerror("rename d/e/x d/x: permission denied")\nerro'
  b'r("eacces")\nerror("eacces")\nerror("eacces")\nerror("eacces")\nerror("unlinkat ./d/e/x: permission denied")\nok(["e"])\n{:none, 0}\n{:director'
  b'y, :none, 0}\nerror("open d/e: permission denied")\nfalse\nerror("eacces")\n[]\nerror("openfdat ./d/e: permission denied")\n',
  b'<stdin>:37:17: could not run ./f: fork/exec ./f: permission denied\n  at T.main (<stdin>:37)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  'System.put_env("PWD", "/nowhere")\n'
  'IO.puts(inspect(File.cwd() == ok(File.cwd!())))\n'
  'IO.puts(inspect(String.starts_with?(File.cwd!(), "/") and File.cwd!() != "/nowhere"))\n'
  'File.mkdir("real")\n'
  'File.ln_s("real", "link")\n'
  'ok(base) = File.cwd()\n'
  'System.put_env("PWD", base <> "/link")\n'
  'IO.puts(inspect(File.cwd() == ok(base <> "/link")))\n'
  'IO.puts(inspect(Path.expand("x") == base <> "/link/x"))\n'
  'IO.puts(inspect(System.cmd("sh", ["-c", "echo $PWD"], [cd: "real"]) == {base <> "/link/real\\n", 0}))\n'
  '  end\n'
  'end\n',
  b'',
  1,
  0,
  b'true\ntrue\nfalse\nfalse\nfalse\n',
  b''),
 ('defmodule T do\n  def main() do\nIO.puts(inspect({0x1F, 0o17, 0b101, 0xff_ff, -0x10, 0x7FFFFFFFFFFFFFFF, -0x8000000000000000}))\n  end\nend\n',
  b'',
  1,
  0,
  b'{31, 15, 5, 65535, -16, 9223372036854775807, -9223372036854775808}\n',
  b'')]
# The pinned compiler rejects these too.
REJECTED=['x = File.rename("a")','x = File.stat(1)','x = File.open("a")','x = File.open("a", ["read"])','x = File.close("a")','x = File.cp("a")','x = File.chmod("a", "b")',
          'x = File.write("a", "b", [1])','x = File.stream!(1)','x = File.ls()','x = System.cmd("a")','x = System.cmd("a", "b")','x = System.cmd("a", ["b"], [cd: 1])',
          'x = System.put_env("a")','x = System.find_executable(1)','x = System.monotonic_time("second")','x = System.convert_time_unit(1, :second)','x = System.tmp_dir(1)',
          'x = Path.wildcard(1)','x = Path.expand()','x = IO.read("line")','x = IO.binread("a")','x = IO.puts(1, "a")','x = IO.read(:stdio, 1)','x = Sys.call(39)','x = 0x','x = 0b2','x = 0o8','x = 0x1_']


def limits():
    os.umask(0o022)
    resource.setrlimit(resource.RLIMIT_AS,(2<<30,2<<30))
    resource.setrlimit(resource.RLIMIT_CPU,(20,20))


def run(program,stdin,directory):
    """The program in a session of its own, which is killed with everything it started."""
    process=subprocess.Popen([program],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=directory,
                             env={'PATH':'/usr/bin:/bin','HOME':'/home/gate'},start_new_session=True,preexec_fn=limits)
    try:out,err=process.communicate(stdin,timeout=120)
    finally:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    return process.returncode,out,err


def verify(compiler):
    checked=skipped=0
    with tempfile.TemporaryDirectory(prefix='alchem-system-') as base:
        for number,(source,stdin,root,status,out,err) in enumerate(RUNS):
            if os.getuid()==0 and not root:skipped+=1;continue
            built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert built.returncode==0,(source,built.returncode,built.stderr)
            program=Path(base)/f'p{number}';program.write_bytes(built.stdout);program.chmod(0o700)
            directory=Path(base)/f'd{number}';directory.mkdir(0o700)
            try:got=run(str(program),stdin,str(directory))
            finally:
                subprocess.run(['chmod','-R','u+rwx',str(directory)],check=False);shutil.rmtree(directory,ignore_errors=True)
            assert got==(status,out,err),(source,got,(status,out,err))
            checked+=1
        for statement in REJECTED:
            source='defmodule M do def main() do '+statement+'\nSystem.halt(0) end end'
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(statement,r.returncode)
    if skipped:print(f'SKIP {skipped} programs that need a user other than root')
    print(f'PASS files and system: {checked} programs as the pinned compiler runs them, {len(REJECTED)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]))
