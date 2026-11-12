package main

import (
	"bytes"
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Each command's mistakes are reported with an exit status, and its less
// common options work.
func TestCommandErrorsAndOptions(t *testing.T) {
	dir := t.TempDir()
	good := filepath.Join(dir, "good.alc")
	os.WriteFile(good, []byte("defmodule Good do\n  def main() do\n    IO.puts(\"good\")\n  end\nend\n"), 0o644)
	bad := filepath.Join(dir, "bad.alc")
	os.WriteFile(bad, []byte("defmodule Bad do\n  def main() do\n    x = nope\n  end\nend\n"), 0o644)
	tagged := filepath.Join(dir, "tagged_test.alc")
	os.WriteFile(tagged, []byte("defmodule TaggedTest do\n  @tag :slow\n  test \"slow\" do\n    assert(true)\n  end\n\n  test \"failing\" do\n    assert(false)\n  end\nend\n"), 0o644)
	empty := filepath.Join(dir, "empty")
	os.Mkdir(empty, 0o755)
	hidden := filepath.Join(dir, "tree")
	os.MkdirAll(filepath.Join(hidden, ".git"), 0o755)
	os.MkdirAll(filepath.Join(hidden, "artifacts"), 0o755)
	os.WriteFile(filepath.Join(hidden, ".git", "skip.alc"), []byte("not alchem"), 0o644)
	os.WriteFile(filepath.Join(hidden, "keep.alc"), []byte("defmodule K do\n  def main() do\n      IO.puts(\"x\")\n  end\nend\n"), 0o644)
	os.WriteFile(filepath.Join(hidden, "notes.txt"), []byte("x"), 0o644)
	broken := filepath.Join(dir, "broken.alc")
	os.WriteFile(broken, []byte("defmodule B do\n  def main( do\nend\n"), 0o644)
	link := filepath.Join(dir, "link.alc")
	linked := "regular file"
	if os.Symlink(good, link) != nil {
		linked = "" // Windows may not allow symbolic links
	}
	unformatted := filepath.Join(dir, "unformatted.alc")
	os.WriteFile(unformatted, []byte("defmodule U do\n  def main() do\n      IO.puts(\"x\")\n  end\nend\n"), 0o644)

	for _, c := range []struct {
		args   []string
		code   int
		output string
	}{
		{[]string{}, 2, "usage"},
		{[]string{"--help"}, 0, "usage"},
		{[]string{"nonsense"}, 2, "unknown command"},
		{[]string{"build", "--no-such-flag"}, 2, ""},
		{[]string{"build", "-h"}, 0, ""},
		{[]string{"run"}, 2, "provide the program to run"},
		{[]string{"new"}, 2, "provide the directory"},
		{[]string{"new", good}, 1, ""},
		{[]string{"build"}, 2, "provide one entry path"},
		{[]string{"check", good, bad}, 2, "provide one entry path"},
		{[]string{"build", "-target", "linux", good}, 2, "GOOS/GOARCH"},
		{[]string{"check", bad}, 1, "undefined binding nope"},
		{[]string{"check", "-json", bad}, 1, "\"line\""},
		{[]string{"check", good}, 0, ""},
		{[]string{"test", "-tag", "slow", tagged}, 0, "1 test, 0 failures"},
		{[]string{"test", "-exclude", "slow", tagged}, 1, "1 failure"},
		{[]string{"fmt", empty}, 1, "no .alc files"},
		{[]string{"fmt", "-check", unformatted}, 1, "unformatted.alc"},
		{[]string{"fmt", filepath.Join(dir, "missing.alc")}, 1, ""},
		{[]string{"syntax", "no-such-topic"}, 1, ""},
		{[]string{"syntax", "a", "b"}, 1, "takes one argument"},
		{[]string{"doc", "No.such_function"}, 1, ""},
		{[]string{"fmt", hidden}, 0, "keep.alc"},
		{[]string{"fmt", broken}, 1, "broken.alc"},
		{[]string{"fmt", link}, 1, linked},
		{[]string{"test", empty}, 1, "no test files"},
		{[]string{"syntax", "-all"}, 0, ""},
		{[]string{"syntax", "-json", "case"}, 0, "{"},
		{[]string{"doc", "-search", "length"}, 0, "String.length"},
		{[]string{"agent-install", "-list"}, 0, ""},
		{[]string{"agent-install"}, 1, "name an agent"},
		{[]string{"build", "-target", "linux/amd64", "-o", filepath.Join(dir, "good.bin"), good}, 0, ""},
		{[]string{"run", good}, 0, "good"},
		{[]string{"run", bad}, 1, "undefined binding nope"},
	} {
		var out, errOut bytes.Buffer
		code := run(context.Background(), c.args, &out, &errOut)
		text := out.String() + errOut.String()
		if code != c.code || !strings.Contains(strings.ToLower(text), strings.ToLower(c.output)) {
			t.Errorf("alchem %s: status %d, want %d; output:\n%s", strings.Join(c.args, " "), code, c.code, text)
		}
	}
}
