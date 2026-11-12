package main

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestNewProjectRunsAndTests(t *testing.T) {
	root := filepath.Join(t.TempDir(), "word_count")
	var out, errOut bytes.Buffer
	invoke := func(args ...string) int {
		out.Reset()
		errOut.Reset()
		return run(context.Background(), args, &out, &errOut)
	}
	if code := invoke("new", root); code != 0 {
		t.Fatal(errOut.String())
	}
	if invoke("new", root) == 0 {
		t.Fatal("new overwrote an existing directory")
	}
	if invoke("new", filepath.Join(t.TempDir(), "9lives")) == 0 {
		t.Fatal("accepted a name that is not a module name")
	}
	library, err := os.ReadFile(filepath.Join(root, "lib", "word_count.alc"))
	if err != nil || !strings.Contains(string(library), "defmodule WordCount do") {
		t.Fatalf("library: %v %s", err, library)
	}
	if code := invoke("fmt", "--check", root); code != 0 {
		t.Fatalf("generated files are not formatted: %s", out.String())
	}
	entry := filepath.Join(root, "main.alc")
	if code := invoke("run", entry); code != 0 || out.String() != "Hello, world!\n" {
		t.Fatalf("run: %d %q %s", code, out.String(), errOut.String())
	}
	if code := invoke("run", entry, "--", "Ada"); code != 0 || out.String() != "Hello, Ada!\n" {
		t.Fatalf("run with arguments: %d %q %s", code, out.String(), errOut.String())
	}
	if code := invoke("test", filepath.Join(root, "test")); code != 0 || !strings.Contains(out.String(), "2 tests, 0 failures") {
		t.Fatalf("test: %d %s %s", code, out.String(), errOut.String())
	}
}

func TestRunPassesExitStatus(t *testing.T) {
	path := filepath.Join(t.TempDir(), "main.alc")
	os.WriteFile(path, []byte(`defmodule App do
  def main() do
    IO.puts(Enum.join(System.argv(), "+"))
    System.halt(3)
  end
end
`), 0600)
	var out, errOut bytes.Buffer
	if code := run(context.Background(), []string{"run", path, "a", "b"}, &out, &errOut); code != 3 || out.String() != "a+b\n" {
		t.Fatalf("got %d %q %s", code, out.String(), errOut.String())
	}
	if code := run(context.Background(), []string{"run", filepath.Join(t.TempDir(), "missing.alc")}, &out, &errOut); code == 0 {
		t.Fatal("ran a missing program")
	}
}

func TestShellSession(t *testing.T) {
	previous, _ := os.Getwd()
	os.Chdir(t.TempDir())
	defer os.Chdir(previous)
	var out bytes.Buffer
	input := strings.NewReader("x = 2\ndef sq(n: integer): integer do\n  n * n\nend\nsq(x)\nh Enum.sum\nbogus\n:quit\n")
	if code := shell(context.Background(), input, &out); code != 0 {
		t.Fatal(out.String())
	}
	text := out.String()
	for _, want := range []string{"alx(1)> 2\n", "...(2)> ...(2)> :ok\n", "alx(3)> 4\n", "Enum.sum(enum[a]) -> a", "** line 1: undefined binding bogus"} {
		if !strings.Contains(text, want) {
			t.Fatalf("missing %q in\n%s", want, text)
		}
	}
}
