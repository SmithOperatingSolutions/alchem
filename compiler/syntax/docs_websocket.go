package syntax

func init() {
	module("WebSocket", "Network", "WebSockets, RFC 6455: a handler of HTTP.serve upgrades its request into a socket, and WebSocket.connect opens one to a server. Messages are text or binary; pings and the closing handshake are answered without the program's help. Calls that wait take milliseconds and give error(\"timeout\") or error(\"closed\"). A socket belongs to the process that made it and closes when that process ends, so a handler that upgrades either keeps the socket or hands it on with controlling_process.")
	module("Crypto", "Text", "Cryptographic building blocks: random bytes from the operating system's secure source, hashes, HMAC signatures and a comparison that takes the same time however much of its input matches. Results are raw bytes; Base.encode16 or Base.encode64 makes them printable.")

	// echo is a server whose handler upgrades its request, answers one
	// message (text in upper case, binary as it came) and then waits for the
	// client to close.
	const echo = "alx> ok(server) = HTTP.serve(\"127.0.0.1:0\", fn request ->\n" +
		"...>   case WebSocket.upgrade(request) do\n" +
		"...>     ok(ws) ->\n" +
		"...>       answered: result[tuple[], string] = case WebSocket.recv(ws, 5000) do\n" +
		"...>         ok(WebSocket.Event.text(text)) -> WebSocket.send(ws, String.upcase(text))\n" +
		"...>         ok(WebSocket.Event.binary(data)) -> WebSocket.send_binary(ws, data)\n" +
		"...>         _ -> ok({})\n" +
		"...>       end\n" +
		"...>       if answered == ok({}) do\n" +
		"...>         WebSocket.recv(ws, 5000)\n" +
		"...>       end\n" +
		"...>       HTTP.text(200, \"\")\n" +
		"...>     error(reason) -> HTTP.text(400, reason)\n" +
		"...>   end\n" +
		"...> end)"
	const connect = "alx> ok(ws) = WebSocket.connect(\"ws://\" <> HTTP.address(server) <> \"/echo\", 1000)"

	doc("WebSocket.upgrade", "Called by an HTTP.serve handler, answers its request with the WebSocket handshake and returns the socket. The response the handler returns afterwards is not sent. A request that is not a WebSocket handshake is error(\"not a WebSocket request: ...\"), and the handler answers it as it likes. [max_message_bytes: n] bounds incoming messages (16 MB by default); a larger one closes the socket with code 1009. Check HTTP.header(request, \"origin\") before upgrading when only your own pages should connect.",
		echo, connect, "alx> WebSocket.send(ws, \"hello\")", "ok({})", "alx> WebSocket.recv(ws, 1000)", "ok(WebSocket.Event.text(\"HELLO\"))",
		"alx> ok(plain) = HTTP.get(\"http://\" <> HTTP.address(server) <> \"/echo\")", "alx> {plain.status, plain.body}", "{400, \"not a WebSocket request: no upgrade to websocket\"}")
	doc("WebSocket.connect", "Opens a WebSocket to a ws:// or wss:// address, waiting up to the given milliseconds for the connection and the handshake. Options, as text: ca_file: a PEM file of certificates to trust, insecure: \"true\" to trust any, and origin: the Origin header to send. A list of {name, value} headers after the options is sent with the handshake, such as a Cookie or Authorization; the headers the handshake sets itself are refused.",
		echo, connect, "alx> WebSocket.send(ws, \"hi\")", "ok({})", "alx> WebSocket.recv(ws, 1000)", "ok(WebSocket.Event.text(\"HI\"))",
		"alx> case WebSocket.connect(\"http://\" <> HTTP.address(server), 1000) do", "...>   ok(_) -> \"connected\"", "...>   error(reason) -> reason", "...> end", "\"a WebSocket address starts with ws:// or wss://\"")
	doc("WebSocket.send", "Sends a text message.",
		echo, connect, "alx> WebSocket.send(ws, \"abc\")", "ok({})", "alx> WebSocket.recv(ws, 1000)", "ok(WebSocket.Event.text(\"ABC\"))")
	doc("WebSocket.send_binary", "Sends a binary message: any bytes, which arrive as WebSocket.Event.binary.",
		echo, connect, "alx> WebSocket.send_binary(ws, \"\\x01\\xff\")", "ok({})", "alx> WebSocket.recv(ws, 1000)", "ok(WebSocket.Event.binary(\"\\x01\\xff\"))")
	doc("WebSocket.recv", "Waits up to the given milliseconds for the next event: a text or binary message, WebSocket.Event.closed(code, reason) when the other end closes, or WebSocket.Event.error(reason) when the connection fails. After the last event it is error(\"closed\").",
		echo, connect, "alx> WebSocket.recv(ws, 10)", "error(\"timeout\")",
		"alx> WebSocket.send(ws, \"x\")", "ok({})", "alx> WebSocket.recv(ws, 1000)", "ok(WebSocket.Event.text(\"X\"))",
		"alx> WebSocket.close(ws)", "true", "alx> WebSocket.recv(ws, 1000)", "ok(WebSocket.Event.closed(1000, \"\"))", "alx> WebSocket.recv(ws, 1000)", "error(\"closed\")")
	doc("WebSocket.close", "Closes with code 1000, or with a code from 3000 to 4999 and a reason of at most 123 bytes, waiting up to a second for the other end to answer. false when the socket was already closed.",
		echo, connect, "alx> WebSocket.close(ws)", "true", "alx> WebSocket.close(ws)", "false", "alx> WebSocket.send(ws, \"late\")", "error(\"closed\")")
	doc("WebSocket.controlling_process", "Hands a socket to another process, whose end then closes it and to which an active socket sends its events.",
		echo, connect, "alx> keeper: pid[WebSocket.Event] = Process.spawn(fn(self: pid[WebSocket.Event]): integer do", "...>   Process.receive(self, 60000)", "...>   0", "...> end, 1)",
		"alx> WebSocket.controlling_process(ws, keeper)", "true")
	doc("WebSocket.setopts", "active: true sends every event to the controlling process as a WebSocket.Event message, active: :once sends one, and active: false stops. The controlling process is the one given to controlling_process, or the socket's maker, and its messages must be WebSocket.Event.",
		echo, connect, "alx> me: pid[WebSocket.Event] = Process.self(8)", "alx> WebSocket.setopts(ws, [active: :once])", "ok({})",
		"alx> WebSocket.send(ws, \"hi\")", "ok({})", "alx> Process.receive(me, 1000)", "{true, WebSocket.Event.text(\"HI\")}")
	doc("WebSocket.peer", "The address of the other end, host:port.",
		echo, connect, "alx> String.starts_with?(WebSocket.peer(ws), \"127.0.0.1:\")", "true")

	doc("Crypto.strong_rand_bytes", "The given number of random bytes from the operating system's secure source, for keys, tokens and nonces.",
		"alx> byte_size(Crypto.strong_rand_bytes(16))", "16", "alx> Crypto.strong_rand_bytes(16) == Crypto.strong_rand_bytes(16)", "false")
	doc("Crypto.hash", "The digest of some data with :md5, :sha1, :sha224, :sha256, :sha384 or :sha512, as raw bytes. MD5 and SHA-1 are for checking old formats, not for security.",
		"alx> Base.encode16(Crypto.hash(:sha256, \"abc\"), [case: :lower])", "\"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad\"")
	doc("Crypto.hmac", "The HMAC of data under a key with one of the hash algorithms, as raw bytes: a signature only someone holding the key can make. Compare signatures with Crypto.secure_compare.",
		"alx> Base.encode16(Crypto.hmac(:sha256, \"Jefe\", \"what do ya want for nothing?\"), [case: :lower])", "\"5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843\"")
	doc("Crypto.secure_compare", "Reports whether two strings are equal, taking a time that depends only on their lengths, so that checking a signature or token does not reveal how much of a guess was right.",
		"alx> Crypto.secure_compare(\"token\", \"token\")", "true", "alx> Crypto.secure_compare(\"token\", \"tokem\")", "false")
}
