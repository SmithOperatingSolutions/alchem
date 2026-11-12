package testrunner

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func fixture(t *testing.T, name, source string) string {
	t.Helper()
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, name+".alc"), []byte(source), 0600); err != nil {
		t.Fatal(err)
	}
	return dir
}

func TestRunHelloFixture(t *testing.T) {
	if err := Run(filepath.Join("..", "tests", "fixtures")); err != nil {
		t.Fatal(err)
	}
}
func TestRunMissingDirectory(t *testing.T) {
	if err := Run(filepath.Join(t.TempDir(), "missing")); err == nil {
		t.Fatal("expected error")
	}
}
func TestRunMismatchedOutput(t *testing.T) {
	dir := fixture(t, "hello", "defmodule Hello do def main() do IO.puts(\"actual\") end end")
	if err := os.WriteFile(filepath.Join(dir, "hello.stdout"), []byte("expected\n"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := Run(dir); err == nil || !strings.Contains(err.Error(), "output mismatch") {
		t.Fatalf("expected output mismatch, got %v", err)
	}
}
func TestRunRejectsUnexpectedAssertionFailure(t *testing.T) {
	dir := fixture(t, "broken.test", "defmodule Broken do def main() do assert(false) end end")
	if err := Run(dir); err == nil || !strings.Contains(err.Error(), "exit code") {
		t.Fatalf("expected failure, got %v", err)
	}
}
func TestRunRejectsWrongExpectedExitCode(t *testing.T) {
	dir := fixture(t, "good.test", "defmodule Good do def main() do assert(true) end end")
	if err := os.WriteFile(filepath.Join(dir, "good.test.exitcode"), []byte("2\n"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := Run(dir); err == nil || !strings.Contains(err.Error(), "exit code") {
		t.Fatalf("expected mismatch, got %v", err)
	}
}
func TestRunRejectsInvalidExitCode(t *testing.T) {
	dir := fixture(t, "good.test", "defmodule Good do def main() do assert(true) end end")
	if err := os.WriteFile(filepath.Join(dir, "good.test.exitcode"), []byte("invalid\n"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := Run(dir); err == nil || !strings.Contains(err.Error(), "invalid exitcode") {
		t.Fatalf("expected invalid exitcode, got %v", err)
	}
}

func TestRunChecksStderrSidecar(t *testing.T) {
	dir := fixture(t, "good.test", "defmodule Good do def main() do assert(true) end end")
	if err := os.WriteFile(filepath.Join(dir, "good.test.stderr"), []byte("missing diagnostic"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := Run(dir); err == nil || !strings.Contains(err.Error(), "stderr mismatch") {
		t.Fatalf("expected stderr mismatch, got %v", err)
	}
}
