package compiler

import (
	"archive/zip"
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// buildAndRun writes the given files into a fresh directory, builds main.alc
// and returns the program's combined output and run error.
func buildAndRun(t *testing.T, files map[string]string) (string, error) {
	t.Helper()
	dir := t.TempDir()
	for name, content := range files {
		path := filepath.Join(dir, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(path, []byte(content), 0600); err != nil {
			t.Fatal(err)
		}
	}
	binary := filepath.Join(dir, "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	if err := BuildTo(filepath.Join(dir, "main.alc"), binary); err != nil {
		t.Fatalf("build: %v", err)
	}
	output, err := exec.Command(binary).CombinedOutput()
	return string(output), err
}

func TestExternStandardLibrary(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{"main.alc": `defmodule App do
  extern upper(text: string): string = "strings.ToUpper"
  extern repeat(text: string, count: integer): string = "strings.Repeat"
  extern fields(text: string): list[string] = "strings.Fields"
  extern join(parts: list[string], separator: string): string = "strings.Join"
  extern has_prefix(text: string, prefix: string): boolean = "strings.HasPrefix"
  extern quote(text: string): string = "strconv.Quote"
  extern itoa(value: integer): string = "strconv.Itoa"
  extern rune_count(text: string): integer = "unicode/utf8.RuneCountInString"
  extern collect() = "runtime.GC"
  def shout(text: string): string do
    return upper(text)
  end
  def main() do
    collect()
    assert(upper("abc") == "ABC")
    assert(repeat("ab", 3) == "ababab")
    assert(fields(" a  b c ") == ["a", "b", "c"])
    assert(join(["x", "y"], "-") == "x-y")
    assert(has_prefix("alchem", "al") and not has_prefix("alchem", "x"))
    assert(quote("hi") == "\"hi\"")
    assert(itoa(-42) == "-42")
    assert(rune_count("héllo") == 5)
    assert(map(["a", "b"], &upper) == ["A", "B"])
    assert("go" |> upper() |> repeat(2) == "GOGO")
    IO.puts(shout("extern ready"))
  end
end
`})
	if err != nil || output != "EXTERN READY\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

func TestExternIntegerRangeIsChecked(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{"main.alc": `defmodule App do
  extern repeat(text: string, count: integer): string = "strings.Repeat"
  extern rune(value: integer): string = "./native.Rune"
  def main() do
    assert(rune(65) == "A")
    text = rune(4294967296 + 65)
    IO.puts(text)
  end
end
`, "native/native.go": "package native\n\nfunc Rune(value int32) string { return string(rune(value)) }\n"})
	if err == nil || !strings.Contains(output, "main.alc:3:10: integer out of range for Go int32") {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

func TestExternLocalGoPackage(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{
		"main.alc": `defmodule App do
  import "lib/text.alc"
  def main() do
    IO.puts(Text.banner("shim", 2))
    assert(Text.total([1, 2, 3]) == 6)
    assert(Text.counts(["a", "bb"]) == %{"a" => 1, "bb" => 2})
  end
end
`,
		"lib/text.alc": `defmodule Text do
  extern banner(text: string, width: integer): string = "./native.Banner"
  extern total(values: list[integer]): integer = "./native.Total"
  extern counts(words: list[string]): map[string, integer] = "./native.Counts"
end
`,
		"lib/native/native.go": `package native

import (
	"fmt"
	"strings"
)

func Banner(text string, width int) string {
	edge := strings.Repeat("*", width)
	return fmt.Sprintf("%s %s %s", edge, text, edge)
}

func Total(values []int64) int64 {
	var sum int64
	for _, v := range values {
		sum += v
	}
	return sum
}

func Counts(words []string) map[string]int {
	out := map[string]int{}
	for _, w := range words {
		out[w] = len(w)
	}
	return out
}
`,
		"lib/native/native_test.go": "package native\n\nthis file must not be copied\n",
	})
	if err != nil || output != "** shim **\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

func TestExternDeclarationErrors(t *testing.T) {
	cases := []struct{ declaration, want string }{
		{`extern f(x: integer): integer = "strings"`, "extern target must be"},
		{`extern f(x: integer): integer = "strings.lower"`, "extern target must be"},
		{`extern f(x: integer): integer = "str ings.Upper"`, "extern target must be"},
		{`extern f(x: integer): integer = "strings\".Upper"`, "extern target must be"},
		{`extern f(x: integer): integer = "/abs/native.Upper"`, "extern target must be"},
		{`extern f(x: fn[integer,integer]): integer = "strings.Map"`, "extern f: Go strings.Map takes 2 parameters, the declaration has 1"},
		{`extern f(x: tuple[integer,integer]): integer = "strings.ToUpper"`, "extern f: parameter x: cannot pass tuple[integer,integer] as Go string"},
		{`extern f(x: string): pid[integer] = "strings.ToUpper"`, "extern f: cannot receive Go string as pid[integer]"},
		{`extern f(x: string): integer = "strings.ToUpper"`, "extern f: cannot receive Go string as integer"},
		{`extern f(x: string, y: string): string = "strings.ToUpper"`, "extern f: Go strings.ToUpper takes 1 parameters, the declaration has 2"},
		{`extern f(x: string): string = "strings.Absent"`, "extern f: Go package strings has no function Absent"},
		{`extern f(x: string): string = "no/such/pkg.Function"`, "load Go packages"},
		{`extern f(x: string): result[integer, integer] = "strconv.Atoi"`, "a Go error becomes result[T,string]"},
		{`extern f(x: string): integer = "strconv.Atoi"`, "Go returns 2 values here"},
		{`extern f(x: string) = "os.Remove"`, "declare the result as result[tuple[],string]"},
		{`extern f(x: a): a = "strings.ToUpper"`, "extern functions cannot use type variables"},
		{`extern type Buffer = "bytes.Missing"`, "extern type Buffer: Go package bytes has no type Missing"},
		{`extern type Buffer = "bytes"`, "extern type target must be"},
		{`extern type Buffer = "*bytes.Buffer" extern f(b: Buffer): integer = "bytes.Buffer.Absent"`, "has no method Absent"},
		{`extern type Buffer = "bytes.Buffer" extern f(b: Buffer, s: string): result[integer, string] = "bytes.Buffer.WriteString"`, "receiver: cannot pass App.Buffer as Go *bytes.Buffer"},
		{`extern type Buffer = "*bytes.Buffer" def same(a: Buffer, b: Buffer): boolean do a == b end`, "do not support equality"},
		{`extern type Buffer = "*bytes.Buffer" def keep(b: Buffer): pid[Buffer] do Process.self(1) end`, "mailbox messages cannot contain"},
		{`extern main() = "os.Exit"`, "main cannot be extern"},
		{`extern f(x: integer): integer = "strings.Count" extern f(x: integer): integer = "strings.Count"`, "duplicate function"},
		{`extern f(x: string) = "os.Unsetenv" def g(): integer do return f("a") end`, "returns no value"},
		{`extern f(x: string) = "os.Unsetenv" def g(): integer do x = f("a") return 1 end`, "returns no value"},
		{`require "example.test/lib" "1.0.0"`, "require needs a module path and a version"},
		{`require "example.test/lib\n" "v1.0.0"`, "require needs a module path and a version"},
		{`require "example.test/lib" "v1.0.0" require "example.test/lib" "v1.1.0"`, "conflicting versions"},
		{`extern f(x: string): string = "./missing.Upper"`, "extern package"},
	}
	for _, tc := range cases {
		t.Run(tc.declaration, func(t *testing.T) {
			dir := t.TempDir()
			entry := filepath.Join(dir, "main.alc")
			os.WriteFile(entry, []byte("defmodule App do "+tc.declaration+" def main() do assert(true) end end"), 0600)
			err := Check(entry)
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v, want %q", err, tc.want)
			}
		})
	}
}

// A signature that does not fit the Go function is reported by the Go
// compiler at the extern declaration's Alchem position.
func TestExternSignatureMismatchPointsAtDeclaration(t *testing.T) {
	dir := t.TempDir()
	entry := filepath.Join(dir, "main.alc")
	os.WriteFile(entry, []byte("defmodule App do\n  extern upper(text: string, extra: string): string = \"strings.ToUpper\"\n  def main() do\n    IO.puts(upper(\"a\", \"b\"))\n  end\nend\n"), 0600)
	err := BuildTo(entry, filepath.Join(dir, "out"))
	if err == nil || !strings.Contains(err.Error(), "main.alc:2") || !strings.Contains(err.Error(), "strings.ToUpper") {
		t.Fatalf("got %v", err)
	}
}

// writeModuleProxy lays out a file-based Go module proxy holding one module
// version, so a dependency can be resolved without network access.
func writeModuleProxy(t *testing.T, root, module, version string, files map[string]string) {
	t.Helper()
	dir := filepath.Join(root, filepath.FromSlash(module), "@v")
	if err := os.MkdirAll(dir, 0700); err != nil {
		t.Fatal(err)
	}
	write := func(name, content string) {
		if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0600); err != nil {
			t.Fatal(err)
		}
	}
	versions, _ := os.ReadFile(filepath.Join(dir, "list"))
	write("list", string(versions)+version+"\n")
	write(version+".info", `{"Version":"`+version+`"}`)
	write(version+".mod", "module "+module+"\n\ngo 1.21\n")
	archive, err := os.Create(filepath.Join(dir, version+".zip"))
	if err != nil {
		t.Fatal(err)
	}
	defer archive.Close()
	writer := zip.NewWriter(archive)
	files["go.mod"] = "module " + module + "\n\ngo 1.21\n"
	for name, content := range files {
		entry, err := writer.Create(module + "@" + version + "/" + name)
		if err != nil {
			t.Fatal(err)
		}
		if _, err = entry.Write([]byte(content)); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestExternRequiredModule(t *testing.T) {
	proxy := useModuleProxy(t)
	writeModuleProxy(t, proxy, "example.test/greet", "v1.2.0", map[string]string{
		"greet.go": "package greet\n\nfunc Hello(name string) string { return \"hello \" + name }\n",
	})
	output, err := buildAndRun(t, map[string]string{"main.alc": `defmodule App do
  require "example.test/greet" "v1.2.0"
  extern hello(name: string): string = "example.test/greet.Hello"
  def main() do
    IO.puts(hello("module"))
  end
end
`})
	if err != nil || output != "hello module\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

func TestExternFormatting(t *testing.T) {
	source := "defmodule App do\n  require \"example.test/greet\" \"v1.2.0\"\n\n  extern hello(name: string): string = \"example.test/greet.Hello\"\n\n  extern quiet(key: string) = \"os.Unsetenv\"\n\n  def main() do\n    IO.puts(hello(\"x\"))\n  end\nend\n"
	formatted, err := Format("defmodule App do require \"example.test/greet\" \"v1.2.0\" extern hello(name: string): string = \"example.test/greet.Hello\" extern quiet(key: string) = \"os.Unsetenv\" def main() do IO.puts(hello(\"x\")) end end")
	if err != nil || formatted != source {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
	again, err := Format(formatted)
	if err != nil || again != formatted {
		t.Fatalf("not idempotent: %v\n%s", err, again)
	}
}

func TestFloatRuntimeFailures(t *testing.T) {
	for expression, want := range map[string]string{
		"1.0 / 0.0":                  "division by zero",
		"trunc(1.0e300)":             "float out of integer range",
		`String.slice("abc", -1, 1)`: "slice bounds must be nonnegative",
	} {
		output, err := buildAndRun(t, map[string]string{"main.alc": "defmodule App do def main() do value = " + expression + " end end"})
		if err == nil || !strings.Contains(output, want) {
			t.Fatalf("%s: err=%v output=%s", expression, err, output)
		}
	}
}

func TestInterpolationFormatting(t *testing.T) {
	source := "defmodule App do\n  def main() do\n    name = \"x\"\n    IO.puts(\"a #{name} \\#{b} #{1 + 2}\\n\")\n    IO.puts(\"c\" <> \"d\")\n    value = 1.5\n  end\nend\n"
	formatted, err := Format(source)
	if err != nil || formatted != source {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
}

func TestPrivateFunctions(t *testing.T) {
	library := `defmodule Lib do
  def double(n: integer): integer do
    twice(n)
  end
  defp twice(0): integer do
    0
  end
  defp twice(n: integer) do
    n * 2
  end
end
`
	output, err := buildAndRun(t, map[string]string{"lib.alc": library, "main.alc": `defmodule App do
  import "lib.alc"
  defp local(n: integer): integer do
    n + 1
  end
  def main() do
    assert(Lib.double(4) == 8 and local(1) == 2)
    IO.puts("private ready")
  end
end
`})
	if err != nil || output != "private ready\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
	for body, want := range map[string]string{
		`assert(Lib.twice(4) == 8)`:           "Lib.twice is private",
		`assert(map([1], &Lib.twice) == [2])`: "Lib.twice is private",
	} {
		dir := t.TempDir()
		os.WriteFile(filepath.Join(dir, "lib.alc"), []byte(library), 0600)
		entry := filepath.Join(dir, "main.alc")
		os.WriteFile(entry, []byte("defmodule App do import \"lib.alc\" def main() do "+body+" end end"), 0600)
		if err := Check(entry); err == nil || !strings.Contains(err.Error(), want) {
			t.Fatalf("%s: got %v", body, err)
		}
	}
	if _, err := Format("defmodule A do def f(0): integer do 1 end defp f(_) do 2 end def main() do assert(true) end end"); err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	entry := filepath.Join(dir, "main.alc")
	os.WriteFile(entry, []byte("defmodule A do def f(0): integer do 1 end defp f(_) do 2 end def main() do assert(true) end end"), 0600)
	if err := Check(entry); err == nil || !strings.Contains(err.Error(), "must all be def or all be defp") {
		t.Fatalf("got %v", err)
	}
	formatted, err := Format("defmodule A do defp f(n: integer): integer do n end def main() do assert(true) end end")
	if err != nil || !strings.Contains(formatted, "  defp f(n: integer): integer do\n") {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
}

// useModuleProxy points the Go toolchain at a file-based proxy for one test.
func useModuleProxy(t *testing.T) string {
	t.Helper()
	proxy := t.TempDir()
	url := "file://" + filepath.ToSlash(proxy)
	if runtime.GOOS == "windows" {
		url = "file:///" + filepath.ToSlash(proxy)
	}
	t.Setenv("GOPROXY", url)
	t.Setenv("GONOSUMDB", "example.test")
	t.Setenv("GOFLAGS", "-modcacherw")
	t.Setenv("GOMODCACHE", t.TempDir())
	return proxy
}

func TestRemoteImports(t *testing.T) {
	proxy := useModuleProxy(t)
	writeModuleProxy(t, proxy, "example.test/mathlib", "v1.2.0", map[string]string{
		"lib/math.alc":                 "defmodule Math do\n  import \"helpers/scale.alc\"\n  struct Span do\n    low: integer\n    high: integer\n  end\n  def double(n: integer): integer do\n    Scale.by(n, 2)\n  end\n  def width(range: Span): integer do\n    range.high - range.low\n  end\nend\n",
		"lib/helpers/scale.alc":        "defmodule Scale do\n  extern repeat(text: string, count: integer): string = \"./native.Repeat\"\n  def by(n: integer, factor: integer): integer do\n    n * factor\n  end\nend\n",
		"lib/helpers/native/native.go": "package native\n\nimport \"strings\"\n\nfunc Repeat(text string, count int) string { return strings.Repeat(text, count) }\n",
		"escape.alc":                   "defmodule Escape do\n  import \"../outside.alc\"\n  def value(): integer do\n    1\n  end\nend\n",
	})
	writeModuleProxy(t, proxy, "example.test/mathlib", "v1.3.0", map[string]string{"lib/math.alc": "defmodule Math do\n  def double(n: integer): integer do\n    n * 2\n  end\nend\n"})
	output, err := buildAndRun(t, map[string]string{"main.alc": `defmodule App do
  import "example.test/mathlib@v1.2.0/lib/math.alc"
  import "example.test/mathlib@v1.2.0/lib/helpers/scale.alc"
  def main() do
    assert(Math.double(21) == 42)
    assert(Math.width(%Math.Span{low: 2, high: 9}) == 7)
    IO.puts(Scale.repeat("remote ", 2) <> "ready")
  end
end
`})
	if err != nil || output != "remote remote ready\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
	cases := map[string]string{
		`import "example.test/mathlib@v1.2.0/lib/math.alc" import "example.test/mathlib@v1.3.0/lib/math.alc"`: "conflicting versions of example.test/mathlib",
		`import "example.test/mathlib@v1.2.0/escape.alc"`:                                                     "leaves the package",
		`import "example.test/mathlib@v1.2.0/../x.alc"`:                                                       "remote imports are written",
		`import "example.test/mathlib@latest/lib/math.alc"`:                                                   "remote imports are written",
		`import "example.test/mathlib@v9.9.9/lib/math.alc"`:                                                   "fetch example.test/mathlib@v9.9.9",
		`import "example.test/mathlib@v1.2.0/lib/absent.alc"`:                                                 "read source",
	}
	for imports, want := range cases {
		dir := t.TempDir()
		entry := filepath.Join(dir, "main.alc")
		os.WriteFile(entry, []byte("defmodule App do "+imports+" def main() do assert(true) end end"), 0600)
		if err := Check(entry); err == nil || !strings.Contains(err.Error(), want) {
			t.Fatalf("%s: got %v, want %q", imports, err, want)
		}
	}
}

// Signatures are verified by check, without building the program.
func TestExternCheckedWithoutBuilding(t *testing.T) {
	dir := t.TempDir()
	entry := filepath.Join(dir, "main.alc")
	os.WriteFile(entry, []byte("defmodule App do\n  extern repeat(text: string, count: string): string = \"strings.Repeat\"\n  def main() do\n    IO.puts(repeat(\"a\", \"b\"))\n  end\nend\n"), 0600)
	diagnostic := Describe(Check(entry))
	if diagnostic == nil || diagnostic.File != entry || diagnostic.Line != 2 || diagnostic.Message != "extern repeat: parameter count: cannot pass string as Go int" {
		t.Fatalf("%+v", diagnostic)
	}
}

func TestExternMethodsHandlesAndVariadics(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{"main.alc": `defmodule App do
  extern type Builder = "*strings.Builder"
  extern type Reader = "io.Reader"
  extern type Regexp = "*regexp.Regexp"

  extern new_builder(): Builder = "./native.NewBuilder"
  extern write(builder: Builder, text: string): result[integer, string] = "strings.Builder.WriteString"
  extern text(builder: Builder): string = "strings.Builder.String"
  extern size(builder: Builder): integer = "strings.Builder.Len"
  extern reader(text: string): Reader = "./native.Reader"
  extern read_all(source: Reader): result[string, string] = "io.ReadAll"
  extern compile(pattern: string): result[Regexp, string] = "regexp.Compile"
  extern find_all(pattern: Regexp, text: string, limit: integer): list[string] = "regexp.Regexp.FindAllString"
  extern sprintf(format: string, values: list[string]): string = "fmt.Sprintf"
  extern sprint(values: list[integer]): string = "fmt.Sprint"
  extern join_path(parts: list[string]): string = "path.Join"
  extern cut(text: string, separator: string): tuple[string, string, boolean] = "strings.Cut"
  extern seconds(nanoseconds: integer): float = "time.Duration.Seconds"
  extern lookup(name: string): option[string] = "os.LookupEnv"

  def main() do
    builder = new_builder()
    assert(write(builder, "hello ") == ok(6) and write(builder, "world") == ok(5))
    assert(text(builder) == "hello world" and size(builder) == 11)
    assert(read_all(reader("stream")) == ok("stream"))
    case compile("[a-z]+[0-9]") do
      ok(pattern) -> assert(find_all(pattern, "ab1 cd2 ef", -1) == ["ab1", "cd2"])
      error(_) -> assert(false)
    end
    case compile("(") do
      ok(_) -> assert(false)
      error(reason) -> assert(String.contains(reason, "missing closing"))
    end
    assert(sprintf("%s-%s", ["a", "b"]) == "a-b" and sprint([1, 2]) == "1 2")
    assert(join_path(["a", "b", "c"]) == "a/b/c")
    assert(cut("key=value", "=") == {"key", "value", true})
    assert(seconds(1500000000) == 1.5)
    assert(lookup("ALCHEM_ABSENT_VARIABLE") == none)
    IO.puts("handles ready")
  end
end
`, "native/native.go": `package native

import (
	"io"
	"strings"
)

func NewBuilder() *strings.Builder { return &strings.Builder{} }

func Reader(text string) io.Reader { return strings.NewReader(text) }
`})
	if err != nil || output != "handles ready\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

func TestExternStructsAndCallbacks(t *testing.T) {
	output, err := buildAndRun(t, map[string]string{"main.alc": `defmodule App do
  struct Point do
    x: integer
    y: integer
    label: string
  end

  struct Line do
    from: Point
    to: Point
    tags: list[string]
  end

  extern shift(point: Point, by: integer): Point = "./native.Shift"
  extern midpoint(line: Line): Point = "./native.Midpoint"
  extern origin(): Point = "./native.Origin"
  extern find(points: list[Point], label: string): option[Point] = "./native.Find"
  extern broken(): Point = "./native.Broken"
  extern each(values: list[integer], f: fn[integer, integer]): list[integer] = "./native.Each"
  extern index(text: string, wanted: fn[integer, boolean]): integer = "strings.IndexFunc"
  extern adder(amount: integer): fn[integer, integer] = "./native.Adder"
  extern visit(values: list[string], f: fn[string, boolean]) = "./native.Visit"

  def main() do
    start = %Point{x: 1, y: 2, label: "start"}
    assert(shift(start, 10) == %Point{x: 11, y: 12, label: "start+10"})
    line = %Line{from: start, to: %Point{x: 5, y: 6, label: "end"}, tags: ["a"]}
    assert(midpoint(line) == %Point{x: 3, y: 4, label: "a"})
    assert(origin() == %Point{x: 0, y: 0, label: "origin"})
    assert(find([start], "start") == some(start) and find([start], "absent") == none)
    factor = 3
    assert(each([1, 2, 3], fn(n: integer): integer do n * factor end) == [3, 6, 9])
    assert(index("abc1", fn(character: integer): boolean do character < 97 end) == 3)
    add = adder(5)
    assert(add(1) == 6 and map([1, 2], add) == [6, 7])
    visit(["x", "y"], fn(value: string): boolean do
      IO.puts("visited #{value}")
      true
    end)
    missing = broken()
    IO.puts(missing.label)
  end
end
`, "native/native.go": `package native

import "fmt"

type Point struct {
	X, Y  int
	Label string
	note  string
}

type Line struct {
	From Point
	To   *Point
	Tags []string
}

func Shift(p Point, by int) Point {
	return Point{X: p.X + by, Y: p.Y + by, Label: fmt.Sprintf("%s+%d", p.Label, by)}
}

func Midpoint(l *Line) Point {
	return Point{X: (l.From.X + l.To.X) / 2, Y: (l.From.Y + l.To.Y) / 2, Label: l.Tags[0]}
}

func Origin() *Point { return &Point{Label: "origin"} }

func Find(points []Point, label string) *Point {
	for i := range points {
		if points[i].Label == label {
			return &points[i]
		}
	}
	return nil
}

func Broken() *Point { return nil }

func Each(values []int64, f func(int64) int64) []int64 {
	out := make([]int64, len(values))
	for i, v := range values {
		out[i] = f(v)
	}
	return out
}

func Adder(amount int) func(int) int { return func(n int) int { return n + amount } }

func Visit(values []string, f func(string) bool) {
	for _, v := range values {
		f(v)
	}
}
`})
	if err == nil || !strings.HasPrefix(output, "visited x\nvisited y\n") || !strings.Contains(output, "main.alc:18:10: Go returned a nil *native.Point") {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

func TestLockFile(t *testing.T) {
	proxy := useModuleProxy(t)
	writeModuleProxy(t, proxy, "example.test/mathlib", "v1.2.0", map[string]string{"math.alc": "defmodule Math do\n  def double(n: integer): integer do\n    n * 2\n  end\nend\n"})
	writeModuleProxy(t, proxy, "example.test/greet", "v1.2.0", map[string]string{"greet.go": "package greet\n\nfunc Hello(name string) string { return \"hello \" + name }\n"})
	dir := t.TempDir()
	entry, lockPath, binary := filepath.Join(dir, "main.alc"), filepath.Join(dir, LockName), filepath.Join(dir, "program")
	os.WriteFile(entry, []byte(`defmodule App do
  import "example.test/mathlib@v1.2.0/math.alc"
  require "example.test/greet" "v1.2.0"
  extern hello(name: string): string = "example.test/greet.Hello"
  def main() do
    IO.puts(hello("lock #{Math.double(2)}"))
  end
end
`), 0600)
	if err := BuildWithOptions(entry, BuildOptions{Output: binary, Locked: true}); err == nil || !strings.Contains(err.Error(), "alchem.lock has no entry for example.test/mathlib@v1.2.0") {
		t.Fatalf("locked build without a lock: %v", err)
	}
	if _, err := os.Stat(lockPath); !os.IsNotExist(err) {
		t.Fatal("locked build wrote a lock file")
	}
	if err := BuildTo(entry, binary); err != nil {
		t.Fatal(err)
	}
	written, err := os.ReadFile(lockPath)
	lock := string(written)
	if err != nil || !strings.Contains(lock, "package example.test/mathlib v1.2.0 h1:") || !strings.Contains(lock, "module example.test/greet v1.2.0 h1:") || !strings.Contains(lock, "module example.test/greet v1.2.0/go.mod h1:") {
		t.Fatalf("err=%v lock=%s", err, lock)
	}
	// An up-to-date lock satisfies locked builds and checks and is left alone.
	if err := BuildWithOptions(entry, BuildOptions{Output: binary, Locked: true}); err != nil {
		t.Fatal(err)
	}
	if err := CheckLocked(context.Background(), entry, true); err != nil {
		t.Fatal(err)
	}
	if again, _ := os.ReadFile(lockPath); string(again) != lock {
		t.Fatalf("lock changed:\n%s", again)
	}
	tamper := func(prefix string) {
		lines := strings.Split(lock, "\n")
		for i, line := range lines {
			if strings.HasPrefix(line, prefix) {
				lines[i] = line[:strings.LastIndex(line, " ")] + " h1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
			}
		}
		os.WriteFile(lockPath, []byte(strings.Join(lines, "\n")), 0600)
	}
	tamper("package example.test/mathlib")
	if err := Check(entry); err == nil || !strings.Contains(err.Error(), "example.test/mathlib@v1.2.0 does not match alchem.lock") {
		t.Fatalf("changed package: %v", err)
	}
	tamper("module example.test/greet v1.2.0 h1:")
	if err := BuildTo(entry, binary); err == nil || !strings.Contains(err.Error(), "checksum mismatch") {
		t.Fatalf("changed module: %v", err)
	}
	// A program that no longer uses anything remote drops its lock.
	os.WriteFile(lockPath, []byte(lock), 0600)
	os.WriteFile(entry, []byte("defmodule App do def main() do assert(true) end end"), 0600)
	if err := Check(entry); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(lockPath); !os.IsNotExist(err) {
		t.Fatal("unused lock was kept")
	}
}

// Fetching through the public Go module proxy needs network access, so this
// runs only on request: ALCHEM_NETWORK_TESTS=1 go test ./compiler -run Public
func TestPublicModuleHost(t *testing.T) {
	if os.Getenv("ALCHEM_NETWORK_TESTS") == "" {
		t.Skip("set ALCHEM_NETWORK_TESTS=1 to fetch from the public module proxy")
	}
	t.Setenv("GOFLAGS", "-modcacherw")
	t.Setenv("GOMODCACHE", t.TempDir())
	output, err := buildAndRun(t, map[string]string{"main.alc": `defmodule App do
  require "rsc.io/quote" "v1.5.2"
  extern hello(): string = "rsc.io/quote.Hello"
  def main() do
    IO.puts(hello())
  end
end
`})
	if err != nil || output != "Hello, world.\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
	// The package downloads and verifies; only the named file is absent.
	dir := t.TempDir()
	entry := filepath.Join(dir, "main.alc")
	os.WriteFile(entry, []byte(`defmodule App do import "rsc.io/quote@v1.5.2/absent.alc" def main() do assert(true) end end`), 0600)
	if err := Check(entry); err == nil || !strings.Contains(err.Error(), "read source") {
		t.Fatalf("got %v", err)
	}
}

func TestFormatTestFiles(t *testing.T) {
	source := "defmodule T do\n  setup do\n    IO.puts(\"s\")\n  end\n\n  test \"top\" do\n    assert(true)\n  end\n\n  describe \"a\" do\n    setup do\n      IO.puts(\"a\")\n    end\n\n    describe \"b\" do\n      test \"inner\" do\n        assert(true)\n      end\n    end\n\n    test \"after\" do\n      refute(false)\n    end\n  end\n\n  describe \"c\" do\n    test \"last\" do\n      cond do\n        true ->\n          assert(1 in 1..3)\n      end\n    end\n  end\nend\n"
	formatted, err := Format(source)
	if err != nil || formatted != source {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
}

// The reference is generated from the signature table, so it cannot drift.
func TestCommentsSurviveFormatting(t *testing.T) {
	source := "# A module comment.\ndefmodule C do\n  # A documented struct.\n  struct P do\n    x: integer\n  end\n\n  # Doubles a number.\n  #\n  #     alx> C.double(2)\n  #     4\n  def double(n: integer): integer do\n    # before the statement\n    doubled = n * 2\n    case doubled do\n      0 ->\n        # inside an arm\n        0\n      _ -> doubled\n    end\n    # at the end of the body\n  end\n\n  def main() do\n    IO.puts(\"x # not a comment #{double(1)}\")\n  end\n  # trailing\nend\n"
	formatted, err := Format(source)
	if err != nil || formatted != source {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
	// An end-of-line comment moves to its own line; nothing is lost.
	moved, err := Format("defmodule C do\n  def main() do\n    x = 1 # why\n    IO.puts(\"#{x}\")\n  end\nend\n")
	if err != nil || !strings.Contains(moved, "    x = 1\n    # why\n    IO.puts") {
		t.Fatalf("err=%v\n%s", err, moved)
	}
	output, err := buildAndRun(t, map[string]string{"main.alc": source})
	if err != nil || output != "x # not a comment 2\n" {
		t.Fatalf("err=%v output=%s", err, output)
	}
}

func TestFormatTestContextTagsAndDoctests(t *testing.T) {
	source := "defmodule T do\n  import \"calc.alc\"\n  doctest Calc\n  @moduletag \"unit\"\n\n  setup_all do\n    1\n  end\n\n  setup base do\n    base + 1\n  end\n\n  @tag \"slow\"\n  @tag \"db\"\n  test \"uses it\", n do\n    assert(n == 2)\n  end\n\n  @tag \"group\"\n  describe \"g\" do\n    test \"matches\", 2 do\n      x = try do\n        raise(\"a\")\n      rescue\n        message -> message\n      after\n        IO.puts(\"done\")\n      end\n      with ok(v) <- Integer.parse(x),\n           some(w) <- List.first([v]) do\n        assert(w == 1)\n      else\n        _ ->\n          assert(for(i <- 1..2, i > 1, do: i) == [2])\n      end\n      for line <- ~w(a b) do\n        IO.puts(line)\n      end\n      assert(String.match?(\"a\", ~r/a/i))\n      assert(~D[2026-01-05] == ~D[2026-01-05])\n    end\n  end\nend\n"
	formatted, err := Format(source)
	if err != nil || formatted != source {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
}

func TestHeredocsAndDocstrings(t *testing.T) {
	q := `"""`
	source := "# About this file.\ndefmodule Shapes do\n  @moduledoc " + q + "\n  Shapes and their areas.\n\n  Second paragraph.\n  " + q + "\n\n  @typedoc " + q + "\n  A point on the plane.\n  " + q + "\n  struct Point do\n    x: integer\n  end\n\n  # An ordinary comment stays a comment.\n  @doc " + q + "\n  Doubles a number.\n\n      alx> Shapes.double(2)\n      4\n  " + q + "\n  def double(0): integer do\n    0\n  end\n\n  def double(n: integer) do\n    n * 2\n  end\n\n  def main() do\n    IO.puts(" + `"lines:\n  indented \"quoted\"\n"` + ")\n  end\nend\n"
	formatted, err := Format(source)
	if err != nil || formatted != source {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
	// A heredoc interpolates and reads escapes, as a string does; ~S""" is
	// literal.
	program := "defmodule Shapes do\n  @doc " + q + "\n  Says hello.\n  " + q + "\n  def main() do\n    text = " + q + "\n    lines:\n      indented \"quoted\" #{1 + 1}\\tend\n    " + q + "\n    IO.write(text)\n    literal = ~S" + q + "\n    #{not interpolated} \\n stays\n    " + q + "\n    IO.write(literal)\n  end\nend\n"
	output, err := buildAndRun(t, map[string]string{"main.alc": program})
	if err != nil || output != "lines:\n  indented \"quoted\" 2\tend\n#{not interpolated} \\n stays\n" {
		t.Fatalf("err=%v output=%q", err, output)
	}
	for body, want := range map[string]string{
		"@doc 5 def main() do assert(true) end":                         "@doc takes a string",
		"def main() do x = " + q + "oops" + q + " end":                  "a heredoc starts with",
		"def main() do x = " + q + "\n never closed\n assert(true) end": "a heredoc starts with",
	} {
		dir := t.TempDir()
		entry := filepath.Join(dir, "main.alc")
		os.WriteFile(entry, []byte("defmodule A do\n"+body+"\nend\n"), 0600)
		if err := Check(entry); err == nil || !strings.Contains(err.Error(), want) {
			t.Fatalf("%s: got %v", body, err)
		}
	}
}

func TestDocumentationAndReduceDiagnostics(t *testing.T) {
	dir := t.TempDir()
	check := func(source string) string {
		path := filepath.Join(dir, "main.alc")
		if err := os.WriteFile(path, []byte(source), 0600); err != nil {
			t.Fatal(err)
		}
		if err := Check(path); err != nil {
			return err.Error()
		}
		return ""
	}
	orphan := check("defmodule T do\n  def main() do\n    IO.puts(\"x\")\n  end\n\n  @doc \"\"\"\n  Orphan.\n  \"\"\"\nend\n")
	if !strings.Contains(orphan, "6:4:") || !strings.Contains(orphan, "@doc is not followed by anything to document") {
		t.Fatalf("documentation with nothing after it: %q", orphan)
	}
	// @doc false documents nothing on purpose, wherever it is written.
	if message := check("defmodule T do\n  @doc false\n  def main() do\n    IO.puts(\"x\")\n  end\n  @doc false\nend\n"); message != "" {
		t.Fatalf("@doc false: %s", message)
	}
	empty := check("defmodule T do\n  def main() do\n    counts = for word <- [\"a\"], reduce: %{} do\n      seen -> Map.put(seen, word, 1)\n    end\n    IO.puts(inspect(counts))\n  end\nend\n")
	if !strings.Contains(empty, "3:41:") || !strings.Contains(empty, "the empty reduce: value needs a type") {
		t.Fatalf("empty reduce value: %q", empty)
	}
	// A function inside an interpolation is formatted on its line and the
	// result still parses.
	source := "defmodule T do\n  def main() do\n    IO.puts(\"#{Enum.max(Enum.take([1], 0), fn -> -1 end)} #{String.duplicate(\"a  b\", 2)}\")\n  end\nend\n"
	formatted, err := Format(source)
	if err != nil || formatted != source {
		t.Fatalf("err=%v\n%s", err, formatted)
	}
}

// The zone database is large, so only a program that puts a DateTime in a
// zone links it; other date and time functions do not.
func TestZoneDatabaseIsLinkedOnlyWhenUsed(t *testing.T) {
	dates := selectLibrary("func main(){ _ = calDateIso(TDate{}); _ = calDateTimeString(TDateTime{}) }")
	if !strings.Contains(dates, "func calDateTimeString(") || strings.Contains(dates, "time/tzdata") || strings.Contains(dates, "time.LoadLocation(") {
		t.Fatal("a program without time zones carries the zone database")
	}
	zones := selectLibrary("func main(){ _ = calShiftZone(TDateTime{}, \"Asia/Tokyo\") }")
	if !strings.Contains(zones, "\"time/tzdata\"") || !strings.Contains(zones, "func calDateTimeString(") {
		t.Fatal("a program with time zones lacks the zone database or the calendar functions")
	}
}

func TestProtocolDiagnostics(t *testing.T) {
	dir := t.TempDir()
	check := func(body string) string {
		path := filepath.Join(dir, "main.alc")
		source := "defmodule T do\n  defprotocol Show do\n    def show(value): string\n    def size(value): integer\n  end\n\n" + body + "\nend\n"
		if err := os.WriteFile(path, []byte(source), 0600); err != nil {
			t.Fatal(err)
		}
		if err := Check(path); err != nil {
			return err.Error()
		}
		return ""
	}
	whole := "  defimpl Show, for: integer do\n    def show(n): string do\n      \"#{n}\"\n    end\n\n    def size(n): integer do\n      n\n    end\n  end\n"
	cases := map[string][2]string{
		"works":             {whole + "  def main() do\n    IO.puts(Show.show(Show.size(3)))\n  end", ""},
		"no implementation": {whole + "  def main() do\n    IO.puts(Show.show(\"text\"))\n  end", "Show is not implemented for string"},
		"missing function":  {"  defimpl Show, for: integer do\n    def show(n): string do\n      \"#{n}\"\n    end\n  end\n  def main() do\n    IO.puts(\"x\")\n  end", "the implementation of Show for integer lacks size"},
		"twice":             {whole + whole + "  def main() do\n    IO.puts(\"x\")\n  end", "Show is already implemented for integer"},
		"wrong result":      {"  defimpl Show, for: integer do\n    def show(n): integer do\n      n\n    end\n\n    def size(n): integer do\n      n\n    end\n  end\n  def main() do\n    IO.puts(\"x\")\n  end", "Show.show returns string, not integer"},
		"extra function":    {"  defimpl Show, for: integer do\n    def other(n): string do\n      \"#{n}\"\n    end\n  end\n  def main() do\n    IO.puts(\"x\")\n  end", "Show has no function other"},
		"unknown protocol":  {"  defimpl Nope, for: integer do\n    def show(n): string do\n      \"#{n}\"\n    end\n  end\n  def main() do\n    IO.puts(\"x\")\n  end", "defimpl of Nope, which no module declares"},
		"type variable":     {whole + "  def both(value: a): string do\n    Show.show(value)\n  end\n  def main() do\n    IO.puts(both(1))\n  end", "cannot be called on a value of the type variable a"},
	}
	for name, test := range cases {
		got := check(test[0])
		if (test[1] == "") != (got == "") || !strings.Contains(got, test[1]) {
			t.Errorf("%s: got %q, want %q", name, got, test[1])
		}
	}
}
