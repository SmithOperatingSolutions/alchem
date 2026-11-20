#!/usr/bin/env python3
"""DiskStore: every program runs as the pinned compiler runs it.

DiskStore (spec/alchem-network.md). Each program runs in an empty directory
of its own, which is also its TMPDIR: the examples of the library reference
keep their file in System.tmp_dir!() under a random name, which is here a
fixed one (Crypto.strong_rand_bytes is not this gate's to depend on). The
programs print what the files hold, byte for byte: the log's records, their
checksums and what a compaction leaves."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import signal
import socket
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule Main do\n'
  '  def main() do\n'
  '    path = "store_a"\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(store))\n'
  '    IO.puts(inspect(DiskStore.put(store, "greeting", "hello")))\n'
  '    IO.puts(inspect(DiskStore.get(store, "greeting")))\n'
  '    IO.puts(inspect(DiskStore.get(store, "missing")))\n'
  '    IO.puts(inspect(DiskStore.commit(store, [{"b", "2"}, {"a", "1"}, {"user:1", "al"}, {"user:2", "bo"}, '
  '{"visit:1", "x"}], ["greeting", "nothing"])))\n'
  '    IO.puts(inspect(DiskStore.keys(store)))\n'
  '    IO.puts(inspect(DiskStore.size(store)))\n'
  '    IO.puts(inspect(DiskStore.prefix(store, "user:")))\n'
  '    IO.puts(inspect(DiskStore.prefix(store, "")))\n'
  '    IO.puts(inspect(DiskStore.prefix(store, "\\xff")))\n'
  '    IO.puts(inspect(DiskStore.range(store, "a", "c")))\n'
  '    IO.puts(inspect(DiskStore.range(store, "c", "a")))\n'
  '    IO.puts(inspect(DiskStore.has_key?(store, "a")))\n'
  '    IO.puts(inspect(DiskStore.delete(store, "a")))\n'
  '    IO.puts(inspect(DiskStore.delete(store, "a")))\n'
  '    IO.puts(inspect(DiskStore.has_key?(store, "a")))\n'
  '    count = fn(held: option[string]): option[string] do\n'
  '      case held do\n'
  '        some(n) -> some(Integer.to_string(String.to_integer(n) + 1))\n'
  '        none -> some("1")\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(DiskStore.update(store, "visits", count)))\n'
  '    IO.puts(inspect(DiskStore.update(store, "visits", count)))\n'
  '    IO.puts(inspect(DiskStore.update(store, "visits", fn(_: option[string]): option[string] do none '
  'end)))\n'
  '    IO.puts(inspect(DiskStore.update(store, "visits", fn(_: option[string]): option[string] do none '
  'end)))\n'
  '    IO.puts(inspect(DiskStore.commit(store, [], [])))\n'
  '    ok(same) = DiskStore.open("./store_a")\n'
  '    IO.puts(inspect(DiskStore.size(same)))\n'
  '    IO.puts(inspect(File.read_binary!(path)))\n'
  '    IO.puts(inspect(DiskStore.compact(store)))\n'
  '    IO.puts(inspect(File.read_binary!(path)))\n'
  '    IO.puts(inspect(File.exists?(path <> ".compact")))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(DiskStore.close(same)))\n'
  '    IO.puts(inspect(DiskStore.put(store, "k", "v")))\n'
  '    IO.puts(inspect(DiskStore.delete(store, "k")))\n'
  '    IO.puts(inspect(DiskStore.commit(store, [{"k", "v"}], [])))\n'
  '    IO.puts(inspect(DiskStore.commit(store, [], [])))\n'
  '    IO.puts(inspect(DiskStore.compact(store)))\n'
  '    IO.puts(inspect(DiskStore.update(store, "k", count)))\n'
  '    ok(again) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.keys(again)))\n'
  '    IO.puts(inspect(DiskStore.prefix(again, "user")))\n'
  '    DiskStore.close(again)\n'
  '    File.write("junk", "this is not a store at all")\n'
  '    IO.puts(inspect(DiskStore.open("junk")))\n'
  '    File.write("short", "ALCHEM")\n'
  '    ok(s2) = DiskStore.open("short")\n'
  '    IO.puts(inspect(DiskStore.keys(s2)))\n'
  '    DiskStore.close(s2)\n'
  '    IO.puts(inspect(File.read_binary!("short")))\n'
  '    File.mkdir("adir")\n'
  '    IO.puts(inspect(DiskStore.open("adir")) |> String.replace(~r/ \\/.*adir/, " DIR"))\n'
  '    IO.puts(inspect(DiskStore.open("nodir/x")))\n'
  '    IO.puts(inspect(DiskStore.open("")) |> String.replace(~r/ \\/[^:]*/, " CWD"))\n'
  '    File.write("cut", File.read_binary!(path) <> "\\x05\\x00\\x00\\x00garbage")\n'
  '    ok(s3) = DiskStore.open("cut")\n'
  '    IO.puts(inspect(DiskStore.keys(s3)))\n'
  '    IO.puts(inspect(File.read_binary!("cut") == File.read_binary!(path)))\n'
  '    DiskStore.close(s3)\n'
  '    IO.puts(inspect(DiskStore.get(store, "k")))\n'
  '  end\n'
  'end\n',
  2,
  b'#storeHandle<>\nok({})\nsome("hello")\nnone\nok({})\n["a", "b", "user:1", "user:2", "visit:1"]\n5\n[{"u'
  b'ser:1", "al"}, {"user:2", "bo"}]\n[{"a", "1"}, {"b", "2"}, {"user:1", "al"}, {"user:2", "bo"}, {"visit:1"'
  b', "x"}]\n[]\n[{"a", "1"}, {"b", "2"}]\n[]\ntrue\nok({})\nok({})\nfalse\nok(some("1"))\nok(some("2"))\n'
  b'ok(none)\nok(none)\nok({})\n4\n"ALCHEMSTORE1\\n\\x10\\x00\\x00\\x00\\xd0\\xc9}\\v\\x01\\bgreeting\\x05h'
  b'ello>\\x00\\x00\\x00\\x01\\x17#O\\x02\\bgreeting\\x02\\anothing\\x01\\x01b\\x012\\x01\\x01a\\x011\\x01\\x'
  b'06user:1\\x02al\\x01\\x06user:2\\x02bo\\x01\\avisit:1\\x01x\\x03\\x00\\x00\\x00\\xf3mk\\xdf\\x02\\x01a\\'
  b'x03\\x00\\x00\\x00\\xf3mk\\xdf\\x02\\x01a\\n\\x00\\x00\\x00\\tQ\\xf8\\xe8\\x01\\x06visits\\x011\\n\\x00'
  b'\\x00\\x00\\xb3\\x00\\xf1q\\x01\\x06visits\\x012\\b\\x00\\x00\\x00gu]\\xb1\\x02\\x06visits"\nok({})\n"ALC'
  b'HEMSTORE1\\n\\x05\\x00\\x00\\x00G\\xc6a\\xd9\\x01\\x01b\\x012\\v\\x00\\x00\\x00\\x12]\\xf88\\x01\\x06u'
  b'ser:1\\x02al\\v\\x00\\x00\\x00\\x85\\xf0i\\x98\\x01\\x06user:2\\x02bo\\v\\x00\\x00\\x00\\x9c\\xf9\\x1b'
  b'\\a\\x01\\avisit:1\\x01x"\nfalse\ntrue\nfalse\nerror("closed")\nerror("closed")\nerror("closed")\nok({}'
  b')\nerror("closed")\nerror("closed")\n["b", "user:1", "user:2", "visit:1"]\n[{"user:1", "al"}, {"user:2",'
  b' "bo"}]\nerror("junk is not a store")\n[]\n"ALCHEMSTORE1\\n"\nerror("read DIR: is a directory")\nerror'
  b'("enoent")\nerror("read CWD: is a directory")\n["b", "user:1", "user:2", "visit:1"]\ntrue\n',
  b'<stdin>:66:21: DiskStore.get: the store is closed\n  at Main.main (<stdin>:66)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(DiskStore.put(store, "k", "v")))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\nerror("closed")\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.put(store, "cart:7", "pen")))\n'
  '    IO.puts(inspect(DiskStore.commit(store, [{"order:1", "pen"}, {"stock:pen", "4"}], ["cart:7"])))\n'
  '    IO.puts(inspect(DiskStore.keys(store)))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\nok({})\n["order:1", "stock:pen"]\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.put(store, "k", "old")))\n'
  '    IO.puts(inspect(DiskStore.put(store, "k", "new")))\n'
  '    IO.puts(inspect(DiskStore.compact(store)))\n'
  '    IO.puts(inspect(DiskStore.get(store, "k")))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\nok({})\nok({})\nsome("new")\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.put(store, "k", "v")))\n'
  '    IO.puts(inspect(DiskStore.delete(store, "k")))\n'
  '    IO.puts(inspect(DiskStore.get(store, "k")))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\nok({})\nnone\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.get(store, "missing")))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'none\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.put(store, "k", "")))\n'
  '    IO.puts(inspect({DiskStore.has_key?(store, "k"), DiskStore.has_key?(store, "other")}))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\n{true, false}\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.commit(store, [{"b", "2"}, {"a", "1"}], [])))\n'
  '    IO.puts(inspect(DiskStore.keys(store)))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\n["a", "b"]\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.put(store, "greeting", "hello")))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    ok(again) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.get(again, "greeting")))\n'
  '    IO.puts(inspect(DiskStore.close(again)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\ntrue\nsome("hello")\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.commit(store, [{"user:1", "al"}, {"user:2", "bo"}, {"visit:1", "x"}], '
  '[])))\n'
  '    IO.puts(inspect(DiskStore.prefix(store, "user:")))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\n[{"user:1", "al"}, {"user:2", "bo"}]\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.put(store, "user:1", "al")))\n'
  '    IO.puts(inspect(DiskStore.get(store, "user:1")))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\nsome("al")\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.commit(store, [{"a", "1"}, {"b", "2"}, {"c", "3"}], [])))\n'
  '    IO.puts(inspect(DiskStore.range(store, "a", "c")))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\n[{"a", "1"}, {"b", "2"}]\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    IO.puts(inspect(DiskStore.put(store, "k", "v")))\n'
  '    IO.puts(inspect(DiskStore.size(store)))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({})\n1\ntrue\nok({})\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    path = Path.join(System.tmp_dir!(), "store_doc_" <> "A1B2C3D4E5F6")\n'
  '    ok(store) = DiskStore.open(path)\n'
  '    count = fn(held: option[string]): option[string] do\n'
  '      case held do\n'
  '        some(n) -> some(Integer.to_string(String.to_integer(n) + 1))\n'
  '        none -> some("1")\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(DiskStore.update(store, "visits", count)))\n'
  '    IO.puts(inspect(DiskStore.update(store, "visits", count)))\n'
  '    IO.puts(inspect(DiskStore.close(store)))\n'
  '    IO.puts(inspect(File.rm(path)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok(some("1"))\nok(some("2"))\ntrue\nok({})\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    ok(s) = DiskStore.open("many")\n'
  '    for i <- 1..500 do DiskStore.put(s, "k" <> Integer.to_string(rem(i * 7919, 1000)), '
  'Integer.to_string(i)) end\n'
  '    keys = DiskStore.keys(s)\n'
  '    IO.puts(inspect({DiskStore.size(s), keys == Enum.sort(keys), Enum.take(keys, 5), '
  'length(DiskStore.prefix(s, "k1")), length(DiskStore.range(s, "k2", "k3"))}))\n'
  '    for i <- 1..250 do DiskStore.delete(s, "k" <> Integer.to_string(rem(i * 7919, 1000))) end\n'
  '    IO.puts(inspect({DiskStore.size(s), Enum.take(DiskStore.keys(s), 3)}))\n'
  '    before = byte_size(File.read_binary!("many"))\n'
  '    IO.puts(inspect(DiskStore.compact(s)))\n'
  '    IO.puts(inspect({before, byte_size(File.read_binary!("many"))}))\n'
  '    DiskStore.close(s)\n'
  '    ok(t) = DiskStore.open("many")\n'
  '    IO.puts(inspect({DiskStore.size(t), DiskStore.get(t, "k919"), DiskStore.get(t, "k" <> '
  'Integer.to_string(rem(300 * 7919, 1000)))}))\n'
  '    DiskStore.close(t)\n'
  '    ok(b) = DiskStore.open("bytes")\n'
  '    DiskStore.commit(b, [{"\\xff", "high"}, {"\\xff\\xff", "higher"}, {"", "empty key"}, {"a\\x00b", '
  '"nul"}, {"a", ""}, {"\\xfe\\xff", "x"}], [])\n'
  '    IO.puts(inspect(DiskStore.keys(b)))\n'
  '    IO.puts(inspect(DiskStore.prefix(b, "\\xff")))\n'
  '    IO.puts(inspect(DiskStore.prefix(b, "\\xfe\\xff")))\n'
  '    IO.puts(inspect(DiskStore.prefix(b, "a")))\n'
  '    IO.puts(inspect(DiskStore.range(b, "", "b")))\n'
  '    IO.puts(inspect(DiskStore.get(b, "")))\n'
  '    big = String.duplicate("v", 300000)\n'
  '    DiskStore.put(b, "big", big)\n'
  '    IO.puts(inspect(DiskStore.get(b, "big") == some(big)))\n'
  '    DiskStore.close(b)\n'
  '    ok(c) = DiskStore.open("bytes")\n'
  '    IO.puts(inspect({DiskStore.size(c), DiskStore.get(c, "big") == some(big), DiskStore.get(c, '
  '"a\\x00b")}))\n'
  '    DiskStore.close(c)\n'
  '    ok(g) = DiskStore.open("grow")\n'
  '    for i <- 1..8 do DiskStore.put(g, "same", String.duplicate(Integer.to_string(i), 200000)) end\n'
  '    IO.puts(inspect({byte_size(File.read_binary!("grow")) < 1500000, DiskStore.get(g, "same") == '
  'some(String.duplicate("8", 200000))}))\n'
  '    DiskStore.close(g)\n'
  '    data = File.read_binary!("many")\n'
  '    File.write("torn", data <> "\\x09\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x01\\x01k")\n'
  '    ok(torn) = DiskStore.open("torn")\n'
  '    IO.puts(inspect({DiskStore.size(torn), File.read_binary!("torn") == data}))\n'
  '    DiskStore.put(torn, "after", "tear")\n'
  '    DiskStore.close(torn)\n'
  '    ok(again) = DiskStore.open("torn")\n'
  '    IO.puts(inspect(DiskStore.get(again, "after")))\n'
  '    DiskStore.close(again)\n'
  '    ok(u) = DiskStore.open("shared")\n'
  '    workers = Enum.map(1..20, fn i -> Task.async(fn ->\n'
  '      DiskStore.update(u, "count", fn(held: option[string]): option[string] do\n'
  '        Process.sleep(1)\n'
  '        case held do\n'
  '          some(n) -> some(Integer.to_string(String.to_integer(n) + 1))\n'
  '          none -> some("1")\n'
  '        end\n'
  '      end)\n'
  '    end) end)\n'
  '    for w <- workers do Task.await(w, 5000) end\n'
  '    IO.puts(inspect(DiskStore.get(u, "count")))\n'
  '    slow = Task.async(fn -> DiskStore.update(u, "slow", fn(held: option[string]): option[string] do\n'
  '      Process.sleep(100)\n'
  '      some("updated")\n'
  '    end) end)\n'
  '    Process.sleep(20)\n'
  '    IO.puts(inspect(DiskStore.get(u, "count")))\n'
  '    IO.puts(inspect(DiskStore.put(u, "other", "waited")))\n'
  '    IO.puts(inspect(DiskStore.get(u, "slow")))\n'
  '    IO.puts(inspect(Task.await(slow)))\n'
  '    IO.puts(inspect(DiskStore.close(u)))\n'
  '    IO.puts(inspect(DiskStore.keys(u)))\n'
  '  end\n'
  'end\n',
  2,
  b'{500, true, ["k102", "k105", "k108", "k109", "k11"], 54, 53}\n{250, ["k102", "k105", "k108"]}\nok({})\n'
  b'{12320, 4486}\n{250, none, some("300")}\n["", "a", "a\\x00b", "\\xfe\\xff", "\\xff", "\\xff\\xff"]\n['
  b'{"\\xff", "high"}, {"\\xff\\xff", "higher"}]\n[{"\\xfe\\xff", "x"}]\n[{"a", ""}, {"a\\x00b", "nul"}]\n[{"'
  b'", "empty key"}, {"a", ""}, {"a\\x00b", "nul"}]\nsome("empty key")\ntrue\n{7, true, some("nul")}\n{true, '
  b'true}\n{250, true}\nsome("tear")\nsome("20")\nsome("20")\nok({})\nsome("updated")\nok(some("updated"))\n'
  b'true\n',
  b'<stdin>:66:21: DiskStore.keys: the store is closed\n  at Main.main (<stdin>:66)\n')]
# the same, for programs that need ::1
SIX=[]
# programs of the library's own functions, as the self-hosted compiler runs them
OWN=[]
# programs the pinned compiler rejects
REJECTS=['defmodule Main do\n'
 '  def main() do\n'
 '    ok(s) = DiskStore.open("x")\n'
 '    DiskStore.commit(s, [{"a", "b"}])\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n'
 '  def main() do\n'
 '    ok(s) = DiskStore.open("x")\n'
 '    IO.puts(inspect(s == s))\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n  def main() do\n    DiskStore.keys("x")\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    DiskStore.open(1)\n  end\nend\n',
 'defmodule Main do\n'
 '  def main() do\n'
 '    ok(s) = DiskStore.open("x")\n'
 '    DiskStore.put(s, "k", 1)\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n  def main() do\n    ok(s) = DiskStore.open("x")\n    TCP.close(s)\n  end\nend\n',
 'defmodule Main do\n'
 '  def main() do\n'
 '    ok(s) = DiskStore.open("x")\n'
 '    DiskStore.update(s, "k", fn(v: string): string do v end)\n'
 '  end\n'
 'end\n']


def loopback6():
    try:
        with socket.socket(socket.AF_INET6,socket.SOCK_STREAM) as s:s.bind(('::1',0))
        return True
    except OSError:return False


def run(compiler,source,base,number):
    """The program's status, output and errors. It runs in an empty directory
    that is also its TMPDIR, in a session of its own that is killed whole."""
    built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
    assert (built.returncode,built.stderr)==(0,b''),(source,built.returncode,built.stderr)
    program=Path(base)/f'p{number}';program.write_bytes(built.stdout);program.chmod(0o700)
    directory=Path(base)/f'd{number}';directory.mkdir(0o700)
    bounds=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),ALCHEM_SECONDS='60',ALCHEM_MEMORY='3G',TMPDIR=str(directory))
    for name in ('XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'):
        if name in os.environ:bounds[name]=os.environ[name]
    process=subprocess.Popen([str(ROOT/'scripts/limited'),str(program)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=bounds,cwd=directory,start_new_session=True)
    try:out,err=process.communicate(timeout=120)
    finally:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait()
    return process.returncode,out,err


def verify(compiler):
    six=len(SIX) if loopback6() else 0
    todo=RUNS+(SIX if six else [])+OWN
    with tempfile.TemporaryDirectory(prefix='alchem-diskstore-') as base:
        with ThreadPoolExecutor(6) as pool:
            got=list(pool.map(lambda item:run(compiler,item[1][0],base,item[0]),enumerate(todo)))
        for (source,status,stdout,stderr),result in zip(todo,got):
            assert result==(status,stdout,stderr),(source,result,(status,stdout,stderr))
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    if SIX and not six:print(f'SKIP {len(SIX)} programs that need ::1')
    print(f'PASS diskstore: {len(RUNS)} programs run as the pinned compiler runs them (the 13 examples of the library reference among them), {len(REJECTS)} rejected; the log on disk byte for byte, torn tails, compaction, updates of several processes')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
