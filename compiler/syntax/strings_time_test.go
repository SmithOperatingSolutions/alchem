package syntax

import (
	"strings"
	"testing"
)

func TestStringIntegerAndTimeOperationsTypeCheck(t *testing.T) {
	valid := []string{
		`x = "a" <> "b" <> Integer.to_string(1)` + "\n assert(x == \"ab1\")",
		`n = String.length("a") + 1` + "\n assert(n == 2)",
		`ok = "a" <> "b" == "ab" and 1 + 2 == 3` + "\n assert(ok)",
		`parts = "a,b" |> String.split(",")` + "\n assert(length(parts) == 2)",
		`t = Time.monotonic() - Time.now()` + "\n assert(t < 0)",
	}
	for _, statements := range valid {
		if _, err := Parse(body(statements)); err != nil {
			t.Errorf("%q: %v", statements, err)
		}
	}
	invalid := []struct{ statements, want string }{
		{`x = "a" <> 1`, "expected string"},
		{`x = 1 <> 2`, "<> requires strings"},
		{`x = String.length(1)`, "expected string"},
		{`x = String.length("a", "b")`, "String.length requires 1 arguments"},
		{`x = String.slice("a", 0)`, "expected Range, found integer"},
		{`x = String.slice("a", "0", 1)`, "expected integer"},
		{`x = String.join("a", ",")`, "expected list[string]"},
		{`x = String.join([1], ",")`, "expected string"},
		{`x: integer = String.trim("a")`, "expected integer, found string"},
		{`x = Integer.to_string("1")`, "expected integer"},
		{`x: integer = Integer.parse("1")`, "expected integer, found result[integer,string]"},
		{`x = Time.now(1)`, "Time.now requires 0 arguments"},
		{`x = String.unknown("a")`, "undefined function String.unknown"},
		{`x = System.argv(1)`, "System.argv requires 0 arguments"},
		{`x: string = System.argv()`, "expected string, found list[string]"},
		{`x: string = IO.read_line()`, "expected string, found option[string]"},
		{`x = IO.read_all("a")`, "IO.read_all requires 0 arguments"},
		{`x = File.read(1)`, "expected string"},
		{`x = File.read()`, "File.read requires 1 arguments"},
		{`x = File.erase("a")`, "undefined function File.erase"},
	}
	for _, tc := range invalid {
		if _, err := Parse(body(tc.statements)); err == nil || !strings.Contains(err.Error(), tc.want) {
			t.Errorf("%q: got %v, want %q", tc.statements, err, tc.want)
		}
	}
}

// <> binds tighter than comparison and pipes, and looser than arithmetic.
func TestConcatenationPrecedence(t *testing.T) {
	program, err := Parse(body(`assert("a" <> "b" == "ab")` + "\n" + `x = "n" <> Integer.to_string(1 + 2)` + "\n assert(x == \"n3\")"))
	if err != nil {
		t.Fatal(err)
	}
	comparison := program.Statements[0].Expr
	if comparison.Op != "==" || comparison.Left.Op != "<>" {
		t.Fatalf("expected (a <> b) == ab, got %s with left %s", comparison.Op, comparison.Left.Op)
	}
}
