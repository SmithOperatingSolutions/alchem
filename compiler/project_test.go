package compiler

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestProject(t *testing.T) {
	d := t.TempDir()
	write := func(n, s string) {
		t.Helper()
		if err := os.WriteFile(filepath.Join(d, n), []byte(s), 0600); err != nil {
			t.Fatal(err)
		}
	}
	write("math.alc", `defmodule Math do def double(n: integer): integer do return n*2 end end`)
	write("main.alc", `defmodule App do import "math.alc" def main() do assert(Math.double(3)==6) assert(map([2],&Math.double)==[4]) IO.puts("project ready") end end`)
	binary := filepath.Join(d, "app")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	if err := BuildTo(filepath.Join(d, "main.alc"), binary); err != nil {
		t.Fatal(err)
	}
	out, err := exec.Command(binary).CombinedOutput()
	if err != nil || string(out) != "project ready\n" {
		t.Fatalf("%v %s", err, out)
	}
	write("math.alc", `defmodule Math do import "main.alc" def double(n: integer): integer do return n end end`)
	if err := BuildTo(filepath.Join(d, "main.alc"), binary); err == nil || !strings.Contains(err.Error(), "cycle") {
		t.Fatalf("got %v", err)
	}
}

func TestProjectFailures(t *testing.T) {
	cases := []struct{ name, main, library, want string }{
		{"missing", `defmodule A do import "absent.alc" def main() do assert(true) end end`, "", "read source"},
		{"duplicate", `defmodule A do import "lib.alc" def main() do assert(true) end end`, `defmodule A do def value(): integer do return 1 end end`, "duplicate module"},
		{"reserved", `defmodule A do import "lib.alc" def main() do assert(true) end end`, `defmodule List do def value(): integer do return 1 end end`, "reserved module name List"},
		{"reserved string", `defmodule A do import "lib.alc" def main() do assert(true) end end`, `defmodule String do def value(): integer do return 1 end end`, "reserved module name String"},
		{"reserved file", `defmodule A do import "lib.alc" def main() do assert(true) end end`, `defmodule File do def value(): integer do return 1 end end`, "reserved module name File"},
		{"reserved system", `defmodule A do import "lib.alc" def main() do assert(true) end end`, `defmodule System do def value(): integer do return 1 end end`, "reserved module name System"},
		{"reserved time", `defmodule A do import "lib.alc" def main() do assert(true) end end`, `defmodule Time do def value(): integer do return 1 end end`, "reserved module name Time"},
		{"visibility", `defmodule A do def main() do assert(B.value()==1) end end`, "", "not imported"},
		{"library main", `defmodule A do import "lib.alc" def main() do assert(true) end end`, `defmodule B do def main() do assert(true) end end`, "cannot define main"},
		{"duplicate function", `defmodule A do import "lib.alc" def main() do assert(true) end end`, `defmodule B do def value(): integer do return 1 end def value(): integer do return 2 end end`, "duplicate function"},
		{"bad return", `defmodule A do import "lib.alc" def main() do assert(true) end end`, `defmodule B do def value(): boolean do return 1 end end`, "expected boolean"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			d := t.TempDir()
			entry := filepath.Join(d, "main.alc")
			os.WriteFile(entry, []byte(tc.main), 0600)
			os.WriteFile(filepath.Join(d, "lib.alc"), []byte(tc.library), 0600)
			err := Check(entry)
			if err == nil || !strings.Contains(err.Error(), tc.want) {
				t.Fatalf("got %v", err)
			}
			if tc.name == "bad return" || tc.name == "duplicate function" {
				diag := Describe(err)
				if diag.File != filepath.Join(d, "lib.alc") || diag.Line < 1 {
					t.Fatalf("%+v", diag)
				}
			}
		})
	}
}

func TestImportedRuntimeFrames(t *testing.T) {
	d := t.TempDir()
	library := filepath.Join(d, "lib.alc")
	entry := filepath.Join(d, "main.alc")
	binary := filepath.Join(d, "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	os.WriteFile(library, []byte("defmodule Library do\n def broken(): integer do\n  return 1 / 0\n end\nend\n"), 0600)
	os.WriteFile(entry, []byte("defmodule App do\n import \"lib.alc\"\n def main() do\n  result = Library.broken()\n end\nend\n"), 0600)
	if err := BuildTo(entry, binary); err != nil {
		t.Fatal(err)
	}
	out, err := exec.Command(binary).CombinedOutput()
	if err == nil || !strings.HasPrefix(string(out), library+":3:12: division by zero\n") || !strings.Contains(string(out), "Library.broken") || !strings.Contains(string(out), "App.main") || strings.Contains(string(out), "alchem-build-") {
		t.Fatalf("%v\n%s", err, out)
	}
}
func TestIntegratedModuleRuntime(t *testing.T) {
	binary := filepath.Join(t.TempDir(), "system")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	err := BuildWithOptions("../examples/system", BuildOptions{Output: binary, Race: true})
	if err != nil && strings.Contains(err.Error(), "-race is not supported") {
		// The Go toolchain has no race detector for some targets (for example
		// windows/arm64); the example must still build and run there.
		t.Logf("race detector unavailable on %s/%s, building without it", runtime.GOOS, runtime.GOARCH)
		err = BuildWithOptions("../examples/system", BuildOptions{Output: binary})
	}
	if err != nil {
		t.Fatal(err)
	}
	out, err := exec.Command(binary).CombinedOutput()
	if err != nil || string(out) != "system ready\n" {
		t.Fatalf("%v\n%s", err, out)
	}
}

func TestStructuredImportPositions(t *testing.T) {
	d := t.TempDir()
	entry := filepath.Join(d, "main.alc")
	os.WriteFile(entry, []byte("defmodule App do\n  import \"missing.alc\"\n  def main() do assert(true) end\nend\n"), 0600)
	diag := Describe(Check(entry))
	if diag.File != entry || diag.Line != 2 || diag.Column != 3 {
		t.Fatalf("%+v", diag)
	}
	library := filepath.Join(d, "missing.alc")
	os.WriteFile(library, []byte("defmodule Library do\n def invalid( do end\nend"), 0600)
	diag = Describe(Check(entry))
	if diag.File != library || diag.Line != 2 {
		t.Fatalf("lost imported source: %+v", diag)
	}
}

// Two processes prepend to the same shared list at the same time. Built with
// the race detector where it exists, so an unsafe in-place extension fails.
func TestSharedListPrependsAreRaceFree(t *testing.T) {
	d := t.TempDir()
	binary := filepath.Join(d, "program")
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	source := filepath.Join("..", "tests", "fixtures", "list_sharing.alc")
	err := BuildWithOptions(source, BuildOptions{Output: binary, Race: true})
	if err != nil && strings.Contains(err.Error(), "-race is not supported") {
		err = BuildWithOptions(source, BuildOptions{Output: binary})
	}
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 20; i++ {
		out, err := exec.Command(binary).CombinedOutput()
		if err != nil || !strings.HasSuffix(string(out), "lists shared safely\n") {
			t.Fatalf("run %d: %v\n%s", i, err, out)
		}
	}
}
