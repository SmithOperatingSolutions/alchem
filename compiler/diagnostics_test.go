package compiler

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func TestRuntimeSourceDiagnostics(t *testing.T) {
	cases := []struct{ name, body, token, message string }{
		{"closure failure", "  xs = map([1],fn(value: integer): integer do return value / 0 end)", "/", "division by zero"},
		{"guard failure", "  case 1 do n when 1 / 0 == n -> assert(true) _ -> assert(false) end", "/", "division by zero"},
		{"missing map key", "  value = %{\"a\" => 1}[\"absent\"]", "[\"absent\"]", "map key not found"},
		{"map pattern", "  %{\"absent\" => x} = %{\"a\" => 1}", "%{\"absent\"", "pattern match failed"},
		{"assertion", "  assert(false)", "assert", "assertion failed"},
		{"overflow", "  value = 9223372036854775807 + 1", "+", "integer overflow"},
		{"division", "  value = 1 / 0", "/", "division by zero"},
		{"index", "  value = [1][-1]", "[-1]", "list index out of bounds"},
		{"upper index", "  value = [1][1]", "[1]", "list index out of bounds"},
		{"empty index", "  xs: list[integer] = [] value = xs[0]", "[0]", "list index out of bounds"},
		{"pattern length", "  [a,b] = [1]", "[a,b]", "pattern match failed"},
		{"pattern literal", "  {0,x} = {1,\"bad\"}", "{0,x}", "pattern match failed"},
		{"pinned pattern", "  x = 1 {^x,y} = {2,3}", "{^x,y}", "pattern match failed"},
		{"negative take", "  value = List.take([1],0-1)", "List.take", "count must be nonnegative"},
		{"negative drop", "  value = List.drop([1],0-1)", "List.drop", "count must be nonnegative"},
		{"oversized range", "  value = List.range(0,1000000)", "List.range", "range exceeds 1000000 elements"},
		{"extreme range", "  value = List.range(-9223372036854775808,9223372036854775807)", "List.range", "range exceeds 1000000 elements"},
		{"negative slice start", "  value = String.slice(\"abc\",0-1,1)", "String.slice", "slice bounds must be nonnegative"},
		{"negative slice count", "  value = String.slice(\"abc\",0,0-1)", "String.slice", "slice bounds must be nonnegative"},
		{"empty separator", "  value = String.split(\"abc\",\"\")", "String.split", "separator must not be empty"},
		{"nested pattern", "  [[],[x]]: list[list[integer]] = [[],[]]", "[[],[x]]", "pattern match failed"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			// Each case builds and runs a program of its own.
			t.Parallel()
			source := filepath.Join(t.TempDir(), "source with spaces.alc")
			binary := filepath.Join(t.TempDir(), "program")
			if runtime.GOOS == "windows" {
				binary += ".exe"
			}
			program := "defmodule Check do\n def main() do\n" + tc.body + "\n end\nend\n"
			if err := os.WriteFile(source, []byte(program), 0600); err != nil {
				t.Fatal(err)
			}
			if err := BuildTo(source, binary); err != nil {
				t.Fatal(err)
			}
			// The cases run in parallel with each other and other packages,
			// so a program gets more time than it needs alone.
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()
			output, err := exec.CommandContext(ctx, binary).CombinedOutput()
			exit, ok := err.(*exec.ExitError)
			if !ok || exit.ExitCode() != 2 {
				t.Fatalf("err=%v output=%s", err, output)
			}
			column := strings.LastIndex(tc.body, tc.token) + 1
			want := fmt.Sprintf("%s:3:%d: %s\n", source, column, tc.message)
			if !strings.HasPrefix(string(output), want) || !strings.Contains(string(output), "  at ") {
				t.Fatalf("got %q want %q", output, want)
			}
		})
	}
}
func TestRuntimeDiagnosticInsideFunction(t *testing.T) {
	source := filepath.Join(t.TempDir(), "function.alc")
	binary := filepath.Join(t.TempDir(), "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	program := "defmodule Check do\n def broken(): integer do\n  return 1 / 0\n end\n def main() do\n  result = broken()\n end\nend\n"
	if err := os.WriteFile(source, []byte(program), 0600); err != nil {
		t.Fatal(err)
	}
	if err := BuildTo(source, binary); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	output, err := exec.CommandContext(ctx, binary).CombinedOutput()
	if err == nil || !strings.HasPrefix(string(output), source+":3:12: division by zero\n") || !strings.Contains(string(output), "Check.broken") {
		t.Fatalf("err=%v output=%q", err, output)
	}
}

// Frames must name the Alchem line of the statement, not a neighbouring one,
// including after multi-line constructs such as closures and case arms.
func TestRuntimeFrameLines(t *testing.T) {
	source := filepath.Join(t.TempDir(), "frames.alc")
	binary := filepath.Join(t.TempDir(), "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	program := `defmodule Frames do
  def broken(n: integer): integer do
    f = fn(d: integer): integer do
      return 1
    end
    case n do
      0 ->
        return 0
      other when other / n == 1 ->
        return f(1) / (n - 7)
      _ ->
        return 2
    end
  end
  def main() do
    empty: pid[list[integer]] = Process.self(1)
    {ok, values} = Process.receive(empty, 0)
    assert(not ok and values == [] and length(values) == 0)
    counts: pid[map[string,integer]] = Process.self(1)
    result = broken(7)
  end
end
`
	if err := os.WriteFile(source, []byte(program), 0600); err != nil {
		t.Fatal(err)
	}
	if err := BuildTo(source, binary); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	output, _ := exec.CommandContext(ctx, binary).CombinedOutput()
	want := fmt.Sprintf("%[1]s:19:40: process mailbox type already fixed\n", source)
	if string(output) != want {
		t.Fatalf("got %q want %q", output, want)
	}
	program = strings.Replace(program, "    counts: pid[map[string,integer]] = Process.self(1)\n", "    IO.puts(\"started\")\n", 1)
	if err := os.WriteFile(source, []byte(program), 0600); err != nil {
		t.Fatal(err)
	}
	if err := BuildTo(source, binary); err != nil {
		t.Fatal(err)
	}
	// The build above may use up the first run's deadline on a slow machine.
	second, cancelSecond := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancelSecond()
	output, _ = exec.CommandContext(second, binary).CombinedOutput()
	// The Go toolchain may normalize separators in frame file names.
	want = filepath.ToSlash(fmt.Sprintf("started\n%[1]s:10:21: division by zero\n  at Frames.broken (%[1]s:10)\n  at Frames.main (%[1]s:20)\n", source))
	if filepath.ToSlash(string(output)) != want {
		t.Fatalf("got %q want %q", output, want)
	}
}
