package syntax

import (
	"strings"
	"testing"
)

func TestBindingsAndStatements(t *testing.T) {
	p, err := Parse(`defmodule Check do def main() do
 value = -42
 copy = value
 text = "hello"
 ok = true
 assert(copy < 0)
 assert(ok)
 IO.puts(text)
 end end`)
	if err != nil {
		t.Fatal(err)
	}
	if len(p.Statements) != 7 {
		t.Fatalf("statements=%+v", p.Statements)
	}
}
func TestBindingErrors(t *testing.T) {
	for _, body := range []string{`x = 1 x = 2`, `x = x`, `assert(missing)`, `X = 1`, `and = false`, `IO.puts = 1`, `x = 1 IO.puts(x)`, `x = true assert(x < false)`, `x = 1 assert(x == true)`, `end`} {
		t.Run(body, func(t *testing.T) {
			_, err := Parse("defmodule Check do def main() do " + body + " end end")
			if err == nil || !strings.Contains(err.Error(), ":") {
				t.Fatalf("expected positioned error, got %v", err)
			}
		})
	}
}
