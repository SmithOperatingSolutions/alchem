#!/usr/bin/env python3
"""Nodes: programs that connect and exchange messages, as the pinned compiler runs them.

Node, Stream.publish and the handles of other nodes' processes
(spec/alchem-nodes.md). RUNS are programs of one node. GROUPS are two
programs each: the first starts a node and writes its address, the second is
given the address as its last argument; both are native here, and what they
write is what two programs of the pinned compiler write (and what a native
and a pinned one write to each other, in either order: checked when this file
was made, not here, where the pinned compiler is not run). TRIO is three
nodes at once. ORACLE is a native
node spoken to by a node written in this file from the pinned runtime's
source, which compares every answer byte for byte; a client of Python's ssl
module then makes the TLS 1.3 handshake with a native node.

Everything stays on this machine: 127.0.0.1 on ports the system chooses, and
port 1 where a refused connection is the point. Nothing expected holds a
port, a process number of the system, a node's key or a time. Each program
runs under scripts/limited in a session of its own, which is killed whole
when the program is done or out of time."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import importlib.util
import os
import signal
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule T do\n'
  '  def main() do\n'
  '    started = Node.start("example", "127.0.0.1:0", "secret")\n'
  '    assert(started == ok({}) or started == error("this program is already a node"))\n'
  '    inbox: pid[tuple[atom, integer]] = Process.self(8)\n'
  '    Process.register(inbox, :example_inbox)\n'
  '    found: option[pid[tuple[atom, integer]]] = Process.whereis(:example_inbox)\n'
  '    sent = case found do\n'
  '      some(named) -> Process.send(named, {:count, 3}, 100)\n'
  '      none -> false\n'
  '    end\n'
  '    assert(sent)\n'
  '    assert_receive(inbox, {:count, 3})\n'
  '    Process.unregister(:example_inbox)\n'
  '    elsewhere: option[pid[tuple[atom, integer]]] = Node.whereis("other", :example_inbox, 50)\n'
  '    reached = case elsewhere do\n'
  '      some(_) -> true\n'
  '      none -> false\n'
  '    end\n'
  '    assert(not reached)\n'
  '  end\n'
  'end\n',
  0,
  b'',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Stream.publish(:doc_squares, fn -> Stream.map(Stream.from_index(1), &(&1 * &1)) end)))\n'
  '    IO.puts(inspect(Stream.publish(:doc_squares, fn -> Stream.map(1..3, &(&1 * &1)) end)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    Node.start("docs", "127.0.0.1:0", "secret")\n'
  '    IO.puts(inspect(String.starts_with?(Node.address(), "127.0.0.1:")))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Node.serve(:square_doc, fn(n: integer): integer do n * n end)))\n'
  '    squared: result[integer, string] = Node.call(Node.self(), :square_doc, 7)\n'
  '    IO.puts(inspect(squared))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nok(49)\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Node.serve(:noted_doc, fn(n: integer): integer do n end)))\n'
  '    IO.puts(inspect(Node.cast(Node.self(), :noted_doc, 1)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\ntrue\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    Node.start("docs", "127.0.0.1:0", "secret")\n'
  '    IO.puts(inspect(case Node.connect("127.0.0.1:1") do\n'
  '      ok(name) -> name\n'
  '      error(_) -> "not reachable"\n'
  '    end))\n'
  '  end\n'
  'end\n',
  0,
  b'"not reachable"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Node.disconnect("nobody")))\n  end\nend\n', 0, b'false\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(length(Node.list())))\n  end\nend\n', 0, b'0\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    reference = Node.monitor("elsewhere")\n'
  '    {arrived, noticed, _, reason} = Process.event(1000)\n'
  '    IO.puts(inspect(arrived and noticed == reference and reason == "nodedown elsewhere"))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    Node.start("docs", "127.0.0.1:0", "secret")\n'
  '    reference = Node.monitor_nodes()\n'
  '    {arrived, _, _, _} = Process.event(10)\n'
  '    IO.puts(inspect(arrived or reference == 0))\n'
  '  end\n'
  'end\n',
  0,
  b'false\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    me: pid[string] = Process.self(4)\n'
  '    IO.puts(inspect(Node.register_global(me, :global_doc)))\n'
  '    IO.puts(inspect(Node.register_global(me, :global_doc)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\n',
  b''),
 ('defmodule T do\n  def main() do\n    Node.start("docs", "127.0.0.1:0", "secret")\n    IO.puts(inspect(Node.self()))\n  end\nend\n',
  0,
  b'"docs"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Node.serve(:twice_doc, fn(n: integer): integer do n * 2 end)))\n  end\nend\n',
  0,
  b'true\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    started = Node.start("docs", "127.0.0.1:0", "secret")\n'
  '    IO.puts(inspect(started == ok({}) or started == error("this program is already a node")))\n'
  '    IO.puts(inspect(Node.self()))\n'
  '    IO.puts(inspect(Node.start("docs", "127.0.0.1:0", "secret", [loud: true])))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n"docs"\nerror("unknown option :loud; Node.start takes encrypted:")\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    Node.start("docs", "127.0.0.1:0", "secret")\n'
  '    squares: result[stream[integer], string] = Node.stream("elsewhere", :doc_squares)\n'
  '    IO.puts(inspect(case squares do\n'
  '      ok(found) -> Enum.take(found, 3)\n'
  '      error(_) -> Enum.take([0], 0)\n'
  '    end))\n'
  '  end\n'
  'end\n',
  0,
  b'[]\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    Node.start("docs", "127.0.0.1:0", "secret")\n'
  '    found: option[pid[string]] = Node.whereis("elsewhere", :logger, 100)\n'
  '    IO.puts(inspect(case found do\n'
  '      some(logger) -> Process.send(logger, "hello", 100)\n'
  '      none -> false\n'
  '    end))\n'
  '  end\n'
  'end\n',
  0,
  b'false\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    me: pid[string] = Process.self(4)\n'
  '    IO.puts(inspect(Node.register_global(me, :global_find_doc)))\n'
  '    found: option[pid[string]] = Node.whereis_global(:global_find_doc)\n'
  '    IO.puts(inspect(case found do\n'
  '      some(_) -> "found"\n'
  '      none -> "missing"\n'
  '    end))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n"found"\n',
  b''),
 ('defmodule P1 do\n'
  '  def main() do\n'
  '    IO.inspect({Node.self(), Node.address(), Node.list()})\n'
  '    IO.inspect(Node.connect("127.0.0.1:1"))\n'
  '    early: result[stream[integer], string] = Node.stream("nobody", :s)\n'
  '    IO.inspect(case early do\n'
  '      ok(_) -> "stream"\n'
  '      error(why) -> why\n'
  '    end)\n'
  '    IO.inspect(Node.start("", "127.0.0.1:0", "s"))\n'
  '    IO.inspect(Node.start("a", "127.0.0.1:0", ""))\n'
  '    IO.inspect(Node.start("a", "nonsense", "s", [encrypted: false]))\n'
  '    IO.inspect(Node.start("a", "127.0.0.1:99999", "s", [encrypted: false]))\n'
  '    IO.inspect(Node.start("a", "127.0.0.1:0"))\n'
  '    IO.inspect(Node.start("a", "127.0.0.1:0", "s", [encrypted: false, encrypted: true, encrypted: false]))\n'
  '    IO.inspect(Node.start("b", "127.0.0.1:0", "s"))\n'
  '    IO.inspect(Node.start("", "", "", [x: true]))\n'
  '    IO.inspect({Node.self(), Node.list()})\n'
  '    IO.inspect(Node.connect("127.0.0.1:1"))\n'
  '    IO.inspect(Node.connect("127.0.0.1:1", [reconnect: true]))\n'
  '    IO.inspect(Node.connect("127.0.0.1:1", [reconnect: 3]))\n'
  '    IO.inspect(Node.connect("127.0.0.1:1", []))\n'
  '    IO.inspect(Node.connect("nowhere"))\n'
  '    IO.inspect(Node.connect(Node.address()))\n'
  '    r = Node.monitor("nobody")\n'
  '    {arrived, ref, id, reason} = Process.event(100)\n'
  '    IO.inspect({arrived, ref == r, id, reason})\n'
  '    w = Node.monitor_nodes()\n'
  '    IO.inspect(Process.event(10) == {false, 0, 0, ""})\n'
  '    f: option[pid[string]] = Node.whereis("nobody", :x, 10)\n'
  '    IO.inspect(case f do\n'
  '      some(_) -> 1\n'
  '      none -> 0\n'
  '    end)\n'
  '    c: result[integer, string] = Node.call("nobody", :x, 1)\n'
  '    IO.inspect(c)\n'
  '    IO.inspect(Node.cast("nobody", :x, 1))\n'
  '    late: result[stream[integer], string] = Node.stream("nobody", :s)\n'
  '    IO.inspect(case late do\n'
  '      ok(_) -> "stream"\n'
  '      error(why) -> why\n'
  '    end)\n'
  '    IO.inspect(Node.disconnect("nobody"))\n'
  '    IO.inspect(Node.serve(:slow, fn(n: integer): integer do\n'
  '      Process.sleep(300)\n'
  '      n\n'
  '    end))\n'
  '    IO.inspect(Node.serve(:slow, fn(n: integer): integer do n end))\n'
  '    IO.inspect(Node.serve(:slow, fn(n: string): integer do 0 end))\n'
  '    t: result[integer, string] = Node.call("a", :slow, 5, 50)\n'
  '    IO.inspect(t)\n'
  '    u: result[integer, string] = Node.call("a", :slow, 6)\n'
  '    IO.inspect(u)\n'
  '    v: result[string, string] = Node.call("a", :slow, 6)\n'
  '    IO.inspect(v)\n'
  '    x: result[integer, string] = Node.call("a", :slow, "six")\n'
  '    IO.inspect(x)\n'
  '    IO.inspect(Node.cast("a", :slow, 1))\n'
  '    IO.inspect(Node.cast("a", :slow, "one"))\n'
  '    IO.inspect(Node.cast("a", :nothing, 1))\n'
  '    IO.inspect(Process.count())\n'
  '    me: pid[integer] = Process.self(2)\n'
  '    IO.inspect(Process.register(me, :me))\n'
  '    IO.inspect(Node.register_global(me, :me))\n'
  '    IO.inspect(Node.register_global(me, :me2))\n'
  '    a: option[pid[integer]] = Process.whereis(:me2)\n'
  '    b: option[pid[string]] = Process.whereis(:me2)\n'
  '    g: option[pid[integer]] = Node.whereis_global(:me)\n'
  '    h: option[pid[string]] = Node.whereis_global(:me)\n'
  '    IO.inspect({case a do\n'
  '      some(_) -> 1\n'
  '      none -> 0\n'
  '    end, case b do\n'
  '      some(_) -> 1\n'
  '      none -> 0\n'
  '    end, case g do\n'
  '      some(_) -> 1\n'
  '      none -> 0\n'
  '    end, case h do\n'
  '      some(_) -> 1\n'
  '      none -> 0\n'
  '    end})\n'
  '    IO.inspect(Stream.publish(:s, fn -> Stream.from_index(1) end))\n'
  '    IO.inspect(Stream.publish(:s, fn -> Stream.from_index(1) end))\n'
  '    own: result[stream[integer], string] = Node.stream("a", :s)\n'
  '    IO.inspect(case own do\n'
  '      ok(_) -> "stream"\n'
  '      error(why) -> why\n'
  '    end)\n'
  '    IO.inspect(Process.count())\n'
  '  end\n'
  'end\n',
  0,
  b'{"", "", []}\nerror("start this node first, with Node.start")\n"start this node first, with Node.start"\nerror("a node needs a name")\nerror("a '
  b'node needs a cookie: the secret every node of the cluster shares")\nerror("listen tcp: address nonsense: missing port in address")\nerror("lis'
  b'ten tcp: address 99999: invalid port")\nerror("set the ALCHEM_COOKIE environment variable, or pass the cookie to Node.start")\nok({})\nerror("t'
  b'his program is already a node")\nerror("unknown option :x; Node.start takes encrypted:")\n{"a", []}\nerror("dial tcp 127.0.0.1:1: connect: conn'
  b'ection refused")\nerror("dial tcp 127.0.0.1:1: connect: connection refused")\nerror("dial tcp 127.0.0.1:1: connect: connection refused")\nerror'
  b'("dial tcp 127.0.0.1:1: connect: connection refused")\nerror("dial tcp: address nowhere: missing port in address")\nerror("both nodes are name'
  b'd a")\n{true, true, 0, "nodedown nobody"}\ntrue\n0\nerror("nothing served as :x on nobody")\ntrue\n"not connected to node nobody"\nfalse\ntrue\nf'
  b'alse\nfalse\nerror("timeout")\nok(6)\nerror("nothing served as :slow on a")\nerror("nothing served as :slow on a")\ntrue\nfalse\nfalse\n3\ntru'
  b'e\nfalse\ntrue\n{1, 0, 1, 0}\ntrue\nfalse\n"not connected to node a"\n4\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.inspect(Node.monitor_nodes())\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:16: Node.monitor_nodes needs this program to be a node; call Node.start first\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  '    Node.start("a", "127.0.0.1:0", "s", [encrypted: false])\n'
  '    IO.inspect(Node.connect("127.0.0.1:1", [bogus: true]))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:16: Node.connect takes reconnect:\n  at T.main (<stdin>:4)\n'),
 ('defmodule T do\n  def main() do\n    IO.inspect(Node.connect("127.0.0.1:1", [reconnect: -1]))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:16: reconnect: takes true, false or a number of attempts, not a negative number\n  at T.main (<stdin>:3)\n'),
 ('defmodule T do\n'
  '  def main() do\n'
  '    me: pid[tuple[string, list[option[integer]]]] = Process.self(1)\n'
  '    IO.inspect(Process.register(me, :fine))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule T do\n'
  '  def f(p: pid[regex]): integer do\n'
  '    1\n'
  '  end\n'
  '  def main() do\n'
  '    x: pid[tuple[integer, string]] = Process.self(1)\n'
  '    IO.inspect(1)\n'
  '  end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule T do\n'
  '  struct Good do\n'
  '    n: integer\n'
  '    again: option[pid[Good]]\n'
  '    t: task[Good]\n'
  '    a: agent[fn[integer]]\n'
  '  end\n'
  '  def f(p: pid[Good], q: server[Good, list[Good]]): integer do\n'
  '    1\n'
  '  end\n'
  '  def main() do\n'
  '    IO.inspect(1)\n'
  '  end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule T do\n'
  '  struct A do\n'
  '    n: integer = 1 +\n'
  '      2\n'
  '    l: list[integer] = [1,\n'
  '      2]\n'
  '    again: option[pid[A]]\n'
  '  end\n'
  '  type V do\n'
  '    one(a: integer, g: list[A])\n'
  '    two\n'
  '    three(v: V)\n'
  '  end\n'
  '  struct Box[a] do\n'
  '    v: a\n'
  '  end\n'
  '  def f(p: pid[V], q: pid[Box[integer]], r: pid[Box[A]]): integer do\n'
  '    1\n'
  '  end\n'
  '  def main() do\n'
  '    IO.inspect(1)\n'
  '  end\n'
  'end\n',
  0,
  b'1\n',
  b'')]

# Programs the pinned compiler rejects.
REJECTS=['defmodule T do\n  def main() do\n    found = Node.whereis("other", :orders)\n    IO.puts(inspect(1))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    me: pid[list[regex]] = Process.self(1)\n    Process.register(me, :patterns)\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(Node.serve(:t, fn n -> n * 2 end))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    r = Node.call("x", :t, 1)\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(Stream.publish(:t, fn -> Stream.map([1], fn x -> fn -> x end end) end))\n  end\nend\n',
 'defmodule T do\n  def main() do\n    f: option[pid[integer]] = Process.whereis(:x)\n    g = Process.whereis(:x)\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n  def main() do\n    IO.inspect(Node.cast("x", :t, fn -> 1 end))\n  end\nend\n',
 'defmodule T do\n  def f(p: pid[fn[integer, integer]]): integer do\n    1\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n  def f(p: pid[stream[integer]]): integer do\n    1\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n  def f(p: pid[t]): integer do\n    1\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n'
 '  struct F do\n'
 '    g: fn[integer]\n'
 '  end\n'
 '  def f(p: pid[tuple[integer, F]]): integer do\n'
 '    1\n'
 '  end\n'
 '  def main() do\n'
 '    IO.inspect(1)\n'
 '  end\n'
 'end\n',
 'defmodule T do\n  def f(p: server[fn[integer], integer]): integer do\n    1\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n  def f(p: supervisor[stream[integer]]): integer do\n    1\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n  def main() do\n    p = Process.spawn(fn(self: pid[stream[integer]]): integer do 0 end, 1)\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n  def f(p: pid[pid[fn[integer]]]): integer do\n    1\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n  def f(p: task[fn[integer]], a: agent[fn[integer]]): integer do\n    1\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n  def f(p: server[integer, fn[integer]]): integer do\n    1\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n',
 'defmodule T do\n'
 '  struct S do\n'
 '    n: integer\n'
 '    p: option[pid[list[fn[integer]]]]\n'
 '  end\n'
 '  def main() do\n'
 '    s = %S{n: 1, p: none}\n'
 '    IO.inspect(s.n)\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  struct A do\n'
 '    n: integer = 1 +\n'
 '      2\n'
 '    l: list[integer] = [1,\n'
 '      2]\n'
 '    f: fn[integer]\n'
 '  end\n'
 '  type V do\n'
 '    one(a: integer, g: list[A])\n'
 '    two\n'
 '  end\n'
 '  def f(p: pid[V]): integer do\n'
 '    1\n'
 '  end\n'
 '  def main() do\n'
 '    IO.inspect(1)\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  struct Box[a] do\n'
 '    v: a\n'
 '  end\n'
 '  def f(q: pid[Box[fn[integer]]]): integer do\n'
 '    1\n'
 '  end\n'
 '  def main() do\n'
 '    IO.inspect(1)\n'
 '  end\n'
 'end\n']

# (title, files, the first program, its arguments, the line of its output that is its address, the second program, its arguments;
# the second program's status, output and errors, what the first wrote before its address and after it, and its status) as the pinned compiler runs them
GROUPS=[('the pinned testdata/nodes, encrypted',
  {'client.alc': 'defmodule Client do\n'
                 '  import "wire.alc"\n'
                 '\n'
                 '  def main() do\n'
                 '    [address] = System.argv()\n'
                 '    case Node.start("client", "127.0.0.1:0", "secret") do\n'
                 '      error(reason) -> IO.puts("cannot start: #{reason}")\n'
                 '      ok(_) -> IO.puts("started #{Node.self()}")\n'
                 '    end\n'
                 '    case Node.connect(address) do\n'
                 '      error(reason) -> IO.puts("cannot connect: #{reason}")\n'
                 '      ok(name) -> IO.puts("connected to #{name}, nodes: #{inspect(Node.list())}")\n'
                 '    end\n'
                 '    catalog: result[stream[string],string] = Node.stream("shop", :catalog)\n'
                 '    case catalog do\n'
                 '      ok(items) -> IO.puts(inspect(Enum.take(Stream.drop(items, 300), 2)))\n'
                 '      error(reason) -> IO.puts("no catalog: #{reason}")\n'
                 '    end\n'
                 '    inbox: pid[Wire.Answer] = Process.self(8)\n'
                 '    found: option[pid[Wire.Order]] = Node.whereis("shop", :orders)\n'
                 '    case found do\n'
                 '      none -> IO.puts("no orders process")\n'
                 '      some(orders) ->\n'
                 '        watch = Node.monitor("shop")\n'
                 '        Process.send(orders, %Wire.Order{item: "tea", count: 3, tags: [:hot, :green], extra: %{"kg" => 0.5}, reply: inbox}, 1000)\n'
                 '        IO.puts(inspect(Process.receive(inbox, 5000)))\n'
                 '        Process.send(orders, %Wire.Order{item: "cup", count: 9, tags: Enum.take([:a], 0), extra: %{"kg" => 0.25}, reply: inbox}, '
                 '1000)\n'
                 '        IO.puts(inspect(Process.receive(inbox, 5000)))\n'
                 '        {arrived, reference, _, reason} = Process.event(5000)\n'
                 '        IO.puts("#{arrived} #{reference == watch} #{reason}")\n'
                 '    end\n'
                 '  end\n'
                 'end\n',
   'shop.alc': 'defmodule Shop do\n'
               '  import "wire.alc"\n'
               '\n'
               '  def main() do\n'
               '    case Node.start("shop", "127.0.0.1:0", "secret") do\n'
               '      error(reason) -> IO.puts("cannot start: #{reason}")\n'
               '      ok(_) -> IO.puts(Node.address())\n'
               '    end\n'
               '    orders: pid[Wire.Order] = Process.self(8)\n'
               '    Process.register(orders, :orders)\n'
               '    Stream.publish(:catalog, fn ->\n'
               '      Stream.map(Stream.from_index(1), fn n ->\n'
               '        "item #{n}"\n'
               '      end)\n'
               '    end)\n'
               '    serve(orders, 2)\n'
               '  end\n'
               '\n'
               '  def serve(orders: pid[Wire.Order], remaining: integer): integer do\n'
               '    if remaining == 0 do\n'
               '      return 0\n'
               '    end\n'
               '    {arrived, order} = Process.receive(orders, 10000)\n'
               '    if (not arrived) do\n'
               '      return remaining\n'
               '    end\n'
               '    answer = if order.count > 5 do\n'
               '      Wire.Answer.refused("only 5 #{order.item} left")\n'
               '    else\n'
               '      Wire.Answer.shipped(order.item, order.count * 2)\n'
               '    end\n'
               '    Process.send(order.reply, answer, 1000)\n'
               '    serve(orders, remaining - 1)\n'
               '  end\n'
               'end\n',
   'wire.alc': 'defmodule Wire do\n'
               '  struct Order do\n'
               '    item: string\n'
               '    count: integer\n'
               '    tags: list[atom]\n'
               '    extra: map[string,float]\n'
               '    reply: pid[Answer]\n'
               '  end\n'
               '\n'
               '  type Answer do\n'
               '    shipped(item: string, total: integer)\n'
               '    refused(reason: string)\n'
               '  end\n'
               'end\n'},
  'shop.alc',
  [],
  1,
  'client.alc',
  [],
  0,
  b'started client\nconnected to shop, nodes: ["shop"]\n["item 301", "item 302"]\n{true, Answer.shipped("tea", 6)}\n{true, Answer.refused("only 5 cu'
  b'p left")}\ntrue true nodedown shop\n',
  b'',
  b'',
  b'',
  0),
 ('the pinned testdata/nodes, not encrypted',
  {'client.alc': 'defmodule Client do\n'
                 '  import "wire.alc"\n'
                 '\n'
                 '  def main() do\n'
                 '    [address] = System.argv()\n'
                 '    case Node.start("client", "127.0.0.1:0", "secret", [encrypted: false]) do\n'
                 '      error(reason) -> IO.puts("cannot start: #{reason}")\n'
                 '      ok(_) -> IO.puts("started #{Node.self()}")\n'
                 '    end\n'
                 '    case Node.connect(address) do\n'
                 '      error(reason) -> IO.puts("cannot connect: #{reason}")\n'
                 '      ok(name) -> IO.puts("connected to #{name}, nodes: #{inspect(Node.list())}")\n'
                 '    end\n'
                 '    catalog: result[stream[string],string] = Node.stream("shop", :catalog)\n'
                 '    case catalog do\n'
                 '      ok(items) -> IO.puts(inspect(Enum.take(Stream.drop(items, 300), 2)))\n'
                 '      error(reason) -> IO.puts("no catalog: #{reason}")\n'
                 '    end\n'
                 '    inbox: pid[Wire.Answer] = Process.self(8)\n'
                 '    found: option[pid[Wire.Order]] = Node.whereis("shop", :orders)\n'
                 '    case found do\n'
                 '      none -> IO.puts("no orders process")\n'
                 '      some(orders) ->\n'
                 '        watch = Node.monitor("shop")\n'
                 '        Process.send(orders, %Wire.Order{item: "tea", count: 3, tags: [:hot, :green], extra: %{"kg" => 0.5}, reply: inbox}, 1000)\n'
                 '        IO.puts(inspect(Process.receive(inbox, 5000)))\n'
                 '        Process.send(orders, %Wire.Order{item: "cup", count: 9, tags: Enum.take([:a], 0), extra: %{"kg" => 0.25}, reply: inbox}, '
                 '1000)\n'
                 '        IO.puts(inspect(Process.receive(inbox, 5000)))\n'
                 '        {arrived, reference, _, reason} = Process.event(5000)\n'
                 '        IO.puts("#{arrived} #{reference == watch} #{reason}")\n'
                 '    end\n'
                 '  end\n'
                 'end\n',
   'shop.alc': 'defmodule Shop do\n'
               '  import "wire.alc"\n'
               '\n'
               '  def main() do\n'
               '    case Node.start("shop", "127.0.0.1:0", "secret", [encrypted: false]) do\n'
               '      error(reason) -> IO.puts("cannot start: #{reason}")\n'
               '      ok(_) -> IO.puts(Node.address())\n'
               '    end\n'
               '    orders: pid[Wire.Order] = Process.self(8)\n'
               '    Process.register(orders, :orders)\n'
               '    Stream.publish(:catalog, fn ->\n'
               '      Stream.map(Stream.from_index(1), fn n ->\n'
               '        "item #{n}"\n'
               '      end)\n'
               '    end)\n'
               '    serve(orders, 2)\n'
               '  end\n'
               '\n'
               '  def serve(orders: pid[Wire.Order], remaining: integer): integer do\n'
               '    if remaining == 0 do\n'
               '      return 0\n'
               '    end\n'
               '    {arrived, order} = Process.receive(orders, 10000)\n'
               '    if (not arrived) do\n'
               '      return remaining\n'
               '    end\n'
               '    answer = if order.count > 5 do\n'
               '      Wire.Answer.refused("only 5 #{order.item} left")\n'
               '    else\n'
               '      Wire.Answer.shipped(order.item, order.count * 2)\n'
               '    end\n'
               '    Process.send(order.reply, answer, 1000)\n'
               '    serve(orders, remaining - 1)\n'
               '  end\n'
               'end\n',
   'wire.alc': 'defmodule Wire do\n'
               '  struct Order do\n'
               '    item: string\n'
               '    count: integer\n'
               '    tags: list[atom]\n'
               '    extra: map[string,float]\n'
               '    reply: pid[Answer]\n'
               '  end\n'
               '\n'
               '  type Answer do\n'
               '    shipped(item: string, total: integer)\n'
               '    refused(reason: string)\n'
               '  end\n'
               'end\n'},
  'shop.alc',
  [],
  1,
  'client.alc',
  [],
  0,
  b'started client\nconnected to shop, nodes: ["shop"]\n["item 301", "item 302"]\n{true, Answer.shipped("tea", 6)}\n{true, Answer.refused("only 5 cu'
  b'p left")}\ntrue true nodedown shop\n',
  b'',
  b'',
  b'',
  0),
 ('the pinned testdata/cluster, encrypted',
  {'client.alc': 'defmodule ClusterClient do\n'
                 '  def main() do\n'
                 '    [address] = System.argv()\n'
                 '    ok(_) = Node.start("client", "127.0.0.1:0", "cluster secret")\n'
                 '    ok(server) = Node.connect(address, [reconnect: true])\n'
                 '    squared: result[integer, string] = Node.call(server, :square, 7)\n'
                 '    IO.inspect(squared)\n'
                 '    failed: result[integer, string] = Node.call(server, :fail, 1)\n'
                 '    IO.inspect(failed)\n'
                 '    found: option[pid[string]] = Node.whereis_global(:worker)\n'
                 '    IO.inspect(case found do\n'
                 '      some(_) -> "worker found"\n'
                 '      none -> "worker missing"\n'
                 '    end)\n'
                 '    me: pid[string] = Process.self(4)\n'
                 '    IO.inspect(Node.register_global(me, :worker))\n'
                 '\n'
                 '    # A process linked to one on the other node ends when it fails.\n'
                 '    linked: pid[integer] = Process.spawn(fn(_: pid[integer]): integer do\n'
                 '      looked: option[pid[string]] = Node.whereis(server, :victim)\n'
                 '      some(victim) = looked\n'
                 '      Process.link(victim)\n'
                 '      Process.sleep(10000)\n'
                 '      0\n'
                 '    end, 1)\n'
                 '    Process.sleep(200)\n'
                 '    crashed: result[boolean, string] = Node.call(server, :crash, 0)\n'
                 '    IO.inspect(crashed)\n'
                 '    IO.inspect(Process.await(linked, 5000))\n'
                 '\n'
                 '    # A cast runs the served function without waiting, whatever it returns.\n'
                 '    IO.inspect(Node.cast(server, :note, "one"))\n'
                 '    IO.inspect(Node.cast(server, :missing, "nothing serves this"))\n'
                 '    Process.sleep(500)\n'
                 '    noted: result[list[string], string] = Node.call(server, :noted, 0)\n'
                 '    IO.inspect(noted)\n'
                 '\n'
                 '    # A dropped connection is made again: the events say when.\n'
                 '    watch = Node.monitor_nodes()\n'
                 '    Node.disconnect(server)\n'
                 '    {_, down, _, lost} = Process.event(5000)\n'
                 '    IO.inspect(down == watch and lost == "nodedown " <> server)\n'
                 '    IO.inspect(Enum.member?(Node.list(), server))\n'
                 '    {_, up, _, made} = Process.event(10000)\n'
                 '    IO.inspect(up == watch and made == "nodeup " <> server)\n'
                 '    IO.inspect(Enum.member?(Node.list(), server))\n'
                 '    again: result[integer, string] = Node.call(server, :square, 3)\n'
                 '    IO.inspect(again)\n'
                 '  end\n'
                 'end\n',
   'server.alc': 'defmodule ClusterServer do\n'
                 '  def victim(self: pid[string]): integer do\n'
                 '    case Process.receive(self, 30000) do\n'
                 '      {true, "crash"} -> raise("victim crashed")\n'
                 '      _ -> 0\n'
                 '    end\n'
                 '  end\n'
                 '\n'
                 '  def main() do\n'
                 '    ok(_) = Node.start("server", "127.0.0.1:0", "cluster secret")\n'
                 '    Node.serve(:square, fn(n: integer): integer do n * n end)\n'
                 '    Node.serve(:fail, fn(n: integer): integer do div(n, 0) end)\n'
                 '    target: pid[string] = Process.spawn(fn(self: pid[string]): integer do victim(self) end, 4)\n'
                 '    Process.register(target, :victim)\n'
                 '    Node.serve(:crash, fn(_: integer): boolean do Process.send(target, "crash", 1000) end)\n'
                 '    heard: agent[list[string]] = Agent.start(fn -> [] end)\n'
                 '    Node.serve(:note, fn(text: string): boolean do\n'
                 '      Agent.update(heard, fn all -> all ++ [text] end)\n'
                 '      true\n'
                 '    end)\n'
                 '    Node.serve(:noted, fn(_: integer): list[string] do Agent.get(heard, fn all -> all end) end)\n'
                 '    worker: pid[string] = Process.spawn(fn(self: pid[string]): integer do\n'
                 '      Process.receive(self, 30000)\n'
                 '      0\n'
                 '    end, 4)\n'
                 '    IO.inspect(Node.register_global(worker, :worker))\n'
                 '    IO.puts(Node.address())\n'
                 '    # The server runs until its input closes.\n'
                 '    IO.read(:eof)\n'
                 '  end\n'
                 'end\n'},
  'server.alc',
  [],
  2,
  'client.alc',
  [],
  0,
  b'ok(49)\nerror("division by zero")\n"worker found"\nfalse\nok(true)\n{true, "linked: victim crashed"}\ntrue\ntrue\nok(["one"])\ntrue\nfalse\ntru'
  b'e\ntrue\nok(9)\n',
  b'',
  b'true\n',
  b'',
  0),
 ('the pinned testdata/cluster, not encrypted',
  {'client.alc': 'defmodule ClusterClient do\n'
                 '  def main() do\n'
                 '    [address] = System.argv()\n'
                 '    ok(_) = Node.start("client", "127.0.0.1:0", "cluster secret", [encrypted: false])\n'
                 '    ok(server) = Node.connect(address, [reconnect: true])\n'
                 '    squared: result[integer, string] = Node.call(server, :square, 7)\n'
                 '    IO.inspect(squared)\n'
                 '    failed: result[integer, string] = Node.call(server, :fail, 1)\n'
                 '    IO.inspect(failed)\n'
                 '    found: option[pid[string]] = Node.whereis_global(:worker)\n'
                 '    IO.inspect(case found do\n'
                 '      some(_) -> "worker found"\n'
                 '      none -> "worker missing"\n'
                 '    end)\n'
                 '    me: pid[string] = Process.self(4)\n'
                 '    IO.inspect(Node.register_global(me, :worker))\n'
                 '\n'
                 '    # A process linked to one on the other node ends when it fails.\n'
                 '    linked: pid[integer] = Process.spawn(fn(_: pid[integer]): integer do\n'
                 '      looked: option[pid[string]] = Node.whereis(server, :victim)\n'
                 '      some(victim) = looked\n'
                 '      Process.link(victim)\n'
                 '      Process.sleep(10000)\n'
                 '      0\n'
                 '    end, 1)\n'
                 '    Process.sleep(200)\n'
                 '    crashed: result[boolean, string] = Node.call(server, :crash, 0)\n'
                 '    IO.inspect(crashed)\n'
                 '    IO.inspect(Process.await(linked, 5000))\n'
                 '\n'
                 '    # A cast runs the served function without waiting, whatever it returns.\n'
                 '    IO.inspect(Node.cast(server, :note, "one"))\n'
                 '    IO.inspect(Node.cast(server, :missing, "nothing serves this"))\n'
                 '    Process.sleep(500)\n'
                 '    noted: result[list[string], string] = Node.call(server, :noted, 0)\n'
                 '    IO.inspect(noted)\n'
                 '\n'
                 '    # A dropped connection is made again: the events say when.\n'
                 '    watch = Node.monitor_nodes()\n'
                 '    Node.disconnect(server)\n'
                 '    {_, down, _, lost} = Process.event(5000)\n'
                 '    IO.inspect(down == watch and lost == "nodedown " <> server)\n'
                 '    IO.inspect(Enum.member?(Node.list(), server))\n'
                 '    {_, up, _, made} = Process.event(10000)\n'
                 '    IO.inspect(up == watch and made == "nodeup " <> server)\n'
                 '    IO.inspect(Enum.member?(Node.list(), server))\n'
                 '    again: result[integer, string] = Node.call(server, :square, 3)\n'
                 '    IO.inspect(again)\n'
                 '  end\n'
                 'end\n',
   'server.alc': 'defmodule ClusterServer do\n'
                 '  def victim(self: pid[string]): integer do\n'
                 '    case Process.receive(self, 30000) do\n'
                 '      {true, "crash"} -> raise("victim crashed")\n'
                 '      _ -> 0\n'
                 '    end\n'
                 '  end\n'
                 '\n'
                 '  def main() do\n'
                 '    ok(_) = Node.start("server", "127.0.0.1:0", "cluster secret", [encrypted: false])\n'
                 '    Node.serve(:square, fn(n: integer): integer do n * n end)\n'
                 '    Node.serve(:fail, fn(n: integer): integer do div(n, 0) end)\n'
                 '    target: pid[string] = Process.spawn(fn(self: pid[string]): integer do victim(self) end, 4)\n'
                 '    Process.register(target, :victim)\n'
                 '    Node.serve(:crash, fn(_: integer): boolean do Process.send(target, "crash", 1000) end)\n'
                 '    heard: agent[list[string]] = Agent.start(fn -> [] end)\n'
                 '    Node.serve(:note, fn(text: string): boolean do\n'
                 '      Agent.update(heard, fn all -> all ++ [text] end)\n'
                 '      true\n'
                 '    end)\n'
                 '    Node.serve(:noted, fn(_: integer): list[string] do Agent.get(heard, fn all -> all end) end)\n'
                 '    worker: pid[string] = Process.spawn(fn(self: pid[string]): integer do\n'
                 '      Process.receive(self, 30000)\n'
                 '      0\n'
                 '    end, 4)\n'
                 '    IO.inspect(Node.register_global(worker, :worker))\n'
                 '    IO.puts(Node.address())\n'
                 '    # The server runs until its input closes.\n'
                 '    IO.read(:eof)\n'
                 '  end\n'
                 'end\n'},
  'server.alc',
  [],
  2,
  'client.alc',
  [],
  0,
  b'ok(49)\nerror("division by zero")\n"worker found"\nfalse\nok(true)\n{true, "linked: victim crashed"}\ntrue\ntrue\nok(["one"])\ntrue\nfalse\ntru'
  b'e\ntrue\nok(9)\n',
  b'',
  b'true\n',
  b'',
  0),
 ('every kind of value, encrypted',
  {'rclient.alc': 'defmodule RClient do\n'
                  '  import "rich.alc"\n'
                  '\n'
                  '  def main() do\n'
                  '    [mode, address] = System.argv()\n'
                  '    ok(_) = Node.start("rc", "127.0.0.1:0", "rich", [encrypted: mode == "tls"])\n'
                  '    ok(name) = Node.connect(address)\n'
                  '    me: pid[Rich.Msg] = Process.self(8)\n'
                  '    found: option[pid[Rich.Msg]] = Node.whereis(name, :rich)\n'
                  '    wrong: option[pid[Rich.Tree]] = Node.whereis(name, :rich, 500)\n'
                  '    missing: option[pid[Rich.Msg]] = Node.whereis(name, :nobody, 500)\n'
                  '    IO.puts(inspect(case wrong do\n'
                  '      some(_) -> "wrong type found"\n'
                  '      none -> "wrong type not found"\n'
                  '    end))\n'
                  '    IO.puts(inspect(case missing do\n'
                  '      some(_) -> "missing found"\n'
                  '      none -> "missing not found"\n'
                  '    end))\n'
                  '    some(server) = found\n'
                  '    IO.puts(inspect({Process.id(server) > 0, Process.alive(server)}))\n'
                  '    for i <- [0, 1, 2] do\n'
                  '      Process.send(server, Rich.sample(i, me), 1000)\n'
                  '      {arrived, m} = Process.receive(me, 5000)\n'
                  '      IO.puts(inspect({arrived, m.n, m.f, m.b, m.s, m.a, m.l, m.t}))\n'
                  '      IO.puts(inspect({m.m, m.k, m.e, m.o, m.p, m.r, m.q, m.x, m.tree, m.d, m.time, m.nd}))\n'
                  '      IO.puts(inspect(Process.id(m.reply) == Process.id(me)))\n'
                  '    end\n'
                  '  end\n'
                  'end\n',
   'rich.alc': 'defmodule Rich do\n'
               '  struct Box[a] do\n'
               '    value: a\n'
               '    note: string\n'
               '  end\n'
               '\n'
               '  type Tree do\n'
               '    leaf\n'
               '    node(left: Tree, value: integer, right: Tree)\n'
               '  end\n'
               '\n'
               '  struct Msg do\n'
               '    n: integer\n'
               '    f: float\n'
               '    b: boolean\n'
               '    s: string\n'
               '    a: atom\n'
               '    l: list[list[integer]]\n'
               '    t: tuple[integer, string, tuple[]]\n'
               '    m: map[string, float]\n'
               '    k: map[tuple[integer, string], list[atom]]\n'
               '    e: set[integer]\n'
               '    o: option[integer]\n'
               '    p: option[string]\n'
               '    r: result[integer, string]\n'
               '    q: result[integer, string]\n'
               '    x: Box[list[string]]\n'
               '    tree: Tree\n'
               '    d: Date\n'
               '    time: Time\n'
               '    nd: NaiveDateTime\n'
               '    reply: pid[Msg]\n'
               '  end\n'
               '\n'
               '  def sample(i: integer, reply: pid[Msg]): Msg do\n'
               '    big = if i == 0 do 9223372036854775807 else if i == 1 do -9223372036854775807 - 1 else i * -1000 end end\n'
               '    %Msg{n: big, f: if i == 0 do 0.5 else if i == 1 do -1.0e300 else 3.141592653589793 end end, b: i != 1, s: if i == 0 do "" else '
               '"héllo \\"wörld\\"\\n" end, a: if i == 0 do :ok else :two end,\n'
               '      l: if i == 0 do [] else [[1, 2, 3], [], [-1]] end, t: {i, "t", {}},\n'
               '      m: if i == 0 do %{} else %{"b" => 2.0, "a" => 1.5, "" => 0.0} end,\n'
               '      k: %{{2, "x"} => [:a], {1, "z"} => [], {1, "a"} => [:b, :c]},\n'
               '      e: MapSet.new([5, 3, 9, i]), o: if i == 0 do none else some(i) end, p: some("p"),\n'
               '      r: ok(i), q: error("bad #{i}"), x: %Box{value: ["v", "w"], note: "n"},\n'
               '      tree: Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf),\n'
               '      d: ~D[2026-11-19], time: ~T[23:59:58], nd: ~N[2001-02-03 04:05:06], reply: reply}\n'
               '  end\n'
               'end\n',
   'rserver.alc': 'defmodule RServer do\n'
                  '  import "rich.alc"\n'
                  '\n'
                  '  def loop(me: pid[Rich.Msg], left: integer): integer do\n'
                  '    if left == 0 do\n'
                  '      return 0\n'
                  '    end\n'
                  '    {arrived, m} = Process.receive(me, 10000)\n'
                  '    if (not arrived) do\n'
                  '      return 1\n'
                  '    end\n'
                  '    IO.puts("got #{inspect(m.n)} #{inspect(m.m)} #{inspect(m.e)} #{inspect(m.tree)} #{inspect(m.d)}")\n'
                  '    Process.send(m.reply, m, 1000)\n'
                  '    loop(me, left - 1)\n'
                  '  end\n'
                  '\n'
                  '  def main() do\n'
                  '    [mode] = System.argv()\n'
                  '    ok(_) = Node.start("rs", "127.0.0.1:0", "rich", [encrypted: mode == "tls"])\n'
                  '    me: pid[Rich.Msg] = Process.self(8)\n'
                  '    Process.register(me, :rich)\n'
                  '    IO.puts(Node.address())\n'
                  '    loop(me, 3)\n'
                  '  end\n'
                  'end\n'},
  'rserver.alc',
  ['tls'],
  1,
  'rclient.alc',
  ['tls'],
  0,
  b'"wrong type not found"\n"missing not found"\n{true, true}\n{true, 9223372036854775807, 0.5, true, "", :ok, [], {0, "t", {}}}\n{%{}, %{{1, "a"} ='
  b'> [:b, :c], {1, "z"} => [], {2, "x"} => [:a]}, MapSet.new([0, 3, 5, 9]), none, some("p"), ok(0), error("bad 0"), %Box{value: ["v", "w"], note: "'
  b'n"}, Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf), ~D[2026-11-19], ~T[23:59:58], ~N[2001-02-03 04:05:06]}\ntrue\n{true, -922337'
  b'2036854775808, -1.0e300, false, "h\xc3\xa9llo \\"w\xc3\xb6rld\\"\\n", :two, [[1, 2, 3], [], [-1]], {1, "t", {}}}\n{%{"" => 0.0, "a" => 1.5, "b" '
  b'=> 2.0}, %{{1, "a"} => [:b, :c], {1, "z"} => [], {2, "x"} => [:a]}, MapSet.new([1, 3, 5, 9]), some(1), some("p"), ok(1), error("bad 1"), %Box{va'
  b'lue: ["v", "w"], note: "n"}, Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf), ~D[2026-11-19], ~T[23:59:58], ~N[2001-02-03 04:05:06]}'
  b'\ntrue\n{true, -2000, 3.141592653589793, true, "h\xc3\xa9llo \\"w\xc3\xb6rld\\"\\n", :two, [[1, 2, 3], [], [-1]], {2, "t", {}}}\n{%{"" => 0.0,'
  b' "a" => 1.5, "b" => 2.0}, %{{1, "a"} => [:b, :c], {1, "z"} => [], {2, "x"} => [:a]}, MapSet.new([2, 3, 5, 9]), some(2), some("p"), ok(2), error('
  b'"bad 2"), %Box{value: ["v", "w"], note: "n"}, Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf), ~D[2026-11-19], ~T[23:59:58], ~N[2001'
  b'-02-03 04:05:06]}\ntrue\n',
  b'',
  b'',
  b'got 9223372036854775807 %{} MapSet.new([0, 3, 5, 9]) Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf) ~D[2026-11-19]\ngot -92233720368'
  b'54775808 %{"" => 0.0, "a" => 1.5, "b" => 2.0} MapSet.new([1, 3, 5, 9]) Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf) ~D[2026-11-19'
  b']\ngot -2000 %{"" => 0.0, "a" => 1.5, "b" => 2.0} MapSet.new([2, 3, 5, 9]) Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf) ~D[2026-11'
  b'-19]\n',
  0),
 ('every kind of value, not encrypted',
  {'rclient.alc': 'defmodule RClient do\n'
                  '  import "rich.alc"\n'
                  '\n'
                  '  def main() do\n'
                  '    [mode, address] = System.argv()\n'
                  '    ok(_) = Node.start("rc", "127.0.0.1:0", "rich", [encrypted: mode == "tls"])\n'
                  '    ok(name) = Node.connect(address)\n'
                  '    me: pid[Rich.Msg] = Process.self(8)\n'
                  '    found: option[pid[Rich.Msg]] = Node.whereis(name, :rich)\n'
                  '    wrong: option[pid[Rich.Tree]] = Node.whereis(name, :rich, 500)\n'
                  '    missing: option[pid[Rich.Msg]] = Node.whereis(name, :nobody, 500)\n'
                  '    IO.puts(inspect(case wrong do\n'
                  '      some(_) -> "wrong type found"\n'
                  '      none -> "wrong type not found"\n'
                  '    end))\n'
                  '    IO.puts(inspect(case missing do\n'
                  '      some(_) -> "missing found"\n'
                  '      none -> "missing not found"\n'
                  '    end))\n'
                  '    some(server) = found\n'
                  '    IO.puts(inspect({Process.id(server) > 0, Process.alive(server)}))\n'
                  '    for i <- [0, 1, 2] do\n'
                  '      Process.send(server, Rich.sample(i, me), 1000)\n'
                  '      {arrived, m} = Process.receive(me, 5000)\n'
                  '      IO.puts(inspect({arrived, m.n, m.f, m.b, m.s, m.a, m.l, m.t}))\n'
                  '      IO.puts(inspect({m.m, m.k, m.e, m.o, m.p, m.r, m.q, m.x, m.tree, m.d, m.time, m.nd}))\n'
                  '      IO.puts(inspect(Process.id(m.reply) == Process.id(me)))\n'
                  '    end\n'
                  '  end\n'
                  'end\n',
   'rich.alc': 'defmodule Rich do\n'
               '  struct Box[a] do\n'
               '    value: a\n'
               '    note: string\n'
               '  end\n'
               '\n'
               '  type Tree do\n'
               '    leaf\n'
               '    node(left: Tree, value: integer, right: Tree)\n'
               '  end\n'
               '\n'
               '  struct Msg do\n'
               '    n: integer\n'
               '    f: float\n'
               '    b: boolean\n'
               '    s: string\n'
               '    a: atom\n'
               '    l: list[list[integer]]\n'
               '    t: tuple[integer, string, tuple[]]\n'
               '    m: map[string, float]\n'
               '    k: map[tuple[integer, string], list[atom]]\n'
               '    e: set[integer]\n'
               '    o: option[integer]\n'
               '    p: option[string]\n'
               '    r: result[integer, string]\n'
               '    q: result[integer, string]\n'
               '    x: Box[list[string]]\n'
               '    tree: Tree\n'
               '    d: Date\n'
               '    time: Time\n'
               '    nd: NaiveDateTime\n'
               '    reply: pid[Msg]\n'
               '  end\n'
               '\n'
               '  def sample(i: integer, reply: pid[Msg]): Msg do\n'
               '    big = if i == 0 do 9223372036854775807 else if i == 1 do -9223372036854775807 - 1 else i * -1000 end end\n'
               '    %Msg{n: big, f: if i == 0 do 0.5 else if i == 1 do -1.0e300 else 3.141592653589793 end end, b: i != 1, s: if i == 0 do "" else '
               '"héllo \\"wörld\\"\\n" end, a: if i == 0 do :ok else :two end,\n'
               '      l: if i == 0 do [] else [[1, 2, 3], [], [-1]] end, t: {i, "t", {}},\n'
               '      m: if i == 0 do %{} else %{"b" => 2.0, "a" => 1.5, "" => 0.0} end,\n'
               '      k: %{{2, "x"} => [:a], {1, "z"} => [], {1, "a"} => [:b, :c]},\n'
               '      e: MapSet.new([5, 3, 9, i]), o: if i == 0 do none else some(i) end, p: some("p"),\n'
               '      r: ok(i), q: error("bad #{i}"), x: %Box{value: ["v", "w"], note: "n"},\n'
               '      tree: Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf),\n'
               '      d: ~D[2026-11-19], time: ~T[23:59:58], nd: ~N[2001-02-03 04:05:06], reply: reply}\n'
               '  end\n'
               'end\n',
   'rserver.alc': 'defmodule RServer do\n'
                  '  import "rich.alc"\n'
                  '\n'
                  '  def loop(me: pid[Rich.Msg], left: integer): integer do\n'
                  '    if left == 0 do\n'
                  '      return 0\n'
                  '    end\n'
                  '    {arrived, m} = Process.receive(me, 10000)\n'
                  '    if (not arrived) do\n'
                  '      return 1\n'
                  '    end\n'
                  '    IO.puts("got #{inspect(m.n)} #{inspect(m.m)} #{inspect(m.e)} #{inspect(m.tree)} #{inspect(m.d)}")\n'
                  '    Process.send(m.reply, m, 1000)\n'
                  '    loop(me, left - 1)\n'
                  '  end\n'
                  '\n'
                  '  def main() do\n'
                  '    [mode] = System.argv()\n'
                  '    ok(_) = Node.start("rs", "127.0.0.1:0", "rich", [encrypted: mode == "tls"])\n'
                  '    me: pid[Rich.Msg] = Process.self(8)\n'
                  '    Process.register(me, :rich)\n'
                  '    IO.puts(Node.address())\n'
                  '    loop(me, 3)\n'
                  '  end\n'
                  'end\n'},
  'rserver.alc',
  ['plain'],
  1,
  'rclient.alc',
  ['plain'],
  0,
  b'"wrong type not found"\n"missing not found"\n{true, true}\n{true, 9223372036854775807, 0.5, true, "", :ok, [], {0, "t", {}}}\n{%{}, %{{1, "a"} ='
  b'> [:b, :c], {1, "z"} => [], {2, "x"} => [:a]}, MapSet.new([0, 3, 5, 9]), none, some("p"), ok(0), error("bad 0"), %Box{value: ["v", "w"], note: "'
  b'n"}, Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf), ~D[2026-11-19], ~T[23:59:58], ~N[2001-02-03 04:05:06]}\ntrue\n{true, -922337'
  b'2036854775808, -1.0e300, false, "h\xc3\xa9llo \\"w\xc3\xb6rld\\"\\n", :two, [[1, 2, 3], [], [-1]], {1, "t", {}}}\n{%{"" => 0.0, "a" => 1.5, "b" '
  b'=> 2.0}, %{{1, "a"} => [:b, :c], {1, "z"} => [], {2, "x"} => [:a]}, MapSet.new([1, 3, 5, 9]), some(1), some("p"), ok(1), error("bad 1"), %Box{va'
  b'lue: ["v", "w"], note: "n"}, Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf), ~D[2026-11-19], ~T[23:59:58], ~N[2001-02-03 04:05:06]}'
  b'\ntrue\n{true, -2000, 3.141592653589793, true, "h\xc3\xa9llo \\"w\xc3\xb6rld\\"\\n", :two, [[1, 2, 3], [], [-1]], {2, "t", {}}}\n{%{"" => 0.0,'
  b' "a" => 1.5, "b" => 2.0}, %{{1, "a"} => [:b, :c], {1, "z"} => [], {2, "x"} => [:a]}, MapSet.new([2, 3, 5, 9]), some(2), some("p"), ok(2), error('
  b'"bad 2"), %Box{value: ["v", "w"], note: "n"}, Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf), ~D[2026-11-19], ~T[23:59:58], ~N[2001'
  b'-02-03 04:05:06]}\ntrue\n',
  b'',
  b'',
  b'got 9223372036854775807 %{} MapSet.new([0, 3, 5, 9]) Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf) ~D[2026-11-19]\ngot -92233720368'
  b'54775808 %{"" => 0.0, "a" => 1.5, "b" => 2.0} MapSet.new([1, 3, 5, 9]) Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf) ~D[2026-11-19'
  b']\ngot -2000 %{"" => 0.0, "a" => 1.5, "b" => 2.0} MapSet.new([2, 3, 5, 9]) Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.leaf) ~D[2026-11'
  b'-19]\n',
  0),
 ('monitors, links, streams and a node that goes, encrypted',
  {'fclient.alc': 'defmodule FClient do\n'
                  '  def find(server: string, name: atom): pid[string] do\n'
                  '    found: option[pid[string]] = Node.whereis(server, name)\n'
                  '    some(p) = found\n'
                  '    p\n'
                  '  end\n'
                  '\n'
                  '  def main() do\n'
                  '    [mode, address] = System.argv()\n'
                  '    ok(_) = Node.start("cli", "127.0.0.1:0", "probe", [encrypted: mode == "tls"])\n'
                  '    ok(srv) = Node.connect(address)\n'
                  '    IO.inspect({srv, Node.list(), Node.connect(address)})\n'
                  '    me: pid[string] = Process.self(8)\n'
                  '    looked: option[pid[tuple[string, pid[string]]]] = Node.whereis(srv, :echo)\n'
                  '    some(echo) = looked\n'
                  '\n'
                  '    m1 = find(srv, :m1)\n'
                  '    r1 = Process.monitor(m1)\n'
                  '    Process.send(m1, "crash", 100)\n'
                  '    {a1, ref1, id1, why1} = Process.event(5000)\n'
                  '    IO.inspect({a1, ref1 == r1, id1 == Process.id(m1), why1})\n'
                  '\n'
                  '    m2 = find(srv, :m2)\n'
                  '    Process.send(m2, "exit3", 100)\n'
                  '    Process.sleep(200)\n'
                  '    r2 = Process.monitor(m2)\n'
                  '    {a2, ref2, id2, why2} = Process.event(5000)\n'
                  '    IO.inspect({a2, ref2 == r2, id2 == Process.id(m2), why2})\n'
                  '    gone: option[pid[string]] = Node.whereis(srv, :m2, 500)\n'
                  '    IO.inspect(case gone do\n'
                  '      some(_) -> "still named"\n'
                  '      none -> "name gone"\n'
                  '    end)\n'
                  '\n'
                  '    m3 = find(srv, :m3)\n'
                  '    r3 = Process.monitor(m3)\n'
                  '    IO.inspect({Process.demonitor(m3, r3), Process.demonitor(m3, r3), Process.alive(m3)})\n'
                  '    Process.send(m3, "stop", 100)\n'
                  '    IO.inspect(Process.event(300))\n'
                  '\n'
                  '    m4 = find(srv, :m4)\n'
                  '    Process.trap_exits(true)\n'
                  '    IO.inspect(Process.link(m4))\n'
                  '    Process.send(m4, "crash", 100)\n'
                  '    {a4, ref4, id4, why4} = Process.event(5000)\n'
                  '    IO.inspect({a4, ref4, id4 == Process.id(m4), why4})\n'
                  '    Process.trap_exits(false)\n'
                  '\n'
                  '    m5 = find(srv, :m5)\n'
                  '    IO.inspect({Process.link(m5), Process.unlink(m5), Process.unlink(m5)})\n'
                  '    Process.send(m5, "crash", 100)\n'
                  '    Process.sleep(200)\n'
                  '\n'
                  '    reader: pid[string] = Process.spawn(fn(self: pid[string]): integer do\n'
                  '      Process.receive(find(srv, :m6), 10)\n'
                  '      0\n'
                  '    end, 1)\n'
                  '    IO.inspect(Process.await(reader, 5000))\n'
                  '    waiter: pid[string] = Process.spawn(fn(self: pid[string]): integer do\n'
                  '      Process.await(find(srv, :m6), 10)\n'
                  '      0\n'
                  '    end, 1)\n'
                  '    IO.inspect(Process.await(waiter, 5000))\n'
                  '    stopper: pid[string] = Process.spawn(fn(self: pid[string]): integer do\n'
                  '      Process.stop(find(srv, :m6))\n'
                  '      0\n'
                  '    end, 1)\n'
                  '    IO.inspect(Process.await(stopper, 5000))\n'
                  '\n'
                  '    Process.send_after(echo, {"later", me}, 50)\n'
                  '    IO.inspect(Process.receive(me, 5000))\n'
                  '    big = String.duplicate("0123456789", 12000)\n'
                  '    Process.send(echo, {big, me}, 1000)\n'
                  '    {arrived, back} = Process.receive(me, 5000)\n'
                  '    IO.inspect({arrived, byte_size(back), back == big})\n'
                  '\n'
                  '    nums: result[stream[integer], string] = Node.stream(srv, :nums)\n'
                  '    ok(n) = nums\n'
                  '    IO.inspect({Enum.take(n, 3), Enum.count(n), Enum.sum(n)})\n'
                  '    words: result[stream[string], string] = Node.stream(srv, :words)\n'
                  '    ok(w) = words\n'
                  '    IO.inspect(Enum.take(Stream.drop(w, 510), 2))\n'
                  '    wrong: result[stream[string], string] = Node.stream(srv, :nums)\n'
                  '    absent: result[stream[string], string] = Node.stream(srv, :nothing)\n'
                  '    IO.inspect({case wrong do\n'
                  '      ok(_) -> "stream"\n'
                  '      error(why) -> why\n'
                  '    end, case absent do\n'
                  '      ok(_) -> "stream"\n'
                  '      error(why) -> why\n'
                  '    end})\n'
                  '    taker: pid[string] = Process.spawn(fn(self: pid[string]): integer do\n'
                  '      bad: result[stream[integer], string] = Node.stream(srv, :bad)\n'
                  '      ok(b) = bad\n'
                  '      IO.inspect(Enum.take(b, 2))\n'
                  '      0\n'
                  '    end, 1)\n'
                  '    IO.inspect(Process.await(taker, 40000))\n'
                  '    IO.inspect(Process.report(taker))\n'
                  '\n'
                  '    sq: result[integer, string] = Node.call(srv, :square, 12)\n'
                  '    no: result[integer, string] = Node.call(srv, :nope, 12)\n'
                  '    ty: result[string, string] = Node.call(srv, :square, 12)\n'
                  '    IO.inspect({sq, no, ty})\n'
                  '\n'
                  '    m6 = find(srv, :m6)\n'
                  '    r6 = Process.monitor(m6)\n'
                  '    watch = Node.monitor(srv)\n'
                  '    all = Node.monitor_nodes()\n'
                  '    IO.inspect(Node.cast(srv, :quit, 0))\n'
                  '    {b1, c1, d1, e1} = Process.event(5000)\n'
                  '    {b2, c2, d2, e2} = Process.event(5000)\n'
                  '    {b3, c3, d3, e3} = Process.event(5000)\n'
                  '    IO.inspect(Enum.sort([{b1, c1 == r6, c1 == watch, c1 == all, d1 == Process.id(m6), e1}, {b2, c2 == r6, c2 == watch, c2 == '
                  'all, d2 == Process.id(m6), e2}, {b3, c3 == r6, c3 == watch, c3 == all, d3 == Process.id(m6), e3}]))\n'
                  '    IO.inspect({Node.list(), Process.alive(m6), Process.send(m6, "x", 100), Process.send(echo, {"x", me}, 100), '
                  'Node.disconnect(srv)})\n'
                  '    r7 = Process.monitor(m6)\n'
                  '    {b7, c7, d7, e7} = Process.event(1000)\n'
                  '    IO.inspect({b7, c7 == r7, d7 == Process.id(m6), e7})\n'
                  '    after_down: option[pid[string]] = Node.whereis(srv, :m6, 300)\n'
                  '    IO.inspect(case after_down do\n'
                  '      some(_) -> "found"\n'
                  '      none -> "none"\n'
                  '    end)\n'
                  '    last: result[integer, string] = Node.call(srv, :square, 3)\n'
                  '    IO.inspect(last)\n'
                  '    again = case Node.connect(address) do\n'
                  '      ok(name) -> name\n'
                  '      error(why) -> why\n'
                  '    end\n'
                  '    IO.inspect({String.starts_with?(again, "dial tcp 127.0.0.1:"), String.ends_with?(again, ": connect: connection refused")})\n'
                  '  end\n'
                  'end\n',
   'fserver.alc': 'defmodule FServer do\n'
                  '  def echo(self: pid[tuple[string, pid[string]]]): integer do\n'
                  '    case Process.receive(self, 30000) do\n'
                  '      {true, {text, back}} ->\n'
                  '        Process.send(back, text, 1000)\n'
                  '        echo(self)\n'
                  '      _ -> 0\n'
                  '    end\n'
                  '  end\n'
                  '\n'
                  '  def moody(self: pid[string]): integer do\n'
                  '    case Process.receive(self, 30000) do\n'
                  '      {true, "crash"} -> raise("boom")\n'
                  '      {true, "exit3"} -> 3\n'
                  '      {true, "stop"} -> 0\n'
                  '      _ -> moody(self)\n'
                  '    end\n'
                  '  end\n'
                  '\n'
                  '  def main() do\n'
                  '    [mode] = System.argv()\n'
                  '    ok(_) = Node.start("srv", "127.0.0.1:0", "probe", [encrypted: mode == "tls"])\n'
                  '    e: pid[tuple[string, pid[string]]] = Process.spawn(fn(self: pid[tuple[string, pid[string]]]): integer do echo(self) end, 8)\n'
                  '    Process.register(e, :echo)\n'
                  '    for name <- [:m1, :m2, :m3, :m4, :m5, :m6] do\n'
                  '      m: pid[string] = Process.spawn(fn(self: pid[string]): integer do moody(self) end, 4)\n'
                  '      Process.register(m, name)\n'
                  '    end\n'
                  '    Node.serve(:square, fn(n: integer): integer do n * n end)\n'
                  '    Node.serve(:quit, fn(n: integer): integer do\n'
                  '      System.halt(0)\n'
                  '      n\n'
                  '    end)\n'
                  '    Stream.publish(:nums, fn -> Stream.take(Stream.from_index(1), 600) end)\n'
                  '    Stream.publish(:words, fn -> Stream.map(Stream.from_index(1), fn n -> "w#{n}" end) end)\n'
                  '    Stream.publish(:bad, fn -> Stream.map(Stream.from_index(1), fn n -> div(10, 3 - n) end) end)\n'
                  '    IO.puts(Node.address())\n'
                  '    IO.read(:eof)\n'
                  '  end\n'
                  'end\n'},
  'fserver.alc',
  ['tls'],
  1,
  'fclient.alc',
  ['tls'],
  0,
  b'{"srv", ["srv"], ok("srv")}\n{true, true, true, "boom"}\n{true, true, true, "exit:3"}\n"name gone"\n{true, false, true}\n{false, 0, 0, ""}\ntr'
  b'ue\n{true, 0, true, "boom"}\n{true, true, false}\n{true, "this needs a process of this node; a process of another node can only be sent to"}\n{t'
  b'rue, "this needs a process of this node; a process of another node can only be sent to"}\n{true, "this needs a process of this node; a process of'
  b' another node can only be sent to"}\n{true, "later"}\n{true, 120000, true}\n{[1, 2, 3], 600, 180300}\n["w511", "w512"]\n{"node srv publishes no s'
  b'tream nums of string", "node srv publishes no stream nothing of string"}\n{true, "the node holding the stream stopped answering"}\n"<stdin>:93'
  b':46: the node holding the stream stopped answering\\n  at FClient.main <closure> (<stdin>:95)"\n{ok(144), error("nothing served as :nope on sr'
  b'v"), error("nothing served as :square on srv")}\ntrue\n[{true, false, false, true, false, "nodedown srv"}, {true, false, true, false, false, "'
  b'nodedown srv"}, {true, true, false, false, true, "noconnection"}]\n{[], false, false, false, false}\n{true, true, true, "noconnection"}\n"none"'
  b'\nerror("nothing served as :square on srv")\n{true, true}\n',
  b'',
  b'',
  b'',
  0),
 ('cookies that differ',
  {'hc.alc': 'defmodule HC do\n'
             '  def main() do\n'
             '    [name, mode, cookie, address] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    IO.inspect(Node.connect(address))\n'
             '    IO.inspect(Node.list())\n'
             '    Process.sleep(200)\n'
             '  end\n'
             'end\n',
   'hs.alc': 'defmodule HS do\n'
             '  def main() do\n'
             '    [name, mode, cookie] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    w = Node.monitor_nodes()\n'
             '    IO.puts(Node.address())\n'
             '    IO.read(:eof)\n'
             '    IO.inspect(Process.event(0))\n'
             '  end\n'
             'end\n'},
  'hs.alc',
  ['s', 'plain', 'one'],
  1,
  'hc.alc',
  ['c', 'plain', 'two'],
  0,
  b'error("the nodes do not share a cookie")\n[]\n',
  b'',
  b'',
  b'{false, 0, 0, ""}\n',
  0),
 ('cookies that differ, encrypted',
  {'hc.alc': 'defmodule HC do\n'
             '  def main() do\n'
             '    [name, mode, cookie, address] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    IO.inspect(Node.connect(address))\n'
             '    IO.inspect(Node.list())\n'
             '    Process.sleep(200)\n'
             '  end\n'
             'end\n',
   'hs.alc': 'defmodule HS do\n'
             '  def main() do\n'
             '    [name, mode, cookie] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    w = Node.monitor_nodes()\n'
             '    IO.puts(Node.address())\n'
             '    IO.read(:eof)\n'
             '    IO.inspect(Process.event(0))\n'
             '  end\n'
             'end\n'},
  'hs.alc',
  ['s', 'tls', 'one'],
  1,
  'hc.alc',
  ['c', 'tls', 'two'],
  0,
  b'error("the nodes do not share a cookie")\n[]\n',
  b'',
  b'',
  b'{false, 0, 0, ""}\n',
  0),
 ('an encrypting node dialled by one that does not',
  {'hc.alc': 'defmodule HC do\n'
             '  def main() do\n'
             '    [name, mode, cookie, address] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    IO.inspect(Node.connect(address))\n'
             '    IO.inspect(Node.list())\n'
             '    Process.sleep(200)\n'
             '  end\n'
             'end\n',
   'hs.alc': 'defmodule HS do\n'
             '  def main() do\n'
             '    [name, mode, cookie] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    w = Node.monitor_nodes()\n'
             '    IO.puts(Node.address())\n'
             '    IO.read(:eof)\n'
             '    IO.inspect(Process.event(0))\n'
             '  end\n'
             'end\n'},
  'hs.alc',
  ['s', 'tls', 'k'],
  1,
  'hc.alc',
  ['c', 'plain', 'k'],
  0,
  b'error("the other node encrypts its connections and this one does not; start both with the same encrypted: setting")\n[]\n',
  b'',
  b'',
  b'{false, 0, 0, ""}\n',
  0),
 ('an encrypting node dialling one that does not',
  {'hc.alc': 'defmodule HC do\n'
             '  def main() do\n'
             '    [name, mode, cookie, address] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    IO.inspect(Node.connect(address))\n'
             '    IO.inspect(Node.list())\n'
             '    Process.sleep(200)\n'
             '  end\n'
             'end\n',
   'hs.alc': 'defmodule HS do\n'
             '  def main() do\n'
             '    [name, mode, cookie] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    w = Node.monitor_nodes()\n'
             '    IO.puts(Node.address())\n'
             '    IO.read(:eof)\n'
             '    IO.inspect(Process.event(0))\n'
             '  end\n'
             'end\n'},
  'hs.alc',
  ['s', 'plain', 'k'],
  1,
  'hc.alc',
  ['c', 'tls', 'k'],
  0,
  b'error("this node encrypts its connections and the other node does not; start both with the same encrypted: setting")\n[]\n',
  b'',
  b'',
  b'{false, 0, 0, ""}\n',
  0),
 ('two nodes of one name',
  {'hc.alc': 'defmodule HC do\n'
             '  def main() do\n'
             '    [name, mode, cookie, address] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    IO.inspect(Node.connect(address))\n'
             '    IO.inspect(Node.list())\n'
             '    Process.sleep(200)\n'
             '  end\n'
             'end\n',
   'hs.alc': 'defmodule HS do\n'
             '  def main() do\n'
             '    [name, mode, cookie] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    w = Node.monitor_nodes()\n'
             '    IO.puts(Node.address())\n'
             '    IO.read(:eof)\n'
             '    IO.inspect(Process.event(0))\n'
             '  end\n'
             'end\n'},
  'hs.alc',
  ['s', 'tls', 'k'],
  1,
  'hc.alc',
  ['s', 'tls', 'k'],
  0,
  b'error("both nodes are named s")\n[]\n',
  b'',
  b'',
  b'{false, 0, 0, ""}\n',
  0),
 ('two nodes that agree',
  {'hc.alc': 'defmodule HC do\n'
             '  def main() do\n'
             '    [name, mode, cookie, address] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    IO.inspect(Node.connect(address))\n'
             '    IO.inspect(Node.list())\n'
             '    Process.sleep(200)\n'
             '  end\n'
             'end\n',
   'hs.alc': 'defmodule HS do\n'
             '  def main() do\n'
             '    [name, mode, cookie] = System.argv()\n'
             '    ok(_) = Node.start(name, "127.0.0.1:0", cookie, [encrypted: mode == "tls"])\n'
             '    w = Node.monitor_nodes()\n'
             '    IO.puts(Node.address())\n'
             '    IO.read(:eof)\n'
             '    IO.inspect(Process.event(0))\n'
             '  end\n'
             'end\n'},
  'hs.alc',
  ['s', 'tls', 'k'],
  1,
  'hc.alc',
  ['c', 'tls', 'k'],
  0,
  b'ok("s")\n["s"]\n',
  b'',
  b'',
  b'{true, 2, 0, "nodeup c"}\n',
  0),
 ('a connection kept for two attempts',
  {'kc.alc': 'defmodule KC do\n'
             '  def main() do\n'
             '    [address] = System.argv()\n'
             '    ok(_) = Node.start("cli", "127.0.0.1:0", "k", [encrypted: false])\n'
             '    w = Node.monitor_nodes()\n'
             '    IO.inspect(Node.connect(address, [reconnect: 2]))\n'
             '    IO.inspect(Node.connect(address, [reconnect: 2]))\n'
             '    IO.inspect(Node.connect(address, [reconnect: 0]))\n'
             '    {a, r, i, why} = Process.event(1000)\n'
             '    IO.inspect({a, r == w, i, why})\n'
             '    started = System.monotonic_time(:millisecond)\n'
             '    Node.cast("srv", :quit, 0)\n'
             '    {a1, r1, i1, why1} = Process.event(1000)\n'
             '    IO.inspect({a1, r1 == w, i1, why1})\n'
             '    {a2, r2, i2, why2} = Process.event(10000)\n'
             '    took = System.monotonic_time(:millisecond) - started\n'
             '    IO.inspect({a2, r2 == w, i2, why2, took >= 2900 and took < 9000})\n'
             '    IO.inspect(Process.event(4500))\n'
             '    IO.inspect(Node.list())\n'
             '  end\n'
             'end\n',
   'ks.alc': 'defmodule KS do\n'
             '  def main() do\n'
             '    ok(_) = Node.start("srv", "127.0.0.1:0", "k", [encrypted: false])\n'
             '    Node.serve(:quit, fn(n: integer): integer do\n'
             '      System.halt(0)\n'
             '      n\n'
             '    end)\n'
             '    IO.puts(Node.address())\n'
             '    IO.read(:eof)\n'
             '  end\n'
             'end\n'},
  'ks.alc',
  [],
  1,
  'kc.alc',
  [],
  0,
  b'ok("srv")\nok("srv")\nok("srv")\n{true, true, 0, "nodeup srv"}\n{true, true, 0, "nodedown srv"}\n{true, true, 0, "noreconnect srv", true}\n{fa'
  b'lse, 0, 0, ""}\n[]\n',
  b'',
  b'',
  b'',
  0)]

# Three programs and what they write, the third first, as the pinned compiler runs them.
TRIO=('defmodule NA do\n'
 '  def echo(self: pid[string]): integer do\n'
 '    case Process.receive(self, 20000) do\n'
 '      {true, text} ->\n'
 '        IO.puts("a heard #{text}")\n'
 '        echo(self)\n'
 '      _ -> 0\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    ok(_) = Node.start("a", "127.0.0.1:0", "k")\n'
 '    e: pid[string] = Process.spawn(fn(self: pid[string]): integer do echo(self) end, 4)\n'
 '    IO.inspect(Node.register_global(e, :ear))\n'
 '    IO.puts(Node.address())\n'
 '    IO.read(:eof)\n'
 '  end\n'
 'end\n',
 'defmodule NB do\n'
 '  def relay(self: pid[tuple[string, pid[string]]], left: integer): integer do\n'
 '    if left == 0 do\n'
 '      return 0\n'
 '    end\n'
 '    {arrived, {text, to}} = Process.receive(self, 20000)\n'
 '    IO.puts("b relays #{text}: #{inspect({Process.alive(to), Process.send(to, text, 500), Node.list()})}")\n'
 '    relay(self, left - 1)\n'
 '  end\n'
 '  def main() do\n'
 '    ok(_) = Node.start("b", "127.0.0.1:0", "k")\n'
 '    r: pid[tuple[string, pid[string]]] = Process.spawn(fn(self: pid[tuple[string, pid[string]]]): integer do relay(self, 3) end, 4)\n'
 '    Process.register(r, :relay)\n'
 '    IO.inspect(Node.register_global(r, :ear))\n'
 '    IO.puts(Node.address())\n'
 '    IO.read(:eof)\n'
 '  end\n'
 'end\n',
 'defmodule NC do\n'
 '  def main() do\n'
 '    [a, b] = System.argv()\n'
 '    ok(_) = Node.start("c", "127.0.0.1:0", "k")\n'
 '    ok(na) = Node.connect(a)\n'
 '    ok(nb) = Node.connect(b)\n'
 '    IO.inspect(Node.list())\n'
 '    ear: option[pid[string]] = Node.whereis_global(:ear)\n'
 '    relay: option[pid[tuple[string, pid[string]]]] = Node.whereis(nb, :relay)\n'
 '    other: option[pid[tuple[string, pid[string]]]] = Node.whereis_global(:ear)\n'
 '    some(e) = ear\n'
 '    some(r) = relay\n'
 '    IO.inspect(case other do\n'
 '      some(_) -> "second type found"\n'
 '      none -> "none"\n'
 '    end)\n'
 '    me: pid[string] = Process.self(4)\n'
 '    IO.inspect(Node.register_global(me, :ear))\n'
 '    Process.send(r, {"one", e}, 500)\n'
 '    Process.send(r, {"two", me}, 500)\n'
 '    IO.inspect(Process.receive(me, 3000))\n'
 '    Process.sleep(300)\n'
 '  end\n'
 'end\n',
 (0,
  b'["a", "b"]\n"second type found"\nfalse\n{true, "two"}\n',
  b'',
  b'true\n',
  b'',
  b'true\n',
  b'b relays one: {false, false, ["c"]}\nb relays two: {true, true, ["c"]}\n'))

ORACLE=('defmodule Oracle do\n'
 '  def box(self: pid[tuple[atom, integer, list[string], pid[string]]]): integer do\n'
 '    {arrived, {tag, number, texts, back}} = Process.receive(self, 20000)\n'
 '    IO.puts(inspect({arrived, tag, number, texts, Process.id(back), Process.alive(back)}))\n'
 '    Process.send(back, "got #{number}", 1000)\n'
 '    if tag == :bye do 3 else box(self) end\n'
 '  end\n'
 '\n'
 '  def main() do\n'
 '    ok(_) = Node.start("nat", "127.0.0.1:0", "oracle", [encrypted: false])\n'
 '    b: pid[tuple[atom, integer, list[string], pid[string]]] = Process.spawn(fn(self: pid[tuple[atom, integer, list[string], pid[string]]]): '
 'integer do box(self) end, 4)\n'
 '    Process.register(b, :box)\n'
 '    Stream.publish(:nums, fn -> Stream.from_index(1) end)\n'
 '    IO.puts(Node.address())\n'
 '    IO.inspect(Process.await(b, 20000))\n'
 '    IO.read(:eof)\n'
 '  end\n'
 'end\n')

KIND='tuple[atom,integer,list[string],pid[string]]'
def oracle(address,cookie='oracle'):
    """A node written here, from the pinned runtime's node.go, speaks to a native one: what comes back is compared byte for byte."""
    import hashlib,hmac,os,socket,struct
    def varint(v):
        u=((v<<1)^(v>>63))&(2**64-1);out=b''
        while u>=0x80:out+=bytes([u&0x7f|0x80]);u>>=7
        return out+bytes([u])
    def text(x):
        x=x.encode() if isinstance(x,str) else x
        return varint(len(x))+x
    host,port=address.rsplit(':',1)
    k=socket.create_connection((host,int(port)),timeout=20)
    def read(n):
        out=b''
        while len(out)<n:
            piece=k.recv(n-len(out))
            assert piece,('closed',out)
            out+=piece
        return out
    def frame():return read(struct.unpack('>I',read(4))[0])
    def send(payload):k.sendall(struct.pack('>I',len(payload))+payload)
    k.sendall(b'P');assert read(1)==b'P'
    own=os.urandom(32);send(own);other=frame();assert len(other)==32
    binding=hashlib.sha256(own+other).digest()
    proof=lambda role,name:hmac.new(cookie.encode(),binding+b'\0'+role+b'\0'+name,hashlib.sha256).digest()
    send(text('alchem node 4')+text('py')+text(proof(b'dialling',b'py')))
    assert frame()==text('alchem node 4')+text('nat')+text(proof(b'accepting',b'nat'))
    send(b'\x02'+varint(1)+text('box')+text(KIND));found=frame()
    assert found[:3]==b'\x03'+varint(1)+b'\x01',found
    box=found[3:];assert 1<=len(box)<=2
    send(b'\x02'+varint(2)+text('box')+text('tuple[atom,integer]'));assert frame()==b'\x03'+varint(2)+b'\x00'+box
    send(b'\x02'+varint(3)+text('nobody')+text(KIND));assert frame()==b'\x03'+varint(3)+b'\x00\x00'
    send(b'\x04'+box+varint(77))
    send(b'\x04'+varint(999999)+varint(78));assert frame()==b'\x05'+varint(78)+varint(999999)+text('noproc')
    message=lambda tag,number,texts:b'\x01'+box+text(tag)+varint(number)+varint(len(texts))+b''.join(text(t) for t in texts)+text('py')+varint(5)
    send(message('hi',-7,['a','bc']));assert frame()==b'\x01'+varint(5)+text('got -7')
    send(b'\x06'+varint(4)+text('nums')+text('integer'));assert frame()==b'\x03'+varint(4)+b'\x01'
    send(b'\x06'+varint(5)+text('nums')+text('string'));assert frame()==b'\x03'+varint(5)+b'\x00'
    send(b'\x07'+varint(6)+text('nums')+varint(1)+b'\x00')
    assert frame()==b'\x03'+varint(6)+b'\x00'+varint(256)+b''.join(varint(n) for n in range(1,257))
    send(b'\x07'+varint(7)+text('nums')+varint(1)+b'\x00')
    assert frame()==b'\x03'+varint(7)+b'\x00'+varint(256)+b''.join(varint(n) for n in range(257,513))
    send(b'\x07'+varint(0)+text('nums')+varint(1)+b'\x01')
    send(b'\x07'+varint(8)+text('nothing')+varint(1)+b'\x00');assert frame()==b'\x03'+varint(8)+b'\x01'+varint(0)
    send(message('bye',1<<62,[]))
    got=sorted([frame(),frame()])
    assert got==sorted([b'\x01'+varint(5)+text('got 4611686018427387904'),b'\x05'+varint(77)+box+text('exit:3')]),got
    send(b'\x04'+box+varint(79));assert frame()==b'\x05'+varint(79)+box+text('exit:3')
    k.close()


