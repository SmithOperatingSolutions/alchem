package syntax

func init() {
	module("TCP", "Network", "TCP connections: listen, accept, connect, send and receive text. Calls that wait take milliseconds (negative waits indefinitely) and give error(\"timeout\") or error(\"closed\"); a process waiting in one still stops when asked. A socket belongs to the process that opened it and closes when that process ends.")
	module("UDP", "Network", "UDP sockets: datagrams sent to and received from host:port addresses, passively with UDP.recv or actively as UDP.Event messages. UDP sockets close as TCP sockets do.")
	module("HTTP", "Network", "An HTTP client, and a server that answers each request in a process of its own. Requests and responses are the HTTP.Request and HTTP.Response structs; header names are lower case.")

	const listen = "alx> ok(listener) = TCP.listen(\"127.0.0.1:0\")"
	const echo = "alx> server = Task.async(fn ->\n...>   ok(client) = TCP.accept(listener, 1000)\n...>   ok(line) = TCP.recv_line(client, 1000)\n...>   TCP.send(client, String.upcase(line) <> \"\\n\")\n...> end)"
	const connect = "alx> ok(conn) = TCP.connect(TCP.address(listener), 1000)"
	doc("TCP.listen", "Listens on an address, host:port; port 0 picks a free one, which TCP.address reports.",
		listen, "alx> String.starts_with?(TCP.address(listener), \"127.0.0.1:\")", "true")
	doc("TCP.accept", "Waits up to the given milliseconds for a connection to a listening socket.",
		listen, "alx> case TCP.accept(listener, 10) do", "...>   ok(_) -> \"connected\"", "...>   error(reason) -> reason", "...> end", "\"timeout\"")
	doc("TCP.connect", "Connects to an address, waiting up to the given milliseconds.",
		listen, echo, connect, "alx> TCP.send(conn, \"hi\\n\")", "ok({})", "alx> TCP.recv_line(conn, 1000)", "ok(\"HI\")")
	doc("TCP.send", "Writes text to a connection.",
		listen, echo, connect, "alx> TCP.send(conn, \"abc\\n\")", "ok({})", "alx> TCP.recv(conn, 4, 1000)", "ok(\"ABC\\n\")")
	doc("TCP.recv", "Reads exactly the given number of bytes, or with 0 whatever has arrived once anything has, waiting up to the given milliseconds. error(\"closed\") once the other end has closed.",
		listen, echo, connect, "alx> TCP.send(conn, \"xy\\n\")", "ok({})", "alx> TCP.recv(conn, 0, 1000)", "ok(\"XY\\n\")", "alx> TCP.recv(conn, 0, 1000)", "error(\"closed\")")
	doc("TCP.recv_line", "Reads a line, without its newline or a carriage return before it, waiting up to the given milliseconds.",
		listen, echo, connect, "alx> TCP.send(conn, \"line\\r\\n\")", "ok({})", "alx> TCP.recv_line(conn, 1000)", "ok(\"LINE\")")
	doc("TCP.close", "Closes a listener or connection; false when it was already closed. Sockets are also closed when the program ends.",
		listen, "alx> TCP.close(listener)", "true", "alx> TCP.close(listener)", "false")
	doc("TCP.controlling_process", "Hands a socket to another process, whose end then closes it instead of the opener's.",
		listen, "alx> keeper: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do", "...>   Process.receive(self, 60000)", "...>   0", "...> end, 1)",
		"alx> TCP.controlling_process(listener, keeper)", "true")
	doc("TCP.address", "The local address of a socket, host:port.",
		listen, "alx> String.contains?(TCP.address(listener), \":\")", "true")
	doc("TCP.setopts", "Sets socket options. active: true sends every packet to the controlling process as TCP.Event.data(text), then TCP.Event.closed or TCP.Event.error(reason); active: :once sends one and makes the socket passive again; active: n sends n; active: false stops. The controlling process is the one given to controlling_process, or the opener, and its messages must be TCP.Event. packet: :raw (the default) delivers what has arrived, packet: :line a line with its newline, and packet: 1, 2 or 4 a packet with a length header of that many bytes, which TCP.send adds. TCP.recv with length 0 reads one packet.",
		listen, echo, connect, "alx> me: pid[TCP.Event] = Process.self(8)", "alx> TCP.setopts(conn, [active: :once])", "ok({})",
		"alx> TCP.send(conn, \"hi\\n\")", "ok({})", "alx> Process.receive(me, 1000)", "{true, TCP.Event.data(\"HI\\n\")}",
		"alx> TCP.setopts(conn, [packet: 4])", "ok({})")
	doc("TCP.shutdown", "Closes one direction of a connection: :write tells the other end there is no more to read, :read stops reading, :read_write closes it.",
		listen, echo, connect, "alx> TCP.send(conn, \"bye\\n\")", "ok({})", "alx> TCP.shutdown(conn, :write)", "ok({})", "alx> TCP.recv_line(conn, 1000)", "ok(\"BYE\")")
	doc("UDP.open", "Opens a UDP socket on an address, host:port; port 0 picks a free one, which UDP.address reports.",
		"alx> ok(socket) = UDP.open(\"127.0.0.1:0\")", "alx> String.starts_with?(UDP.address(socket), \"127.0.0.1:\")", "true")
	doc("UDP.send", "Sends a datagram to an address.",
		"alx> ok(a) = UDP.open(\"127.0.0.1:0\")", "alx> ok(b) = UDP.open(\"127.0.0.1:0\")", "alx> UDP.send(a, UDP.address(b), \"ping\")", "ok({})",
		"alx> case UDP.recv(b, 1000) do", "...>   ok({_, text}) -> text", "...>   error(reason) -> reason", "...> end", "\"ping\"")
	doc("UDP.recv", "Waits up to the given milliseconds for a datagram: ok({from, text}), or error(\"timeout\").",
		"alx> ok(socket) = UDP.open(\"127.0.0.1:0\")", "alx> UDP.recv(socket, 10)", "error(\"timeout\")")
	doc("UDP.setopts", "active: true, :once, false or a number sends datagrams to the controlling process as UDP.Event.datagram(from, text), as TCP.setopts does for TCP.",
		"alx> me: pid[UDP.Event] = Process.self(8)", "alx> ok(socket) = UDP.open(\"127.0.0.1:0\")", "alx> UDP.setopts(socket, [active: :once])", "ok({})",
		"alx> UDP.send(socket, UDP.address(socket), \"self\")", "ok({})",
		"alx> case Process.receive(me, 1000) do", "...>   {true, UDP.Event.datagram(_, text)} -> text", "...>   _ -> \"nothing\"", "...> end", "\"self\"")
	doc("UDP.close", "Closes a UDP socket; false when it was already closed.",
		"alx> ok(socket) = UDP.open(\"127.0.0.1:0\")", "alx> UDP.close(socket)", "true", "alx> UDP.close(socket)", "false")
	doc("UDP.address", "The local address of a UDP socket, host:port.",
		"alx> ok(socket) = UDP.open(\"127.0.0.1:0\")", "alx> String.contains?(UDP.address(socket), \":\")", "true")
	doc("UDP.controlling_process", "Hands a UDP socket to another process, which then receives its events and whose end closes it.",
		"alx> ok(socket) = UDP.open(\"127.0.0.1:0\")", "alx> keeper: pid[UDP.Event] = Process.spawn(fn(self: pid[UDP.Event]): integer do", "...>   Process.receive(self, 60000)", "...>   0", "...> end, 1)",
		"alx> UDP.controlling_process(socket, keeper)", "true")
	doc("TCP.peer", "The address of the other end of a connection; none for a listener.",
		listen, "alx> TCP.peer(listener)", "none")

	const serve = "alx> ok(server) = HTTP.serve(\"127.0.0.1:0\", fn request ->\n...>   HTTP.text(200, request.method <> \" \" <> request.path <> \" \" <> request.body)\n...> end)"
	const base = "alx> base = \"http://\" <> HTTP.address(server)"
	doc("HTTP.serve", "Serves HTTP on an address, host:port. Each request runs the handler in a process of its own; a handler that fails answers 500. The server stops when HTTP.stop is called or the program ends. A third argument sets limits: read_timeout:, write_timeout:, idle_timeout: (how long a kept-alive connection waits for its next request) and header_timeout: in milliseconds, max_header_bytes:, max_body_bytes: (64 MB by default; larger requests get 413), and keep_alive: 0 to close each connection after one request.",
		serve, base, "alx> ok(response) = HTTP.get(base <> \"/hello\")", "alx> {response.status, response.body}", "{200, \"GET /hello \"}", "alx> HTTP.stop(server)", "true")
	doc("HTTP.address", "The address a server listens on, host:port, with the port chosen when it was 0.",
		serve, "alx> String.starts_with?(HTTP.address(server), \"127.0.0.1:\")", "true")
	doc("HTTP.stop", "Stops a server and closes its connections.",
		serve, "alx> HTTP.stop(server)", "true", "alx> HTTP.await(server, 1000)", "true")
	doc("HTTP.await", "Waits up to the given milliseconds (negative waits indefinitely) for a server to stop; a program that only serves ends main with HTTP.await(server, -1).",
		serve, "alx> HTTP.await(server, 10)", "false")
	doc("HTTP.get", "Sends a GET request, with optional headers, waiting up to 30 seconds. A response with any status is ok; error is for a request that got no response.",
		serve, base, "alx> ok(response) = HTTP.get(base <> \"/a\", [{\"accept\", \"text/plain\"}])", "alx> response.body", "\"GET /a \"")
	doc("HTTP.post", "Sends a POST request with a body and headers.",
		serve, base, "alx> ok(response) = HTTP.post(base <> \"/items\", \"apple\", [{\"content-type\", \"text/plain\"}])", "alx> response.body", "\"POST /items apple\"")
	doc("HTTP.request", "Sends a request with any method, headers and body, waiting up to 30 seconds or the given milliseconds; error(\"timeout\") when no response came in time. Options may take the place of the milliseconds: timeout: (as text), ca_file: a PEM file of certificates to trust, insecure: \"true\" to trust any, stream: \"true\" for the body as chunks, as HTTP.stream gives it, and redirect: \"false\" to return a redirect as it came, with its status and location header, instead of following it.",
		serve, base, "alx> ok(response) = HTTP.request(\"PUT\", base <> \"/x\", [], \"v\")", "alx> response.body", "\"PUT /x v\"",
		"alx> ok(kept) = HTTP.request(\"GET\", base <> \"/x\", [], \"\", [redirect: \"false\"])", "alx> kept.status", "200",
		"alx> case HTTP.request(\"GET\", \"http://127.0.0.1:1/\", [], \"\", 1000) do", "...>   ok(_) -> \"answered\"", "...>   error(_) -> \"no response\"", "...> end", "\"no response\"")
	doc("HTTP.stream", "Sends a request and returns once the head of the response has come, with the body as some(stream) in chunks, read as it arrives: for long or endless responses. HTTP.read reads it whole.",
		serve, base, "alx> ok(response) = HTTP.stream(\"GET\", base <> \"/s\", [], \"\")", "alx> HTTP.read(response)", "\"GET /s \"")
	doc("HTTP.read", "The whole body of a response: its body, followed by its chunks when it has any.",
		"alx> HTTP.read(HTTP.chunked(200, [], [\"a\", \"b\"]))", "\"ab\"", "alx> HTTP.read(HTTP.text(200, \"c\"))", "\"c\"")
	doc("HTTP.chunked", "A response whose body is sent as the enumerable gives it, each piece as soon as it is made: a server can stream a large or slow body without holding it whole.",
		"alx> ok(server) = HTTP.serve(\"127.0.0.1:0\", fn _ -> HTTP.chunked(200, [], Stream.map(1..3, fn n -> to_string(n) end)) end)",
		"alx> ok(response) = HTTP.get(\"http://\" <> HTTP.address(server))", "alx> response.body", "\"123\"")
	doc("HTTP.serve_tls", "Serves HTTPS with a certificate and key read from PEM files, given as [certfile: path, keyfile: path], and the same limits as HTTP.serve. Clients trust it through the system's authorities, or HTTP.request with [ca_file: path].",
		"alx> case HTTP.serve_tls(\"127.0.0.1:0\", fn _ -> HTTP.text(200, \"secure\") end, [certfile: \"missing.pem\", keyfile: \"missing.pem\"]) do", "...>   ok(_) -> \"serving\"", "...>   error(_) -> \"no certificate\"", "...> end", "\"no certificate\"")
	doc("HTTP.match", "Matches a request against a method (or \"*\") and a path pattern, whose segments may be :name for one segment or *name for the rest: some of the parameters, or none.",
		"alx> request = %HTTP.Request{method: \"GET\", path: \"/users/7\", query: \"\", headers: [], body: \"\"}",
		"alx> HTTP.match(request, \"GET\", \"/users/:id\")", "some(%{\"id\" => \"7\"})", "alx> HTTP.match(request, \"GET\", \"/posts/:id\")", "none")
	doc("HTTP.route", "Answers a request with the first of a list of {method, pattern, handler} routes that matches, as HTTP.match does; the handler also gets the parameters. A path no route takes is 404, and one only other methods take is 405 with an allow header.",
		"alx> show = fn(_: HTTP.Request, params: map[string, string]): HTTP.Response do HTTP.text(200, Map.get(params, \"id\", \"\")) end",
		"alx> request = %HTTP.Request{method: \"GET\", path: \"/users/7\", query: \"\", headers: [], body: \"\"}",
		"alx> HTTP.route(request, [{\"GET\", \"/users/:id\", show}]).body", "\"7\"",
		"alx> HTTP.route(request, [{\"POST\", \"/users/:id\", show}]).status", "405")
	doc("HTTP.text", "A response with a status and a plain text body.",
		"alx> response = HTTP.text(404, \"not found\")", "alx> {response.status, response.body}", "{404, \"not found\"}")
	doc("HTTP.json", "A response with a status and a JSON body.",
		"alx> HTTP.json(200, JSON.object(%{\"ok\" => JSON.boolean(true)})).body", "\"{\\\"ok\\\":true}\"")
	doc("HTTP.header", "The first value of a header, by name in any case.",
		"alx> HTTP.header([{\"content-type\", \"text/plain\"}], \"Content-Type\")", "some(\"text/plain\")")
}
