package main

import (
	"bufio"
	"bytes"
	"context"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"
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

// Ending alchem run ends the program it started, and waits for it: the
// program is not left running as an orphan.
func TestRunEndsItsProgramWhenEnded(t *testing.T) {
	if testing.Short() {
		t.Skip("builds and runs a program")
	}
	path := filepath.Join(t.TempDir(), "waits.alc")
	if err := os.WriteFile(path, []byte("defmodule Waits do\n  def main() do\n    IO.puts(System.pid())\n    Process.sleep(60000)\n  end\nend\n"), 0600); err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	reader, writer := io.Pipe()
	done := make(chan int, 1)
	go func() {
		var errOut bytes.Buffer
		done <- run(ctx, []string{"run", path}, writer, &errOut)
		writer.Close()
	}()
	line, err := bufio.NewReader(reader).ReadString('\n')
	if err != nil {
		t.Fatalf("the program did not start: %v", err)
	}
	pid, err := strconv.Atoi(strings.TrimSpace(line))
	if err != nil {
		t.Fatalf("the program printed %q", line)
	}
	go io.Copy(io.Discard, reader)
	started := time.Now()
	cancel()
	select {
	case code := <-done:
		if code == 0 {
			t.Fatalf("alchem run reported success after being ended")
		}
	case <-time.After(20 * time.Second):
		t.Fatal("alchem run did not end")
	}
	if waited := time.Since(started); waited > 15*time.Second {
		t.Fatalf("ending took %v", waited)
	}
	// The run returned only after the program was waited for, so the
	// program is gone; on Unix a signal 0 confirms it.
	if runtime.GOOS != "windows" {
		if process, err := os.FindProcess(pid); err == nil && process.Signal(syscall.Signal(0)) == nil {
			process.Kill()
			t.Fatalf("the program (pid %d) is still running", pid)
		}
	}
}