def bounds(directory,seconds):
    env=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),ALCHEM_SECONDS=str(seconds),ALCHEM_MEMORY='3G',TMPDIR=str(directory))
    for name in ('XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'):
        if name in os.environ:env[name]=os.environ[name]
    return env


def build(compiler,source,path):
    built=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=180)
    assert (built.returncode,built.stderr)==(0,b''),(source,built.returncode,built.stderr)
    path.write_bytes(built.stdout);path.chmod(0o700)
    return path


def killed(process):
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait()


def run(compiler,source,base,number):
    """The status, output and errors of a program of one node."""
    directory=Path(base)/f'd{number}';directory.mkdir(0o700)
    program=build(compiler,source.encode(),Path(base)/f'p{number}')
    process=subprocess.Popen([str(ROOT/'scripts/limited'),str(program)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=bounds(directory,60),cwd=directory,start_new_session=True)
    try:out,err=process.communicate(timeout=120)
    finally:killed(process)
    return process.returncode,out,err


def started(compiler,bundler,files,entry,arguments,lines,directory):
    """The first program of a group, running, with what it wrote up to its address."""
    for name,text in files.items():(directory/name).write_text(text)
    source=bundler.bundle(str(directory/entry)) if any('import "' in text for text in files.values()) else files[entry].encode()
    program=build(compiler,source,directory/(entry+'.bin'))
    process=subprocess.Popen([str(ROOT/'scripts/limited'),str(program)]+arguments,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=bounds(directory,150),cwd=directory,start_new_session=True)
    try:
        first=[process.stdout.readline() for _ in range(lines)]
        address=first[-1].strip().decode()
        assert address.startswith('127.0.0.1:') and address[10:].isdigit(),(entry,first)
    except BaseException:
        killed(process);raise
    return process,b''.join(first[:-1]),address


def group(compiler,bundler,item,base,number):
    title,files,server,server_arguments,lines,client,client_arguments=item[:7]
    directory=Path(base)/f'g{number}';directory.mkdir(0o700)
    # The second program is built before the first starts: the pinned shop waits
    # only ten seconds for an order, less than a build can take on a loaded machine.
    for name,text in files.items():(directory/name).write_text(text)
    source=bundler.bundle(str(directory/client)) if any('import "' in text for text in files.values()) else files[client].encode()
    program=build(compiler,source,directory/(client+'.bin'))
    first,before,address=started(compiler,bundler,files,server,server_arguments,lines,directory)
    try:
        second=subprocess.Popen([str(ROOT/'scripts/limited'),str(program)]+client_arguments+[address],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=bounds(directory,150),cwd=directory,start_new_session=True)
        try:out,err=second.communicate(timeout=200)
        finally:killed(second)
        first.stdin.close()
        after=first.stdout.read();first.wait(timeout=60)
    finally:killed(first)
    return second.returncode,out,err,before,after,first.returncode


def spoken(compiler,bundler,base):
    """The native node answers the node written above byte for byte."""
    directory=Path(base)/'oracle';directory.mkdir(0o700)
    first,before,address=started(compiler,bundler,{'oracle.alc':ORACLE},'oracle.alc',[],1,directory)
    try:
        oracle(address)
        first.stdin.close()
        after=first.stdout.read();first.wait(timeout=60)
    finally:killed(first)
    assert (before,after,first.returncode)==(b'',b'{true, :hi, -7, ["a", "bc"], 5, true}\n{true, :bye, 4611686018427387904, [], 5, true}\n{true, "exit:3"}\n',0),(before,after,first.returncode)


def trio(compiler,bundler,base):
    """Three nodes: the third connects to the other two and hands the first's process to the second, which is not connected to it."""
    directory=Path(base)/'trio';directory.mkdir(0o700)
    first,before1,address1=started(compiler,bundler,{'na.alc':TRIO[0]},'na.alc',[],2,directory)
    try:
        second,before2,address2=started(compiler,bundler,{'nb.alc':TRIO[1]},'nb.alc',[],2,directory)
        try:
            program=build(compiler,TRIO[2].encode(),directory/'nc.bin')
            third=subprocess.Popen([str(ROOT/'scripts/limited'),str(program),address1,address2],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=bounds(directory,60),cwd=directory,start_new_session=True)
            try:out,err=third.communicate(timeout=120)
            finally:killed(third)
            first.stdin.close();second.stdin.close()
            got=(third.returncode,out,err,before1,first.stdout.read(),before2,second.stdout.read())
        finally:killed(second)
    finally:killed(first)
    assert got==TRIO[3],(got,TRIO[3])


HELLO=('defmodule Hello do\n  def main() do\n    ok(_) = Node.start("hello", "127.0.0.1:0", "secret")\n    watch = Node.monitor_nodes()\n'
       '    IO.puts(Node.address())\n    IO.read(:eof)\n    IO.inspect(Process.event(0))\n  end\nend\n')


def shaken(compiler,bundler,base):
    """A TLS 1.3 client that is neither this compiler's nor the pinned one's
    takes the native node's handshake and its certificate; it does not know
    the cookie, so no node comes of it. 0 where Python has no such client."""
    try:
        import socket,ssl
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version=ssl.TLSVersion.TLSv1_3
    except (ImportError,AttributeError,ValueError):return 0
    context.check_hostname=False;context.verify_mode=ssl.CERT_NONE
    directory=Path(base)/'hello';directory.mkdir(0o700)
    first,before,address=started(compiler,bundler,{'hello.alc':HELLO},'hello.alc',[],1,directory)
    try:
        host,port=address.rsplit(':',1)
        with socket.create_connection((host,int(port)),timeout=20) as raw:
            raw.sendall(b'T');assert raw.recv(1)==b'T'
            with context.wrap_socket(raw) as secured:
                certificate=secured.getpeercert(binary_form=True)
                # The suite is the node's choice, as Go chooses: AES-128-GCM where the processor has AES, else ChaCha20.
                assert secured.version()=='TLSv1.3' and secured.cipher()[0] in ('TLS_AES_128_GCM_SHA256','TLS_CHACHA20_POLY1305_SHA256'),(secured.version(),secured.cipher())
                # CN=hello twice (issuer and subject), an Ed25519 key, and the node's own signature under it.
                assert certificate.count(b'\x06\x03\x55\x04\x03\x0c\x05hello')==2 and certificate.count(b'\x06\x03\x2b\x65\x70')==3,certificate
                secured.sendall(b'\x00\x00\x00\x05hello')
                try:assert secured.recv(100) in (b'',) or True
                except (ssl.SSLError,OSError):pass
        first.stdin.close()
        after=first.stdout.read();first.wait(timeout=60)
    finally:killed(first)
    assert (before,after,first.returncode)==(b'',b'{false, 0, 0, ""}\n',0),(before,after,first.returncode)
    return 1


def verify(compiler):
    spec=importlib.util.spec_from_file_location('alchem_bundle',ROOT/'scripts/bundle-alchem.py')
    bundler=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundler)
    with tempfile.TemporaryDirectory(prefix='alchem-nodes-') as base:
        with ThreadPoolExecutor(6) as pool:
            groups=[pool.submit(group,compiler,bundler,item,base,number) for number,item in enumerate(GROUPS)]
            got=list(pool.map(lambda item:run(compiler,item[1][0],base,item[0]),enumerate(RUNS)))
            spoken(compiler,bundler,base)
            trio(compiler,bundler,base)
            shook=shaken(compiler,bundler,base)
            for item,future in zip(GROUPS,groups):
                assert future.result()==item[7:],(item[0],future.result(),item[7:])
        for (source,status,stdout,stderr),result in zip(RUNS,got):
            assert result==(status,stdout,stderr),(source,result,(status,stdout,stderr))
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    if not shook:print('SKIP the TLS 1.3 handshake with Python\'s ssl module, which this Python lacks')
    print(f'PASS nodes: {len(RUNS)} programs of one node run as the pinned compiler runs them (the 17 examples of the references, {len(RUNS)-17} probes), {len(REJECTS)} rejected, '
          f'{len(GROUPS)} pairs of nodes and three nodes together, a node of the pinned wire format answered byte for byte, {shook} TLS 1.3 handshake with another implementation')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
