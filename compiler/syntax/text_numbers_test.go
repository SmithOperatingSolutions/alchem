package syntax

import (
	"strings"
	"testing"
)

func TestTextAndNumberErrors(t *testing.T) {
	cases := []struct{ body, want string }{
		{`x = 1 + 1.5`, "expected integer, found float"},
		{`x = 1.5 % 2.0`, "requires integers"},
		{`x = "a" <> 1`, "expected string, found integer"},
		{`x = 1 <> 2`, "<> requires strings"},
		{`x = "a" + "b"`, "arithmetic requires integers or floats"},
		{`x = true < false`, "ordering requires integers, floats, strings or atoms"},
		{`x = "#{[1]}"`, "interpolation requires a string, integer, float, boolean or atom"},
		{`x = "#{1 +}"`, "expected expression"},
		{`x = "#{"`, "unterminated"},
		{`x = String.length(1)`, "expected string, found integer"},
		{`x = String.length("a", "b")`, "String.length requires 1 argument"},
		{`x = String.missing("a")`, "undefined function String.missing"},
		{`m = %{[1] => 1}`, "map keys must be integers, floats, strings, booleans, atoms or tuples of them"},
		{`x = 1.`, "invalid field name"},
		{`x = trunc(1)`, "expected float, found integer"},
	}
	for _, tc := range cases {
		t.Run(tc.body, func(t *testing.T) {
			_, err := Parse("defmodule X do def main() do " + tc.body + " end end")
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}
