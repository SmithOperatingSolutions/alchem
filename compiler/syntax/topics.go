package syntax

import (
	"strconv"
	"strings"
)

// Topic is one entry of the syntax help: a construct of the language, the
// rules worth knowing about it, and examples. Every example is compiled and
// run by the test suite.
type Topic struct {
	Name, Group, Summary string
	// Notes are short rules, one sentence each.
	Notes    []string
	Examples []Sample
	// See names related topics and library modules.
	See []string
}

// Sample is one example of a topic. Body is statements, shown and run inside
// a function; Defs are the module-level declarations they need. File, when
// set, is a whole test file instead, and Files are other files beside it.
type Sample struct {
	Title, Defs, Body, File string
	Files                   map[string]string
}

// Topics is in presentation order.
var Topics []Topic

func topic(group, name, summary string, notes []string, see []string, examples ...Sample) {
	Topics = append(Topics, Topic{Name: name, Group: group, Summary: summary, Notes: notes, Examples: examples, See: see})
}

// TopicNamed finds a topic by name.
func TopicNamed(name string) (Topic, bool) {
	for _, entry := range Topics {
		if entry.Name == name {
			return entry, true
		}
	}
	return Topic{}, false
}

func init() {
	topic("Basics", "program", "A file is one module; the entry module has a main function.",
		[]string{
			"A file holds exactly one defmodule with an uppercase name.",
			"The entry module has exactly one main/0; imported modules have none.",
			"alchem build main.alc compiles to a native executable; alchem check only reports errors.",
			"The whole file is type-checked before anything runs, including unused functions.",
		}, []string{"functions", "modules", "tests"},
		Sample{Title: "a complete program", File: "defmodule Hello do\n  def greeting(name: string): string do\n    \"hello, #{name}\"\n  end\n\n  def main() do\n    IO.puts(greeting(\"world\"))\n  end\nend\n"})

	topic("Basics", "values", "Integers, floats, booleans and strings.",
		[]string{
			"integer is signed 64-bit and overflow fails at run time; float is 64-bit.",
			"A float literal needs digits on both sides of the point: 1.0, not 1.",
			"There is no implicit conversion: 1 + 1.5 is a type error. Use Float.from_integer, round, trunc.",
			"A float in interpolation or to_string is its shortest text, in exponent form when that is shorter: 1000.0 is \"1.0e3\" and 1250.0 is \"1250.0\". inspect keeps plain digits.",
			"There is no nil: use option and result. Atoms are a type of their own (see atoms).",
		}, []string{"operators", "strings", "option-result"},
		Sample{Title: "literals", Body: "count = 42\nprice = 9.5\nready = true\nname = \"ada\"\nassert(count + 1 == 43)\nassert(price * 2.0 == 19.0)\nassert(ready and name == \"ada\")\nassert(Float.from_integer(count) + 0.5 == 42.5)"})

	topic("Basics", "bindings", "name = expression binds a name once; bindings are immutable.",
		[]string{
			"A name cannot be rebound or shadowed in the same function: pick a new name.",
			"An annotation gives the type where the value alone does not: xs: list[integer] = [].",
			"Bindings made inside a branch do not escape it.",
			"The left side may be a pattern (see patterns).",
		}, []string{"patterns", "values"},
		Sample{Title: "bindings and annotations", Body: "total = 2 + 3 * 4\ndoubled = total * 2\nempty: list[string] = []\nmissing: option[integer] = none\nassert(doubled == 28)\nassert(length(empty) == 0)\nassert(missing == none)"})

	topic("Basics", "operators", "Arithmetic, comparison, boolean, string and list operators.",
		[]string{
			"Arithmetic: + - * / on two integers or two floats; integer / truncates; % and rem are integer remainder; ** is power.",
			"Comparison: == != < <= > >=. == compares lists, tuples, maps, structs and sum types structurally.",
			"Boolean: and, or, not (also && || !); operands must be booleans.",
			"Strings: <> concatenates; text =~ ~r/pattern/ tests a regular expression.",
			"Lists: ++ concatenates, -- removes, value in enumerable tests membership.",
			"first..last is an inclusive range; first..last//step sets the step.",
			"|> passes the left value as the first argument of the call on the right.",
		}, []string{"pipes", "ranges", "strings"},
		Sample{Title: "operators", Body: "assert(7 / 2 == 3 and 7 % 2 == 1)\nassert(2 ** 10 == 1024)\nassert(7.0 / 2.0 == 3.5)\nassert(\"al\" <> \"chem\" == \"alchem\")\nassert([1, 2] ++ [3] == [1, 2, 3])\nassert([1, 2, 3, 2] -- [2] == [1, 3, 2])\nassert(2 in [1, 2, 3] and not (5 in 1..3))\nassert(\"order 42\" =~ ~r/\\d+/)\nassert({1, \"a\"} == {1, \"a\"})"})

	topic("Basics", "strings", "UTF-8 text with interpolation, heredocs and the String module.",
		[]string{
			"\"#{expression}\" interpolates a string, integer, float or boolean; write \\#{ for the literal characters.",
			"Escapes: \\n, \\t, \\r, \\e (escape), \\s (space), \\\\, \\\", \\xHH for a byte, and \\uHHHH, \\UHHHHHHHH or \\u{H...} for a Unicode code point, as in \"caf\\u{e9}\".",
			"A heredoc starts with \"\"\" at the end of a line and ends at the next line that begins with \"\"\"; the indentation of the closing quotes is removed from every line. What follows the closing quotes continues the expression, so a heredoc can be an argument, closed with \"\"\").",
			"A heredoc has escapes and #{...} interpolation, as a string does; ~S\"\"\" starts one that is taken literally, as documentation with examples usually is.",
			"inspect(value) renders any value as text; to_string renders the four primitive types.",
		}, []string{"String", "Regex", "sigils"},
		Sample{Title: "interpolation and concatenation", Body: "name = \"ada\"\nage = 36\nline = \"#{name} is #{age}\"\nassert(line == \"ada is 36\")\nassert(String.upcase(name) <> \"!\" == \"ADA!\")\nassert(inspect([1, 2]) == \"[1, 2]\")"},
		Sample{Title: "heredoc", Body: "text = \"\"\"\n  first line\n    indented\n  \"\"\"\nassert(text == \"first line\\n  indented\\n\")"})

	topic("Basics", "comments", "# comments, and @moduledoc, @doc and @typedoc documentation.",
		[]string{
			"# starts a comment that runs to the end of the line.",
			"@moduledoc documents the module, @doc the next function, @typedoc the next struct or type. Each takes a string or heredoc.",
			"alx> lines inside @doc are examples; a test file runs them with doctest Module (see doctests).",
			"alchem doc file.alc prints a file's documentation.",
		}, []string{"doctests", "strings"},
		Sample{Title: "a documented module", File: "defmodule Temperature do\n  @moduledoc \"\"\"\n  Temperature conversion.\n  \"\"\"\n\n  @doc \"\"\"\n  Converts Celsius to Fahrenheit.\n\n      alx> Temperature.to_fahrenheit(100.0)\n      212.0\n  \"\"\"\n  def to_fahrenheit(celsius: float): float do\n    # nine fifths, plus the offset\n    celsius * 9.0 / 5.0 + 32.0\n  end\n\n  def main() do\n    assert(to_fahrenheit(0.0) == 32.0)\n  end\nend\n"})

	topic("Functions", "functions", "def name(parameter: type): result do ... end.",
		[]string{
			"Parameters carry types; the result type follows the parentheses and may be left out when a first clause or the body fixes it.",
			"The last expression is the result; return value leaves early.",
			"defp defines a function private to its module.",
			"A function that returns nothing omits the result type.",
			"Names may end in ? or !. Recursion is the loop; Process.loop and Enum cover the rest.",
			"&name refers to a named function as a value.",
			"name: type \\\\ value gives a trailing parameter a default, which a call may leave out. The value is a constant: literals, lists, tuples and maps of them, none, some(...), ok(...) or error(...).",
			"A function has one number of parameters: there is no second definition with a different arity.",
		}, []string{"clauses", "anonymous-functions", "generics"},
		Sample{Title: "definitions and calls", Defs: "def area(width: float, height: float): float do\n  width * height\nend\n\ndef sign(n: integer): string do\n  if n < 0 do\n    return \"negative\"\n  end\n  \"non-negative\"\nend\n\ndefp double(n: integer): integer do\n  n * 2\nend",
			Body: "assert(area(2.0, 3.0) == 6.0)\nassert(sign(-1) == \"negative\")\nassert(Enum.map([1, 2], &double) == [2, 4])"},
		Sample{Title: "default arguments", Defs: "def greet(name: string, greeting: string \\\\ \"hello\", marks: integer \\\\ 1): string do\n  \"#{greeting}, #{name}\" <> String.duplicate(\"!\", marks)\nend",
			Body: "assert(greet(\"ada\") == \"hello, ada!\")\nassert(greet(\"ada\", \"hi\") == \"hi, ada!\")\nassert(greet(\"ada\", \"hi\", 3) == \"hi, ada!!!\")"})

	topic("Functions", "clauses", "Several definitions of one function, chosen by pattern and guard.",
		[]string{
			"Clauses are tried top to bottom; parameters may be patterns and literals.",
			"The first clause gives the types; later clauses may leave them out.",
			"when adds a guard, a boolean expression over the parameters.",
			"Clauses of one function must be adjacent and have the same number of parameters; a definition with another number of parameters is another function, as in Elixir: area/1 and area/2.",
			"Together the clauses must cover every input: end with a catch-all when guards leave gaps.",
		}, []string{"patterns", "functions"},
		Sample{Title: "pattern-matching clauses", Defs: "def fact(0): integer do\n  1\nend\n\ndef fact(n: integer) when n > 0 do\n  n * fact(n - 1)\nend\n\ndef fact(_) do\n  raise(\"fact needs a non-negative number\")\nend\n\ndef sum([]: list[integer]): integer do\n  0\nend\n\ndef sum([head | tail]) do\n  head + sum(tail)\nend",
			Body: "assert(fact(5) == 120)\nassert(sum([1, 2, 3]) == 6)"})

	topic("Functions", "anonymous-functions", "fn x -> body end, captures with &, and closures.",
		[]string{
			"fn x, y -> body end takes its types from where it is used: an argument, an annotated binding or a return.",
			"Where nothing gives the types, annotate: fn(x: integer): integer do x + 1 end.",
			"&(&1 + &2) and &String.length(&1) are short forms; &name refers to a named function.",
			"A parameter may be a pattern: fn {key, value} -> ... end.",
			"With clauses on the lines after fn, each pattern -> body with an optional guard, the function takes one argument and tries them in order; match a tuple for several values.",
			"A function value is called like a function, f(1), or as in Elixir, f.(1). Its type is fn[argument, ..., result].",
			"Functions capture the bindings around them, which never change.",
		}, []string{"functions", "Enum"},
		Sample{Title: "function values", Defs: "def adder(offset: integer): fn[integer, integer] do\n  fn value -> value + offset end\nend",
			Body: "add_ten = adder(10)\nassert(add_ten(5) == 15)\nassert(Enum.map([1, 2, 3], fn n -> n * n end) == [1, 4, 9])\nassert(Enum.reduce([1, 2, 3], 0, &(&1 + &2)) == 6)\nassert(Enum.map([\"a\", \"bb\"], &String.length(&1)) == [1, 2])\nsquare = fn(n: integer): integer do n * n end\nassert(square(4) == 16)\npairs = Enum.map(%{\"a\" => 1}, fn {key, value} -> \"#{key}:#{value}\" end)\nassert(pairs == [\"a:1\"])"},
		Sample{Title: "clauses", Body: "labels = Enum.map([0, -3, 7], fn\n  0 -> \"zero\"\n  n when n < 0 -> \"negative\"\n  _ -> \"positive\"\nend)\nassert(labels == [\"zero\", \"negative\", \"positive\"])\nareas = Enum.map([{2, 3}, {4, 0}], fn\n  {_, 0} -> 0\n  {width, height} -> width * height\nend)\nassert(areas == [6, 0])"})

	topic("Functions", "generics", "Lowercase type names are type variables.",
		[]string{
			"A function is generic in the type variables of its parameters; each call picks the types.",
			"Inside the function a type variable's values can be passed, stored, returned and compared, but not used in arithmetic.",
			"Structs and sum types take parameters in brackets: struct Pair[a, b], type Tree[t].",
			"A misspelled type name is therefore read as a type variable and reported where the value is first used.",
		}, []string{"functions", "structs", "sum-types"},
		Sample{Title: "a generic function and type", Defs: "struct Pair[a, b] do\n  left: a\n  right: b\nend\n\ndef swap(pair: Pair[a, b]): Pair[b, a] do\n  %Pair{left: pair.right, right: pair.left}\nend\n\ndef first_or(items: list[t], fallback: t): t do\n  case items do\n    [] -> fallback\n    [head | _] -> head\n  end\nend",
			Body: "swapped = swap(%Pair{left: 1, right: \"one\"})\nassert(swapped.left == \"one\" and swapped.right == 1)\nassert(first_or([\"a\"], \"z\") == \"a\")\nassert(first_or(Enum.take([1], 0), 9) == 9)"})

	topic("Control flow", "if", "if condition do ... else ... end, as a statement or a value.",
		[]string{
			"The condition must be a boolean; there is no truthiness.",
			"As a value both branches must end in the same type, and else is required.",
			"There is no else if: nest, or use cond.",
			"unless condition do ... end runs its body when the condition is false; it may have an else and be used as a value.",
			"On one line: if condition, do: value, else: value, and the same for unless.",
		}, []string{"cond", "case"},
		Sample{Title: "statement and value", Body: "count = 3\nlabel = if count > 0 do \"some\" else \"none\" end\nassert(label == \"some\")\nif count > 2 do\n  IO.puts(\"many\")\nelse\n  IO.puts(\"few\")\nend"},
		Sample{Title: "unless", Body: "items = [1, 2]\nunless items == [] do\n  IO.puts(\"has items\")\nend\nstate = unless length(items) > 5 do \"short\" else \"long\" end\nassert(state == \"short\")"},
		Sample{Title: "one line", Body: "n = 1\nnoun = if n == 1, do: \"item\", else: \"items\"\nassert(noun == \"item\")\nif n > 0, do: IO.puts(\"positive\")"})

	topic("Control flow", "case", "Matches a value against patterns, with optional guards.",
		[]string{
			"Arms are pattern -> body, tried in order; _ matches anything.",
			"when adds a guard to an arm.",
			"A case over a sum type, option or result must cover every variant or end in a catch-all.",
			"As a value every arm must end in the same type.",
		}, []string{"patterns", "sum-types", "option-result"},
		Sample{Title: "matching lists, tuples and results", Defs: "def describe(items: list[integer]): string do\n  case items do\n    [] -> \"empty\"\n    [only] -> \"one: #{only}\"\n    [first | _] when first < 0 -> \"starts negative\"\n    _ -> \"many\"\n  end\nend",
			Body: "assert(describe([7]) == \"one: 7\")\nassert(describe([-1, 2]) == \"starts negative\")\nparsed = case Integer.parse(\"42\") do\n  ok(n) -> n\n  error(_) -> 0\nend\nassert(parsed == 42)"})

	topic("Control flow", "cond", "Runs the first branch whose condition is true.",
		[]string{
			"Arms are condition -> body; end with true -> for the default.",
			"Without a default, a cond in which nothing is true fails with no cond clause matched.",
		}, []string{"if", "case"},
		Sample{Title: "cond as a value", Body: "n = 0\nlabel = cond do\n  n < 0 -> \"negative\"\n  n == 0 -> \"zero\"\n  true -> \"positive\"\nend\nassert(label == \"zero\")"})

	topic("Control flow", "patterns", "Destructuring in bindings, case arms, function parameters, fn parameters, with and for.",
		[]string{
			"Tuples {a, b}; lists [], [a, b], [head | tail]; maps %{\"key\" => value}; structs %Name{field: value}; sum variants Shape.circle(r); some(x), none, ok(x), error(e).",
			"Literals match themselves; _ ignores; ^name matches the value of an existing binding instead of binding.",
			"A map or struct pattern matches when the listed keys or fields match; others are ignored.",
			"A binding whose pattern does not match fails with pattern match failed.",
		}, []string{"case", "clauses", "with", "for"},
		Sample{Title: "destructuring", Body: "{count, label} = {3, \"ok\"}\n[first | rest] = [1, 2, 3]\nassert(count == 3 and label == \"ok\")\nassert(first == 1 and rest == [2, 3])\nexpected = 3\nmatched = case {3, \"x\"} do\n  {^expected, text} -> text\n  _ -> \"other\"\nend\nassert(matched == \"x\")\nfound = case %{\"count\" => 4} do\n  %{\"count\" => n} when n > 0 -> n\n  _ -> 0\nend\nassert(found == 4)"})

	topic("Control flow", "pipes", "value |> function(arguments) passes the value as the first argument.",
		[]string{
			"Each step is a call; the piped value becomes its first argument.",
			"then(value, fn) pipes into a function value; tap(value, fn) runs an effect and passes the value on.",
		}, []string{"Enum", "Stream"},
		Sample{Title: "a pipeline", Body: "total = [1, 2, 3, 4, 5, 6]\n  |> Enum.filter(&(rem(&1, 2) == 0))\n  |> Enum.map(&(&1 * &1))\n  |> Enum.sum()\nassert(total == 56)\nassert((\"  alchem  \" |> String.trim() |> String.upcase()) == \"ALCHEM\")"})

	topic("Control flow", "with", "Chains pattern matches, stopping at the first that fails.",
		[]string{
			"Each clause is pattern <- expression; bindings are visible to later clauses and the body.",
			"Without else, the first value that does not match becomes the result, so error(reason) and none pass straight through.",
			"With else, that value is matched against the else arms.",
		}, []string{"option-result", "patterns", "try"},
		Sample{Title: "chaining results", Defs: "def parse_point(text: string): result[tuple[integer, integer], string] do\n  with [left, right] <- String.split(text, \",\"),\n       ok(x) <- Integer.parse(left),\n       ok(y) <- Integer.parse(right) do\n    ok({x, y})\n  else\n    error(reason) -> error(\"bad number: #{reason}\")\n    parts -> error(\"expected 2 parts, got #{length(parts)}\")\n  end\nend",
			Body: "assert(parse_point(\"3,4\") == ok({3, 4}))\nassert(parse_point(\"3\") == error(\"expected 2 parts, got 1\"))"})

	topic("Control flow", "for", "Comprehensions: generators and filters producing a list.",
		[]string{
			"for pattern <- enumerable, filter, do: expression — or a do ... end block.",
			"Several generators nest; later ones see earlier bindings.",
			"Elements that do not match a generator's pattern are skipped.",
			"Without an option the result is a list. A body that ends in IO.puts or another call with no value gives {} for each element, as Elixir's gives :ok. One option may follow the generators and filters.",
			"into: collectable adds the values to a map (from {key, value} tuples), a set, a list or a string; an empty %{} or [] takes its type from the values.",
			"uniq: true drops values already produced.",
			"reduce: initial takes a do block of accumulator -> body arms; the body's value is the next accumulator and the last one is the result. An empty initial value such as %{} needs a type from an annotation.",
		}, []string{"Enum", "ranges", "patterns"},
		Sample{Title: "generators and filters", Body: "squares = for n <- 1..5, do: n * n\nassert(squares == [1, 4, 9, 16, 25])\npairs = for x <- [1, 2, 3], y <- [1, 2, 3], x < y do\n  {x, y}\nend\nassert(pairs == [{1, 2}, {1, 3}, {2, 3}])\npresent = for some(n) <- [some(1), none, some(3)], do: n\nassert(present == [1, 3])"},
		Sample{Title: "into, uniq and reduce", Body: "squares = for n <- 1..3, into: %{}, do: {n, n * n}\nassert(squares == %{1 => 1, 2 => 4, 3 => 9})\ninitials = for word <- [\"bee\", \"ant\", \"bat\"], uniq: true, do: String.slice(word, 0, 1)\nassert(initials == [\"b\", \"a\"])\ntotal = for x <- [1, 2, 3], x != 2, reduce: 0 do\n  acc -> acc + x\nend\nassert(total == 4)\ncounts: map[string, integer] = for word <- [\"a\", \"b\", \"a\"], reduce: %{} do\n  seen -> Map.update(seen, word, 1, &(&1 + 1))\nend\nassert(counts == %{\"a\" => 2, \"b\" => 1})"})

	topic("Control flow", "try", "try / rescue / catch / else / after, raise, throw and defexception.",
		[]string{
			"raise(message) fails the current process with a message; every runtime failure has one.",
			"defexception Name do message: string ... end declares an exception, a struct with a message field; raise(%Name{...}) raises it.",
			"rescue arms match a failure: e in Name binds the exception, %Name{field: x} matches its fields, and a string literal or a name matches the message of any failure.",
			"throw(value) unwinds to the nearest catch arm that takes the value's type; the type comes from the throws in the body, from the arm's pattern, or from value: Type ->.",
			"else arms match the body's value when nothing was raised or thrown; a failure in an else arm is not rescued by the same try.",
			"after runs on every way out; its value is discarded. return cannot be used inside try.",
			"Prefer result and option for expected failures; try is for the unexpected, and throw for leaving a loop early.",
		}, []string{"option-result", "with"},
		Sample{Title: "rescuing a failure", Defs: "def safe_div(a: integer, b: integer): result[integer, string] do\n  try do\n    ok(a / b)\n  rescue\n    \"division by zero\" -> error(\"cannot divide by zero\")\n    message -> error(message)\n  after\n    IO.puts(\"divided\")\n  end\nend",
			Body: "assert(safe_div(6, 3) == ok(2))\nassert(safe_div(1, 0) == error(\"cannot divide by zero\"))\nmessage = try do\n  raise(\"boom\")\nrescue\n  text -> text\nend\nassert(message == \"boom\")"},
		Sample{Title: "exceptions, throw and else", Defs: "defexception NotFound do\n  message: string\n  id: integer\nend\n\ndef fetch(id: integer): string do\n  if id > 9 do\n    raise(%NotFound{message: \"no such item\", id: id})\n  end\n  \"item\"\nend",
			Body: "missing = try do\n  fetch(42)\nrescue\n  e in NotFound -> \"missing \" <> to_string(e.id)\nend\nassert(missing == \"missing 42\")\nfirst = try do\n  Enum.each([1, 7, 9], fn n -> if n > 5 do throw(n) end end)\n  0\ncatch\n  n -> n\nend\nassert(first == 7)\nparsed = try do\n  Integer.parse(\"12\")\nrescue\n  _ -> 0\nelse\n  ok(n) -> n\n  error(_) -> -1\nend\nassert(parsed == 12)"})

	topic("Data", "lists", "list[T]: immutable, written [1, 2, 3].",
		[]string{
			"An empty list needs a type from an annotation or its use: xs: list[integer] = [].",
			"[head | tail] is a pattern; build with prepend(list, value), ++ or Enum.",
			"list[index] reads by zero-based position and fails out of range; Enum.at returns an option.",
			"length(list), hd(list), tl(list). The Enum module works on every enumerable; List has positional updates.",
		}, []string{"Enum", "List", "for", "patterns"},
		Sample{Title: "building and reading lists", Body: "numbers = [3, 1, 2]\nassert(numbers[0] == 3 and length(numbers) == 3)\nassert(prepend(numbers, 0) == [0, 3, 1, 2])\nassert(Enum.sort(numbers) == [1, 2, 3])\nassert(Enum.at(numbers, 9) == none)\nnested: list[list[integer]] = [[], [1, 2]]\nassert(nested[1][0] == 1)"})

	topic("Data", "tuples", "tuple[A, B]: a fixed group of values, written {a, b}.",
		[]string{
			"Positions have their own types; read with tuple[index] using a literal index, or destructure.",
			"{} is the empty tuple, the value of a function that returns nothing useful.",
		}, []string{"patterns", "structs"},
		Sample{Title: "tuples", Defs: "def min_max(items: list[integer]): tuple[integer, integer] do\n  {Enum.min(items), Enum.max(items)}\nend",
			Body: "{low, high} = min_max([3, 9, 2])\nassert(low == 2 and high == 9)\npair = {\"a\", 1}\nassert(pair[0] == \"a\" and pair[1] == 1)"})

	topic("Data", "maps", "map[K, V]: immutable, written %{key => value}.",
		[]string{
			"Keys are integers, strings or booleans; all keys share one type and all values another.",
			"map[key] fails when the key is absent; Map.get returns an option, or a default with a third argument.",
			"Map.put, Map.delete, Map.update and friends return a new map; the original is unchanged.",
			"Maps enumerate as {key, value} tuples in ascending key order.",
			"An empty map needs a type: counts: map[string, integer] = %{}.",
		}, []string{"Map", "MapSet", "structs"},
		Sample{Title: "reading and updating maps", Body: "stock = %{\"apple\" => 3, \"pear\" => 0}\nmore = Map.put(stock, \"fig\", 7)\nassert(stock[\"apple\"] == 3 and map_size(more) == 3)\nassert(Map.get(stock, \"kiwi\") == none)\nassert(Map.get(stock, \"kiwi\", 0) == 0)\nassert(Map.update(stock, \"apple\", 1, &(&1 + 1))[\"apple\"] == 4)\nnames = Enum.map(stock, fn {name, _} -> name end)\nassert(names == [\"apple\", \"pear\"])\ncounts: map[string, integer] = %{}\nassert(map_size(counts) == 0)"})

	topic("Data", "structs", "struct Name do field: type ... end: a named record.",
		[]string{
			"Declared inside a module. A field may have a default, field: type = value, which %Name{...} fills in when it leaves the field out; every other field must be given, and %Name{} gives every field its default.",
			"value.field reads; %Name{value | field: new} copies with fields replaced.",
			"%Name{field: pattern} is a pattern; unlisted fields are ignored.",
			"From another module the type is Module.Name and the literal %Module.Name{...}.",
		}, []string{"sum-types", "generics", "patterns"},
		Sample{Title: "declare, build, update, match", Defs: "struct Account do\n  owner: string\n  balance: integer = 0\nend\n\ndef deposit(account: Account, amount: integer): Account do\n  %Account{account | balance: account.balance + amount}\nend\n\ndef owner_of(%Account{owner: name}: Account): string do\n  name\nend",
			Body: "assert(%Account{owner: \"bo\"}.balance == 0)\naccount = %Account{owner: \"ada\", balance: 10}\nricher = deposit(account, 15)\nassert(richer.balance == 25 and account.balance == 10)\nassert(owner_of(richer) == \"ada\")"})

	topic("Data", "sum-types", "type Name do variant(fields) ... end: a value that is one of several shapes.",
		[]string{
			"Build with Name.variant(arguments), or Name.variant for one without fields; the same forms are patterns.",
			"A case or set of clauses over a sum type must cover every variant or include a catch-all.",
			"Sum types may be recursive and take type parameters: type Tree[t].",
			"Use a sum type where Elixir would use atoms or tagged tuples.",
		}, []string{"case", "structs", "option-result"},
		Sample{Title: "variants and matching", Defs: "type Shape do\n  circle(radius: float)\n  rect(width: float, height: float)\n  empty\nend\n\ndef area(shape: Shape): float do\n  case shape do\n    Shape.circle(radius) -> 3.14159 * radius * radius\n    Shape.rect(width, height) -> width * height\n    Shape.empty -> 0.0\n  end\nend",
			Body: "assert(area(Shape.rect(2.0, 3.0)) == 6.0)\nassert(area(Shape.empty) == 0.0)\nshapes = [Shape.circle(1.0), Shape.empty]\nassert(length(shapes) == 2)"})

	topic("Data", "option-result", "option[T] is some(value) or none; result[T, E] is ok(value) or error(reason).",
		[]string{
			"These replace nil and {:ok, value} / {:error, reason} tuples.",
			"Library functions return option for an absent value and result for an expected failure; names ending in ! fail instead.",
			"Take them apart with case, with, or a pattern in for.",
			"none, or ok(1) alone, needs a type from an annotation, parameter or return type.",
		}, []string{"case", "with", "try"},
		Sample{Title: "returning and matching", Defs: "def halve(n: integer): result[integer, string] do\n  if n % 2 == 0 do\n    ok(n / 2)\n  else\n    error(\"#{n} is odd\")\n  end\nend\n\ndef first_even(items: list[integer]): option[integer] do\n  Enum.find(items, &(rem(&1, 2) == 0))\nend",
			Body: "assert(halve(10) == ok(5))\nassert(halve(3) == error(\"3 is odd\"))\nlabel = case first_even([1, 3]) do\n  some(n) -> \"found #{n}\"\n  none -> \"none found\"\nend\nassert(label == \"none found\")"})

	topic("Data", "atoms", ":name is an atom; [name: value] is a keyword list.",
		[]string{
			"An atom is a name used as a value, of type atom. Atoms compare, sort, match in patterns, key maps and interpolate as their name.",
			"A colon starts an atom unless it follows a name or a closing bracket, where it introduces a type or a value: write a space before :name.",
			"Any atom fits the type atom, so a case over atoms needs a catch-all. For a fixed set of alternatives the compiler should check, use a sum type.",
			"Library functions do not return {:ok, value} tuples: they return option and result.",
			"[name: value, other: value] is a keyword list, a list[tuple[atom, T]] whose values share one type. It keeps its order and may repeat a key; the Keyword module reads and changes it.",
		}, []string{"sum-types", "option-result", "Atom", "Keyword", "maps"},
		Sample{Title: "atoms and a keyword list", Defs: "def status(code: integer): atom do\n  case code do\n    200 -> :ok\n    404 -> :not_found\n    _ -> :error\n  end\nend",
			Body: "assert(status(404) == :not_found)\nassert(\"status: #{status(200)}\" == \"status: ok\")\ncounts = %{:red => 1, :blue => 2}\nassert(counts[:blue] == 2)\noptions = [verbose: true, color: false]\nassert(Keyword.get(options, :verbose) == some(true))\nassert(Keyword.put(options, :color, true) == [color: true, verbose: true])\nassert(options == [{:verbose, true}, {:color, false}])"})

	topic("Data", "ranges", "first..last: the integers from first to last inclusive.",
		[]string{
			"Counts down when first > last; first..last//step sets the step.",
			"A range is a Range struct, with first, last and step, and an enumerable of its integers: use it with Enum, Stream, for and in, and the Range functions. Written where a stream[integer] is expected, it is that stream.",
		}, []string{"streams", "for", "Enum"},
		Sample{Title: "ranges", Body: "assert(Enum.to_list(1..4) == [1, 2, 3, 4])\nassert(Enum.to_list(3..1) == [3, 2, 1])\nassert(Enum.to_list(0..10//5) == [0, 5, 10])\nassert(Enum.sum(1..100) == 5050)\nassert(3 in 1..5)\nr = 1..10//3\nassert(r.step == 3 and Range.size(r) == 4)\nassert(Enum.slice([1, 2, 3, 4, 5], 1..-2) == [2, 3, 4])"})

	topic("Data", "streams", "stream[T]: a lazy sequence, consumed by Enum.",
		[]string{
			"Stream functions build a pipeline and run nothing; an Enum function (to_list, take, sum, each, reduce) pulls only what it needs.",
			"Streams may be infinite: Stream.iterate, Stream.cycle, Stream.from_index, Stream.repeatedly, Stream.unfold.",
			"File.stream!(path) reads a file lazily by line, or by chunks of bytes with a size; IO.stream() reads standard input.",
			"Stream.chunk_every(n) batches a stream for processing in chunks.",
			"Streams cannot be compared or sent to a process.",
		}, []string{"Stream", "Enum", "ranges", "File"},
		Sample{Title: "lazy pipelines", Body: "evens = Stream.iterate(0, &(&1 + 2))\nassert(Enum.take(evens, 3) == [0, 2, 4])\nbatches = 1..1000000000\n  |> Stream.map(&(&1 * 2))\n  |> Stream.chunk_every(2)\n  |> Enum.take(2)\nassert(batches == [[2, 4], [6, 8]])"})

	topic("Data", "sigils", "~r regex, ~w words, ~s strings, ~D ~T ~N ~U dates and times.",
		[]string{
			"~r/pattern/ is a regex checked at compile time (RE2 syntax); modifiers i, m, s, u may follow.",
			"~w(one two) is a list of strings; ~s(text) is a string that may contain double quotes.",
			"~D[2026-01-05] Date, ~T[13:04:05] Time, ~N[2026-01-05 13:04:05] NaiveDateTime, ~U[2026-01-05T13:04:05Z] DateTime.",
			"Delimiters may be / | \" ' ( ) [ ] { } < >; the text has no escapes.",
			"~s, ~w and ~r interpolate #{expression}; ~S never does. A ~r that interpolates is compiled when it runs rather than checked at compile time.",
			"String.replace and String.split accept a ~r in place of the text to look for.",
			"~c(text) is the code points of the text as a list of integers; there are no charlists.",
			"~h is an HTML template: it builds Markup, escaping every value it interpolates (see alchem syntax templates); ~H does not interpolate.",
			"Any other letter is a sigil the program defines: ~x(text)mods calls sigil_x(text, \"mods\"), a function taking two strings. A lower-case one interpolates.",
		}, []string{"Regex", "Date", "strings"},
		Sample{Title: "sigils", Body: "assert(~w(red green blue) == [\"red\", \"green\", \"blue\"])\nassert(Regex.run(~r/(\\d+)-(\\d+)/, \"10-20\") == some([\"10-20\", \"10\", \"20\"]))\nassert(\"Hello\" =~ ~r/^hello$/i)\nassert(Date.add(~D[2026-12-31], 1) == ~D[2027-01-01])\nassert(~s(say \"hi\") == \"say \\\"hi\\\"\")"},
		Sample{Title: "interpolation and regular expressions with String", Body: "name = \"ada\"\nassert(~s(hello #{name}) == \"hello ada\")\nassert(~w(#{name} lovelace) == [\"ada\", \"lovelace\"])\nassert(Regex.match?(~r/^#{name}$/i, \"ADA\"))\nassert(~S(raw #{name}) == \"raw \\#{name}\")\nassert(String.replace(\"a1b22c\", ~r/[0-9]+/, \"-\") == \"a-b-c\")\nassert(String.split(\"a, b;c\", ~r/[,;] */) == [\"a\", \"b\", \"c\"])"},
		Sample{Title: "code points and a sigil of your own", Defs: "def sigil_p(text: string, modifiers: string): list[string] do\n  parts = String.split(text, \"/\")\n  if modifiers == \"r\" do\n    Enum.reverse(parts)\n  else\n    parts\n  end\nend",
			Body: "assert(~c(hi!) == [104, 105, 33])\nassert(~p(usr/local/bin) == [\"usr\", \"local\", \"bin\"])\nroot = \"opt\"\nassert(~p(#{root}/bin)r == [\"bin\", \"opt\"])"})

	topic("Modules", "modules", "import \"file.alc\" brings another module's public functions and types.",
		[]string{
			"import takes a path relative to the importing file; call with the module's name: Math.double(3).",
			"def is public, defp private. Imported types are written Module.Type.",
			"Imports of a published package name a host path and version: import \"github.com/owner/repo@v1.2.0/lib/math.alc\"; versions are recorded in alchem.lock.",
			"Library modules (Enum, String, ...) need no import.",
		}, []string{"program", "extern", "functions"},
		Sample{Title: "two files", File: "defmodule ShapesTest do\n  import \"geometry.alc\"\n\n  test \"imported functions and types\" do\n    size = %Geometry.Size{width: 2, height: 3}\n    assert(Geometry.area(size) == 6)\n  end\nend\n",
			Files: map[string]string{"geometry.alc": "defmodule Geometry do\n  struct Size do\n    width: integer\n    height: integer\n  end\n\n  def area(size: Size): integer do\n    size.width * size.height\n  end\nend\n"}})

	topic("Text", "templates", "~h\"...\" and ~h\"\"\"...\"\"\" are HTML templates that escape what they interpolate.",
		[]string{
			"A template's own text is HTML as written. Each #{...} value is escaped by its type: a string is escaped, Markup (such as another template) goes in as it is, integers, floats and atoms are written as text, and a list of Markup is joined.",
			"The result is a Markup value; Markup.to_string gives its text. Markup.raw makes Markup from trusted text, and Markup.escape escapes a string.",
			"Markup.parts takes a template's Markup apart into its fixed text and its values, for a library that sends the fixed text once and then only the values that change.",
			"Quote attribute values, href=\"#{url}\": escaping makes a value safe inside quotes. It does not check what a URL points to.",
			"Any other type in #{...}, such as a boolean or a map, is a compile error; convert it to a string first.",
		}, []string{"sigils", "strings"},
		Sample{Title: "a list page", File: "defmodule Example do\n  def item(name: string): Markup do\n    ~h\"<li>#{name}</li>\"\n  end\n\n  def page(names: list[string]): Markup do\n    ~h\"\"\"\n    <h1>#{length(names)} names</h1>\n    <ul>#{Enum.map(names, &item/1)}</ul>\n    \"\"\"\n  end\n\n  def main() do\n    html = Markup.to_string(page([\"ada\", \"<script>\"]))\n    assert(html == \"<h1>2 names</h1>\\n<ul><li>ada</li><li>&lt;script&gt;</li></ul>\\n\")\n  end\nend\n"})

	topic("Modules", "constants", "@name value declares a module constant; @name anywhere in the module stands for the value.",
		[]string{
			"The value is built from literals, lists, tuples, maps, operators and earlier constants: @timeout 60 * 1000, @colors [:red, :green]. It cannot call functions or read bindings.",
			"A constant is visible throughout its module, including tests and struct field defaults, but not in other modules; share a value between modules with a function.",
			"Each use is replaced by the value when the program is compiled. A name may be defined once; @doc, @moduledoc, @typedoc and the test tags are not constants.",
		}, []string{"modules", "values", "operators"},
		Sample{Title: "limits as constants", File: "defmodule Example do\n  @attempts 3\n  @delay_ms 250\n  @budget_ms @attempts * @delay_ms\n\n  def plan(): string do\n    Integer.to_string(@attempts) <> \" tries within \" <> Integer.to_string(@budget_ms) <> \" ms\"\n  end\n\n  def main() do\n    assert(plan() == \"3 tries within 750 ms\")\n  end\nend\n"})

	topic("Modules", "protocols", "defprotocol declares functions; defimpl supplies them for one type.",
		[]string{
			"defprotocol Name do def function(value): type ... end declares functions without bodies.",
			"defimpl Name, for: Type do ... end defines every function of the protocol for one type: a builtin type, a struct or sum type from any module, or a generic type such as list[a]. The first parameter is the value and needs no annotation.",
			"A call Name.function(value, ...) is resolved when the program is compiled, from the type of its first argument. There is no dispatch while the program runs, so the type must be known where the call is written: it cannot be a type variable.",
			"A protocol is known by its own name in every module of the program, and a type may be given an implementation in any module.",
			"An implementation that lacks a function, or disagrees with the protocol on the number of arguments or the result type, is a compile error.",
		}, []string{"modules", "structs", "generics"},
		Sample{Title: "one protocol, three types", Defs: "struct Circle do\n  radius: float\nend\n\ndefprotocol Describe do\n  def describe(value): string\nend\n\ndefimpl Describe, for: integer do\n  def describe(n): string do\n    \"the number #{n}\"\n  end\nend\n\ndefimpl Describe, for: Circle do\n  def describe(circle): string do\n    \"a circle of radius #{circle.radius}\"\n  end\nend\n\ndefimpl Describe, for: list[a] do\n  def describe(items): string do\n    \"a list of #{length(items)}\"\n  end\nend",
			Body: "assert(Describe.describe(7) == \"the number 7\")\nassert(Describe.describe(%Circle{radius: 1.5}) == \"a circle of radius 1.5\")\nassert(Describe.describe([\"a\", \"b\"]) == \"a list of 2\")\nassert(Enum.map([1, 2], &Describe.describe(&1)) == [\"the number 1\", \"the number 2\"])"})

	topic("Modules", "macros", "defmacro defines a template; a call is replaced by the template with its arguments filled in.",
		[]string{
			"defmacro name(parameters) do quote do ... end end. Inside the quote, unquote(parameter) stands for the argument given at the call.",
			"Expansion happens before anything is typed and runs no code: it copies the quoted code and substitutes. What comes out is checked like any other code, and a problem is reported where the macro was called.",
			"A last parameter written do: name takes a do ... end block: name(arguments) do ... end. Only a macro takes a block.",
			"A macro whose template is one expression can be used as a value; one with several statements is used as a statement.",
			"An argument is put in wherever it is unquoted, so unquoting it twice evaluates it twice. Bind it once in the template to avoid that.",
			"A name the template binds is separate from the same name at the call, and a function the template calls is the one in the macro's own module.",
			"From another module a macro is called Module.name(...). A macro named __using__ holds function definitions, which use Module, option: value adds to the module that says so.",
		}, []string{"functions", "modules", "protocols"},
		Sample{Title: "a value, statements, and a block", Defs: "defmacro square(value) do\n  quote do\n    unquote(value) * unquote(value)\n  end\nend\n\ndefmacro check(label, value) do\n  quote do\n    result = unquote(value)\n    assert(result > 0)\n    IO.puts(\"#{unquote(label)}: #{result}\")\n  end\nend\n\ndefmacro unless_empty(items, do: body) do\n  quote do\n    if unquote(items) != [] do\n      unquote(body)\n    end\n  end\nend",
			Body: "result = 3\nassert(square(result + 1) == 16)\ncheck(\"doubled\", result * 2)\nassert(result == 3)\nunless_empty([1, 2]) do\n  IO.puts(\"has items\")\nend"})

	topic("Concurrency", "nodes", "Programs connect as nodes and their processes exchange messages, which are copied.",
		[]string{
			"Node.start(name, address, cookie) makes a program a node; Node.connect(address) connects it to another that knows the same cookie. With two arguments Node.start reads the cookie from ALCHEM_COOKIE.",
			"Process.register(pid, :name) names a process. Node.whereis(node, :name) finds it from another node as an option[pid[T]], where T comes from the annotation and must be the type it was registered with.",
			"Process.send to that handle copies the message across. A process handle inside a message crosses too, so the receiver can reply through it.",
			"A handle to a process of another node can be sent to and monitored: Process.monitor reports its exit as an event, or \"noconnection\" if its node is lost first. Process.alive tells whether its node is connected. Receiving, linking and awaiting need a process of this node. Node.monitor(node) reports a lost connection as an event whose reason is \"nodedown\" and the node's name. Node.monitor_nodes() reports every connection made (\"nodeup\") or lost (\"nodedown\"), for as long as the process runs. Node.connect(address, reconnect: true) makes a lost connection again, a second later at first and up to 30 seconds apart; reconnect: n gives up after n failed attempts in a row, reported as \"noreconnect\".",
			"Stream.publish(:name, fn -> stream end) offers a stream to other nodes, and Node.stream(node, :name) reads it from one: elements are pulled a chunk at a time as they are consumed, so an endless or very large stream stays where it is.",
			"Only values that can be copied cross: no functions, streams, regular expressions, ports, tasks, agents or servers. The compiler checks this where a process is registered or looked up.",
			"Nodes that exchange a message type must agree on it: share the module that declares it.",
			"Connections are encrypted with TLS 1.3, and the cookie decides who may connect: each node proves it knows the cookie without sending it. Use a long random cookie, and keep it out of source control.",
			"Node.start(name, address, cookie, [encrypted: false]) turns encryption off, for a network you trust. Only nodes with the same setting connect, and a mismatch is reported on both sides.",
			"A send to another node returns once the message is written, not once it is received, and a full mailbox there delays and then drops messages.",
		}, []string{"processes", "Node", "Process"},
		Sample{Title: "starting a node and naming a process", Body: "started = Node.start(\"example\", \"127.0.0.1:0\", \"secret\")\nassert(started == ok({}) or started == error(\"this program is already a node\"))\ninbox: pid[tuple[atom, integer]] = Process.self(8)\nProcess.register(inbox, :example_inbox)\nfound: option[pid[tuple[atom, integer]]] = Process.whereis(:example_inbox)\nsent = case found do\n  some(named) -> Process.send(named, {:count, 3}, 100)\n  none -> false\nend\nassert(sent)\nassert_receive(inbox, {:count, 3})\nProcess.unregister(:example_inbox)\nelsewhere: option[pid[tuple[atom, integer]]] = Node.whereis(\"other\", :example_inbox, 50)\nreached = case elsewhere do\n  some(_) -> true\n  none -> false\nend\nassert(not reached)"})

	topic("Modules", "extern", "extern name(params): result = \"package.Function\" calls a Go function.",
		[]string{
			"The Alchem signature is checked against the Go one by alchem check.",
			"A Go (T, error) result is declared result[T, string]; (T, bool) is option[T].",
			"extern type Name = \"*package.Type\" names an opaque Go type; methods are \"package.Type.Method\" with the receiver first.",
			"require \"module/path\" \"v1.2.3\" adds a third-party Go module; \"./dir.Function\" refers to Go code beside the program.",
		}, []string{"modules"},
		Sample{Title: "calling the Go standard library", Defs: "extern shout(text: string): string = \"strings.ToUpper\"\nextern to_number(text: string): result[integer, string] = \"strconv.Atoi\"",
			Body: "assert(shout(\"hello\") == \"HELLO\")\nassert(to_number(\"42\") == ok(42))"})

	topic("Concurrency", "processes", "Lightweight processes with typed mailboxes.",
		[]string{
			"pid[T] is a process whose mailbox carries T. Process.spawn(function, capacity) starts one; the function receives its own pid and returns an exit status.",
			"Process.self(capacity) is the current process; annotate it to fix the message type.",
			"Process.send(pid, message, timeout_ms) and Process.receive(self, timeout_ms) -> {arrived, message}.",
			"For state, prefer Server (request/reply), Agent (shared state) or Task (one result) over raw processes.",
			"Supervisor restarts failed children; Process.monitor and Process.link observe failures.",
		}, []string{"Process", "Server", "Task", "Agent", "Supervisor"},
		Sample{Title: "send and receive", Body: "parent: pid[string] = Process.self(8)\nworker: pid[string] = Process.spawn(fn(self: pid[string]): integer do\n  {_, text} = Process.receive(self, 1000)\n  Process.send(parent, String.upcase(text), 1000)\n  0\nend, 8)\nProcess.send(worker, \"hello\", 1000)\nassert(Process.receive(parent, 1000) == {true, \"HELLO\"})"},
		Sample{Title: "tasks and a server", Defs: "type Request do\n  add(amount: integer)\n  read\nend\n\ndef handle(total: integer, request: Request): tuple[integer, integer] do\n  case request do\n    Request.add(amount) -> {total + amount, total + amount}\n    Request.read -> {total, total}\n  end\nend",
			Body: "squares = Task.async_stream(1..4, fn n -> n * n end) |> Enum.to_list()\nassert(squares == [1, 4, 9, 16])\ncounter = Server.start(0, &handle)\nassert(Server.call(counter, Request.add(5), 1000) == ok(5))\nassert(Server.call(counter, Request.read, 1000) == ok(5))\nServer.stop(counter)"})

	topic("Testing", "tests", "Test files end in _test.alc and are run by alchem test.",
		[]string{
			"test \"name\" do ... end defines a test; describe \"group\" do ... end groups tests and may nest.",
			"assert, refute, assert_raise, assert_in_delta and flunk are the assertions; a failed comparison shows both sides.",
			"on_exit(fn -> ... end) runs when the test ends, passed or failed; capture_io(fn -> ... end) returns what was printed; assert_receive(self, pattern) takes the first matching message from the test's own mailbox and binds the pattern's names; refute_receive(self, pattern) fails if one arrives. Both accept a when guard, a timeout in milliseconds and a failure message; assert_received and refute_received do not wait.",
			"setup do ... end runs before each test in its describe; setup_all once per file. A setup that ends in a struct passes it to tests written test \"name\", context do.",
			"@tag \"slow\" or @tag :slow marks the next test, @describetag the next describe and @moduletag the file; a tag may have a value, @tag kind: :db, owner: \"ada\". Run with --tag or --exclude, by name (kind) or by name and value (kind:db). @tag timeout: 500 gives one test its own limit in milliseconds, or :infinity; @tag :skip or skip: \"reason\" skips.",
			"alchem test --seed N repeats an order; --only text, --trace, --max-failures N, --cover and --cover-min P are the other flags.",
			"Test files are compiled and run in parallel, one per processor; --jobs 1 runs them one at a time. Their output is printed in the same order either way.",
		}, []string{"doctests", "Testing"},
		Sample{Title: "a test file", File: "defmodule CartTest do\n  struct Context do\n    prices: list[integer]\n  end\n\n  setup do\n    %Context{prices: [5, 10]}\n  end\n\n  describe \"totals\" do\n    test \"adds prices\", context do\n      assert(Enum.sum(context.prices) == 15)\n    end\n\n    describe \"empty carts\" do\n      test \"total nothing\" do\n        assert(Enum.sum(Enum.take([1], 0)) == 0)\n      end\n    end\n  end\n\n  @tag \"slow\"\n  test \"division by zero is reported\" do\n    assert_raise(\"division by zero\", fn -> 1 / 0 end)\n  end\nend\n"})

	topic("Testing", "properties", "check all pattern <- generator, ... do ... end checks a property on generated values.",
		[]string{
			"Generators come from the Gen module: Gen.integer(), Gen.integer(low, high), Gen.string(:alphanumeric), Gen.list_of(g), Gen.tuple(a, b), Gen.member_of(list), Gen.one_of(generators), Gen.map, Gen.filter, Gen.bind and more.",
			"Each generator may use what the ones before it bound: check all low <- Gen.integer(0, 9), high <- Gen.integer(low, 20) do ... end.",
			"Conditions between the generators drop the values that fail them, and max_runs: n changes how many values are tried, 100 unless ALCHEM_PROPERTY_RUNS says otherwise.",
			"Values grow with each run. When the body fails, the value is shrunk to the smallest one that still fails, and that one is reported with the failure.",
			"The values come from the test seed, so alchem test --seed N repeats a failure.",
		}, []string{"tests", "Gen"},
		Sample{Title: "a property", File: "defmodule ReverseTest do\n  test \"reversing twice gives the list back\" do\n    check all list <- Gen.list_of(Gen.integer()), max_runs: 50 do\n      assert(Enum.reverse(Enum.reverse(list)) == list)\n    end\n  end\n\n  test \"a sorted list is ordered\" do\n    check all list <- Gen.list_of(Gen.integer(-5, 5)) do\n      sorted = Enum.sort(list)\n      assert(Enum.all?(Enum.zip(sorted, Enum.drop(sorted, 1)), fn {a, b} -> a <= b end))\n    end\n  end\nend\n"})

	topic("Testing", "doctests", "doctest Module runs the alx> examples in a module's @doc strings.",
		[]string{
			"In @doc, a line alx> expression is run; the lines after it, up to a blank line, are the expected value.",
			"...> continues the expression on the next line; an example without an expected value is only run.",
			"Examples in one @doc share bindings, top to bottom.",
			"The test file imports the module and says doctest Module.",
		}, []string{"comments", "tests"},
		Sample{Title: "documented examples as tests", File: "defmodule PriceTest do\n  import \"price.alc\"\n  doctest Price\nend\n",
			Files: map[string]string{"price.alc": "defmodule Price do\n  @doc \"\"\"\n  Adds tax at a percentage.\n\n      alx> Price.with_tax(100, 20)\n      120\n      alx> net = 50\n      alx> Price.with_tax(net, 10)\n      55\n  \"\"\"\n  def with_tax(net: integer, percent: integer): integer do\n    net + net * percent / 100\n  end\nend\n"}})
}

func indent(text, prefix string) string {
	lines := strings.Split(text, "\n")
	for i, line := range lines {
		if line != "" {
			lines[i] = prefix + line
		}
	}
	return strings.Join(lines, "\n")
}

// Program is the sample as a complete file: the module named, holding the
// declarations and either a main function or, for test, one test.
func (s Sample) Program(module string, test bool) string {
	if s.File != "" {
		return s.File
	}
	var b strings.Builder
	b.WriteString("defmodule " + module + " do\n")
	if s.Defs != "" {
		b.WriteString(indent(s.Defs, "  ") + "\n\n")
	}
	if test {
		b.WriteString("  test " + strconv.Quote(s.Title) + " do\n")
	} else {
		b.WriteString("  def main() do\n")
	}
	b.WriteString(indent(s.Body, "    ") + "\n  end\nend\n")
	return b.String()
}
