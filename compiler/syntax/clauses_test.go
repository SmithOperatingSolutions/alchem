package syntax

import (
	"strings"
	"testing"
)

func TestClausesAndImplicitReturns(t *testing.T) {
	_, err := Parse(`defmodule X do
 def size([]: list[string]): integer do 0 end
 def size([_ | rest]) do 1 + size(rest) end
 def pick(true, a: integer, _: integer): integer do a end
 def pick(false, _, b) do b end
 def label(n: integer): string do
  case n do
   0 -> "zero"
   _ -> if n > 0 do "up" else "down" end
  end
 end
 def main() do
  assert(size(["a"]) == 1 and pick(false, 1, 2) == 2 and label(3) == "up")
 end
end`)
	if err != nil {
		t.Fatal(err)
	}
}

func TestClauseErrors(t *testing.T) {
	cases := []struct{ declarations, want string }{
		{`def f(0): integer do 1 end def f(1) do 2 end`, "non-exhaustive"},
		{`def f(n: integer): integer when n > 0 do 1 end`, "non-exhaustive"},
		{`def f(n: integer): integer do 1 end def f(0) do 2 end`, "unreachable"},
		{`def f(n: integer): integer do 1 end def f(a, b) do 2 end`, "f/2 needs a return type"},
		{`def f(0): integer do 1 end def f(n: string) do 2 end`, "parameter 1 of f is integer in one clause and string in another"},
		{`def f(0): integer do 1 end def f(n: integer): string do "x" end`, "returns integer in one clause and string in another"},
		{`def f([]): integer do 1 end def f(_) do 2 end`, "parameter 1 of f needs a type"},
		{`def f(0) do 1 end def f(_) do 2 end`, "f needs a return type"},
		{`def f(0): integer do 1 end def g(): integer do 1 end def f(_) do 2 end`, "clauses of f must be adjacent"},
		{`def f(n: integer): integer do IO.puts("x") end`, "must return on every path"},
		{`def f(n: integer): integer do if n > 0 do 1 end end`, "must return on every path"},
		{`def f(n: integer): integer do "text" end`, "expected integer, found string"},
		{`def f(n: integer): integer do n n end`, "expected binding or function call"},
	}
	for _, tc := range cases {
		t.Run(tc.declarations, func(t *testing.T) {
			_, err := Parse("defmodule X do " + tc.declarations + " def main() do assert(true) end end")
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}

// A line break ends an expression before "(" or a sign, so a bare tail
// expression is never absorbed into the statement above it.
func TestLineBreakEndsExpression(t *testing.T) {
	_, err := Parse("defmodule X do\n def f(n: integer): integer do\n  a = n\n  (a + 1) * 2\n end\n def g(n: integer): integer do\n  a = n\n  -a\n end\n def main() do\n  total = 1 +\n   2\n  piped = [1]\n   |> length()\n  assert(f(1) == 4 and g(2) == -2 and total == 3 and piped == 1)\n end\nend")
	if err != nil {
		t.Fatal(err)
	}
}

func TestExhaustiveness(t *testing.T) {
	for _, tc := range []struct {
		body string
		ok   bool
	}{
		{`case {true, [1]} do {true, _} -> assert(true) {false, []} -> assert(true) {false, [_ | _]} -> assert(true) end`, true},
		{`case {true, [1]} do {true, _} -> assert(true) {false, []} -> assert(true) end`, false},
		{`case [1] do [] -> assert(true) [_] -> assert(true) [_, _ | _] -> assert(true) end`, true},
		{`case [1] do [] -> assert(true) [_] -> assert(true) end`, false},
		{`case {1, true} do {_, true} -> assert(true) {_, false} -> assert(true) end`, true},
		{`case [[1]] do [] -> assert(true) [[] | _] -> assert(true) [[_ | _] | _] -> assert(true) end`, true},
		{`case 1 do 1 -> assert(true) 2 -> assert(true) end`, false},
	} {
		t.Run(tc.body, func(t *testing.T) {
			_, err := Parse("defmodule X do def main() do " + tc.body + " end end")
			if (err == nil) != tc.ok {
				t.Fatalf("ok=%v err=%v", tc.ok, err)
			}
		})
	}
}
