package compiler

import (
	"encoding/json"
	"github.com/SmithOperatingSolutions/alchem/compiler/syntax"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

func TestFormatCompleteGrammar(t *testing.T) {
	paths, err := filepath.Glob("../tests/fixtures/*.alc")
	if err != nil {
		t.Fatal(err)
	}
	for _, path := range paths {
		t.Run(filepath.Base(path), func(t *testing.T) {
			data, err := os.ReadFile(path)
			if err != nil {
				t.Fatal(err)
			}
			formatted, err := Format(string(data))
			if err != nil {
				t.Fatal(err)
			}
			again, err := Format(formatted)
			if err != nil || again != formatted {
				t.Fatalf("not idempotent: %v\n%s", err, formatted)
			}
			// Check the formatted file in a copy of the fixtures, so that files
			// which import their neighbours still resolve.
			copied := t.TempDir()
			if err := os.CopyFS(copied, os.DirFS(filepath.Dir(path))); err != nil {
				t.Fatal(err)
			}
			target := filepath.Join(copied, filepath.Base(path))
			if err := os.WriteFile(target, []byte(formatted), 0600); err != nil {
				t.Fatal(err)
			}
			if err := Check(target); err != nil {
				t.Fatalf("format invalidated program: %v", err)
			}
			if !strings.HasSuffix(formatted, "\n") {
				t.Fatal("missing newline")
			}
		})
	}
}

// Statements have no terminator, so formatting must never make one statement
// start with a parenthesis the author did not write.
func TestFormatPreservesStatementBoundaries(t *testing.T) {
	source := `defmodule F do
  def pick(xs: list[fn[integer,integer]]): integer do
    y = 1
    xs[0](y)
    t = {1, "a"}
    z = -(5)
    assert(t[0] == 1)
    assert((1 + 2) * 3 == 9)
    return [z][0]
  end
  def main() do
    f = fn(n: integer): integer do
      return n + 1
    end
    assert(pick([f]) == -5)
  end
end
`
	formatted, err := Format(source)
	if err != nil {
		t.Fatal(err)
	}
	again, err := Format(formatted)
	if err != nil || again != formatted {
		t.Fatalf("not idempotent: %v\n%s\n%s", err, formatted, again)
	}
	if _, err := syntax.Parse(source); err != nil {
		t.Fatal(err)
	}
	if _, err := syntax.Parse(formatted); err != nil {
		t.Fatalf("format invalidated program: %v\n%s", err, formatted)
	}
	for _, want := range []string{"    xs[0](y)\n", "    z = -5\n", "t[0] == 1"} {
		if !strings.Contains(formatted, want) {
			t.Fatalf("missing %q in\n%s", want, formatted)
		}
	}
}

// Formatting changes how a program is written, never what it means: the
// syntax tree of every fixture is the same before and after, ignoring
// positions.
func TestFormatKeepsMeaning(t *testing.T) {
	paths, err := filepath.Glob("../tests/fixtures/*.alc")
	if err != nil {
		t.Fatal(err)
	}
	positions := regexp.MustCompile(`"(Line|Column)":\d+,?`)
	generated := regexp.MustCompile(`\$\d+_\d+`)
	shape := func(source string) string {
		program, err := syntax.ParseSyntax(source)
		if err != nil {
			t.Fatal(err)
		}
		program.Leading = nil
		data, err := json.Marshal(program)
		if err != nil {
			t.Fatal(err)
		}
		// Names the parser makes up carry the position they were made at.
		return generated.ReplaceAllString(positions.ReplaceAllString(string(data), ""), "$$")
	}
	tricky := t.TempDir() + "/tricky.alc"
	if err := os.WriteFile(tricky, []byte(`defmodule Tricky do
  def main() do
    a = 1
    b = 2
    c = 3
    x = a - (b - c)
    y = (a - b) - c
    z = 2 ** (3 ** 2)
    w = (2 ** 3) ** 2
    v = (a + b) * c
    u = a + b * c
    s = ("a" <> "b") <> ("c" <> "d")
    r = (a < b) == (b < c)
    q = not (a == b) and (b == c or c == a)
    p = (a == b) or (b == c) and true
    o = [1, 2] ++ ([3] -- [3])
    m = (1..3) |> Enum.map(fn n -> n * (n + 1) end)
    l = 1..(c + 1)//2
    k = (a in [1, 2]) == true
    j = (a |> Integer.to_string()) <> "x"
    i = -(a + b)
    h = &(&1 * (&1 + 1))
    f = %{"k" => a + b}["k"] - (c - a)
  end
end
`), 0600); err != nil {
		t.Fatal(err)
	}
	for _, path := range append(paths, "../examples/system/main.alc", "../examples/system/workers.alc", tricky) {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		formatted, err := Format(string(data))
		if err != nil {
			t.Fatal(err)
		}
		if before, after := shape(string(data)), shape(formatted); before != after {
			t.Errorf("%s: formatting changed the program\n%s", path, formatted)
		}
	}
}

// Heredocs are written back as heredocs, at the indentation of the code
// around them; formatting changes nothing else about them.
func TestFormatKeepsHeredocs(t *testing.T) {
	source := `defmodule Main do
  def text(name: string): list[string] do
      plain = """
        line one
          indented "quoted"
        """
      raw = ~S"""
      no \n escapes #{here}
      """
      escaped = ~s"""
      hi #{name}\tthere
      """
      words = ~w"""
      alpha beta
      """
      [plain, raw, escaped] ++ words
  end

  def size(): integer do
    String.length(
      """
      abc
      """
    )
  end

  def main() do
    IO.inspect(text("x"))
  end
end
`
	want := `defmodule Main do
  def text(name: string): list[string] do
    plain = """
    line one
      indented "quoted"
    """
    raw = ~S"""
    no \n escapes #{here}
    """
    escaped = ~s"""
    hi #{name}\tthere
    """
    words = ~w"""
    alpha beta
    """
    [plain, raw, escaped] ++ words
  end

  def size(): integer do
    String.length("""
    abc
    """)
  end

  def main() do
    IO.inspect(text("x"))
  end
end
`
	got, err := Format(source)
	if err != nil {
		t.Fatal(err)
	}
	if got != want {
		t.Fatalf("formatted:\n%s\nwant:\n%s", got, want)
	}
	again, err := Format(got)
	if err != nil || again != got {
		t.Fatalf("not stable: %v\n%s", err, again)
	}
}

// A one-line sigil keeps the delimiters it was written with.
func TestFormatKeepsSigilDelimiters(t *testing.T) {
	source := `defmodule Main do
  def main() do
    name = "ada"
    page = ~h"<p class=\"x\">#{name}</p>"
    plain = ~H(<br>)
    words = ~w[a b]
    pattern = ~r{a/b}i
    text = ~S|raw \n|
    quoted = ~s'it\'s'
    day = ~D"2026-01-02"
    IO.inspect({page, plain, words, pattern, text, quoted, day})
  end
end
`
	got, err := Format(source)
	if err != nil {
		t.Fatal(err)
	}
	if got != source {
		t.Fatalf("formatted:\n%s\nwant it unchanged:\n%s", got, source)
	}
}

// The one-line if and unless and the empty struct literal are written back
// as they were.
func TestFormatKeepsOneLineIfAndEmptyStructs(t *testing.T) {
	source := `defmodule Main do
  struct Options do
    retries: integer = 3
  end

  def main() do
    n = 2
    word = if n == 1, do: "item", else: "items"
    unless n == 1, do: IO.puts(word)
    if n > 0, do: assert(true)
    options = %Options{}
    IO.inspect(options)
  end
end
`
	got, err := Format(source)
	if err != nil {
		t.Fatal(err)
	}
	if got != source {
		t.Fatalf("formatted:\n%s\nwant it unchanged:\n%s", got, source)
	}
}

// A comment above a module attribute stays above it, and a module that
// starts with attributes gets no blank first line.
func TestFormatKeepsCommentsAboveConstants(t *testing.T) {
	source := `defmodule Limits do
  # How many times to try.
  @tries 3
  # How long to wait,
  # in milliseconds.
  @wait_ms 500
  @plain 1

  # The total wait.
  def total(): integer do
    @tries * @wait_ms
  end
  # Nothing follows this.
end
`
	formatted, err := Format(source)
	if err != nil || formatted != source {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
}
