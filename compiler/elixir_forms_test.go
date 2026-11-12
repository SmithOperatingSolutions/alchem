package compiler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Imports may follow @moduledoc, and a module's overloaded functions are
// reached from another module by their number of arguments.
func TestOverloadsAcrossModules(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{
		"shapes.alc": `defmodule Shapes do
  @moduledoc """
  Areas.
  """

  def area(side: integer): integer do
    side * side
  end

  def area(width: integer, height: integer): integer do
    width * height
  end

  defp secret(n: integer): integer do
    n
  end

  defp secret(n: integer, m: integer): integer do
    secret(n) + m
  end

  def exposed(n: integer): integer do
    secret(n, 1)
  end
end
`,
		"main.alc": `defmodule App do
  @moduledoc """
  Uses Shapes.
  """
  import "shapes.alc"

  def main() do
    IO.inspect({Shapes.area(3), Shapes.area(2, 4), Shapes.exposed(1)})
    IO.inspect(Enum.map([1, 2], &Shapes.area/1))
  end
end
`})
	if err != nil || output != "{9, 8, 2}\n[1, 4]\n" {
		t.Fatalf("err=%v output=%q", err, output)
	}
}

func TestOverloadErrors(t *testing.T) {
	cases := map[string]string{
		`def f(n: integer): integer do n end
  def f(a: integer, b: integer): integer do a + b end
  def main() do IO.inspect(f(1, 2, 3)) end`: "f takes f/1 or f/2; no f/3 is defined",
		`def f(n: integer): integer do n end
  def f(a: integer, b: integer): integer do a + b end
  def main() do IO.inspect(Enum.map([1], &f)) end`: "f has more than one arity; write &f/1 or &f/2",
		`def f(n: integer, m: integer \\ 0): integer do n + m end
  def f(n: integer): integer do n end
  def main() do IO.inspect(f(1)) end`: "both accept 1 arguments",
		`def g(n: integer): integer do n end
  def main() do IO.inspect(Enum.map([1], &g/2)) end`: "g takes 1 arguments, not 2",
		`def get(n: integer): integer do n end
  def main() do IO.inspect(get(1)) end`: "get is reserved for a builtin",
	}
	for body, want := range cases {
		path := filepath.Join(t.TempDir(), "main.alc")
		if err := os.WriteFile(path, []byte("defmodule App do\n  "+body+"\nend\n"), 0o600); err != nil {
			t.Fatal(err)
		}
		err := Check(path)
		if err == nil || !strings.Contains(err.Error(), want) {
			t.Errorf("%s\ngot %v, want %q", body, err, want)
		}
	}
}
