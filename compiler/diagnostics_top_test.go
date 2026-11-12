package compiler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Each program is wrong in one way, and checking it fails with the words
// given.
func TestTopLevelDiagnostics(t *testing.T) {
	const main = "\n  def main() do\n    IO.inspect(1)\n  end\nend\n"
	cases := []struct{ name, source, want string }{
		{"type name", "defmodule Main do\n  type foo = integer" + main, "type name must be one capitalized word"},
		{"macro twice", "defmodule Main do\n  defmacro m() do\n    quote do\n      1\n    end\n  end\n  defmacro m() do\n    quote do\n      2\n    end\n  end" + main, "macro m is defined twice"},
		{"macro and function", "defmodule Main do\n  defmacro m() do\n    quote do\n      1\n    end\n  end\n  def m(): integer do\n    1\n  end" + main, "both a macro and a function"},
		{"macro parameters", "defmodule Main do\n  defmacro m(a b) do\n    quote do\n      1\n    end\n  end" + main, "parameters of a macro are names"},
		{"protocol twice", "defmodule Main do\n  defprotocol P do\n    def f(v: a): string\n  end\n  defprotocol P do\n    def f(v: a): string\n  end" + main, "protocol P is declared twice"},
		{"protocol name", "defmodule Main do\n  defprotocol p do\n    def f(v: a): string\n  end" + main, "protocol name is one capitalized word"},
		{"protocol function", "defmodule Main do\n  defprotocol P do\n    def f(): string\n  end" + main, "takes at least the value"},
		{"impl arity", "defmodule Main do\n  defprotocol P do\n    def f(v: a): string\n  end\n  defimpl P, for: integer do\n    def f(v: integer, w: integer): string do\n      \"\"\n    end\n  end" + main, "takes 1 arguments, not 2"},
		{"impl without for", "defmodule Main do\n  defprotocol P do\n    def f(v: a): string\n  end\n  defimpl P do\n  end" + main, "defimpl names a protocol and a type"},
		{"default order", "defmodule Main do\n  def f(a: integer \\\\ 1, b: integer): integer do\n    a + b\n  end" + main, "cannot follow one that has it"},
		{"default on pattern", "defmodule Main do\n  def f({a, b} \\\\ {1, 2}): integer do\n    a + b\n  end" + main, "only a named parameter"},
		{"extern parameters", "defmodule Main do\n  extern up(1): string = \"strings.ToUpper\"" + main, "extern parameters are typed names"},
		{"type parameters", "defmodule Main do\n  type Box[T] = T" + main, "type parameters are lowercase names"},
		{"duplicate type parameter", "defmodule Main do\n  type Pair[a, a] = {a, a}" + main, "duplicate type parameter a"},
		{"duplicate field", "defmodule Main do\n  struct P do\n    x: integer\n    x: integer\n  end" + main, "duplicate field x"},
		{"integer range", "defmodule Main do\n  def main() do\n    IO.inspect(99999999999999999999)\n  end\nend\n", "integer outside signed 64-bit range"},
		{"float range", "defmodule Main do\n  def main() do\n    IO.inspect(1.0e999)\n  end\nend\n", "float outside 64-bit range"},
		{"capture placeholder", "defmodule Main do\n  def main() do\n    f = &(&17 + 1)\n    IO.inspect(1)\n  end\nend\n", "capture placeholders are &1 to &16"},
		{"nested capture", "defmodule Main do\n  def main() do\n    f = &(&(&1))\n    IO.inspect(1)\n  end\nend\n", "captures cannot be nested"},
		{"receive arguments", "defmodule Main do\n  def main() do\n    assert_receive(1)\n  end\nend\n", "takes a process and a pattern"},
		{"for options", "defmodule Main do\n  def main() do\n    x = for n <- [1], uniq: true, uniq: true, do: n\n    IO.inspect(x)\n  end\nend\n", "for takes one option"},
		{"for reduce body", "defmodule Main do\n  def main() do\n    x = for n <- [1], reduce: 0, do: n\n    IO.inspect(x)\n  end\nend\n", "for with reduce: needs a do"},
		{"main in tests", "defmodule MainTest do\n  def main() do\n    IO.inspect(1)\n  end\n  test \"x\" do\n    assert(true)\n  end\nend\n", "cannot define main"},
		{"test name", "defmodule ATest do\n  test \"\" do\n    assert(true)\n  end\nend\n", "needs a name"},
		{"describe name", "defmodule ATest do\n  describe \"a\\u001f\" do\n  end\nend\n", "invalid describe name"},
		{"describe contents", "defmodule ATest do\n  describe \"d\" do\n    def f(): integer do\n      1\n    end\n  end\nend\n", "a describe block holds tests"},
		{"tag spaces", "defmodule ATest do\n  @tag \"a b\"\n  test \"x\" do\n    assert(true)\n  end\nend\n", "a tag is a name without spaces"},
		{"tag form", "defmodule ATest do\n  @tag 1\n  test \"x\" do\n    assert(true)\n  end\nend\n", "a tag is \"name\", :name or name: value"},
		{"tag value kind", "defmodule ATest do\n  @tag owner: maybe\n  test \"x\" do\n    assert(true)\n  end\nend\n", "a tag's value is a string, atom, integer or boolean"},
		{"tag value text", "defmodule ATest do\n  @tag owner: \"a,b\"\n  test \"x\" do\n    assert(true)\n  end\nend\n", "has no commas"},
		{"use without macro", "defmodule Tools do\n  def f(): integer do\n    1\n  end\nend\ndefmodule Main do\n  use Tools" + main, "has no __using__ macro"},
		{"use option missing", "defmodule Tools do\n  defmacro __using__(name) do\n    quote do\n      def hello(): string do\n        unquote(name)\n      end\n    end\n  end\nend\ndefmodule Main do\n  use Tools" + main, "needs the option name:"},
		{"use option unknown", "defmodule Tools do\n  defmacro __using__(name) do\n    quote do\n      def hello(): string do\n        unquote(name)\n      end\n    end\n  end\nend\ndefmodule Main do\n  use Tools, name: \"a\", other: 1" + main, "takes the options name"},
		{"use defines twice", "defmodule Tools do\n  defmacro __using__() do\n    quote do\n      def hello(): string do\n        \"a\"\n      end\n    end\n  end\nend\ndefmodule Main do\n  use Tools\n  def hello(): string do\n    \"b\"\n  end" + main, "which this module also defines"},
		{"use options form", "defmodule Tools do\n  defmacro __using__() do\n    quote do\n      1\n    end\n  end\nend\ndefmodule Main do\n  use Tools, name 1" + main, "use takes options written name: value"},
		{"unquote unknown", "defmodule Main do\n  defmacro m(v) do\n    quote do\n      unquote(w)\n    end\n  end\n  def main() do\n    IO.inspect(m(1))\n  end\nend\n", "names no parameter of m"},
		{"handler binding", "defmodule Main do\n  def main() do\n    x = try do\n      1\n    rescue\n      Bad in RuntimeError -> 2\n    end\n    IO.inspect(x)\n  end\nend\n", "invalid binding name"},
		{"map pattern", "defmodule Main do\n  def main() do\n    case 1 do\n      %{\"a\" => _} -> IO.inspect(1)\n      _ -> IO.inspect(2)\n    end\n  end\nend\n", "map pattern requires map value"},
		{"variant arity", "defmodule Main do\n  def main() do\n    case some(1) do\n      some(a, b) -> IO.inspect(a)\n      _ -> IO.inspect(2)\n    end\n  end\nend\n", "requires 1 argument"},
		{"index", "defmodule Main do\n  def main() do\n    x = 1\n    IO.inspect(x[0])\n  end\nend\n", ""},
		{"raise arguments", "defmodule Main do\n  def main() do\n    raise(\"a\", \"b\")\n  end\nend\n", "raise requires one argument"},
		{"operand types", "defmodule Main do\n  def main() do\n    IO.inspect(1 + 1.0 + \"a\")\n  end\nend\n", ""},
		{"list difference", "defmodule Main do\n  def main() do\n    IO.inspect(1 -- 2)\n  end\nend\n", "-- requires lists"},
		{"power", "defmodule Main do\n  def main() do\n    IO.inspect(true ** true)\n  end\nend\n", "** requires integers or floats"},
		{"void reference", "defmodule Main do\n  def main() do\n    f = &IO.puts/1\n    IO.inspect(1)\n  end\nend\n", ""},
		{"untyped closure", "defmodule Main do\n  def main() do\n    f = fn a -> a end\n    IO.inspect(1)\n  end\nend\n", "cannot infer the parameter types"},
		{"try else value", "defmodule Main do\n  def main() do\n    x = try do\n      IO.puts(\"a\")\n    rescue\n      _ -> 1\n    else\n      _ -> 2\n    end\n    IO.inspect(x)\n  end\nend\n", ""},
		{"nested impl body", "defmodule Main do\n  defprotocol P do\n    def f(v: a): string\n  end\n  defimpl P, for: integer do\n    def f(v: integer): string do\n      nope\n    end\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n", "nope"},
		{"nested test body", "defmodule ATest do\n  test \"x\" do\n    assert(nope)\n  end\nend\n", "nope"},
		{"nested setup body", "defmodule ATest do\n  setup do\n    nope\n  end\n  test \"x\" do\n    assert(true)\n  end\nend\n", "nope"},
		{"nested describe test", "defmodule ATest do\n  describe \"d\" do\n    test \"x\" do\n      assert(nope)\n    end\n  end\nend\n", "nope"},
		{"nested check all", "defmodule ATest do\n  test \"x\" do\n    check all n <- Gen.integer() do\n      assert(nope)\n    end\n  end\nend\n", "nope"},
		{"nested check all generator", "defmodule ATest do\n  test \"x\" do\n    check all n <- nope do\n      assert(true)\n    end\n  end\nend\n", "nope"},
		{"nested struct default", "defmodule Main do\n  struct P do\n    y: integer\n    x: integer = nope\n  end\n  def main() do\n    IO.inspect(%P{y: 1})\n  end\nend\n", "nope"},
		{"nested function body", "defmodule Main do\n  def f(): integer do\n    nope\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n", "nope"},
		{"nested guard", "defmodule Main do\n  def f(n: integer): integer when nope do\n    n\n  end\n  def main() do\n    IO.inspect(1)\n  end\nend\n", "nope"},
		{"nested macro body", "defmodule Main do\n  defmacro m() do\n    quote do\n      nope\n    end\n  end\n  def main() do\n    IO.inspect(m())\n  end\nend\n", "nope"},
	}
	dir := t.TempDir()
	path := filepath.Join(dir, "main.alc")
	for _, c := range cases {
		if strings.Contains(c.source, "Test do") {
			path = filepath.Join(dir, "main_test.alc")
		} else {
			path = filepath.Join(dir, "main.alc")
		}
		source := c.source
		// A module that another uses is imported from a file of its own.
		if at := strings.Index(source, "end\ndefmodule Main do\n"); at >= 0 {
			os.WriteFile(filepath.Join(dir, "tools.alc"), []byte(source[:at+4]), 0o600)
			source = "defmodule Main do\n  import \"tools.alc\"\n" + source[at+len("end\ndefmodule Main do\n"):]
		}
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
		if err == nil || !strings.Contains(err.Error(), c.want) {
			t.Errorf("%s: got %v, want %q", c.name, err, c.want)
		}
	}
}
