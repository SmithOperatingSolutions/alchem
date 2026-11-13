package compiler

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Generic Go functions are bound with their type arguments inferred from
// the declaration, including through constraints such as S ~[]E and
// through callbacks.
func TestExternGenericFunctions(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{
		"main.alc": `defmodule App do
  extern max_int(xs: list[integer]): integer = "slices.Max"
  extern max_text(xs: list[string]): string = "slices.Max"
  extern contains(xs: list[float], x: float): boolean = "slices.Contains"
  extern index(xs: list[string], x: string): integer = "slices.Index"
  extern first(xs: list[integer], test: fn[integer, boolean]): integer = "slices.IndexFunc"
  extern copy_of(xs: list[integer]): list[integer] = "slices.Clone"
  extern equal(a: map[string, integer], b: map[string, integer]): boolean = "maps.Equal"
  extern pick(xs: list[integer], width: integer): integer = "./native.Pick"

  def main() do
    assert(max_int([3, 9, 2]) == 9)
    assert(max_text(["b", "c", "a"]) == "c")
    assert(contains([1.5, 2.5], 2.5) and not contains([1.5], 3.0))
    assert(index(["a", "b"], "b") == 1 and index(["a"], "z") == -1)
    assert(first([1, 3, 4, 6], fn n -> rem(n, 2) == 0 end) == 2)
    assert(copy_of([1, 2]) == [1, 2])
    assert(equal(%{"a" => 1}, %{"a" => 1}) and not equal(%{"a" => 1}, %{"a" => 2}))
    assert(pick([5, 6, 7], 1) == 6)
    IO.puts("generic")
  end
end
`,
		"native/native.go": `package native

// Pick takes a slice of any integer type and an index of another.
func Pick[S ~[]E, E ~int64 | ~int32, I ~int | ~int64](xs S, at I) E {
	return xs[at]
}
`,
	})
	if err != nil || output != "generic\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

// Alchem functions implement Go interfaces: a function for an interface of
// one method, a struct of functions for one of several, with Go errors and
// several results converted.
func TestExternInterfaces(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{
		"main.alc": `defmodule App do
  struct Square do
    side: float
    area: fn[float, float]
    name: fn[string]
  end

  struct Splitter do
    split_pair: fn[string, tuple[string, string]]
  end

  extern write(w: fn[string, result[integer, string]], text: string): result[integer, string] = "io.WriteString"
  extern describe(shape: Square, side: float): string = "./native.Describe"
  extern visit(v: fn[integer, result[tuple[], string]], n: integer): result[integer, string] = "./native.VisitAll"
  extern halves(s: Splitter, text: string): string = "./native.Halves"
  extern problem(message: string): string = "./native.Explain"
  extern stringer(f: fn[string]): string = "./native.Show"

  def main() do
    me: pid[string] = Process.self(8)
    written = write(fn text ->
      Process.send(me, text, 100)
      if text == "" do
        error("empty")
      else
        ok(String.length(text))
      end
    end, "hello")
    assert(written == ok(5))
    assert(Process.receive(me, 100) == {true, "hello"})
    assert(write(fn _ -> error("refused") end, "x") == error("refused"))
    square = %Square{side: 2.0, area: fn side -> side * side end, name: fn -> "square" end}
    assert(describe(square, 3.0) == "square 9.0")
    stop_at_three = fn(n: integer): result[tuple[], string] do
      if n < 3 do
        ok({})
      else
        error("stop at " <> Integer.to_string(n))
      end
    end
    assert(visit(stop_at_three, 5) == error("stop at 3"))
    assert(visit(fn _ -> ok({}) end, 2) == ok(2))
    assert(halves(%Splitter{split_pair: fn text -> {String.slice(text, 0, 2), String.slice(text, 2, 9)} end}, "abcd") == "ab|cd")
    assert(problem("disk full") == "error: disk full")
    assert(stringer(fn -> "shown" end) == "<shown>")
    IO.puts("interfaces")
  end
end
`,
		"native/native.go": `package native

import "fmt"

type Shape interface {
	Area(side float64) float64
	Name() string
}

func Describe(s Shape, side float64) string { return fmt.Sprintf("%s %.1f", s.Name(), s.Area(side)) }

type Visitor interface{ Visit(n int) error }

// VisitAll visits 0..n-1 and stops at the first error.
func VisitAll(v Visitor, n int) (int, error) {
	for i := 0; i < n; i++ {
		if err := v.Visit(i); err != nil {
			return i, err
		}
	}
	return n, nil
}

type Pair interface{ SplitPair(s string) (string, string) }

func Halves(p Pair, s string) string { a, b := p.SplitPair(s); return a + "|" + b }

func Explain(err error) string { return "error: " + err.Error() }

func Show(s fmt.Stringer) string { return "<" + s.String() + ">" }
`,
	})
	if err != nil || output != "interfaces\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

func TestExternInterfaceAndGenericMismatches(t *testing.T) {
	cases := []struct{ declaration, want string }{
		{`extern f(xs: list[boolean]): boolean = "slices.Max"`, "bool does not satisfy cmp.Ordered"},
		{`extern f(): integer = "slices.Max"`, "takes 1 parameters, the declaration has 0"},
		{`extern f(xs: tuple[integer, integer]): integer = "slices.Max"`, "cannot infer the Go type parameter S"},
		{`extern f(w: fn[string, integer], s: string): result[integer, string] = "io.WriteString"`, "Go returns an error"},
		{`extern f(w: fn[integer, result[integer, string]], s: string): result[integer, string] = "io.WriteString"`, "cannot receive Go []byte as integer"},
		{`extern f(w: integer, s: string): result[integer, string] = "io.WriteString"`, "cannot pass integer as Go io.Writer"},
		{`extern f(data: fn[integer]) = "sort.Sort"`, "an interface of one method, and it has 3"},
		{`struct Data do len: fn[integer] end extern f(data: Data) = "sort.Sort"`, "it has no field for the method Less"},
		{`struct Data do len: integer end extern f(data: Data) = "sort.Sort"`, "field len is not a function"},
	}
	for _, tc := range cases {
		t.Run(tc.declaration, func(t *testing.T) {
			entry := filepath.Join(t.TempDir(), "main.alc")
			os.WriteFile(entry, []byte("defmodule App do "+tc.declaration+" def main() do assert(true) end end"), 0o600)
			if err := Check(entry); err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}
