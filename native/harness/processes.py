#!/usr/bin/env python3
"""Processes: every program runs as the pinned compiler runs it.

Process, Task, Task.Supervisor, Agent, Server, Supervisor, DynamicSupervisor,
Registry, Port and the receive assertions (spec/alchem-processes.md). The
programs are ones whose outcome does not depend on how the pinned runtime's
goroutines are scheduled: nothing here prints a process number that a race
decides, an address or a time. Each native program runs under
scripts/limited with a few seconds to live, since a scheduler that goes
wrong is exactly what never ends."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.crash("bad input") end, '
  '1)\n'
  '{ended, reason} = Process.await(worker, 1000)\n'
  'IO.puts(inspect({ended, reason}))\n'
  'IO.puts(Process.report(worker))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, "bad input"}\n<stdin>:3:73: bad input\n  at Example.main <closure> (<stdin>:3)\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 3 end, 1)\n'
  'IO.puts(inspect(Process.await(worker, 1000)))\n'
  'IO.puts(Process.report(worker))\n'
  'IO.puts(inspect(Process.alive(worker)))\n'
  'IO.puts(inspect(Process.id(worker)))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, "exit:3"}\nexit:3\nfalse\n2\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 0 end, 1)\n'
  'reference = Process.monitor(worker)\n'
  'IO.puts(inspect(Process.event(1000)))\n'
  'IO.puts(inspect(reference))\n'
  'IO.puts(inspect(Process.event(10)))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, 3, 2, "normal"}\n3\n{false, 0, 0, ""}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(60000) end, 1)\n'
  'IO.puts(inspect(Process.stop(worker)))\n'
  'IO.puts(inspect(Process.stop(worker)))\n'
  'IO.puts(inspect(Process.await(worker, 1000)))\n'
  'IO.puts(Process.report(worker))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\n{true, "shutdown"}\nshutdown\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  Process.sleep(20)\n'
  '  raise("boom")\n'
  'end, 1)\n'
  'IO.puts(inspect(Process.link(worker)))\n'
  'Process.sleep(1000)\n'
  'IO.puts("not reached")\n'
  '  end\n'
  'end\n',
  2,
  b'true\n',
  b'<stdin>:5:3: boom\n  at Example.main <closure> (<stdin>:5)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'Process.trap_exits(true)\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  Process.sleep(20)\n'
  '  raise("boom")\n'
  'end, 1)\n'
  'IO.puts(inspect(Process.link(worker)))\n'
  'IO.puts(inspect(Process.event(1000)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n{true, 0, 2, "boom"}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'IO.puts(inspect(Process.loop(1, fn(n: integer): tuple[boolean, integer] do {n < 100, n * 2} end)))\n'
  '  end\n'
  'end\n',
  0,
  b'256\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'before = Process.count()\n'
  'worker: pid[integer] = Process.spawn(fn(inbox: pid[integer]): integer do\n'
  '  {_, value} = Process.receive(inbox, 1000)\n'
  '  value\n'
  'end, 1)\n'
  'IO.puts(inspect(Process.count() == before + 1))\n'
  'IO.puts(inspect(Process.send(worker, 0, 100)))\n'
  'IO.puts(inspect(Process.await(worker, 100)))\n'
  'IO.puts(inspect(Process.count()))\n'
  '  end\n'
  'end\n',
  0,
  b'true\ntrue\n{true, "normal"}\n1\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(4)\n'
  'IO.puts(inspect(Process.send(me, 7, 100)))\n'
  'IO.puts(inspect(Process.receive(me, 100)))\n'
  'IO.puts(inspect(Process.receive(me, 10)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n{true, 7}\n{false, 0}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  try do\n'
  '    Process.sleep(60000)\n'
  '  after\n'
  '    IO.puts("cleanup")\n'
  '  end\n'
  'end, 1)\n'
  'Process.sleep(10)\n'
  'IO.puts("main done")\n'
  '  end\n'
  'end\n',
  0,
  b'main done\ncleanup\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  try do\n'
  '    Process.sleep(60000)\n'
  '  after\n'
  '    IO.puts("cleanup")\n'
  '  end\n'
  'end, 1)\n'
  'Process.sleep(10)\n'
  'raise("main failed")\n'
  '  end\n'
  'end\n',
  2,
  b'cleanup\n',
  b'<stdin>:11:1: main failed\n  at Example.main (<stdin>:11)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  throw(5)\n'
  '  0\n'
  'end, 1)\n'
  'IO.puts(inspect(Process.await(worker, 1000)))\n'
  'IO.puts(Process.report(worker))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, "uncaught throw"}\n<stdin>:4:3: uncaught throw\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.crash("normal") end, 1)\n'
  'IO.puts(inspect(Process.await(worker, 1000)))\n'
  'IO.puts(Process.report(worker))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, "error: normal"}\n<stdin>:3:73: normal\n  at Example.main <closure> (<stdin>:3)\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(2)\n'
  'IO.puts(inspect([Process.send(me, 1, 0), Process.send(me, 2, 0), Process.send(me, 3, 0), Process.send(me, '
  '4, 20)]))\n'
  'IO.puts(inspect([Process.receive(me, 0), Process.receive(me, 0), Process.receive(me, 0)]))\n'
  '  end\n'
  'end\n',
  0,
  b'[true, true, false, false]\n[{true, 1}, {true, 2}, {false, 0}]\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(1000) end, 1)\n'
  'IO.puts(inspect(Process.receive(worker, 10)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:17: only the mailbox owner may receive\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def deep(n: integer): integer do\n'
  '    if n == 0 do 0 else 1 + deep(n - 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do deep(99998) end, 1)\n'
  '    IO.puts(inspect(Process.await(w, 5000)))\n'
  '    w2: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do deep(99999) end, 1)\n'
  '    IO.puts(inspect(Process.await(w2, 5000)))\n'
  '    IO.puts(inspect(length(String.split(Process.report(w2), "\\n"))))\n'
  '    IO.puts(hd(String.split(Process.report(w2), "\\n")))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, "exit:99998"}\n{true, "call depth exceeded"}\n62\n<stdin>:2:7: call depth exceeded\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(4)\n'
  'other: pid[integer] = Process.self(9)\n'
  'IO.puts(inspect(Process.id(me) == Process.id(other)))\n'
  'IO.puts(inspect([Process.send(me, 1, 0), Process.send(me, 2, 0), Process.send(me, 3, 0), Process.send(me, '
  '4, 0), Process.send(other, 5, 0)]))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n[true, true, true, true, false]\n',
  b''),
 ('defmodule Example do\n  def main() do\nme: pid[integer] = Process.self(0)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:20: mailbox capacity must be 1..1000000\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 0 end, 1000001)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:19: mailbox capacity must be 1..1000000\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n  def main() do\nProcess.sleep(-1)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:1: sleep duration must be nonnegative\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(1)\n'
  'Process.await(me, 1)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:1: cannot await self\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(60000) end, 1)\n'
  'reference = Process.monitor(worker)\n'
  'IO.puts(inspect(Process.demonitor(worker, reference)))\n'
  'IO.puts(inspect(Process.demonitor(worker, reference)))\n'
  'IO.puts(inspect(Process.stop(worker)))\n'
  'IO.puts(inspect(Process.event(50)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\ntrue\n{false, 0, 0, ""}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 0 end, 1)\n'
  'reference = Process.monitor(worker)\n'
  'Process.await(worker, 1000)\n'
  'IO.puts(inspect(Process.demonitor(worker, reference)))\n'
  'IO.puts(inspect(Process.event(50)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n{false, 0, 0, ""}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 7 end, 1)\n'
  'Process.await(worker, 1000)\n'
  'reference = Process.monitor(worker)\n'
  'IO.puts(inspect(Process.event(50)))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, 3, 2, "exit:7"}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 7 end, 1)\n'
  'Process.await(worker, 1000)\n'
  'IO.puts(inspect(Process.link(worker)))\n'
  'IO.puts("after")\n'
  'Process.sleep(1)\n'
  'IO.puts("after2")\n'
  '  end\n'
  'end\n',
  2,
  b'false\n',
  b'<runtime>: linked: exit:7\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do raise("x") end, 1)\n'
  'Process.await(worker, 1000)\n'
  'IO.puts(inspect(Process.link(worker)))\n'
  'Process.sleep(1)\n'
  'IO.puts("after2")\n'
  '  end\n'
  'end\n',
  2,
  b'false\n',
  b'<stdin>:3:73: x\n  at Example.main <closure> (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(60000) end, 1)\n'
  'IO.puts(inspect(Process.unlink(worker)))\n'
  'IO.puts(inspect(Process.link(worker)))\n'
  'IO.puts(inspect(Process.link(worker)))\n'
  'IO.puts(inspect(Process.unlink(worker)))\n'
  'IO.puts(inspect(Process.unlink(worker)))\n'
  'me: pid[integer] = Process.self(1)\n'
  'IO.puts(inspect(Process.link(me)))\n'
  'IO.puts(inspect(Process.trap_exits(true)))\n'
  'IO.puts(inspect(Process.trap_exits(false)))\n'
  '  end\n'
  'end\n',
  0,
  b'false\ntrue\ntrue\ntrue\nfalse\nfalse\nfalse\ntrue\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(1)\n'
  'IO.puts(inspect(Process.stop(me)))\n'
  'IO.puts("after")\n'
  '  end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule Example do\n'
  '  defexception Bad do\n'
  '    message: string\n'
  '    code: integer\n'
  '  end\n'
  '  def main() do\n'
  '    w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do raise(%Bad{message: "very bad", '
  'code: 3}) end, 1)\n'
  '    IO.puts(inspect(Process.await(w, 1000)))\n'
  '    IO.puts(Process.report(w))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, "very bad"}\n<stdin>:7:72: very bad\n  at Example.main <closure> (<stdin>:7)\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  try do\n'
  '    raise("inner")\n'
  '  rescue\n'
  '    m -> IO.puts("rescued " <> m)\n'
  '  end\n'
  '  4\n'
  'end, 1)\n'
  'IO.puts(inspect(Process.await(w, 1000)))\n'
  '  end\n'
  'end\n',
  0,
  b'rescued inner\n{true, "exit:4"}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  Process.sleep(10)\n'
  '  9\n'
  'end, 1)\n'
  'Process.link(w)\n'
  'Process.sleep(1000)\n'
  'IO.puts("no")\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<runtime>: linked: exit:9\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'task = Task.async(fn -> div(1, 0) end)\n'
  'IO.puts(inspect(Task.await(task)))\n'
  'IO.puts("no")\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:17: task failed: division by zero\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'Process.trap_exits(true)\n'
  'task = Task.async(fn -> div(1, 0) end)\n'
  'IO.puts(inspect(Task.yield(task, 1000)))\n'
  'IO.puts(inspect(Process.event(100)))\n'
  '  end\n'
  'end\n',
  0,
  b'some(error("division by zero"))\n{true, 0, 2, "division by zero"}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'task = Task.start(fn -> div(1, 0) end)\n'
  'IO.puts(inspect(Task.await(task)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:17: task failed: division by zero\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'task = Task.start(fn -> Process.sleep(500) end)\n'
  'IO.puts(inspect(Task.await(task, 10)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:17: task timed out\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'task = Task.start(fn -> raise("oops") end)\n'
  'IO.puts(inspect(Task.yield(task, 1000)))\n'
  'IO.puts(inspect(Task.yield(task, 1000)))\n'
  '  end\n'
  'end\n',
  0,
  b'some(error("oops"))\nsome(error("oops"))\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'ts = [Task.async(fn -> 1 end), Task.async(fn -> Process.sleep(20) end), Task.async(fn -> 3 end)]\n'
  'IO.puts(inspect(Task.await_many(ts)))\n'
  'IO.puts(inspect(Task.await_many(ts, 100)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 0, 3]\n[1, 0, 3]\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'ts = [Task.start(fn -> 1 end), Task.start(fn -> Process.sleep(300) end)]\n'
  'IO.puts(inspect(Task.await_many(ts, 20)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:17: task timed out\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'IO.puts(inspect(Task.async_stream([1], fn n -> n end, 0) |> Enum.to_list()))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:17: async_stream needs a concurrency of at least 1\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'Process.trap_exits(true)\n'
  's = Task.async_stream([1, 0, 3], fn n -> div(6, n) end, 1)\n'
  'IO.puts("made")\n'
  'IO.puts(inspect(Enum.to_list(s)))\n'
  '  end\n'
  'end\n',
  2,
  b'made\n',
  b'<stdin>:4:5: task failed: division by zero\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'x = 20\n'
  't = Task.async(fn -> x + 1 end)\n'
  'u = Task.async(fn -> x + 2 end)\n'
  'IO.puts(inspect([Task.await(u), Task.await(t)]))\n'
  'me: pid[integer] = Process.self(1)\n'
  'IO.puts(inspect(Process.id(me)))\n'
  'w: pid[integer] = Process.spawn(fn(s: pid[integer]): integer do 0 end, 1)\n'
  'IO.puts(inspect(Process.id(w)))\n'
  '  end\n'
  'end\n',
  0,
  b'[22, 21]\n1\n4\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  't = Task.async(fn ->\n'
  '  me: pid[string] = Process.self(2)\n'
  '  Process.send(me, "x", 0)\n'
  '  Process.receive(me, 0)\n'
  'end)\n'
  'IO.puts(inspect(Task.await(t)))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, "x"}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'counter = Agent.start(fn -> 0 end)\n'
  'IO.puts(inspect(Agent.cast(counter, fn n -> n + 1 end)))\n'
  'Agent.update(counter, fn n -> n * 10 end)\n'
  'IO.puts(inspect(Agent.get(counter, fn n -> n end)))\n'
  'IO.puts(inspect(Agent.get_and_update(counter, fn n -> {"was #{n}", n + 1} end)))\n'
  'IO.puts(inspect(Agent.get(counter, fn n -> n end, 100)))\n'
  'IO.puts(inspect(Agent.stop(counter)))\n'
  'IO.puts(inspect(Agent.stop(counter)))\n'
  'IO.puts(inspect(Agent.cast(counter, fn n -> n + 1 end)))\n'
  'IO.puts(inspect(Agent.get(counter, fn n -> n end)))\n'
  '  end\n'
  'end\n',
  2,
  b'true\n10\n"was 10"\n11\ntrue\nfalse\nfalse\n',
  b'<stdin>:12:17: agent is not running\n  at Example.main (<stdin>:12)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'counter = Agent.start(fn -> 0 end)\n'
  'IO.puts(inspect(Agent.get(counter, fn n -> div(1, n) end)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:17: agent stopped: division by zero\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'Process.trap_exits(true)\n'
  'counter = Agent.start(fn -> 0 end)\n'
  'r = try do\n'
  '  Agent.get(counter, fn n -> div(1, n) end)\n'
  'rescue\n'
  '  m -> IO.puts(m)\n'
  '  -1\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  'IO.puts(inspect(Agent.cast(counter, fn n -> n end)))\n'
  '  end\n'
  'end\n',
  0,
  b'agent stopped: division by zero\n-1\nfalse\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'counter = Agent.start(fn -> 0 end)\n'
  'IO.puts(inspect(Agent.get(counter, fn n -> Process.sleep(200) end, 20)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:17: agent timed out\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'Agent.start_link(fn -> 1 end, [name: :doc_agent])\n'
  'IO.puts(inspect(Agent.get(:doc_agent, fn(n: integer): integer do n + 1 end)))\n'
  'Agent.update(:doc_agent, fn(n: integer): integer do n + 5 end)\n'
  'IO.puts(inspect(Agent.get_and_update(:doc_agent, fn(n: integer): tuple[integer, integer] do {n, 0} '
  'end)))\n'
  'IO.puts(inspect(Agent.cast(:doc_agent, fn(n: integer): integer do n + 5 end)))\n'
  'IO.puts(inspect(Agent.get(:doc_agent, fn(n: integer): integer do n end)))\n'
  'found: option[agent[string]] = Agent.whereis(:doc_agent)\n'
  'IO.puts(inspect(case found do\n'
  '  some(_) -> "yes"\n'
  '  none -> "no"\n'
  'end))\n'
  'Agent.start(fn -> 2 end, [name: :doc_agent])\n'
  '  end\n'
  'end\n',
  2,
  b'2\n6\ntrue\n5\n"no"\n',
  b'<stdin>:14:1: the name :doc_agent is already taken\n  at Example.main (<stdin>:14)\n'),
 ('defmodule Example do\n  def main() do\nAgent.start(fn -> 2 end, [nme: :doc_agent])\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:1: unknown option :nme; Agent.start_link takes name:\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'IO.puts(inspect(Agent.get(:nobody, fn(n: integer): integer do n + 1 end)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:17: no agent named :nobody with this state type is running\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'a = Agent.start(fn -> div(1, 0) end)\n'
  'IO.puts(inspect(Agent.get(a, fn n -> n end)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:17: agent stopped: division by zero\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'a = Agent.start(fn -> 0 end)\n'
  'b = Agent.start(fn -> 0 end)\n'
  'IO.puts(inspect(Agent.get(a, fn n -> Agent.get(b, fn m -> m + 1 end) end)))\n'
  '  end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  's = Server.start(0, fn(total: integer, d: integer): tuple[integer, integer] do {total, div(10, d)} end)\n'
  'IO.puts(inspect(Server.call(s, 2, 1000)))\n'
  'IO.puts(inspect(Server.call(s, 0, 1000)))\n'
  'IO.puts(inspect(Server.call(s, 2, 1000)))\n'
  'IO.puts(inspect(Server.await(s, 100)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok(5)\nerror("server stopped: division by zero")\nerror("server is not running")\n{true, "division by z'
  b'ero"}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  's = Server.start(0, fn(total: integer, d: integer): tuple[integer, integer] do {total, Process.sleep(d)} '
  'end)\n'
  'IO.puts(inspect(Server.call(s, 200, 20)))\n'
  'IO.puts(inspect(Server.call(s, 1, 1000)))\n'
  '  end\n'
  'end\n',
  0,
  b'error("timeout")\nok(0)\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  's = Server.start_supervised(0, fn(total: integer, d: integer): tuple[integer, integer] do {total + 1, '
  'div(10, d)} end, 3, 1000)\n'
  'IO.puts(inspect(Server.call(s, 2, 1000)))\n'
  'IO.puts(inspect(Server.call(s, 0, 1000)))\n'
  'IO.puts(inspect(Server.call(s, 5, 1000)))\n'
  'IO.puts(inspect(Server.restarts(s)))\n'
  'IO.puts(inspect(Server.call(s, 0, 1000)))\n'
  'IO.puts(inspect(Server.call(s, 0, 1000)))\n'
  'IO.puts(inspect(Server.call(s, 0, 1000)))\n'
  'IO.puts(inspect(Server.await(s, 1000)))\n'
  'IO.puts(inspect(Server.call(s, 1, 1000)))\n'
  'IO.puts(inspect(Server.restarts(s)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok(5)\nerror("server stopped: division by zero")\nok(2)\n1\nerror("server stopped: division by zero")\ner'
  b'ror("server stopped: division by zero")\nerror("server stopped: division by zero")\n{true, "restart_in'
  b'tensity"}\nerror("server is not running")\n3\n',
  b''),
 ('defmodule Example do\n  def main() do\nme: server[integer, integer] = Server.self()\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:32: Server.self is called from a process that is not a server\n  at Example.main (<stdin>:3'
  b')\n'),
 ('defmodule Example do\n  def main() do\nServer.continue(1)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:1: Server.continue is called from a process that is not a server\n  at Example.main (<stdin>:3)'
  b'\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  's = Server.start(0, fn(total: integer, d: integer): tuple[integer, integer] do\n'
  '  if d == 1 do\n'
  '    Server.continue("x")\n'
  '  end\n'
  '  {total, d}\n'
  'end)\n'
  'IO.puts(inspect(Server.call(s, 1, 1000)))\n'
  '  end\n'
  'end\n',
  0,
  b'error("server stopped: Server.continue is given a request of another type than its server\'s")\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  's = Server.start(0, fn(total: integer, d: integer): tuple[integer, integer] do\n'
  '  me: server[integer, integer] = Server.self()\n'
  '  IO.puts(inspect(Server.call(me, 1, 10)))\n'
  '  {total, d}\n'
  'end)\n'
  'IO.puts(inspect(Server.call(s, 1, 1000)))\n'
  '  end\n'
  'end\n',
  0,
  b'error("server stopped: a server cannot call itself")\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'counter = Server.start(0, fn(total: integer, amount: integer): tuple[integer, integer] do {total + '
  'amount, total + amount} end)\n'
  'IO.puts(inspect([Server.register(counter, :c1), Server.register(counter, :c1)]))\n'
  'found: option[server[integer, integer]] = Server.whereis(:c1)\n'
  'IO.puts(inspect(case found do\n'
  '  some(named) -> Server.call(named, 4, 1000)\n'
  '  none -> error("missing")\n'
  'end))\n'
  'other: option[server[string, string]] = Server.whereis(:c1)\n'
  'IO.puts(inspect(case other do\n'
  '  some(_) -> "found"\n'
  '  none -> "not found"\n'
  'end))\n'
  'p: option[pid[integer]] = Process.whereis(:c1)\n'
  'IO.puts(inspect(case p do\n'
  '  some(_) -> "found"\n'
  '  none -> "not found"\n'
  'end))\n'
  'IO.puts(inspect(Process.send_after(:c1, 10, 5) > 0))\n'
  'IO.puts(inspect(Process.send_after(:c1, "str", 5) > 0))\n'
  't = Server.send_after(counter, 100, 5)\n'
  'u = Server.send_after(counter, 1000, 500)\n'
  'IO.puts(inspect(Process.cancel_timer(u)))\n'
  'Process.sleep(60)\n'
  'IO.puts(inspect(Server.call(counter, 0, 1000)))\n'
  'IO.puts(inspect(Process.cancel_timer(t)))\n'
  'IO.puts(inspect(Server.stop(counter)))\n'
  'Process.sleep(10)\n'
  'IO.puts(inspect(Server.register(counter, :c1)))\n'
  'found2: option[server[integer, integer]] = Server.whereis(:c1)\n'
  'IO.puts(inspect(case found2 do\n'
  '  some(_) -> "found"\n'
  '  none -> "not found"\n'
  'end))\n'
  '  end\n'
  'end\n',
  0,
  b'[true, false]\nok(4)\n"not found"\n"not found"\ntrue\ntrue\ntrue\nok(114)\nfalse\ntrue\ntrue\n"not foun'
  b'd"\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'group = Supervisor.start("one", 3, 1000, [{"a", "permanent", fn(self: pid[integer]): integer do 0 end}], '
  '4)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:9: invalid supervision strategy\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'group = Supervisor.start("one_for_one", 3, 0, [{"a", "permanent", fn(self: pid[integer]): integer do 0 '
  'end}], 4)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:9: invalid supervision limits, capacity or empty children\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'group = Supervisor.start("one_for_one", 3, 10, [{"a", "permanent", fn(self: pid[integer]): integer do 0 '
  'end}, {"a", "permanent", fn(self: pid[integer]): integer do 0 end}], 4)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:9: invalid or duplicate child specification\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'group = Supervisor.start("one_for_one", 3, 10, [{"a", "permanent", fn(self: pid[integer]): integer do '
  'Process.sleep(1000) end}], 4)\n'
  'Supervisor.child(group, "zz")\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:1: unknown supervised child: zz\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'group = Supervisor.start_link("one_for_one", 1, 1000, [{"a", "permanent", fn(self: pid[integer]): integer '
  'do raise("bad") end}], 4)\n'
  'Process.sleep(500)\n'
  'IO.puts("no")\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:9: restart_intensity\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'tree = Supervisor.start("one_for_one", 3, 1000, [Supervisor.server(:doc_total, "permanent", 0, fn(total: '
  'integer, n: integer): tuple[integer, integer] do {total + n, div(10, n)} end)], 1)\n'
  'found: option[server[integer, integer]] = Server.whereis(:doc_total)\n'
  'case found do\n'
  '  some(total) ->\n'
  '    IO.puts(inspect(Server.call(total, 5, 1000)))\n'
  '    IO.puts(inspect(Server.call(total, 0, 1000)))\n'
  '  none -> IO.puts("not found")\n'
  'end\n'
  'Process.sleep(50)\n'
  'again: option[server[integer, integer]] = Server.whereis(:doc_total)\n'
  'IO.puts(inspect(case again do\n'
  '  some(total) -> Server.call(total, 2, 1000)\n'
  '  none -> error("not found")\n'
  'end))\n'
  'IO.puts(inspect([Supervisor.restarts(tree), Process.count()]))\n'
  'IO.puts(inspect(Supervisor.stop(tree, 1000)))\n'
  'IO.puts(inspect(Process.count()))\n'
  '  end\n'
  'end\n',
  0,
  b'ok(2)\nerror("server stopped: division by zero")\nok(5)\n[1, 4]\ntrue\n1\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'Supervisor.server(:x, "sometimes", 0, fn(total: integer, n: integer): tuple[integer, integer] do {total + '
  'n, total} end)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:1: Supervisor.server: the restart policy is "permanent", "transient" or "temporary", not "some'
  b'times"\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n  def main() do\nd = DynamicSupervisor.start_link([max_kids: 2])\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:5: unknown option :max_kids; DynamicSupervisor.start_link takes max_restarts:, max_seconds: an'
  b'd max_children:\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'd = DynamicSupervisor.start_link()\n'
  'DynamicSupervisor.start_child(d, fn(self: pid[integer]): integer do 1 end, :sometimes)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b"<stdin>:4:1: a child's restart is permanent, transient or temporary\n  at Example.main (<stdin>:4)\n"),
 ('defmodule Example do\n'
  '  def main() do\n'
  'd = DynamicSupervisor.start_link()\n'
  's = DynamicSupervisor.start_server(d, 0, fn(total: integer, n: integer): tuple[integer, integer] do '
  '{total + n, div(10, n)} end)\n'
  'case s do\n'
  '  ok(server) ->\n'
  '    IO.puts(inspect([Server.call(server, 5, 100), Server.call(server, 0, 100), Server.call(server, 2, '
  '100)]))\n'
  '    IO.puts(inspect([Server.restarts(server), DynamicSupervisor.count_children(d), Process.count()]))\n'
  '    IO.puts(inspect(Server.stop(server)))\n'
  '    Process.sleep(20)\n'
  '    IO.puts(inspect([DynamicSupervisor.count_children(d), Process.count()]))\n'
  '  error(e) -> IO.puts(e)\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'[ok(2), error("server stopped: division by zero"), ok(5)]\n[1, 1, 4]\ntrue\n[0, 2]\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'tasks = Task.Supervisor.start_link()\n'
  'IO.puts(inspect(Task.await(Task.Supervisor.async(tasks, fn -> 6 * 7 end))))\n'
  't = Task.Supervisor.async_nolink(tasks, fn -> div(1, 0) end)\n'
  'IO.puts(inspect(Task.yield(t, 1000)))\n'
  'ok(u) = Task.Supervisor.start_child(tasks, fn -> Process.sleep(60000) end)\n'
  'IO.puts(inspect(length(Task.Supervisor.children(tasks))))\n'
  'IO.puts(inspect([Task.Supervisor.terminate_child(tasks, u), Task.Supervisor.terminate_child(tasks, u)]))\n'
  'IO.puts(inspect(Task.Supervisor.children(tasks)))\n'
  'limited = Task.Supervisor.start_link([max_children: 1])\n'
  'ok(v) = Task.Supervisor.start_child(limited, fn -> Process.sleep(60000) end)\n'
  'IO.puts(inspect(case Task.Supervisor.start_child(limited, fn -> 1 end) do\n'
  '  ok(_) -> "ok"\n'
  '  error(e) -> e\n'
  'end))\n'
  'IO.puts(inspect(DynamicSupervisor.stop(limited)))\n'
  'IO.puts(inspect(case Task.Supervisor.start_child(limited, fn -> 1 end) do\n'
  '  ok(_) -> "ok"\n'
  '  error(e) -> e\n'
  'end))\n'
  'x = Task.Supervisor.async(limited, fn -> 1 end)\n'
  '  end\n'
  'end\n',
  2,
  b'42\nsome(error("division by zero"))\n1\n[true, false]\n[]\n"max_children"\ntrue\n"supervisor is not run'
  b'ning"\n',
  b'<stdin>:22:5: Task.Supervisor.async: supervisor is not running\n  at Example.main (<stdin>:22)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'tasks = Task.Supervisor.start_link()\n'
  't = Task.Supervisor.async(tasks, fn -> div(1, 0) end)\n'
  'Process.sleep(100)\n'
  'IO.puts("no")\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:40: division by zero\n  at Example.main <closure> (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'r: registry[string, integer] = Registry.start_link([keys: :some])\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:32: keys: is :unique or :duplicate, not :some\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'r: registry[string, integer] = Registry.start_link([key: :unique])\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:32: unknown option :key; Registry.start_link takes keys:\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'r: registry[string, integer] = Registry.start_link([])\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:32: Registry.start_link needs keys: :unique or keys: :duplicate\n  at Example.main (<stdin>'
  b':3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'r: registry[string, integer] = Registry.start_link([keys: :unique], [partitions: 0])\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:32: partitions: is from 1 to 1024\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'r: registry[string, integer] = Registry.start_link([keys: :unique], [parts: 2])\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:32: unknown option :parts; the numbers Registry.start_link takes are partitions:\n  at Example.'
  b'main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[tuple[string, integer]] = Process.self(8)\n'
  'Process.send(me, {"started", 1}, 100)\n'
  'Process.send(me, {"finished", 42}, 100)\n'
  'assert_receive(me, {"finished", result})\n'
  'IO.puts(inspect(result))\n'
  'assert_receive(me, {_, count} when count < 10, 500, "the start was never reported")\n'
  'IO.puts(inspect(count))\n'
  'IO.puts(inspect(Process.receive(me, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'42\n1\n{false, {"", 0}}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[tuple[string, integer]] = Process.self(8)\n'
  'Process.send(me, {"started", 1}, 100)\n'
  'Process.send(me, {"other", 2}, 100)\n'
  'assert_receive(me, {"finished", result})\n'
  'IO.puts(inspect(result))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:6:1: no message matching the pattern arrived within 100ms\n     pattern: {"finished", result}'
  b'\n     mailbox: {"started", 1}, {"other", 2}\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[tuple[string, integer]] = Process.self(8)\n'
  'want = 7\n'
  'name = "x"\n'
  'Process.send(me, {"x", 1}, 100)\n'
  'assert_receive(me, {^name, ^want}, 20, "nothing came")\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:7:1: nothing came\n     pattern: {^name, ^want}\n     pinned:  name = "x"\n     pinned:  want ='
  b' 7\n     mailbox: {"x", 1}\n  at Example.main (<stdin>:7)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(4)\n'
  'Process.send(me, 7, 100)\n'
  'assert_received(me, n when n > 5)\n'
  'IO.puts(inspect(n))\n'
  'assert_received(me, 9)\n'
  '  end\n'
  'end\n',
  2,
  b'7\n',
  b'<stdin>:7:1: no message matching the pattern has arrived\n     pattern: 9\n     mailbox: empty\n  at Ex'
  b'ample.main (<stdin>:7)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(4)\n'
  'assert_received(me, 9, "nine is missing")\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:1: nine is missing\n     pattern: 9\n     mailbox: empty\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[string] = Process.self(4)\n'
  'Process.send(me, "ok", 100)\n'
  'refute_receive(me, "error", 10)\n'
  'assert_receive(me, "ok")\n'
  'refute_receive(me, _, 10)\n'
  'Process.send(me, "late", 100)\n'
  'refute_receive(me, _, 10)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:9:1: a message matching the pattern arrived, but none was expected\n     pattern: _\n     rece'
  b'ived: "late"\n  at Example.main (<stdin>:9)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[string] = Process.self(4)\n'
  'refute_received(me, "x")\n'
  'Process.send(me, "x", 100)\n'
  'Process.send(me, "y", 100)\n'
  'refute_received(me, "y", "no y please")\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:7:1: no y please\n     pattern: "y"\n     received: "y"\n  at Example.main (<stdin>:7)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(40)\n'
  'Enum.each(1..15, fn i -> Process.send(me, i, 10) end)\n'
  'assert_receive(me, 99, 5)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:5:1: no message matching the pattern arrived within 5ms\n     pattern: 99\n     mailbox: (last'
  b' 10 of 15) 6, 7, 8, 9, 10, 11, 12, 13, 14, 15\n  at Example.main (<stdin>:5)\n'),
 ('defmodule Example do\n'
  '  def wait(me: pid[tuple[atom, integer]]): integer do\n'
  '    assert_receive(me,\n'
  '      {:done, n},\n'
  '      50)\n'
  '    n + 1\n'
  '  end\n'
  '  def main() do\n'
  '    me: pid[tuple[atom, integer]] = Process.self(4)\n'
  '    Process.send(me, {:skip, 1}, 10)\n'
  '    Process.send(me, {:done, 5}, 10)\n'
  '    IO.puts(inspect(wait(me)))\n'
  '    IO.puts(inspect(Process.receive(me, 0)))\n'
  '    IO.puts(inspect(wait(me)))\n'
  '  end\n'
  'end\n',
  2,
  b'6\n{true, {:skip, 1}}\n',
  b'<stdin>:3:5: no message matching the pattern arrived within 50ms\n     pattern: {:done, n}\n     mailb'
  b'ox: empty\n  at Example.wait (<stdin>:3)\n  at Example.main (<stdin>:14)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(1000) end, 1)\n'
  'assert_receive(w, 1)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:1: only the mailbox owner may receive\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'parent: pid[string] = Process.self(8)\n'
  'worker: pid[string] = Process.spawn(fn(self: pid[string]): integer do\n'
  '  {_, text} = Process.receive(self, 1000)\n'
  '  Process.send(parent, String.upcase(text), 1000)\n'
  '  0\n'
  'end, 8)\n'
  'Process.send(worker, "hello", 1000)\n'
  'IO.puts(inspect(Process.receive(parent, 1000) == {true, "HELLO"}))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule Example do\n'
  '  type Request do\n'
  '    add(amount: integer)\n'
  '    read\n'
  '  end\n'
  '\n'
  '  def handle(total: integer, request: Request): tuple[integer, integer] do\n'
  '    case request do\n'
  '      Request.add(amount) -> {total + amount, total + amount}\n'
  '      Request.read -> {total, total}\n'
  '    end\n'
  '  end\n'
  '\n'
  '  def main() do\n'
  '    squares = Task.async_stream(1..4, fn n -> n * n end) |> Enum.to_list()\n'
  '    IO.puts(inspect(squares))\n'
  '    counter = Server.start(0, &handle)\n'
  '    IO.puts(inspect(Server.call(counter, Request.add(5), 1000)))\n'
  '    IO.puts(inspect(Server.call(counter, Request.read, 1000)))\n'
  '    IO.puts(inspect(Server.stop(counter)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 4, 9, 16]\nok(5)\nok(5)\ntrue\n',
  b''),
 ('defmodule Example do\n'
  '  def pong(self: pid[tuple[pid[integer], integer]]): integer do\n'
  '    case Process.receive(self, 1000) do\n'
  '      {true, {from, n}} ->\n'
  '        Process.send(from, n + 1, 100)\n'
  '        if n >= 2000 do 0 else pong(self) end\n'
  '      {false, _} -> 1\n'
  '    end\n'
  '  end\n'
  '  def ping(me: pid[integer], other: pid[tuple[pid[integer], integer]], n: integer): integer do\n'
  '    Process.send(other, {me, n}, 100)\n'
  '    case Process.receive(me, 1000) do\n'
  '      {true, m} -> if m > 2000 do m else ping(me, other, m) end\n'
  '      {false, _} -> -1\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    me: pid[integer] = Process.self(4)\n'
  '    other: pid[tuple[pid[integer], integer]] = Process.spawn(&pong/1, 4)\n'
  '    IO.puts(inspect(ping(me, other, 0)))\n'
  '    IO.puts(inspect(Process.await(other, 1000)))\n'
  '  end\n'
  'end\n',
  0,
  b'2001\n{true, "normal"}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  '    me: pid[integer] = Process.self(1000)\n'
  '    Enum.each(1..300, fn i ->\n'
  '      Process.spawn(fn(self: pid[integer]): integer do\n'
  '        Process.send(me, i, 100)\n'
  '        0\n'
  '      end, 1)\n'
  '    end)\n'
  '    Process.sleep(20)\n'
  '    total = Enum.reduce(1..300, 0, fn i, acc ->\n'
  '      {_, v} = Process.receive(me, 100)\n'
  '      acc + v\n'
  '    end)\n'
  '    IO.puts(inspect(total))\n'
  '    IO.puts(inspect(Process.count()))\n'
  '  end\n'
  'end\n',
  0,
  b'45150\n1\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'a: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(30) end, 1)\n'
  'b: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 5 end, 1)\n'
  'ra = Process.monitor(a)\n'
  'rb = Process.monitor(b)\n'
  '{_, r1, i1, why1} = Process.event(1000)\n'
  '{_, r2, i2, why2} = Process.event(1000)\n'
  'IO.puts(inspect([r1 == rb, i1 == Process.id(b), r2 == ra, i2 == Process.id(a)]))\n'
  'IO.puts(inspect([why1, why2]))\n'
  '  end\n'
  'end\n',
  0,
  b'[true, true, true, true]\n["exit:5", "normal"]\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'a: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  b: pid[integer] = Process.spawn(fn(inner: pid[integer]): integer do\n'
  '    Process.sleep(10)\n'
  '    raise("inner failed")\n'
  '  end, 1)\n'
  '  Process.link(b)\n'
  '  Process.sleep(60000)\n'
  'end, 1)\n'
  'IO.puts(inspect(Process.await(a, 1000)))\n'
  'IO.puts(Process.report(a))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, "linked: inner failed"}\n<stdin>:6:5: inner failed\n  at Example.main <closure> (<stdin>:6)\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  try do\n'
  '    Process.sleep(60000)\n'
  '  rescue\n'
  '    m -> IO.puts("rescued " <> m)\n'
  '    1\n'
  '  after\n'
  '    IO.puts("after ran")\n'
  '  end\n'
  'end, 1)\n'
  'Process.sleep(5)\n'
  'IO.puts(inspect(Process.stop(w)))\n'
  'IO.puts(inspect(Process.await(w, 1000)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nafter ran\n{true, "shutdown"}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[string] = Process.self(4)\n'
  't1 = Process.send_after(me, "late", 60000)\n'
  't2 = Process.send_after(me, "soon", 10)\n'
  'IO.puts(inspect([Process.cancel_timer(t1), Process.cancel_timer(t1)]))\n'
  'IO.puts(inspect(Process.receive(me, 1000)))\n'
  'IO.puts(inspect(Process.cancel_timer(t2)))\n'
  'IO.puts(inspect(Process.register(me, :inbox)))\n'
  'IO.puts(inspect(Process.send_after(:inbox, "named", 10) > 0))\n'
  'IO.puts(inspect(Process.send_after(:inbox, 5, 10) > 0))\n'
  'IO.puts(inspect(Process.receive(me, 1000)))\n'
  'IO.puts(inspect(Process.receive(me, 50)))\n'
  'IO.puts(inspect([Process.unregister(:inbox), Process.unregister(:inbox)]))\n'
  'found: option[pid[string]] = Process.whereis(:inbox)\n'
  'IO.puts(inspect(case found do\n'
  '  some(_) -> "yes"\n'
  '  none -> "no"\n'
  'end))\n'
  '  end\n'
  'end\n',
  0,
  b'[true, false]\n{true, "soon"}\nfalse\ntrue\ntrue\ntrue\n{true, "named"}\n{false, ""}\n[true, false]\n"no"'
  b'\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(1)\n'
  'a: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 0 end, 1)\n'
  'r = Process.monitor(a)\n'
  'b: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 0 end, 1)\n'
  't = Task.async(fn -> 1 end)\n'
  'c: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 0 end, 1)\n'
  'IO.puts(inspect([Process.id(me), Process.id(a), r, Process.id(b), Process.id(c)]))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 3, 4, 6]\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(60000) end, 1)\n'
  'IO.puts("bye")\n'
  'System.halt(3)\n'
  '  end\n'
  'end\n',
  3,
  b'bye\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[PortEvent] = Process.self(16)\n'
  'IO.puts(inspect(case Port.open("sort", Enum.take([""], 0), me) do\n'
  '  ok(sorter) ->\n'
  '    Port.command(sorter, "pear\\napple\\n")\n'
  '    Port.close(sorter)\n'
  '  error(_) -> false\n'
  'end))\n'
  'assert_receive(me, PortEvent.data(first), 5000)\n'
  'IO.puts(first)\n'
  'assert_receive(me, PortEvent.data("pear"), 5000)\n'
  'assert_receive(me, PortEvent.exit(status), 5000)\n'
  'IO.puts(inspect(status))\n'
  '  end\n'
  'end\n',
  0,
  b'true\napple\n0\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[PortEvent] = Process.self(16)\n'
  'ok(a) = Port.open("sh", ["-c", "printf \'one\\\\ntwo\'; echo err 1>&2"], me, [mode: :binary, stderr: '
  ':discard])\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'ok(b) = Port.open("sh", ["-c", "echo out; echo err 1>&2"], me, [stderr: :discard])\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'ok(c) = Port.open("sh", ["-c", "echo out; echo shown 1>&2"], me, [stderr: :inherit])\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, PortEvent.data("one\\ntwo")}\n{true, PortEvent.exit(0)}\n{true, PortEvent.data("out")}\n{true, Po'
  b'rtEvent.exit(0)}\n{true, PortEvent.data("out")}\n{true, PortEvent.exit(0)}\n',
  b'shown\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[PortEvent] = Process.self(16)\n'
  'ok(p) = Port.open("cat", [], me, [packet: 2])\n'
  'IO.puts(inspect([Port.command(p, "hello"), Port.command(p, ""), Port.command(p, "wide é")]))\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'some(i) = Port.info(p)\n'
  'IO.puts(inspect({i.input, i.output}))\n'
  'IO.puts(inspect(Port.close(p)))\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  '  end\n'
  'end\n',
  0,
  b'[true, true, true]\n{true, PortEvent.data("hello")}\n{true, PortEvent.data("")}\n{true, PortEvent.data('
  b'"wide \xc3\xa9")}\n{18, 12}\ntrue\n{true, PortEvent.exit(0)}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[PortEvent] = Process.self(16)\n'
  'Port.open("cat", [], me, [packet: 3])\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:1: Port.open takes packet: 1, 2 or 4\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[PortEvent] = Process.self(16)\n'
  'Port.open("cat", [], me, [mode: :lines])\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:1: Port.open takes mode: :line or :binary and stderr: :merge, :discard or :inherit\n  at Exampl'
  b'e.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[PortEvent] = Process.self(16)\n'
  'owner: pid[PortEvent] = Process.spawn(fn(self: pid[PortEvent]): integer do\n'
  '  ok(p) = Port.open("cat", [], self)\n'
  '  Port.monitor(p, me)\n'
  '  Process.send(me, PortEvent.data("opened"), 100)\n'
  '  Process.sleep(60000)\n'
  'end, 4)\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'IO.puts(inspect(Process.stop(owner)))\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'IO.puts(inspect(Process.count()))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, PortEvent.data("opened")}\ntrue\n{true, PortEvent.exit(-1)}\n1\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[PortEvent] = Process.self(16)\n'
  'ok(p) = Port.open("cat", [], me)\n'
  'IO.puts(inspect(Port.command(p, "x\\n")))\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'IO.puts(inspect(Process.count()))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n{true, PortEvent.data("x")}\n2\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[PortEvent] = Process.self(16)\n'
  'ok(p) = Port.open("sh", ["-c", "exit 7"], me)\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'ok(q) = Port.open("sh", ["-c", "kill -9 $$"], me)\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'ok(r) = Port.open("true", [], me)\n'
  'IO.puts(inspect(Process.receive(me, 5000)))\n'
  'IO.puts(inspect([Port.monitor(r, me), Port.kill(r), Port.info(r) == none, Port.os_pid(r) > 0]))\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, PortEvent.exit(7)}\n{true, PortEvent.exit(-1)}\n{true, PortEvent.exit(0)}\n[false, false, true, '
  b'true]\n#portHandle<>\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  '    me: pid[PortEvent] = Process.self(8)\n'
  '    r = Port.open("alchem-no-such-program", [], me)\n'
  '    IO.puts(inspect(r))\n'
  '    r2 = Port.open("./nothere", [], me)\n'
  '    IO.puts(inspect(r2))\n'
  '    r3 = Port.open("/etc/passwd", [], me)\n'
  '    IO.puts(inspect(r3))\n'
  '    ok(p) = Port.open("sh", ["-c", "echo out; echo err 1>&2; printf \'part\'; exit 3"], me)\n'
  '    IO.puts(inspect(Port.info(p) != none))\n'
  '    IO.puts(inspect(Process.receive(me, 2000)))\n'
  '    IO.puts(inspect(Process.receive(me, 2000)))\n'
  '    IO.puts(inspect(Process.receive(me, 2000)))\n'
  '    IO.puts(inspect(Process.receive(me, 2000)))\n'
  '    IO.puts(inspect(Port.info(p)))\n'
  '    IO.puts(inspect([Port.command(p, "x"), Port.close(p), Port.close(p), Port.command(p, "x"), '
  'Port.kill(p), Port.monitor(p, me)]))\n'
  '    ok(q) = Port.open("cat", [], me)\n'
  '    IO.puts(inspect(Port.command(q, "hello\\r\\nworld")))\n'
  '    IO.puts(inspect(Process.receive(me, 2000)))\n'
  '    some(i) = Port.info(q)\n'
  '    IO.puts(inspect({i.name, i.os_pid > 0}))\n'
  '    IO.puts(inspect(Port.kill(q)))\n'
  '    IO.puts(inspect(Process.receive(me, 2000)))\n'
  '    IO.puts(inspect(Process.receive(me, 2000)))\n'
  '    IO.puts(inspect(Process.count()))\n'
  '  end\n'
  'end\n',
  0,
  b'error("exec: \\"alchem-no-such-program\\": executable file not found in $PATH")\nerror("fork/exec ./not'
  b'here: no such file or directory")\nerror("fork/exec /etc/passwd: permission denied")\ntrue\n{true, Port'
  b'Event.data("out")}\n{true, PortEvent.data("err")}\n{true, PortEvent.data("part")}\n{true, PortEvent.exi'
  b't(3)}\nnone\n[false, true, false, false, false, false]\ntrue\n{true, PortEvent.data("hello")}\n{"cat", tr'
  b'ue}\ntrue\n{true, PortEvent.data("world")}\n{true, PortEvent.exit(-1)}\n1\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  '    me: pid[integer] = Process.self(5000)\n'
  '    Enum.each(1..3000, fn i ->\n'
  '      Process.spawn(fn(self: pid[integer]): integer do\n'
  '        Process.sleep(rem(i, 7))\n'
  '        Process.send(me, 1, 1000)\n'
  '        0\n'
  '      end, 1)\n'
  '    end)\n'
  '    total = Enum.reduce(1..3000, 0, fn i, acc ->\n'
  '      {_, v} = Process.receive(me, 5000)\n'
  '      acc + v\n'
  '    end)\n'
  '    IO.puts(inspect(total))\n'
  '    Process.sleep(5)\n'
  '    IO.puts(inspect(Process.count()))\n'
  '  end\n'
  'end\n',
  0,
  b'3000\n1\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(4)\n'
  'Process.send_after(me, 1, 60000)\n'
  'Process.send_after(me, 2, 5)\n'
  'IO.puts(inspect(Process.receive(me, 1000)))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, 2}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(1)\n'
  'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  Process.send(me, 1, 1000)\n'
  '  IO.puts(inspect(Process.send(me, 2, 1000)))\n'
  '  IO.puts(inspect(Process.send(me, 3, 10)))\n'
  '  0\n'
  'end, 1)\n'
  'Process.sleep(20)\n'
  'IO.puts(inspect(Process.receive(me, 100)))\n'
  'Process.sleep(50)\n'
  'IO.puts(inspect(Process.receive(me, 100)))\n'
  'IO.puts(inspect(Process.receive(me, 100)))\n'
  'IO.puts(inspect(Process.await(w, 100)))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, 1}\ntrue\nfalse\n{true, 2}\n{false, 0}\n{true, "normal"}\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  '    outer = Supervisor.start("one_for_one", 2, 1000, [{"inner", "permanent", fn(self: pid[integer]): '
  'integer do\n'
  '      inner = Supervisor.start_link("one_for_one", 0, 1000, [{"leaf", "permanent", fn(leaf: '
  'pid[integer]): integer do\n'
  '        {_, n} = Process.receive(leaf, 60000)\n'
  '        n\n'
  '      end}], 2)\n'
  '      {_, why} = Supervisor.await(inner, 60000)\n'
  '      IO.puts("inner ended: " <> why)\n'
  '      1\n'
  '    end}], 2)\n'
  '    Process.sleep(20)\n'
  '    IO.puts(inspect([Process.count(), Supervisor.restarts(outer)]))\n'
  '    IO.puts(inspect(Supervisor.stop(outer, 1000)))\n'
  '    IO.puts(inspect(Process.count()))\n'
  '  end\n'
  'end\n',
  0,
  b'[5, 0]\ntrue\n1\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  try do\n'
  '    Process.sleep(60000)\n'
  '  after\n'
  '    IO.puts("cleanup")\n'
  '  end\n'
  'end, 1)\n'
  'Process.sleep(5)\n'
  'IO.puts("bye")\n'
  'System.stop(3)\n'
  'IO.puts("not here")\n'
  '  end\n'
  'end\n',
  3,
  b'bye\ncleanup\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  try do\n'
  '    Process.sleep(60000)\n'
  '  after\n'
  '    IO.puts("cleanup")\n'
  '  end\n'
  'end, 1)\n'
  'Process.sleep(5)\n'
  'throw(1)\n'
  '  end\n'
  'end\n',
  2,
  b'cleanup\n',
  b'<stdin>:11:1: uncaught throw\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  'me: pid[integer] = Process.self(10)\n'
  'a: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '  IO.puts("a")\n'
  '  0\n'
  'end, 1)\n'
  'Process.await(a, 100)\n'
  'IO.puts("main")\n'
  '  end\n'
  'end\n',
  0,
  b'a\nmain\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'IO.puts(inspect(Process.loop([], fn(l: list[integer]): tuple[boolean, list[integer]] do {length(l) < 3, l '
  '++ [1]} end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 1, 1, 1]\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'IO.puts(inspect(try do\n'
  '  Enum.map([1], fn x -> raise("no #{x}") end)\n'
  'rescue\n'
  '  m -> []\n'
  'end))\n'
  '  end\n'
  'end\n',
  0,
  b'[]\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  'rooms: registry[string, integer] = Registry.start_link([keys: :duplicate])\n'
  'IO.puts(inspect([Registry.register(rooms, "lobby", 1), Registry.register(rooms, "hall", 2)]))\n'
  'IO.puts(inspect(Enum.map(Registry.select(rooms, fn key, _, _ -> key == "hall" end), fn {key, _, value} -> '
  '{key, value} end)))\n'
  'IO.puts(inspect(length(Registry.select(rooms, fn _, _, _ -> true end))))\n'
  '  end\n'
  'end\n',
  0,
  b'[ok({}), ok({})]\n[{"hall", 2}]\n2\n',
  b''),
 ('defmodule Example do\n'
  '  def echo(self: pid[integer], total: integer): integer do\n'
  '    case Process.receive(self, 1000) do\n'
  '      {true, 0} -> total\n'
  '      {true, n} -> echo(self, total + 1)\n'
  '      {false, _} -> -1\n'
  '    end\n'
  '  end\n'
  '  def feed(to: pid[integer], n: integer): integer do\n'
  '    if n == 0 do 0 else\n'
  '      Process.send(to, n, 1000)\n'
  '      feed(to, n - 1)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
  '      if echo(self, 0) == 1000000 do 7 else 1 end\n'
  '    end, 16)\n'
  '    feed(w, 1000000)\n'
  '    Process.send(w, 0, 1000)\n'
  '    IO.puts(inspect(Process.await(w, 60000)))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, "exit:7"}\n',
  b''),
 ('defmodule Example do\n'
  '  def deep(n: integer): integer do\n'
  '    if n == 0 do 0 else 1 + deep(n - 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    Process.trap_exits(true)\n'
  '    a = Agent.start(fn -> 0 end)\n'
  '    IO.puts(inspect(Agent.get(a, fn x -> deep(99998) end)))\n'
  '    s = Server.start(0, fn(t: integer, n: integer): tuple[integer, integer] do {t, deep(n)} end)\n'
  '    IO.puts(inspect(Server.call(s, 99998, 5000)))\n'
  '    IO.puts(inspect(Server.call(s, 99999, 5000)))\n'
  '    r = try do\n'
  '      Agent.get(a, fn x -> deep(99999) end)\n'
  '    rescue\n'
  '      m -> -1\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'99998\nok(99998)\nerror("server stopped: call depth exceeded")\n-1\n',
  b'')]
# programs the pinned compiler rejects
REJECTS=['defmodule Example do\n'
 '  def main() do\n'
 'counter = Server.start(0, fn(total: integer, amount: integer): tuple[integer, integer] do {total + amount, '
 'total + amount} end)\n'
 'IO.puts(inspect([Server.call(counter, 5, 1000), Server.call(counter, 2, 1000)]))\n'
 'IO.puts(inspect(Server.cast(counter, 5)))\n'
 'IO.puts(inspect(Server.call(counter, 0, 1000)))\n'
 'IO.puts(inspect([Server.alive(counter), Server.restarts(counter)]))\n'
 'IO.puts(inspect(Server.stop(counter)))\n'
 'IO.puts(inspect(Server.stop(counter)))\n'
 'IO.puts(inspect(Server.await(counter, 1000)))\n'
 'IO.puts(inspect([Server.alive(counter), Server.cast(counter, 1)]))\n'
 'IO.puts(inspect(Server.call(counter, 0, 1000)))\n'
 'IO.puts(inspect(counter))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def worker(name: string, log: pid[string]): fn[pid[integer], integer] do\n'
 '    fn(self: pid[integer]): integer do\n'
 '      Process.send(log, name <> " up", 100)\n'
 '      {_, n} = Process.receive(self, 60000)\n'
 '      n\n'
 '    end\n'
 '  end\n'
 '  def drain(me: pid[string], acc: list[string]): list[string] do\n'
 '    case Process.receive(me, 30) do\n'
 '      {true, m} -> drain(me, acc ++ [m])\n'
 '      {false, _} -> acc\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    log: pid[string] = Process.self(100)\n'
 '    group = Supervisor.start("one_for_one", 3, 1000, [{"a", "permanent", worker("a", log)}, {"b", '
 '"transient", worker("b", log)}, {"c", "temporary", worker("c", log)}], 4)\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Supervisor.children(group)))\n'
 '    IO.puts(inspect(Process.send(Supervisor.child(group, "a"), 0, 100)))\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Process.send(Supervisor.child(group, "b"), 0, 100)))\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Process.send(Supervisor.child(group, "b"), 1, 100)))\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Process.send(Supervisor.child(group, "c"), 1, 100)))\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Supervisor.children(group)))\n'
 '    IO.puts(inspect([Supervisor.restarts(group), Supervisor.alive(group), Process.count()]))\n'
 '    IO.puts(inspect(Supervisor.stop(group, 1000)))\n'
 '    IO.puts(inspect([Supervisor.await(group, 100), Supervisor.alive(group), Process.count()]))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def worker(name: string, log: pid[string]): fn[pid[integer], integer] do\n'
 '    fn(self: pid[integer]): integer do\n'
 '      Process.send(log, name <> " up", 100)\n'
 '      {_, n} = Process.receive(self, 60000)\n'
 '      n\n'
 '    end\n'
 '  end\n'
 '  def drain(me: pid[string], acc: list[string]): list[string] do\n'
 '    case Process.receive(me, 30) do\n'
 '      {true, m} -> drain(me, acc ++ [m])\n'
 '      {false, _} -> acc\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    log: pid[string] = Process.self(100)\n'
 '    group = Supervisor.start("rest_for_one", 3, 1000, [{"a", "permanent", worker("a", log)}, {"b", '
 '"transient", worker("b", log)}, {"c", "temporary", worker("c", log)}], 4)\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Process.send(Supervisor.child(group, "b"), 1, 100)))\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Supervisor.children(group)))\n'
 '    all = Supervisor.start("one_for_all", 1, 1000, [{"x", "permanent", worker("x", log)}, {"y", '
 '"permanent", worker("y", log)}], 4)\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Process.send(Supervisor.child(all, "y"), 1, 100)))\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Process.send(Supervisor.child(all, "y"), 1, 100)))\n'
 '    IO.puts(inspect(drain(log, [])))\n'
 '    IO.puts(inspect(Supervisor.await(all, 500)))\n'
 '    IO.puts(inspect([Supervisor.restarts(all), Supervisor.alive(all)]))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'd = DynamicSupervisor.start_link()\n'
 'me: pid[string] = Process.self(10)\n'
 'r = DynamicSupervisor.start_child(d, fn(self: pid[integer]): integer do\n'
 '  Process.send(me, "up", 10)\n'
 '  {_, n} = Process.receive(self, 60000)\n'
 '  n\n'
 'end)\n'
 'IO.puts(inspect(Process.receive(me, 100)))\n'
 'IO.puts(inspect([DynamicSupervisor.count_children(d), length(DynamicSupervisor.which_children(d)), '
 'DynamicSupervisor.restarts(d), Process.count()]))\n'
 'case r do\n'
 '  ok(p) ->\n'
 '    IO.puts(inspect(Process.send(p, 1, 10)))\n'
 '    IO.puts(inspect(Process.receive(me, 100)))\n'
 '    IO.puts(inspect([DynamicSupervisor.count_children(d), DynamicSupervisor.restarts(d), '
 'Process.alive(p)]))\n'
 '    IO.puts(inspect(DynamicSupervisor.terminate_child(d, p)))\n'
 '  error(e) -> IO.puts(e)\n'
 'end\n'
 'IO.puts(inspect([DynamicSupervisor.count_children(d), DynamicSupervisor.restarts(d), Process.count()]))\n'
 'IO.puts(inspect(DynamicSupervisor.alive(d)))\n'
 'IO.puts(inspect(DynamicSupervisor.stop(d)))\n'
 'IO.puts(inspect([DynamicSupervisor.alive(d), Process.count()]))\n'
 'IO.puts(inspect(DynamicSupervisor.stop(d)))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'd = DynamicSupervisor.start_link([max_children: 2, max_restarts: 1, max_seconds: 1])\n'
 'a = DynamicSupervisor.start_child(d, fn(self: pid[integer]): integer do Process.sleep(60000) end, '
 ':temporary)\n'
 'b = DynamicSupervisor.start_child(d, fn(self: pid[integer]): integer do\n'
 '  {_, n} = Process.receive(self, 60000)\n'
 '  n\n'
 'end, :transient)\n'
 'c = DynamicSupervisor.start_child(d, fn(self: pid[integer]): integer do Process.sleep(60000) end)\n'
 'IO.puts(inspect(case c do\n'
 '  ok(_) -> "started"\n'
 '  error(e) -> e\n'
 'end))\n'
 'case b do\n'
 '  ok(p) ->\n'
 '    IO.puts(inspect(Process.send(p, 0, 10)))\n'
 '    Process.sleep(20)\n'
 '    IO.puts(inspect([DynamicSupervisor.count_children(d), DynamicSupervisor.restarts(d)]))\n'
 '  error(e) -> IO.puts(e)\n'
 'end\n'
 'e = DynamicSupervisor.start_child(d, fn(self: pid[integer]): integer do 1 end, :permanent)\n'
 'Process.sleep(50)\n'
 'IO.puts(inspect([DynamicSupervisor.alive(d), DynamicSupervisor.restarts(d), Process.count()]))\n'
 'f = DynamicSupervisor.start_child(d, fn(self: pid[integer]): integer do 1 end)\n'
 'IO.puts(inspect(case f do\n'
 '  ok(_) -> "started"\n'
 '  error(e) -> e\n'
 'end))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'names: registry[atom, integer] = Registry.start_link([keys: :unique])\n'
 'IO.puts(inspect([Registry.register(names, :alpha, 1), Registry.register(names, :alpha, 2), '
 'Registry.register(names, :beta, 3)]))\n'
 'me: pid[string] = Process.self(4)\n'
 'IO.puts(inspect([Registry.lookup(names, :alpha), Registry.lookup(names, :gamma)]))\n'
 'IO.puts(inspect(Registry.entries(names, :alpha) == [{Process.id(me), 1}]))\n'
 'IO.puts(inspect(Enum.sort(Registry.keys(names, me))))\n'
 'IO.puts(inspect(Registry.values(names, :beta, me)))\n'
 'IO.puts(inspect([Registry.count(names), Registry.partitions(names)]))\n'
 'IO.puts(inspect(Registry.update_value(names, :alpha, fn n -> n + 10 end)))\n'
 'IO.puts(inspect(Registry.update_value(names, :gamma, fn n -> n + 10 end)))\n'
 'IO.puts(inspect([Registry.unregister(names, :alpha), Registry.unregister(names, :alpha)]))\n'
 'IO.puts(inspect(Registry.count(names)))\n'
 'w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do\n'
 '  IO.puts(inspect(Registry.register(names, :beta, 9)))\n'
 '  IO.puts(inspect(Registry.register(names, :worker, 9)))\n'
 '  Process.receive(self, 60000)\n'
 '  0\n'
 'end, 1)\n'
 'Process.sleep(20)\n'
 'IO.puts(inspect([Registry.count(names), Registry.lookup(names, :worker), Registry.values(names, :worker, '
 'me), Registry.keys(names, w)]))\n'
 'Process.send(w, 0, 10)\n'
 'Process.await(w, 100)\n'
 'IO.puts(inspect([Registry.count(names), Registry.lookup(names, :worker)]))\n'
 'IO.puts(inspect(Registry.put_meta(names, :owner, "chat")))\n'
 'o: option[string] = Registry.meta(names, :owner)\n'
 'p: option[integer] = Registry.meta(names, :owner)\n'
 'q: option[string] = Registry.meta(names, :nobody)\n'
 'IO.puts(inspect({o, p, q}))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'rooms: registry[string, integer] = Registry.start_link([keys: :duplicate], [partitions: 8])\n'
 'IO.puts(inspect([Registry.register(rooms, "lobby", 1), Registry.register(rooms, "lobby", 7), '
 'Registry.register(rooms, "hall", 2)]))\n'
 'IO.puts(inspect(Registry.count_match(rooms, "lobby", fn n -> n > 5 end)))\n'
 'IO.puts(inspect(Enum.map(Registry.match(rooms, "lobby", fn n -> n > 5 end), fn e -> elem(e, 1) end)))\n'
 'IO.puts(inspect(Registry.dispatch(rooms, "lobby", fn entries -> IO.puts(inspect(length(entries))) end)))\n'
 'IO.puts(inspect(Registry.dispatch(rooms, "nobody", fn entries -> IO.puts(inspect(length(entries))) end)))\n'
 'IO.puts(inspect(Registry.unregister_match(rooms, "lobby", fn n -> n > 5 end)))\n'
 'IO.puts(inspect([Registry.lookup(rooms, "lobby"), Registry.partitions(rooms)]))\n'
 'IO.puts(inspect(Registry.update_value(rooms, "lobby", fn n -> n * 3 end)))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n  def main() do\nme = Process.self(4)\nIO.puts("x")\n  end\nend\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'me: pid[integer] = Process.self(4)\n'
 'Process.send(me, "text", 0)\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'w = Process.spawn(fn(n: integer): integer do n end, 1)\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n  def main() do\nIO.puts(inspect(Process.receive(5, 0)))\n  end\nend\n',
 'defmodule Example do\n  def main() do\nProcess.sleep("1")\n  end\nend\n',
 'defmodule Example do\n  def main() do\nIO.puts(inspect(Task.await(5)))\n  end\nend\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'a = Agent.start(fn -> 0 end)\n'
 'IO.puts(inspect(Agent.get(a, fn(s: string): string do s end)))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 's = Server.start(0, fn(t: integer, n: integer): tuple[integer, integer] do {t, n} end)\n'
 'IO.puts(inspect(Server.call(s, "x", 10)))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'me: pid[integer] = Process.self(4)\n'
 'Process.send(me, 1)\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n  def main() do\nProcess.monitor(3)\n  end\nend\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'r: registry[string, integer] = Registry.start_link([keys: :unique])\n'
 'Registry.register(r, 5, 5)\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'g = Supervisor.start("one_for_one", 1, 1000, [{"a", 1, 2}], 1)\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'me: pid[integer] = Process.self(4)\n'
 'assert_receive(me, "text")\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'a = Agent.start(fn -> [] end)\n'
 'Agent.update(a, fn l -> l ++ [1] end)\n'
 'IO.puts(inspect(Agent.get(a, fn l -> length(l) end)))\n'
 '  end\n'
 'end\n',
 'defmodule Example do\n'
 '  def main() do\n'
 'task = Task.start(fn -> raise("oops") end)\n'
 'IO.puts(inspect(Task.yield(task, 1000)))\n'
 'IO.puts(inspect(Task.yield(task, 1000)))\n'
 'f = fn -> raise("never") end\n'
 'IO.puts(inspect(try do\n'
 '  f()\n'
 'rescue\n'
 '  m -> {}\n'
 'end))\n'
 '  end\n'
 'end\n']


def verify(compiler):
    limited=[str(ROOT/'scripts/limited')]
    bounds=dict(PATH=os.environ.get('PATH','/usr/bin:/bin'),ALCHEM_SECONDS='30',ALCHEM_MEMORY='2G')
    for name in ('XDG_RUNTIME_DIR','DBUS_SESSION_BUS_ADDRESS'):
        if name in os.environ:bounds[name]=os.environ[name]
    with tempfile.TemporaryDirectory(prefix='alchem-processes-') as d:
        out=Path(d)/'out'
        for source,status,stdout,stderr in RUNS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run(limited+[str(out)],capture_output=True,env=bounds,cwd=d,timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    print(f'PASS processes: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; spawn, send, receive, links, monitors, exits and their traces, timers, names, tasks, agents, servers, supervisors, registries, ports, receive assertions')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
