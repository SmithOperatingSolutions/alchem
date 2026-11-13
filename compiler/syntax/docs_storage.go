package syntax

func init() {
	module("DiskStore", "Files and system", "A table of text under text keys, kept in one file so that it outlasts the program: a write is on the disk when it returns, keys are read in order by range or prefix, and any process may use it.")

	// scratch opens a store in a new file, so that each example starts empty.
	const scratch = "alx> path = Path.join(System.tmp_dir!(), \"store_doc_\" <> Base.encode16(Crypto.strong_rand_bytes(6)))\n" +
		"alx> ok(store) = DiskStore.open(path)"
	const tidy = "alx> DiskStore.close(store)\ntrue\nalx> File.rm(path)\nok({})"
	doc("DiskStore.open", "Opens the store in a file, making the file when there is none. What a crash cut short at the end of the file is dropped. Opening a path that is already open gives the same store, and one program opens a given file at a time. A file that is something else is an error. Every key and value is also held in memory, where reads are answered, so a store suits data that fits there. Values of other types are kept as text: JSON.encode! writes one and JSON.decode_as reads it back.",
		scratch, "alx> DiskStore.put(store, \"greeting\", \"hello\")", "ok({})", "alx> DiskStore.close(store)", "true",
		"alx> ok(again) = DiskStore.open(path)", "alx> DiskStore.get(again, \"greeting\")", "some(\"hello\")", "alx> DiskStore.close(again)", "true", "alx> File.rm(path)", "ok({})")
	doc("DiskStore.close", "Closes a store once the writes under way are on the disk; false when it was closed already. A closed store refuses writes with error(\"closed\"), and reading one fails.",
		scratch, "alx> DiskStore.close(store)", "true", "alx> DiskStore.close(store)", "false", "alx> DiskStore.put(store, \"k\", \"v\")", "error(\"closed\")", "alx> File.rm(path)", "ok({})")
	doc("DiskStore.put", "Stores a value under a key, replacing what the key held, and returns when the change is on the disk.",
		scratch, "alx> DiskStore.put(store, \"user:1\", \"al\")", "ok({})", "alx> DiskStore.get(store, \"user:1\")", "some(\"al\")", tidy)
	doc("DiskStore.get", "The value under a key, or none.",
		scratch, "alx> DiskStore.get(store, \"missing\")", "none", tidy)
	doc("DiskStore.has_key?", "Reports whether a key holds a value.",
		scratch, "alx> DiskStore.put(store, \"k\", \"\")", "ok({})", "alx> {DiskStore.has_key?(store, \"k\"), DiskStore.has_key?(store, \"other\")}", "{true, false}", tidy)
	doc("DiskStore.delete", "Removes a key; a key that holds nothing is left as it is.",
		scratch, "alx> DiskStore.put(store, \"k\", \"v\")", "ok({})", "alx> DiskStore.delete(store, \"k\")", "ok({})", "alx> DiskStore.get(store, \"k\")", "none", tidy)
	doc("DiskStore.commit", "Makes several changes as one: the {key, value} pairs are stored and the listed keys removed, and after a crash either all of it is there or none.",
		scratch, "alx> DiskStore.put(store, \"cart:7\", \"pen\")", "ok({})",
		"alx> DiskStore.commit(store, [{\"order:1\", \"pen\"}, {\"stock:pen\", \"4\"}], [\"cart:7\"])", "ok({})", "alx> DiskStore.keys(store)", "[\"order:1\", \"stock:pen\"]", tidy)
	doc("DiskStore.update", "Changes one key by a function of what it holds, none when it holds nothing: the function gives some(value) to store or none to remove the key, and no other write to the store comes between its reading and its writing. The result is what the function gave. The function must not itself write to the store, which waits for it.",
		scratch, "alx> count = fn(held: option[string]): option[string] do", "...>   case held do", "...>     some(n) -> some(Integer.to_string(String.to_integer(n) + 1))", "...>     none -> some(\"1\")", "...>   end", "...> end",
		"alx> DiskStore.update(store, \"visits\", count)", "ok(some(\"1\"))", "alx> DiskStore.update(store, \"visits\", count)", "ok(some(\"2\"))", tidy)
	doc("DiskStore.keys", "Every key, in order.",
		scratch, "alx> DiskStore.commit(store, [{\"b\", \"2\"}, {\"a\", \"1\"}], [])", "ok({})", "alx> DiskStore.keys(store)", "[\"a\", \"b\"]", tidy)
	doc("DiskStore.size", "The number of keys.",
		scratch, "alx> DiskStore.put(store, \"k\", \"v\")", "ok({})", "alx> DiskStore.size(store)", "1", tidy)
	doc("DiskStore.range", "The {key, value} pairs whose keys are at or after the first key and before the second, in key order.",
		scratch, "alx> DiskStore.commit(store, [{\"a\", \"1\"}, {\"b\", \"2\"}, {\"c\", \"3\"}], [])", "ok({})", "alx> DiskStore.range(store, \"a\", \"c\")", "[{\"a\", \"1\"}, {\"b\", \"2\"}]", tidy)
	doc("DiskStore.prefix", "The {key, value} pairs whose keys begin with a prefix, in key order: with keys written as kind:id, everything of one kind.",
		scratch, "alx> DiskStore.commit(store, [{\"user:1\", \"al\"}, {\"user:2\", \"bo\"}, {\"visit:1\", \"x\"}], [])", "ok({})", "alx> DiskStore.prefix(store, \"user:\")", "[{\"user:1\", \"al\"}, {\"user:2\", \"bo\"}]", tidy)
	doc("DiskStore.compact", "Writes the file afresh with only what the store holds now, dropping the record of earlier values. A store does this by itself when its file has grown well past what it holds, so calling it is seldom needed.",
		scratch, "alx> DiskStore.put(store, \"k\", \"old\")", "ok({})", "alx> DiskStore.put(store, \"k\", \"new\")", "ok({})", "alx> DiskStore.compact(store)", "ok({})", "alx> DiskStore.get(store, \"k\")", "some(\"new\")", tidy)

	doc("Crypto.pbkdf2", "A key of the given number of bytes derived from a password and a salt by PBKDF2 over HMAC with one of the hash algorithms, as raw bytes. The count of iterations makes each guess at the password cost that much work. For storing passwords, Crypto.hash_password chooses the salt and the count.",
		"alx> Base.encode16(Crypto.pbkdf2(:sha256, \"password\", \"salt\", 4096, 32), [case: :lower])", "\"c5e478d59288c841aa530db6845c4c8d962893a001ce4e11a4963873aa98134a\"")
	doc("Crypto.hash_password", "What to store in place of a password: its PBKDF2-HMAC-SHA256 key under a fresh random salt, written with the salt and the count of iterations as $pbkdf2-sha256$i=600000$salt$key, so that Crypto.verify_password needs nothing else. The same password gives a different result each time. [iterations: n] sets the count, 600,000 by default; passwords stored with an older count still verify.",
		"alx> stored = Crypto.hash_password(\"correct horse\", [iterations: 1000])", "alx> String.starts_with?(stored, \"$pbkdf2-sha256$i=1000$\")", "true",
		"alx> Crypto.verify_password(\"correct horse\", stored)", "true", "alx> stored == Crypto.hash_password(\"correct horse\", [iterations: 1000])", "false")
	doc("Crypto.verify_password", "Reports whether a password is the one Crypto.hash_password made a stored value from. Text that is not such a value matches no password.",
		"alx> stored = Crypto.hash_password(\"correct horse\", [iterations: 1000])", "alx> {Crypto.verify_password(\"correct horse\", stored), Crypto.verify_password(\"wrong\", stored)}", "{true, false}",
		"alx> Crypto.verify_password(\"correct horse\", \"not a stored password\")", "false")

	doc("JSON.decode_as", "Reads JSON as the type the result is annotated with, from text or from a JSON value: the reverse of what JSON.encode! writes for that type. A struct is read from an object by field name, where a field that is an option may be left out and members the struct has no field for are passed over; a variant from its name, or from {\"name\": [fields]} when it has fields; lists, sets and tuples from arrays; a map from an object, its keys read as strings, atoms, integers, floats or booleans; an option from null or the value; and an integer is accepted where a float is wanted. JSON that does not fit is an error that says where, as in \"items[2].price: expected an integer, found a string\". A type holding functions or processes cannot be read. In a generic function the type may be one of the function's type variables, and is read as the type the function was called with, which must then be one that can be read.",
		"alx> prices: result[map[string, list[integer]], string] = JSON.decode_as(\"{\\\"pen\\\": [3, 4]}\")", "alx> prices", "ok(%{\"pen\" => [3, 4]})",
		"alx> pair: result[tuple[string, option[float]], string] = JSON.decode_as(JSON.decode!(\"[\\\"x\\\", null]\"))", "alx> pair", "ok({\"x\", none})",
		"alx> wrong: result[map[string, list[integer]], string] = JSON.decode_as(\"{\\\"pen\\\": [3, \\\"four\\\"]}\")", "alx> wrong", "error(\"pen[1]: expected an integer, found a string\")")
	doc("WebSocket.compressed?", "Reports whether the handshake agreed to compress messages: the server upgraded with compress: and the client offered it.",
		"alx> ok(server) = HTTP.serve(\"127.0.0.1:0\", fn request ->", "...>   ok(socket) = WebSocket.upgrade(request, [compress: true])", "...>   WebSocket.recv(socket, 1000)", "...>   HTTP.text(200, \"\")", "...> end)",
		"alx> ok(ws) = WebSocket.connect(\"ws://\" <> HTTP.address(server), 1000, [compress: \"true\"])", "alx> WebSocket.compressed?(ws)", "true",
		"alx> ok(plain) = WebSocket.connect(\"ws://\" <> HTTP.address(server), 1000)", "alx> WebSocket.compressed?(plain)", "false")
}
