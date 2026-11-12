package syntax

import (
	"strings"
	"testing"
)

func body(statements string) string {
	return "defmodule T do\n def main() do\n" + statements + "\n end\nend\n"
}

func TestPinPatternsAndCollectionOperationsTypeCheck(t *testing.T) {
	valid := []string{
		"x = 1\n case 2 do\n ^x -> assert(false)\n _ -> assert(true)\n end",
		"x = 1\n {^x, y} = {1, 2}\n assert(y == 2)",
		"xs: list[integer] = List.reverse([])\n assert(length(xs) == 0)",
		"m: map[string,integer] = Map.merge(%{}, %{})\n assert(length(m) == 0)",
		"zs = List.zip([1], [\"a\"])\n assert(zs[0] == {1, \"a\"})",
	}
	for _, statements := range valid {
		if _, err := Parse(body(statements)); err != nil {
			t.Errorf("%q: %v", statements, err)
		}
	}
	invalid := []struct{ statements, want string }{
		{"case 1 do\n ^missing -> assert(true)\n _ -> assert(true)\n end", "is not defined before this pattern"},
		{"{x, ^x} = {1, 1}", "is not defined before this pattern"},
		{"x = \"a\"\n case 1 do\n ^x -> assert(true)\n _ -> assert(true)\n end", "has type string, pattern requires integer"},
		{"f = fn(n: integer): integer do return n end\n case f do\n ^f -> assert(true)\n _ -> assert(true)\n end", "without equality"},
		{"x = 1\n case 1 do\n ^x -> assert(true)\n end", "non-exhaustive case"},
		{"x = 1\n case 1 do\n ^x -> assert(true)\n ^x -> assert(true)\n _ -> assert(true)\n end", "unreachable case branch"},
		{"^x = 1", "is not defined before this pattern"},
		{"y = ^x", "expected expression"},
		{"x = List.reverse(1)", "List.reverse requires a list"},
		{"x = List.reverse([1], [2])", "List.reverse requires 1 arguments"},
		{"x = List.sort([true])", "List.sort requires list[integer], list[float] or list[string]"},
		{"x = List.take([1], \"a\")", "expected integer"},
		{"f = fn(n: integer): integer do return n end\n x = List.contains([f], f)", "support equality"},
		{"x = List.contains([1], \"a\")", "expected integer"},
		{"x = List.range(1, true)", "expected integer"},
		{"x = List.zip([1], 2)", "List.zip requires two lists"},
		{"x = Map.merge(%{\"a\" => 1}, %{1 => 1})", "expected string"},
		{"x = Map.merge([1], [2])", "Map.merge requires two maps"},
		{"x = List.unknown([1])", "undefined function List.unknown"},
	}
	for _, tc := range invalid {
		if _, err := Parse(body(tc.statements)); err == nil || !strings.Contains(err.Error(), tc.want) {
			t.Errorf("%q: got %v, want %q", tc.statements, err, tc.want)
		}
	}
}
