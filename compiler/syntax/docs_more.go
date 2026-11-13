package syntax

func init() {
	doc("Enum.chunk_while", "Splits into chunks under the control of a state. The step function takes an element and the state and returns {emit, next_state}, where emit is some(chunk) to produce a chunk or none; the last function may produce one more chunk from the final state.",
		"alx> Enum.chunk_while([1, 2, 6, 7, 20], Enum.take([0], 0), fn n, run ->",
		"...>   case run do",
		"...>     [last | _] when n - last > 1 -> {some(Enum.reverse(run)), [n]}",
		"...>     _ -> {none, prepend(run, n)}",
		"...>   end",
		"...> end, fn run -> if run == [] do none else some(Enum.reverse(run)) end end)",
		"[[1, 2], [6, 7], [20]]")
	doc("Stream.chunk_while", "Lazily splits into chunks under the control of a state; see Enum.chunk_while.",
		"alx> Stream.chunk_while(1..7, 0, fn n, total ->",
		"...>   if total + n >= 6 do {some(total + n), 0} else {none, total + n} end",
		"...> end, fn total -> if total > 0 do some(total) else none end end) |> Enum.to_list()",
		"[6, 9, 6, 7]")

	doc("Calendar.strftime", "Formats a Date, Time, NaiveDateTime or DateTime. Directives: %Y %y year, %m month, %d day, %j day of year, %q quarter, %u weekday number (Monday is 1), %a %A weekday name, %b %B month name, %H %I hour, %M minute, %S second, %f fraction, %p %P AM/PM, %z %Z zone, %c %x %X preferred forms, %% a percent sign. A flag after % changes padding (- none, 0 zeros, _ spaces) and a number sets the width. A directive the value has no field for fails.",
		"alx> Calendar.strftime(~D[2026-03-05], \"%A %-d %B %Y\")", "\"Thursday 5 March 2026\"",
		"alx> Calendar.strftime(~U[2026-03-14T15:09:26Z], \"%y-%m-%d %I:%M:%S %p\")", "\"26-03-14 03:09:26 PM\"",
		"alx> Calendar.strftime(~T[09:04:05], \"%H:%M\")", "\"09:04\"",
		"alx> Calendar.strftime(~N[2026-03-05 09:04:05], \"%j %q %u %a %b %%\")", "\"064 1 4 Thu Mar %\"")

	doc("URI.encode", "Percent-encodes every character that is neither reserved nor unreserved in a URI, so an address keeps its structure.",
		"alx> URI.encode(\"https://example.com/a b?q=é\")", "\"https://example.com/a%20b?q=%C3%A9\"")
	doc("URI.decode", "Decodes percent-encoding, returning an error for a malformed escape.",
		"alx> URI.decode(\"a%20b\")", "ok(\"a b\")",
		"alx> case URI.decode(\"%zz\") do", "...>   ok(_) -> \"valid\"", "...>   error(_) -> \"malformed\"", "...> end", "\"malformed\"")
	doc("URI.encode_www_form", "Encodes text as a form value: everything but letters, digits and -_.~ is escaped, and a space becomes +.",
		"alx> URI.encode_www_form(\"a b&c=d\")", "\"a+b%26c%3Dd\"")
	doc("URI.decode_www_form", "Decodes a form value, where + is a space.",
		"alx> URI.decode_www_form(\"a+b%26c\")", "ok(\"a b&c\")")
	doc("URI.encode_query", "Encodes a map as a query string, keys in ascending order.",
		"alx> URI.encode_query(%{\"q\" => \"a b\", \"page\" => \"2\"})", "\"page=2&q=a+b\"")
	doc("URI.decode_query", "Decodes a query string into a map; a later pair replaces an earlier one with the same key.",
		"alx> URI.decode_query(\"q=a+b&page=2\")", "%{\"page\" => \"2\", \"q\" => \"a b\"}")

	doc("Version.parse", "Parses a semantic version into a Version struct, with its pre-release identifiers and build metadata.",
		"alx> ok(v) = Version.parse(\"2.10.3\")", "alx> {v.major, v.minor, v.patch}", "{2, 10, 3}",
		"alx> ok(pre) = Version.parse(\"1.0.0-rc.1+build5\")", "alx> {pre.pre, pre.build}", "{[\"rc\", \"1\"], some(\"build5\")}",
		"alx> case Version.parse(\"1.2\") do", "...>   ok(_) -> \"valid\"", "...>   error(reason) -> reason", "...> end", "\"invalid version \\\"1.2\\\"\"")
	doc("Version.compare", "Returns :lt, :eq or :gt as the first version is lower than, equal to or higher than the second. A pre-release is lower than its release. Fails on an invalid version.",
		"alx> Version.compare(\"1.9.0\", \"1.10.0\")", ":lt", "alx> Version.compare(\"2.0.0-rc.1\", \"2.0.0\")", ":lt", "alx> Version.compare(\"1.0.0-alpha.2\", \"1.0.0-alpha.10\")", ":lt", "alx> Version.compare(\"3.1.4\", \"3.1.4\")", ":eq")

	doc("Enum.into", "Adds the elements to a collectable: a list or set takes them as they are, a map takes {key, value} tuples, and a string takes strings. An empty %{} or [] takes its type from the elements. for ... into: does the same.",
		"alx> Enum.into([{\"a\", 1}], %{\"z\" => 0})", "%{\"a\" => 1, \"z\" => 0}",
		"alx> Enum.into([1, 2], [0])", "[0, 1, 2]",
		"alx> Enum.into([\"b\", \"c\"], \"a\")", "\"abc\"",
		"alx> Enum.into([3, 1, 3], MapSet.new([2])) |> MapSet.to_list()", "[1, 2, 3]", "alx> Enum.into([{1, \"one\"}], %{})", "%{1 => \"one\"}")

	doc("capture_io", "Runs the function and returns what was written to standard output meanwhile.",
		"alx> capture_io(fn -> IO.puts(\"hello\") end)", "\"hello\\n\"")
	doc("on_exit", "Registers a function to run when the current test ends, whether it passed or failed; several run last first. A failure in one fails the test.",
		"alx> File.write!(\"doc_on_exit.txt\", \"temporary\")", "alx> on_exit(fn -> File.rm!(\"doc_on_exit.txt\") end)", "alx> File.exists?(\"doc_on_exit.txt\")", "true")
	legacy("assert_receive", "assert_receive(pid[t], pattern)", "assert_receive(pid[t], pattern, integer)", "assert_receive(pid[t], pattern, integer, string)")
	legacy("refute_receive", "refute_receive(pid[t], pattern)", "refute_receive(pid[t], pattern, integer)", "refute_receive(pid[t], pattern, integer, string)")
	legacy("assert_received", "assert_received(pid[t], pattern)", "assert_received(pid[t], pattern, string)")
	legacy("refute_received", "refute_received(pid[t], pattern)", "refute_received(pid[t], pattern, string)")
	doc("assert_receive", "A statement that takes the first message in the current process's mailbox matching a pattern, waiting for one to arrive: 100 milliseconds unless --receive-timeout or a third argument says otherwise. Other messages stay in the mailbox in their order. Names in the pattern are bound for the rest of the test, ^name compares with an existing binding, and when adds a guard. A failure shows the pattern, the values of pinned names and the last ten messages in the mailbox; a fourth argument replaces its first line.",
		"alx> me: pid[tuple[string, integer]] = Process.self(8)",
		"alx> Process.send(me, {\"started\", 1}, 100)", "true",
		"alx> Process.send(me, {\"finished\", 42}, 100)", "true",
		"alx> assert_receive(me, {\"finished\", result})",
		"alx> result", "42",
		"alx> assert_receive(me, {_, count} when count < 10, 500, \"the start was never reported\")",
		"alx> count", "1")
	doc("refute_receive", "A statement that fails if a message matching the pattern is in the current process's mailbox, or arrives within the wait. Use _ for any message. The arguments after the pattern are those of assert_receive.",
		"alx> me: pid[string] = Process.self(4)", "alx> Process.send(me, \"ok\", 100)", "true",
		"alx> refute_receive(me, \"error\", 10)", "alx> assert_receive(me, \"ok\")", "alx> refute_receive(me, _, 10)")
	doc("assert_received", "Like assert_receive, but looks only at messages that have already arrived and does not wait. An argument after the pattern replaces the first line of the failure.",
		"alx> me: pid[integer] = Process.self(4)", "alx> Process.send(me, 7, 100)", "true",
		"alx> assert_received(me, n when n > 5)", "alx> n", "7")
	doc("refute_received", "Like refute_receive, but looks only at messages that have already arrived and does not wait.",
		"alx> me: pid[integer] = Process.self(4)", "alx> refute_received(me, _)", "alx> Process.send(me, 7, 100)", "true", "alx> refute_received(me, 8, \"an eight arrived\")")

	doc("Duration.years", "A duration of that many years; the other units are zero.", "alx> Duration.years(3).year", "3")
	doc("Duration.months", "A duration of that many months; the other units are zero.", "alx> Duration.months(3).month", "3")
	doc("Duration.weeks", "A duration of that many weeks; the other units are zero.", "alx> Duration.weeks(3).week", "3")
	doc("Duration.days", "A duration of that many days; the other units are zero.", "alx> Duration.days(3).day", "3")
	doc("Duration.hours", "A duration of that many hours; the other units are zero.", "alx> Duration.hours(3).hour", "3")
	doc("Duration.minutes", "A duration of that many minutes; the other units are zero.", "alx> Duration.minutes(3).minute", "3")
	doc("Duration.seconds", "A duration of that many seconds; the other units are zero.", "alx> Duration.seconds(3).second", "3")
	doc("Duration.microseconds", "A duration of that many microseconds; the other units are zero.", "alx> Duration.microseconds(3).microsecond", "3")
	doc("Duration.add", "Adds two durations unit by unit. Nothing is carried from one unit to another.",
		"alx> Duration.add(Duration.months(1), Duration.days(10)) |> Duration.to_iso8601()", "\"P1M10D\"")
	doc("Duration.subtract", "Subtracts the second duration from the first, unit by unit.",
		"alx> Duration.subtract(Duration.days(10), Duration.days(3)).day", "7")
	doc("Duration.negate", "The same amounts with the opposite sign, for shifting backwards.",
		"alx> Date.shift(~D[2026-03-31], Duration.negate(Duration.months(1)))", "~D[2026-02-28]")
	doc("Duration.multiply", "Multiplies every unit.",
		"alx> Duration.multiply(Duration.hours(2), 3).hour", "6")
	doc("Duration.to_iso8601", "The duration in ISO 8601 form, leaving out units that are zero.",
		"alx> Duration.to_iso8601(Duration.add(Duration.years(1), Duration.minutes(90)))", "\"P1YT90M\"", "alx> Duration.to_iso8601(Duration.days(0))", "\"PT0S\"")
	doc("Duration.from_iso8601", "Parses an ISO 8601 duration such as P1Y2M3DT4H5M6S.",
		"alx> Duration.from_iso8601(\"P2Y1M4DT3H7M1.5S\")", "ok(%Duration{year: 2, month: 1, week: 0, day: 4, hour: 3, minute: 7, second: 1, microsecond: 500000})",
		"alx> case Duration.from_iso8601(\"soon\") do", "...>   ok(_) -> \"valid\"", "...>   error(_) -> \"invalid\"", "...> end", "\"invalid\"")

	doc("Date.shift", "Moves a date by a duration of years, months, weeks and days. A month is added on the calendar: the day is kept, or becomes the last day the new month has. A duration with time units fails.",
		"alx> Date.shift(~D[2026-01-31], Duration.months(1))", "~D[2026-02-28]",
		"alx> Date.shift(~D[2024-02-29], Duration.add(Duration.years(1), Duration.days(1)))", "~D[2025-03-01]")
	doc("Time.shift", "Moves a time of day by a duration of hours, minutes, seconds and microseconds, wrapping around midnight. A duration with date units fails.",
		"alx> Time.shift(~T[23:30:00], Duration.minutes(45))", "~T[00:15:00]")
	doc("NaiveDateTime.shift", "Moves a date and time by a duration: the calendar units first, then the time units.",
		"alx> NaiveDateTime.shift(~N[2026-01-31 22:00:00], Duration.add(Duration.months(1), Duration.hours(3)))", "~N[2026-03-01 01:00:00]")
	doc("DateTime.shift", "Moves a DateTime by a duration, staying in its time zone: calendar units move its wall clock, so a day later is the same time of day across a clock change, and time units are elapsed time.",
		"alx> DateTime.shift(~U[2026-01-31T12:00:00Z], Duration.months(1))", "~U[2026-02-28T12:00:00Z]",
		"alx> paris = DateTime.shift_zone!(~U[2026-03-28T11:00:00Z], \"Europe/Paris\")",
		"alx> DateTime.to_iso8601(DateTime.shift(paris, Duration.days(1)))", "\"2026-03-29T12:00:00+02:00\"",
		"alx> DateTime.to_iso8601(DateTime.shift(paris, Duration.hours(24)))", "\"2026-03-29T13:00:00+02:00\"")

	doc("DateTime.shift_zone", "The same moment as the wall clock of another time zone shows it, by its name in the zone database, which is built into the program. An unknown name is an error.",
		"alx> case DateTime.shift_zone(~U[2026-01-05T12:00:00Z], \"Europe/Paris\") do", "...>   ok(paris) -> DateTime.to_string(paris)", "...>   error(reason) -> reason", "...> end", "\"2026-01-05 13:00:00+01:00 CET Europe/Paris\"",
		"alx> DateTime.shift_zone(~U[2026-01-05T12:00:00Z], \"Mars/Olympus\")", "error(\"unknown time zone \\\"Mars/Olympus\\\"\")")
	doc("DateTime.shift_zone!", "The same moment in another time zone; fails on an unknown zone name. The time_zone and utc_offset fields say where it is.",
		"alx> new_york = DateTime.shift_zone!(~U[2026-07-04T16:00:00Z], \"America/New_York\")",
		"alx> DateTime.to_iso8601(new_york)", "\"2026-07-04T12:00:00-04:00\"",
		"alx> new_york.utc_offset", "-14400",
		"alx> DateTime.compare(new_york, ~U[2026-07-04T16:00:00Z])", ":eq",
		"alx> Calendar.strftime(new_york, \"%H:%M %Z %z\")", "\"12:00 EDT -0400\"")
	doc("DateTime.now", "The current moment in a time zone.",
		"alx> case DateTime.now(\"Asia/Tokyo\") do", "...>   ok(now) -> now.utc_offset", "...>   error(_) -> 0", "...> end", "32400")
	doc("DateTime.from_naive", "Reads a date and time as the wall clock of a time zone. A time the clocks skipped moves forward by the gap, and one they repeated takes its first occurrence.",
		"alx> case DateTime.from_naive(~N[2026-01-05 13:00:00], \"Europe/Paris\") do", "...>   ok(paris) -> DateTime.to_unix(paris) == DateTime.to_unix(~U[2026-01-05T12:00:00Z])", "...>   error(_) -> false", "...> end", "true")

	doc("URI.parse", "Splits an address into a URI struct: scheme, userinfo, host, port, path, query and fragment. Parts the address lacks are none; http, https, ws, wss and ftp get their usual port. Text that is not an address becomes a URI with only a path.",
		"alx> uri = URI.parse(\"https://ada@example.com:8443/a/b?q=1#top\")",
		"alx> {uri.scheme, uri.userinfo, uri.host, uri.port}", "{some(\"https\"), some(\"ada\"), some(\"example.com\"), some(8443)}",
		"alx> {uri.path, uri.query, uri.fragment}", "{\"/a/b\", some(\"q=1\"), some(\"top\")}",
		"alx> URI.parse(\"http://example.com\").port", "some(80)",
		"alx> URI.parse(\"/only/a/path\").host", "none")
	doc("URI.new", "Like URI.parse, returning an error for text that is not a well-formed address.",
		"alx> case URI.new(\"http://example.com/%zz\") do", "...>   ok(_) -> \"valid\"", "...>   error(_) -> \"malformed\"", "...> end", "\"malformed\"")
	doc("URI.to_string", "Writes a URI struct as text, leaving out the usual port of its scheme.",
		"alx> URI.to_string(URI.parse(\"https://example.com:443/a?b=1\"))", "\"https://example.com/a?b=1\"",
		"alx> uri = URI.parse(\"http://example.com/a\")",
		"alx> URI.to_string(%URI{uri | path: \"/b\", query: some(\"page=2\")})", "\"http://example.com/b?page=2\"")
	doc("Version.parse!", "Parses a semantic version into a Version struct, failing when it is not one.",
		"alx> Version.parse!(\"1.2.3\").minor", "2")
	doc("Version.to_string", "Writes a Version back as text.",
		"alx> Version.to_string(%Version{major: 2, minor: 0, patch: 1, pre: [\"beta\", \"2\"]})", "\"2.0.1-beta.2\"")
	doc("Version.parse_requirement", "Checks a requirement once, giving a Version.Requirement to match versions against.",
		"alx> ok(req) = Version.parse_requirement(\"~> 2.0\")", "alx> Version.match?(\"2.4.0\", req)", "true",
		"alx> case Version.parse_requirement(\"bogus\") do", "...>   ok(_) -> \"valid\"", "...>   error(_) -> \"invalid\"", "...> end", "\"invalid\"")
	doc("Version.parse_requirement!", "Like Version.parse_requirement, failing on an invalid requirement.",
		"alx> Version.match?(\"1.0.0\", Version.parse_requirement!(\">= 1.0.0\"))", "true")
	doc("Version.match?", "Reports whether a version meets a requirement: comparisons with ==, !=, >, >=, <, <= and ~>, joined by and and or. ~> 2.1 allows 2.1 and later within 2; ~> 2.1.3 allows 2.1.3 and later within 2.1. Fails on an invalid version or requirement.",
		"alx> Version.match?(\"2.3.1\", \"~> 2.1\")", "true", "alx> Version.match?(\"3.0.0\", \"~> 2.1\")", "false",
		"alx> Version.match?(\"2.1.9\", \"~> 2.1.3\")", "true", "alx> Version.match?(\"1.5.0\", \">= 1.0.0 and < 2.0.0\")", "true",
		"alx> Version.match?(\"0.9.0\", \">= 1.0.0 or == 0.9.0\")", "true",
		"alx> Version.match?(\"2.1.0-rc.1\", \"~> 2.0\", [allow_pre: false])", "false",
		"alx> Version.match?(Version.parse!(\"2.3.0\"), \"~> 2.1\")", "true")

	doc("Logger.debug", "Writes a debug message to standard error, when the level allows it.", "alx> Logger.debug(\"cache miss\")")
	doc("Logger.info", "Writes an informational message to standard error as time, level and text.", "alx> Logger.info(\"listening on 8080\")")
	doc("Logger.warning", "Writes a warning to standard error.", "alx> Logger.warning(\"retrying\")")
	doc("Logger.error", "Writes an error message to standard error.", "alx> Logger.error(\"connection lost\")")
	doc("Logger.configure", "Sets the lowest level that is written: debug, info, warning, error or none. It starts at debug, or at what the ALCHEM_LOG_LEVEL environment variable names.",
		"alx> Logger.configure(\"warning\")", "alx> Logger.level()", "\"warning\"", "alx> Logger.configure(\"debug\")")
	doc("Logger.level", "The lowest level that is currently written.", "alx> Logger.configure(\"info\")", "alx> Logger.level()", "\"info\"", "alx> Logger.configure(\"debug\")")

	doc("OptionParser.parse", "Reads switches from command-line arguments. The second argument maps each switch to its type: boolean, string, integer, float or count; a third maps one-letter aliases to switch names. It returns the values as text by name, the arguments that are not switches, and the switches that are unknown or have a value of the wrong type. --name=value and --name value both work, --no-name sets a boolean to false, dashes in a name become underscores, and -- ends the switches.",
		"alx> {options, files, invalid} = OptionParser.parse([\"--verbose\", \"--jobs=4\", \"a.txt\", \"--dry-run\", \"--color\", \"red\", \"b.txt\"], %{\"verbose\" => \"boolean\", \"jobs\" => \"integer\", \"dry_run\" => \"boolean\"})",
		"alx> options", "%{\"dry_run\" => \"true\", \"jobs\" => \"4\", \"verbose\" => \"true\"}",
		"alx> files", "[\"a.txt\", \"red\", \"b.txt\"]",
		"alx> invalid", "[{\"--color\", \"\"}]",
		"alx> {short, _, _} = OptionParser.parse([\"-v\", \"-v\", \"--no-color\", \"-n\", \"x\"], %{\"verbose\" => \"count\", \"color\" => \"boolean\", \"name\" => \"string\"}, %{\"v\" => \"verbose\", \"n\" => \"name\"})",
		"alx> short", "%{\"color\" => \"false\", \"name\" => \"x\", \"verbose\" => \"2\"}")

	doc("Atom.to_string", "The name of an atom as a string, without the colon. Interpolation does the same.", "alx> Atom.to_string(:not_found)", "\"not_found\"", "alx> \"status: #{:ok}\"", "\"status: ok\"")
	doc("String.to_atom", "The atom with the given name.", "alx> String.to_atom(\"ok\") == :ok", "true")

	doc("Keyword.get", "The value of the first pair with the key, as an option or with a default.", "alx> Keyword.get([a: 1, b: 2], :b)", "some(2)", "alx> Keyword.get([a: 1], :z, 0)", "0")
	doc("Keyword.fetch", "The value of the first pair with the key, as an option.", "alx> Keyword.fetch([a: 1], :a)", "some(1)")
	doc("Keyword.fetch!", "The value of the first pair with the key; fails when it is absent.", "alx> Keyword.fetch!([a: 1], :a)", "1")
	doc("Keyword.get_values", "Every value stored under the key, in order.", "alx> Keyword.get_values([x: 1, y: 2, x: 3], :x)", "[1, 3]")
	doc("Keyword.has_key?", "Reports whether a pair has the key.", "alx> Keyword.has_key?([a: 1], :a)", "true")
	doc("Keyword.put", "Removes every pair with the key and puts the new pair first.", "alx> Keyword.put([x: 1, y: 2, x: 3], :x, 9)", "[x: 9, y: 2]")
	doc("Keyword.put_new", "Adds the pair only when the key is absent.", "alx> Keyword.put_new([x: 1], :x, 9)", "[x: 1]", "alx> Keyword.put_new([x: 1], :y, 2)", "[y: 2, x: 1]")
	doc("Keyword.delete", "Removes every pair with the key.", "alx> Keyword.delete([x: 1, y: 2, x: 3], :x)", "[y: 2]")
	doc("Keyword.keys", "The keys in order, repeats included.", "alx> Keyword.keys([x: 1, y: 2])", "[:x, :y]")
	doc("Keyword.values", "The values in order.", "alx> Keyword.values([x: 4, y: 5])", "[4, 5]")
	doc("Keyword.merge", "The first list without the keys the second has, followed by the second.", "alx> Keyword.merge([a: 1, b: 2], [b: 9, c: 3])", "[a: 1, b: 9, c: 3]")
	doc("Keyword.take", "Keeps the pairs whose key is in the list.", "alx> Keyword.take([x: 1, y: 2, z: 3], [:x, :z])", "[x: 1, z: 3]")
	doc("Keyword.drop", "Removes the pairs whose key is in the list.", "alx> Keyword.drop([x: 1, y: 2, z: 3], [:x, :z])", "[y: 2]")
	doc("Keyword.update", "Applies the function to the first value under the key, or adds the default at the end when the key is absent.", "alx> Keyword.update([a: 1], :a, 0, &(&1 + 1))", "[a: 2]", "alx> Keyword.update([a: 1], :b, 0, &(&1 + 1))", "[a: 1, b: 0]")
	doc("Keyword.pop", "The first value under the key, as an option, with the list without that key.", "alx> Keyword.pop([a: 1, b: 2], :a)", "{some(1), [b: 2]}")
	doc("Keyword.to_map", "A map from each key to its first value.", "alx> Keyword.to_map([x: 1, y: 2, x: 3])", "%{:x => 1, :y => 2}")

	doc("Port.open", "Starts an external program with arguments. Each line it writes, to standard output or standard error, is sent to the owner as PortEvent.data(text), and PortEvent.exit(status) follows when it ends. The result is an error when the program cannot be started.",
		"alx> me: pid[PortEvent] = Process.self(16)",
		"alx> case Port.open(\"sort\", Enum.take([\"\"], 0), me) do",
		"...>   ok(sorter) ->",
		"...>     Port.command(sorter, \"pear\\napple\\n\")",
		"...>     Port.close(sorter)",
		"...>   error(_) -> false",
		"...> end", "true",
		"alx> assert_receive(me, PortEvent.data(first), 5000)", "alx> first", "\"apple\"",
		"alx> assert_receive(me, PortEvent.data(\"pear\"), 5000)",
		"alx> assert_receive(me, PortEvent.exit(status), 5000)", "alx> status", "0",
		"alx> case Port.open(\"alchem-no-such-program\", Enum.take([\"\"], 0), me) do", "...>   ok(_) -> \"started\"", "...>   error(_) -> \"not found\"", "...> end", "\"not found\"")
	doc("Port.command", "Writes text to the program's standard input; false once the port is closed or the program has gone.",
		"alx> me: pid[PortEvent] = Process.self(8)",
		"alx> case Port.open(\"cat\", Enum.take([\"\"], 0), me) do", "...>   ok(echo) -> Port.command(echo, \"hello\\n\") and Port.close(echo)", "...>   error(_) -> false", "...> end", "true",
		"alx> assert_receive(me, PortEvent.data(\"hello\"), 5000)")
	doc("Port.close", "Closes the program's standard input, so a program that reads to the end can finish; false when it was already closed. The program is ended when its owner, the process its output goes to, ends, and when the Alchem program does, also when it is interrupted or asked to terminate; Port.kill ends it on request.",
		"alx> me: pid[PortEvent] = Process.self(8)",
		"alx> case Port.open(\"cat\", Enum.take([\"\"], 0), me) do", "...>   ok(echo) -> {Port.close(echo), Port.close(echo)}", "...>   error(_) -> {false, false}", "...> end", "{true, false}",
		"alx> assert_receive(me, PortEvent.exit(0), 5000)")
	doc("Port.kill", "Ends the program and waits briefly until it has gone; false when it had already ended. The program is asked to stop first, with an interrupt where the system has one, so that a program which runs others can stop them, and is killed if it has not gone half a second later. The owner still receives PortEvent.exit.",
		"alx> me: pid[PortEvent] = Process.self(8)",
		"alx> case Port.open(\"cat\", Enum.take([\"\"], 0), me) do", "...>   ok(waiting) -> {Port.kill(waiting), Port.kill(waiting)}", "...>   error(_) -> {false, false}", "...> end", "{true, false}",
		"alx> assert_receive(me, PortEvent.exit(_), 5000)")
	doc("Port.os_pid", "The operating system's process identifier of the program.",
		"alx> me: pid[PortEvent] = Process.self(8)",
		"alx> case Port.open(\"cat\", Enum.take([\"\"], 0), me) do", "...>   ok(echo) -> Port.os_pid(echo) > 0 and Port.close(echo)", "...>   error(_) -> false", "...> end", "true")

	doc("Node.start", "Makes this program a node: it listens at the address for other nodes, under a name, and accepts those that know the same cookie. Port 0 picks a free port. With two arguments the cookie comes from the ALCHEM_COOKIE environment variable. Connections are encrypted; a fourth argument, [encrypted: false], turns that off for a trusted network, and only nodes with the same setting connect. A program becomes a node once.",
		"alx> started = Node.start(\"docs\", \"127.0.0.1:0\", \"secret\")",
		"alx> started == ok({}) or started == error(\"this program is already a node\")", "true",
		"alx> Node.self()", "\"docs\"",
		"alx> Node.start(\"docs\", \"127.0.0.1:0\", \"secret\", [loud: true])", "error(\"unknown option :loud; Node.start takes encrypted:\")")
	doc("Node.self", "This node's name, or \"\" before Node.start.",
		"alx> Node.start(\"docs\", \"127.0.0.1:0\", \"secret\")", "alx> Node.self()", "\"docs\"")
	doc("Node.address", "The address this node listens at, with the port that was picked.",
		"alx> Node.start(\"docs\", \"127.0.0.1:0\", \"secret\")", "alx> String.starts_with?(Node.address(), \"127.0.0.1:\")", "true")
	doc("Node.connect", "Connects to the node listening at an address and returns its name. Both nodes must have the same cookie. Messages to its processes are then copied over the connection. With reconnect: true the connection is kept: when it is lost it is made again, a second later at first and up to 30 seconds apart while that keeps failing, until the program ends. With reconnect: n it is given up after n failed attempts in a row, which Node.monitor_nodes reports as \"noreconnect\" and the node's name.",
		"alx> Node.start(\"docs\", \"127.0.0.1:0\", \"secret\")",
		"alx> case Node.connect(\"127.0.0.1:1\") do", "...>   ok(name) -> name", "...>   error(_) -> \"not reachable\"", "...> end", "\"not reachable\"")
	doc("Node.list", "The names of the nodes this one is connected to, in order.",
		"alx> length(Node.list())", "0")
	doc("Node.disconnect", "Closes the connection to a node; false when there is none.",
		"alx> Node.disconnect(\"nobody\")", "false")
	doc("Node.monitor", "Asks for one event when the connection to a node ends, read with Process.event: its reason is \"nodedown\" and the node's name. A node that is not connected produces the event at once.",
		"alx> reference = Node.monitor(\"elsewhere\")",
		"alx> {arrived, noticed, _, reason} = Process.event(1000)",
		"alx> arrived and noticed == reference and reason == \"nodedown elsewhere\"", "true")
	doc("Node.monitor_nodes", "Subscribes the calling process to an event, read with Process.event, for every connection to another node from now on: its reason is \"nodeup\" and the node's name when one is made, \"nodedown\" when one is lost, and \"noreconnect\" when a connection kept with reconnect: n is given up. Every event carries the reference returned. The program must be a node.",
		"alx> Node.start(\"docs\", \"127.0.0.1:0\", \"secret\")",
		"alx> reference = Node.monitor_nodes()",
		"alx> {arrived, _, _, _} = Process.event(10)",
		"alx> arrived or reference == 0", "false")
	doc("Node.whereis", "Finds a process another node has registered under a name, waiting up to 5 seconds or the given milliseconds. The message type comes from the annotation and must be the type the name was registered with. The handle can be sent to and put in messages; receiving, monitoring and linking need a process of this node.",
		"alx> Node.start(\"docs\", \"127.0.0.1:0\", \"secret\")",
		"alx> found: option[pid[string]] = Node.whereis(\"elsewhere\", :logger, 100)",
		"alx> case found do", "...>   some(logger) -> Process.send(logger, \"hello\", 100)", "...>   none -> false", "...> end", "false")
	doc("Process.register", "Gives a process a name by which this node, and the nodes connected to it, can find it. A name belongs to one living process at a time. The message type must be one that can be copied to another node: no functions, streams or other handles tied to this program.",
		"alx> me: pid[string] = Process.self(4)",
		"alx> Process.register(me, :doc_register)", "true",
		"alx> Process.register(me, :doc_register)", "false",
		"alx> Process.unregister(:doc_register)", "true")
	doc("Process.unregister", "Frees a name; false when it was not registered.",
		"alx> Process.unregister(:doc_nobody)", "false")
	doc("Process.whereis", "Finds a process of this node by name. The message type comes from the annotation and must be the one the name was registered with.",
		"alx> me: pid[integer] = Process.self(4)",
		"alx> Process.register(me, :doc_whereis)", "true",
		"alx> found: option[pid[integer]] = Process.whereis(:doc_whereis)",
		"alx> case found do", "...>   some(named) -> Process.send(named, 7, 100)", "...>   none -> false", "...> end", "true",
		"alx> assert_receive(me, 7)",
		"alx> other: option[pid[string]] = Process.whereis(:doc_whereis)",
		"alx> case other do", "...>   some(_) -> \"found\"", "...>   none -> \"registered for another type\"", "...> end", "\"registered for another type\"")

	doc("Stream.publish", "Offers a stream to other nodes under a name. The function builds the stream, once for each reader, in a process of this node that advances it as readers ask; false when the name is taken. The stream stays here: only the elements a reader consumes are copied to it.",
		"alx> Stream.publish(:doc_squares, fn -> Stream.map(Stream.from_index(1), &(&1 * &1)) end)", "true",
		"alx> Stream.publish(:doc_squares, fn -> Stream.map(1..3, &(&1 * &1)) end)", "false")
	doc("Node.stream", "Finds a stream another node has published and returns one that pulls from it, a chunk at a time, as it is consumed. The element type comes from the annotation and must be the one published. An endless stream can be read from; a reader that stops early pulls no more. Reading fails if the other node stops answering.",
		"alx> Node.start(\"docs\", \"127.0.0.1:0\", \"secret\")",
		"alx> squares: result[stream[integer], string] = Node.stream(\"elsewhere\", :doc_squares)",
		"alx> case squares do", "...>   ok(found) -> Enum.take(found, 3)", "...>   error(_) -> Enum.take([0], 0)", "...> end", "Enum.take([0], 0)")
}
