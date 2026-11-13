package compiler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Each program is wrong in one way, and checking it reports that, with the
// words given.
func TestMoreDiagnostics(t *testing.T) {
	cases := []struct{ name, body, defs, want string }{
		{"char sigil", `x = ~c"a#{1}"`, "", "~c does not interpolate"},
		{"regex modifier", `x = ~r/a/q`, "", "~r accepts the modifiers"},
		{"unknown sigil", `x = ~z"a"`, "", "unknown sigil ~z"},
		{"uniq", `x = for n <- [1], uniq: 1, do: n`, "", "uniq: takes true or false"},
		{"generator", `x = for n <- 5, do: n`, "", "a for generator needs"},
		{"reduce arm", "x = for n <- [1], reduce: 0 do\n      acc -> \"text\"\n    end", "", "expected integer, found string"},
		{"with unmatched", "x = with ok(n) <- Integer.parse(\"1\") do\n      n\n    end\n    y: string = x", "", ""},
		{"try else value", "x = try do\n      1\n    rescue\n      _ -> 2\n    else\n      n -> IO.puts(\"x\")\n    end", "", ""},
		{"in", `x = 1 in 5`, "", "in requires a list, map, set or stream"},
		{"JSON read of a function", "x: result[fn[integer, integer], string] = JSON.decode_as(\"1\")", "", "fn[integer,integer] has no JSON form"},
		{"JSON read through a caller's type", "step = fn(n: integer): integer do n end\n    x = twice(step, \"[]\")", "def like(_: a, text: string): result[a, string] do\n    JSON.decode_as(text)\n  end\n  def twice(sample: b, text: string): result[list[b], string] do\n    like([sample], text)\n  end\n", "twice reads b from JSON, and fn[integer,integer] cannot be read"},
		{"elem index", `x = elem({1, 2}, "a")`, "", "integer literal for the index"},
		{"elem arity", `x = elem({1, 2})`, "", "takes 2 arguments"},
		{"put_elem tuple", `x = put_elem([1], 0, 2)`, "", "put_elem needs a tuple"},
		{"put_elem bounds", `x = put_elem({1}, 3, 2)`, "", "tuple index out of bounds"},
		{"pattern type", "case 1 do\n      %Nope{} -> 1\n    end", "", "unknown"},
		{"pattern field", "case %P{x: 1} do\n      %P{y: _} -> 1\n    end", "struct P do\n    x: integer\n  end\n", "field"},
		{"pattern duplicate", "case %P{x: 1} do\n      %P{x: a, x: b} -> 1\n    end", "struct P do\n    x: integer\n  end\n", "duplicate field"},
		{"pattern mismatch", "case 1 do\n      \"a\" -> 1\n    end", "", ""},
		{"unreachable arm", "case some(1) do\n      _ -> 1\n      some(_) -> 2\n    end", "", ""},
		{"tag value", "x = 1", "@tag owner: [1]\n", ""},
		{"protocol arity", "x = Show.show(1, 2)", "defprotocol Show do\n    def show(v: a): string\n  end\n", ""},
		{"macro statement", "x = twice()", "defmacro twice() do\n    quote do\n      IO.puts(\"a\")\n      IO.puts(\"b\")\n    end\n  end\n", "used as a statement"},
		{"macro no value", "x = say()", "defmacro say() do\n    quote do\n      IO.puts(\"a\")\n    end\n  end\n", "without a value"},
		{"unquote arguments", "x = bad(1)", "defmacro bad(v) do\n    quote do\n      unquote(v, v)\n    end\n  end\n", "unquote takes"},
		{"use without using", "x = 1", "use Missing\n", ""},
		{"funcref private", "x = &nothing/3", "", "unknown function reference"},
		{"generic reference", "x = &pick/1", "def pick(v: a): a do\n    v\n  end\n", "needs an expected function type"},
		{"void reference", "x = &quiet/0", "def quiet() do\n    IO.puts(\"q\")\n  end\n", "quiet returns void"},
		{"reference arity", "x = &one/2", "def one(n: integer): integer do\n    n\n  end\n", "takes 1 arguments"},
		{"nested with clause", "x = with ok(n) <- nope do\n      n\n    end", "", "nope"},
		{"nested with body", "x = with ok(n) <- Integer.parse(\"1\") do\n      nope\n    end", "", "nope"},
		{"nested with else", "x = with ok(n) <- Integer.parse(\"1\") do\n      n\n    else\n      error(_) -> nope\n    end", "", "nope"},
		{"nested for generator", "x = for n <- nope, do: n", "", "nope"},
		{"nested for filter", "x = for n <- [1], nope, do: n", "", "nope"},
		{"nested for body", "x = for n <- [1], do: nope", "", "nope"},
		{"nested for into", "x = for n <- [1], into: nope, do: n", "", "nope"},
		{"nested for reduce", "x = for n <- [1], reduce: nope do\n      acc -> acc + n\n    end", "", "nope"},
		{"nested for reduce arm", "x = for n <- [1], reduce: 0 do\n      acc -> nope\n    end", "", "nope"},
		{"nested try body", "x = try do\n      nope\n    rescue\n      _ -> 1\n    end", "", "nope"},
		{"nested try rescue", "x = try do\n      1\n    rescue\n      _ -> nope\n    end", "", "nope"},
		{"nested try after", "x = try do\n      1\n    after\n      nope\n    end", "", "nope"},
		{"nested try else", "x = try do\n      1\n    rescue\n      _ -> 2\n    else\n      n -> nope\n    end", "", "nope"},
		{"nested try catch", "x = try do\n      1\n    catch\n      v: integer -> nope\n    end", "", "nope"},
		{"nested cond test", "x = cond do\n      nope -> 1\n      true -> 2\n    end", "", "nope"},
		{"nested cond body", "x = cond do\n      true -> nope\n    end", "", "nope"},
		{"nested case guard", "x = case 1 do\n      n when nope -> n\n      _ -> 2\n    end", "", "nope"},
		{"nested case subject", "x = case nope do\n      _ -> 2\n    end", "", "nope"},
		{"nested if test", "x = if nope do\n      1\n    else\n      2\n    end", "", "nope"},
		{"nested unless body", "x = unless true do\n      nope\n    else\n      2\n    end", "", "nope"},
		{"nested list element", "x = [1, nope]", "", "nope"},
		{"nested cons tail", "x = [1 | nope]", "", "nope"},
		{"nested tuple element", "x = {1, nope}", "", "nope"},
		{"nested map value", "x = %{\"a\" => nope}", "", "nope"},
		{"nested struct field", "x = %P{x: nope}", "struct P do\n    x: integer\n  end\n", "nope"},
		{"nested struct update", "p = %P{x: 1}\n    x = %P{p | x: nope}", "struct P do\n    x: integer\n  end\n", "nope"},
		{"nested index", "x = [1][nope]", "", "nope"},
		{"nested pipe", "x = nope |> Enum.sum()", "", "nope"},
		{"nested closure body", "f = fn(n: integer): integer do\n      nope\n    end", "", "nope"},
		{"nested capture body", "f: fn[integer, integer] = &(&1 + nope)", "", "nope"},
		{"nested call argument", "x = Enum.sum([nope])", "", "nope"},
		{"nested dynamic call", "f = fn(n: integer): integer do\n      n\n    end\n    x = f.(nope)", "", "nope"},
		{"nested interpolation", "x = \"a#{nope}\"", "", "nope"},
		{"nested sigil interpolation", "x = ~s\"a#{nope}\"", "", "nope"},
		{"nested unary", "x = -nope", "", "nope"},
		{"nested not", "x = not nope", "", "nope"},
		{"nested binary left", "x = nope + 1", "", "nope"},
		{"nested in right", "x = 1 in nope", "", "nope"},
		{"nested range", "x = 1..nope", "", "nope"},
		{"nested range step", "x = 1..5//nope", "", "nope"},
		{"nested raise argument", "raise(nope)", "", "nope"},
		{"nested elem", "x = elem(nope, 0)", "", "nope"},
		{"nested put_elem", "x = put_elem({1}, 0, nope)", "", "nope"},
		{"nested macro argument", "x = twice(nope)", "defmacro twice(v) do\n    quote do\n      unquote(v) + unquote(v)\n    end\n  end\n", "nope"},
		{"nested pattern pin", "x = case 1 do\n      ^nope -> 1\n      _ -> 2\n    end", "", "nope"},
		{"nested match right", "{a, b} = nope", "", "nope"},
		{"nested assert", "assert(nope)", "", "nope"},
		{"nested protocol call", "x = Show.show(nope)", "defprotocol Show do\n    def show(v: a): string\n  end\n", "nope"},
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "main.alc")
	for _, c := range cases {
		source := "defmodule Main do\n  " + c.defs + "\n  def main() do\n    " + c.body + "\n    IO.inspect(1)\n  end\nend\n"
		os.WriteFile(path, []byte(source), 0o600)
		var err error
		func() {
			defer func() {
				if v := recover(); v != nil {
					t.Errorf("%s: the checker panicked: %v", c.name, v)
				}
			}()
			err = Check(path)
		}()
		if c.want == "" {
			continue
		}
		if err == nil || !strings.Contains(err.Error(), c.want) {
			t.Errorf("%s: got %v, want %q", c.name, err, c.want)
		}
	}
}
