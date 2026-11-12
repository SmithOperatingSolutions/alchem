package compiler

import "testing"

func TestParseHello(t *testing.T) {
	cases := []struct {
		name, source, want string
		fails              bool
	}{
		{"valid", "defmodule Hello do\n def main() do\n IO.puts(\"Hello from Alchem!\")\n end\nend", "Hello from Alchem!", false},
		{"escaped", "defmodule Hi do def main() do IO.puts(\"hi\\nthere\") end end", "hi\nthere", false},
		{"missing main", "defmodule Hello do end", "", true},
		{"extra statement", "defmodule Hello do def main() do IO.puts(\"x\") IO.puts(\"y\") end end", "", true},
		{"invalid escape", "defmodule Hello do def main() do IO.puts(\"\\q\") end end", "", true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseHello(tc.source)
			if (err != nil) != tc.fails {
				t.Fatalf("error=%v, want failure=%v", err, tc.fails)
			}
			if err == nil && got != tc.want {
				t.Fatalf("got %q want %q", got, tc.want)
			}
		})
	}
}
