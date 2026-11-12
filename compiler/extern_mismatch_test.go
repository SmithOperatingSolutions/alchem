package compiler

import (
	"os"
	"path/filepath"
	"testing"
)

// An extern declaration that does not fit the Go function it names is
// reported when the program is checked, whatever the part that does not fit.
func TestExternMismatchesAreReported(t *testing.T) {
	native := `package native

type Point struct {
	X, Y int64
	Label string
}

type Hidden struct{ x int64 }

func Shift(p Point, by int64) Point            { return Point{p.X + by, p.Y + by, p.Label} }
func Take(h Hidden) int64                       { return h.x }
func Each(values []int64, f func(int64) int64) []int64 { return values }
func Make() func(int64) int64                   { return nil }
func Pair() (int64, string)                     { return 1, "a" }
func Lookup(m map[string]int64) bool            { return m != nil }
func Many(xs ...string) int                     { return len(xs) }
func Show(v any) string                         { return "" }
func Quiet()                                    {}
func Split() (int64, string, error)             { return 1, "a", nil }
func Hidden2() hidden                           { return hidden{} }

type hidden struct{}

type Counter struct{ N int64 }

func (c Counter) Get() int64 { return c.N }
`
	cases := map[string]string{
		"argument type":           `extern f(x: float): string = "strings.ToUpper"`,
		"result type":             `extern f(x: string): integer = "strings.ToUpper"`,
		"argument count":          `extern f(): string = "strings.ToUpper"`,
		"unknown package":         `extern f(): integer = "alchem_no_such_pkg.F"`,
		"unknown function":        `extern f(): integer = "strings.NoSuchFunction"`,
		"unknown type":            `extern f(x: string): string = "strings.NoSuchType.Method"`,
		"method receiver":         `extern f(x: string): string = "strings.Builder.String"`,
		"boolean for integer":     `extern f(x: boolean): string = "strconv.Itoa"`,
		"list element":            `extern f(x: list[integer]): string = "strings.Join"`,
		"map type":                `extern f(x: map[string, string]): boolean = "./native.Lookup"`,
		"struct field":            `struct P do` + "\n    x: string\n  end\n  " + `extern f(p: P, by: integer): P = "./native.Shift"`,
		"unexported fields":       `struct H do` + "\n    x: integer\n  end\n  " + `extern f(h: H): integer = "./native.Take"`,
		"not a struct":            `struct S do` + "\n    x: integer\n  end\n  " + `extern f(x: S): string = "strings.ToUpper"`,
		"callback parameter":      `extern f(xs: list[integer], g: fn[string, integer]): list[integer] = "./native.Each"`,
		"callback result":         `extern f(xs: list[integer], g: fn[integer, string]): list[integer] = "./native.Each"`,
		"callback returned":       `extern f(): fn[string, integer] = "./native.Make"`,
		"two results":             `extern f(): string = "./native.Pair"`,
		"variadic":                `extern f(x: integer): integer = "./native.Many"`,
		"float result":            `extern f(x: float): boolean = "math.Sqrt"`,
		"tuple":                   `extern f(x: tuple[integer, string]): string = "strings.ToUpper"`,
		"option":                  `extern f(x: option[string]): string = "strings.ToUpper"`,
		"any of a tuple":          `extern f(x: tuple[integer, string]): string = "./native.Show"`,
		"any of a list":           `extern f(x: list[tuple[integer]]): string = "./native.Show"`,
		"any of a map":            `extern f(x: map[string, option[integer]]): string = "./native.Show"`,
		"nothing returned":        `extern f(): integer = "./native.Quiet"`,
		"error not string":        `extern f(): result[tuple[integer, string], integer] = "./native.Split"`,
		"results tuple":           `extern f(): result[tuple[integer], string] = "./native.Split"`,
		"result element":          `extern f(): result[tuple[string, string], string] = "./native.Split"`,
		"unexported result":       `extern f(): integer = "./native.Hidden2"`,
		"method without receiver": `extern f(): integer = "./native.Counter.Get"`,
	}
	for name, declaration := range cases {
		dir := t.TempDir()
		os.MkdirAll(filepath.Join(dir, "native"), 0o755)
		os.WriteFile(filepath.Join(dir, "go.mod"), []byte("module app\n\ngo 1.21\n"), 0o644)
		os.WriteFile(filepath.Join(dir, "native", "native.go"), []byte(native), 0o644)
		entry := filepath.Join(dir, "main.alc")
		source := "defmodule App do\n  " + declaration + "\n\n  def main() do\n    IO.puts(\"never\")\n  end\nend\n"
		os.WriteFile(entry, []byte(source), 0o644)
		func() {
			defer func() {
				if v := recover(); v != nil {
					t.Errorf("%s: the checker panicked: %v", name, v)
				}
			}()
			if err := Check(entry); err == nil {
				t.Errorf("%s: accepted %s", name, declaration)
			}
		}()
	}
}

// Values that Go takes as "any", Go maps and multi-result functions convert
// both ways.
func TestExternConversionsAreAccepted(t *testing.T) {
	native := `package native

type Counter struct{ N int64 }

func (c Counter) Get() int64                 { return c.N }
func Show(v any) string                      { return "" }
func Lookup(m map[string]int64) bool         { return m != nil }
func Keys() map[string][]float64             { return nil }
func Split() (int64, string, error)          { return 1, "a", nil }
func Maybe() (int64, string, bool)           { return 1, "a", true }
`
	declarations := []string{
		`extern f(x: float): string = "./native.Show"`,
		`extern f(x: boolean): string = "./native.Show"`,
		`extern f(x: list[integer]): string = "./native.Show"`,
		`extern f(x: map[string, float]): string = "./native.Show"`,
		`extern f(x: map[string, integer]): boolean = "./native.Lookup"`,
		`extern f(): map[string, list[float]] = "./native.Keys"`,
		`extern f(): result[tuple[integer, string], string] = "./native.Split"`,
		`extern f(): option[tuple[integer, string]] = "./native.Maybe"`,
	}
	for _, declaration := range declarations {
		dir := t.TempDir()
		os.MkdirAll(filepath.Join(dir, "native"), 0o755)
		os.WriteFile(filepath.Join(dir, "go.mod"), []byte("module app\n\ngo 1.21\n"), 0o644)
		os.WriteFile(filepath.Join(dir, "native", "native.go"), []byte(native), 0o644)
		entry := filepath.Join(dir, "main.alc")
		source := "defmodule App do\n  " + declaration + "\n\n  def main() do\n    IO.puts(\"never\")\n  end\nend\n"
		os.WriteFile(entry, []byte(source), 0o644)
		if err := Check(entry); err != nil {
			t.Errorf("%s: %v", declaration, err)
		}
	}
}
