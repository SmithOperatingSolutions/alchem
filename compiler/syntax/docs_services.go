package syntax

func init() {
	module("Registry", "Concurrency", "Finds processes by key. Each entry belongs to the process that registered it, holds a value, and goes away when that process ends.")
	module("DynamicSupervisor", "Concurrency", "A supervisor that starts children while it runs, of any message type, and restarts the ones that fail.")

	doc("Process.send_after", "Sends a message to a process after the given milliseconds and returns a timer reference for Process.cancel_timer. A message to a process that has ended by then is dropped. Given a name instead of a pid, the message goes to whatever holds the name when the time comes: a process registered with Process.register whose messages are of the message's type, or a server registered with Server.register whose requests are, as a cast; when nothing fitting holds it, the message is dropped.",
		"alx> me: pid[string] = Process.self(4)",
		"alx> timer = Process.send_after(me, \"ping\", 10)", "alx> timer > 0", "true",
		"alx> Process.receive(me, 1000)", "{true, \"ping\"}",
		"alx> Process.register(me, :doc_inbox)", "true",
		"alx> Process.send_after(:doc_inbox, \"named\", 10) > 0", "true",
		"alx> Process.receive(me, 1000)", "{true, \"named\"}", "alx> Process.unregister(:doc_inbox)", "true")
	doc("Process.cancel_timer", "Cancels a timer from Process.send_after or Server.send_after; false when it had already fired or been cancelled.",
		"alx> me: pid[string] = Process.self(4)",
		"alx> timer = Process.send_after(me, \"late\", 60000)", "alx> Process.cancel_timer(timer)", "true", "alx> Process.cancel_timer(timer)", "false")

	const ticker = "alx> counter = Server.start(0, fn(total: integer, amount: integer): tuple[integer, integer] do {total + amount, total + amount} end)"
	doc("Server.send_after", "Casts a request to a server after the given milliseconds and returns a timer reference for Process.cancel_timer. A server can schedule work for itself with Server.self.",
		ticker, "alx> Server.send_after(counter, 5, 10) > 0", "true",
		"alx> Process.sleep(100)", "alx> Server.call(counter, 0, 1000)", "ok(5)", "alx> Server.stop(counter)", "true")
	doc("Server.self", "The server whose handler is running, for a handler that schedules requests for itself or gives its handle away. The request and reply types come from the annotation and must be the server's own.",
		"alx> counter = Server.start(0, fn(total: integer, amount: integer): tuple[integer, integer] do",
		"...>   me: server[integer, integer] = Server.self()",
		"...>   if amount > 1 do", "...>     Server.cast(me, amount - 1)", "...>   end",
		"...>   {total + amount, total + amount}", "...> end)",
		"alx> Server.cast(counter, 3)", "true", "alx> Process.sleep(50)",
		"alx> Server.call(counter, 0, 1000)", "ok(6)", "alx> Server.stop(counter)", "true")
	doc("Server.register", "Gives a server a name that Server.whereis finds. A name belongs to one living process or server at a time; a supervised server keeps its name across restarts. Process.unregister frees it.",
		ticker, "alx> Server.register(counter, :doc_counter)", "true", "alx> Server.register(counter, :doc_counter)", "false",
		"alx> Process.unregister(:doc_counter)", "true", "alx> Server.stop(counter)", "true")
	doc("Server.whereis", "Finds a server by name. The request and reply types come from the annotation; a name registered for other types, or for a process, is not found.",
		ticker, "alx> Server.register(counter, :doc_named)", "true",
		"alx> found: option[server[integer, integer]] = Server.whereis(:doc_named)",
		"alx> case found do", "...>   some(named) -> Server.call(named, 4, 1000)", "...>   none -> error(\"missing\")", "...> end", "ok(4)",
		"alx> other: option[server[string, string]] = Server.whereis(:doc_named)",
		"alx> case other do", "...>   some(_) -> \"found\"", "...>   none -> \"not found\"", "...> end", "\"not found\"", "alx> Server.stop(counter)", "true")
	doc("Server.monitor", "Turns a process's exit into a request to a server: when the process ends, the function makes a request from the exit reason, inside the server, and it is queued like a cast. This is how a server hears of the processes it depends on.",
		"alx> log = Server.start([], fn(seen: list[string], event: string): tuple[list[string], list[string]] do {[event] ++ seen, [event] ++ seen} end)",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do 0 end, 1)",
		"alx> Server.monitor(log, worker, fn reason -> \"worker ended: \" <> reason end)", "true",
		"alx> Process.sleep(50)", "alx> Server.call(log, \"checked\", 1000)", "ok([\"checked\", \"worker ended: normal\"])", "alx> Server.stop(log)", "true")

	doc("Server.continue", "Asks the running server to handle a request of its own as soon as it has answered the current one, ahead of any request already waiting: the work a handler defers until after its reply, as handle_continue does in Elixir. Replies to continued requests go nowhere.",
		"alx> loader = Server.start([], fn(steps: list[string], step: string): tuple[list[string], list[string]] do",
		"...>   if step == \"start\" do", "...>     Server.continue(\"load\")", "...>   end",
		"...>   {steps ++ [step], steps ++ [step]}", "...> end)",
		"alx> Server.call(loader, \"start\", 1000)", "ok([\"start\"])",
		"alx> Server.call(loader, \"check\", 1000)", "ok([\"start\", \"load\", \"check\"])", "alx> Server.stop(loader)", "true")
	doc("Server.mailbox", "Gives a server a pid that any process, port or socket can send to. Each message becomes a request, made from the message inside the server by the function and queued like a cast: the messages Elixir delivers to handle_info. The mailbox ends with the server; for a supervised server it outlives restarts.",
		"alx> log = Server.start([], fn(seen: list[string], event: string): tuple[list[string], list[string]] do {seen ++ [event], seen ++ [event]} end)",
		"alx> inbox: pid[integer] = Server.mailbox(log, fn n -> \"got \" <> to_string(n) end)",
		"alx> Process.send(inbox, 7, 1000)", "true", "alx> Process.sleep(50)",
		"alx> Server.call(log, \"checked\", 1000)", "ok([\"got 7\", \"checked\"])", "alx> Server.stop(log)", "true")

	doc("Registry.start_link", "Starts a registry. keys: :unique allows one living entry per key; keys: :duplicate allows any number, from one process or several. The key and value types come from the annotation; keys are integers, strings, booleans or atoms.",
		"alx> rooms: registry[string, pid[string]] = Registry.start_link([keys: :duplicate])", "alx> Registry.count(rooms)", "0")
	doc("Registry.register", "Registers the calling process under a key with a value, until it ends or unregisters. In a unique registry a key held by a living process gives error(\"already_registered\").",
		"alx> names: registry[atom, integer] = Registry.start_link([keys: :unique])",
		"alx> Registry.register(names, :alpha, 1)", "ok({})", "alx> Registry.register(names, :alpha, 2)", "error(\"already_registered\")")
	doc("Registry.unregister", "Removes the calling process's entries under a key; false when it had none.",
		"alx> names: registry[atom, integer] = Registry.start_link([keys: :unique])",
		"alx> Registry.register(names, :alpha, 1)", "ok({})", "alx> Registry.unregister(names, :alpha)", "true", "alx> Registry.lookup(names, :alpha)", "[]")
	doc("Registry.lookup", "The values registered under a key by living processes, in the order they registered. Elixir also returns each entry's pid; put the pid in the value when it is needed.",
		"alx> rooms: registry[string, integer] = Registry.start_link([keys: :duplicate])",
		"alx> Registry.register(rooms, \"lobby\", 1)", "ok({})", "alx> Registry.register(rooms, \"lobby\", 2)", "ok({})",
		"alx> Registry.lookup(rooms, \"lobby\")", "[1, 2]")
	doc("Registry.keys", "The keys a process holds.",
		"alx> rooms: registry[string, integer] = Registry.start_link([keys: :duplicate])",
		"alx> Registry.register(rooms, \"lobby\", 1)", "ok({})", "alx> me: pid[string] = Process.self(4)",
		"alx> Registry.keys(rooms, me)", "[\"lobby\"]")
	const lobby = "alx> rooms: registry[string, integer] = Registry.start_link([keys: :duplicate])"
	doc("Registry.entries", "The process ids and values registered under a key by living processes, in the order they registered, as Elixir's lookup gives pids and values. Process.id gives a pid's id.",
		lobby, "alx> Registry.register(rooms, \"lobby\", 1)", "ok({})", "alx> me: pid[string] = Process.self(4)",
		"alx> Registry.entries(rooms, \"lobby\") == [{Process.id(me), 1}]", "true")
	doc("Registry.match", "The entries under a key whose values pass the test, as {process id, value}.",
		lobby, "alx> Registry.register(rooms, \"lobby\", 1)", "ok({})", "alx> Registry.register(rooms, \"lobby\", 7)", "ok({})",
		"alx> Enum.map(Registry.match(rooms, \"lobby\", fn n -> n > 5 end), fn {_, n} -> n end)", "[7]")
	doc("Registry.count_match", "How many entries under a key have values that pass the test.",
		lobby, "alx> Registry.register(rooms, \"lobby\", 1)", "ok({})", "alx> Registry.register(rooms, \"lobby\", 7)", "ok({})",
		"alx> Registry.count_match(rooms, \"lobby\", fn n -> n > 5 end)", "1")
	doc("Registry.unregister_match", "Removes the calling process's entries under a key whose values pass the test, and returns how many it removed.",
		lobby, "alx> Registry.register(rooms, \"lobby\", 1)", "ok({})", "alx> Registry.register(rooms, \"lobby\", 7)", "ok({})",
		"alx> Registry.unregister_match(rooms, \"lobby\", fn n -> n > 5 end)", "1", "alx> Registry.lookup(rooms, \"lobby\")", "[1]")
	doc("Registry.values", "The values one process registered under a key.",
		lobby, "alx> Registry.register(rooms, \"lobby\", 1)", "ok({})", "alx> me: pid[string] = Process.self(4)",
		"alx> Registry.values(rooms, \"lobby\", me)", "[1]")
	doc("Registry.dispatch", "Calls the function with the entries under a key, as {process id, value}, when there are any, and returns :ok. Put a pid in the value to send to the processes.",
		"alx> rooms: registry[string, pid[string]] = Registry.start_link([keys: :duplicate])", "alx> me: pid[string] = Process.self(4)",
		"alx> Registry.register(rooms, \"news\", me)", "ok({})",
		"alx> Registry.dispatch(rooms, \"news\", fn entries -> Enum.each(entries, fn {_, inbox} -> Process.send(inbox, \"hello\", 100) end) end)", ":ok",
		"alx> Process.receive(me, 1000)", "{true, \"hello\"}")
	doc("Registry.select", "Every entry whose key, process id and value pass the test, as {key, process id, value}: what Elixir's select does with a match specification.",
		lobby, "alx> Registry.register(rooms, \"lobby\", 1)", "ok({})", "alx> Registry.register(rooms, \"hall\", 2)", "ok({})",
		"alx> Enum.map(Registry.select(rooms, fn key, _, _ -> key == \"hall\" end), fn {key, _, value} -> {key, value} end)", "[{\"hall\", 2}]")
	doc("Registry.update_value", "Replaces the value of the calling process's entry under a key with the function's result: ok({new, old}), or error(\"not_registered\").",
		"alx> names: registry[atom, integer] = Registry.start_link([keys: :unique])", "alx> Registry.register(names, :hits, 1)", "ok({})",
		"alx> Registry.update_value(names, :hits, fn n -> n + 1 end)", "ok({2, 1})")
	doc("Registry.partitions", "The number of partitions; start_link takes [partitions: n] after the keys option. Each partition has its own lock, so processes registering under different keys seldom wait for each other.",
		"alx> rooms: registry[string, integer] = Registry.start_link([keys: :duplicate], [partitions: 8])", "alx> Registry.partitions(rooms)", "8")
	doc("Registry.put_meta", "Stores a value under a name for the whole registry, and returns :ok.",
		lobby, "alx> Registry.put_meta(rooms, :owner, \"chat\")", ":ok")
	doc("Registry.meta", "A value stored with put_meta. Its type comes from the annotation; a value of another type is not found.",
		lobby, "alx> Registry.put_meta(rooms, :owner, \"chat\")", ":ok",
		"alx> owner: option[string] = Registry.meta(rooms, :owner)", "alx> owner", "some(\"chat\")")
	doc("Registry.count", "The number of entries held by living processes.",
		"alx> rooms: registry[string, integer] = Registry.start_link([keys: :duplicate])",
		"alx> worker: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do",
		"...>   Registry.register(rooms, \"lobby\", 1)", "...>   Process.receive(self, 60000)", "...>   0", "...> end, 1)",
		"alx> Process.sleep(50)", "alx> Registry.count(rooms)", "1",
		"alx> Process.send(worker, 0, 100)", "true", "alx> Process.await(worker, 1000)", "{true, \"normal\"}", "alx> Registry.count(rooms)", "0")

	const dynamic = "alx> sup = DynamicSupervisor.start_link()"
	doc("DynamicSupervisor.start_link", "Starts a supervisor with no children. It gives up, stopping its children, after more than max_restarts restarts within max_seconds: 3 within 5 unless the options say otherwise. With max_children: it runs at most that many children at once, and start_child returns error(\"max_children\") beyond them.",
		dynamic, "alx> DynamicSupervisor.count_children(sup)", "0",
		"alx> strict = DynamicSupervisor.start_link([max_restarts: 1, max_seconds: 10])", "alx> DynamicSupervisor.alive(strict)", "true")
	const worker = "alx> ok(worker) = DynamicSupervisor.start_child(sup, fn(self: pid[string]): integer do"
	const body = "...>   Process.receive(self, 60000)"
	const done = "...>   0"
	doc("DynamicSupervisor.start_child", "Starts a process under the supervisor and returns its pid. The restart is :permanent (restarted whenever it ends, the default), :transient (restarted when it fails) or :temporary (never restarted). A restarted child is a new process with a new pid.",
		dynamic, worker, body, done, "...> end)",
		"alx> DynamicSupervisor.count_children(sup)", "1",
		"alx> ok(once) = DynamicSupervisor.start_child(sup, fn(self: pid[string]): integer do 0 end, :temporary)",
		"alx> Process.await(once, 1000)", "{true, \"normal\"}", "alx> Process.sleep(20)", "alx> DynamicSupervisor.count_children(sup)", "1")
	doc("DynamicSupervisor.start_server", "Starts a server under the supervisor. The server restarts itself after a handler failure, within the supervisor's limits, so its handle stays good; it stops when the supervisor stops.",
		dynamic, "alx> ok(counter) = DynamicSupervisor.start_server(sup, 0, fn(total: integer, amount: integer): tuple[integer, integer] do {total + amount, total + amount} end)",
		"alx> Server.call(counter, 2, 1000)", "ok(2)", "alx> DynamicSupervisor.stop(sup)", "true", "alx> Server.alive(counter)", "false")
	doc("DynamicSupervisor.terminate_child", "Stops a child and forgets it, so it is not restarted; false when the pid is not a child.",
		dynamic, worker, body, done, "...> end)",
		"alx> DynamicSupervisor.terminate_child(sup, worker)", "true", "alx> DynamicSupervisor.count_children(sup)", "0",
		"alx> DynamicSupervisor.terminate_child(sup, worker)", "false")
	doc("DynamicSupervisor.which_children", "The process ids of the running children, in the order they were started.",
		dynamic, worker, body, done, "...> end)",
		"alx> DynamicSupervisor.which_children(sup) == [Process.id(worker)]", "true")
	doc("DynamicSupervisor.count_children", "How many children are running.",
		dynamic, "alx> DynamicSupervisor.count_children(sup)", "0")
	doc("DynamicSupervisor.restarts", "How many times children have been restarted.",
		dynamic, worker, "...>   Process.crash(\"boom\")", "...> end)",
		"alx> Process.sleep(50)", "alx> DynamicSupervisor.restarts(sup) > 0", "true")
	doc("DynamicSupervisor.stop", "Stops the supervisor and its children, waiting up to five seconds; true when they ended.",
		dynamic, "alx> DynamicSupervisor.stop(sup)", "true", "alx> DynamicSupervisor.alive(sup)", "false")
	doc("DynamicSupervisor.alive", "Reports whether the supervisor is running.",
		dynamic, "alx> DynamicSupervisor.alive(sup)", "true")
}
