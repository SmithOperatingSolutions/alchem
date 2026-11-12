package syntax

import "testing"

func TestParse(t *testing.T) {
	p, err := Parse("defmodule Hello do def main() do IO.puts(\"Hello!\") end end")
	if err != nil {
		t.Fatal(err)
	}
	if p.Module != "Hello" || p.Output != "Hello!" {
		t.Fatalf("program=%+v", p)
	}
}
func TestParseRejectsUnsupported(t *testing.T) {
	for _, src := range []string{
		"defmodule Hello do end",
		"defmodule hello do def main() do IO.puts(\"x\") end end",
		"defmodule Hello do def main() do IO.puts(\"x\") unknown(\"y\") end end",
	} {
		if _, err := Parse(src); err == nil {
			t.Fatalf("accepted %q", src)
		}
	}
}
