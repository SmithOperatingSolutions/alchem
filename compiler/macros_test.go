package compiler

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

// testdata/macros has a module of macros and a program that uses them:
// macros as values and as statements, with blocks, calling functions of
// their own module, built on other macros, and use with an option. A name
// the template binds must not disturb the same name at the call.
func TestMacrosAcrossModules(t *testing.T) {
	if testing.Short() {
		t.Skip("builds and runs a program")
	}
	binary := filepath.Join(t.TempDir(), "macros")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	if err := BuildTo(filepath.Join("testdata", "macros", "main.alc"), binary); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	got, err := exec.CommandContext(ctx, binary).CombinedOutput()
	want := "36 8\n[first] 10\n[second] 15\nstill 5\nsum 500500\nloop took under a second: true\nhas items\nhello, ada\nHELLO, BO[!] 1\n"
	if err != nil || strings.ReplaceAll(string(got), "\r\n", "\n") != want {
		t.Fatalf("err=%v\ngot:\n%s\nwant:\n%s", err, got, want)
	}
	for _, name := range []string{"main.alc", "tools.alc"} {
		source, err := os.ReadFile(filepath.Join("testdata", "macros", name))
		if err != nil {
			t.Fatal(err)
		}
		if formatted, err := Format(string(source)); err != nil || formatted != string(source) {
			t.Errorf("%s is not as the formatter writes it: %v", name, err)
		}
	}
}

func TestMacroDiagnostics(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "main.alc")
	macros := "  defmacro twice(value) do\n    quote do\n      unquote(value) + unquote(value)\n    end\n  end\n\n" +
		"  defmacro report(value) do\n    quote do\n      shown = unquote(value)\n      IO.puts(\"#{shown}\")\n    end\n  end\n\n" +
		"  defmacro wrap(do: body) do\n    quote do\n      IO.puts(\"before\")\n      unquote(body)\n    end\n  end\n\n" +
		"  defmacro forever(value) do\n    quote do\n      forever(unquote(value))\n    end\n  end\n\n"
	check := func(body, extra string) string {
		source := "defmodule T do\n" + extra + macros + "  def main() do\n" + body + "  end\nend\n"
		if err := os.WriteFile(path, []byte(source), 0600); err != nil {
			t.Fatal(err)
		}
		if err := Check(path); err != nil {
			return err.Error()
		}
		return ""
	}
	cases := map[string][2]string{
		"works":               {"    IO.puts(\"#{twice(2)}\")\n    report(3)\n    wrap() do\n      IO.puts(\"inside\")\n    end\n", ""},
		"argument count":      {"    IO.puts(\"#{twice(1, 2)}\")\n", "twice takes 1 arguments, not 2"},
		"statements as value": {"    IO.puts(\"#{report(1)}\")\n", "report expands to 2 statements, so it is used as a statement"},
		"block missing":       {"    wrap()\n", "wrap takes a do ... end block"},
		"block not taken":     {"    report(1) do\n      IO.puts(\"x\")\n    end\n", "report does not take a do ... end block"},
		"block on function":   {"    IO.puts(\"x\") do\n      IO.puts(\"y\")\n    end\n", "only a macro takes a do ... end block"},
		"endless":             {"    forever(1)\n", "forever keeps expanding into more macro calls"},
		// What a macro expands to is typed like any other code, and a
		// problem is reported where the macro was called.
		"typed after": {"    IO.puts(\"#{twice(\"a\")}\")\n", "main.alc:29:16: arithmetic requires integers or floats"},
	}
	for name, test := range cases {
		got := check(test[0], "")
		if (test[1] == "") != (got == "") || !strings.Contains(got, test[1]) {
			t.Errorf("%s: got %q, want %q", name, got, test[1])
		}
	}
	if got := check("    IO.puts(\"x\")\n", "  use Nowhere\n"); !strings.Contains(got, "use Nowhere: no imported module has that name") {
		t.Errorf("use of an unknown module: %q", got)
	}
}
