package compiler

import (
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestBuildHelloExecutable(t *testing.T) {
	if _, err := exec.LookPath("go"); err != nil {
		t.Skip("Go toolchain unavailable")
	}
	dir := t.TempDir()
	source := filepath.Join(dir, "hello.alc")
	program := "defmodule Hello do\n def main() do\n IO.puts(\"Hello from Alchem!\")\n end\nend"
	if err := os.WriteFile(source, []byte(program), 0600); err != nil {
		t.Fatal(err)
	}
	old, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(dir); err != nil {
		t.Fatal(err)
	}
	defer os.Chdir(old)
	if err := Build(source); err != nil {
		t.Fatal(err)
	}
	binary := "hello"
	if runtime.GOOS == "windows" {
		binary += ".exe"
	}
	output, err := exec.Command(filepath.Join(dir, binary)).CombinedOutput()
	if err != nil {
		t.Fatalf("run: %v: %s", err, output)
	}
	if string(output) != "Hello from Alchem!\n" {
		t.Fatalf("unexpected output: %q", output)
	}
}

func TestBuildRejectsInvalidSource(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "bad.alc")
	if err := os.WriteFile(source, []byte("not alchem"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := Build(source); err == nil || !strings.Contains(err.Error(), "unsupported syntax") {
		t.Fatalf("unexpected error: %v", err)
	}
}
