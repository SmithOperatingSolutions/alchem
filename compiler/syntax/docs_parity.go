package syntax

import "strings"

// Documentation for the functions that complete Elixir's standard library.
func init() {
	module("IO.ANSI", "Core", "Escape sequences that color and move text on a terminal. Each name, such as IO.ANSI.red(), gives its sequence; IO.ANSI.format joins text and names.")
	for _, name := range ANSINames {
		example := "alx> String.starts_with?(IO.ANSI." + name + "(), \"\\e[\")"
		doc("IO.ANSI."+name, "The escape sequence for "+strings.ReplaceAll(name, "_", " ")+".", example, "true")
	}
	doc("IO.ANSI.enabled?", "Reports whether standard output is a terminal that shows escape sequences: not when it is redirected, when TERM is dumb or NO_COLOR is set.",
		"alx> IO.ANSI.enabled?() or not IO.ANSI.enabled?()", "true")
	doc("IO.ANSI.format", "Joins the parts, given as name: text pairs: text: is written as it is, and any other name, such as red: or reset:, puts its escape sequence there, with a reset at the end. With false the sequences are left out, for output that is not a terminal.",
		"alx> IO.ANSI.format([red: \"\", text: \"alert\"], false)", "\"alert\"",
		"alx> IO.ANSI.format([bright: \"\", text: \"x\"], true)", "\"\\e[1mx\\e[0m\"")
	doc("IO.ANSI.clear", "The sequence that clears the screen.", "alx> IO.ANSI.clear()", "\"\\e[2J\"")
	doc("IO.ANSI.clear_line", "The sequence that clears the current line.", "alx> IO.ANSI.clear_line()", "\"\\e[2K\"")
	doc("IO.ANSI.home", "The sequence that moves the cursor to the top left.", "alx> IO.ANSI.home()", "\"\\e[H\"")
	doc("IO.ANSI.cursor", "The sequence that moves the cursor to a line and column, counted from 1.", "alx> IO.ANSI.cursor(2, 5)", "\"\\e[2;5H\"")
	doc("IO.ANSI.cursor_up", "The sequence that moves the cursor up some lines.", "alx> IO.ANSI.cursor_up(3)", "\"\\e[3A\"")
	doc("IO.ANSI.cursor_down", "The sequence that moves the cursor down some lines.", "alx> IO.ANSI.cursor_down(1)", "\"\\e[1B\"")
	doc("IO.ANSI.cursor_right", "The sequence that moves the cursor right some columns.", "alx> IO.ANSI.cursor_right(2)", "\"\\e[2C\"")
	doc("IO.ANSI.cursor_left", "The sequence that moves the cursor left some columns.", "alx> IO.ANSI.cursor_left(2)", "\"\\e[2D\"")
	doc("IO.ANSI.color", "The sequence for one of the 256 terminal colors.", "alx> IO.ANSI.color(208)", "\"\\e[38;5;208m\"")
	doc("IO.ANSI.color_background", "The sequence for one of the 256 terminal colors as the background.", "alx> IO.ANSI.color_background(17)", "\"\\e[48;5;17m\"")

	doc("IO.read", "Reads standard input: :line gives the next line with its newline, :eof the rest of the input, a number that many characters; none at the end. Given a file opened with File.open first, it reads that file.",
		"alx> ok(f) = File.open(Path.join(System.tmp_dir!(), \"io_read_doc.txt\"), [:write])", "alx> IO.write(f, \"one\\ntwo\\n\")", "ok({})", "alx> File.close(f)", "true",
		"alx> File.open(Path.join(System.tmp_dir!(), \"io_read_doc.txt\"), [:read], fn file -> {IO.read(file, :line), IO.read(file, 2), IO.read(file, :eof)} end)",
		"ok({some(\"one\\n\"), some(\"tw\"), some(\"o\\n\")})")
	doc("IO.binread", "Reads that many bytes from standard input, or from a file opened with File.open; none at the end.",
		"alx> ok(f) = File.open(Path.join(System.tmp_dir!(), \"io_binread_doc.txt\"), [:write])", "alx> IO.write(f, \"bytes\")", "ok({})", "alx> File.close(f)", "true",
		"alx> File.open(Path.join(System.tmp_dir!(), \"io_binread_doc.txt\"), [:read], fn file -> IO.binread(file, 3) end)", "ok(some(\"byt\"))")

	const scratch = "alx> path = Path.join(System.tmp_dir!(), \"file_doc.txt\")"
	doc("File.open", "Opens a file with modes: :read (the default), :write (from empty), :append, :exclusive (only a new file), with :utf8 and :binary accepted. The file belongs to the process that opened it and closes when it ends. Given a function, the file is passed to it and closed afterwards, and the result is the function's.",
		scratch, "alx> ok(f) = File.open(path, [:write])", "alx> IO.puts(f, \"line\")", "ok({})", "alx> File.close(f)", "true",
		"alx> File.open(path, [:read], fn file -> IO.read(file, :line) end)", "ok(some(\"line\\n\"))",
		"alx> case File.open(Path.join(System.tmp_dir!(), \"no/such/dir/x\"), [:read]) do", "...>   ok(_) -> \"opened\"", "...>   error(reason) -> reason", "...> end", "\"enoent\"")
	doc("File.close", "Closes a file opened with File.open; false when it was already closed.",
		scratch, "alx> ok(f) = File.open(path, [:write])", "alx> File.close(f)", "true", "alx> File.close(f)", "false")
	doc("File.stat", "What is known about a file: its size in bytes, type (:regular, :directory, :symlink or :other), the access this program has (:read, :write, :read_write or :none), when it last changed in seconds since 1970, and its permission bits.",
		scratch, "alx> File.write(path, \"12345\")", "ok({})", "alx> ok(stat) = File.stat(path)", "alx> {stat.size, stat.type}", "{5, :regular}")
	doc("File.lstat", "Like File.stat, describing a symbolic link itself rather than what it points to.",
		"alx> ok(stat) = File.lstat(System.tmp_dir!())", "alx> stat.type in [:directory, :symlink]", "true")
	doc("File.ln", "Makes a hard link: a second name for the same file.",
		scratch, "alx> File.write(path, \"x\")", "ok({})", "alx> link = path <> \".hard\"", "alx> File.rm(link)", "alx> File.ln(path, link)", "ok({})", "alx> File.read(link)", "ok(\"x\")")
	doc("File.ln_s", "Makes a symbolic link to a path.",
		scratch, "alx> File.write(path, \"y\")", "ok({})", "alx> link = path <> \".soft\"", "alx> File.rm(link)",
		"alx> case File.ln_s(path, link) do", "...>   ok(_) -> File.read(link)", "...>   error(_) -> ok(\"y\")", "...> end", "ok(\"y\")")
	doc("File.chmod", "Sets a file's permission bits, written in octal as 0o644.",
		scratch, "alx> File.write(path, \"z\")", "ok({})", "alx> File.chmod(path, 0o600)", "ok({})", "alx> ok(stat) = File.stat(path)", "alx> stat.access in [:read_write, :read]", "true")
	doc("File.cp_r", "Copies a file, or a directory and everything in it, and returns the paths written.",
		"alx> from = Path.join(System.tmp_dir!(), \"cp_r_doc\")", "alx> File.rm_rf(from)", "alx> File.mkdir_p(from)", "alx> File.write(Path.join(from, \"a.txt\"), \"a\")", "ok({})",
		"alx> to = from <> \"_copy\"", "alx> File.rm_rf(to)", "alx> ok(written) = File.cp_r(from, to)", "alx> length(written)", "2", "alx> File.read(Path.join(to, \"a.txt\"))", "ok(\"a\")")

	doc("JSON.encode", "Writes any value as JSON: ok(text), or error(reason) for a value with no JSON form, such as an infinite float. Structs become objects by field name, maps objects with their keys as text, lists, sets and tuples arrays, atoms strings, none null and some(x) x; a variant without fields becomes its name and one with fields {\"name\": [fields]}. JSON.encode! takes the same values, and [pretty: true] indents the result.",
		"alx> JSON.encode(%{\"a\" => [1, 2]})", "ok(\"{\\\"a\\\":[1,2]}\")", "alx> JSON.encode!({:ok, some(1.5)})", "\"[\\\"ok\\\",1.5]\"")

	doc("Keyword.get_lazy", "The value of a key, or what the function gives when it is missing; the function runs only then.",
		"alx> Keyword.get_lazy([a: 1], :b, fn -> 2 end)", "2")
	doc("Keyword.pop_lazy", "Removes a key and returns its value, or what the function gives when it is missing, with the rest of the list.",
		"alx> Keyword.pop_lazy([a: 1, b: 2], :a, fn -> 0 end)", "{1, [b: 2]}")
	doc("Keyword.put_new_lazy", "Adds a key with what the function gives, only when the key is missing.",
		"alx> Keyword.put_new_lazy([a: 1], :b, fn -> 2 end)", "[b: 2, a: 1]")
	doc("Keyword.split", "Separates the pairs with the given keys from the others.",
		"alx> Keyword.split([x: 1, y: 2, z: 3], [:x, :z])", "{[x: 1, z: 3], [y: 2]}")
	doc("Keyword.validate", "Checks that a keyword list has only the allowed keys: ok(list), with the defaults of the allowed keys it lacks, or error(the unknown keys). The allowed keys are given as a keyword list of defaults, or as a list of names.",
		"alx> Keyword.validate([a: 1], [a: 0, b: 2])", "ok([a: 1, b: 2])", "alx> Keyword.validate([c: 1], [:a, :b])", "error([:c])")
	doc("List.myers_difference", "The edits that turn one list into another, as runs of {:eq | :del | :ins, elements}.",
		"alx> List.myers_difference([1, 2, 3, 4], [1, 4, 5])", "[eq: [1], del: [2, 3], eq: [4], ins: [5]]")
	doc("Map.get_and_update", "Passes the value under a key, or none, to the function, which returns what to give back and the new value, or none to remove the key; the result is that and the updated map.",
		"alx> Map.get_and_update(%{\"a\" => 1}, \"a\", fn current -> {current, some(5)} end)", "{some(1), %{\"a\" => 5}}")
	doc("Map.pop_lazy", "Removes a key and returns its value with the rest of the map, or what the function gives and the map unchanged when it is missing.",
		"alx> Map.pop_lazy(%{\"a\" => 1}, \"a\", fn -> 0 end)", "{1, %{}}")
	doc("Map.replace_lazy", "Replaces the value of a key with what the function makes of it, when the key is there.",
		"alx> Map.replace_lazy(%{\"a\" => 1}, \"a\", fn v -> v + 1 end)", "%{\"a\" => 2}")
	doc("Enum.slide", "Moves the element at an index to another, shifting those between.",
		"alx> Enum.slide([:a, :b, :c, :d], 0, 2)", "[:b, :c, :a, :d]")

	doc("String.jaro_distance", "How alike two strings are, from 0.0 for nothing in common to 1.0 for equal, by the Jaro measure over grapheme clusters.",
		"alx> String.jaro_distance(\"Dwayne\", \"Duane\")", "0.8222222222222223")
	doc("String.myers_difference", "The edits that turn one string into another, as runs of {:eq | :del | :ins, text}.",
		"alx> String.myers_difference(\"abc\", \"adc\")", "[eq: \"a\", del: \"b\", ins: \"d\", eq: \"c\"]")
	doc("String.next_grapheme", "Splits off the first grapheme cluster, or none for an empty string.",
		"alx> String.next_grapheme(\"e\\u0301x\")", "some({\"e\\u0301\", \"x\"})")
	doc("String.normalize", "The string in Unicode normalization form :nfc, :nfd, :nfkc or :nfkd.",
		"alx> String.normalize(\"e\\u0301\", :nfc)", "\"é\"", "alx> String.length(String.normalize(\"é\", :nfd))", "1",
		"alx> String.normalize(\"ﬁ\", :nfkc)", "\"fi\"")
	doc("String.splitter", "Splits lazily at a pattern, or at any of a list of patterns, giving a stream.",
		"alx> String.splitter(\"red,green blue\", [\",\", \" \"]) |> Enum.to_list()", "[\"red\", \"green\", \"blue\"]")

	doc("Float.ratio", "The float as an exact fraction, {numerator, denominator}.", "alx> Float.ratio(0.75)", "{3, 4}")
	doc("Float.max_finite", "The largest finite float.", "alx> Float.max_finite() > 1.0e308", "true")
	doc("Float.min_finite", "The most negative finite float.", "alx> Float.min_finite() < -1.0e308", "true")
	doc("binary_part", "The bytes of a string from a position, of a length; a negative length counts back from the position.",
		"alx> binary_part(\"hello\", 1, 3)", "\"ell\"", "alx> binary_part(\"hello\", 5, -2)", "\"lo\"")
	doc("Base.hex_encode32", "Encodes in base 32 with the extended hexadecimal alphabet; options as for encode32.",
		"alx> Base.hex_encode32(\"f\")", "\"CO======\"", "alx> Base.hex_encode32(\"f\", [padding: false])", "\"CO\"")
	doc("Base.hex_decode32", "Decodes base 32 with the extended hexadecimal alphabet; none when the text is not valid.",
		"alx> Base.hex_decode32(\"CO======\")", "some(\"f\")")
	doc("Path.type", "Whether a path is :absolute, :relative, or on Windows :volumerelative.",
		"alx> Path.type(Path.expand(\"docs\"))", ":absolute", "alx> Path.type(\"docs\")", ":relative")
	doc("Path.safe_relative", "A relative path cleaned of . and .., when it stays inside the directory it is relative to; none when it would leave it or is absolute. Given a directory, an absolute path inside it is made relative to it first.",
		"alx> Path.safe_relative(\"a/../b\")", "some(\"b\")", "alx> Path.safe_relative(\"../etc\")", "none")

	doc("System.monotonic_time", "A clock that only moves forward, for measuring: in nanoseconds, or in a unit, :second, :millisecond, :microsecond or :nanosecond.",
		"alx> System.monotonic_time(:millisecond) >= 0", "true")
	doc("System.system_time", "The time since 1970 in nanoseconds, or in a unit as for monotonic_time.",
		"alx> System.system_time(:second) > 1700000000", "true")
	doc("System.os_time", "The operating system's clock, as for system_time.", "alx> System.os_time(:second) > 1700000000", "true")
	doc("System.convert_time_unit", "Converts an amount of time between units, rounding down.",
		"alx> System.convert_time_unit(2, :second, :millisecond)", "2000", "alx> System.convert_time_unit(1500, :millisecond, :second)", "1")
	doc("System.stop", "Ends the program with a status after an orderly shutdown: the main process stops as if it had returned, and the other processes are then stopped in the usual way. System.halt ends it at once.",
		"alx> stop = fn(code: integer): boolean do", "...>   System.stop(code)", "...>   true", "...> end")

	doc("Date.range", "The dates from one to another, inclusive, a day apart or a given number of days; backwards when the last is earlier.",
		"alx> Date.range(~D[2026-01-30], ~D[2026-02-01]) |> Enum.to_list()", "[~D[2026-01-30], ~D[2026-01-31], ~D[2026-02-01]]",
		"alx> Date.range(~D[2026-01-01], ~D[2026-01-31], 7) |> Enum.count()", "5")
	doc("Date.week_of_year", "The ISO 8601 week of the year, from 1 to 53.", "alx> Date.week_of_year(~D[2026-01-01])", "1")
	doc("Time.truncate", "Drops precision: :second keeps no fraction, :millisecond thousandths.", "alx> Time.truncate(~T[10:00:00.123456], :millisecond)", "~T[10:00:00.123000]")
	doc("NaiveDateTime.truncate", "Drops precision, as Time.truncate does.", "alx> NaiveDateTime.truncate(~N[2026-01-01 10:00:00.5], :second)", "~N[2026-01-01 10:00:00]")
	doc("DateTime.truncate", "Drops precision, as Time.truncate does.", "alx> DateTime.truncate(~U[2026-01-01T10:00:00.5Z], :second)", "~U[2026-01-01T10:00:00Z]")
	doc("Duration.new!", "A duration from a keyword list of year:, month:, week:, day:, hour:, minute:, second: and microsecond:.",
		"alx> Duration.new!([hour: 2, minute: 30]).minute", "30")
	doc("URI.merge", "Resolves a reference against a base URI, as a browser resolves a link.",
		"alx> URI.to_string(URI.merge(\"http://a.com/x/y\", \"../z?q=1\"))", "\"http://a.com/z?q=1\"")
	doc("URI.append_path", "Adds a path, which starts with /, to the URI's path.",
		"alx> URI.to_string(URI.append_path(URI.parse(\"http://a.com/api\"), \"/v1\"))", "\"http://a.com/api/v1\"")
	doc("URI.append_query", "Adds a query to the URI's query, joined with &.",
		"alx> URI.to_string(URI.append_query(URI.parse(\"http://a.com/?x=1\"), \"y=2\"))", "\"http://a.com/?x=1&y=2\"")

	doc("OptionParser.parse_head", "Like OptionParser.parse with options, stopping at the first argument that is not a switch.",
		"alx> OptionParser.parse_head([\"--x\", \"1\", \"cmd\", \"--y\"], [strict: [x: :integer]])", "{[x: \"1\"], [\"cmd\", \"--y\"], []}")
	doc("OptionParser.to_argv", "Writes switches back as arguments: --name value, and --name or --no-name for \"true\" and \"false\".",
		"alx> OptionParser.to_argv([name: \"ada\", debug: \"true\", color: \"false\"])", "[\"--name\", \"ada\", \"--debug\", \"--no-color\"]")
	doc("OptionParser.split", "Splits a command line into arguments as a shell does: at spaces outside quotes, with backslash escapes.",
		"alx> OptionParser.split(\"a 'b c' \\\"d e\\\"\")", "[\"a\", \"b c\", \"d e\"]")

	doc("Logger.log", "Logs a message at a level given as :debug, :info, :warning or :error.", "alx> Logger.log(:debug, \"from the docs\")")
	doc("Logger.metadata", "Adds name: value pairs to the calling process's metadata, which goes with every message it logs; without arguments, the metadata so far.",
		"alx> Logger.metadata([request_id: \"r1\"])", "alx> Logger.metadata()", "[request_id: \"r1\"]")
	doc("Logger.add_handler", "Sends every message that passes the level, with its level and metadata, to a function as well as to the console; false when the name is taken. :console names the console itself, which remove_handler can turn off.",
		"alx> me: pid[string] = Process.self(4)", "alx> Logger.add_handler(:doc_handler, fn level, text, _ -> Process.send(me, to_string(level) <> \" \" <> text, 100) end)", "true",
		"alx> Logger.error(\"handled\")", "alx> Process.receive(me, 1000)", "{true, \"error handled\"}", "alx> Logger.remove_handler(:doc_handler)", "true")
	doc("Logger.remove_handler", "Stops sending messages to a handler; false when there is none by that name.",
		"alx> Logger.remove_handler(:never_added)", "false")

	doc("Port.info", "What is known about a port's running program: its name, operating system process id and the bytes written to and read from it; none once it has ended.",
		"alx> me: pid[PortEvent] = Process.self(8)", "alx> ok(port) = Port.open(\"cat\", [], me)", "alx> some(info) = Port.info(port)", "alx> info.name", "\"cat\"", "alx> Port.close(port)", "true")
	doc("Port.monitor", "Sends the program's exit status to another process too, as PortEvent.exit, when it ends; false when it has already ended.",
		"alx> me: pid[PortEvent] = Process.self(8)", "alx> ok(port) = Port.open(\"true\", [], me)", "alx> Process.receive(me, 5000)", "{true, PortEvent.exit(0)}", "alx> Port.monitor(port, me)", "false")

	doc("Node.serve", "Offers a function to other nodes under a name, for Node.call and Node.cast: each call runs it in a process of its own, and a failure is returned to the caller as error(reason). Its argument and result must be able to cross between nodes.",
		"alx> Node.serve(:twice_doc, fn(n: integer): integer do n * 2 end)", "true")
	doc("Node.call", "Runs a function a node serves and returns its result: ok(value), or error(reason) when it failed, nothing is served under the name, or no answer came within 5 seconds or the given milliseconds. The result's type comes from the annotation.",
		"alx> Node.serve(:square_doc, fn(n: integer): integer do n * n end)", "true",
		"alx> squared: result[integer, string] = Node.call(Node.self(), :square_doc, 7)", "alx> squared", "ok(49)")
	doc("Node.cast", "Runs a function a node serves without waiting for it.",
		"alx> Node.serve(:noted_doc, fn(n: integer): integer do n end)", "true", "alx> Node.cast(Node.self(), :noted_doc, 1)", "true")
	doc("Node.register_global", "Registers a process under a name that no connected node has for the same message type, so that any of them finds it with whereis_global; false when one has.",
		"alx> me: pid[string] = Process.self(4)", "alx> Node.register_global(me, :global_doc)", "true", "alx> Node.register_global(me, :global_doc)", "false")
	doc("Node.whereis_global", "Finds a process registered under a name on this node or any connected one. The message type comes from the annotation.",
		"alx> me: pid[string] = Process.self(4)", "alx> Node.register_global(me, :global_find_doc)", "true",
		"alx> found: option[pid[string]] = Node.whereis_global(:global_find_doc)", "alx> case found do", "...>   some(_) -> \"found\"", "...>   none -> \"missing\"", "...> end", "\"found\"")

	module("Range", "Collections", "Ranges of integers, first..last//step: a Range struct with first, last and step, and an enumerable of its integers. A range written where a stream is expected is that stream.")
	doc("Range.new", "The range from first to last, a step of 1 apart, or of a given step.",
		"alx> Range.new(1, 3)", "1..3", "alx> Range.new(0, 10, 5) |> Enum.to_list()", "[0, 5, 10]")
	doc("Range.size", "How many integers a range holds.", "alx> Range.size(1..10)", "10", "alx> Range.size(1..10//4)", "3", "alx> Range.size(1..0//1)", "0")
	doc("Range.disjoint?", "Reports whether two ranges hold no integer in common.", "alx> Range.disjoint?(1..5, 6..9)", "true", "alx> Range.disjoint?(1..5, 5..9)", "false")
	doc("Range.shift", "Moves a range by a number of its steps.", "alx> Range.shift(1..3, 2)", "3..5")
	doc("Range.split", "Splits a range after a number of its integers, or before the last of them for a negative number.", "alx> Range.split(1..10, 3)", "{1..3, 4..10}")
	doc("Range.to_list", "The integers of a range, in order.", "alx> Range.to_list(5..1//-2)", "[5, 3, 1]")
	doc("Stream.into", "Writes each element to a file opened with File.open as the stream is consumed, and passes the elements on; a function, when given, makes the text written for each.",
		"alx> path = Path.join(System.tmp_dir!(), \"stream_into_doc.txt\")", "alx> ok(f) = File.open(path, [:write])",
		"alx> Stream.into([\"a\\n\", \"b\\n\"], f) |> Enum.count()", "2", "alx> File.close(f)", "true", "alx> File.read(path)", "ok(\"a\\nb\\n\")")
}
