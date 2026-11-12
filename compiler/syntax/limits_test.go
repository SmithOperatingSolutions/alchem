package syntax

import (
	"strings"
	"testing"
)

func wrap(expression string) string {
	return "defmodule Limits do\n def main() do\n  x = " + expression + "\n end\nend\n"
}

// Pathological input must produce a diagnostic rather than exhaust the stack.
func TestParserBoundsRecursionAndSize(t *testing.T) {
	cases := []struct{ name, source, want string }{
		{"parentheses", wrap(strings.Repeat("(", 100000) + "1" + strings.Repeat(")", 100000)), "nesting exceeds"},
		{"unary", wrap(strings.Repeat("not ", 100000) + "true"), "nesting exceeds"},
		{"lists", wrap(strings.Repeat("[", 100000) + strings.Repeat("]", 100000)), "nesting exceeds"},
		{"patterns", "defmodule Limits do\n def main() do\n  " + strings.Repeat("[", 100000) + "x" + strings.Repeat("]", 100000) + " = 1\n end\nend\n", "nesting exceeds"},
		{"types", "defmodule Limits do\n def f(x: " + strings.Repeat("list[", 100000) + "integer" + strings.Repeat("]", 100000) + "): integer do\n  return 1\n end\n def main() do\n  assert(true)\n end\nend\n", "nesting exceeds"},
		{"blocks", "defmodule Limits do\n def main() do\n" + strings.Repeat("if true do\n", 1000) + "assert(true)\n" + strings.Repeat("end\n", 1000) + " end\nend\n", "nesting exceeds"},
		{"operators", wrap("1" + strings.Repeat(" + 1", 5000)), "chains more than"},
		{"postfix", wrap("x" + strings.Repeat("[0]", 5000)), "chains more than"},
		{"size", wrap("\"" + strings.Repeat("a", MaxSourceBytes) + "\""), "source exceeds"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			for _, parse := range []func(string) error{
				func(s string) error { _, err := Parse(s); return err },
				func(s string) error { _, err := ParseModule(s); return err },
			} {
				if err := parse(tc.source); err == nil || !strings.Contains(err.Error(), tc.want) {
					t.Fatalf("got %.200v, want %q", err, tc.want)
				}
			}
		})
	}
}

// Ordinary programs sit far below the limits.
func TestParserAcceptsReasonableNesting(t *testing.T) {
	source := wrap(strings.Repeat("(", 60) + "1" + strings.Repeat(")", 60) + strings.Repeat(" + 1", 500))
	if _, err := Parse(source); err != nil {
		t.Fatal(err)
	}
}
