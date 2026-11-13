package syntax

func init() {
	legacy("Process.self", "Process.self(integer) -> pid[t]")
	legacy("Process.spawn", "Process.spawn(fn[pid[t],integer], integer) -> pid[t]")
	legacy("Process.id", "Process.id(pid[t]) -> integer")
	legacy("Process.alive", "Process.alive(pid[t]) -> boolean")
	legacy("Process.send", "Process.send(pid[t], t, integer) -> boolean")
	legacy("Process.receive", "Process.receive(pid[t], integer) -> tuple[boolean,t]")
	legacy("Process.await", "Process.await(pid[t], integer) -> tuple[boolean,string]")
	legacy("Process.stop", "Process.stop(pid[t]) -> boolean")
	legacy("Process.loop", "Process.loop(s, fn[s,tuple[boolean,s]]) -> s")
	legacy("Process.sleep", "Process.sleep(integer) -> integer")
	legacy("Process.crash", "Process.crash(string) -> integer")
	legacy("Process.report", "Process.report(pid[t]) -> string")
	legacy("Process.monitor", "Process.monitor(pid[t]) -> integer")
	legacy("Process.demonitor", "Process.demonitor(pid[t], integer) -> boolean")
	legacy("Process.link", "Process.link(pid[t]) -> boolean")
	legacy("Process.unlink", "Process.unlink(pid[t]) -> boolean")
	legacy("Process.trap_exits", "Process.trap_exits(boolean) -> boolean")
	legacy("Process.event", "Process.event(integer) -> tuple[boolean,integer,integer,string]")
	doc("Process.self", "The current process, creating its mailbox with the given capacity on first use. The message type comes from the annotation.",
		"alx> me: pid[string] = Process.self(8)", "alx> Process.send(me, \"hello\", 100)", "true", "alx> Process.receive(me, 100)", "{true, \"hello\"}")
	doc("Process.spawn", "Starts a process running the function, which receives its own pid and returns an exit status. The second argument is the mailbox capacity.",
		"alx> parent: pid[integer] = Process.self(8)",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do", "...>   {_, n} = Process.receive(self, 1000)", "...>   Process.send(parent, n * 2, 1000)", "...>   0", "...> end, 8)",
		"alx> Process.send(worker, 21, 1000)", "true", "alx> Process.receive(parent, 1000)", "{true, 42}")
	doc("Process.id", "The process's unique positive identifier. Pids are compared by id.",
		"alx> me: pid[integer] = Process.self(1)", "alx> Process.id(me) > 0", "true")
	doc("Process.alive", "Reports whether the process is still running.",
		"alx> me: pid[integer] = Process.self(1)", "alx> Process.alive(me)", "true")
	doc("Process.send", "Queues a message for a process, waiting up to the given milliseconds for room. False when it timed out or the process has ended.",
		"alx> me: pid[integer] = Process.self(4)", "alx> Process.send(me, 7, 100)", "true")
	doc("Process.receive", "Takes the next message from the current process's mailbox, waiting up to the given milliseconds. The flag is false on timeout.",
		"alx> me: pid[integer] = Process.self(4)", "alx> Process.send(me, 7, 100)", "true", "alx> Process.receive(me, 100)", "{true, 7}",
		"alx> {arrived, _} = Process.receive(me, 10)", "alx> arrived", "false")
	doc("Process.await", "Waits up to the given milliseconds for a process and everything it started to end, returning whether it did and its exit reason.",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 0 end, 1)", "alx> Process.await(worker, 1000)", "{true, \"normal\"}")
	doc("Process.stop", "Asks a process to stop; true when this request was the first.",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(60000) end, 1)", "alx> Process.stop(worker)", "true",
		"alx> {ended, _} = Process.await(worker, 1000)", "alx> ended", "true")
	doc("Process.loop", "Runs a state loop without growing the stack: the function returns {continue, next_state}, and the final state is returned once continue is false.",
		"alx> Process.loop(1, fn(n: integer): tuple[boolean, integer] do {n < 100, n * 2} end)", "256")
	doc("Process.sleep", "Pauses the current process for a number of milliseconds and returns 0. Process.sleep(0) yields to other processes.",
		"alx> Process.sleep(1)", "0")
	doc("Process.crash", "Fails the current process with a reason. Typed as integer so a worker can end with it.",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.crash(\"bad input\") end, 1)",
		"alx> {ended, reason} = Process.await(worker, 1000)", "alx> ended and String.contains?(reason, \"bad input\")", "true")
	doc("Process.report", "Where and why a process failed, or its exit reason; meaningful once it has ended.",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.crash(\"bad input\") end, 1)",
		"alx> Process.await(worker, 1000)", "alx> String.contains?(Process.report(worker), \"bad input\")", "true")
	doc("Process.monitor", "Asks to be notified once when the process ends, returning a reference. Process.event receives the notification.",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 0 end, 1)", "alx> reference = Process.monitor(worker)",
		"alx> {arrived, noticed, _, reason} = Process.event(1000)", "alx> arrived and noticed == reference and reason == \"normal\"", "true")
	doc("Process.demonitor", "Cancels a monitor and discards its notification if already queued.",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(60000) end, 1)", "alx> reference = Process.monitor(worker)",
		"alx> Process.demonitor(worker, reference)", "true", "alx> Process.stop(worker)", "true")
	doc("Process.link", "Links the current process with another: when either fails, the other is stopped too unless it traps exits.",
		"alx> Process.trap_exits(true)", "alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(60000) end, 1)",
		"alx> Process.link(worker)", "true", "alx> Process.unlink(worker)", "true", "alx> Process.stop(worker)", "true")
	doc("Process.unlink", "Removes a link in both directions; true when there was one.",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do Process.sleep(60000) end, 1)",
		"alx> Process.unlink(worker)", "false", "alx> Process.stop(worker)", "true")
	doc("Process.trap_exits", "Chooses whether linked failures arrive as events instead of stopping this process, returning the previous setting.",
		"alx> Process.trap_exits(true)", "alx> Process.trap_exits(false)", "true")
	doc("Process.event", "Waits up to the given milliseconds for a monitor or link notification: {arrived, reference, process_id, reason}. Link events have reference 0.",
		"alx> {arrived, _, _, _} = Process.event(1)", "alx> arrived", "false")

	legacy("Supervisor.start", "Supervisor.start(string, integer, integer, list[tuple[string,string,fn[pid[t],integer]]], integer) -> supervisor[t]")
	legacy("Supervisor.start_link", "Supervisor.start_link(string, integer, integer, list[tuple[string,string,fn[pid[t],integer]]], integer) -> supervisor[t]")
	legacy("Supervisor.child", "Supervisor.child(supervisor[t], string) -> pid[t]")
	legacy("Supervisor.children", "Supervisor.children(supervisor[t]) -> list[tuple[string,integer]]")
	legacy("Supervisor.restarts", "Supervisor.restarts(supervisor[t]) -> integer")
	legacy("Supervisor.alive", "Supervisor.alive(supervisor[t]) -> boolean")
	legacy("Supervisor.stop", "Supervisor.stop(supervisor[t], integer) -> boolean")
	legacy("Supervisor.await", "Supervisor.await(supervisor[t], integer) -> tuple[boolean,string]")
	const group = "alx> group = Supervisor.start(\"one_for_one\", 3, 1000, [{\"worker\", \"permanent\", fn(self: pid[integer]): integer do Process.sleep(60000) end}], 4)"
	doc("Supervisor.server", "A child for Supervisor.start that runs a server under a name: the child registers the server, Supervisor.start returns once it has, and Server.whereis finds whichever server is running. A failing server makes its child fail, so the strategy and the policy (\"permanent\", \"transient\" or \"temporary\") decide the restart, which begins from the initial state. Servers of different types can share one supervisor.",
		"alx> tree = Supervisor.start(\"one_for_one\", 3, 1000, [Supervisor.server(:doc_total, \"permanent\", 0, fn(total: integer, n: integer): tuple[integer, integer] do {total + n, total + n} end)], 1)",
		"alx> found: option[server[integer, integer]] = Server.whereis(:doc_total)",
		"alx> case found do", "...>   some(total) -> Server.call(total, 5, 1000)", "...>   none -> error(\"not found\")", "...> end", "ok(5)",
		"alx> Supervisor.stop(tree, 1000)", "true")
	doc("Supervisor.start", "Starts children under a strategy (\"one_for_one\", \"one_for_all\" or \"rest_for_one\"), giving up after max_restarts within window_ms. Each child is {name, restart_policy, function}, with policy \"permanent\", \"transient\" or \"temporary\"; the last argument is each child's mailbox capacity.",
		group, "alx> Supervisor.alive(group)", "true", "alx> Supervisor.stop(group, 1000)", "true")
	doc("Supervisor.start_link", "Like Supervisor.start, and also links the supervisor to the process starting it.",
		"alx> group = Supervisor.start_link(\"one_for_one\", 3, 1000, [{\"worker\", \"permanent\", fn(self: pid[integer]): integer do Process.sleep(60000) end}], 4)",
		"alx> Supervisor.stop(group, 1000)", "true")
	doc("Supervisor.child", "The current pid of a named child, for sending it messages.",
		group, "alx> Process.alive(Supervisor.child(group, \"worker\"))", "true", "alx> Supervisor.stop(group, 1000)", "true")
	doc("Supervisor.children", "Each child's name with its current process id, in declaration order.",
		group, "alx> Enum.map(Supervisor.children(group), fn {name, _} -> name end)", "[\"worker\"]", "alx> Supervisor.stop(group, 1000)", "true")
	doc("Supervisor.restarts", "How many restarts the supervisor has performed.",
		group, "alx> Supervisor.restarts(group)", "0", "alx> Supervisor.stop(group, 1000)", "true")
	doc("Supervisor.alive", "Reports whether the supervisor is running.",
		group, "alx> Supervisor.stop(group, 1000)", "true", "alx> Supervisor.alive(group)", "false")
	doc("Supervisor.stop", "Stops the supervisor and its children, waiting up to the given milliseconds; false when the wait ran out.",
		group, "alx> Supervisor.stop(group, 1000)", "true")
	doc("Supervisor.await", "Waits up to the given milliseconds for the supervisor to end, returning whether it did and why.",
		group, "alx> Supervisor.stop(group, 1000)", "true", "alx> {ended, _} = Supervisor.await(group, 1000)", "alx> ended", "true")

	legacy("Server.start", "Server.start(s, fn[s,q,tuple[s,r]]) -> server[q,r]")
	legacy("Server.start_supervised", "Server.start_supervised(s, fn[s,q,tuple[s,r]], integer, integer) -> server[q,r]")
	legacy("Server.restarts", "Server.restarts(server[q,r]) -> integer")
	legacy("Server.call", "Server.call(server[q,r], q, integer) -> result[r,string]")
	legacy("Server.cast", "Server.cast(server[q,r], q) -> boolean")
	legacy("Server.stop", "Server.stop(server[q,r]) -> boolean")
	legacy("Server.alive", "Server.alive(server[q,r]) -> boolean")
	legacy("Server.await", "Server.await(server[q,r], integer) -> tuple[boolean,string]")
	const counter = "alx> counter = Server.start(0, fn(total: integer, amount: integer): tuple[integer, integer] do {total + amount, total + amount} end)"
	doc("Server.start", "Starts a process owning a state. The handler takes the state and a request and returns {next_state, reply}; requests are answered one at a time, in order.",
		counter, "alx> Server.call(counter, 5, 1000)", "ok(5)", "alx> Server.call(counter, 2, 1000)", "ok(7)", "alx> Server.stop(counter)", "true")
	doc("Server.start_supervised", "Like Server.start, restarting the server with its initial state when the handler fails, up to max_restarts within window_ms.",
		"alx> counter = Server.start_supervised(0, fn(total: integer, amount: integer): tuple[integer, integer] do {total + amount, total + amount} end, 3, 1000)",
		"alx> Server.call(counter, 5, 1000)", "ok(5)", "alx> Server.restarts(counter)", "0", "alx> Server.stop(counter)", "true")
	doc("Server.restarts", "How many times a supervised server has been restarted; 0 for an unsupervised one.",
		counter, "alx> Server.restarts(counter)", "0", "alx> Server.stop(counter)", "true")
	doc("Server.call", "Sends a request and waits up to the given milliseconds for the reply: ok(reply), or error(\"timeout\"), error(\"server is not running\") or error(\"server stopped: reason\").",
		counter, "alx> Server.call(counter, 5, 1000)", "ok(5)", "alx> Server.stop(counter)", "true")
	doc("Server.cast", "Queues a request without waiting for the reply; false when the server has stopped or its queue is full.",
		counter, "alx> Server.cast(counter, 5)", "true", "alx> Server.call(counter, 0, 1000)", "ok(5)", "alx> Server.stop(counter)", "true")
	doc("Server.stop", "Asks the server to shut down.",
		counter, "alx> Server.stop(counter)", "true")
	doc("Server.alive", "Reports whether the server is running.",
		counter, "alx> Server.alive(counter)", "true", "alx> Server.stop(counter)", "true")
	doc("Server.await", "Waits up to the given milliseconds for the server to end, returning whether it did and its exit reason.",
		counter, "alx> Server.stop(counter)", "true", "alx> {ended, _} = Server.await(counter, 1000)", "alx> ended", "true")

	doc("Task.async", "Runs the function in its own process, linked to the caller, and returns a task to await. A task that fails takes its caller with it, unless the caller traps exits; Task.Supervisor.async_nolink starts one that does not.",
		"alx> task = Task.async(fn -> 6 * 7 end)", "alx> Task.await(task)", "42")
	doc("Task.start", "Runs the function in its own process, not linked to the caller, for work nobody needs to wait for; the task can still be awaited or shut down.",
		"alx> task = Task.start(fn -> 5 end)", "alx> Task.await(task)", "5")
	doc("Task.start_link", "Like Task.start, linked to the caller: a task that fails takes the caller with it.",
		"alx> task = Task.start_link(fn -> 8 end)", "alx> Task.await(task, 1000)", "8")
	doc("Task.Supervisor.start_link", "Starts a task supervisor, with DynamicSupervisor's options such as max_children:.",
		"alx> tasks = Task.Supervisor.start_link()", "alx> Task.Supervisor.children(tasks)", "[]",
		"alx> limited = Task.Supervisor.start_link([max_children: 4])", "alx> DynamicSupervisor.stop(limited)", "true")
	doc("Task.Supervisor.async", "Runs the function as a task under the supervisor, linked to the caller, and returns it to await.",
		"alx> tasks = Task.Supervisor.start_link()", "alx> Task.await(Task.Supervisor.async(tasks, fn -> 6 * 7 end))", "42")
	doc("Task.Supervisor.async_nolink", "Runs the function as a task under the supervisor, not linked to the caller: a failure is seen only by awaiting or yielding the task.",
		"alx> tasks = Task.Supervisor.start_link()",
		"alx> task = Task.Supervisor.async_nolink(tasks, fn -> div(1, 0) end)",
		"alx> case Task.yield(task, 1000) do", "...>   some(error(_)) -> \"failed\"", "...>   _ -> \"other\"", "...> end", "\"failed\"")
	doc("Task.Supervisor.start_child", "Starts a task under the supervisor that nobody needs to await, unlinked: ok(task), or error(\"max_children\") or error(\"supervisor is not running\").",
		"alx> tasks = Task.Supervisor.start_link()", "alx> ok(task) = Task.Supervisor.start_child(tasks, fn -> 1 end)", "alx> Task.await(task)", "1")
	doc("Task.Supervisor.children", "The process ids of the supervisor's running tasks.",
		"alx> tasks = Task.Supervisor.start_link()",
		"alx> ok(_) = Task.Supervisor.start_child(tasks, fn -> Process.sleep(60000) end)",
		"alx> length(Task.Supervisor.children(tasks))", "1", "alx> DynamicSupervisor.stop(tasks)", "true")
	doc("Task.Supervisor.terminate_child", "Stops one of the supervisor's tasks; false when it is not running there.",
		"alx> tasks = Task.Supervisor.start_link()",
		"alx> ok(task) = Task.Supervisor.start_child(tasks, fn -> Process.sleep(60000) end)",
		"alx> Task.Supervisor.terminate_child(tasks, task)", "true", "alx> Task.Supervisor.terminate_child(tasks, task)", "false")
	doc("Task.async_stream", "Runs the function over each element concurrently, at most one task per processor (or the given number) at a time, yielding results in input order.",
		"alx> Task.async_stream([1, 2, 3], fn n -> n * n end) |> Enum.to_list()", "[1, 4, 9]", "alx> Task.async_stream(1..4, fn n -> n + 1 end, 2) |> Enum.sum()", "14")
	doc("Task.await", "Waits for a task's result, for 5 seconds or the given milliseconds. Fails the caller when the task failed or the time ran out.",
		"alx> Task.await(Task.async(fn -> \"done\" end), 1000)", "\"done\"")
	doc("Task.await_many", "Waits for every task, returning the results in order.",
		"alx> Task.await_many([Task.async(fn -> 1 end), Task.async(fn -> 2 end)])", "[1, 2]")
	doc("Task.shutdown", "Stops a task whose result is no longer wanted.",
		"alx> task = Task.async(fn -> Process.sleep(60000) end)", "alx> Task.shutdown(task)", "true")
	doc("Task.yield", "Waits up to the given milliseconds: some(ok(value)) when the task finished, some(error(reason)) when it failed, none when it is still running.",
		"alx> Task.yield(Task.async(fn -> 42 end), 1000)", "some(ok(42))",
		"alx> slow = Task.async(fn -> Process.sleep(60000) end)", "alx> Task.yield(slow, 1)", "none", "alx> Task.shutdown(slow)", "true")

	doc("Agent.start", "Starts a process holding the state the function returns.",
		"alx> counter = Agent.start(fn -> 0 end)", "alx> Agent.get(counter, fn n -> n end)", "0", "alx> Agent.stop(counter)", "true")
	doc("Agent.start_link", "Like Agent.start, and also links the agent to the process starting it. With [name: :name] the agent is registered under the name, and the functions that take an agent also take the name; the state's type then comes from the function's annotation.",
		"alx> names = Agent.start_link(fn -> [\"ada\"] end)", "alx> Agent.get(names, &length(&1))", "1", "alx> Agent.stop(names)", "true",
		"alx> Agent.start_link(fn -> 1 end, [name: :doc_agent])",
		"alx> Agent.get(:doc_agent, fn(n: integer): integer do n + 1 end)", "2")
	doc("Agent.whereis", "Finds an agent by name. The state's type comes from the annotation; a name registered for another type is not found.",
		"alx> Agent.start(fn -> 3 end, [name: :doc_found])",
		"alx> found: option[agent[integer]] = Agent.whereis(:doc_found)",
		"alx> case found do", "...>   some(agent) -> Agent.get(agent, fn n -> n end)", "...>   none -> 0", "...> end", "3")
	doc("Agent.get", "Runs the function on the state inside the agent and returns its result. A last argument waits that many milliseconds instead of 5 seconds.",
		"alx> counter = Agent.start(fn -> 41 end)", "alx> Agent.get(counter, fn n -> n + 1 end)", "42", "alx> Agent.stop(counter)", "true")
	doc("Agent.update", "Replaces the state with the function's result, waiting until it is done.",
		"alx> counter = Agent.start(fn -> 0 end)", "alx> Agent.update(counter, fn n -> n + 5 end)", "alx> Agent.get(counter, fn n -> n end)", "5", "alx> Agent.stop(counter)", "true")
	doc("Agent.get_and_update", "The function returns {reply, next_state}: one step that reads and changes the state.",
		"alx> counter = Agent.start(fn -> 10 end)", "alx> Agent.get_and_update(counter, fn n -> {n, n + 1} end)", "10", "alx> Agent.get(counter, fn n -> n end)", "11", "alx> Agent.stop(counter)", "true")
	doc("Agent.cast", "Queues a state update without waiting for it; false when the agent has stopped.",
		"alx> counter = Agent.start(fn -> 0 end)", "alx> Agent.cast(counter, fn n -> n + 1 end)", "true", "alx> Agent.get(counter, fn n -> n end)", "1", "alx> Agent.stop(counter)", "true")
	doc("Agent.stop", "Stops the agent.",
		"alx> counter = Agent.start(fn -> 0 end)", "alx> Agent.stop(counter)", "true")

	doc("Gen.integer", "Integers: without bounds, between -size and size as the runs grow; with bounds, from low to high. Shrinks toward 0, or the bound nearest it.",
		"alx> Enum.all?(Gen.sample(Gen.integer(1, 6), 20), fn n -> n >= 1 and n <= 6 end)", "true")
	doc("Gen.positive_integer", "Integers from 1, shrinking toward 1.",
		"alx> Enum.all?(Gen.sample(Gen.positive_integer(), 20), fn n -> n >= 1 end)", "true")
	doc("Gen.float", "Floats between -size and size, shrinking toward 0.",
		"alx> length(Gen.sample(Gen.float(), 5))", "5")
	doc("Gen.boolean", "true or false, shrinking to false.",
		"alx> Enum.all?(Gen.sample(Gen.boolean(), 10), fn b -> b or not b end)", "true")
	doc("Gen.constant", "Always the same value.",
		"alx> Gen.sample(Gen.constant(7), 3)", "[7, 7, 7]")
	doc("Gen.string", "Strings of :alphanumeric, :alpha, :lower, :digit, :ascii or :printable characters, up to size long, shrinking to shorter and earlier ones.",
		"alx> Enum.all?(Gen.sample(Gen.string(:digit), 10), fn s -> String.match?(s, ~r/^[0-9]*$/) end)", "true")
	doc("Gen.list_of", "Lists of the generator's values, up to size long or from min to max long. Shrinks by leaving elements out, then by shrinking them.",
		"alx> Enum.all?(Gen.sample(Gen.list_of(Gen.boolean(), 2, 3), 10), fn l -> length(l) >= 2 and length(l) <= 3 end)", "true")
	doc("Gen.map_of", "Maps with generated keys and values.",
		"alx> Enum.all?(Gen.sample(Gen.map_of(Gen.integer(1, 3), Gen.boolean()), 10), fn m -> map_size(m) <= 3 end)", "true")
	doc("Gen.member_of", "One of the given values, shrinking toward the first.",
		"alx> Enum.all?(Gen.sample(Gen.member_of([:red, :green]), 10), fn c -> c in [:red, :green] end)", "true")
	doc("Gen.one_of", "A value of one of the generators, chosen at random.",
		"alx> Enum.all?(Gen.sample(Gen.one_of([Gen.constant(0), Gen.integer(10, 20)]), 10), fn n -> n == 0 or n >= 10 end)", "true")
	doc("Gen.map", "The generator's values changed by the function.",
		"alx> Enum.all?(Gen.sample(Gen.map(Gen.integer(), fn n -> n * 2 end), 10), fn n -> rem(n, 2) == 0 end)", "true")
	doc("Gen.filter", "The generator's values that pass the test; generating 100 in a row that fail it is an error, so filter out few.",
		"alx> Enum.all?(Gen.sample(Gen.filter(Gen.integer(), fn n -> n != 0 end), 10), fn n -> n != 0 end)", "true")
	doc("Gen.bind", "A generator chosen from each value of another: the second may depend on the first. check all does this for each generator after the first.",
		"alx> Enum.all?(Gen.sample(Gen.bind(Gen.integer(0, 3), fn n -> Gen.list_of(Gen.constant(n), n, n) end), 10), fn l -> Enum.all?(l, fn n -> n == length(l) end) end)", "true")
	doc("Gen.tuple", "Tuples of two or three generators' values.",
		"alx> Enum.all?(Gen.sample(Gen.tuple(Gen.integer(0, 1), Gen.constant(\"x\")), 5), fn {n, s} -> n <= 1 and s == \"x\" end)", "true")
	doc("Gen.resize", "The generator with its size fixed: Gen.resize(Gen.integer(), 3) stays between -3 and 3.",
		"alx> Enum.all?(Gen.sample(Gen.resize(Gen.integer(), 3), 20), fn n -> n >= -3 and n <= 3 end)", "true")
	doc("Gen.sample", "That many values of a generator, growing in size, to see what it makes.",
		"alx> length(Gen.sample(Gen.integer(), 4))", "4")
	doc("Gen.check", "Runs the function on generated values, 100 or the given number of times, and fails with the smallest failing value, shrunk, when it fails. check all is the usual way to write it.",
		"alx> Gen.check(Gen.integer(), fn n -> assert(n + 0 == n) end, 20)")

	legacy("assert", "assert(boolean)")
	doc("assert", "Fails the test, or the program, when the condition is false. A failed comparison reports both sides.",
		"alx> assert(1 + 1 == 2)", "alx> assert(\"a\" in [\"a\", \"b\"])")
	doc("refute", "Fails when the condition is true.", "alx> refute(1 > 2)")
	doc("assert_raise", "Fails unless the function raises with a message containing the text.",
		"alx> assert_raise(\"division by zero\", fn -> div(1, 0) end)")
	doc("assert_in_delta", "Fails unless two floats differ by at most the delta.", "alx> assert_in_delta(0.1 + 0.2, 0.3, 0.0001)")
	doc("flunk", "Fails the test with a message.", "alx> assert_raise(\"not reached\", fn -> flunk(\"not reached\") end)")
}
